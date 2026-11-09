"""Geographic views of real aggregate routes; never fabricate flight tracks."""
from functools import lru_cache
import math
from pathlib import Path

import pandas as pd
import pydeck as pdk

COORDINATES = Path(__file__).resolve().parents[1]/"assets/airport_coordinates.csv"
MAP_METRICS = {
    "delay15_rate": {"label": "Tỷ lệ trễ ≥15 phút", "ceiling": .5, "ticks": ["0%", "25%", "≥50%"]},
    "avg_arr_delay_net": {"label": "Delay đến trung bình", "ceiling": 30., "ticks": ["≤0 phút", "15 phút", "≥30 phút"]},
    "cancel_rate": {"label": "Tỷ lệ hủy chuyến", "ceiling": .1, "ticks": ["0%", "5%", "≥10%"]},
}
PALETTE = [(45, 212, 191), (251, 191, 36), (251, 113, 133)]


@lru_cache(maxsize=1)
def airport_reference():
    data = pd.read_csv(COORDINATES, keep_default_na=False)
    if data.code.duplicated().any():
        raise ValueError("Airport reference contains duplicate codes")
    for field, limit in [("latitude", 90), ("longitude", 180)]:
        data[field] = pd.to_numeric(data[field], errors="raise")
        if not data[field].map(math.isfinite).all() or not data[field].between(-limit, limit).all():
            raise ValueError(f"Invalid {field} in airport reference")
    return data


def locate_routes(routes, reference=None):
    """Left joins preserve route identity and report every omitted coordinate."""
    reference = airport_reference() if reference is None else reference
    data = routes.copy()
    for side in ("origin", "dest"):
        rename = {"code": side, "name": f"{side}_name", "city": f"{side}_city",
                  "latitude": f"{side}_lat", "longitude": f"{side}_lon"}
        subset = reference[list(rename)].rename(columns=rename)
        data = data.merge(subset, how="left", on=side, validate="many_to_one")
    valid = data[["origin_lat", "origin_lon", "dest_lat", "dest_lon"]].notna().all(axis=1)
    missing = sorted(set(data.loc[data.origin_lat.isna(), "origin"]) |
                     set(data.loc[data.dest_lat.isna(), "dest"]))
    return data.loc[valid].copy(), {"codes": missing, "routes": int((~valid).sum()),
                                  "flights": int(data.loc[~valid, "flights"].sum())}


def metric_color(value, metric):
    if value is None or not math.isfinite(float(value)):
        return [148, 163, 184]
    ratio = min(1., max(0., float(value)/MAP_METRICS[metric]["ceiling"]))
    segment = min(int(ratio*2), 1)
    amount = ratio*2-segment
    return [round(a+(b-a)*amount) for a, b in zip(PALETTE[segment], PALETTE[segment+1])]


def pretty(value, suffix="%"):
    if value is None or not math.isfinite(float(value)):
        return "Chưa có dữ liệu"
    return f"{value*100:.1f}%" if suffix == "%" else f"{value:.1f} phút"


def longitude_center(longitudes):
    """Smallest circular extent, so Alaska/Guam don't force a 350° viewport."""
    values = sorted({float(x) % 360 for x in longitudes})
    if not values:
        return -98.
    gaps = [((values[(i+1) % len(values)]-value) % 360, i) for i, value in enumerate(values)]
    gap, index = max(gaps)
    if len(values) == 1:
        return (values[0]+180) % 360-180
    start = values[(index+1) % len(values)]
    return (start+(360-gap)/2+180) % 360-180


def unwrap(longitude, center):
    return (float(longitude)-center+180) % 360-180+center


def fitted_view(airports, pitch=0):
    center = longitude_center(airports.lon)
    lons = [unwrap(x, center) for x in airports.lon]
    ys = [math.log(math.tan(math.pi/4+math.radians(max(-80, min(80, y)))/2))/(2*math.pi)
          for y in airports.lat]
    lon_span = max(.5, max(lons)-min(lons))
    y_span = max(.005, max(ys)-min(ys))
    zoom = min(math.log2(900/(512*lon_span/360)), math.log2(470/(512*y_span)))
    latitude = math.degrees(2*math.atan(math.exp((min(ys)+max(ys))*math.pi))-math.pi/2)
    return pdk.ViewState(longitude=center, latitude=latitude, zoom=max(.5, min(6, zoom)),
                         pitch=pitch, bearing=0), center


