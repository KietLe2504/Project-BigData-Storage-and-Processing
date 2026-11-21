"""M4: Kafka flight observations -> event-time KPI windows -> M5 MongoDB.

Spark target: 3.5.3 (spark-sql-kafka-0-10_2.12:3.5.3)

Each event is expanded into the eight grouping sets for carrier, origin and
 destination. One streaming aggregation then maintains a separate full-window
 aggregate for each grouping. MongoDB stores a flat record for the M5 Streaming
 table: pipeline_id, date, window_start, window_end, revision, carrier, origin,
 dest and the KPI fields. Missing dimensions are stored as ".". The source is
 retained as metadata for provenance and source-specific record identity.

Flight counting is distinct by flight_key within each source/window/group.
When more than one observation for a flight occurs in that window, the latest
(event_time, event_id) observation supplies its status and departure delay.
"""

from __future__ import annotations

import math
import os
from datetime import datetime, timezone
from typing import Any

from pymongo.errors import DuplicateKeyError

from pyspark.sql import DataFrame, SparkSession, functions as F
from pyspark.sql.types import (
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
)

from m5.mongo import connect
from m5.stream_writer import normalize


EVENT_SCHEMA = StructType(
    [
        StructField("schema_version", IntegerType(), True),
        StructField("source", StringType(), True),
        StructField("event_type", StringType(), True),
        StructField("observed_at", StringType(), True),
        StructField("flight_key", StringType(), True),
        StructField("event_id", StringType(), True),
        StructField("airline_iata", StringType(), True),
        StructField("flight_status", StringType(), True),
        StructField("departure_iata", StringType(), True),
        StructField("arrival_iata", StringType(), True),
        StructField("departure_scheduled", StringType(), True),
        StructField("departure_delay", DoubleType(), True),
    ]
)


PIPELINE_ID = os.getenv("M4_PIPELINE_ID", "m4-flight-status-v1")
WINDOW_DURATION = os.getenv("M4_WINDOW_DURATION", "5 minutes")
WATERMARK_DELAY = os.getenv("M4_WATERMARK_DELAY", "10 minutes")
PROCESSING_TIME = os.getenv("M4_PROCESSING_TIME", "10 seconds")
CHECKPOINT = os.getenv(
    "M4_CHECKPOINT",
    "hdfs://aero-namenode:9000/aero/checkpoints/m4/flight-status-v1",
)

# The values identify the grouping level for logging and validation. The M5
# document does not need a separate scope field: its dimensions keys encode it.
GROUPING_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "all": (),
    "carrier": ("carrier",),
    "dest": ("dest",),
    "origin": ("origin",),
    "carrier_dest": ("carrier", "dest"),
    "carrier_origin": ("carrier", "origin"),
    "origin_dest": ("origin", "dest"),
    "carrier_origin_dest": ("carrier", "origin", "dest"),
}


def utc_iso(value) -> str:
    """Format Spark's Python datetime as an explicit UTC ISO timestamp."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


FLAT_PAYLOAD_FIELDS = (
    "pipeline_id",
    "source",
    "date",
    "window_start",
    "window_end",
    "carrier",
    "origin",
    "dest",
    "flights",
    "cancelled",
    "diverted",
    "on_time",
    "delayed15",
    "delayed60",
    "sum_dep_delay",
)


def same_aggregate(previous: dict[str, Any], candidate: dict[str, Any]) -> bool:
    """Compare flat logical fields, excluding revision and MongoDB _id."""
    return all(
        previous.get(field) == candidate.get(field)
        for field in FLAT_PAYLOAD_FIELDS
    )


def write_full_window_with_revision(db, record: dict[str, Any]) -> str:
    """Persist a flat full-window record with a durable, replay-safe revision.

    ``record["_identity"]`` is the legacy M5 logical identity payload. Passing it
    through normalize() preserves the existing _id semantics (pipeline, source,
    full event-time window and actual dimension keys), while the stored document
    itself uses the flat v3 schema.
    """
    collection = db.stream_window_kpi
    identity = normalize({**record["_identity"], "revision": 0})
    logical_id = identity["_id"]
    flat_payload = record["document"]

    # Optimistic compare-and-replace avoids silently overwriting a concurrent
    # revision. A duplicate insert means another writer won the first-write race;
    # re-read and retry using its revision.
    for _ in range(10):
        previous = collection.find_one({"_id": logical_id})
        if previous is not None and same_aggregate(previous, flat_payload):
            return "unchanged"

        next_revision = 1 if previous is None else int(previous.get("revision", 0)) + 1
        document = {
            "_id": logical_id,
            **flat_payload,
            "revision": next_revision,
        }

        if previous is None:
            try:
                collection.insert_one(document)
                return "inserted"
            except DuplicateKeyError:
                continue

        result = collection.replace_one(
            {"_id": logical_id, "revision": previous.get("revision")},
            document,
            upsert=False,
        )
        if result.matched_count == 1:
            return "updated"

    raise RuntimeError(
        f"Could not persist M4 window after concurrent revision retries: {logical_id}"
    )


def _utc_window_parts(value) -> tuple[str, str]:
    """Return (UTC date, UTC clock time) for a Spark window timestamp."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    value = value.astimezone(timezone.utc)
    return value.strftime("%Y-%m-%d"), value.strftime("%H:%M:%S")


