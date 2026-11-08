from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from m5.batch_writer import load_snapshot
from m5.contracts import BOX_KEYS

pytestmark = pytest.mark.integration
APP = str(Path(__file__).resolve().parents[1]/"app.py")


def test_dashboard_empty_then_all_pages(db, snapshot_factory):
    import streamlit as st
    st.cache_resource.clear()
    st.cache_data.clear()
    app = AppTest.from_file(APP, default_timeout=30).run()
    assert not app.exception
    assert any("Chưa có snapshot" in item.value for item in app.info)
    load_snapshot(db, snapshot_factory())
    app.run()
    assert not app.exception
    assert len(app.metric) == 5
    for page in ["Thời gian & mùa vụ", "Hãng bay", "Sân bay xuất phát", "Tuyến bay", "Danh mục hãng bay & sân bay", "Phân phối delay", "Streaming", "Dữ liệu & vận hành"]:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, page
        if page == "Thời gian & mùa vụ":
            for grain in ["Tháng trong năm · toàn kỳ", "Ngày lịch · toàn kỳ", "Giờ khởi hành · toàn kỳ"]:
                app.selectbox[0].set_value(grain).run()
                assert not app.exception, grain
        elif page in ("Hãng bay", "Sân bay xuất phát"):
            app.number_input[0].set_value(1).run()
            assert not app.exception
            assert app.dataframe
        elif page == "Tuyến bay":
            app.selectbox[0].set_value(2022).run()
            assert not app.exception
            assert app.dataframe
            assert app.get("deck_gl_json_chart")
            next(w for w in app.selectbox if w.key == "map_metric").set_value("avg_arr_delay_net").run()
            assert not app.exception
            next(w for w in app.selectbox if w.key == "map_focus").set_value("JFK").run()
            assert not app.exception
            next(w for w in app.checkbox if w.key == "map_3d").set_value(True).run()
            assert not app.exception
            next(w for w in app.number_input if w.key == "map_minimum").set_value(101).run()
            assert not app.exception
            assert any("Không có tuyến đạt" in item.value for item in app.info)
        elif page == "Danh mục hãng bay & sân bay":
            assert app.dataframe
            next(w for w in app.text_input if w.key == "directory_carrier_search").set_value("no-match").run()
            assert not app.exception
            assert any("Không có hãng phù hợp" in item.value for item in app.info)
            next(w for w in app.text_input if w.key == "directory_carrier_search").set_value("american").run()
            assert next(w for w in app.selectbox if w.key == "directory_carrier").options == ["AA · American Airlines Inc."]
            next(w for w in app.radio if w.key == "directory_kind").set_value("📍 Sân bay").run()
            assert next(w for w in app.selectbox if w.key == "directory_airport").options == [
                "JFK · John F. Kennedy International Airport", "LAX · Los Angeles International Airport"]
            next(w for w in app.selectbox if w.key == "directory_airport").set_value("LAX").run()
            assert not app.exception
            next(w for w in app.selectbox if str(w.key).startswith("airport-pair-")).set_value("JFK").run()
            assert not app.exception
            assert any("Thống kê kết nối LAX ↔ JFK" in item.value for item in app.subheader)
            assert any("Chưa nạp bảng hãng theo tuyến" in item.value for item in app.info)
            next(w for w in app.radio if str(w.key).startswith("pair-direction-")).set_value("outbound").run()
            assert not app.exception
            assert any("Không có chuyến trong chiều" in item.value for item in app.info)
            next(w for w in app.text_input if w.key == "directory_airport_search").set_value("los angeles").run()
            assert not app.exception
            assert next(w for w in app.radio if w.key == "directory_kind").value == "📍 Sân bay"
            assert len(next(w for w in app.selectbox if w.key == "directory_airport").options) == 1
            next(w for w in app.text_input if w.key == "directory_airport_search").set_value("no-match").run()
            assert not app.exception
            assert any("Không có sân bay phù hợp" in item.value for item in app.info)
            next(w for w in app.selectbox if w.key == "directory_year").set_value(2026).run()
            assert not app.exception
            assert any("Chưa có dữ liệu tuyến" in item.value for item in app.info)
        elif page == "Phân phối delay":
            for grain in BOX_KEYS:
                app.selectbox[0].set_value(grain).run()
                assert not app.exception, grain
    st.cache_resource.clear()
    st.cache_data.clear()
