import json

import pytest

from m5.contracts import inspect_snapshot, safe_file, strict_json
from m5.metrics import ratio, summarize


def test_inspect_full_fixture(snapshot_factory):
    manifest, digests, identity = inspect_snapshot(snapshot_factory())
    assert len(digests) == 20
    assert digests["kpi_month_overall"]["total_flights"] == 5100
    assert len(identity) == 64


@pytest.mark.parametrize("mutation", ["duplicate", "bad_type", "count", "null_key", "missing", "coverage"])
def test_reject_corrupt_input(snapshot_factory, mutation):
    folder = snapshot_factory()
    path = folder / "kpi__month_overall.jsonl"
    data = [json.loads(x) for x in path.read_text().splitlines()]
    if mutation == "duplicate":
        data[-1] = data[0]
    elif mutation == "bad_type":
        data[0]["flights"] = "100"
    elif mutation == "count":
        data.pop()
    elif mutation == "null_key":
        data[0]["month"] = None
    elif mutation == "missing":
        path.unlink()
    else:
        manifest_path = folder / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["coverage"]["total_flights"] = 0
        manifest_path.write_text(json.dumps(manifest))
    if mutation != "missing":
        path.write_text("".join(json.dumps(row)+"\n" for row in data))
    with pytest.raises(ValueError):
        inspect_snapshot(folder)


def test_reject_escape_and_duplicate_json(tmp_path):
    with pytest.raises(ValueError):
        safe_file(tmp_path, "../outside.jsonl")
    with pytest.raises(ValueError):
        strict_json('{"year":2022,"year":2023}')
    with pytest.raises(ValueError):
        strict_json('{"value":NaN}')


def test_weighted_rollup_null_and_negative_delay():
    result = summarize([{"flights": 10, "cancelled": 5, "arr_n": 5, "on_time": 5, "sum_arr_delay": -10},
                        {"flights": 90, "cancelled": 0, "arr_n": 90, "on_time": 45, "sum_arr_delay": -90}])
    assert result["cancel_rate"] == .05
    assert result["otp_operated"] == 50/95
    assert result["avg_arr_delay_net"] == -100/95
    assert result["dep_delay15_rate"] is None
    assert ratio(1, 0) is None
    assert summarize([]) == {}
