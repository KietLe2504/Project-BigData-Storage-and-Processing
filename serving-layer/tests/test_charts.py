import pandas as pd
import pytest

from m5 import charts


def test_arrival_mix_has_one_population_and_no_overlap():
    totals = dict(flights=120, cancelled=20, arr_n=100, on_time=75,
                  delayed15=25, delayed60=5, otp_operated=.75)
    figure = charts.arrival_donut(totals)
    assert list(figure.data[0].values) == [75, 20, 5]
    assert sum(figure.data[0].values) == totals["arr_n"]
    with pytest.raises(ValueError):
        charts.arrival_counts({**totals, "delayed60": 30})


def test_treemap_other_preserves_total_without_double_counting():
    data = pd.DataFrame({"carrier": ["AA", "DL", "UA"], "flights": [100, 50, 25]})
    trace = charts.share_treemap(data, "carrier", top_n=1).data[0]
    leaves = [value for parent, value in zip(trace.parents, trace.values) if parent]
    assert sum(leaves) == 175
    assert trace.values[0] == 175
    assert list(trace.labels) == ["Toàn bộ đã chọn", "AA", "Nhóm còn lại"]


def test_sankey_keeps_departures_and_arrivals_separate():
    data = pd.DataFrame([{"origin": "JFK", "dest": "LAX", "flights": 100},
                         {"origin": "LAX", "dest": "JFK", "flights": 80}])
    trace = charts.route_sankey(data).data[0]
    assert len(trace.node.label) == 4
    assert sum(trace.link.value) == 180
    assert all(source != target for source, target in zip(trace.link.source, trace.link.target))
    assert "JFK · đi" in trace.node.label and "JFK · đến" in trace.node.label


def test_animation_uses_observed_common_groups_and_fixed_axes():
    data = pd.DataFrame([
        {"carrier": "AA", "year": 2022, "flights": 100, "delay15_rate": .2},
        {"carrier": "AA", "year": 2023, "flights": 120, "delay15_rate": .1},
        {"carrier": "DL", "year": 2022, "flights": 200, "delay15_rate": .3}])
    figure = charts.bubble(data, "carrier", animate=True)
    assert len(figure.frames) == 2
    assert all(trace.name == "AA" for frame in figure.frames for trace in frame.data)
    assert figure.layout.yaxis.range == (0, 1)
    assert figure.layout.xaxis.range[1] >= 120


def test_disjoint_animation_groups_have_no_fabricated_zero_rows():
    data = pd.DataFrame([{"carrier": "AA", "year": 2022, "flights": 100, "delay15_rate": .2},
                         {"carrier": "DL", "year": 2023, "flights": 120, "delay15_rate": .1}])
    assert charts.bubble(data, "carrier", animate=True) is None
