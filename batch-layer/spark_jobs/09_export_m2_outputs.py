"""Export eda_lite KPI/box tables from HDFS for the M5 MongoDB loader.

Run with spark-submit inside the project's Spark container. No pandas required.
Only aggregate tables are exported; raw flights and base/hist are not read.
"""

import argparse
import csv
import json
import math
import os
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory


KPI_KEYS = {
    "day_overall": ["year", "month", "day"],
    "calendar_day_overall": ["month", "day"],
    "month_overall": ["year", "month"],
    "month_of_year_overall": ["month"],
    "year_overall": ["year"],
    "month_carrier": ["year", "month", "carrier"],
    "month_of_year_carrier": ["month", "carrier"],
    "year_carrier": ["year", "carrier"],
    "month_origin": ["year", "month", "origin"],
    "year_origin": ["year", "origin"],
    "year_route": ["year", "origin", "dest"],
    "year_carrier_origin": ["year", "carrier", "origin"],
    "hour_overall": ["dep_hour"],
}
BOX_KEYS = {
    "day_overall": ["year", "month", "day"],
    "month_overall": ["year", "month"],
    "month_carrier": ["year", "month", "carrier"],
    "month_of_year_overall": ["month"],
    "month_of_year_carrier": ["month", "carrier"],
    "year_overall": ["year"],
    "year_carrier": ["year", "carrier"],
}


def json_value(value):
    """Preserve scalar types and represent missing/non-finite values as null."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(v) for v in value]
    return value


def write_rows(directory, stem, rows, columns, keys, max_rows):
    """Write both formats from the same iterator; reject duplicate natural keys."""
    seen = set()
    count = 0
    with (directory / (stem + ".csv")).open(
        "w", encoding="utf-8-sig", newline=""
    ) as csv_file, (directory / (stem + ".jsonl")).open(
        "w", encoding="utf-8"
    ) as json_file:
        writer = csv.DictWriter(csv_file, fieldnames=columns)
        writer.writeheader()
        for raw in rows:
            row = json_value(raw)
            identity = json.dumps(
                [row[k] for k in keys], ensure_ascii=False, allow_nan=False
            )
            if identity in seen:
                raise ValueError("Duplicate key in {}: {}".format(stem, identity))
            seen.add(identity)
            count += 1
            if count > max_rows:
                raise ValueError(
                    "{} exceeds --max-rows={}; check the input table before "
                    "increasing this limit.".format(stem, max_rows)
                )
            writer.writerow(row)
            json_file.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    if not count:
        raise ValueError("Empty aggregate table: " + stem)
    return count


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--analytics-root", default=os.environ.get("AERO_ANALYTICS", "/aero/analytics/eda")
    )
    parser.add_argument("--hdfs", default=os.environ.get("AERO_HDFS", "hdfs://namenode:9000"))
    parser.add_argument("--output-dir", default="/opt/spark_jobs/export/m2_to_m5")
    parser.add_argument("--max-rows", type=int, default=200000, help="Limit per aggregate table")
    args = parser.parse_args()
    if args.max_rows < 1:
        parser.error("--max-rows must be positive")
    if "://" in args.output_dir:
        parser.error("--output-dir must be a local/container directory, not an HDFS URI")
    return args


def main():
    args = parse_args()
    from pyspark.sql import SparkSession

    builder = SparkSession.builder.appName("AERO-M2-M5-Export")
    if args.hdfs:
        builder = builder.config("spark.hadoop.fs.defaultFS", args.hdfs)
    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    try:
        specs = [("kpi", name, keys) for name, keys in KPI_KEYS.items()]
        specs += [
            ("box", name, keys + ["var", "population"])
            for name, keys in BOX_KEYS.items()
        ]
        sources = []
        for group, name, keys in specs:
            source = "{}/{}/{}".format(args.analytics_root.rstrip("/"), group, name)
            path = spark._jvm.org.apache.hadoop.fs.Path(source)
            fs = path.getFileSystem(spark._jsc.hadoopConfiguration())
            if not fs.exists(path):
                raise FileNotFoundError(
                    "Missing {}. Run eda_lite.ipynb through the build cell first; "
                    "06_batch_process_all.py alone does not create KPI tables.".format(source)
                )
            sources.append((group, name, keys, source))

        timestamp = datetime.now(timezone.utc)
        export_root = Path(args.output_dir)
        export_root.mkdir(parents=True, exist_ok=True)
        destination = export_root / timestamp.strftime("%Y%m%dT%H%M%S%fZ")
        # Publish a complete new snapshot only after every table has been exported.
        with TemporaryDirectory(prefix=".building-", dir=str(export_root)) as temporary:
            directory = Path(temporary)
            tables = []
            for group, name, keys, source in sources:
                df = spark.read.parquet(source)
                required = set(keys) | (
                    {"flights", "cancel_rate", "otp_scheduled"}
                    if group == "kpi" else {"n", "q1", "median", "q3"}
                )
                missing = required - set(df.columns)
                if missing:
                    raise ValueError("{} is missing columns: {}".format(source, sorted(missing)))
                stem = group + "__" + name
                count = write_rows(
                    directory, stem,
                    (row.asDict(recursive=True) for row in df.orderBy(*keys).toLocalIterator()),
                    df.columns, keys, args.max_rows,
                )
                tables.append({
                    "group": group,
                    "name": name,
                    "source_path": source,
                    "rows": count,
                    "keys": keys,
                    "suggested_collection": group + "_" + name,
                    "csv": stem + ".csv",
                    "jsonl": stem + ".jsonl",
                    "spark_schema": df.schema.jsonValue(),
                })
                print("Exported {}: {:,} rows".format(stem, count), flush=True)

            with (directory / "kpi__month_overall.jsonl").open(encoding="utf-8") as handle:
                monthly = [json.loads(line) for line in handle]
            months = sorted((row["year"], row["month"]) for row in monthly)
            expected = [(year, month) for year in range(2022, 2027)
                        for month in range(1, 4 if year == 2026 else 13)]
            manifest = {
                "format_version": 1,
                "exported_at_utc": timestamp.isoformat(),
                "source": "BTS historical batch aggregates from eda_lite.ipynb",
                "analytics_root": args.analytics_root,
                "coverage": {
                    "months": ["{}-{:02d}".format(y, m) for y, m in months],
                    "month_count": len(months),
                    "total_flights": sum(row["flights"] for row in monthly),
                    "matches_project_period_2022_01_to_2026_03": months == expected,
                },
                "conventions": {
                    "rates": "Fractions 0..1; multiply by 100 for display as percent",
                    "delays": "Minutes; avg_arr_delay_net can be negative",
                    "reliability_score": "Team-defined score 0..100, not an industry standard",
                    "nulls": "JSON null / empty CSV cell; do not automatically replace with zero",
                    "rollups": "Sum count/sum columns and recompute ratios; do not average rates",
                    "csv_encoding": "UTF-8 with BOM",
                    "preferred_mongo_input": "JSONL preserves numbers, booleans and nulls",
                    "exported_at_utc": "Export time; not the time upstream data was collected or built",
                    "consistency": "Export while upstream ETL/EDA jobs are idle",
                },
                "tables": tables,
            }
            (directory / "manifest.json").write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                encoding="utf-8",
            )
            directory.rename(destination)

        print("\nEXPORT COMPLETE:", destination)
        print("Coverage: {} months; {:,} flights".format(
            len(months), manifest["coverage"]["total_flights"]
        ))
        if months != expected:
            print("NOTE: This snapshot does not cover all 51 project months. See manifest.json.")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
