"""One link per airport pair, preserving directional counts and valid populations."""
import math

import pandas as pd
import pydeck as pdk

from m5.directory import airport_profiles
from m5.metrics import summarize
from m5.route_map import fitted_view, unwrap

LINK_LAYER = "airport-connections"
NODE_LAYER = "network-airports"
VOLUME_COLORS = [[96, 165, 250], [45, 212, 191], [251, 191, 36], [251, 113, 133]]


def records(data):
    return data.astype(object).where(data.notna(), None).to_dict("records")


def connections(routes, hub):
    incident = routes[(routes.origin == hub) | (routes.dest == hub)].copy()
    if incident.empty:
        return pd.DataFrame()
    incident["peer"] = incident.dest.where(incident.origin == hub, incident.origin)
    result = []
    for peer, group in incident.groupby("peer", sort=True):
        if peer == hub:
            continue
        totals = summarize(records(group))
        result.append({"hub": hub, "peer": peer, **totals,
            "outbound": int(group.loc[group.origin == hub, "flights"].sum()),
            "inbound": int(group.loc[group.dest == hub, "flights"].sum())})
    return pd.DataFrame(result)


def color(value, minimum, maximum):
    ratio = 0.5 if maximum == minimum else (math.sqrt(value)-math.sqrt(minimum))/(math.sqrt(maximum)-math.sqrt(minimum))
    scaled = max(0., min(1., ratio))*(len(VOLUME_COLORS)-1)
    segment = min(int(scaled), len(VOLUME_COLORS)-2)
    amount = scaled-segment
    return [round(a+(b-a)*amount) for a, b in zip(VOLUME_COLORS[segment], VOLUME_COLORS[segment+1])]+[235]


def build_map(routes, hub, reference=None):
    """Connected endpoints only. Search/region filters never trim the hub's neighbors."""
    reference = airport_profiles() if reference is None else reference
    pairs = connections(routes, hub)
    codes = {hub} | (set(pairs.peer) if not pairs.empty else set())
    points = pd.DataFrame({"code": sorted(codes)}).merge(reference, on="code", how="left", validate="one_to_one")
    valid = points[["latitude", "longitude"]].notna().all(axis=1)
    missing = points.loc[~valid, "code"].tolist()
    points = points.loc[valid].copy().rename(columns={"latitude": "lat", "longitude": "lon"})
    if points.empty:
        return None, pairs, [], [], missing
    view, center = fitted_view(points)
    points["lon"] = points.lon.map(lambda value: unwrap(value, center))
    by_code = points.set_index("code").to_dict("index")
    node_records, edges = [], []
    lookup = {} if pairs.empty else pairs.set_index("peer").to_dict("index")
    total = 0 if pairs.empty else int(pairs.flights.sum())
    maximum = 1 if pairs.empty else float(pairs.flights.max())
    minimum = 1 if pairs.empty else float(pairs.flights.min())
    for code, point in by_code.items():
        movement = total if code == hub else lookup[code]["flights"]
        node_records.append({"code": code, "lon": point["lon"], "lat": point["lat"],
            "radius": 13 if code == hub else 4+6*math.sqrt(movement/maximum),
            "color": [251, 191, 36, 255] if code == hub else [125, 211, 252, 240],
            "tip_title": f"{code} · {point['name']}",
            "tip_body": f"{movement:,.0f} chuyến trong mạng đang xem\nBấm để xem các kết nối của sân bay này"})
    if hub in by_code:
        for row in records(pairs) if not pairs.empty else []:
            peer = row["peer"]
            if peer not in by_code:
                continue
            edges.append({"hub": hub, "peer": peer, "flights": int(row["flights"]),
                "source": [by_code[hub]["lon"], by_code[hub]["lat"]],
                "target": [by_code[peer]["lon"], by_code[peer]["lat"]],
                "width": 1.5+8*math.sqrt(row["flights"]/maximum),
                "color": color(row["flights"], minimum, maximum),
                "tip_title": f"{hub} ↔ {peer}",
                "tip_body": f"Tổng hai chiều: {row['flights']:,.0f} chuyến\n{hub} → {peer}: {row['outbound']:,.0f}\n{peer} → {hub}: {row['inbound']:,.0f}\nBấm đường để xem thống kê cặp sân bay"})
    layers = [pdk.Layer("ArcLayer", id=LINK_LAYER, data=edges, pickable=True, auto_highlight=True,
        get_source_position="source", get_target_position="target", get_source_color="color", get_target_color="color",
        get_width="width", width_units=pdk.types.String("pixels"), width_min_pixels=2, width_max_pixels=10,
        get_height=.25, get_tilt=35, num_segments=40, highlight_color=[255, 255, 255, 255], opacity=.8),
        pdk.Layer("ScatterplotLayer", id=NODE_LAYER, data=node_records, pickable=True, auto_highlight=True,
            get_position="[lon, lat]", get_radius="radius", radius_units=pdk.types.String("pixels"),
            get_fill_color="color", stroked=True, get_line_color=[225, 244, 255, 235], line_width_min_pixels=1)]
    deck = pdk.Deck(layers=layers, initial_view_state=view, map_style=pdk.map_styles.DARK, map_provider="carto",
        tooltip={"text": "{tip_title}\n{tip_body}", "style": {"whiteSpace": "pre-line", "maxWidth": "360px"}})
    return deck, pairs, node_records, edges, missing


def decode_selection(event, nodes, edges):
    """Use indices against server-owned records; never trust client-supplied stats."""
    indices = (event or {}).get("selection", {}).get("indices", {})
    for layer, kind, data, field in [(NODE_LAYER, "airport", nodes, "code"), (LINK_LAYER, "pair", edges, "peer")]:
        selected = indices.get(layer, [])
        if selected and type(selected[0]) is int and 0 <= selected[0] < len(data):
            return kind, data[selected[0]][field]
    return None


def pair_rows(routes, hub, peer, direction="both"):
    outbound = (routes.origin == hub) & (routes.dest == peer)
    inbound = (routes.origin == peer) & (routes.dest == hub)
    mask = outbound if direction == "outbound" else inbound if direction == "inbound" else outbound | inbound
    return routes.loc[mask].copy()


def outcome_counts(totals):
    """Disjoint status buckets; severe delays are already included in delayed15."""
    fields = ["flights", "on_time", "delayed15", "cancelled", "diverted"]
    if any(totals.get(key) is None for key in fields):
        return None
    known = [totals[key] for key in fields[1:]]
    unknown = totals["flights"]-sum(known)
    if unknown < -1e-6 or any(value < 0 for value in known):
        raise ValueError("Flight outcomes do not form a valid disjoint population")
    return pd.DataFrame({"status": ["Đúng giờ / trễ <15′", "Trễ ≥15′", "Hủy chuyến", "Chuyển hướng", "Thiếu giờ đến hợp lệ"],
                         "flights": known+[max(0, unknown)]})
