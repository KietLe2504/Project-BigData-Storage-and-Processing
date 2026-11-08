"""Plotly figures built only from actual M2 aggregates; no synthetic flights."""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from m5.metrics import summarize

COLORS = {"traffic": "#60a5fa", "ontime": "#2dd4bf", "delay": "#fbbf24",
          "cancel": "#fb7185", "purple": "#c4a2ff", "muted": "#64748b"}
PALETTE = ["#60a5fa", "#2dd4bf", "#fbbf24", "#c4a2ff", "#fb7185", "#38bdf8",
           "#a3e635", "#f472b6", "#fb923c", "#818cf8", "#22d3ee", "#e879f9",
           "#fca5a5", "#34d399", "#fcd34d", "#93c5fd", "#d8b4fe", "#67e8f9",
           "#bef264", "#f9a8d4", "#fdba74", "#a5b4fc", "#5eead4", "#cbd5e1"]
AIRLINES = dict(zip(["AA", "AS", "B6", "DL", "F9", "G4", "HA", "MQ", "NK", "OO", "UA", "WN",
                     "9E", "OH", "YX", "YV", "QX", "ZW", "C5", "G7", "CP", "SY", "MX", "9K"], PALETTE))
LABELS = {"flights": "Số chuyến", "otp_operated": "Tỷ lệ đúng giờ", "cancel_rate": "Tỷ lệ hủy",
          "delay15_rate": "Tỷ lệ trễ ≥15 phút", "avg_arr_delay_net": "Delay đến trung bình (phút)",
          "reliability_score": "Điểm tin cậy", "carrier": "Hãng bay", "origin": "Sân bay đi",
          "dest": "Sân bay đến", "year": "Năm"}
RATE_METRICS = {"otp_operated", "cancel_rate", "delay15_rate"}
RISK_SCALE = [[0, "#2dd4bf"], [.5, "#fbbf24"], [1, "#fb7185"]]


def rgba(hex_color, alpha):
    return "rgba(%d,%d,%d,%s)" % (*[int(hex_color[i:i+2], 16) for i in (1, 3, 5)], alpha)


def rollup_frame(df, keys):
    records = []
    for group, data in df.groupby(keys, dropna=False, sort=True):
        values = group if isinstance(group, tuple) else (group,)
        records.append({**dict(zip(keys, values)), **summarize(data.to_dict("records"))})
    return pd.DataFrame(records)


def arrival_counts(totals):
    """Disjoint buckets, all using the arr_n population (not all scheduled flights)."""
    fields = ["on_time", "delayed15", "delayed60", "arr_n"]
    if any(totals.get(k) is None for k in fields):
        return []
    values = [totals["on_time"], totals["delayed15"]-totals["delayed60"], totals["delayed60"]]
    if any(v < 0 for v in values) or abs(sum(values)-totals["arr_n"]) > 1e-6:
        raise ValueError("Arrival counts do not form disjoint arr_n buckets")
    return values


def traffic(df, mode="Diện tích"):
    fig = go.Figure()
    if mode == "Cột":
        fig.add_bar(x=df.period, y=df.flights, marker_color=COLORS["traffic"], name="Chuyến bay")
    else:
        fig.add_scatter(x=df.period, y=df.flights, mode="lines", fill="tozeroy",
                        line=dict(color=COLORS["traffic"], width=2.5),
                        fillcolor=rgba(COLORS["traffic"], .16), name="Chuyến bay")
    fig.update_traces(hovertemplate="%{x|%m/%Y}<br><b>%{y:,.0f}</b> chuyến<extra></extra>")
    fig.update_layout(yaxis_title="Chuyến bay", xaxis_title=None)
    return fig


def arrival_donut(totals):
    values = arrival_counts(totals)
    if not values or sum(values) == 0:
        return None
    fig = go.Figure(go.Pie(labels=["Đúng giờ / trễ <15′", "Trễ 15–59′", "Trễ ≥60′"], values=values,
                           hole=.72, sort=False, direction="clockwise", textinfo="percent",
                           textfont=dict(color="#0b1324", size=13),
                           marker=dict(colors=[COLORS["ontime"], COLORS["delay"], COLORS["cancel"]],
                                       line=dict(color="#101c30", width=4)),
                           hovertemplate="%{label}<br>%{value:,.0f} chuyến · %{percent}<extra></extra>"))
    fig.add_annotation(text=f"<b>{totals['otp_operated']:.1%}</b><br>ĐÚNG GIỜ", x=.5, y=.5,
                       showarrow=False, font_size=22)
    fig.update_layout(legend=dict(orientation="h", y=-.12, x=.5, xanchor="center"))
    return fig


