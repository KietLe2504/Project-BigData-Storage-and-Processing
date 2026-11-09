"""Interactive historical BTS observatory backed by one pinned MongoDB snapshot."""
import math
from datetime import datetime, timezone
from functools import partial
from html import escape
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from pymongo.errors import PyMongoError

from m5 import airport_network, charts, directory, route_carriers, route_map
from m5.contracts import BOX_KEYS
from m5.metrics import summarize
from m5.mongo import connect
from m5.queries import active_run, query_rows

st.set_page_config(page_title="AERO · Air Traffic Observatory", page_icon="✈", layout="wide")
st.markdown((Path(__file__).parent/"assets/dashboard.css").read_text(), unsafe_allow_html=True)
PAGES = ["Tổng quan", "Thời gian & mùa vụ", "Hãng bay", "Sân bay xuất phát",
         "Tuyến bay", "Danh mục hãng bay & sân bay", "Phân phối delay", "Streaming", "Dữ liệu & vận hành"]
with st.sidebar:
    st.markdown("## ✈ AERO")
    st.caption("AIR TRAFFIC OBSERVATORY")
    st.markdown('<span class="source-badge">● BTS HISTORICAL</span>', unsafe_allow_html=True)
    st.write("")
    page = st.radio("Khám phá dữ liệu", PAGES, label_visibility="collapsed")
    st.divider()
    st.caption("Khám phá bằng hover, zoom, bộ lọc và nút phát theo năm. Mỗi biểu đồ giữ nguyên phạm vi dữ liệu được ghi bên dưới.")
    if st.button("↻ Làm mới dữ liệu", width="stretch"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()


@st.cache_resource
def database():
    return connect()


@st.cache_data(ttl=60, max_entries=48)
def fetch(snapshot_id, collection, filters):
    _, db = database()
    return query_rows(db, snapshot_id, collection, dict(filters))


def rows(collection, filters=None):
    normalized = tuple(sorted((k, tuple(v)) for k, v in (filters or {}).items()))
    return fetch(run["_id"], collection, normalized)


def frame(collection, filters=None):
    return pd.DataFrame(rows(collection, filters))


@st.cache_data(ttl=60, max_entries=12)
def directory_data(snapshot_id, year):
    filters = () if year is None else (("year", (year,)),)
    monthly = pd.DataFrame(fetch(snapshot_id, "kpi_month_carrier", filters))
    routes = pd.DataFrame(fetch(snapshot_id, "kpi_year_route", filters))
    return directory.carriers(monthly), directory.airports(routes), monthly, routes


@st.cache_data(ttl=60, max_entries=96)
def fetch_pair_carriers(snapshot_id, hub, peer, years, direction):
    _, db = database()
    return route_carriers.pair_carriers(db, snapshot_id, hub, peer, years, direction)


@st.cache_data(ttl=60, max_entries=96)
def fetch_carrier_destinations(snapshot_id, carrier, years):
    _, db = database()
    return route_carriers.carrier_destinations(db, snapshot_id, carrier, years)


def fmt(value, style="number"):
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "—"
    if style == "percent":
        return f"{value:.1%}"
    if style == "minutes":
        return f"{value:.1f} phút"
    return f"{value:,.0f}"


def plot(fig, height=360):
    if fig is None:
        st.info("Chưa đủ dữ liệu cho biểu đồ này trong phạm vi đã chọn.")
        return
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", height=height,
                      margin=dict(l=16, r=20, t=35, b=24),
                      font=dict(family="Arial, sans-serif", size=12, color="#c4d5e8"),
                      colorway=charts.PALETTE,
                      modebar=dict(bgcolor="rgba(0,0,0,0)", color="#8fa9c4", activecolor="#5eead4"))
    fig.update_xaxes(gridcolor="#22334a", zerolinecolor="#344a62")
    fig.update_yaxes(gridcolor="#22334a", zerolinecolor="#344a62")
    st.plotly_chart(fig, use_container_width=True,
                    config={"displaylogo": False, "scrollZoom": False,
                            "toImageButtonOptions": {"format": "png", "scale": 2, "filename": "aero_chart"}})


def title(kicker, heading):
    st.markdown(f'<div class="panel-kicker">{escape(kicker)}</div>', unsafe_allow_html=True)
    st.subheader(heading)


def table(data, filename):
    df = data if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
    st.dataframe(df, width="stretch", hide_index=True)
    st.download_button("↓ Tải bảng đang xem · CSV", df.to_csv(index=False).encode("utf-8-sig"),
                       file_name=filename, mime="text/csv")


def choose_time(include_month=True, single_year=False):
    years = sorted({int(x[:4]) for x in run["manifest"]["coverage"]["months"]})
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            if single_year:
                year = st.selectbox("Năm", years, index=len(years)-1)
                filters = {"year": [year]}
            else:
                filters = {"year": st.multiselect("Năm", years, default=years)}
        if include_month:
            with col2:
                filters["month"] = st.multiselect("Tháng", list(range(1, 13)), default=list(range(1, 13)))
    if any(not v for v in filters.values()):
        st.info("Chọn ít nhất một giá trị cho mỗi bộ lọc.")
        st.stop()
    if 2026 in filters["year"]:
        st.caption("2026 chỉ có tháng 1–3. Khi so sánh các năm, chọn cùng kỳ để có góc nhìn phù hợp.")
    return filters


def show_overview():
    data = rows("kpi_month_overall", choose_time())
    if not data:
        st.info("Không có dữ liệu trong thời gian đã chọn.")
        return
    totals = summarize(data)
    for col, label, key, style in zip(st.columns(5),
        ["Chuyến bay sau cleaning", "Tỷ lệ đúng giờ", "Trễ từ 15 phút", "Hủy chuyến", "Delay đến trung bình"],
        ["flights", "otp_operated", "delay15_rate", "cancel_rate", "avg_arr_delay_net"],
        ["number", "percent", "percent", "percent", "minutes"]):
        col.metric(label, fmt(totals.get(key), style))
    st.write("")
    df = pd.DataFrame(data).sort_values(["year", "month"])
    df["period"] = pd.to_datetime(dict(year=df.year, month=df.month, day=1))
    left, right = st.columns([1.65, 1])
    with left, st.container(border=True):
        title("TRAFFIC PULSE", "Nhịp vận hành theo tháng")
        mode = st.radio("Kiểu biểu đồ lưu lượng", ["Diện tích", "Cột"], horizontal=True, label_visibility="collapsed")
        plot(charts.traffic(df, mode), 330)
    with right, st.container(border=True):
        title("ARRIVAL MIX", "Cơ cấu chuyến đến")
        plot(charts.arrival_donut(totals), 360)
        st.caption("Mẫu số: chuyến có dữ liệu giờ đến hợp lệ; không bao gồm chuyến hủy/chuyển hướng.")
    left, right = st.columns(2)
    with left, st.container(border=True):
        title("SERVICE QUALITY", "Đúng giờ và độ trễ")
        plot(charts.reliability(df), 340)
    with right, st.container(border=True):
        title("MONTHLY COMPOSITION", "Mức trễ trong từng tháng")
        plot(charts.arrival_stack(df), 340)
    with st.expander("Dữ liệu nguồn và cách tính"):
        st.caption("Tỷ lệ tính từ tổng số đếm. Delay âm biểu thị đến sớm; giá trị thiếu giữ null. Biểu đồ cơ cấu chia các nhóm không chồng lấn trong cùng quần thể chuyến đến hợp lệ.")
        table(df.drop(columns="period"), "aero_monthly.csv")


