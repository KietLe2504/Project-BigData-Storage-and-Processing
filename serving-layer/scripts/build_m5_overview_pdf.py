"""Build the Vietnamese M5 briefing PDF and vector-derived diagram assets.

Optional documentation dependencies: doc_guide/pdf_assets/requirements.txt.
This script only reads project evidence and writes documentation artifacts.
It does not start containers, load MongoDB, or deploy Kubernetes.
"""
from __future__ import annotations

import io
import json
import math
import os
from pathlib import Path
import re
import shutil
from xml.sax.saxutils import escape

import fitz
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate, Flowable, Frame, Image, KeepTogether, PageBreak,
    PageTemplate, Paragraph, Spacer, Table, TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "doc_guide"
ASSETS = GUIDE / "pdf_assets"
PDF = GUIDE / "M5_TASK_OBJECTIVES_INPUT_OUTPUT_HA_TANG.pdf"
W, H = A4
CW = W - 88
NAVY = colors.HexColor("#10283f")
BLUE = colors.HexColor("#2563eb")
TEAL = colors.HexColor("#087f8c")
AMBER = colors.HexColor("#a86408")
INK = colors.HexColor("#20334a")
MUTED = colors.HexColor("#5d6f83")
LINE = colors.HexColor("#dce5ee")
PALE = colors.HexColor("#f1f5fa")
WHITE = colors.white


def register_fonts():
    override = os.environ.get("M5_PDF_FONT_DIR")
    candidates = [
        (Path(override), ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSansMono.ttf"))
        if override else None,
        (Path("/usr/share/fonts/truetype/dejavu"),
         ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSansMono.ttf")),
        (Path("C:/Windows/Fonts"), ("arial.ttf", "arialbd.ttf", "consola.ttf")),
    ]
    for option in candidates:
        if option and all((option[0] / name).is_file() for name in option[1]):
            for alias, name in zip(("Body", "BodyBold", "Code"), option[1]):
                pdfmetrics.registerFont(TTFont(alias, str(option[0] / name)))
            pdfmetrics.registerFontFamily("Body", normal="Body", bold="BodyBold",
                                          italic="Body", boldItalic="BodyBold")
            return
    raise RuntimeError("Set M5_PDF_FONT_DIR to a directory containing DejaVu Sans fonts")


register_fonts()
S = {
    "body": ParagraphStyle("BodyTextM5", fontName="Body", fontSize=10.1,
                           leading=15.1, textColor=INK, spaceAfter=8),
    "small": ParagraphStyle("SmallM5", fontName="Body", fontSize=8.3,
                            leading=12.0, textColor=MUTED, spaceAfter=6),
    "h1": ParagraphStyle("HeadingM5", fontName="BodyBold", fontSize=24,
                         leading=30, textColor=NAVY, spaceAfter=12),
    "h2": ParagraphStyle("SubheadingM5", fontName="BodyBold", fontSize=12.3,
                         leading=17, textColor=TEAL, spaceBefore=7, spaceAfter=7),
    "cell": ParagraphStyle("CellM5", fontName="Body", fontSize=9,
                           leading=13, textColor=INK),
    "head": ParagraphStyle("HeadM5", fontName="BodyBold", fontSize=9,
                           leading=13, textColor=WHITE),
    "code": ParagraphStyle("CodeM5", fontName="Code", fontSize=8,
                           leading=12, textColor=INK, spaceAfter=7),
}


def p(text, kind="body"):
    return Paragraph(text, S[kind])


def h(text):
    return p(text, "h2")


def bullet(text):
    return Paragraph("•  " + text, S["body"])


def grid(headers, rows, widths):
    data = [[p(x, "head") for x in headers]]
    data += [[p(str(x), "cell") for x in row] for row in rows]
    table = Table(data, colWidths=[CW * w for w in widths], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PALE, WHITE]),
        ("LINEBELOW", (0, 0), (-1, -1), .45, LINE),
    ]))
    table.spaceAfter = 11
    return table


def note(title, text, tone="teal"):
    color = AMBER if tone == "amber" else TEAL
    content = p(f'<b>{title}</b><br/>{text}')
    table = Table([[content]], colWidths=[CW])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fff5e4") if tone == "amber" else colors.HexColor("#eaf6f5")),
        ("LINEBEFORE", (0, 0), (0, -1), 3, color),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    table.spaceAfter = 12
    return table


def mono(text):
    return p(escape(text).replace("\n", "<br/>").replace(" ", "&#160;"), "code")


def label(c, text, x, y, size=10, color=INK, bold=False):
    c.setFillColor(color)
    c.setFont("BodyBold" if bold else "Body", size)
    c.drawString(x, y, text)


def text_at(c, text, x, top, width, size=10, color=INK, bold=False, center=False):
    style = ParagraphStyle("DiagramText", fontName="BodyBold" if bold else "Body",
                           fontSize=size, leading=size * 1.32, textColor=color,
                           alignment=TA_CENTER if center else TA_LEFT)
    paragraph = Paragraph(text, style)
    _, height = paragraph.wrap(width, 1000)
    paragraph.drawOn(c, x, top - height)
    return height


def box(c, x, top, w, height, title, subtitle="", fill=NAVY, accent=None, size=11):
    c.setFillColor(fill)
    c.setStrokeColor(accent or fill)
    c.setLineWidth(1)
    c.roundRect(x, top - height, w, height, 12, fill=1, stroke=1)
    color = WHITE if fill == NAVY else INK
    title_height = text_at(c, title, x + 12, top - 12, w - 24,
                          size=size, color=color, bold=True, center=True)
    used = 12 + title_height
    if subtitle:
        used += 5 + text_at(c, subtitle, x + 12, top - used - 5, w - 24,
                             size=8.5, color=colors.HexColor("#bee5ed") if fill == NAVY else MUTED,
                             center=True)
    if used > height - 5:
        raise ValueError(f"Diagram box overflow: {title}, {used} > {height}")


def arrow(c, x1, y1, x2, y2, color=MUTED, dashed=False):
    c.setStrokeColor(color)
    c.setFillColor(color)
    c.setLineWidth(1.25)
    c.setDash(4, 3) if dashed else c.setDash()
    c.line(x1, y1, x2, y2)
    c.setDash()
    angle = math.atan2(y2 - y1, x2 - x1)
    path = c.beginPath()
    path.moveTo(x2, y2)
    for delta in (-.5, .5):
        path.lineTo(x2 - 7 * math.cos(angle + delta), y2 - 7 * math.sin(angle + delta))
    path.close()
    c.drawPath(path, fill=1, stroke=0)


