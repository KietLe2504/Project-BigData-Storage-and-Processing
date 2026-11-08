import json

import pandas as pd
import pytest

from m5 import route_map
from m5.metrics import summarize


def routes():
    return pd.DataFrame([
        dict(origin="JFK", dest="LAX", flights=100, delayed15=18, arr_n=90, on_time=72,
             delay15_rate=.2, avg_arr_delay_net=8., otp_operated=.8, cancel_rate=.1),
        dict(origin="LAX", dest="JFK", flights=20, delayed15=10, arr_n=20, on_time=10,
             delay15_rate=.5, avg_arr_delay_net=None, otp_operated=.5, cancel_rate=0.),
    ])


def test_map_preserves_direction_counts_and_weighted_risk():
    source = routes()
    deck, drawn, nodes, missing = route_map.build_map(source)
    assert len(drawn) == 2 and drawn.flights.sum() == 120
    assert missing == {"codes": [], "routes": 0, "flights": 0}
    jfk = nodes.set_index("code").loc["JFK"]
    assert jfk.departures == 100 and jfk.arrivals == 20
    assert nodes.movements.sum() == 240  # each flight has two endpoints
    totals = summarize(drawn.astype(object).where(drawn.notna(), None).to_dict("records"))
    assert totals["delay15_rate"] == pytest.approx(28/110)
    assert totals["delay15_rate"] != pytest.approx(.35)
    assert set(drawn.tip_title) == {"JFK → LAX", "LAX → JFK"}
    assert "origin_lon" not in source  # no mutation of input


def test_map_json_has_no_nan_or_fabricated_zero_for_missing_delay():
    deck, drawn, _, _ = route_map.build_map(routes(), metric="avg_arr_delay_net")
    spec = json.loads(deck.to_json(), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    arc = next(layer for layer in spec["layers"] if layer["id"] == "route-arcs")
    assert len(arc["data"]) == 2
    unknown = next(row for row in arc["data"] if row["tip_title"] == "LAX → JFK")
    assert unknown["color"] == [148, 163, 184, 255]
    assert "Delay đến TB: Chưa có dữ liệu" in unknown["tip_body"]


def test_missing_airport_is_reported_and_never_placed_at_zero():
    data = pd.concat([routes(), pd.DataFrame([dict(origin="UNKNOWN", dest="JFK", flights=300)])], ignore_index=True)
    located, missing = route_map.locate_routes(data)
    assert len(located) == 2
    assert missing == {"codes": ["UNKNOWN"], "routes": 1, "flights": 300}
    deck, drawn, nodes, missing = route_map.build_map(data[data.origin == "UNKNOWN"])
    assert deck is None and drawn.empty and nodes.empty


def test_reference_duplicate_cannot_multiply_route_counts():
    reference = route_map.airport_reference()
    duplicate = pd.concat([reference, reference[reference.code == "JFK"]])
    with pytest.raises(pd.errors.MergeError):
        route_map.locate_routes(routes(), duplicate)


def test_dateline_view_is_local_instead_of_almost_the_entire_world():
    nodes = pd.DataFrame({"lon": [179., -179.], "lat": [52., 53.]})
    view, center = route_map.fitted_view(nodes)
    longitudes = [route_map.unwrap(x, center) for x in nodes.lon]
    assert max(longitudes)-min(longitudes) == pytest.approx(2)
    assert abs(abs(view.longitude)-180) < 1
    assert view.zoom > 4


def test_color_scale_distinguishes_early_arrival_and_missing_values():
    assert route_map.metric_color(-7., "avg_arr_delay_net") == list(route_map.PALETTE[0])
    assert route_map.metric_color(0., "delay15_rate") == list(route_map.PALETTE[0])
    assert route_map.metric_color(.5, "delay15_rate") == list(route_map.PALETTE[-1])
    assert route_map.metric_color(None, "delay15_rate") == [148, 163, 184]


def test_reference_has_valid_unique_coordinates_and_historical_pbi_key():
    data = route_map.airport_reference().set_index("code")
    assert data.index.is_unique
    assert data.loc["PBI", "source_ident"] == "KPBI"
    assert data.loc["JFK", "longitude"] == pytest.approx(-73.78, abs=.1)
    assert data.latitude.between(-90, 90).all()
    assert data.longitude.between(-180, 180).all()


def test_large_network_retains_every_directed_route_and_flight():
    codes = route_map.airport_reference().code.head(40).tolist()
    source = pd.DataFrame([dict(origin=a, dest=b, flights=100, delay15_rate=.2)
                           for a in codes for b in codes if a != b])
    deck, drawn, nodes, missing = route_map.build_map(source)
    spec = json.loads(deck.to_json())
    edges = next(layer["data"] for layer in spec["layers"] if layer["id"] == "route-arcs")
    assert len(edges) == len(drawn) == 40*39
    assert drawn.flights.sum() == 40*39*100
    assert len(nodes) == 40 and not missing["routes"]
    for layer in spec["layers"]:
        for prop in ("widthUnits", "radiusUnits"):
            if prop in layer:
                assert layer[prop] == "pixels"  # enum string, not a JS accessor
    assert all(len(edge["color"]) == 4 and edge["color"][3] == 255 for edge in edges)