def show_time():
    grain = st.selectbox("Góc nhìn", ["Ngày trong kỳ", "Tháng trong năm · toàn kỳ", "Ngày lịch · toàn kỳ", "Giờ khởi hành · toàn kỳ"])
    if grain == "Ngày trong kỳ":
        df = frame("kpi_day_overall", choose_time())
        if df.empty:
            st.info("Không có ngày phù hợp bộ lọc.")
            return
        df["date"] = pd.to_datetime(dict(year=df.year, month=df.month, day=df.day))
        df = df.sort_values("date")
        title("DAILY RHYTHM", "Nhịp bay từng ngày")
        daily = df.set_index("date").flights.asfreq("D")
        fig = go.Figure(go.Scatter(x=daily.index, y=daily, mode="lines", name="Chuyến bay", connectgaps=False,
                                   line=dict(color=charts.COLORS["traffic"], width=1.7),
                                   fill="tozeroy", fillcolor=charts.rgba(charts.COLORS["traffic"], .1)))
        average = daily.rolling(7, min_periods=7).mean()
        fig.add_scatter(x=average.index, y=average, name="Trung bình 7 ngày", connectgaps=False,
                        line=dict(color=charts.COLORS["delay"], width=2.5))
        fig.update_layout(yaxis_title="Chuyến bay", legend=dict(orientation="h", y=1.12))
        plot(fig, 420)
        st.caption("Đường vàng dùng 7 ngày lịch có đủ dữ liệu; khoảng ngày không chọn được để trống, không điền thành 0.")
    elif grain.startswith("Tháng"):
        st.caption("Đã gộp toàn bộ năm trong snapshot; không áp dụng bộ lọc năm.")
        df = frame("kpi_month_of_year_overall")
        left, right = st.columns(2)
        with left, st.container(border=True):
            title("SEASONALITY", "Tháng nào dễ trễ hơn?")
            fig = px.bar(df, x="month", y="delay15_rate", color="delay15_rate",
                         color_continuous_scale=charts.RISK_SCALE,
                         labels={"month": "Tháng", "delay15_rate": "Tỷ lệ trễ"})
            fig.update_layout(coloraxis_showscale=False)
            fig.update_yaxes(tickformat=".0%")
            plot(fig)
        with right, st.container(border=True):
            title("SEASONAL VOLUME", "Lưu lượng theo tháng lịch")
            fig = px.bar(df, x="month", y="flights", color="month", color_discrete_sequence=charts.PALETTE,
                         labels={"month": "Tháng", "flights": "Chuyến bay"})
            fig.update_layout(showlegend=False, coloraxis_showscale=False)
            plot(fig)
    elif grain.startswith("Ngày lịch"):
        st.caption("Cùng ngày/tháng qua các năm; phạm vi là toàn snapshot. Mỗi ô là đúng KPI của ngày lịch đó.")
        df = frame("kpi_calendar_day_overall")
        grid = df.pivot(index="day", columns="month", values="delay15_rate")
        title("CALENDAR HEATMAP", "Bản đồ nhiệt độ trễ trong năm")
        fig = go.Figure(go.Heatmap(x=grid.columns.tolist(), y=grid.index.tolist(), z=grid.to_numpy(),
            colorscale=charts.RISK_SCALE, xgap=5, ygap=3, colorbar=dict(title="Tỷ lệ trễ", tickformat=".0%"),
            hovertemplate="Ngày %{y} / tháng %{x}<br>Trễ ≥15′: %{z:.1%}<extra></extra>"))
        fig.update_layout(xaxis=dict(title="Tháng", dtick=1), yaxis=dict(title="Ngày", autorange="reversed", dtick=2))
        plot(fig, 640)
    else:
        st.caption("Giờ khởi hành theo lịch trong dữ liệu BTS; đã gộp toàn kỳ.")
        df = frame("kpi_hour_overall")
        left, right = st.columns(2)
        with left, st.container(border=True):
            title("24-HOUR CLOCK", "Đồng hồ độ trễ")
            fig = charts.hour_polar(df)
            fig.update_layout(polar=dict(bgcolor="rgba(0,0,0,0)",
                angularaxis=dict(rotation=90, direction="clockwise", tickvals=list(range(0,360,45)),
                                 ticktext=[f"{x:02d}:00" for x in range(0,24,3)], gridcolor="#2b4059"),
                radialaxis=dict(ticksuffix="%", gridcolor="#2b4059")))
            plot(fig, 420)
        with right, st.container(border=True):
            title("DEPARTURE VOLUME", "Lưu lượng theo giờ")
            fig = px.bar(df, x="dep_hour", y="flights", color="delay15_rate",
                         color_continuous_scale=charts.RISK_SCALE,
                         labels={"dep_hour":"Giờ khởi hành", "flights":"Chuyến bay", "delay15_rate":"Tỷ lệ trễ"})
            fig.update_layout(coloraxis_colorbar=dict(tickformat=".0%"))
            plot(fig, 420)
    with st.expander("Xem bảng dữ liệu"):
        table(df, "aero_time.csv")