def build_map(routes, metric="delay15_rate", *, camera="Toàn mạng đang chọn", three_d=False,
              reference=None):
    """One Arc per directed route; bubbles count incident departures/arrivals."""
    if metric not in MAP_METRICS:
        raise ValueError("Unknown map metric")
    data, missing = locate_routes(routes, reference)
    if data.empty:
        return None, data, pd.DataFrame(), missing
    data = data.sort_values("flights", kind="stable").copy()  # thin routes first
    nodes = {}
    for row in data.to_dict("records"):
        flights = int(row["flights"])
        for side, counter in [("origin", "departures"), ("dest", "arrivals")]:
            code = row[side]
            node = nodes.setdefault(code, {"code": code, "name": row[f"{side}_name"],
                "lat": row[f"{side}_lat"], "lon": row[f"{side}_lon"], "departures": 0, "arrivals": 0})
            node[counter] += flights
    airports = pd.DataFrame(nodes.values())
    airports["movements"] = airports.departures+airports.arrivals
    airports["radius"] = 3.+12.*(airports.movements/airports.movements.max()).pow(.5)
    airports["tip_title"] = airports.code + " · " + airports.name
    airports["tip_body"] = airports.apply(lambda r: f"Lượt đi: {r.departures:,.0f}\nLượt đến: {r.arrivals:,.0f}\nTrong các tuyến đang vẽ", axis=1)
    pitch = 38 if three_d else 0
    if camera == "Hoa Kỳ lục địa":
        center = -98.
        view = pdk.ViewState(longitude=center, latitude=38.5, zoom=3.1, pitch=pitch)
    else:
        view, center = fitted_view(airports, pitch)
    airports["lon"] = airports.lon.map(lambda x: unwrap(x, center))
    for side in ("origin", "dest"):
        data[f"{side}_lon"] = data[f"{side}_lon"].map(lambda x: unwrap(x, center))
    data["width"] = .5+5.5*(data.flights/data.flights.max()).pow(.5)
    values = data.get(metric, pd.Series(float("nan"), index=data.index))
    data["color"] = values.map(lambda x: metric_color(x, metric)+[255])
    data["tip_title"] = data.origin + " → " + data.dest
    data["tip_body"] = data.apply(lambda r: "\n".join([
        f"{r.origin_name} → {r.dest_name}", f"Số chuyến: {r.flights:,.0f}",
        f"Trễ ≥15 phút: {pretty(r.get('delay15_rate'))}",
        f"Delay đến TB: {pretty(r.get('avg_arr_delay_net'), 'minutes')}",
        f"Đúng giờ: {pretty(r.get('otp_operated'))}", f"Hủy chuyến: {pretty(r.get('cancel_rate'))}"]), axis=1)
    opacity = .32 if len(data) > 1000 else .65
    # Pass only render attributes: source KPI columns may contain null/NaN,
    # which must never leak as non-standard JSON into deck.gl's specification.
    arc_records = data[["origin_lon", "origin_lat", "dest_lon", "dest_lat", "width", "color", "tip_title", "tip_body"]].to_dict("records")
    node_records = airports.to_dict("records")
    common = dict(data=arc_records, id="route-arcs", pickable=True, auto_highlight=True,
        highlight_color=[255, 255, 255, 235], get_source_position="[origin_lon, origin_lat]",
        get_target_position="[dest_lon, dest_lat]", get_width="width", width_units=pdk.types.String("pixels"),
        width_min_pixels=.5)
    # A full annual network has >6,000 directed routes. A straight GPU line
    # preserves every route without allocating 32 arc segments per edge.
    if len(data) > 1000:
        connections = pdk.Layer("LineLayer", **common, get_color="color", width_scale=.5,
                                width_max_pixels=3, opacity=.24)
    else:
        connections = pdk.Layer("ArcLayer", **common, get_source_color="color", get_target_color="color",
            width_max_pixels=6, get_height=.45 if three_d else .25, get_tilt=35,
            num_segments=32, opacity=opacity)
    layers = [connections,
        pdk.Layer("ScatterplotLayer", data=node_records, id="airport-glow", get_position="[lon, lat]",
            get_radius="radius * 1.8", radius_units=pdk.types.String("pixels"), get_fill_color=[96, 165, 250, 35]),
        pdk.Layer("ScatterplotLayer", data=node_records, id="airport-nodes", pickable=True,
            get_position="[lon, lat]", get_radius="radius", radius_units=pdk.types.String("pixels"),
            get_fill_color=[125, 211, 252, 215], stroked=True, get_line_color=[225, 244, 255, 235],
            line_width_min_pixels=1)]
    deck = pdk.Deck(layers=layers, initial_view_state=view, map_style=pdk.map_styles.DARK,
        map_provider="carto", tooltip={"text": "{tip_title}\n{tip_body}",
            "style": {"backgroundColor": "#101c30", "color": "#e2e8f0", "fontSize": "13px",
                      "whiteSpace": "pre-line", "maxWidth": "360px"}})
    return deck, data, airports, missing