def latest_by_flight(observations) -> dict[str, Any]:
    """Return one latest observation per flight_key in a window/group."""
    latest: dict[str, tuple[tuple[Any, str], Any]] = {}
    for event in observations or []:
        key = event.flight_key
        if not key:
            continue

        # event_id provides deterministic tie-breaking for equal event timestamps.
        rank = (event.event_time, event.event_id or "")
        previous = latest.get(key)
        if previous is None or rank > previous[0]:
            latest[key] = (rank, event)

    return {key: item[1] for key, item in latest.items()}


def make_record(row) -> dict[str, Any] | None:
    """Build the flat v3 MongoDB document and its stable logical identity."""
    latest = latest_by_flight(row.observations)
    if not latest:
        return None

    statuses = {
        key: (event.flight_status or "").strip().lower()
        for key, event in latest.items()
    }

    cancelled = sum(status in ("cancelled", "canceled") for status in statuses.values())
    diverted = sum(status == "diverted" for status in statuses.values())

    # Punctuality metrics require both a valid scheduled departure timestamp and
    # a finite reported departure_delay. departure_actual is deliberately unused:
    # the KPI is based on the available scheduled-time/delay fields.
    departure_delays: list[float] = []
    for event in latest.values():
        if not event.departure_scheduled_valid or event.departure_delay is None:
            continue

        delay = float(event.departure_delay)
        if math.isfinite(delay):
            departure_delays.append(delay)

    metrics = {
        "flights": int(len(latest)),
        "cancelled": int(cancelled),
        "diverted": int(diverted),
        # Thresholds are cumulative: a 60+ minute delay contributes to both
        # delayed15 and delayed60. Negative/zero delays are classified as on-time.
        "on_time": int(sum(delay < 15 for delay in departure_delays)),
        "delayed15": int(sum(delay >= 15 for delay in departure_delays)),
        "delayed60": int(sum(delay >= 60 for delay in departure_delays)),
        # Sum positive delay minutes only; early departures count as on-time but
        # do not subtract minutes from the delay total.
        "sum_dep_delay": float(sum(max(delay, 0.0) for delay in departure_delays)),
    }

    dimensions: dict[str, str] = {}
    for key in ("carrier", "origin", "dest"):
        value = getattr(row, key)
        if value is not None:
            normalized_value = str(value).strip()
            if normalized_value:
                dimensions[key] = normalized_value

    # The grouping expansion ensures only the dimensions selected by this
    # grouping level are non-null. Validate the logical grouping before flattening.
    expected = set(GROUPING_REQUIREMENTS[row.scope])
    if set(dimensions) != expected:
        raise ValueError(
            f"Invalid dimensions for scope={row.scope}: "
            f"expected={sorted(expected)}, actual={sorted(dimensions)}"
        )

    window_start_iso = utc_iso(row.window.start)
    window_end_iso = utc_iso(row.window.end)
    date, window_start_time = _utc_window_parts(row.window.start)
    _, window_end_time = _utc_window_parts(row.window.end)

    # Keep the previous logical identity convention so source-specific records
    # and the full window remain distinct even though the displayed schema has
    # separate date/time columns and omits source from the visible table.
    identity = {
        "pipeline_id": PIPELINE_ID,
        "source": row.source,
        "window_start": window_start_iso,
        "window_end": window_end_iso,
        "revision": 0,
        "dimensions": dimensions,
        "metrics": metrics,
    }

    # The web table can select these fields in this exact order. Missing
    # dimensions are represented by a literal period, not null or JSON text.
    document = {
        "pipeline_id": PIPELINE_ID,
        "source": row.source,  # metadata; omit from the visible 15-column table
        "date": date,
        "window_start": window_start_time,
        "window_end": window_end_time,
        "revision": 0,  # replaced with the durable MongoDB revision on write
        "carrier": dimensions.get("carrier", "."),
        "origin": dimensions.get("origin", "."),
        "dest": dimensions.get("dest", "."),
        **metrics,
        # Metadata used by the M5 dashboard to show the latest ingestion/update time.
        "ingested_at": datetime.now(timezone.utc),
    }

    return {"_identity": identity, "document": document}


