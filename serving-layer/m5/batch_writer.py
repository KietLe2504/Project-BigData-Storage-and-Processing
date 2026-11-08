"""Publish immutable, fully verified snapshots using one atomic active pointer."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import uuid

from pymongo import ASCENDING, ReplaceOne, ReturnDocument
from pymongo.errors import DuplicateKeyError

from m5.contracts import inspect_snapshot, read_rows, table_digest


def utcnow():
    return datetime.now(timezone.utc)


@contextmanager
def loader_lock(db):
    owner = uuid.uuid4().hex

    def renew():
        now = utcnow()
        query = {"_id": "batch_loader", "$or": [
            {"expires_at": {"$lte": now}}, {"owner": owner}]}
        try:
            lock = db.serving_locks.find_one_and_update(query, {"$set": {
                "owner": owner, "expires_at": now + timedelta(minutes=10)}},
                upsert=True, return_document=ReturnDocument.AFTER)
        except DuplicateKeyError as exc:
            raise RuntimeError("Another loader is running; after a crash the lease expires in 10 minutes") from exc
        if lock["owner"] != owner:
            raise RuntimeError("Loader lock was lost")
    renew()
    try:
        yield renew
    finally:
        db.serving_locks.delete_one({"_id": "batch_loader", "owner": owner})


def ensure_indexes(db, table):
    collection = db[table["suggested_collection"]]
    collection.create_index([(k, ASCENDING) for k in ["snapshot_id", *table["keys"]]],
                            unique=True, name="snapshot_business_key")
    for dimension in ("carrier", "origin", "dest"):
        if dimension in table["keys"]:
            collection.create_index([("snapshot_id", 1), (dimension, 1)], name=f"filter_{dimension}")


def verify_run(db, run, renew=lambda: None):
    snapshot_id = run["_id"]
    checked = []
    for table in run["manifest"]["tables"]:
        renew()
        name = table["suggested_collection"]
        cursor = db[name].find({"snapshot_id": snapshot_id}, {"_id": 0, "snapshot_id": 0})
        actual = table_digest(cursor, table)
        if actual != run["digests"][name]:
            raise ValueError(f"MongoDB/source values mismatch in {name}")
        checked.append({"collection": name, **actual})
    return {"result": "PASS", "snapshot_id": snapshot_id,
            "checked_at": utcnow().isoformat(), "tables": checked,
            "total_documents": sum(t["rows"] for t in checked),
            "coverage": run["manifest"]["coverage"]}


def finish_activation(db, run):
    """Recover a crash between verification and pointer update, without rollback."""
    state = db.serving_state.find_one({"_id": "historical"})
    active = (state or {}).get("snapshot_id")
    if active == run.get("previous_snapshot_id"):
        db.serving_state.replace_one({"_id": "historical"}, {
            "_id": "historical", "snapshot_id": run["_id"], "activated_at": utcnow()}, upsert=True)
    db.batch_runs.update_one({"_id": run["_id"]}, {"$set": {"activation_pending": False}})


def load_snapshot(db, folder, allow_partial=False, source=None, progress=print):
    manifest, digests, snapshot_id = inspect_snapshot(folder, allow_partial)
    with loader_lock(db) as renew:
        existing = db.batch_runs.find_one({"_id": snapshot_id})
        if existing and existing.get("status") == "published":
            report = verify_run(db, existing, renew)
            if existing.get("activation_pending"):
                finish_activation(db, existing)
            progress(f"ALREADY LOADED: {snapshot_id}; values verified; active selection unchanged")
            return report
        run = {"_id": snapshot_id, "status": "loading", "manifest": manifest,
               "digests": digests, "source": source or {"format": "jsonl", "path": str(folder)},
               "started_at": utcnow()}
        db.batch_runs.replace_one({"_id": snapshot_id}, run, upsert=True)
        try:
            for table in manifest["tables"]:
                renew()
                ensure_indexes(db, table)
                collection = db[table["suggested_collection"]]
                writes = []
                for row in read_rows(folder, table):
                    query = {"snapshot_id": snapshot_id, **{k: row[k] for k in table["keys"]}}
                    writes.append(ReplaceOne(query, {**row, "snapshot_id": snapshot_id}, upsert=True))
                    if len(writes) == 1000:
                        renew()
                        collection.bulk_write(writes, ordered=False)
                        writes = []
                if writes:
                    collection.bulk_write(writes, ordered=False)
                progress(f"LOADED {table['suggested_collection']}: {table['rows']} documents")
            # Fingerprint again: files must not change between validation and ingest.
            if inspect_snapshot(folder, allow_partial)[2] != snapshot_id:
                raise ValueError("Source changed during ingestion; snapshot was not published")
            report = verify_run(db, run, renew)
            renew()
        except Exception as exc:
            db.batch_runs.update_one({"_id": snapshot_id}, {"$set": {
                "status": "failed", "error": str(exc), "failed_at": utcnow()}})
            raise
        state = db.serving_state.find_one({"_id": "historical"})
        run.update(status="published", verified_at=utcnow(), report=report,
                   previous_snapshot_id=(state or {}).get("snapshot_id"), activation_pending=True)
        db.batch_runs.replace_one({"_id": snapshot_id}, run)
        # Separate from ingest failure handling: this verified run can recover
        # activation if the process/network dies at this exact boundary.
        finish_activation(db, run)
    progress(f"LOAD COMPLETE: {snapshot_id}; {report['total_documents']} documents; PASS")
    return report
