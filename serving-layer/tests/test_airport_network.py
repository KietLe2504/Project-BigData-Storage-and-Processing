import json

import pandas as pd
import pytest

from m5 import airport_network as network


def routes():
    return pd.DataFrame([
        dict(year=2022, origin="JFK", dest="LAX", flights=100, on_time=70, delayed15=20, cancelled=5, diverted=2, arr_n=90, sum_arr_delay=900),
        dict(year=2023, origin="LAX", dest="JFK", flights=20, on_time=5, delayed15=10, cancelled=5, diverted=0, arr_n=15, sum_arr_delay=300),
        dict(year=2022, origin="JFK", dest="BOS", flights=10, on_time=8, delayed15=2, cancelled=0, diverted=0, arr_n=10, sum_arr_delay=20),
        dict(year=2022, origin="SFO", dest="SEA", flights=500, on_time=400, delayed15=100, cancelled=0, diverted=0, arr_n=500, sum_arr_delay=3000),
    ])


def test_network_collapses_two_directions_without_unrelated_routes_or_mean_of_rates():
    data = network.connections(routes(), "JFK").set_index("peer")
    assert set(data.index) == {"LAX", "BOS"}
    assert data.loc["LAX", "flights"] == 120
    assert data.loc["LAX", "outbound"] == 100 and data.loc["LAX", "inbound"] == 20
    assert data.loc["LAX", "delay15_rate"] == pytest.approx(30/105)
    assert network.pair_rows(routes(), "JFK", "LAX", "outbound").flights.sum() == 100
    assert network.pair_rows(routes(), "JFK", "LAX", "inbound").flights.sum() == 20


def test_map_draws_one_pickable_link_per_pair_with_volume_width_color_and_all_neighbors():
    deck, pairs, nodes, edges, missing = network.build_map(routes(), "JFK")
    assert not missing
    assert {node["code"] for node in nodes} == {"JFK", "LAX", "BOS"}
    assert len(edges) == len(pairs) == 2
    edge_lookup = {row["peer"]: row for row in edges}
    assert edge_lookup["LAX"]["width"] > edge_lookup["BOS"]["width"]
    assert edge_lookup["LAX"]["color"] != edge_lookup["BOS"]["color"]
    assert next(n for n in nodes if n["code"] == "JFK")["color"] == [251, 191, 36, 255]
    spec = json.loads(deck.to_json(), parse_constant=lambda value: pytest.fail(value))
    assert {layer["id"] for layer in spec["layers"]} == {network.LINK_LAYER, network.NODE_LAYER}
    assert all(layer["pickable"] for layer in spec["layers"])
    assert all(layer.get("widthUnits", layer.get("radiusUnits")) == "pixels" for layer in spec["layers"])


def test_selection_uses_valid_server_owned_indices_not_untrusted_object_metadata():
    _, _, nodes, edges, _ = network.build_map(routes(), "JFK")
    event = {"selection": {"indices": {network.LINK_LAYER: [0]}, "objects": {network.LINK_LAYER: [{"peer": "FAKE"}]}}}
    assert network.decode_selection(event, nodes, edges) == ("pair", edges[0]["peer"])
    assert network.decode_selection({"selection": {"indices": {network.NODE_LAYER: [1]}}}, nodes, edges) == ("airport", nodes[1]["code"])
    for index in [-1, 9999, True, "0"]:
        assert network.decode_selection({"selection": {"indices": {network.LINK_LAYER: [index]}}}, nodes, edges) is None
    assert network.decode_selection({}, nodes, edges) is None


def test_missing_coordinate_is_reported_without_losing_pair_statistics():
    source = pd.concat([routes(), pd.DataFrame([dict(year=2022, origin="JFK", dest="ZZZ", flights=30)])], ignore_index=True)
    deck, pairs, nodes, edges, missing = network.build_map(source, "JFK")
    assert missing == ["ZZZ"]
    assert "ZZZ" in pairs.peer.tolist() and all(edge["peer"] != "ZZZ" for edge in edges)
    assert deck is not None


def test_status_counts_are_disjoint_and_preserve_unknown_arrivals():
    pair = network.connections(routes(), "JFK").set_index("peer").loc["LAX"]
    outcomes = network.outcome_counts(pair).set_index("status").flights
    assert outcomes.sum() == 120
    assert outcomes["Đúng giờ / trễ <15′"] == 75 and outcomes["Trễ ≥15′"] == 30
    assert outcomes["Hủy chuyến"] == 10 and outcomes["Thiếu giờ đến hợp lệ"] == 3
    assert network.outcome_counts({"flights": 3}) is None
    with pytest.raises(ValueError):
        network.outcome_counts(dict(flights=1, on_time=1, delayed15=1, cancelled=0, diverted=0))


def test_single_pair_map_has_finite_width_and_view_and_zero_arrival_ratio_is_missing():
    source = pd.DataFrame([dict(year=2022, origin="JFK", dest="LAX", flights=5, arr_n=0, delayed15=0, sum_arr_delay=None)])
    deck, pairs, _, edges, _ = network.build_map(source, "JFK")
    assert pairs.delay15_rate.iloc[0] is None
    assert edges[0]["width"] > 0 and len(edges[0]["color"]) == 4
    json.loads(deck.to_json(), parse_constant=lambda value: pytest.fail(value))
