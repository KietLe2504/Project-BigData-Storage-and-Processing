import argparse
import json
from pathlib import Path

from m5.batch_writer import load_snapshot
from m5.contracts import inspect_snapshot
from m5.mongo import connect


def main():
    parser = argparse.ArgumentParser(description="Validate and load an explicit M2 export snapshot")
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--check-only", action="store_true", help="Validate without connecting to MongoDB")
    parser.add_argument("--report", default="/app/evidence/load_report.json")
    args = parser.parse_args()
    if args.check_only:
        manifest, digests, snapshot_id = inspect_snapshot(args.snapshot, args.allow_partial)
        report = {"result": "PASS", "snapshot_id": snapshot_id,
                  "coverage": manifest["coverage"], "tables": digests,
                  "total_documents": sum(x["rows"] for x in digests.values())}
    else:
        client, db = connect()
        try:
            report = load_snapshot(db, args.snapshot, args.allow_partial)
        finally:
            client.close()
    path = Path(args.report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report if args.check_only else {
        "result": report["result"], "snapshot_id": report["snapshot_id"],
        "total_documents": report["total_documents"]}, indent=2))
    print(f"REPORT: {path}")


if __name__ == "__main__":
    main()
