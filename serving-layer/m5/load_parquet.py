"""Read the 20 aggregate Parquet tables directly from HDFS and load MongoDB.

Run via compose.hdfs.yml. Stage a validated JSONL snapshot in ephemeral storage
so source inspection, retry, fingerprints and publication use the same writer.
No cleaned flight records or CSV input are read by this adapter.
"""
import argparse
from datetime import datetime, timezone, date
import json
import math
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from m5.batch_writer import load_snapshot
from m5.contracts import CATALOG, PROJECT_MONTHS, canonical
from m5.mongo import connect


def scalar(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def export_parquet(spark, folder, analytics_root):
    tables, months, total_flights = [], [], 0
    for (group, name), keys in CATALOG.items():
        path = f"{analytics_root.rstrip('/')}/{group}/{name}"
        df = spark.read.parquet(path)
        if set(keys) - set(df.columns):
            raise ValueError(f"Missing keys in {path}")
        schema = json.loads(df.schema.json())
        filename = f"{group}__{name}.jsonl"
        count = 0
        with (folder / filename).open("w", encoding="utf-8") as handle:
            for row in df.toLocalIterator():
                count += 1
                if count > 200_000:
                    raise ValueError(f"Aggregate exceeds 200,000 rows: {path}")
                data = {k: scalar(v) for k, v in row.asDict().items()}
                handle.write(canonical(data) + "\n")
                if (group, name) == ("kpi", "month_overall"):
                    months.append(f"{data['year']}-{data['month']:02d}")
                    total_flights += data["flights"]
        tables.append({"group": group, "name": name, "keys": keys,
                       "suggested_collection": f"{group}_{name}", "rows": count,
                       "source_path": path, "spark_schema": schema, "jsonl": filename})
        print(f"READ HDFS {path}: {count}", flush=True)
    months.sort()
    manifest = {"format_version": 1, "exported_at_utc": datetime.now(timezone.utc).isoformat(),
                "source": "BTS historical aggregate Parquet directly read by M5",
                "analytics_root": analytics_root, "tables": tables,
                "coverage": {"months": months, "month_count": len(months),
                             "total_flights": total_flights,
                             "matches_project_period_2022_01_to_2026_03": months == PROJECT_MONTHS}}
    (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main():
    from pyspark.sql import SparkSession
    parser = argparse.ArgumentParser(description="Load KPI/box Parquet directly from HDFS")
    parser.add_argument("--analytics-root", default="/aero/analytics/eda")
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--report", default="/app/evidence/hdfs_load_report.json")
    args = parser.parse_args()
    spark = (SparkSession.builder.appName("aero-m5-hdfs-loader")
             .config("spark.sql.shuffle.partitions", "8").getOrCreate())
    spark.sparkContext.setLogLevel("WARN")
    client = None
    try:
        with TemporaryDirectory(prefix="aero-m5-hdfs-") as temporary:
            folder = Path(temporary)
            export_parquet(spark, folder, args.analytics_root)
            client, db = connect()
            report = load_snapshot(db, folder, args.allow_partial, source={
                "format": "hdfs-parquet", "path": args.analytics_root,
                "hdfs": spark.sparkContext._jsc.hadoopConfiguration().get("fs.defaultFS")})
            report["input_format"] = "hdfs-parquet"
            report["analytics_root"] = args.analytics_root
            output = Path(args.report)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        if client:
            client.close()
        spark.stop()


if __name__ == "__main__":
    main()