def show_ranking(dimension):
    filters = choose_time()
    df = frame(f"kpi_month_{dimension}", filters)
    if df.empty:
        st.info("Không có dữ liệu phù hợp.")
        return
    selected = st.multiselect("Hãng bay" if dimension == "carrier" else "Sân bay xuất phát", sorted(df[dimension].unique()))
    if selected:
        df = df[df[dimension].isin(selected)]
    left, right = st.columns(2)
    with left:
        minimum = st.number_input("Số chuyến tối thiểu để xếp hạng", min_value=1, value=200, step=100)
    with right:
        metric = st.selectbox("Chỉ số so sánh", ["flights", "delay15_rate", "cancel_rate", "otp_operated", "avg_arr_delay_net", "reliability_score"],
                              format_func=lambda x: charts.LABELS[x])
    ranking = charts.rollup_frame(df, [dimension])
    ranking = ranking[ranking.flights >= minimum]
    if ranking.empty:
        st.info("Không có nhóm đạt số chuyến tối thiểu.")
        return
    ranking = ranking.sort_values(metric, ascending=metric in ("delay15_rate", "cancel_rate", "avg_arr_delay_net"))
    top = ranking.head(20)
    rank_tab, compare_tab, share_tab, animation_tab = st.tabs(["Xếp hạng", "Quy mô & hiệu suất", "Cơ cấu lưu lượng", "▶ Diễn biến theo năm"])
    with rank_tab:
        title("PERFORMANCE RANKING", "So sánh các nhóm dẫn đầu")
        plot(charts.ranking_bar(top, dimension, metric), max(360, min(700, len(top)*30+90)))
        st.caption("Hiển thị tối đa 20 nhóm theo chỉ số đã chọn. Màu thanh giúp nhận biết mức chỉ số.")
    with compare_tab:
        title("VOLUME × DELAY", "Quy mô lớn có đi kèm trễ nhiều?")
        plot(charts.bubble(ranking, dimension), 510)
        st.caption("Mỗi bong bóng là một nhóm; diện tích biểu thị số chuyến, trục dọc là tỷ lệ trễ ≥15 phút.")
        if dimension == "origin":
            st.caption("Màu bong bóng theo điểm tin cậy: đỏ → vàng → xanh ngọc tương ứng điểm thấp → cao.")
    with share_tab:
        title("TRAFFIC SHARE", "Cơ cấu lưu lượng")
        plot(charts.share_treemap(ranking, dimension), 460)
        st.caption("Diện tích ô theo số chuyến của các nhóm đạt ngưỡng lọc. Các nhóm ngoài top 15 được gom thành Nhóm còn lại.")
    with animation_tab:
        title("YEAR-BY-YEAR", "Bấm Phát để khám phá từng năm")
        by_year = charts.rollup_frame(df[df[dimension].isin(top[dimension])], ["year", dimension])
        plot(charts.bubble(by_year, dimension, animate=True), 550)
        st.caption("Chạy theo năm với các tháng đã chọn. Animation chỉ dùng nhóm có quan sát ở mọi năm được hiển thị; không tạo chuyến bay giả cho nhóm thiếu. Năm 2026 chỉ có quý 1.")
    st.caption("Tỷ lệ và điểm được tính lại từ tổng số đếm. Điểm tin cậy là chỉ số tự định nghĩa của nhóm (0–100).")
    with st.expander("Xem bảng xếp hạng đầy đủ"):
        table(ranking, f"aero_{dimension}.csv")


def directory_table(data, columns, filename):
    view = data.reindex(columns=columns).copy()
    for field in ("delay15_rate", "otp_operated", "cancel_rate"):
        if field in view:
            view[field] = view[field].map(lambda value: fmt(value, "percent"))
    if "avg_arr_delay_net" in view:
        view["avg_arr_delay_net"] = view.avg_arr_delay_net.map(lambda value: fmt(value, "minutes"))
    table(view.rename(columns=columns), filename)


def show_carrier_directory(catalog, monthly, filters):
    query = st.text_input("Tìm hãng theo mã hoặc tên", placeholder="Ví dụ: AA, American, SkyWest…", key="directory_carrier_search")
    found = directory.search(catalog, query, ["code", "name"])
    st.caption(f"Tìm thấy {len(found):,}/{len(catalog):,} hãng trong phạm vi đang chọn.")
    if found.empty:
        st.info("Không có hãng phù hợp. Hãy thử mã hoặc một phần tên khác.")
        return
    names = found.set_index("code").name.to_dict()
    selected = st.selectbox("Xem hồ sơ hãng bay", found.code.tolist(),
        format_func=lambda code: f"{code} · {names[code]}", key="directory_carrier")
    profile = found.set_index("code").loc[selected]
    with st.container(border=True):
        title("AIRLINE PROFILE", profile["name"])
        st.write(f"**Mã hãng trong M2:** {selected} · **Tháng có bản ghi:** {profile.first_month} → {profile.last_month} ({profile.observed_months} tháng)")
        for col, label, field, style in zip(st.columns(4),
            ["Chuyến bay", "Đúng giờ", "Trễ ≥15 phút", "Hủy chuyến"],
            ["flights", "otp_operated", "delay15_rate", "cancel_rate"],
            ["number", "percent", "percent", "percent"]):
            col.metric(label, fmt(profile[field], style))
        st.caption("KPI thuộc các chuyến mang mã hãng này trong M2; tỷ lệ được tính lại từ tổng số đếm của kỳ đang chọn.")
    with st.container():
        title("TRAFFIC HISTORY", "Lưu lượng theo tháng")
        history = monthly[monthly.carrier == selected].copy().sort_values(["year", "month"])
        history["period"] = pd.to_datetime(dict(year=history.year, month=history.month, day=1))
        # Leave unobserved months blank rather than drawing a continuous fictitious history.
        series = history.set_index("period").flights.asfreq("MS")
        fig = go.Figure(go.Scatter(x=series.index, y=series, mode="lines+markers", connectgaps=False,
            line=dict(color=charts.AIRLINES.get(selected, charts.COLORS["traffic"])), name="Chuyến bay"))
        fig.update_layout(yaxis_title="Chuyến bay", xaxis_title=None)
        plot(fig, 330)
    departures, arrivals = st.columns(2)
    with departures:
        title("DEPARTURE FOOTPRINT", "Các sân bay xuất phát nhiều chuyến nhất")
        footprint = frame("kpi_year_carrier_origin", {**filters, "carrier": [selected]})
        if footprint.empty:
            st.info("Chưa có thống kê sân bay cho hãng này trong kỳ đã chọn.")
        else:
            top = charts.rollup_frame(footprint, ["origin"]).nlargest(10, "flights")
            plot(charts.ranking_bar(top, "origin", "flights"), 330)
            st.caption(f"Top {len(top)} trong {footprint.origin.nunique()} sân bay xuất phát có bản ghi của hãng.")
    with arrivals:
        title("DESTINATION FOOTPRINT", "Các sân bay điểm đến nhiều chuyến nhất")
        destinations = fetch_carrier_destinations(run["_id"], selected, tuple(filters.get("year", [])))
        if destinations is None:
            st.info("Chưa nạp bảng hãng theo tuyến cho snapshot này để thống kê điểm đến. Chạy scripts/load_route_carriers.ps1 theo hướng dẫn bản đồ kết nối.")
        elif not destinations:
            st.info("Chưa có thống kê điểm đến cho hãng này trong kỳ đã chọn.")
        elif sum(row["flights"] for row in destinations) != profile["flights"]:
            st.warning("Thống kê điểm đến chưa khớp tổng chuyến của hãng trong kỳ đã chọn. Hãy làm mới hoặc kiểm tra bảng hãng theo tuyến.")
        else:
            top = pd.DataFrame(destinations).head(10)
            plot(charts.ranking_bar(top, "dest", "flights"), 330)
            st.caption(f"Top {len(top)} trong {len(destinations)} sân bay điểm đến theo lịch có bản ghi của hãng. "
                "Đếm từ mọi sân bay xuất phát, áp dụng cùng phạm vi năm của hồ sơ.")
    title("AIRLINE DIRECTORY", "Danh sách hãng bay")
    directory_table(found, {"code": "Mã hãng", "name": "Tên hãng", "flights": "Chuyến bay",
        "otp_operated": "Đúng giờ", "delay15_rate": "Trễ ≥15 phút", "cancel_rate": "Hủy chuyến",
        "first_month": "Tháng đầu có bản ghi", "last_month": "Tháng cuối có bản ghi"}, "aero_airlines_directory.csv")


