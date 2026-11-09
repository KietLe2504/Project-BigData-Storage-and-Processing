"""Proposed M4 sink for FULL window aggregates, not deltas. See contract."""
import argparse
from datetime import datetime, timezone
import hashlib
import math

from pymongo.errors import DuplicateKeyError

from m5.contracts import canonical, strict_json
from m5.mongo import connect


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Window timestamps must contain a timezone")
    return parsed.astimezone(timezone.utc)


def normalize(record):
    if set(record) != {"pipeline_id", "source", "window_start", "window_end", "revision", "dimensions", "metrics"}:
        raise ValueError("Streaming record fields do not match M4_TO_M5.md")
    if record["source"] not in ("aviationstack", "simulated"):
        raise ValueError("source must be aviationstack or simulated")
    if not isinstance(record["pipeline_id"], str) or not record["pipeline_id"].strip():
        raise ValueError("pipeline_id is required")
    if type(record["revision"]) is not int or record["revision"] < 0:
        raise ValueError("revision must be a nonnegative, durable, monotonic integer")
    dimensions = record["dimensions"]
    if not isinstance(dimensions, dict) or set(dimensions) - {"carrier", "origin", "dest"}:
        raise ValueError("Unknown dimensions")
    if any(not isinstance(v, str) or not v.strip() for v in dimensions.values()):
        raise ValueError("Dimension values must be nonempty strings")
    metrics = record["metrics"]
    if not isinstance(metrics, dict) or not metrics or "flights" not in metrics:
        raise ValueError("Full metrics including flights are required")
    allowed = {"flights", "cancelled", "diverted", "arr_n", "on_time", "delayed15", "delayed60", "sum_arr_delay"}
    if set(metrics) - allowed:
        raise ValueError("Unsupported streaming metric")
    for key, value in metrics.items():
        if key == "sum_arr_delay":
            valid = type(value) in (int, float) and math.isfinite(value)
        else:
            valid = type(value) is int and 0 <= value < 2**63
        if not valid:
            raise ValueError(f"Invalid streaming metric: {key}")
    start, end = timestamp(record["window_start"]), timestamp(record["window_end"])
    if start >= end:
        raise ValueError("window_start must precede window_end")
    identity = [record["source"], record["pipeline_id"], start.isoformat(), end.isoformat(), dimensions]
    document = {**record, "_id": hashlib.sha256(canonical(identity).encode()).hexdigest(),
                "window_start": start, "window_end": end,
                "dimensions_key": canonical(dimensions),
                "payload_sha256": hashlib.sha256(canonical({**record,
                    "window_start": start.isoformat(), "window_end": end.isoformat()}).encode()).hexdigest(),
                "ingested_at": datetime.now(timezone.utc)}
    return document


def write_window(db, record):
    document = normalize(record)
    collection = db.stream_window_kpi
    collection.create_index([("source", 1), ("pipeline_id", 1), ("window_end", -1)], name="recent_windows")
    for _ in range(10):
        previous = collection.find_one({"_id": document["_id"]})
        if previous is None:
            try:
                collection.insert_one(document)
                return "inserted"
            except DuplicateKeyError:
                continue
        if previous["revision"] > document["revision"]:
            return "stale_ignored"
        if previous["revision"] == document["revision"]:
            if previous["payload_sha256"] != document["payload_sha256"]:
                raise ValueError("Same window/revision has conflicting payload")
            return "replay_ignored"
        result = collection.replace_one({"_id": document["_id"], "revision": previous["revision"]}, document)
        if result.matched_count:
            return "updated"
    raise RuntimeError("Concurrent updates did not settle; retry the same full aggregate")


def main():
    parser = argparse.ArgumentParser(description="Load FULL M4 window aggregates conforming to the proposed contract")
    parser.add_argument("--input", required=True)
    args = parser.parse_args()
    client, db = connect()
    try:
        with open(args.input, encoding="utf-8") as handle:
            for line in handle:
                print(write_window(db, strict_json(line)))
    finally:
        client.close()


if __name__ == "__main__":
    main()
