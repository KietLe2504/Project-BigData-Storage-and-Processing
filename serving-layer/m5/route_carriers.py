"""Validate and atomically publish an optional, snapshot-bound route/airline supplement."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from pymongo import ReplaceOne

from m5.contracts import canonical, inspect_snapshot, safe_file, strict_json
from m5.mongo import connect
from m5.queries import active_run

KEYS = ["year", "origin", "dest", "carrier"]


def digest(rows):
    return hashlib.sha256(canonical(sorted(rows, key=lambda row: tuple(row[k] for k in KEYS))).encode()).hexdigest()


def load_supplement(db, folder, base_folder):
    folder, base_folder = Path(folder), Path(base_folder)
    _, _, snapshot_id = inspect_snapshot(base_folder)
    run = active_run(db)
    if run is None or run["_id"] != snapshot_id:
        raise ValueError("Supplement must target the currently published M2 snapshot")
    meta = strict_json((folder/"manifest.json").read_text(encoding="utf-8"))
    if meta.get("format_version") != 1 or meta.get("kind") != "route_carrier_supplement":
        raise ValueError("Unsupported route-carrier supplement")
    if meta.get("coverage") != run["manifest"]["coverage"]["months"]:
        raise ValueError("Supplement coverage differs from M2")
    if hashlib.sha256((base_folder/"kpi__year_route.jsonl").read_bytes()).hexdigest() != meta.get("base_route_file_sha256"):
        raise ValueError("Supplement was generated against a different M2 route export")
    path = safe_file(folder, meta.get("file"))
    if hashlib.sha256(path.read_bytes()).hexdigest() != meta.get("sha256"):
        raise ValueError("Supplement file SHA-256 mismatch")
    source, seen, counts = [], set(), defaultdict(int)
    for line in path.open(encoding="utf-8"):
        row = strict_json(line)
        if set(row) != set(KEYS+["flights"]) or type(row["year"]) is not int or type(row["flights"]) is not int or row["flights"] <= 0:
            raise ValueError("Invalid route-carrier row")
        if any(not isinstance(row[k], str) or not row[k].strip() or len(row[k]) > 16 for k in KEYS[1:]):
            raise ValueError("Invalid route-carrier code")
        key = tuple(row[k] for k in KEYS)
        if key in seen or len(source) >= 500_000:
            raise ValueError("Duplicate/oversized route-carrier supplement")
        seen.add(key)
        source.append(row)
        counts[key[:3]] += row["flights"]
    expected = {(r["year"], r["origin"], r["dest"]): r["flights"]
                for r in db.kpi_year_route.find({"snapshot_id": snapshot_id})}
    if not source or len(source) != meta.get("rows") or sum(counts.values()) != meta.get("flights") or dict(counts) != expected:
        raise ValueError("Supplement counts do not reconcile with every published M2 route")
    # Independently verify airline identity against the existing carrier/origin grain.
    carrier_counts = defaultdict(int)
    for row in source:
        carrier_counts[(row["year"], row["carrier"], row["origin"]) ] += row["flights"]
    expected_carriers = {(r["year"], r["carrier"], r["origin"]): r["flights"]
                         for r in db.kpi_year_carrier_origin.find({"snapshot_id": snapshot_id})}
    if dict(carrier_counts) != expected_carriers:
        raise ValueError("Supplement airline counts disagree with published M2 carrier/origin counts")
    content_digest = digest(source)
    version = hashlib.sha256(canonical([snapshot_id, content_digest]).encode()).hexdigest()
    db.route_carrier_counts.create_index([("data_version", 1), *[(key, 1) for key in KEYS]], unique=True)
    db.route_carrier_counts.create_index([("snapshot_id", 1), ("data_version", 1), ("origin", 1), ("dest", 1), ("year", 1)])
    for start in range(0, len(source), 1000):
        db.route_carrier_counts.bulk_write([ReplaceOne({"data_version": version, **{key: row[key] for key in KEYS}},
            {**row, "data_version": version, "snapshot_id": snapshot_id}, upsert=True) for row in source[start:start+1000]], ordered=False)
    actual = list(db.route_carrier_counts.find({"snapshot_id": snapshot_id, "data_version": version},
                                              {"_id": 0, "snapshot_id": 0, "data_version": 0}))
    if len(actual) != len(source) or digest(actual) != content_digest:
        raise ValueError("MongoDB route-carrier verification failed; supplement not published")
    report = {"_id": snapshot_id, "status": "ready", "data_version": version, "rows": len(source),
        "flights": sum(counts.values()), "verified_routes": len(expected),
        "verified_at": datetime.now(timezone.utc), "source": meta}
    db.route_carrier_state.replace_one({"_id": snapshot_id}, report, upsert=True)
    return report


def pair_carriers(db, snapshot_id, hub, peer, years=None, direction="both"):
    state = db.route_carrier_state.find_one({"_id": snapshot_id, "status": "ready"})
    if state is None:
        return None
    outgoing, incoming = {"origin": hub, "dest": peer}, {"origin": peer, "dest": hub}
    query = {"snapshot_id": snapshot_id, "data_version": state["data_version"]}
    if direction == "outbound":
        query.update(outgoing)
    elif direction == "inbound":
        query.update(incoming)
    else:
        query["$or"] = [outgoing, incoming]
    if years:
        query["year"] = {"$in": list(years)}
    return list(db.route_carrier_counts.find(query, {"_id": 0, "snapshot_id": 0, "data_version": 0}))


def carrier_destinations(db, snapshot_id, carrier, years=None):
    """Count destinations across all origins for this airline and published version."""
    state = db.route_carrier_state.find_one({"_id": snapshot_id, "status": "ready"})
    if state is None:
        return None
    query = {"snapshot_id": snapshot_id, "data_version": state["data_version"], "carrier": carrier}
    if years:
        query["year"] = {"$in": list(years)}
    return list(db.route_carrier_counts.aggregate([
        {"$match": query},
        {"$group": {"_id": "$dest", "flights": {"$sum": "$flights"}}},
        {"$project": {"_id": 0, "dest": "$_id", "flights": 1}},
        {"$sort": {"flights": -1, "dest": 1}},
    ]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--supplement", type=Path, required=True)
    parser.add_argument("--base-snapshot", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=Path("/app/evidence/route_carrier_load.json"))
    args = parser.parse_args()
    client, db = connect()
    try:
        report = load_supplement(db, args.supplement, args.base_snapshot)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str)+"\n", encoding="utf-8")
        print(json.dumps({key: value for key, value in report.items() if key != "source"}, default=str))
    finally:
        client.close()


if __name__ == "__main__":
    main()