def on_airport_network_select(chart_key, pair_key, nodes, edges, found_codes):
    selected = airport_network.decode_selection(st.session_state.get(chart_key), nodes, edges)
    if selected is None:
        return
    kind, code = selected
    if kind == "pair":
        st.session_state[pair_key] = code
    else:
        st.session_state["directory_airport"] = code
        if code not in found_codes:
            st.session_state["directory_airport_search"] = ""
            st.session_state["directory_region"] = "Tất cả"


def show_airport_pair(routes, hub, peer, filters):
    with st.container(border=True):
        title("AIRPORT PAIR DETAILS", f"Thống kê kết nối {hub} ↔ {peer}")
        direction = st.radio("Chiều thống kê", ["both", "outbound", "inbound"], horizontal=True,
            format_func=lambda key: {"both": "Cả hai chiều", "outbound": f"{hub} → {peer}", "inbound": f"{peer} → {hub}"}[key],
            key=f"pair-direction-{hub}-{peer}")
        selected_rows = airport_network.pair_rows(routes, hub, peer, direction)
        if selected_rows.empty:
            st.info("Không có chuyến trong chiều và phạm vi năm đang chọn.")
            return
        totals = summarize(airport_network.records(selected_rows))
        for col, label, field in zip(st.columns(5),
            ["Tổng chuyến theo lịch", "Đúng giờ / trễ <15′", "Trễ ≥15 phút", "Hủy chuyến", "Chuyển hướng"],
            ["flights", "on_time", "delayed15", "cancelled", "diverted"]):
            col.metric(label, fmt(totals.get(field)))
        st.caption(f"Trễ ≥15′ trên chuyến đến hợp lệ: {fmt(totals.get('delay15_rate'), 'percent')} · "
            f"Delay đến trung bình: {fmt(totals.get('avg_arr_delay_net'), 'minutes')}. "
            "Các nhóm trạng thái không chồng lấn; trễ ≥60′ đã nằm trong trễ ≥15′.")
        left, right = st.columns(2)
        with left:
            title("AIRLINE MIX ON THIS PAIR", "Phân bố hãng bay trên cặp sân bay")
            data = fetch_pair_carriers(run["_id"], hub, peer, tuple(filters.get("year", [])), direction)
            if data is None:
                st.info("Chưa nạp bảng hãng theo tuyến cho snapshot này. Chạy scripts/load_route_carriers.ps1 theo hướng dẫn bản đồ kết nối.")
            elif not data or sum(row["flights"] for row in data) != totals["flights"]:
                st.warning("Phân bố hãng chưa khớp tổng chuyến của cặp sân bay trong phạm vi này. Hãy làm mới hoặc kiểm tra bảng bổ sung.")
            else:
                mix = pd.DataFrame(data).groupby("carrier", as_index=False).flights.sum().sort_values("flights", ascending=False)
                names = directory.airline_reference().set_index("code").name.to_dict()
                mix["name"] = mix.carrier.map(lambda code: names.get(code, code))
                mix["label"] = mix.carrier+" · "+mix.name
                mix["share"] = mix.flights/totals["flights"]
                fig = px.bar(mix, x="flights", y="label", orientation="h", color="carrier",
                    color_discrete_map=charts.AIRLINES, custom_data=["share"],
                    labels={"flights": "Chuyến bay", "label": "", "carrier": "Hãng"})
                fig.update_traces(hovertemplate="%{y}<br>%{x:,.0f} chuyến · %{customdata[0]:.1%}<extra></extra>")
                fig.update_layout(showlegend=False, yaxis=dict(categoryorder="total ascending"))
                plot(fig, max(330, len(mix)*28+90))
                st.caption("Đếm đúng theo năm, hãng, sân bay đi và đến từ Parquet M2 đã làm sạch; tổng hãng khớp tổng chuyến của phạm vi này.")
        with right:
            title("FLIGHT OUTCOMES", "Cơ cấu trạng thái chuyến bay")
            outcomes = airport_network.outcome_counts(totals)
            if outcomes is None:
                st.info("Thiếu số đếm để phân loại trạng thái chuyến bay.")
            else:
                outcomes = outcomes[outcomes.flights > 0]
                fig = px.pie(outcomes, names="status", values="flights", hole=.58,
                    color="status", color_discrete_map={"Đúng giờ / trễ <15′": charts.COLORS["ontime"],
                        "Trễ ≥15′": charts.COLORS["delay"], "Hủy chuyến": charts.COLORS["cancel"],
                        "Chuyển hướng": charts.COLORS["purple"], "Thiếu giờ đến hợp lệ": charts.COLORS["muted"]})
                fig.update_traces(textinfo="percent", hovertemplate="%{label}<br>%{value:,.0f} chuyến · %{percent}<extra></extra>")
                fig.update_layout(legend=dict(orientation="h", y=-.12))
                plot(fig, 380)
        directional = []
        for origin, dest in [(hub, peer), (peer, hub)]:
            data = selected_rows[(selected_rows.origin == origin) & (selected_rows.dest == dest)]
            if not data.empty:
                directional.append({"Chiều tuyến": f"{origin} → {dest}", **summarize(airport_network.records(data))})
        directory_table(pd.DataFrame(directional), {"Chiều tuyến": "Chiều tuyến", "flights": "Tổng chuyến",
            "on_time": "Đúng giờ / trễ <15′", "delayed15": "Trễ ≥15′", "cancelled": "Hủy", "diverted": "Chuyển hướng",
            "delay15_rate": "Tỷ lệ trễ ≥15′", "avg_arr_delay_net": "Delay đến trung bình"}, f"aero_pair_{hub}_{peer}.csv")


