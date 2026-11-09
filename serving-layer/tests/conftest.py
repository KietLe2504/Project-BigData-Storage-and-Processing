import json
import os
from pathlib import Path
import sys
import uuid

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from m5.contracts import CATALOG, PROJECT_MONTHS
from m5.metrics import ADDITIVE


@pytest.fixture
def snapshot_factory(tmp_path):
    def make(factor=1):
        folder = tmp_path / f"snapshot_{uuid.uuid4().hex}"
        folder.mkdir()
        tables = []
        for (group, name), keys in CATALOG.items():
            values = {"year": 2022, "month": 1, "day": 1, "dep_hour": 8,
                      "carrier": "AA", "origin": "JFK", "dest": "LAX", "var": "arr", "population": "all"}
            row = {k: values[k] for k in keys}
            if group == "kpi":
                row.update({k: 0 for k in ADDITIVE})
                row.update(flights=100*factor, cancelled=10*factor, arr_n=90*factor,
                           on_time=70*factor, delayed15=20*factor, delayed60=1*factor,
                           sum_arr_delay=100.*factor, otp_operated=70/90,
                           cancel_rate=.1, delay15_rate=20/90)
            else:
                row.update(q1=0, median=5, q3=10, whisker_low=-5, whisker_high=20, n=90, reliable=True)
            rows = [row]
            if (group, name) == ("kpi", "month_overall"):
                rows = [{**row, "year": int(m[:4]), "month": int(m[5:])} for m in PROJECT_MONTHS]
            fields = [{"name": k, "type": "boolean" if type(v) is bool else
                       "long" if type(v) is int else "double" if type(v) is float else "string", "nullable": True,
                       "metadata": {}} for k, v in row.items()]
            filename = f"{group}__{name}.jsonl"
            (folder/filename).write_text("".join(json.dumps(r)+"\n" for r in rows))
            tables.append({"group": group, "name": name, "keys": keys, "rows": len(rows),
                           "suggested_collection": f"{group}_{name}", "jsonl": filename,
                           "spark_schema": {"type": "struct", "fields": fields}})
        manifest = {"format_version": 1, "source": "test fixture", "tables": tables,
                    "coverage": {"months": PROJECT_MONTHS, "month_count": 51,
                                 "total_flights": 5100*factor,
                                 "matches_project_period_2022_01_to_2026_03": True}}
        (folder/"manifest.json").write_text(json.dumps(manifest))
        return folder
    return make


@pytest.fixture
def db(monkeypatch):
    uri = os.environ.get("M5_TEST_MONGO_URI")
    if not uri:
        pytest.skip("Set M5_TEST_MONGO_URI to run real MongoDB integration tests")
    from pymongo import MongoClient
    client = MongoClient(uri, serverSelectionTimeoutMS=3000, tz_aware=True)
    client.admin.command("ping")
    name = "aero_m5_test_" + uuid.uuid4().hex
    monkeypatch.setenv("M5_MONGO_URI", uri)
    monkeypatch.setenv("M5_DATABASE", name)
    yield client[name]
    client.drop_database(name)
    client.close()