class Diagram(Flowable):
    def __init__(self, name, height):
        super().__init__()
        self.name, self.width, self.height = name, CW, height

    def draw(self):
        getattr(self, "draw_" + self.name)(self.canv)

    def draw_batch(self, c):
        blocks = [
            ("BTS trên HDFS", "Mỗi dòng là một chuyến bay"),
            ("M2: Spark làm sạch dữ liệu", "Tính các thống kê lịch sử"),
            ("KPI lịch sử dạng Parquet trên HDFS", "Theo tháng, năm, hãng, sân bay, tuyến"),
            ("M5: Chương trình nạp KPI", "Đọc Parquet và ghi vào MongoDB"),
            ("MongoDB", "Lưu các document có thể truy vấn"),
            ("Ứng dụng dashboard", "Truy vấn MongoDB và hiển thị biểu đồ"),
        ]
        top = self.height - 3
        for i, (title, sub) in enumerate(blocks):
            box(c, 16, top, 306, 67, title, sub, size=10.7)
            if i < len(blocks) - 1:
                arrow(c, 169, top - 68, 169, top - 88)
            top -= 91
        text_at(c, "DỮ LIỆU THÔ", 344, self.height - 20, 151, 9, TEAL, True)
        text_at(c, "Chi tiết từng chuyến, số lượng lớn.", 344, self.height - 40, 151, 9.2)
        text_at(c, "DỮ LIỆU TỔNG HỢP", 344, self.height - 198, 151, 9, TEAL, True)
        text_at(c, "M2 bàn giao KPI có schema và khóa rõ ràng cho M5.", 344, self.height - 219, 151, 9.2)
        text_at(c, "LỚP PHỤC VỤ", 344, self.height - 380, 151, 9, TEAL, True)
        text_at(c, "M5 tổ chức truy vấn và giao diện. Nhánh JSONL là cách chuyển giao khác của cùng các KPI.",
                344, self.height - 401, 151, 9.2)

    def draw_team(self, c):
        gap, bw = 24, (CW - 24) / 2
        for col, x in enumerate((0, bw + gap)):
            label(c, "LUỒNG LỊCH SỬ" if col == 0 else "LUỒNG GẦN THỜI GIAN THỰC",
                  x + 4, self.height - 13, 8.6, TEAL, True)
            nodes = [
                ("M1 — Ingestion & HDFS", "BTS CSV → raw HDFS, metadata"),
                ("M2 — Spark Batch", "Raw HDFS → clean Parquet, KPI lịch sử"),
                ("M5 — NoSQL & Dashboard", "KPI lịch sử → document truy vấn, biểu đồ"),
            ] if col == 0 else [
                ("M3 — API / Producer / Kafka", "API hoặc mô phỏng → JSON trong Kafka"),
                ("M4 — Spark Structured Streaming", "Kafka → sự kiện chuẩn hóa, KPI window"),
                ("M5 — NoSQL & Dashboard", "KPI streaming → trạng thái, độ mới trên UI"),
            ]
            top = self.height - 32
            for i, (title, sub) in enumerate(nodes):
                box(c, x, top, bw, 97, title, sub, size=10.2)
                if i < 2:
                    arrow(c, x + bw / 2, top - 99, x + bw / 2, top - 124)
                top -= 132
        text_at(c, "ĐÃ CÓ LUỒNG BATCH", 2, 34, bw, 9.5, TEAL, True, True)
        text_at(c, "CHỜ TÍCH HỢP M4 → M5", bw + gap, 34, bw, 9.5, AMBER, True, True)

    def draw_docker(self, c):
        c.setFillColor(PALE)
        c.setStrokeColor(LINE)
        c.roundRect(0, 5, CW, self.height - 10, 14, fill=1, stroke=1)
        label(c, "MÁY WINDOWS / DOCKER DESKTOP", 16, self.height - 25, 9, MUTED, True)
        box(c, 15, self.height - 46, 148, 72, "Trình duyệt", "localhost:8501", fill=WHITE, accent=LINE)
        box(c, 179, self.height - 46, 148, 72, "Compass (tùy chọn)", "localhost:27017", fill=WHITE, accent=LINE, size=10)
        box(c, 343, self.height - 46, 148, 72, "Snapshot M2", "JSONL + manifest", fill=WHITE, accent=LINE)
        box(c, 15, self.height - 166, 148, 89, "dashboard", "Streamlit + Plotly<br/>Cổng container 8501")
        box(c, 179, self.height - 166, 148, 89, "mongo", "MongoDB 8.0.16<br/>mongo:27017")
        box(c, 343, self.height - 166, 148, 89, "loader", "Validate → upsert → verify<br/>Chạy theo nhu cầu", size=10.5)
        for x in (89, 253, 417):
            arrow(c, x, self.height - 120, x, self.height - 164)
        arrow(c, 165, self.height - 208, 177, self.height - 208, TEAL)
        arrow(c, 341, self.height - 208, 329, self.height - 208, TEAL)
        box(c, 179, self.height - 303, 148, 62, "Volume MongoDB", "Giữ dữ liệu tại /data/db", fill=WHITE, accent=TEAL, size=10)
        box(c, 343, self.height - 303, 148, 62, "Logs & evidence", "Mount ra thư mục Windows", fill=WHITE, accent=TEAL, size=10)
        arrow(c, 253, self.height - 257, 253, self.height - 301)
        arrow(c, 417, self.height - 257, 417, self.height - 301)
        text_at(c, "Mạng nội bộ Compose<br/>Dashboard/loader dùng<br/>mongodb://mongo:27017",
                20, self.height - 305, 142, 8.8, MUTED)

    def draw_k8s(self, c):
        c.setFillColor(PALE)
        c.setStrokeColor(LINE)
        c.roundRect(0, 5, CW, self.height - 10, 14, fill=1, stroke=1)
        label(c, "KUBERNETES — KIẾN TRÚC ĐỀ XUẤT, CHƯA TRIỂN KHAI", 15, self.height - 24, 8.4, AMBER, True)
        box(c, 146, self.height - 43, 214, 62, "Trình duyệt / người dùng", "Local: port-forward · Dùng chung: Ingress", fill=WHITE, accent=LINE, size=10)
        box(c, 146, self.height - 137, 214, 72, "Service dashboard", "Deployment Streamlit<br/>Ban đầu 1 replica")
        box(c, 15, self.height - 250, 205, 88, "Job loader / verifier", "Nạp snapshot khi cần<br/>Chờ MongoDB sẵn sàng")
        box(c, 286, self.height - 250, 205, 88, "Service mongo", "StatefulSet MongoDB<br/>Ban đầu 1 instance")
        box(c, 286, self.height - 378, 205, 62, "PersistentVolumeClaim", "Lưu trữ bền vững cho MongoDB", fill=WHITE, accent=TEAL, size=10)
        box(c, 15, self.height - 378, 205, 62, "Snapshot / report storage", "Đưa nguồn vào · lấy evidence ra", fill=WHITE, accent=TEAL, size=10)
        arrow(c, 253, self.height - 107, 253, self.height - 135)
        arrow(c, 300, self.height - 211, 388, self.height - 248, TEAL)
        arrow(c, 222, self.height - 293, 284, self.height - 293, TEAL)
        arrow(c, 388, self.height - 340, 388, self.height - 376)
        arrow(c, 117, self.height - 376, 117, self.height - 340)
        text_at(c, "ConfigMap: tên database / cấu hình thường · Secret: URI có thông tin đăng nhập",
                15, 17, CW - 30, 7.4, MUTED, center=True)