def show_airport_connections(catalog, routes, hub, filters, found_codes):
    title("CONNECTED AIRPORTS", f"Mạng kết nối của {hub} · tất cả chiều đi và đến")
    deck, pairs, nodes, edges, missing = airport_network.build_map(routes, hub, reference=directory.airport_profiles())
    context = f"{run['_id'][:12]}-{'-'.join(map(str, filters.get('year', []))) or 'all'}-{hub}"
    chart_key, pair_key = f"airport-network-{context}", f"airport-pair-{context}"
    if deck is not None:
        if not pairs.empty:
            minimum, maximum = int(pairs.flights.min()), int(pairs.flights.max())
            st.markdown(f'''<div class="route-map-legend"><div><strong>Tổng chuyến hai chiều trên mỗi đường</strong>
                <div class="route-volume-gradient"></div><div class="route-map-ticks"><span>{minimum:,} chuyến</span>
                <span>{maximum:,} chuyến</span></div></div><div>Đường dày hơn → nhiều chuyến hơn<br>
                Điểm vàng → {escape(hub)} · Điểm xanh → sân bay kết nối<br>Bấm điểm để đổi sân bay · Bấm đường để xem thống kê</div></div>''', unsafe_allow_html=True)
        st.pydeck_chart(deck, height=580, use_container_width=True, key=chart_key,
            on_select=partial(on_airport_network_select, chart_key, pair_key, nodes, edges, found_codes),
            selection_mode="single-object")
    else:
        st.info("Chưa có tọa độ để vẽ mạng kết nối này.")
    if missing:
        st.warning("Thiếu tọa độ cho: "+", ".join(missing)+". Các cặp này vẫn có thể chọn ở danh sách thống kê.")
    if pairs.empty:
        st.info("Không có cặp sân bay kết nối trong phạm vi năm đang chọn.")
        return
    st.caption(f"{len(pairs)} sân bay kết nối · {len(edges)} đường đã vẽ · {pairs.flights.sum():,.0f} chuyến hai chiều. "
        "Một đường gộp cả chiều đi và đến; độ dày và màu dùng thang căn bậc hai. Các đường nối minh họa kết nối lịch sử giữa sân bay.")
    peer_names = catalog.set_index("code").name.to_dict()
    peers = pairs.sort_values("flights", ascending=False).peer.tolist()
    peer = st.selectbox("Xem thống kê cặp sân bay · hoặc bấm một đường trên bản đồ", [None]+peers,
        format_func=lambda code: "Chọn một đường kết nối…" if code is None else f"{hub} ↔ {code} · {peer_names.get(code, code)}", key=pair_key)
    if peer is not None:
        show_airport_pair(routes, hub, peer, filters)


def show_airport_directory(catalog, routes, filters):
    left, right = st.columns([1.7, 1])
    with left:
        query = st.text_input("Tìm sân bay theo mã, tên hoặc thành phố", placeholder="Ví dụ: JFK, Los Angeles, Honolulu…", key="directory_airport_search")
    with right:
        regions = sorted(catalog.region.dropna().unique())
        region = st.selectbox("Bang / vùng lãnh thổ", ["Tất cả"]+regions, key="directory_region")
    found = directory.search(catalog, query, ["code", "name", "city", "icao", "region"])
    if region != "Tất cả":
        found = found[found.region == region]
    st.caption(f"Tìm thấy {len(found):,}/{len(catalog):,} sân bay; gồm cả sân bay chỉ xuất hiện ở chiều đến.")
    if found.empty:
        st.info("Không có sân bay phù hợp. Hãy thử từ khóa khác hoặc bỏ lọc vùng.")
        return
    names = found.set_index("code").name.to_dict()
    selected = st.selectbox("Xem hồ sơ sân bay", found.code.tolist(),
        format_func=lambda code: f"{code} · {names[code]}", key="directory_airport")
    profile = found.set_index("code").loc[selected]
    with st.container(border=True):
        title("AIRPORT PROFILE", profile["name"])
        left, right = st.columns(2)
        def known(field):
            value = profile.get(field)
            return "Chưa có thông tin" if pd.isna(value) or value == "" else str(value)
        with left:
            st.write(f"**Mã sân bay M2:** {selected} · **ICAO:** {known('icao')}")
            st.write(f"**Thành phố:** {known('city')}")
            st.write(f"**Quốc gia / vùng:** {known('country')} · {known('region')}")
            types = {"large_airport": "Sân bay lớn", "medium_airport": "Sân bay vừa", "small_airport": "Sân bay nhỏ", "closed": "Đã đóng theo danh mục tham chiếu"}
            st.write(f"**Phân loại tham chiếu:** {types.get(profile.get('airport_type'), known('airport_type'))}")
            st.write(f"**Độ cao:** {known('elevation_ft')} ft")
            if pd.notna(profile.get("latitude")) and pd.notna(profile.get("longitude")):
                st.write(f"**Tọa độ:** {profile.latitude:.5f}, {profile.longitude:.5f}")
            for field, label in [("website", "Website sân bay ↗"), ("reference_url", "Hồ sơ OurAirports ↗")]:
                url = profile.get(field)
                if isinstance(url, str) and url.startswith("https://"):
                    st.link_button(label, url)
        with right:
            st.markdown("**Khám phá mạng đường bay bên dưới**")
            st.write("Chọn sân bay để xem toàn bộ sân bay có chuyến đi hoặc đến. Bấm vào đường nối để xem lưu lượng, trạng thái chuyến bay và phân bố hãng của cặp sân bay đó.")
            st.caption("Tìm kiếm và lọc vùng chỉ giới hạn danh sách hồ sơ; bản đồ vẫn giữ đủ các sân bay kết nối.")
    for col, label, value, style in zip(st.columns(4),
        ["Chuyến đi theo lịch", "Chuyến đến theo lịch", "Sân bay kết nối", "Trễ ≥15′ · chuyến đến"],
        [profile.departures, profile.arrivals,
         len(set(routes.loc[routes.origin == selected, "dest"]) | set(routes.loc[routes.dest == selected, "origin"])),
         profile.delay15_rate], ["number", "number", "number", "percent"]):
        col.metric(label, fmt(value, style))
    st.caption("Lượt đi/đến lấy từ KPI tuyến sau cleaning, gồm chuyến hủy theo lịch. Tỷ lệ trễ dùng chuyến đến hợp lệ của các tuyến đi vào sân bay. Mỗi chuyến có hai đầu; không cộng lượt mọi sân bay thành tổng chuyến.")
    show_airport_connections(catalog, routes, selected, filters, found.code.tolist())
    left, right = st.columns(2)
    with left:
        title("AIRLINE PRESENCE", "Hãng có chuyến xuất phát tại sân bay")
        footprint = frame("kpi_year_carrier_origin", {**filters, "origin": [selected]})
        if footprint.empty:
            st.info("Chưa có bản ghi hãng xuất phát tại sân bay trong kỳ này.")
        else:
            top = charts.rollup_frame(footprint, ["carrier"]).nlargest(10, "flights")
            plot(charts.ranking_bar(top, "carrier", "flights"), 330)
    with right:
        title("AIRPORT CONNECTIONS", "Các tuyến nhiều chuyến nhất · cả hai chiều")
        incident = routes[(routes.origin == selected) | (routes.dest == selected)]
        top = charts.rollup_frame(incident, ["origin", "dest"]).nlargest(10, "flights")
        top["route"] = top.origin+" → "+top.dest
        plot(charts.ranking_bar(top, "route", "flights"), 330)
    title("AIRPORT DIRECTORY", "Danh sách sân bay")
    directory_table(found, {"code": "Mã sân bay", "name": "Tên sân bay", "city": "Thành phố", "region": "Bang / vùng",
        "country": "Quốc gia", "icao": "ICAO", "departures": "Chuyến đi theo lịch", "arrivals": "Chuyến đến theo lịch",
        "delay15_rate": "Trễ ≥15′ · chuyến đến", "avg_arr_delay_net": "Delay đến trung bình"}, "aero_airports_directory.csv")


