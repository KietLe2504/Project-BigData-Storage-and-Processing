"""Observed airline/airport profiles, with provenance and weighted M2 statistics."""
from functools import lru_cache
from pathlib import Path
import unicodedata

import pandas as pd
import pydeck as pdk

from m5.charts import rollup_frame
from m5.route_map import airport_reference, fitted_view, unwrap

ASSETS = Path(__file__).resolve().parents[1]/"assets"


def _rollup(data, keys):
    # A zero-valid-arrival group may have a null delay sum. Pandas represents
    # that as NaN; normalize it before summarize() so it cannot poison totals.
    nullable = data.astype(object).where(data.notna(), None)
    return rollup_frame(nullable, keys)


@lru_cache(maxsize=1)
def airline_reference():
    data = pd.read_csv(ASSETS/"airline_reference.csv", keep_default_na=False)
    if data.code.duplicated().any():
        raise ValueError("Duplicate airline reference codes")
    return data


@lru_cache(maxsize=1)
def airport_profiles():
    details = pd.read_csv(ASSETS/"airport_details.csv", keep_default_na=False)
    return airport_reference().merge(details, on="code", how="left", validate="one_to_one")


def carriers(monthly, reference=None):
    if monthly.empty:
        return pd.DataFrame()
    reference = airline_reference() if reference is None else reference
    data = _rollup(monthly, ["carrier"]).rename(columns={"carrier": "code"})
    periods = monthly.assign(period=monthly.year.astype(str)+"-"+monthly.month.astype(str).str.zfill(2))
    coverage = periods.groupby("carrier").agg(first_month=("period", "min"), last_month=("period", "max"),
                                               observed_months=("period", "nunique"))
    data = data.merge(coverage, left_on="code", right_index=True, validate="one_to_one")
    data = data.merge(reference, on="code", how="left", validate="one_to_one")
    data["name"] = data.name.fillna("Chưa có tên trong danh mục")
    return data.sort_values("code").reset_index(drop=True)


def airports(routes, reference=None):
    """Union of both route endpoints, including airports observed only as destinations."""
    if routes.empty:
        return pd.DataFrame()
    reference = airport_profiles() if reference is None else reference
    dep = routes.groupby("origin").agg(departures=("flights", "sum"), destinations=("dest", "nunique"))
    arr = routes.groupby("dest").agg(arrivals=("flights", "sum"), origins=("origin", "nunique"))
    data = dep.join(arr, how="outer")
    data.index.name = "code"
    for field in ("departures", "arrivals", "destinations", "origins"):
        data[field] = data[field].fillna(0).astype("int64")
    arrivals = _rollup(routes, ["dest"]).rename(columns={"dest": "code"})
    data = data.reset_index().merge(arrivals[["code", "delay15_rate", "avg_arr_delay_net", "otp_operated"]],
                                    on="code", how="left", validate="one_to_one")
    data = data.merge(reference, on="code", how="left", validate="one_to_one")
    data["name"] = data.name.fillna("Chưa có tên trong danh mục")
    return data.sort_values("code").reset_index(drop=True)


def search(data, text, fields):
    """Literal Unicode-insensitive search; user input is never a regular expression."""
    def normalized(value):
        return "".join(c for c in unicodedata.normalize("NFKD", str(value).casefold())
                       if not unicodedata.combining(c)).replace("đ", "d")
    query = normalized(text).strip()
    if not query:
        return data
    values = data.reindex(columns=fields).fillna("").astype(str).agg(" ".join, axis=1)
    return data[values.map(normalized).str.contains(query, regex=False)]


def airport_map(data, selected):
    located = data.dropna(subset=["latitude", "longitude"]).copy()
    if located.empty:
        return None
    located = located.rename(columns={"latitude": "lat", "longitude": "lon"})
    view, center = fitted_view(located)
    located["lon"] = located.lon.map(lambda x: unwrap(x, center))
    located["color"] = located.code.map(lambda code: [251, 191, 36, 255] if code == selected else [96, 165, 250, 185])
    located["radius"] = located.code.map(lambda code: 11 if code == selected else 4)
    located["city"] = located.city.fillna("")
    records = located[["code", "name", "city", "lat", "lon", "color", "radius", "departures", "arrivals"]].to_dict("records")
    return pdk.Deck(layers=[pdk.Layer("ScatterplotLayer", data=records, id="directory-airports",
        get_position="[lon, lat]", get_radius="radius", radius_units=pdk.types.String("pixels"),
        get_fill_color="color", pickable=True)], initial_view_state=view, map_style=pdk.map_styles.DARK,
        map_provider="carto", tooltip={"text": "{code} · {name}\n{city}\nChuyến đi: {departures}\nChuyến đến: {arrivals}"})
