"""Render the M5 learning document as a single-column Times New Roman paper.

Reads doc_guide/TAI_LIEU_HOC_TAP_M5_THEO_TASK.md. No operational commands run.
Optional authoring dependencies: doc_guide/pdf_assets/requirements.txt.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
from xml.sax.saxutils import escape

import fitz
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Flowable, Frame, Image, KeepTogether,
    PageTemplate, Paragraph, Spacer, XPreformatted,
)

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "doc_guide"
SOURCE = GUIDE / "TAI_LIEU_HOC_TAP_M5_THEO_TASK.md"
PDF = GUIDE / "M5_TAI_LIEU_HOC_TAP_THEO_TASK.pdf"
OUT = ROOT / "logs" / "m5_learning_paper_pdf"
W, H = A4
LEFT, RIGHT, TOP, BOTTOM = 30 * mm, 25 * mm, 25 * mm, 25 * mm
WIDTH, HEIGHT = W - LEFT - RIGHT, H - TOP - BOTTOM
BLACK = colors.black
STORY = []
HEADINGS = []
COMMANDS = []


def register_fonts():
    candidates = [Path(os.environ["M5_PAPER_FONT_DIR"])] if os.environ.get("M5_PAPER_FONT_DIR") else []
    candidates += [Path("/mnt/c/Windows/Fonts"), Path("C:/Windows/Fonts")]
    names = ["times.ttf", "timesbd.ttf", "timesi.ttf", "timesbi.ttf"]
    for folder in candidates:
        if all((folder / name).is_file() for name in names):
            for alias, name in zip(("TNR", "TNR-Bold", "TNR-Italic", "TNR-BoldItalic"), names):
                pdfmetrics.registerFont(TTFont(alias, str(folder / name)))
            pdfmetrics.registerFontFamily("TNR", normal="TNR", bold="TNR-Bold",
                                          italic="TNR-Italic", boldItalic="TNR-BoldItalic")
            mono = folder / "consola.ttf"
            if mono.exists():
                pdfmetrics.registerFont(TTFont("PaperCode", str(mono)))
            else:
                pdfmetrics.registerFont(TTFont("PaperCode", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"))
            return
    raise RuntimeError("Set M5_PAPER_FONT_DIR to a directory containing the four Times New Roman TTF files")


register_fonts()
STYLES = {
    "title": ParagraphStyle("PaperTitle", fontName="TNR-Bold", fontSize=16, leading=21,
                            alignment=TA_CENTER, spaceAfter=12, keepWithNext=True),
    "meta": ParagraphStyle("PaperMeta", fontName="TNR-Italic", fontSize=11, leading=15,
                           alignment=TA_CENTER, spaceAfter=5, keepWithNext=True),
    "h1": ParagraphStyle("PaperH1", fontName="TNR-Bold", fontSize=14, leading=18,
                         alignment=TA_LEFT, spaceBefore=14, spaceAfter=8, keepWithNext=True),
    "h2": ParagraphStyle("PaperH2", fontName="TNR-Bold", fontSize=12, leading=18,
                         alignment=TA_LEFT, spaceBefore=9, spaceAfter=5, keepWithNext=True),
    "body": ParagraphStyle("PaperBody", fontName="TNR", fontSize=12, leading=18,
                           alignment=TA_JUSTIFY, firstLineIndent=18, spaceAfter=6,
                           allowWidows=0, allowOrphans=0, splitLongWords=True),
    "abstract": ParagraphStyle("PaperAbstract", fontName="TNR", fontSize=11, leading=16.5,
                               alignment=TA_JUSTIFY, firstLineIndent=0, spaceAfter=8,
                               allowWidows=0, allowOrphans=0),
    "caption": ParagraphStyle("PaperCaption", fontName="TNR-Italic", fontSize=11, leading=15,
                              alignment=TA_CENTER, spaceBefore=5, spaceAfter=10),
    "ref": ParagraphStyle("PaperReference", fontName="TNR", fontSize=11, leading=15,
                          alignment=TA_LEFT, firstLineIndent=-17, leftIndent=17,
                          spaceAfter=6, allowWidows=0, allowOrphans=0),
    "code": ParagraphStyle("PaperCodeBlock", fontName="PaperCode", fontSize=9, leading=12,
                           alignment=TA_LEFT, leftIndent=8, spaceBefore=5, spaceAfter=9),
}


def inline(text):
    text = escape(text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^\s)]+)\)",
                  r'<link href="\2" color="black"><u>\1</u></link>', text)
    text = re.sub(r"`([^`]+)`", r"<i>\1</i>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", text)
    return text


def paragraph(text, kind="body"):
    return Paragraph(inline(text), STYLES[kind])


def arrow(c, x, top, bottom):
    c.setStrokeColor(BLACK)
    c.setFillColor(BLACK)
    c.setLineWidth(.65)
    c.line(x, top, x, bottom)
    path = c.beginPath()
    path.moveTo(x, bottom)
    path.lineTo(x - 3, bottom + 5)
    path.lineTo(x + 3, bottom + 5)
    path.close()
    c.drawPath(path, fill=1, stroke=0)


class PaperDiagram(Flowable):
    def __init__(self, kind):
        super().__init__()
        self.kind, self.width = kind, WIDTH
        self.height = 333 if kind == "batch" else 248

    def draw(self):
        c = self.canv
        boxes = [
            ("BTS trên HDFS", "Mỗi dòng là một chuyến bay"),
            ("M2: Spark batch", "Làm sạch dữ liệu và tính thống kê"),
            ("KPI / box lịch sử", "Aggregate Parquet hoặc JSONL + manifest"),
            ("M5: loader và lớp truy vấn", "Kiểm tra, upsert, đối chiếu và công bố"),
            ("MongoDB", "Document, index và metadata snapshot"),
            ("Dashboard", "Truy vấn, lọc, so sánh và trực quan hóa"),
        ] if self.kind == "batch" else [
            ("Thao tác từ Windows", "PowerShell, trình duyệt và Compass"),
            ("Docker Desktop / Docker Compose", "Môi trường container, mạng và health checks"),
            ("Các service M5", "dashboard và loader kết nối mongo:27017"),
            ("Lưu trữ kết quả", "Volume MongoDB; logs và evidence trên host"),
        ]
        width, box_height = min(WIDTH - 30, 340), 41
        x = (WIDTH - width) / 2
        step = 56 if self.kind == "batch" else 63
        top = self.height - 4
        for i, (title, detail) in enumerate(boxes):
            c.setLineWidth(.65)
            c.setStrokeColor(BLACK)
            c.rect(x, top - box_height, width, box_height, fill=0, stroke=1)
            c.setFillColor(BLACK)
            c.setFont("TNR-Bold", 11)
            c.drawCentredString(WIDTH / 2, top - 15, title)
            c.setFont("TNR", 10.5)
            c.drawCentredString(WIDTH / 2, top - 30, detail)
            if i < len(boxes) - 1:
                arrow(c, WIDTH / 2, top - box_height - 1, top - step + 2)
            top -= step


class PaperDocument(BaseDocTemplate):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.section_count = 0

    def afterFlowable(self, item):
        if isinstance(item, Paragraph) and item.style.name in ("PaperH1", "PaperH2"):
            self.section_count += 1
            key = f"section-{self.section_count}"
            self.canv.bookmarkPage(key)
            level = 0 if item.style.name == "PaperH1" else 1
            self.canv.addOutlineEntry(item.getPlainText(), key, level=level)


def decorate(c, doc):
    c.saveState()
    if doc.page > 1:
        c.setFont("TNR-Italic", 9)
        c.drawString(LEFT, H - 16 * mm, "M5 — NoSQL, Serving và Dashboard")
    c.setFont("TNR", 10)
    c.drawCentredString(W / 2, 14 * mm, str(doc.page))
    c.restoreState()


def blocks(source):
    lines = source.splitlines()
    parsed, i = [], 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
        line = lines[i].strip()
        if line.startswith("```"):
            language = line[3:]
            i += 1
            content = []
            while i < len(lines) and not lines[i].startswith("```"):
                content.append(lines[i])
                i += 1
            assert i < len(lines), "Unclosed code block"
            parsed.append(("code", (language, "\n".join(content))))
        elif line.startswith("{{figure:"):
            parsed.append(("figure", line.removeprefix("{{figure:").removesuffix("}}")))
        elif line.startswith("### "):
            parsed.append(("h2", line[4:]))
        elif line.startswith("## "):
            parsed.append(("h1", line[3:]))
        elif line.startswith("# "):
            parsed.append(("title", line[2:]))
        else:
            content = [line]
            while i + 1 < len(lines) and lines[i + 1].strip():
                if lines[i + 1].startswith(("#", "```", "{{figure:")):
                    break
                i += 1
                content.append(lines[i].strip())
            parsed.append(("paragraph", " ".join(content)))
        i += 1
    return parsed


def build_story():
    parsed = blocks(SOURCE.read_text(encoding="utf-8"))
    section = "front"
    i = 0
    while i < len(parsed):
        kind, text = parsed[i]
        if kind in ("title", "h1", "h2"):
            STORY.append(paragraph(text, kind))
            if kind == "h1":
                section = text
                HEADINGS.append(text)
        elif kind == "paragraph":
            style = "body"
            if section == "front":
                style = "meta"
            elif section == "Tóm tắt":
                style = "abstract"
            elif section == "Tài liệu tham khảo":
                style = "ref"
            STORY.append(paragraph(text, style))
        elif kind == "code":
            language, raw = text
            COMMANDS.append({"language": language, "code": raw})
            widest = max(pdfmetrics.stringWidth(line, "PaperCode", 9) for line in raw.splitlines())
            assert widest <= WIDTH - 12, f"Code exceeds column: {raw}"
            STORY.append(XPreformatted(escape(raw), STYLES["code"]))
        elif kind == "figure":
            figure = (Image(str(GUIDE / "pdf_assets/dashboard_thuc_te.png"), width=400, height=475)
                      if text == "dashboard" else PaperDiagram(text))
            contents = [Spacer(1, 6), figure]
            if i + 1 < len(parsed) and parsed[i + 1][0] == "paragraph" and parsed[i + 1][1].startswith("*Hình"):
                i += 1
                contents.append(paragraph(parsed[i][1], "caption"))
            STORY.append(KeepTogether(contents))
        i += 1


def validate():
    doc = fitz.open(PDF)
    complete = " ".join(" ".join(p.get_text().split()) for p in doc)
    tasks = [heading for heading in HEADINGS if "Task " in heading]
    assert len(tasks) == 10
    for heading in HEADINGS:
        assert heading in complete, heading
    assert len(doc.get_toc()) >= len(HEADINGS)
    fonts = sorted({font[3] for page in doc for font in page.get_fonts()})
    assert any("TimesNewRoman" in font for font in fonts), fonts
    assert not any("DejaVuSans" in font for font in fonts), fonts
    for page in doc:
        assert abs(page.rect.width - W) < 1 and abs(page.rect.height - H) < 1
        assert "\ufffd" not in page.get_text() and "\u25a0" not in page.get_text()
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    x0, y0, x1, y1 = span["bbox"]
                    assert x0 >= LEFT - 1 and x1 <= W - RIGHT + 1, (page.number, span["text"])
                    assert y0 >= 0 and y1 < H - 20, (page.number, span["text"])
        page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False).save(OUT / f"page_{page.number + 1:02d}.png")
    for command in COMMANDS:
        assert " ".join(command["code"].split()) in complete, command
    reference = ROOT.parent / "batch-layer/spark_jobs/export/m2_to_m5/20261107T042703414867Z/manifest.json"
    manifest_checked = False
    if reference.exists():
        m = json.loads(reference.read_text(encoding="utf-8"))
        assert len(m["tables"]) == 20 and sum(t["rows"] for t in m["tables"]) == 74921
        assert m["coverage"]["month_count"] == 51 and m["coverage"]["total_flights"] == 29328846
        manifest_checked = True
    report = {"result": "PASS", "pages": len(doc), "major_tasks": len(tasks),
              "layout": "A4, one column; continuous article; no tables/cards or forced section page breaks",
              "body_font": "Times New Roman", "body_size_pt": 12, "leading_pt": 18,
              "margins_mm": {"left": 30, "right": 25, "top": 25, "bottom": 25},
              "embedded_fonts": fonts, "bookmarks": len(doc.get_toc()),
              "reference_manifest_checked": manifest_checked, "command_blocks": len(COMMANDS),
              "checks": ["ten major tasks", "all headings", "Vietnamese text extraction", "font embedding",
                         "text inside column", "commands preserved in PDF", "A4"],
              "bytes": PDF.stat().st_size, "scope": "Document generation only"}
    (GUIDE / "pdf_assets/learning_paper_validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "command_blocks.json").write_text(json.dumps(COMMANDS, ensure_ascii=False), encoding="utf-8")
    doc.close()
    print(json.dumps(report, ensure_ascii=False))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    build_story()
    doc = PaperDocument(str(PDF), pagesize=A4, leftMargin=LEFT, rightMargin=RIGHT,
                        topMargin=TOP, bottomMargin=BOTTOM,
                        title="M5 — Tài liệu học tập theo các nhiệm vụ thành phần",
                        author="Nhóm dự án AERO",
                        subject="Tài liệu một cột, Times New Roman, tổ chức theo mười task lớn")
    frame = Frame(LEFT, BOTTOM, WIDTH, HEIGHT, leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="single-column-paper", frames=[frame], onPage=decorate)])
    doc.build(STORY)
    validate()


if __name__ == "__main__":
    main()