def show_directory():
    title("AVIATION DIRECTORY", "Tra cứu hãng bay và sân bay")
    st.write("Tìm hiểu các hãng và sân bay có trong dữ liệu M2, xem hồ sơ cùng quy mô hoạt động trong giai đoạn đã chọn.")
    years = sorted({int(x[:4]) for x in run["manifest"]["coverage"]["months"]})
    year = st.selectbox("Phạm vi hồ sơ và thống kê", [None]+years,
        format_func=lambda value: "Toàn bộ giai đoạn M2" if value is None else str(value), key="directory_year")
    filters = {} if year is None else {"year": [year]}
    carriers, airports, monthly, routes = directory_data(run["_id"], year)
    for col, label, value in zip(st.columns(3), ["Hãng có bản ghi", "Sân bay có bản ghi", "Chuyến bay trong phạm vi"],
        [len(carriers), len(airports), monthly.flights.sum() if not monthly.empty else 0]):
        col.metric(label, fmt(value))
    st.caption("Danh mục bao phủ các mã có bản ghi trong phạm vi đã chọn. Thống kê là dữ liệu lịch sử; năm 2026 chỉ gồm tháng 1–3.")
    kind = st.radio("Loại hồ sơ", ["✈ Hãng bay", "📍 Sân bay"], horizontal=True,
                    label_visibility="collapsed", key="directory_kind")
    if kind == "✈ Hãng bay":
        if carriers.empty:
            st.info("Chưa có dữ liệu hãng bay trong phạm vi này.")
        else:
            show_carrier_directory(carriers, monthly, filters)
    else:
        if airports.empty:
            st.info("Chưa có dữ liệu tuyến để lập danh mục sân bay trong phạm vi này.")
        else:
            show_airport_directory(airports, routes, filters)
    with st.expander("Nguồn thông tin và phạm vi danh mục"):
        st.markdown("Tên hãng đối chiếu [BTS Airline Codes](https://www.bts.gov/topics/airlines-and-airports/airline-codes). "
            "Tên, vị trí và hồ sơ sân bay dùng [OurAirports](https://ourairports.com/data/), lưu cục bộ cùng ngày tải và nguồn. "
            "Thông tin tham chiếu có thể cập nhật khác thời kỳ KPI. Mã M2 được giữ nguyên; tháng đầu/cuối có bản ghi không phải ngày thành lập hay ngừng hoạt động. "
            "Danh mục phục vụ các hãng, sân bay xuất hiện trong M2, không phải toàn bộ hãng và sân bay trên thế giới.")


