"""Supplement M2 with exact yearly airline counts per directed airport pair.

Read cleaned Parquet once. Publish only after counts reconcile with BOTH the
existing year_route and year_carrier_origin exports. The 20-table M2 contract
and its existing snapshot are left intact.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def main():
    from pyspark.sql import SparkSession, functions as F
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-snapshot", type=Path, required=True)
    parser.add_argument("--processed", default="hdfs://namenode:9000/aero/processed")
    parser.add_argument("--output-root", type=Path, default=Path("/opt/spark_jobs/export/m2_route_carriers"))
    args = parser.parse_args()
    base = args.base_snapshot
    manifest = json.loads((base/"manifest.json").read_text())
    months = manifest["coverage"]["months"]
    spark = (SparkSession.builder.appName("AERO-route-carrier-supplement")
             .config("spark.sql.shuffle.partitions", "8").getOrCreate())
    spark.sparkContext.setLogLevel("WARN")
    try:
        paths = [f"{args.processed}/year={month[:4]}/month={month[5:]}" for month in months]
        raw = spark.read.option("basePath", args.processed).parquet(*paths)
        low = {name.lower(): name for name in raw.columns}
        def column(candidates):
            return F.col(next(low[name.lower()] for name in candidates if name.lower() in low))
        flights = raw.select(F.year(F.to_date(column(["FL_DATE", "FlightDate"]))).alias("year"),
            column(["OP_UNIQUE_CARRIER", "OP_CARRIER", "REPORTING_AIRLINE", "CARRIER"]).cast("string").alias("carrier"),
            column(["ORIGIN"]).cast("string").alias("origin"), column(["DEST"]).cast("string").alias("dest"))
        records = [row.asDict() for row in flights.groupBy("year", "origin", "dest", "carrier").agg(F.count("*").alias("flights")).collect()]
        if not records or len(records) > 500_000:
            raise ValueError("Empty or unexpectedly large route-carrier aggregate")
        routes, carriers = defaultdict(int), defaultdict(int)
        for row in records:
            if any(row[key] is None or str(row[key]).strip() == "" for key in ("year", "origin", "dest", "carrier")):
                raise ValueError("Null/empty business key; resolve before publication")
            routes[(row["year"], row["origin"], row["dest"])] += row["flights"]
            carriers[(row["year"], row["carrier"], row["origin"])] += row["flights"]
        expected_routes = {(r["year"], r["origin"], r["dest"]): r["flights"] for r in read_jsonl(base/"kpi__year_route.jsonl")}
        expected_carriers = {(r["year"], r["carrier"], r["origin"]): r["flights"] for r in read_jsonl(base/"kpi__year_carrier_origin.jsonl")}
        if dict(routes) != expected_routes or dict(carriers) != expected_carriers:
            raise ValueError("Cleaned data does not reconcile with the selected M2 snapshot")
        args.output_root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        with TemporaryDirectory(prefix=".building-", dir=args.output_root) as temporary:
            folder = Path(temporary)
            data_file = folder/"route_carrier.jsonl"
            with data_file.open("w", encoding="utf-8") as handle:
                for row in sorted(records, key=lambda r: (r["year"], r["origin"], r["dest"], r["carrier"])):
                    handle.write(json.dumps(row, sort_keys=True, allow_nan=False)+"\n")
            meta = {"format_version": 1, "kind": "route_carrier_supplement", "rows": len(records),
                "flights": sum(routes.values()), "file": data_file.name,
                "sha256": hashlib.sha256(data_file.read_bytes()).hexdigest(),
                "base_route_file_sha256": hashlib.sha256((base/"kpi__year_route.jsonl").read_bytes()).hexdigest(),
                "coverage": months, "processed_source": args.processed,
                "exported_at_utc": datetime.now(timezone.utc).isoformat(),
                "reconciled_year_routes": len(routes), "reconciled_year_carrier_origins": len(carriers)}
            (folder/"manifest.json").write_text(json.dumps(meta, indent=2)+"\n")
            destination = args.output_root/stamp
            folder.rename(destination)
        print(json.dumps({"result": "PASS", "output": str(destination), **meta}, indent=2), flush=True)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