def write_batch(batch_df: DataFrame, batch_id: int) -> None:
    """Write changed windows as full aggregates; safe for Spark batch replay."""
    if batch_df.isEmpty():
        print(f"M4 batch_id={batch_id}: no updated windows")
        return

    client, db = connect()
    written = 0
    unchanged = 0
    try:
        for row in batch_df.toLocalIterator():
            record = make_record(row)
            if record is None:
                continue

            result = write_full_window_with_revision(db, record)
            if result == "unchanged":
                unchanged += 1
            else:
                written += 1

            print(
                "M4_WINDOW",
                f"scope={row.scope}",
                f"date={record['document']['date']}",
                f"window_start={record['document']['window_start']}",
                f"window_end={record['document']['window_end']}",
                f"carrier={record['document']['carrier']}",
                f"origin={record['document']['origin']}",
                f"dest={record['document']['dest']}",
                f"result={result}",
            )
    finally:
        client.close()

    print(
        f"M4 batch_id={batch_id}: changed_or_written={written}, "
        f"unchanged_replays={unchanged}"
    )


def _dimension_expression(column_name: str):
    """Normalize blank IATA codes to null before creating grouping sets."""
    value = F.trim(F.col(column_name))
    return F.when(F.length(value) > 0, value).otherwise(F.lit(None).cast(StringType()))


def _grouping_struct(scope: str, carrier, origin, dest):
    return F.struct(
        F.lit(scope).alias("scope"),
        carrier.alias("carrier"),
        origin.alias("origin"),
        dest.alias("dest"),
    )