class Cover(Flowable):
    def __init__(self):
        super().__init__()
        self.width, self.height = CW, 712

    def draw(self):
        c = self.canv
        c.setFillColor(NAVY)
        c.roundRect(0, 192, CW, 514, 18, fill=1, stroke=0)
        label(c, "AERO  /  BIG DATA STORAGE AND PROCESSING", 26, 669, 9, colors.HexColor("#72d5d3"), True)
        label(c, "M5", 24, 557, 90, WHITE, True)
        text_at(c, "NoSQL, Serving<br/>& Dashboard", 28, 515, CW - 56, 29, WHITE, True)
        text_at(c, "Từ kết quả xử lý dữ liệu<br/>đến thông tin có thể truy vấn và giải thích", 28, 407,
                CW - 56, 13, colors.HexColor("#c9dce9"))
        text_at(c, "PHẠM VI · OBJECTIVES · INPUT · OUTPUT · HẠ TẦNG", 28, 334, CW - 56, 9,
                colors.HexColor("#72d5d3"), True)
        text_at(c, "Tài liệu giải thích cho thành viên dự án<br/>Phiên bản 1.0  |  Cập nhật 07/11/2026", 28, 293,
                CW - 56, 10.5, WHITE)
        for i, (value, desc) in enumerate([("20", "bảng KPI / box"), ("74.921", "document tổng hợp"), ("51", "tháng lịch sử")]):
            x = 10 + i * 169
            label(c, value, x, 149, 25, TEAL, True)
            label(c, desc, x, 126, 9, MUTED)
        text_at(c, "Hiện trạng: batch M2 → MongoDB → dashboard đã kiểm thử.<br/>Streaming: chờ M4 tích hợp. Kubernetes: phương án triển khai đề xuất.",
                2, 88, CW - 4, 10.2, INK)
        text_at(c, "Minh họa: sơ đồ vẽ lại theo các hình người dùng đã gửi, kết hợp ảnh dashboard thực tế. Số liệu tham chiếu thuộc snapshot M2 ngày 07/11/2026.",
                2, 35, CW - 4, 8.1, MUTED)


class Document(BaseDocTemplate):
    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name == "HeadingM5":
            title = flowable.getPlainText()
            key = f"page-{self.page}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(title, key, level=0)


def decorate(c, doc):
    c.saveState()
    c.setFillColor(NAVY)
    c.rect(0, H - 27, W, 27, fill=1, stroke=0)
    label(c, "AERO  /  M5 TASK BRIEF", 44, H - 18, 7.7, WHITE, True)
    c.setFont("Body", 7.4)
    c.drawRightString(W - 44, H - 18, "TEAM REFERENCE  •  07/11/2026")
    c.setStrokeColor(LINE)
    c.line(44, 39, W - 44, 39)
    label(c, "M5 • NoSQL, Serving & Dashboard", 44, 25, 7.4, MUTED)
    c.setFont("Body", 7.4)
    c.drawRightString(W - 44, 25, f"{doc.page:02d}")
    c.restoreState()


PAGES = []


def page(title, *items):
    PAGES.append((title, [p(title, "h1"), *items]))


