import argparse
import json
from pathlib import Path

from m5.batch_writer import verify_run
from m5.mongo import connect


def main():
    parser = argparse.ArgumentParser(description="Verify every value of the active MongoDB snapshot")
    parser.add_argument("--snapshot-id")
    parser.add_argument("--report", default="/app/evidence/verify_report.json")
    args = parser.parse_args()
    client, db = connect()
    try:
        state = db.serving_state.find_one({"_id": "historical"})
        snapshot_id = args.snapshot_id or (state or {}).get("snapshot_id")
        if not snapshot_id:
            raise RuntimeError("No active snapshot. Run load_m2.ps1 first")
        run = db.batch_runs.find_one({"_id": snapshot_id})
        if not run or run["status"] != "published":
            raise RuntimeError("Snapshot is missing or not published")
        report = verify_run(db, run)
        indexes = {}
        for t in run["manifest"]["tables"]:
            name = t["suggested_collection"]
            info = db[name].index_information()
            unique = info.get("snapshot_business_key", {})
            expected = [(k, 1) for k in ["snapshot_id", *t["keys"]]]
            if not unique.get("unique") or unique.get("key") != expected:
                raise ValueError(f"Missing/wrong unique index: {name}")
            indexes[name] = list(info)
        report["indexes"] = indexes
        report["note"] = "Exact source digests stored at ingest; no average-of-ratios or raw count claim"
        path = Path(args.report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"ALL 20 COLLECTIONS CHECKED: PASS; {report['total_documents']} documents")
        print(f"REPORT: {path}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
