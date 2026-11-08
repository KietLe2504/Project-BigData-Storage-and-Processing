import json

import pandas as pd
import pytest

from m5 import directory


def route_rows():
    return pd.DataFrame([
        dict(year=2022, origin="JFK", dest="LAX", flights=100, arr_n=100, delayed15=10,
             on_time=90, sum_arr_delay=1000),
        dict(year=2023, origin="JFK", dest="LAX", flights=10, arr_n=10, delayed15=10,
             on_time=0, sum_arr_delay=300),
        dict(year=2022, origin="LAX", dest="UNKNOWN", flights=5, arr_n=0, delayed15=0,
             on_time=0, sum_arr_delay=0),
    ])


def test_airport_directory_includes_destination_only_and_unknown_codes():
    data = directory.airports(route_rows()).set_index("code")
    assert set(data.index) == {"JFK", "LAX", "UNKNOWN"}
    assert data.loc["JFK", "departures"] == 110
    assert data.loc["JFK", "arrivals"] == 0
    assert pd.isna(data.loc["JFK", "delay15_rate"])  # no arrivals, not 0% delay
    assert data.loc["LAX", "delay15_rate"] == pytest.approx(20/110)
    assert data.loc["LAX", "avg_arr_delay_net"] == pytest.approx(1300/110)
    assert data.loc["JFK", "destinations"] == 1  # same endpoint across years
    assert data.loc["UNKNOWN", "arrivals"] == 5 and data.loc["UNKNOWN", "departures"] == 0
    assert data.loc["UNKNOWN", "name"] == "Chưa có tên trong danh mục"
    assert data.departures.sum() == data.arrivals.sum() == route_rows().flights.sum()


def test_carrier_profiles_preserve_unknowns_weight_rates_and_observed_months():
    monthly = pd.DataFrame([
        dict(carrier="AA", year=2022, month=1, flights=100, arr_n=90, delayed15=9),
        dict(carrier="AA", year=2023, month=3, flights=10, arr_n=10, delayed15=10),
        dict(carrier="ZZ", year=2022, month=2, flights=5, arr_n=0, delayed15=0),
    ])
    result = directory.carriers(monthly).set_index("code")
    assert result.loc["AA", "delay15_rate"] == pytest.approx(.19)
    assert result.loc["AA", "observed_months"] == 2
    assert result.loc["AA", "first_month"] == "2022-01"
    assert result.loc["AA", "last_month"] == "2023-03"
    assert result.loc["AA", "name"] == "American Airlines Inc."
    assert result.loc["ZZ", "name"] == "Chưa có tên trong danh mục"
    assert pd.isna(result.loc["ZZ", "delay15_rate"])


def test_reference_join_rejects_duplicate_codes():
    reference = directory.airport_profiles()
    duplicate = pd.concat([reference, reference.iloc[[0]]])
    with pytest.raises(pd.errors.MergeError):
        directory.airports(route_rows(), reference=duplicate)


def test_all_cancelled_route_does_not_poison_airport_average_delay():
    cancelled = pd.DataFrame([dict(year=2024, origin="JFK", dest="LAX", flights=5,
        arr_n=0, delayed15=0, on_time=0, sum_arr_delay=None)])
    source = pd.concat([route_rows(), cancelled], ignore_index=True)
    assert source.sum_arr_delay.isna().any()  # real pandas null representation
    airport = directory.airports(source).set_index("code").loc["LAX"]
    assert airport.arrivals == 115
    assert airport.delay15_rate == pytest.approx(20/110)
    assert airport.avg_arr_delay_net == pytest.approx(1300/110)


def test_literal_search_ignores_case_accents_and_handles_no_results():
    data = pd.DataFrame([dict(code="SGN", name="Sân bay Tân Sơn Nhất", city="Hồ Chí Minh"),
                         dict(code="JFK", name="John F. Kennedy", city="New York")])
    assert directory.search(data, "  tan son  ", ["code", "name", "city"]).code.tolist() == ["SGN"]
    assert directory.search(data, "jFk", ["code", "name"]).code.tolist() == ["JFK"]
    assert directory.search(data, ".*", ["name"]).empty
    assert directory.search(data, "no-match", ["name"]).empty
    assert len(directory.search(data, "", ["name"])) == 2


def test_airport_profile_map_omits_unlocated_and_highlights_selected_without_nan_json():
    data = directory.airports(route_rows())
    deck = directory.airport_map(data, "LAX")
    spec = json.loads(deck.to_json(), parse_constant=lambda value: pytest.fail(value))
    layer = spec["layers"][0]
    assert layer["radiusUnits"] == "pixels"
    assert {row["code"] for row in layer["data"]} == {"JFK", "LAX"}
    assert next(row for row in layer["data"] if row["code"] == "LAX")["color"] == [251, 191, 36, 255]
    assert directory.airport_map(data[data.code == "UNKNOWN"], "UNKNOWN") is None


def test_saved_references_are_unique_and_match_provenance():
    import hashlib
    for stem in ("airline_reference", "airport_details"):
        path = directory.ASSETS/f"{stem}.csv"
        metadata = json.loads(path.with_suffix(".source.json").read_text())
        data = pd.read_csv(path)
        assert not data.code.duplicated().any()
        assert len(data) == metadata["records"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == metadata["reference_sha256"]
    assert set(directory.airport_profiles().code) == set(pd.read_csv(directory.ASSETS/"airport_details.csv").code)