def reliability(df):
    fig = go.Figure()
    for key, name, color in [("otp_operated", "Đúng giờ", COLORS["ontime"]),
                             ("delay15_rate", "Trễ ≥15′", COLORS["delay"]),
                             ("cancel_rate", "Hủy chuyến", COLORS["cancel"])]:
        fig.add_scatter(x=df.period, y=df[key], name=name, mode="lines+markers",
                        line=dict(color=color, width=2), marker=dict(size=4),
                        hovertemplate="%{x|%m/%Y}<br>%{y:.1%}<extra>%{fullData.name}</extra>")
    fig.update_layout(yaxis=dict(tickformat=".0%", title="Tỷ lệ"), xaxis_title=None,
                      legend=dict(orientation="h", y=1.14))
    return fig


def arrival_stack(df):
    fig = go.Figure()
    for label, key, color in [("Đúng giờ / <15′", "on_time", COLORS["ontime"]),
                               ("Trễ 15–59′", "moderate", COLORS["delay"]),
                               ("Trễ ≥60′", "delayed60", COLORS["cancel"])]:
        counts = df.delayed15-df.delayed60 if key == "moderate" else df[key]
        fractions = counts/df.arr_n.replace(0, float("nan"))
        fig.add_bar(x=df.period, y=fractions, name=label, marker_color=color,
                    hovertemplate="%{x|%m/%Y}<br>%{y:.1%}<extra>%{fullData.name}</extra>")
    fig.update_layout(barmode="stack", yaxis=dict(range=[0, 1], tickformat=".0%", title="Chuyến có dữ liệu đến"),
                      legend=dict(orientation="h", y=1.14), xaxis_title=None, bargap=.2)
    return fig


def ranking_bar(df, dimension, metric):
    favorable = metric in ("flights", "otp_operated", "reliability_score")
    view = df.sort_values(metric)
    scale = ["#315479", COLORS["ontime"]] if favorable else RISK_SCALE
    fig = px.bar(view, x=metric, y=dimension, orientation="h", color=metric,
                 color_continuous_scale=scale, labels=LABELS)
    fig.update_layout(coloraxis_showscale=False, yaxis_title=None)
    fig.update_traces(marker_line_width=0, marker_cornerradius=5,
                      hovertemplate=("%{y}<br>%{x:.1%}<extra></extra>" if metric in RATE_METRICS else
                                     "%{y}<br>%{x:,.1f}<extra></extra>"))
    if metric in RATE_METRICS:
        fig.update_xaxes(tickformat=".0%")
    return fig


def bubble(df, dimension, animate=False):
    """Animate common observed groups only; never fill absent groups with zeros."""
    data = df.copy()
    kwargs = {}
    if animate and data.year.nunique() > 1:
        groups = data.groupby("year")[dimension].apply(set)
        common = set.intersection(*groups.tolist())
        data = data[data[dimension].isin(common)].sort_values(["year", dimension])
        if data.empty:
            return None
        data["year"] = data.year.astype(str)
        kwargs.update(animation_frame="year", animation_group=dimension)
    max_flights = float(data.flights.max()) if not data.empty else 1
    colors = {v: AIRLINES.get(v, PALETTE[i % len(PALETTE)]) for i, v in enumerate(sorted(data[dimension].unique()))}
    color_options = {"color": dimension, "color_discrete_map": colors}
    if dimension == "origin":
        color_options = {"color": "reliability_score", "range_color": [0, 100],
                         "color_continuous_scale": [[0, COLORS["cancel"]], [.65, COLORS["delay"]], [1, COLORS["ontime"]]]}
    fig = px.scatter(data, x="flights", y="delay15_rate", size="flights",
                     hover_name=dimension, size_max=55, **color_options,
                     range_x=[0, max(1, max_flights*1.12)], range_y=[0, 1],
                     labels=LABELS, **kwargs)
    fig.update_traces(marker=dict(opacity=.85, line=dict(width=1.5, color="#d7edff")),
                      hovertemplate="%{hovertext}<br>%{x:,.0f} chuyến<br>Trễ ≥15′: %{y:.1%}<extra></extra>")
    fig.update_yaxes(tickformat=".0%")
    fig.update_layout(legend=dict(orientation="h", y=-.22))
    if fig.layout.updatemenus:
        fig.layout.updatemenus[0].buttons[0].label = "▶ Phát"
        fig.layout.updatemenus[0].buttons[1].label = "❚❚ Dừng"
    return fig