def build_content():
    PAGES.append(("Bìa", [Cover()]))
    page("01 / M5 cần đạt điều gì?",
         p("<b>M5 là lớp phục vụ dữ liệu (serving layer)</b>: nhận kết quả đã được M2/M4 xử lý, tổ chức trong MongoDB và cung cấp dashboard để người dùng hiểu tình hình hoạt động hàng không."),
         grid(["Objective", "Kết quả cần chứng minh"], [
             ("Dữ liệu có thể truy vấn", "KPI được lưu đúng schema, đúng khóa và đúng snapshot; truy vấn theo kỳ, hãng, sân bay hoặc tuyến có trong bảng."),
             ("Kết quả hiển thị chính xác", "Dashboard đối chiếu được với KPI nguồn; giữ đúng mẫu số, đơn vị, null và mức tổng hợp."),
             ("Nạp lại và phục hồi được", "Nạp cùng nội dung không tăng bản ghi; nạp lỗi không thay bộ đang phục vụ; dữ liệu còn sau stop/start."),
             ("Truy xuất được nguồn", "Biết snapshot, coverage, nguồn và thời điểm cập nhật; có log, report và bằng chứng demo."),
             ("Quan sát streaming", "Sau khi M4 tích hợp: window mới/cập nhật mới xuất hiện đúng, replay không nhân đôi và trạng thái cũ được nhận diện."),
         ], [.28, .72]),
         h("Các nhóm công việc của M5"),
         p("Thiết kế collection/index → xây loader batch và writer streaming → xây truy vấn/KPI hiển thị → làm dashboard → kiểm thử và vận hành → bàn giao code, dữ liệu có thể tái nạp và evidence."),
         note("Ranh giới trách nhiệm", "M2 sở hữu cleaning và thống kê batch; M3 sở hữu ingestion/Kafka; M4 sở hữu xử lý streaming và checkpoint. M5 kiểm tra, lưu, truy vấn và hiển thị kết quả; không mặc định ghép BTS lịch sử với sự kiện API theo mã chuyến."),
         p("Căn cứ: tài liệu phân công dự án, trang 6–8; hợp đồng M2 → M5 và contract M4 → M5 trong repo. [N1–N3]", "small"))

    page("02 / Từ dữ liệu thô đến dashboard",
         p("Sơ đồ batch dưới đây giữ nội dung chuỗi bạn đã gửi: dữ liệu từng chuyến được M2 tổng hợp, sau đó M5 đưa vào MongoDB và phục vụ biểu đồ."),
         Diagram("batch", 539),
         p("Hình 1. Vẽ lại theo hai ảnh sơ đồ batch trong hội thoại, ghép thành một luồng đầy đủ; không phải ảnh gốc. Nhánh đọc Parquet của M5 đã có adapter; nhánh bàn giao JSONL dùng cùng quy tắc ghi và đối chiếu.", "small"))

    page("03 / M5 phối hợp với ai?",
         p("M5 nhận hai nhánh kết quả. Cả nhóm phải thống nhất schema, khóa, đơn vị đo và cách cập nhật trước khi nối chương trình."),
         Diagram("team", 426),
         p("Hình 2. Vẽ lại theo ảnh “Luồng bàn giao dữ liệu giữa các thành viên” bạn gửi; bố cục đổi thành hai nhánh song song để dễ so sánh.", "small"),
         grid(["Bên bàn giao", "Thông tin cần cung cấp cho M5"], [
             ("M2", "KPI/box, schema, khóa nghiệp vụ, coverage, đơn vị và đường dẫn/bộ export nhất quán."),
             ("M4", "Aggregate window, source, event time, update semantics, revision, nhịp cập nhật và ví dụ hợp lệ."),
             ("M5 → nhóm trưởng", "Dashboard, collections/indexes, truy vấn, test/report, demo và giới hạn đã biết."),
         ], [.25, .75]))

    page("04 / Input lịch sử từ M2",
         h("Đầu vào là KPI tổng hợp, không phải toàn bộ raw"),
         p("M5 đọc <b>13 bảng KPI + 7 bảng box</b>. Có hai đường nhận: JSONL + manifest do M2 export, hoặc adapter Spark đọc trực tiếp aggregate Parquet trên HDFS. Cleaned Parquet từng chuyến không phải bộ KPI để nạp vào các collections này."),
         grid(["Thành phần", "Ý nghĩa"], [
             ("manifest.json", "Danh mục bảng, schema Spark, khóa, số dòng, coverage và quy ước dữ liệu."),
             ("20 JSONL", "Nguồn nạp giữ kiểu số, boolean và null; mỗi dòng là một nhóm thống kê."),
             ("20 CSV đi kèm", "Thuận tiện đọc/đối chiếu; không phải nguồn chính của loader."),
             ("Aggregate Parquet", "/aero/analytics/eda/kpi và /aero/analytics/eda/box trên HDFS."),
         ], [.29, .71]),
         h("Mức dữ liệu (grain) quyết định được lọc theo gì"),
         grid(["Ví dụ collection", "Một document đại diện cho"], [
             ("kpi_month_overall", "Một năm + một tháng"),
             ("kpi_year_carrier", "Một năm + một hãng"),
             ("kpi_year_route", "Một năm + sân bay đi + sân bay đến"),
             ("box_year_carrier", "Một năm + hãng + var (arr/dep) + population (all/late)"),
         ], [.43, .57]),
         note("Mốc dữ liệu mẫu", "Snapshot 20261107T042703414867Z: 51 tháng (2022-01 → 2026-03), 64.249 dòng KPI + 10.672 dòng box = 74.921 document; tổng flights bảng tháng là 29.328.846. Đây là số của bộ mẫu, không phải định mức cho mọi lần nạp."))

    page("05 / Input streaming từ M4",
         note("Trạng thái: hợp đồng đề xuất, chờ tích hợp", "Đã có writer M5 và tests; chưa có bằng chứng chạy toàn luồng M3 → Kafka → M4 → M5. Phải đối chiếu output M4 thật hoặc sửa adapter trước khi nghiệm thu.", "amber"),
         p("M5 nhận <b>aggregate đầy đủ cho một cửa sổ thời gian</b>, thay vì tự cộng mỗi thông điệp vào bộ đếm. M4 chịu trách nhiệm event time, watermark, checkpoint và cung cấp revision bền vững qua restart."),
         grid(["Trường", "Ý nghĩa"], [
             ("pipeline_id / source", "Định danh pipeline; nguồn thực tế aviationstack hoặc simulated."),
             ("window_start / window_end", "Khoảng thời gian có timezone, chuẩn hóa UTC; start trước end."),
             ("dimensions", "Các chiều thật có: carrier, origin, dest; object rỗng cho overall."),
             ("metrics", "Bắt buộc flights; có thể có arr_n, on_time, delayed15, cancelled, sum_arr_delay… theo contract."),
             ("revision", "Phiên bản tăng cho cùng khóa logic; không được quay về thấp hơn sau restart."),
         ], [.32, .68]),
         h("Quy tắc tiếp nhận và độ mới"),
         bullet("Cùng khóa + cùng revision + cùng nội dung: bỏ qua replay. Revision mới thay toàn bộ aggregate; revision cũ không ghi đè."),
         bullet("Cùng revision nhưng nội dung khác: báo lỗi xung đột. Replay không được làm thời gian nhận dữ liệu trông mới hơn."),
         bullet("UI hiện cấu hình refresh 10 giây, stale sau 60 giây; cần điều chỉnh theo trigger M4. Đây là cấu hình dự kiến, không phải SLA đã đo end-to-end."),
         p("Khóa logic gồm source + pipeline_id + window_start + window_end + toàn bộ dimensions. Tài liệu chi tiết: contracts/M4_TO_M5.md. Không tuyên bố exactly-once toàn hệ thống chỉ từ tests của writer. [N3]", "small"))

    page("06 / M5 xử lý dữ liệu ra sao?",
         p("Luồng batch được thiết kế để dashboard chỉ đọc một bộ kết quả đã được nạp và kiểm tra hoàn chỉnh."),
         grid(["Bước", "Công việc và ý nghĩa"], [
             ("1. Inspect", "Đọc manifest và toàn bộ JSONL; kiểm tra đúng 20 bảng, schema, kiểu dữ liệu, khóa trùng, coverage và tổng flights."),
             ("2. Fingerprint", "Tính định danh từ schema, giá trị và coverage. Cùng nội dung được nhận diện dù tên thư mục khác."),
             ("3. Lock & index", "Một loader giữ lease để điều phối lần nạp; tạo unique index theo snapshot_id + khóa nghiệp vụ."),
             ("4. Bulk upsert", "Ghi theo lô 1.000 thao tác: có khóa thì thay document, chưa có thì thêm. Snapshot đã công bố không sửa tại chỗ."),
             ("5. Verify", "Kiểm tra nguồn vẫn nhất quán và đọc lại MongoDB, so digest toàn bộ giá trị với nguồn đã inspect."),
             ("6. Publish", "Sau khi đạt kiểm tra mới đổi con trỏ active; dashboard truy vấn theo snapshot_id đó."),
         ], [.26, .74]),
         note("Nạp lại và lỗi giữa chừng", "Bộ đã có: ALREADY LOADED và kiểm tra lại giá trị. Lần lỗi: giữ bộ active cũ, có thể retry bộ chưa hoàn tất. Nạp lại một snapshot cũ đã công bố không tự chuyển dashboard lùi về quá khứ."),
         h("Đường đi trong code"),
         mono("scripts/load_m2.ps1\n  → m5/load_batch.py → m5/contracts.py\n  → m5/batch_writer.py → MongoDB\napp.py → m5/queries.py → m5/metrics.py → m5/charts.py"),
         p("Adapter m5/load_parquet.py đọc 20 bảng aggregate HDFS, stage JSONL tạm và gọi cùng writer. Không yêu cầu MongoDB Spark Connector JAR trong phương án hiện tại.", "small"))

    page("07 / MongoDB lưu những gì?",
         p("<b>Document</b> là bản ghi dạng đối tượng có trường và giá trị; <b>collection</b> là tập document cùng mục đích. M5 chọn cấu trúc gần với output M2 để kiểm tra và truy vết thuận tiện. HDFS tiếp tục giữ dữ liệu phân tích; MongoDB giữ bản tổng hợp phục vụ ứng dụng."),
         grid(["Nhóm", "Nội dung"], [
             ("13 kpi_*", "Số chuyến, đúng giờ, trễ, hủy và các count/sum phục vụ gộp KPI."),
             ("7 box_*", "Q1, median, Q3, whiskers và các thống kê phân phối M2 đã tính."),
             ("batch_runs", "Manifest, digests, nguồn và trạng thái từng lần/bộ nạp."),
             ("serving_state", "Con trỏ snapshot đang được dashboard dùng."),
             ("serving_locks", "Lease điều phối loader; không phải dữ liệu KPI."),
             ("stream_window_kpi", "Aggregate window khi đã tích hợp M4; tách khỏi số liệu lịch sử."),
         ], [.32, .68]),
         h("Khóa và index có tác dụng gì?"),
         p("Ví dụ KPI tháng có khóa <b>snapshot_id + year + month</b>. Unique index ngăn hai document cùng tổ hợp đó. Với box theo hãng, khóa còn gồm carrier, var và population để không gộp nhầm quần thể."),
         p("Index phụ theo carrier/origin/dest hỗ trợ một số mẫu lọc. Hiệu năng phải đo bằng truy vấn thực và explain; không mặc định có index là mọi truy vấn đều nhanh."),
         note("Đọc đúng snapshot", "74.921 là document dữ liệu của một bộ mẫu. Tổng toàn database có thể lớn hơn vì metadata hoặc nhiều snapshot. M5 không tự xóa các snapshot cũ; cần chính sách lưu giữ khi vận hành lâu dài."))

    page("08 / Output nhìn thấy được",
         p("Dashboard truy vấn MongoDB qua lớp Python; không đọc trực tiếp CSV/JSONL để vẽ các biểu đồ lịch sử. Người dùng chọn phạm vi rồi xem KPI, xu hướng và phân phối."),
         Image(str(ASSETS / "dashboard_thuc_te.png"), width=420, height=498.75),
         p("Hình 3. Ảnh dashboard thực tế của project, bộ BTS 2022-01 → 2026-03. Toàn kỳ có 29.328.846 chuyến; các tỷ lệ dùng đúng quần thể được chú thích trên giao diện. Ảnh có sẵn trong evidence kiểm thử 07/11/2026.", "small"),
         p("Màu chỉ số: xanh dương = lưu lượng; xanh ngọc = đúng giờ; vàng = trễ; đỏ = hủy/trễ nặng. Biểu đồ theo nhóm có chú giải riêng.", "small"))

    page("09 / Output phải bàn giao",
         grid(["Output", "Người nhận dùng để làm gì?"], [
             ("MongoDB collections/indexes", "Truy vấn KPI theo khóa và bộ dữ liệu đã kiểm tra."),
             ("Dashboard 8 trang", "Tổng quan, thời gian/mùa vụ, hãng, sân bay xuất phát, tuyến, phân phối, streaming, dữ liệu/vận hành."),
             ("Code và cấu hình", "Dựng lại môi trường, nạp bộ mới và bảo trì giao diện."),
             ("Log + load/verify reports", "Xác nhận số document, coverage, snapshot và đối chiếu giá trị/index."),
             ("Ảnh, CSV, ZIP evidence", "Minh họa demo và lưu bằng chứng đúng lần chạy."),
             ("Hướng dẫn + contract", "Thành viên khác biết input cần nhận, cách chạy và giới hạn tích hợp."),
         ], [.32, .68]),
         h("Các câu hỏi dashboard trả lời"),
         p("Bao nhiêu chuyến và bao nhiêu bị hủy? Tỷ lệ đúng giờ biến động thế nào? Hãng/sân bay/tuyến nào có lượng chuyến hoặc delay cao? Phân phối trễ có khác nhau giữa nhóm đến/đi hoặc all/late?"),
         h("Quy tắc trình bày số liệu"),
         bullet("Tỷ lệ nguồn 0–1, nhân 100 khi hiển thị %. Gộp từ tổng count/sum, không lấy trung bình tỷ lệ tháng."),
         bullet("Delay theo phút, có thể âm khi đến sớm; null không tự chuyển thành 0. Không lấy trung bình phân vị để ghép box."),
         bullet("2026 chỉ có quý 1. Animation theo năm là lịch sử, không phải live; Sankey chỉ biểu diễn top tuyến đang chọn."),
         note("Bộ bàn giao tái lập", "Gửi code + snapshot M2 + ZIP evidence. ZIP evidence không chứa MongoDB volume hoặc toàn bộ input; clone repo chưa có các exports đang được Git bỏ qua."))

    page("10 / Hạ tầng: từng thành phần",
         p("<b>Hạ tầng</b> là môi trường giúp code chạy, các thành phần tìm thấy nhau và dữ liệu được giữ lại. Cấu hình local hiện tại được mô tả trong compose.yml và compose.hdfs.yml."),
         grid(["Thành phần", "Vai trò trong M5", "Bắt buộc khi nào?"], [
             ("Docker Desktop", "Chạy container Linux trên máy phát triển Windows.", "Luồng local đang dùng"),
             ("Docker image", "Gói code, Python và dependencies; tạo môi trường chạy thống nhất.", "App và loader"),
             ("Docker Compose", "Khai báo services, mạng, volumes và health checks trong YAML.", "Điều phối local"),
             ("MongoDB server", "Lưu document, indexes, metadata và active snapshot.", "Phục vụ dữ liệu"),
             ("PyMongo", "Thư viện Python kết nối, ghi và đọc MongoDB.", "Trong loader/dashboard"),
             ("Streamlit / Plotly", "Ứng dụng web Python và biểu đồ tương tác; trình duyệt là client.", "Hiển thị dashboard"),
             ("Volume / bind mount", "Volume giữ database; bind mount đưa input/report giữa Windows và container.", "Giữ và trao đổi dữ liệu"),
             ("Spark / HDFS", "Đọc trực tiếp aggregate Parquet của M2.", "Chỉ nhánh nạp HDFS"),
             ("MongoDB Compass", "Giao diện xem document/index, kết nối server đã chạy.", "Tùy chọn"),
         ], [.25, .47, .28]),
         p("Phiên bản hiện tại: MongoDB 8.0.16; Python 3.12.12; PyMongo 4.10.1; Streamlit 1.50.0; Plotly 6.3.1. Adapter HDFS dùng Spark 3.5.3. Xem Dockerfiles và requirements để tái lập. [N4]", "small"),
         p("Compose quản lý nhiều container từ một cấu hình; Streamlit gồm backend Python và frontend trình duyệt. [T1, T5]", "small"))

    page("11 / Triển khai Docker hiện tại",
         Diagram("docker", 387),
         p("Hình 4. Sơ đồ từ cấu hình Compose hiện tại. Mũi tên biểu diễn kết nối/đường dữ liệu; loader được chạy khi có lệnh, không phải dịch vụ luôn bật.", "small"),
         h("Mạng, cổng và lưu trữ"),
         p("Windows dùng <b>localhost:8501</b> để mở dashboard và <b>localhost:27017</b> để mở Compass. Bên trong mạng serving, dashboard/loader dùng <b>mongodb://mongo:27017</b>. Tên mongo là tên service trong mạng container."),
         p("Volume <b>aero-serving_m5_mongo_data</b> mount vào /data/db giữ database khi stop/start. Input được mount read-only; logs/evidence được mount ra thư mục serving-layer trên Windows."),
         note("Phạm vi local", "MongoDB và dashboard hiện publish trên 127.0.0.1, dành cho máy chạy M5. Gửi link localhost cho thành viên khác không làm họ truy cập được máy bạn. Dùng chung qua mạng cần phương án host, truy cập và xác thực riêng."),
         p("Health checks xác nhận tiến trình sẵn sàng; verify mới xác nhận bộ dữ liệu. MongoDB hiện chạy một instance, chưa phải cụm dự phòng.", "small"))

    page("12 / Kubernetes sẽ gồm những gì?",
         p("Kubernetes quản lý các container theo cấu hình mong muốn. Vẫn dùng image build từ Dockerfile; phần điều phối chuyển từ Compose sang các tài nguyên Kubernetes. Đây là kiến trúc đề xuất cho M5, chưa phải trạng thái đã triển khai. [T2]"),
         Diagram("k8s", 462),
         p("Hình 5. Kiến trúc Kubernetes đề xuất cho riêng serving layer. Chưa thể suy ra hạ tầng cloud hoặc khả năng dự phòng nhiều máy chỉ từ sơ đồ này.", "small"),
         note("Vai trò lưu trữ", "PVC là yêu cầu cấp lưu trữ cho MongoDB; storage backend và chính sách giữ/xóa dữ liệu phải được cấu hình trên cluster. Volume Docker hiện tại không tự biến thành PVC. Một instance MongoDB cùng PVC vẫn chưa tạo replica set dự phòng. [T3]"))

    page("13 / Chuyển Compose → Kubernetes",
         grid(["Thành phần", "Tài nguyên / việc cần bổ sung"], [
             ("Dashboard", "Deployment quản lý Pod ứng dụng, Service tạo điểm truy cập; bắt đầu một replica."),
             ("MongoDB", "StatefulSet + Service + PVC; chọn StorageClass hoặc storage phù hợp môi trường."),
             ("Loader / verifier", "Job chạy tới khi hoàn tất. Có bước chờ MongoDB, retry có kiểm soát và lấy report ra ngoài."),
             ("Cấu hình", "ConfigMap cho cấu hình thường; Secret cho URI có credentials khi bật xác thực."),
             ("Images", "Đẩy image có version vào registry hoặc nạp image vào cluster local; node phải truy cập được."),
             ("Truy cập và sức khỏe", "Local dùng port-forward; triển khai dùng chung cần cơ chế truy cập phù hợp, probes và requests/limits."),
         ], [.28, .72]),
         h("Lộ trình chuyển phù hợp project"),
         p("<b>1.</b> Giữ Compose đang hoạt động và snapshot nguồn. <b>2.</b> Dựng riêng M5 trên Kubernetes với database/volume mới. <b>3.</b> Đưa snapshot JSONL vào và chạy load/verify. <b>4.</b> So dashboard, nạp lại, thử tạo lại Pod rồi kiểm tra dữ liệu. <b>5.</b> Sau đó mới nối HDFS trực tiếp và M4."),
         note("Điểm cần xử lý riêng", "Mạng batch-layer_default của Compose không tự nối với Kubernetes; HDFS cần truy cập được cả NameNode và DataNode. Nếu scale Streamlit nhiều replica, cần session affinity phù hợp. Chuyển hạ tầng không tự hoàn thành tích hợp streaming.", "amber"),
         p("Job phù hợp chương trình chạy một lần; tài nguyên Secret cần chính sách truy cập phù hợp. Streamlit có hướng dẫn Kubernetes và lưu ý về nhiều replicas. [T4–T6]", "small"))

    page("14 / Tiêu chí nghiệm thu và trạng thái",
         grid(["Tiêu chí", "Bằng chứng cần có", "Hiện trạng"], [
             ("Batch ingest", "Đủ 20 bảng, schema/khóa/coverage đúng; load và verify PASS.", "Đã kiểm thử"),
             ("Đối chiếu dữ liệu", "Digest nguồn/MongoDB và unique indexes; bộ mẫu 74.921 document.", "Đã kiểm thử"),
             ("Nạp lại / phục hồi", "Không tăng document khi replay; lỗi không thay active; stop/start giữ dữ liệu.", "Đã kiểm thử"),
             ("Dashboard", "Truy vấn dữ liệu M2 thật, bộ lọc hợp lệ, KPI đúng, biểu đồ render được.", "Đã kiểm thử"),
             ("Nhánh HDFS", "Đọc 20 aggregate Parquet, fingerprint khớp JSONL cùng nội dung.", "Đã kiểm thử"),
             ("Streaming", "M3/M4 thật tạo/update window, replay/late update/restart và độ mới trên UI.", "Chờ tích hợp"),
             ("Kubernetes / cloud", "Manifests, môi trường chạy thật, persistence và evidence triển khai.", "Chưa triển khai"),
         ], [.24, .53, .23]),
         h("Evidence hiện có khác mục tiêu tương lai"),
         p("Biên bản 07/11/2026 ghi 21 tests passed và một cảnh báo dependency; đã kiểm tra UI với MongoDB phục vụ thật, nhánh JSONL/HDFS và stop/start. Đây là bằng chứng local cho bản code đã kiểm thử, không phải bảo đảm mọi môi trường mới hoặc toàn luồng streaming đều đạt."),
         note("Giới hạn của verify", "Đối chiếu giá trị phục vụ với nguồn được ghi nhận lúc ingest. Muốn kết luận KPI đúng từ raw cần kết hợp kiểm chứng cleaning/công thức ở M2. Với streaming phải đo source/sink và delivery semantics trong điều kiện tích hợp thật."),
         p("Tham chiếu: doc_guide/KET_QUA_KIEM_THU_M5.md và contract M4. [N3, N5]", "small"))

    page("15 / Vận hành và bàn giao cho team",
         h("Thứ tự thao tác trên máy Windows"),
         p("Nhận code và snapshot M2 → mở Docker Desktop → kiểm tra đường dẫn → start MongoDB/dashboard → CheckOnly → load → verify → mở dashboard → lưu ảnh/report → đóng gói evidence. Hướng dẫn thao tác chi tiết nằm trong repo, không yêu cầu mở notebook."),
         grid(["Script trong serving-layer/scripts", "Vai trò"], [
             ("start_m5.ps1", "Build/start và chờ MongoDB, dashboard healthy."),
             ("load_m2.ps1 -SnapshotPath ...", "Kiểm tra/nạp snapshot chỉ định; -CheckOnly chưa ghi database."),
             ("verify_m5.ps1", "Đối chiếu active snapshot và indexes."),
             ("test_m5.ps1", "Chạy unit/integration tests trong container, dùng database test riêng."),
             ("collect_evidence.ps1", "Verify lại và đóng gói logs, reports, ảnh có sẵn và tài liệu."),
             ("stop_m5.ps1", "Dừng serving, giữ volume MongoDB."),
         ], [.53, .47]),
         h("Output nằm ở đâu?"),
         p("<b>Database:</b> aero_m5 trong MongoDB.<br/><b>Dashboard:</b> http://localhost:8501.<br/><b>Logs:</b> serving-layer/logs/.<br/><b>Reports:</b> serving-layer/evidence/load_report.json, verify_report.json.<br/><b>ZIP:</b> serving-layer/evidence/M5_HANDOFF_&lt;ngày_giờ&gt;.zip."),
         note("Bàn giao đủ để người khác chạy lại", "Code đúng phiên bản + snapshot M2 có manifest và 20 JSONL + ZIP evidence + hướng dẫn. Các file export/log/evidence không tự có qua Git. Các báo cáo/log tên cố định có thể bị ghi lại khi chạy lần sau; lưu bộ bàn giao của lần cần giữ."),
         p("Không dùng down -v để dừng thông thường vì có thể xóa volume. Các lệnh Python/JavaScript chỉ chạy trong môi trường tương ứng; khối PowerShell trong hướng dẫn mới dán vào dấu nhắc PS.", "small"))

    page("16 / Đọc thêm và thuật ngữ",
         h("Tài liệu nội bộ — căn cứ dự án"),
         p("<b>[N1]</b> Big_Data_Project_Plan_5_Members.pdf, trang 6–8: phạm vi M4/M5 và trách nhiệm tích hợp.<br/><b>[N2]</b> batch-layer/doc_guide/HUONG_DAN_BAN_GIAO_M2_M5.md và manifest của snapshot 20261107T042703414867Z.<br/><b>[N3]</b> serving-layer/contracts/M4_TO_M5.md: hợp đồng streaming đề xuất.<br/><b>[N4]</b> serving-layer/compose.yml, compose.hdfs.yml, Dockerfiles và requirements.txt.<br/><b>[N5]</b> serving-layer/doc_guide/KET_QUA_KIEM_THU_M5.md: kết quả kiểm thử local."),
         h("Tài liệu chính thức — hạ tầng"),
         p('<b>[T1]</b> <link href="https://docs.docker.com/compose/" color="#2563eb">Docker Compose — services, mạng và volumes</link><br/>'
           '<b>[T2]</b> <link href="https://kubernetes.io/docs/concepts/workloads/" color="#2563eb">Kubernetes Workloads — Deployment, StatefulSet</link><br/>'
           '<b>[T3]</b> <link href="https://kubernetes.io/docs/concepts/storage/persistent-volumes/" color="#2563eb">Kubernetes Persistent Volumes / Claims</link><br/>'
           '<b>[T4]</b> <link href="https://kubernetes.io/docs/concepts/workloads/controllers/job/" color="#2563eb">Kubernetes Jobs</link> · '
           '<link href="https://kubernetes.io/docs/concepts/configuration/secret/" color="#2563eb">Secrets</link><br/>'
           '<b>[T5]</b> <link href="https://docs.streamlit.io/develop/concepts/architecture/architecture" color="#2563eb">Streamlit — client/server và session affinity</link><br/>'
           '<b>[T6]</b> <link href="https://docs.streamlit.io/deploy/tutorials/kubernetes" color="#2563eb">Streamlit — triển khai với Kubernetes</link>'),
         h("Các từ cần nhớ"),
         grid(["Thuật ngữ", "Diễn giải ngắn"], [
             ("Serving / KPI / grain", "Phục vụ dữ liệu / chỉ số nghiệp vụ / một dòng đại diện cho nhóm nào."),
             ("Snapshot / upsert", "Một bộ dữ liệu nhất quán / cập nhật nếu có khóa, thêm nếu chưa có."),
             ("Image / container / Pod", "Gói môi trường / tiến trình chạy từ image / đơn vị chạy container trên Kubernetes."),
             ("Service / PVC", "Điểm kết nối trong cluster / yêu cầu cấp lưu trữ bền vững."),
             ("Freshness / stale", "Độ mới / dữ liệu đã quá ngưỡng thời gian cập nhật mong đợi."),
         ], [.34, .66]),
         p("Sơ đồ 1–2 là bản vẽ lại nội dung ảnh trong hội thoại; ảnh gốc không có trong workspace. Sơ đồ 4 là cấu hình hiện tại; sơ đồ 5 là đề xuất. Tài liệu mang tính giải thích và bàn giao, không xác nhận các hạng mục chưa được triển khai.", "small"))


