import json

import pytest
from pymongo.errors import DuplicateKeyError

from m5.batch_writer import load_snapshot, loader_lock, verify_run
from m5.queries import active_run, query_rows
from m5.stream_writer import write_window

pytestmark = pytest.mark.integration


def test_load_idempotency_indexes_and_tamper_detection(db, snapshot_factory):
    folder = snapshot_factory()
    first = load_snapshot(db, folder)
    second = load_snapshot(db, folder)
    assert first["snapshot_id"] == second["snapshot_id"]
    assert db.kpi_month_overall.count_documents({}) == 51
    row = db.kpi_month_overall.find_one({})
    row.pop("_id")
    with pytest.raises(DuplicateKeyError):
        db.kpi_month_overall.insert_one(row)
    db.kpi_month_overall.update_one({"snapshot_id": first["snapshot_id"]}, {"$inc": {"flights": 1}})
    with pytest.raises(ValueError):
        verify_run(db, active_run(db))


def test_partial_failure_keeps_old_snapshot_and_retry_recovers(db, snapshot_factory):
    old = load_snapshot(db, snapshot_factory())
    new_folder = snapshot_factory(factor=2)

    def fail_after_table(message):
        raise RuntimeError("Simulated connection interruption after first table")

    with pytest.raises(RuntimeError):
        load_snapshot(db, new_folder, progress=fail_after_table)
    assert active_run(db)["_id"] == old["snapshot_id"]
    new = load_snapshot(db, new_folder)
    assert active_run(db)["_id"] == new["snapshot_id"]
    assert new["snapshot_id"] != old["snapshot_id"]
    assert len(query_rows(db, new["snapshot_id"], "kpi_month_overall")) == 51
    # Re-importing an older published snapshot must not roll the dashboard back.
    old_folder = snapshot_factory()
    load_snapshot(db, old_folder)
    assert active_run(db)["_id"] == new["snapshot_id"]


def test_lock_and_filter_guards(db, snapshot_factory):
    with loader_lock(db):
        with pytest.raises(RuntimeError):
            with loader_lock(db):
                pass
    loaded = load_snapshot(db, snapshot_factory())
    with pytest.raises(ValueError):
        query_rows(db, loaded["snapshot_id"], "kpi_year_route", {"month": [1]})
    selected = query_rows(db, loaded["snapshot_id"], "kpi_month_overall", {"year": [2026]})
    assert len(selected) == 3


def test_activation_failure_can_resume_without_rollback(db, snapshot_factory, monkeypatch):
    import m5.batch_writer as writer
    first = load_snapshot(db, snapshot_factory())
    folder = snapshot_factory(factor=2)
    original = writer.finish_activation
    with monkeypatch.context() as patch:
        patch.setattr(writer, "finish_activation", lambda *args: (_ for _ in ()).throw(RuntimeError("network lost before activation")))
        with pytest.raises(RuntimeError):
            load_snapshot(db, folder)
    assert active_run(db)["_id"] == first["snapshot_id"]
    second = load_snapshot(db, folder)
    assert active_run(db)["_id"] == second["snapshot_id"]


def test_new_snapshot_does_not_serve_removed_groups(db, snapshot_factory):
    old_folder = snapshot_factory()
    path = old_folder / "kpi__year_route.jsonl"
    extra = json.loads(path.read_text())
    extra["dest"] = "SFO"
    path.write_text(path.read_text()+json.dumps(extra)+"\n")
    manifest_path = old_folder / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    next(t for t in manifest["tables"] if t["name"] == "year_route")["rows"] = 2
    manifest_path.write_text(json.dumps(manifest))
    old = load_snapshot(db, old_folder)
    new = load_snapshot(db, snapshot_factory())
    assert len(query_rows(db, old["snapshot_id"], "kpi_year_route")) == 2
    assert len(query_rows(db, new["snapshot_id"], "kpi_year_route")) == 1


def window(revision=1, flights=100):
    return {"pipeline_id": "test-v1", "source": "simulated", "window_start": "2026-11-07T00:00:00Z",
            "window_end": "2026-11-07T00:05:00Z", "revision": revision,
            "dimensions": {"carrier": "AA"}, "metrics": {"flights": flights}}


def test_stream_replay_stale_and_conflict(db):
    assert write_window(db, window()) == "inserted"
    ingested_at = db.stream_window_kpi.find_one({})["ingested_at"]
    assert write_window(db, window()) == "replay_ignored"
    equivalent = window()
    equivalent["window_start"] = "2026-11-07T00:00:00+00:00"
    assert write_window(db, equivalent) == "replay_ignored"
    assert db.stream_window_kpi.find_one({})["ingested_at"] == ingested_at
    assert write_window(db, window(2, 110)) == "updated"
    assert write_window(db, window(1)) == "stale_ignored"
    with pytest.raises(ValueError):
        write_window(db, window(2, 120))
    assert db.stream_window_kpi.count_documents({}) == 1
    assert db.stream_window_kpi.find_one({})["metrics"]["flights"] == 110