def show_route_map(df):
    title("GEOGRAPHIC NETWORK", "Toàn cảnh mạng đường bay")
    left, right = st.columns([1.2, 1])
    with left:
        metric = st.selectbox("Màu tuyến biểu thị", list(route_map.MAP_METRICS),
            format_func=lambda key: route_map.MAP_METRICS[key]["label"], key="map_metric")
    with right:
        codes = sorted(set(df.origin) | set(df.dest))
        focus = st.selectbox("Tập trung một sân bay · cả chiều đi và đến", ["Tất cả sân bay"]+codes, key="map_focus")
    selected = df if focus == "Tất cả sân bay" else df[(df.origin == focus) | (df.dest == focus)]
    with st.expander("Tùy chỉnh mạng tuyến và góc nhìn", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            minimum = st.number_input("Số chuyến tối thiểu / tuyến", min_value=1, value=1, step=50, key="map_minimum")
            mode = st.radio("Phạm vi tuyến", ["Toàn bộ tuyến", "Top tuyến nhiều chuyến"], index=1, key="map_mode")
        with col2:
            camera = st.selectbox("Góc nhìn bản đồ", ["Toàn mạng đang chọn", "Hoa Kỳ lục địa"], key="map_camera")
            three_d = st.checkbox("Góc nhìn nghiêng 3D", value=False, key="map_3d")
        with col3:
            limit = st.slider("Số tuyến trong chế độ Top", min_value=10, max_value=500, value=150, step=10, key="map_limit")
    eligible = selected[selected.flights >= minimum]
    if eligible.empty:
        st.info("Không có tuyến đạt số chuyến tối thiểu. Hãy giảm ngưỡng hoặc chọn sân bay khác.")
        return
    selected = eligible if mode == "Toàn bộ tuyến" else eligible.nlargest(limit, "flights")
    deck, drawn, airports, missing = route_map.build_map(selected, metric, camera=camera, three_d=three_d)
    if missing["routes"]:
        st.warning(f"Chưa vẽ {missing['routes']:,} tuyến ({missing['flights']:,} chuyến) vì thiếu tọa độ: "
                   + ", ".join(missing["codes"]) + ". Các tuyến này vẫn có trong bảng dữ liệu.")
    if deck is None:
        st.info("Chưa có tọa độ cho các sân bay trong bộ lọc này.")
        return
    records = drawn.astype(object).where(drawn.notna(), None).to_dict("records")
    totals = summarize(records)
    for col, name, value in zip(st.columns(4),
        ["Tuyến đang vẽ", "Sân bay trên bản đồ", "Chuyến trong các tuyến", "Tỷ lệ trễ ≥15 phút"],
        [f"{len(drawn):,}", f"{len(airports):,}", fmt(totals.get("flights")), fmt(totals.get("delay15_rate"), "percent")]):
        col.metric(name, value)
    info = route_map.MAP_METRICS[metric]
    ticks = info["ticks"]
    st.markdown(f'''<div class="route-map-legend">
        <div><strong>Màu tuyến · {escape(info['label'])}</strong>
        <div class="route-map-gradient"></div><div class="route-map-ticks">
        <span>{ticks[0]}</span><span>{ticks[1]}</span><span>{ticks[2]}</span></div></div>
        <div>Đường dày hơn → nhiều chuyến hơn<br>Điểm lớn hơn → nhiều lượt đi/đến hơn<br>
        Màu xám → chưa có chỉ tiêu</div></div>''', unsafe_allow_html=True)
    st.pydeck_chart(deck, height=680, use_container_width=True, key="route-network-map")
    share = drawn.flights.sum()/eligible.flights.sum()
    st.caption(f"Đang vẽ {len(drawn):,}/{len(eligible):,} tuyến đạt bộ lọc, chiếm {share:.1%} số chuyến của các tuyến đó. "
               "Rê chuột vào đường bay hoặc sân bay để xem chi tiết; kéo và cuộn để khám phá bản đồ.")
    if len(drawn) > 1000:
        st.caption("Mạng nhiều tuyến dùng đường nối gọn để đọc toàn cảnh; tập trung một sân bay hoặc chọn Top để xem các cung riêng.")
    with st.expander("Cách đọc bản đồ và nguồn tọa độ"):
        st.markdown("""- Mỗi đường nối là **một chiều origin → dest**; tooltip ghi số chuyến, tỷ lệ trễ, delay đến trung bình, đúng giờ và hủy chuyến.
- Độ dày đường và bán kính điểm dùng thang căn bậc hai để giữ các tuyến nhỏ có thể nhìn thấy. Số chuyến chính xác nằm trong tooltip/bảng.
- Mỗi sân bay cộng riêng lượt đi và lượt đến từ các tuyến đang vẽ; không cộng các điểm sân bay thành tổng số chuyến của mạng.
- Đây là **KPI lịch sử theo năm**, đường nối minh họa giữa hai sân bay; không phải quỹ đạo hoặc vị trí máy bay đang bay.
- Tọa độ được ghép theo mã sân bay từ [OurAirports](https://ourairports.com/data/) và lưu sẵn trong project. Bản đồ nền CARTO cần Internet để tải.
""")
    with st.expander("Chi tiết các tuyến đang vẽ trên bản đồ"):
        columns = [key for key in ["year", "origin", "dest", "flights", "delay15_rate", "avg_arr_delay_net", "otp_operated", "cancel_rate"] if key in drawn]
        table(drawn[columns].sort_values("flights", ascending=False), "aero_route_map.csv")


def show_routes():
    filters = choose_time(include_month=False, single_year=True)
    st.caption("KPI tuyến theo năm; không áp dụng bộ lọc tháng hoặc hãng bay.")
    df = frame("kpi_year_route", filters)
    if df.empty:
        st.info("Không có tuyến trong năm đã chọn.")
        return
    origin, dest = st.columns(2)
    with origin:
        origins = st.multiselect("Sân bay đi", sorted(df.origin.unique()))
    if origins:
        df = df[df.origin.isin(origins)]
    with dest:
        destinations = st.multiselect("Sân bay đến", sorted(df.dest.unique()))
    if destinations:
        df = df[df.dest.isin(destinations)]
    if df.empty:
        st.info("Không có tuyến phù hợp.")
        return
    df = df.copy()
    df["route"] = df.origin+" → "+df.dest
    map_tab, flow_tab, volume_tab, quality_tab = st.tabs(["Bản đồ mạng bay", "Luồng bay · Sankey", "Lưu lượng tuyến", "Lưu lượng & độ trễ"])
    with map_tab:
        show_route_map(df)
    with flow_tab:
        limit = st.slider("Số tuyến nổi bật cho Sankey và các biểu đồ so sánh", min_value=5, max_value=40, value=15, step=5)
        top = df.nlargest(limit, "flights")
        title("ROUTE FLOW", "Dòng chảy giữa các sân bay")
        plot(charts.route_sankey(top), max(460, min(720, len(top)*23)))
        st.caption(f"Độ rộng luồng theo số chuyến của {len(top)} tuyến nhiều chuyến nhất trong bộ lọc; không phải toàn bộ mạng bay.")
    with volume_tab:
        title("BUSIEST ROUTES", "Các tuyến nhiều chuyến nhất")
        plot(charts.ranking_bar(top, "route", "flights"), max(380, len(top)*24))
    with quality_tab:
        title("ROUTE PERFORMANCE", "Tuyến bận rộn và rủi ro trễ")
        fig = px.scatter(top, x="flights", y="delay15_rate", size="flights", color="delay15_rate",
                         color_continuous_scale=charts.RISK_SCALE, hover_name="route", size_max=55, labels=charts.LABELS)
        fig.update_yaxes(tickformat=".0%")
        fig.update_layout(coloraxis_colorbar=dict(tickformat=".0%"))
        plot(fig, 460)
    with st.expander("Xem toàn bộ tuyến trong bộ lọc"):
        table(df, "aero_routes.csv")


def show_boxes():
    collection = st.selectbox("Mức thống kê", list(BOX_KEYS))
    keys = BOX_KEYS[collection]
    filters = {}
    if "year" in keys:
        filters["year"] = [st.selectbox("Năm", sorted({int(x[:4]) for x in run["manifest"]["coverage"]["months"]}))]
    else:
        st.caption("Bảng này đã gộp qua các năm trong toàn snapshot.")
    if "month" in keys:
        filters["month"] = [st.selectbox("Tháng", list(range(1, 13)))]
    filters["var"] = [st.selectbox("Loại delay", ["arr", "dep"], format_func=lambda x: "Đến" if x == "arr" else "Khởi hành")]
    filters["population"] = [st.selectbox("Quần thể", ["all", "late"], format_func=lambda x: "Tất cả hợp lệ" if x == "all" else "Trễ từ 15 phút")]
    df = frame(f"box_{collection}", filters)
    if df.empty:
        st.info("Không có thống kê box cho bộ lọc này.")
        return
    if "carrier" in keys:
        chosen = st.multiselect("Hãng bay", sorted(df.carrier.unique()))
        if chosen:
            df = df[df.carrier.isin(chosen)]
    label_keys = [k for k in keys if k not in ("var", "population")]
    labels = [" / ".join(str(row[k]) for k in label_keys) for _, row in df.iterrows()]
    box_tab, range_tab, outlier_tab = st.tabs(["Box-plot nhiều màu", "Khoảng tứ phân vị", "Ngoại lệ & quy mô"])
    with box_tab:
        title("DELAY DISTRIBUTION", "Phân phối độ trễ theo nhóm")
        plot(charts.boxes(df, label_keys), 460)
        st.caption("Mỗi nhóm là một box riêng. Vạch vàng đánh dấu ngưỡng trễ 15 phút.")
    with range_tab:
        title("INTERQUARTILE RANGE", "50% chuyến nằm trong khoảng nào?")
        plot(charts.quartile_range(df, labels), max(340, min(750, len(df)*24+80)))
        st.caption("Thanh màu nối Q1–Q3; điểm trắng là trung vị. Đây là khoảng phân bố, không phải khoảng tin cậy của ước lượng.")
    with outlier_tab:
        if {"n_out_low", "n_out_high", "n"} <= set(df):
            view = pd.DataFrame({"group": labels, "Ngoại lệ thấp": df.n_out_low/df.n.replace(0, float('nan')),
                                 "Ngoại lệ cao": df.n_out_high/df.n.replace(0, float('nan'))})
            fig = px.bar(view, x="group", y=["Ngoại lệ thấp", "Ngoại lệ cao"],
                         color_discrete_map={"Ngoại lệ thấp": charts.COLORS["purple"], "Ngoại lệ cao": charts.COLORS["cancel"]},
                         labels={"group":"Nhóm", "value":"Tỷ lệ ngoại lệ", "variable":"Loại"})
            fig.update_layout(barmode="group")
            fig.update_yaxes(tickformat=".0%")
            plot(fig, 420)
            st.caption("Ngoại lệ theo hàng rào Tukey đã tính ở M2; không dựng các điểm chuyến bay giả.")
        else:
            st.info("Bảng hiện tại chưa có số đếm ngoại lệ.")
    with st.expander("Xem phân vị và số mẫu"):
        table(df, "aero_box.csv")


def show_streaming(db):
    st.caption("KPI cửa sổ streaming · refresh mỗi 10 giây · tách biệt dữ liệu BTS lịch sử")

    @st.fragment(run_every="10s")
    def panel():
        data = list(db.stream_window_kpi.find({}, {"_id": 0}).sort("window_end", -1).limit(200))
        if not data:
            st.markdown('<div class="empty-state"><div class="signal">◌</div><h3>Đang chờ tín hiệu M4</h3><p>Khi aggregate streaming được kết nối, các cửa sổ mới sẽ tự cập nhật tại đây.</p></div>', unsafe_allow_html=True)
            st.info("Chưa kết nối dữ liệu M4. Cần tích hợp contract M4_TO_M5.md để hiển thị nguồn thực tế.")
            return
        updated = max(row["ingested_at"] for row in data)
        age = (datetime.now(timezone.utc)-updated).total_seconds()
        st.metric("Độ mới bản ghi vừa nhận", f"{max(0, age):.0f} giây")
        if age > 60:
            st.warning("Chưa nhận cập nhật trong hơn 60 giây. Kiểm tra nhịp trigger và nguồn M4.")
        st.write("Nguồn:", ", ".join(sorted({r["source"] for r in data})))
        if any(r["source"] == "simulated" for r in data):
            st.warning("Có dữ liệu mô phỏng dùng kiểm thử; không phải API live.")
        table(pd.DataFrame(data), "aero_stream_windows.csv")
    panel()


def show_status(db):
    coverage = run["manifest"]["coverage"]
    st.success("Snapshot đã được loader kiểm tra trước khi công bố")
    inventory = [{"collection": t["suggested_collection"], "documents": t["rows"],
                  "group": "KPI lịch sử" if t["group"] == "kpi" else "Thống kê box",
                  "keys": ", ".join(t["keys"])} for t in run["manifest"]["tables"]]
    fig = px.bar(pd.DataFrame(inventory).sort_values("documents"), x="documents", y="collection", orientation="h",
                 color="group", color_discrete_map={"KPI lịch sử": charts.COLORS["traffic"], "Thống kê box": charts.COLORS["purple"]},
                 labels={"documents":"Document theo manifest", "collection":"", "group":"Nhóm"})
    plot(fig, 620)
    st.code(run["_id"], language=None)
    st.write("Nguồn ingest:", run["source"])
    st.write("Phạm vi:", coverage["months"][0], "→", coverage["months"][-1])
    st.write("Export M2 (UTC):", run["manifest"].get("exported_at_utc"))
    st.write("Kiểm tra MongoDB (UTC):", run.get("verified_at"))
    st.caption("Thời điểm export/ingest không phải thời điểm thu thập BTS. Đây là dữ liệu lịch sử.")
    table(inventory, "aero_inventory.csv")
    with st.expander("Coverage chi tiết"):
        st.json(coverage)


st.markdown('<div class="eyebrow">AERO / AVIATION ANALYTICS</div>', unsafe_allow_html=True)
st.title("Air Traffic Observatory")
st.markdown('<div class="hero-copy">Khám phá nhịp bay, độ trễ và hiệu suất hàng không Hoa Kỳ qua các góc nhìn tương tác.</div>', unsafe_allow_html=True)
st.markdown('<div class="legend-strip">'+''.join(
    f'<span><i class="legend-dot" style="background:{charts.COLORS[key]}"></i>{label}</span>'
    for key, label in [("traffic","Lưu lượng"),("ontime","Đúng giờ"),("delay","Trễ chuyến"),("cancel","Hủy / trễ nặng"),("purple","Phân phối")]
)+'</div>', unsafe_allow_html=True)
try:
    client, db = database()
    client.admin.command("ping")
    run = active_run(db)
    st.subheader(page)
    if page == "Streaming":
        show_streaming(db)
    elif run is None:
        st.info("Chưa có snapshot lịch sử. Chạy scripts\\load_m2.ps1 rồi nhấn Làm mới dữ liệu.")
    else:
        coverage = run["manifest"]["coverage"]
        st.caption(f"BTS lịch sử · {coverage['months'][0]} → {coverage['months'][-1]} · {coverage['month_count']} tháng")
        if page == "Tổng quan": show_overview()
        elif page == "Thời gian & mùa vụ": show_time()
        elif page == "Hãng bay": show_ranking("carrier")
        elif page == "Sân bay xuất phát": show_ranking("origin")
        elif page == "Tuyến bay": show_routes()
        elif page == "Danh mục hãng bay & sân bay": show_directory()
        elif page == "Phân phối delay": show_boxes()
        else: show_status(db)
except PyMongoError:
    st.error("Không kết nối được MongoDB hoặc truy vấn thất bại. Kiểm tra Docker Desktop và chạy scripts\\start_m5.ps1.")
    st.caption("Nếu MongoDB vừa restart, chờ healthy rồi nhấn Làm mới dữ liệu.")