def share_treemap(df, dimension, top_n=15):
    ordered = df.sort_values("flights", ascending=False)
    main, rest = ordered.head(top_n), ordered.iloc[top_n:]
    labels = main[dimension].astype(str).tolist()
    values = main.flights.tolist()
    if not rest.empty:
        labels.append("Nhóm còn lại")
        values.append(float(rest.flights.sum()))
    ids = ["total"] + [f"group_{i}" for i in range(len(labels))]
    colors = ["#172941"] + [AIRLINES.get(label, PALETTE[i % len(PALETTE)]) for i, label in enumerate(labels)]
    fig = go.Figure(go.Treemap(ids=ids, labels=["Toàn bộ đã chọn"]+labels,
                               parents=[""]+["total"]*len(labels), values=[sum(values)]+values,
                               branchvalues="total", marker=dict(colors=colors, line=dict(width=3, color="#101c30")),
                               textinfo="label+percent root", textfont_size=16,
                               hovertemplate="%{label}<br>%{value:,.0f} chuyến<extra></extra>"))
    return fig


def route_sankey(df):
    origins, destinations = sorted(df.origin.unique()), sorted(df.dest.unique())
    labels = [f"{x} · đi" for x in origins] + [f"{x} · đến" for x in destinations]
    source = {code: i for i, code in enumerate(origins)}
    target = {code: i+len(origins) for i, code in enumerate(destinations)}
    origin_colors = {code: PALETTE[i % len(PALETTE)] for i, code in enumerate(origins)}
    fig = go.Figure(go.Sankey(arrangement="snap", node=dict(label=labels, pad=18, thickness=16,
        color=[origin_colors[c] for c in origins]+[COLORS["ontime"]]*len(destinations),
        line=dict(color="#101c30", width=1)), link=dict(
        source=[source[c] for c in df.origin], target=[target[c] for c in df.dest],
        value=df.flights.tolist(), color=[rgba(origin_colors[c], .38) for c in df.origin],
        customdata=(df.origin+" → "+df.dest).tolist(),
        hovertemplate="%{customdata}<br><b>%{value:,.0f}</b> chuyến<extra></extra>")))
    return fig


def hour_polar(df):
    return go.Figure(go.Barpolar(theta=df.dep_hour*15, r=df.delay15_rate*100, width=14,
        marker=dict(color=df.delay15_rate, colorscale=RISK_SCALE, line=dict(color="#101c30", width=2)),
        customdata=df.dep_hour,
        hovertemplate="%{customdata}:00<br>Trễ ≥15′: %{r:.1f}%<extra></extra>"))


def boxes(df, keys):
    fig = go.Figure()
    for i, (_, row) in enumerate(df.iterrows()):
        label = " / ".join(str(int(row[k])) if isinstance(row[k], (int, float)) else str(row[k]) for k in keys)
        color = AIRLINES.get(row.get("carrier"), PALETTE[i % len(PALETTE)])
        fig.add_trace(go.Box(name=label, q1=[row.q1], median=[row["median"]], q3=[row.q3],
                            lowerfence=[row.whisker_low], upperfence=[row.whisker_high],
                            line=dict(color=color, width=2), fillcolor=rgba(color, .24), boxpoints=False))
    fig.update_layout(showlegend=False, yaxis_title="Delay (phút)")
    fig.add_hline(y=15, line_dash="dot", line_color=COLORS["delay"], annotation_text="Ngưỡng trễ 15′")
    return fig


def quartile_range(df, labels):
    fig = go.Figure()
    for i, (_, row) in enumerate(df.iterrows()):
        color = PALETTE[i % len(PALETTE)]
        fig.add_scatter(x=[row.q1, row.q3], y=[labels[i], labels[i]], mode="lines",
                        line=dict(color=color, width=9), showlegend=False,
                        hovertemplate="%{y}<br>%{x:.0f} phút<extra>Q1–Q3</extra>")
        fig.add_scatter(x=[row["median"]], y=[labels[i]], mode="markers",
                        marker=dict(color="#f8fafc", size=8, line=dict(color=color, width=2)),
                        showlegend=False, hovertemplate="%{y}<br>Trung vị: %{x:.0f} phút<extra></extra>")
    fig.update_layout(xaxis_title="Delay (phút)", yaxis_title=None)
    return fig