def export_diagram_assets():
    for name, height in [("batch", 539), ("team", 426), ("docker", 387), ("k8s", 462)]:
        stream = io.BytesIO()
        c = canvas.Canvas(stream, pagesize=(CW + 24, height + 24))
        c.translate(12, 12)
        Diagram(name, height).drawOn(c, 0, 0)
        c.save()
        doc = fitz.open(stream=stream.getvalue(), filetype="pdf")
        doc[0].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False).save(ASSETS / f"so_do_{name}.png")
        doc.close()


def validate_pdf():
    doc = fitz.open(PDF)
    if len(doc) != len(PAGES):
        raise AssertionError(f"Unexpected pagination: {len(doc)} pages, expected {len(PAGES)}")
    texts = [page.get_text() for page in doc]
    for i, ((title, _), text) in enumerate(zip(PAGES, texts), 1):
        if i > 1 and title not in re.sub(r"\s+", " ", text):
            raise AssertionError(f"Wrong section on page {i}: {title}")
        if "\ufffd" in text or "\u25a0" in text:
            raise AssertionError(f"Missing-glyph placeholder on page {i}")
        for block in doc[i - 1].get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    x0, y0, x1, y1 = span["bbox"]
                    if x0 < 0 or y0 < 0 or x1 > W + .5 or y1 > H + .5:
                        raise AssertionError(f"Text outside page {i}: {span['text']}")
    all_text = "\n".join(texts)
    for required in ["74.921", "29.328.846", "Kubernetes", "MongoDB", "Chờ tích hợp", "OBJECTIVES"]:
        if required not in all_text:
            raise AssertionError(f"Missing required content: {required}")
    if not doc.get_toc() or len(doc.get_toc()) != len(PAGES) - 1:
        raise AssertionError("Missing section bookmarks")
    preview = ROOT / "logs" / "pdf_preview"
    preview.mkdir(exist_ok=True)
    for i in range(len(doc)):
        doc[i].get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False).save(preview / f"page_{i + 1:02d}.png")
    reference_manifest = ROOT.parent / "batch-layer/spark_jobs/export/m2_to_m5/20261107T042703414867Z/manifest.json"
    reference_checked = False
    if reference_manifest.is_file():
        manifest = json.loads(reference_manifest.read_text(encoding="utf-8"))
        counts = {group: sum(t["rows"] for t in manifest["tables"] if t["group"] == group)
                  for group in ("kpi", "box")}
        assert counts == {"kpi": 64249, "box": 10672}
        assert len(manifest["tables"]) == 20
        assert manifest["coverage"]["month_count"] == 51
        assert manifest["coverage"]["total_flights"] == 29328846
        reference_checked = True
    report = {"result": "PASS", "pages": len(doc), "bookmarks": len(doc.get_toc()),
              "pdf_bytes": PDF.stat().st_size, "diagram_assets": 4,
              "image_provenance": "Diagrams 1–2 redrawn from conversation images; original image files unavailable. Dashboard screenshot copied from actual project evidence.",
              "checks": ["expected pagination", "all section headings", "Vietnamese text extraction",
                         "no replacement glyphs", "text page boundaries", "bookmarks"],
              "reference_manifest_counts_checked": reference_checked,
              "scope": "Document build only; no containers or database changed"}
    (ASSETS / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    doc.close()
    print(json.dumps(report, ensure_ascii=False))


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    screenshot = ASSETS / "dashboard_thuc_te.png"
    if not screenshot.exists():
        source = ROOT / "evidence" / "dashboard_visual_overview.png"
        if not source.is_file():
            raise FileNotFoundError("Missing actual dashboard screenshot: " + str(source))
        shutil.copy2(source, screenshot)
    build_content()
    # Each section has an intentional page. Catch overflows before building.
    for title, items in PAGES:
        height = 0
        for item in items:
            _, ih = item.wrap(CW, 1000)
            height += ih + item.getSpaceBefore() + item.getSpaceAfter()
        if height > 736:
            raise AssertionError(f"Section too tall: {title}, {height:.1f}pt")
    doc = Document(str(PDF), pagesize=A4, leftMargin=44, rightMargin=44,
                   topMargin=48, bottomMargin=48,
                   title="M5 — Task, Objectives, Input, Output và Hạ tầng triển khai",
                   author="AERO Project Team", subject="Vietnamese M5 serving-layer team briefing")
    frame = Frame(44, 49, CW, 740, leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=decorate)])
    story = []
    for i, (_, items) in enumerate(PAGES):
        if i:
            story.append(PageBreak())
        story.extend(items)
    doc.build(story)
    export_diagram_assets()
    validate_pdf()


if __name__ == "__main__":
    main()
