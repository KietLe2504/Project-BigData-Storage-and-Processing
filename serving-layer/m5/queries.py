from m5.contracts import CATALOG

COLLECTIONS = {f"{g}_{n}": keys for (g, n), keys in CATALOG.items()}


def active_run(db):
    state = db.serving_state.find_one({"_id": "historical"})
    if not state:
        return None
    return db.batch_runs.find_one({"_id": state["snapshot_id"], "status": "published"})


def query_rows(db, snapshot_id, collection, filters=None):
    if collection not in COLLECTIONS:
        raise ValueError("Collection is not in the M2 contract")
    filters = filters or {}
    if set(filters) - set(COLLECTIONS[collection]):
        raise ValueError(f"Unsupported filters for {collection}: {set(filters) - set(COLLECTIONS[collection])}")
    query = {"snapshot_id": snapshot_id}
    for key, values in filters.items():
        if not isinstance(values, (list, tuple)) or not values:
            raise ValueError(f"Filter {key} must be a nonempty list")
        query[key] = {"$in": list(values)}
    return list(db[collection].find(query, {"_id": 0, "snapshot_id": 0})
                .sort([(key, 1) for key in COLLECTIONS[collection]]))