def build_windowed_events(parsed: DataFrame) -> DataFrame:
    """Expand every event into available grouping sets and aggregate by window."""
    normalized = (
        parsed.withColumn("carrier", _dimension_expression("airline_iata"))
        .withColumn("origin", _dimension_expression("departure_iata"))
        .withColumn("dest", _dimension_expression("arrival_iata"))
        .withColumn(
            "departure_scheduled_valid",
            F.to_timestamp(F.col("departure_scheduled")).isNotNull(),
        )
    )

    null_string = F.lit(None).cast(StringType())
    grouping_sets = F.array(
        _grouping_struct("all", null_string, null_string, null_string),
        _grouping_struct("carrier", F.col("carrier"), null_string, null_string),
        _grouping_struct("dest", null_string, null_string, F.col("dest")),
        _grouping_struct("origin", null_string, F.col("origin"), null_string),
        _grouping_struct("carrier_dest", F.col("carrier"), null_string, F.col("dest")),
        _grouping_struct("carrier_origin", F.col("carrier"), F.col("origin"), null_string),
        _grouping_struct("origin_dest", null_string, F.col("origin"), F.col("dest")),
        _grouping_struct(
            "carrier_origin_dest", F.col("carrier"), F.col("origin"), F.col("dest")
        ),
    )

    expanded = (
        normalized.withColumn("grouping", F.explode(grouping_sets))
        .select(
            "event_time",
            "source",
            "flight_key",
            "event_id",
            "flight_status",
            "departure_scheduled_valid",
            "departure_delay",
            F.col("grouping.scope").alias("scope"),
            F.col("grouping.carrier").alias("carrier"),
            F.col("grouping.origin").alias("origin"),
            F.col("grouping.dest").alias("dest"),
        )
    )

    # A grouping level that includes a dimension requires that source dimension.
    # For example, a missing carrier still contributes to all/origin/dest groups,
    # but cannot form a carrier or carrier-combination group.
    valid_grouping = F.lit(False)
    for scope, required_dimensions in GROUPING_REQUIREMENTS.items():
        condition = F.col("scope") == F.lit(scope)
        for dimension in required_dimensions:
            condition = condition & F.col(dimension).isNotNull()
        valid_grouping = valid_grouping | condition

    observations = F.struct(
        F.col("event_time").alias("event_time"),
        F.col("flight_key").alias("flight_key"),
        F.col("event_id").alias("event_id"),
        F.col("flight_status").alias("flight_status"),
        F.col("departure_scheduled_valid").alias("departure_scheduled_valid"),
        F.col("departure_delay").alias("departure_delay"),
    )

    return (
        expanded.where(valid_grouping)
        .groupBy(
            F.window(F.col("event_time"), WINDOW_DURATION).alias("window"),
            F.col("source"),
            F.col("scope"),
            F.col("carrier"),
            F.col("origin"),
            F.col("dest"),
        )
        .agg(F.collect_list(observations).alias("observations"))
    )


def main() -> None:
    kafka_bootstrap = os.getenv("M4_KAFKA_BOOTSTRAP", "kafka:9092")
    kafka_topic = os.getenv("M4_KAFKA_TOPIC", "flight-realtime")
    allowed_sources = [
        value.strip()
        for value in os.getenv("M4_ALLOWED_SOURCES", "aviationstack").split(",")
        if value.strip()
    ]
    if not allowed_sources or any(
        value not in ("aviationstack", "simulated") for value in allowed_sources
    ):
        raise ValueError(
            "M4_ALLOWED_SOURCES may contain only aviationstack and/or simulated"
        )

    shuffle_partitions = os.getenv("M4_SHUFFLE_PARTITIONS", "3")
    starting_offsets = os.getenv("M4_STARTING_OFFSETS", "earliest")

    spark = (
        SparkSession.builder.appName("AERO-M4-Flight-Status-Streaming")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", shuffle_partitions)
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    kafka_rows = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", kafka_bootstrap)
        .option("subscribe", kafka_topic)
        .option("startingOffsets", starting_offsets)
        .load()
    )

    parsed = (
        kafka_rows.select(F.col("value").cast("string").alias("json"))
        .select(F.from_json(F.col("json"), EVENT_SCHEMA).alias("event"))
        .select("event.*")
        .withColumn("event_time", F.to_timestamp(F.col("observed_at")))
        .where(
            (F.col("schema_version") == 1)
            & (F.col("event_type") == "flight_status_observation")
            & F.col("source").isin(*allowed_sources)
            & F.col("flight_key").isNotNull()
            & (F.length(F.trim(F.col("flight_key"))) > 0)
            & F.col("event_time").isNotNull()
        )
        .withWatermark("event_time", WATERMARK_DELAY)
    )

    windowed = build_windowed_events(parsed)

    query = (
        windowed.writeStream.outputMode("update")
        .foreachBatch(write_batch)
        .option("checkpointLocation", CHECKPOINT)
        .trigger(processingTime=PROCESSING_TIME)
        .start()
    )

    print(
        "M4_STARTED",
        f"pipeline_id={PIPELINE_ID}",
        f"topic={kafka_topic}",
        f"bootstrap={kafka_bootstrap}",
        f"sources={allowed_sources}",
        f"window={WINDOW_DURATION}",
        f"watermark={WATERMARK_DELAY}",
        f"checkpoint={CHECKPOINT}",
        f"grouping_sets={len(GROUPING_REQUIREMENTS)}",
    )
    query.awaitTermination()


if __name__ == "__main__":
    main()
