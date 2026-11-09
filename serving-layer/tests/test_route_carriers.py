import hashlib
import json

import pytest

from m5.batch_writer import load_snapshot
from m5.route_carriers import carrier_destinations, load_supplement, pair_carriers

pytestmark = pytest.mark.integration


def supplement(base, path, count=100):
    path.mkdir()
    row = dict(year=2022, origin="JFK", dest="LAX", carrier="AA", flights=count)
    data = path/"route_carrier.jsonl"
    data.write_text(json.dumps(row)+"\n")
    manifest = json.loads((base/"manifest.json").read_text())
    meta = {"format_version": 1, "kind": "route_carrier_supplement", "file": data.name,
        "rows": 1, "flights": count, "coverage": manifest["coverage"]["months"],
        "sha256": hashlib.sha256(data.read_bytes()).hexdigest(),
        "base_route_file_sha256": hashlib.sha256((base/"kpi__year_route.jsonl").read_bytes()).hexdigest()}
    (path/"manifest.json").write_text(json.dumps(meta))
    return path


def test_supplement_is_idempotent_bound_to_snapshot_and_filters_direction(db, snapshot_factory, tmp_path):
    base = snapshot_factory()
    report = load_snapshot(db, base)
    sid = report["snapshot_id"]
    assert pair_carriers(db, sid, "JFK", "LAX") is None
    folder = supplement(base, tmp_path/"supplement")
    first = load_supplement(db, folder, base)
    second = load_supplement(db, folder, base)
    assert first["data_version"] == second["data_version"]
    assert db.route_carrier_counts.count_documents({}) == 1
    assert pair_carriers(db, sid, "JFK", "LAX")[0]["flights"] == 100
    assert len(pair_carriers(db, sid, "LAX", "JFK", [2022], "inbound")) == 1
    assert pair_carriers(db, sid, "JFK", "LAX", [2023]) == []
    assert pair_carriers(db, sid, "JFK", "LAX", direction="inbound") == []
    assert pair_carriers(db, "different-snapshot", "JFK", "LAX") is None


def test_invalid_supplement_cannot_replace_valid_published_distribution(db, snapshot_factory, tmp_path):
    base = snapshot_factory()
    sid = load_snapshot(db, base)["snapshot_id"]
    load_supplement(db, supplement(base, tmp_path/"good"), base)
    state = db.route_carrier_state.find_one({"_id": sid})
    with pytest.raises(ValueError, match="reconcile"):
        load_supplement(db, supplement(base, tmp_path/"bad", count=99), base)
    assert db.route_carrier_state.find_one({"_id": sid}) == state
    assert pair_carriers(db, sid, "JFK", "LAX")[0]["flights"] == 100
    with pytest.raises(ValueError, match="currently published"):
        load_supplement(db, tmp_path/"good", snapshot_factory(factor=2))


def test_carrier_destinations_sum_all_origins_and_respect_year_carrier_snapshot_version(db):
    assert carrier_destinations(db, "snapshot-a", "9E") is None
    db.route_carrier_state.insert_one({"_id": "snapshot-a", "status": "ready", "data_version": "published"})
    docs = [
        dict(year=2022, origin="JFK", dest="LAX", carrier="9E", flights=30),
        dict(year=2022, origin="ATL", dest="LAX", carrier="9E", flights=20),
        dict(year=2022, origin="LAX", dest="JFK", carrier="9E", flights=10),
        dict(year=2023, origin="ATL", dest="LAX", carrier="9E", flights=70),
        dict(year=2022, origin="JFK", dest="BOS", carrier="AA", flights=999),
    ]
    db.route_carrier_counts.insert_many([{**row, "snapshot_id": "snapshot-a", "data_version": "published"} for row in docs])
    db.route_carrier_counts.insert_many([
        {**docs[0], "snapshot_id": "snapshot-a", "data_version": "old-version", "flights": 1000},
        {**docs[0], "snapshot_id": "another-snapshot", "data_version": "published", "flights": 2000},
    ])
    assert carrier_destinations(db, "snapshot-a", "9E") == [dict(dest="LAX", flights=120), dict(dest="JFK", flights=10)]
    assert carrier_destinations(db, "snapshot-a", "9E", [2022]) == [dict(dest="LAX", flights=50), dict(dest="JFK", flights=10)]
    assert carrier_destinations(db, "snapshot-a", "AA", [2022]) == [dict(dest="BOS", flights=999)]
    assert carrier_destinations(db, "snapshot-a", "9E", [2024]) == []
