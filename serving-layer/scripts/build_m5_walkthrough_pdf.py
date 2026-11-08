"""Create the Vietnamese end-to-end M5 practical walkthrough PDF.

Uses the existing briefing renderer and optional PDF authoring dependencies.
Only documentation artifacts are written; operational commands are never run.
"""
from __future__ import annotations

import json
import re
from xml.sax.saxutils import escape

import fitz
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import Flowable, Frame, Image, PageBreak, PageTemplate, Table, TableStyle, XPreformatted

import build_m5_overview_pdf as base

ROOT, GUIDE, CW, W, H = base.ROOT, base.GUIDE, base.CW, base.W, base.H
PDF = GUIDE / "HUONG_DAN_M5_TU_DAU_DEN_CUOI_CHI_TIET.pdf"
OUT = ROOT / "logs" / "m5_walkthrough_pdf"
ASSETS = GUIDE / "pdf_assets"
PAGES = []
COMMANDS = []
p, h, grid, note, bullet = base.p, base.h, base.grid, base.note, base.bullet


def code(text, language="powershell"):
    text = text.strip("\n")
    COMMANDS.append({"language": language, "code": text})
    size = 8.2
    widest = max(pdfmetrics.stringWidth(line, "Code", size) for line in text.splitlines())
    if widest > CW - 26:
        raise ValueError(f"Code line too wide ({widest:.1f}): {max(text.splitlines(), key=len)}")
    style = ParagraphStyle("WalkthroughCode", fontName="Code", fontSize=size,
                           leading=12, textColor=base.INK)
    caption = {"powershell": "POWERSHELL WINDOWS", "javascript": "MONGOSH — JAVASCRIPT",
               "json": "FILTER COMPASS — JSON", "text": "KẾT QUẢ / CẤU HÌNH THAM CHIẾU"}[language]
    table = Table([[p(caption, "small")], [XPreformatted(escape(text), style)]],
                  colWidths=[CW], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), base.PALE),
        ("BOX", (0, 0), (-1, -1), .5, base.LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, 0), 7),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
        ("TOPPADDING", (0, 1), (-1, 1), 3),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 10),
    ]))
    table.spaceAfter = 11
    return table


def page(title, *items):
    PAGES.append((title, [p(title, "h1"), *items]))


class Cover(Flowable):
    def __init__(self):
        super().__init__()
        self.width, self.height = CW, 712

    def draw(self):
        c = self.canv
        c.setFillColor(base.NAVY)
        c.roundRect(0, 189, CW, 517, 18, fill=1, stroke=0)
        base.label(c, "AERO  /  PRACTICAL WALKTHROUGH", 27, 668, 9, base.colors.HexColor("#72d5d3"), True)
        base.label(c, "M5", 24, 564, 88, base.WHITE, True)
        base.text_at(c, "Từ đầu đến cuối", 27, 520, CW - 54, 30, base.WHITE, True)
        base.text_at(c, "Làm gì · Vì sao · Thao tác thế nào", 27, 470, CW - 54, 15, base.WHITE)
        base.text_at(c, "Nhận dữ liệu M2 → Docker → MongoDB<br/>→ kiểm tra → dashboard → bàn giao", 27, 410,
                     CW - 54, 13, base.colors.HexColor("#c9dce9"))
        base.text_at(c, "HƯỚNG DẪN THỰC HÀNH WINDOWS / POWERSHELL", 27, 332,
                     CW - 54, 9, base.colors.HexColor("#72d5d3"), True)
        base.text_at(c, "Dành cho thành viên triển khai và người thuyết trình<br/>Phiên bản 1.0 · Đối chiếu code ngày 07/11/2026", 27, 286,
                     CW - 54, 10.2, base.WHITE)
        base.text_at(c, "Mỗi bước đều có mục đích, lệnh/thao tác, giải thích code,<br/>kết quả cần thấy và hướng xử lý khi không đạt.", 3, 151,
                     CW - 6, 12, base.TEAL, True)
        base.text_at(c, "Luồng chính: batch M2 → MongoDB → dashboard đã có code và kiểm thử.<br/>HDFS: nhánh tùy chọn. Streaming M4: chờ tích hợp.<br/>Kubernetes: phương án mở rộng, chưa có triển khai trong repo.",
                     3, 91, CW - 6, 10, base.INK)
        base.text_at(c, "Đọc theo thứ tự; chỉ chuyển bước khi kiểm tra đạt. Số liệu mẫu: 20 bảng, 74.921 document, 51 tháng, 29.328.846 chuyến sau cleaning.",
                     3, 29, CW - 6, 8.2, base.MUTED)


def decorate(c, doc):
    c.saveState()
    c.setFillColor(base.NAVY)
    c.rect(0, H - 27, W, 27, fill=1, stroke=0)
    base.label(c, "AERO  /  M5 — HƯỚNG DẪN TỪ ĐẦU ĐẾN CUỐI", 44, H - 18, 7.7, base.WHITE, True)
    c.setFont("Body", 7.4)
    c.drawRightString(W - 44, H - 18, "TEAM REFERENCE  •  07/11/2026")
    c.setStrokeColor(base.LINE)
    c.line(44, 39, W - 44, 39)
    base.label(c, "M5 • NoSQL, Serving & Dashboard", 44, 25, 7.4, base.MUTED)
    c.setFont("Body", 7.4)
    c.drawRightString(W - 44, 25, f"{doc.page:02d}")
    c.restoreState()


def content():
    PAGES.append(("Bìa", [Cover()]))
    page("Lộ trình và cách đọc tài liệu",
         p("Mục tiêu là giúp một thành viên nhận đúng code và dữ liệu, tự dựng M5, giải thích được chương trình làm gì, kiểm tra kết quả và bàn giao lại. Thực hiện luồng chính trước; các nhánh cuối được ghi rõ điều kiện."),
         grid(["Nhóm bước", "Nội dung", "Trang"], [
             ("Chuẩn bị", "<link href='#page-3' color='#2563eb'>Input, hợp đồng dữ liệu, cài đặt, đường dẫn</link>", "3–7"),
             ("Khởi động và nạp", "<link href='#page-8' color='#2563eb'>Start, CheckOnly, load và cách writer hoạt động</link>", "8–11"),
             ("Xác minh / xem data", "<link href='#page-12' color='#2563eb'>Verifier, Compass và mongosh</link>", "12–14"),
             ("Sử dụng / nghiệm thu", "<link href='#page-15' color='#2563eb'>Dashboard, chỉ số, tests và vị trí output</link>", "15–18"),
             ("Bàn giao / tiếp tục", "<link href='#page-19' color='#2563eb'>ZIP evidence, dừng và khởi động lại</link>", "19–20"),
             ("Xử lý lỗi / lệnh thay thế", "<link href='#page-21' color='#2563eb'>Chẩn đoán lỗi và Docker khi script bị chặn</link>", "21–22"),
             ("Nhánh mở rộng", "<link href='#page-23' color='#2563eb'>HDFS, streaming M4 và Kubernetes</link>", "23–25"),
             ("Giải thích code / hoàn tất", "<link href='#page-26' color='#2563eb'>Đường đi code, checklist và tài liệu nguồn</link>", "26–27"),
         ], [.26, .61, .13]),
         note("Quy tắc chạy lệnh", "Khối POWERSHELL WINDOWS chạy tại dấu nhắc PS. Khối MONGOSH chạy sau khi đã vào mongosh. JSON Filter nhập vào Compass. Không dán Python như spark.stop() vào PowerShell; M5 không yêu cầu chạy notebook."),
         p("Lệnh nhiều dòng ở tài liệu này có thể dùng dấu backtick ` ở cuối dòng để nối lệnh PowerShell. Giữ nguyên dấu đó, không thêm khoảng trắng phía sau. Không sao chép dấu nhắc terminal; không thêm dấu \\ cuối dòng."),
         p("Các tên snapshot và số lượng trong ví dụ thuộc bộ 20261107T042703414867Z. Nếu nhận bộ khác, phải xác nhận hợp đồng/coverage được hỗ trợ và điều chỉnh mốc đối chiếu.", "small"))

    page("01 / Nhận đúng code và dữ liệu",
         h("Mục đích"),
         p("Có đủ hai thứ độc lập: code M5 để thực thi, và output M2 để nạp. M5 phục vụ kết quả tổng hợp; không cần chuyển 29 triệu dòng raw vào MongoDB cho dashboard này."),
         grid(["Cần nhận", "Kiểm tra bằng File Explorer / VS Code"], [
             ("Code serving-layer", "compose.yml, Dockerfile, requirements/constraints, app.py, m5/, scripts/, tests/, assets/, .streamlit/, doc_guide/. Giữ các file/thư mục ẩn."),
             ("Snapshot M2", "Một thư mục chứa trực tiếp manifest.json và 20 JSONL. Bộ đầy đủ còn có 20 CSV: tổng cộng 41 file."),
             ("Metadata bàn giao", "Tên snapshot, nguồn/coverage, quy ước KPI, tên phiên bản code và những bước M2 đã hoàn tất."),
         ], [.29, .71]),
         h("Hai cách nhận cùng một loại input"),
         p("<b>Export gốc:</b> batch-layer/spark_jobs/export/m2_to_m5/20261107T042703414867Z.<br/><b>ZIP bàn giao M2:</b> giải nén bằng Extract All, chọn thư mục data bên trong M2_HANDOFF_20261107T042703414867Z."),
         note("Điều kiện để sang bước tiếp theo", "Đã nhìn thấy manifest và JSONL, code có thư mục scripts/m5 thật. Clone repo chưa bảo đảm có exports vì dữ liệu được Git bỏ qua. Không truyền đường dẫn ZIP hoặc thư mục cha chứa nhiều snapshot cho loader."),
         p("Luồng JSONL không cần Hadoop/Spark M2 đang chạy. Nhánh đọc trực tiếp aggregate Parquet cần HDFS và mạng tương ứng, được hướng dẫn riêng ở trang 23."))

    page("02 / Hiểu hợp đồng và hạ tầng",
         p("M2 tạo KPI/box; M5 kiểm tra schema, khóa, giá trị rồi lưu vào MongoDB. Dashboard đọc MongoDB. Đây là sự phân chia công việc giúp team không lặp việc xử lý raw."),
         grid(["Khái niệm", "Trong project này"], [
             ("Grain", "Một document đại diện cho một nhóm: tháng, năm/hãng hoặc năm/tuyến. Không phải một document cho mỗi chuyến bay."),
             ("Khóa nghiệp vụ", "KPI tháng: year + month. Tuyến: year + origin + dest. Box còn có var và population."),
             ("Đơn vị / mẫu số", "Tỷ lệ 0–1; delay là phút, có thể âm; null giữ nguyên. Quần thể chuyến đến hợp lệ khác tổng chuyến."),
             ("Snapshot", "Bộ dữ liệu nhất quán; M5 thêm snapshot_id để cô lập các lần xuất và truy vấn đúng bộ active."),
         ], [.27, .73]),
         grid(["Thành phần", "Vai trò và nơi chạy"], [
             ("PowerShell / Docker Desktop", "Terminal Windows điều khiển các container Linux."),
             ("mongo", "MongoDB server lưu KPI và metadata trong volume."),
             ("loader", "Python/PyMongo chạy một lần để kiểm tra và nạp."),
             ("dashboard", "Streamlit + Plotly trả giao diện cho trình duyệt."),
             ("Compass", "Ứng dụng Windows tùy chọn để xem server MongoDB."),
         ], [.37, .63]),
         note("Kết quả cần hiểu", "74.921 document là số dòng tổng hợp của bộ mẫu; 29.328.846 là tổng flights được mô tả. Không cộng các bảng overall, hãng và sân bay với nhau vì chúng là các góc nhìn khác nhau của cùng tập chuyến."))

    page("03 / Cài và kiểm tra môi trường",
         h("Cài đặt lần đầu trên Windows"),
         p('Tải theo <link href="https://docs.docker.com/desktop/setup/install/windows-install/" color="#2563eb">hướng dẫn Docker Desktop chính thức</link>; kiểm tra yêu cầu Windows/ảo hóa, dùng backend WSL 2 và Linux containers. Nếu đã chạy Docker M2 bình thường thì không cần cài lại.'),
         p('Nếu chưa có WSL, theo <link href="https://learn.microsoft.com/en-us/windows/wsl/install" color="#2563eb">hướng dẫn Microsoft</link>. Chỉ lệnh cài WSL bên dưới chạy trong PowerShell <b>Run as administrator</b>; khởi động lại máy nếu được yêu cầu.'),
         code("wsl --install"),
         h("Kiểm tra sau khi mở Docker Desktop"),
         code("docker version\ndocker compose version"),
         note("Kết quả cần thấy", "docker version có cả Client và Server; không lỗi kết nối daemon. docker compose version in được phiên bản. Lần đầu build cần Internet để tải images/dependencies. Nếu terminal chưa nhận docker sau cài đặt, mở lại terminal."),
         h("Có cần cài MongoDB/Python riêng không?"),
         p("Không cần cho luồng chạy bằng Docker: image có Python và các thư viện; MongoDB server chạy trong container. Muốn xem dữ liệu bằng GUI thì cài thêm <link href='https://www.mongodb.com/docs/compass/install/' color='#2563eb'>MongoDB Compass</link>, kết nối sau khi nạp. Compass không thay MongoDB server."),
         p("Các bước sau dùng PowerShell thông thường. Trạng thái kiểm thử trong repo là kiểm thử local trên bản code hiện có, không xác nhận mọi máy mới đều đã cài thành công.", "small"))

    page("04 / Khai báo đúng đường dẫn",
         p("Mở PowerShell hoặc terminal PowerShell trong VS Code. Sửa biến đầu nếu dự án nằm ở ổ khác; dấu <b>$</b> trước tên biến là bắt buộc. Khai báo lại khi mở terminal mới."),
         code(r"""$AeroProject = 'F:\Project-BigData-Storage-and-Processing'
$AeroServing = Join-Path $AeroProject 'serving-layer'
$AeroExport = Join-Path $AeroProject 'batch-layer\spark_jobs\export'
$AeroSnapshot = Join-Path $AeroExport 'm2_to_m5\20261107T042703414867Z'
Set-Location $AeroServing
Get-Location"""),
         h("Nếu dùng thư mục data từ ZIP M2"),
         p("Chỉ thay riêng giá trị AeroSnapshot trước khi làm tiếp, ví dụ bên dưới. Giữ các biến còn lại. Đây là nhánh lựa chọn, không bắt buộc chạy cả hai."),
         code(r"$AeroSnapshot = 'D:\M2_HANDOFF_20261107T042703414867Z\data'"),
         h("Kiểm tra file và vị trí terminal"),
         code(r"""Test-Path .\compose.yml
Test-Path .\scripts\start_m5.ps1
Test-Path .\m5\load_batch.py
Test-Path (Join-Path $AeroSnapshot 'manifest.json')
@(Get-ChildItem -LiteralPath $AeroSnapshot -Filter '*.jsonl' -File).Count"""),
         note("Kết quả cần thấy", "Get-Location là serving-layer; bốn Test-Path trả True, số JSONL là 20. Nếu False hoặc biến null, sửa ở bước này rồi chạy kiểm tra lại; chưa nạp MongoDB."),
         p("Compose có mount export gốc trong cây dự án; script cũng mount thêm SnapshotPath cụ thể để dùng được data ở ổ khác. Giữ cây dự án ở vị trí có thể ghi.", "small"))

    page("05 / Đọc manifest và số liệu mẫu",
         p("Manifest là bảng mô tả dữ liệu M2 bàn giao: tên bảng, file, schema, khóa, số dòng và coverage. Đọc mô tả trước giúp nhận ra thiếu file hoặc chọn nhầm bộ; bước CheckOnly sẽ kiểm tra nội dung thật."),
         code(r"""$AeroManifestFile = Join-Path $AeroSnapshot 'manifest.json'
$AeroManifest = Get-Content -LiteralPath $AeroManifestFile `
  -Raw -Encoding UTF8 | ConvertFrom-Json
$AeroManifest.coverage
$AeroManifest.tables | Select-Object group, name, rows
($AeroManifest.tables | Measure-Object -Property rows -Sum).Sum"""),
         grid(["Mốc bộ 20261107T042703414867Z", "Giá trị"], [
             ("Bảng KPI / box", "13 / 7"),
             ("Document KPI / box", "64.249 / 10.672"),
             ("Tổng document dữ liệu", "74.921, chưa tính metadata"),
             ("month_count / coverage", "51 / 2022-01 → 2026-03"),
             ("total_flights", "29.328.846 chuyến sau cleaning"),
         ], [.61, .39]),
         h("Giải thích các file liên quan"),
         p("contracts.py chứa catalog 20 bảng và quy tắc kiểm tra. JSONL giữ số/boolean/null theo schema, CSV dùng để đọc/đối chiếu. Không sửa rows/schema trong manifest chỉ để làm loader bỏ qua lỗi."),
         note("Điều kiện tiếp tục", "Đúng bộ dữ liệu, đủ bảng và số liệu khớp kỳ dự kiến. Với bộ khác, xác nhận lại phạm vi được loader hỗ trợ trước khi chạy; các số mẫu không áp dụng cho mọi export."))

    page("06 / Khởi động MongoDB và UI",
         h("Chạy tại PowerShell trong serving-layer"),
         code(r""".\scripts\start_m5.ps1
docker compose -f compose.yml ps"""),
         h("Script thực hiện những gì?"),
         p("Kiểm tra Compose → build image ứng dụng từ Dockerfile/requirements → bật mongo và dashboard → chờ health checks. Container loader chưa cần chạy vì nó chỉ thực thi lúc nạp/verify. Build lần đầu có thể lâu hơn; đợi lệnh kết thúc."),
         grid(["Kiểm tra", "Kết quả mong đợi"], [
             ("docker compose ps", "Có mongo và dashboard, trạng thái healthy."),
             ("Dashboard trên Windows", "http://localhost:8501; chưa nạp thì chưa có snapshot."),
             ("MongoDB trên Windows", "mongodb://localhost:27017; database mặc định aero_m5."),
             ("Kết nối trong container", "Dashboard/loader dùng mongodb://mongo:27017."),
         ], [.39, .61]),
         note("Nếu cổng bị chiếm", "Tạo .env từ .env.example nếu chưa có, đổi M5_MONGO_PORT hoặc M5_DASHBOARD_PORT, start lại. Không ghi đè .env hiện có. Khi đổi cổng Windows, URI nội bộ mongo:27017 vẫn giữ nguyên."),
         code(r"""if (-not (Test-Path .\.env)) { Copy-Item .\.env.example .\.env }
notepad .\.env"""),
         p("Ví dụ đổi 27018/8502 thì Compass dùng localhost:27018, trình duyệt dùng localhost:8502. Nếu .ps1 bị Execution Policy chặn, làm nhánh lệnh Docker ở trang 22; không cần đổi policy vĩnh viễn.", "small"))

    page("07 / Kiểm tra trước khi nạp",
         h("Mục đích: xác minh input, chưa ghi MongoDB"),
         code(r".\scripts\load_m2.ps1 -SnapshotPath $AeroSnapshot -CheckOnly"),
         grid(["Chương trình kiểm tra", "Ý nghĩa"], [
             ("Catalog / schema", "Đủ 13 KPI + 7 box, đúng tên collection, fields và kiểu dữ liệu."),
             ("Khóa / phạm vi", "Không trùng khóa, không null ở khóa; month/day/hour và var/population hợp lệ."),
             ("Rows / coverage", "Đếm dữ liệu thật, so manifest và yêu cầu kỳ dự án; kiểm tra tổng flights liên quan."),
             ("Fingerprint", "Tính định danh từ schema, giá trị và coverage để nhận diện cùng bộ nội dung."),
         ], [.34, .66]),
         h("Kết quả cuối cần có với bộ mẫu"),
         code('"result": "PASS"\n"total_documents": 74921\nREPORT: /app/evidence/load_report.json', "text"),
         p("Đường dẫn REPORT trong container tương ứng serving-layer/evidence/load_report.json trên Windows. Log script nằm ở logs/load_m2.log. CheckOnly không kết nối/ghi MongoDB nhưng vẫn có thể build image."),
         note("Nếu không đạt", "Kiểm tra đúng thư mục snapshot, file thiếu/hỏng, manifest/schema hoặc coverage. Không thêm -AllowPartial để che lỗi bộ bàn giao; tùy chọn này dành cho thử nghiệm có ghi rõ phạm vi và vẫn yêu cầu 20 bảng.", "amber"),
         p("Báo cáo CheckOnly sẽ bị lần load sau ghi lại cùng tên. Nếu cần giữ bằng chứng riêng, chép file trước khi làm bước kế tiếp.", "small"))

    page("08 / Nạp dữ liệu vào MongoDB",
         code(r".\scripts\load_m2.ps1 -SnapshotPath $AeroSnapshot"),
         h("Từ lệnh PowerShell đến chương trình Python"),
         p("load_m2.ps1 nhận đường dẫn Windows, xác nhận có manifest và mount nguồn read-only vào /data/snapshot. Docker gọi python -m m5.load_batch; chương trình dùng PyMongo kết nối service mongo và gọi writer."),
         h("Kết quả cần thấy lần nạp đầu"),
         code("LOADED ...\nLOAD COMPLETE: <snapshot_id>; 74921 documents; PASS\n\"result\": \"PASS\"", "text"),
         p("snapshot_id là fingerprint nội dung, khác tên thư mục thời gian. Lệnh kết thúc thành công mới sang bước verify. Nếu bị lỗi giữa chừng, đọc log; không dùng report cũ còn trên ổ để kết luận lần mới thành công."),
         h("Thử nạp lại cùng bộ để chứng minh không nhân bản"),
         code(r".\scripts\load_m2.ps1 -SnapshotPath $AeroSnapshot"),
         note("Kết quả nạp lại", "ALREADY LOADED; values verified; active selection unchanged, cùng số document. Nếu bộ đã được nạp trước buổi demo, thấy ALREADY LOADED ngay lần đầu thao tác trong buổi đó là đúng. Không cần xóa database để tạo lại lần nạp đầu."),
         p("Input không bị sửa; dữ liệu phục vụ nằm trong MongoDB và volume riêng. Code/log/report là các thành phần khác nhau; lưu ý vị trí của từng loại ở trang 18.", "small"))

    page("09 / Bên trong writer làm gì?",
         p("Dùng trang này để giải thích code sau khi team đã thấy thao tác nạp. Thứ tự dưới đây giúp dashboard nhận một bộ dữ liệu hoàn chỉnh."),
         grid(["Thao tác", "Lý do và cách thực hiện"], [
             ("Inspect / digest", "Kiểm tra toàn bộ nguồn trước ghi, tạo digest theo khóa để sau đó đối chiếu giá trị."),
             ("Lease loader", "Điều phối writer bằng khóa có hạn 10 phút, gia hạn theo lô/bảng; loader cũ bị kill thì chờ lease hết."),
             ("Unique indexes", "snapshot_id + toàn bộ khóa nghiệp vụ; box luôn gồm var và population."),
             ("Bulk upsert", "Ghi theo lô 1.000 ReplaceOne: có khóa thì thay document, chưa có thì thêm. Snapshot đã published không sửa tại chỗ."),
             ("Verify nguồn/DB", "Inspect lại nguồn và đọc MongoDB, so đủ digest giá trị trước khi công bố."),
             ("Publish pointer", "serving_state trỏ snapshot mới sau khi đạt; dashboard đọc theo con trỏ trong lượt chạy."),
         ], [.29, .71]),
         note("Những tình huống quan trọng", "Lần nạp chưa hoàn tất có thể retry. Lần lỗi không thay snapshot active cũ. Nạp lại một bộ cũ đã published không tự rollback dashboard. Metadata hỗ trợ khôi phục ở ranh giới verify/publish."),
         h("Mở file để xem logic"),
         p("m5/contracts.py: schema, keys, read_rows, table_digest.<br/>m5/batch_writer.py: loader_lock, ensure_indexes, load_snapshot, verify_run.<br/>m5/queries.py: lấy active snapshot và lọc đúng chiều."),
         p("Các cơ chế này bảo vệ tính nhất quán serving; không mặc định tạo bảo đảm exactly-once cho toàn bộ Kafka/Spark/sink hoặc thay thế kiểm chứng công thức ở M2.", "small"))

    page("10 / Xác minh dữ liệu đã nạp",
         code(r""".\scripts\verify_m5.ps1
Get-Content .\evidence\verify_report.json -Raw -Encoding UTF8"""),
         h("Kết quả cần thấy"),
         code("ALL 20 COLLECTIONS CHECKED: PASS; 74921 documents", "text"),
         grid(["Nội dung", "Cách kiểm tra"], [
             ("Snapshot active", "Đọc serving_state và batch_runs; bộ phải đã published."),
             ("Tất cả bảng", "Đọc document của snapshot, tính digest từ giá trị và so với nguồn được ghi nhận ở ingest."),
             ("Unique index", "Tên snapshot_business_key, unique=true, đúng snapshot_id + keys từng bảng."),
             ("Báo cáo", "result, snapshot_id, total_documents, coverage, tables và indexes trong verify_report.json."),
         ], [.31, .69]),
         h("Lưu bằng chứng đúng lần chạy"),
         p("Log: serving-layer/logs/verify_m5.log.<br/>Report: serving-layer/evidence/verify_report.json.<br/>Có thể mở bằng VS Code hoặc Notepad. Chỉ coi report là kết quả mới khi lệnh verify hiện tại đã thành công."),
         note("Phạm vi kết luận", "PASS chứng minh dữ liệu/index trong MongoDB khớp nguồn đã inspect lúc nạp. Muốn chứng minh KPI đúng từ raw phải kết hợp kiểm chứng cleaning và công thức ở M2. Không cần đếm lại 29 triệu dòng ở mỗi lần mở dashboard."),
         p("Nếu báo No active snapshot, quay lại bước nạp. Nếu MongoDB/source values mismatch, giữ log và điều tra dữ liệu bị thay đổi; không sửa report để đánh dấu PASS.", "small"))

    page("11 / Xem dữ liệu bằng Compass",
         h("Thao tác trên ứng dụng MongoDB Compass"),
         p('Cài theo <link href="https://www.mongodb.com/docs/compass/install/" color="#2563eb">trang Compass chính thức</link> nếu chưa có. MongoDB trong Docker phải đang healthy. Theo <link href="https://www.mongodb.com/docs/compass/connect/" color="#2563eb">hướng dẫn kết nối</link>, chọn Add New Connection, nhập URI dưới và Connect/Save &amp; Connect.'),
         code("mongodb://localhost:27017", "text"),
         p("<b>1.</b> Mở database aero_m5.<br/><b>2.</b> Mở collection serving_state, tìm document _id = historical.<br/><b>3.</b> Sao chép snapshot_id của document đó.<br/><b>4.</b> Mở kpi_month_overall → tab Documents.<br/><b>5.</b> Dán Filter dưới đây, thay chuỗi mẫu bằng snapshot_id thật rồi bấm Find."),
         code('''{
  "snapshot_id": "THAY_BANG_SNAPSHOT_ID_VUA_SAO_CHEP",
  "year": 2025,
  "month": 1
}''', "json"),
         h("Đọc và đối chiếu document"),
         p("Cần thấy một document KPI tháng 1/2025 của bộ active. Xem flights, arr_n, on_time, otp_operated, delay15_rate, cancel_rate. Tỷ lệ 0.8 tương ứng 80%. Mở tab Indexes để thấy snapshot_business_key unique."),
         note("Thông tin kết nối", "Cấu hình local hiện tại không yêu cầu username/password. Nếu đã đổi M5_MONGO_PORT thì dùng cổng Windows mới. Không dùng hostname mongo của mạng container trong Compass Windows. Nếu không thấy aero_m5, kiểm tra đã nạp đúng instance/port chưa."))

    page("12 / Xem data bằng mongosh",
         p("Không cần cài shell riêng trên Windows vì container MongoDB có sẵn mongosh. Đây là cách kiểm tra trực tiếp khi không dùng Compass."),
         code("docker compose -f compose.yml exec mongo mongosh aero_m5"),
         note("Đổi đúng nơi nhập lệnh", "Sau lệnh trên, dấu nhắc chuyển sang mongosh của database aero_m5. Chỉ lúc đó mới dán các lệnh JavaScript bên dưới. Không dán chúng vào dấu nhắc PS."),
         code('''show collections
var active = db.serving_state.findOne({_id: "historical"});
var sid = active.snapshot_id;
db.kpi_month_overall.countDocuments({snapshot_id: sid});
db.kpi_month_overall.findOne({snapshot_id: sid, year: 2025, month: 1});
db.kpi_month_overall.getIndexes();''', "javascript"),
         h("Tính tổng flights từ KPI tháng trong MongoDB"),
         code('''db.kpi_month_overall.aggregate([
  {$match: {snapshot_id: sid}},
  {$group: {_id: null, flights: {$sum: "$flights"}}}
]);''', "javascript"),
         p("Bộ mẫu: countDocuments = <b>51</b>; tổng flights = <b>29328846</b>. Index có snapshot_id, year, month và unique:true. Có metadata/nhiều snapshot thì tổng toàn database lớn hơn; luôn lọc đúng sid."),
         p("Gõ <b>exit</b> trong mongosh để về PowerShell. Nếu active là null thì chưa có snapshot được công bố. Nếu đổi M5_DATABASE, thay tên database trong lệnh mở shell.", "small"))

    page("13 / Mở và sử dụng dashboard",
         code("Start-Process 'http://localhost:8501'"),
         p("Nếu đổi cổng thì dùng URL mới. Nếu đã mở từ trước khi nạp, nhấn <b>Làm mới dữ liệu</b>. Chọn toàn bộ năm 2022–2026 và các tháng để so tổng 29.328.846; một kỳ đang lọc sẽ có tổng nhỏ hơn."),
         grid(["Trang", "Thao tác và kết quả"], [
             ("Tổng quan", "Chọn năm/tháng; xem 5 KPI, lưu lượng Diện tích/Cột, donut và cơ cấu mức trễ."),
             ("Thời gian & mùa vụ", "Chọn ngày trong kỳ hoặc bảng gộp tháng/ngày lịch/giờ; xem đường, heatmap, polar 24 giờ."),
             ("Hãng bay", "Chọn kỳ/hãng, ngưỡng flights, chỉ số; xem ranking, bubble, treemap và animation theo năm."),
             ("Sân bay xuất phát", "Chọn origin và chỉ số; so sánh lưu lượng/độ trễ theo chuyến xuất phát."),
             ("Tuyến bay", "Chọn năm, origin/dest, top N; xem Sankey và so sánh cùng top tuyến."),
             ("Phân phối delay", "Chọn bảng, kỳ, arr/dep và all/late; đọc Q1, median, Q3 và whiskers."),
             ("Streaming", "Hiện chờ khi chưa tích hợp M4; chưa phải bằng chứng realtime."),
             ("Dữ liệu & vận hành", "Xem bộ active, coverage, số dòng và metadata để truy nguồn."),
         ], [.31, .69]),
         p("Hover để xem số; click chú giải để ẩn/hiện; kéo zoom và nhấn đúp reset khi biểu đồ hỗ trợ. Camera xuất PNG, phần dữ liệu có tải CSV. File tải về nằm trong thư mục trình duyệt chọn, không tự vào evidence.", "small"))

    page("14 / Đọc và giải thích biểu đồ",
         Image(str(ASSETS / "dashboard_thuc_te.png"), width=335, height=397.8125),
         p("Ảnh dashboard thực tế từ evidence ngày 07/11/2026, toàn kỳ BTS 2022-01 → 2026-03. Đây không phải dữ liệu streaming.", "small"),
         bullet("Tỷ lệ gộp từ tổng count/sum; không lấy trung bình tỷ lệ của các tháng. Tổng flights khác quần thể chuyến đến hợp lệ của OTP/donut."),
         bullet("Delay là phút và có thể âm khi đến sớm; null không tự thành 0. Phân vị box lấy từ M2 ở đúng mức, không lấy trung bình phân vị tháng."),
         bullet("2026 chỉ có quý 1; animation là các năm lịch sử. Tuyến chỉ có năm nên không có lọc tháng; Sankey thể hiện top tuyến đang chọn."),
         p("reliability_score là chỉ số nhóm tự định nghĩa 0–100. Màu giúp phân biệt: xanh dương lưu lượng, xanh ngọc đúng giờ, vàng trễ, đỏ hủy/trễ nặng; nhóm có chú giải riêng.", "small"))

    page("15 / Kiểm thử và chụp evidence",
         h("Chạy khi nghiệm thu bản code"),
         code(r".\scripts\test_m5.ps1"),
         p("MongoDB phải đang chạy. Script mount source read-only vào container test dùng một lần, cài requirements-dev và chạy pytest; tests tạo/xóa database ngẫu nhiên aero_m5_test_*, không ghi fixture vào database dashboard."),
         grid(["Nhóm kiểm thử", "Điều cần chứng minh"], [
             ("Input / ingest", "Schema/count/coverage hỏng bị chặn; nạp/verify và unique indexes hoạt động."),
             ("Consistency / retry", "Nạp lại, lỗi giữa chừng, khôi phục publish, bộ cũ/mới và khóa điều phối."),
             ("KPI / UI", "Weighted rollup, null/negative delay, filter guard, dashboard và dữ liệu biểu đồ."),
             ("Streaming writer", "Replay/version guards với fixture; chưa thay thế test M3/M4 thực."),
         ], [.32, .68]),
         note("Kết quả cần thấy", "Không có FAILED. Khi nghiệm thu tích hợp MongoDB, integration tests phải được chạy, không chỉ SKIP. Biên bản bản code đã kiểm thử có 21 passed và một DeprecationWarning từ dependency; số test có thể đổi theo phiên bản code."),
         h("Chụp gì để thành viên khác kiểm tra được?"),
         p("Chụp terminal verify PASS; Tổng quan kèm năm/tháng đang lọc; một trang hãng/tuyến/box; trang Dữ liệu & vận hành. Có thể thêm Compass và unique index. Ghi rõ snapshot, bộ lọc, ngày và phiên bản code."),
         p("Lưu ảnh PNG/JPG trực tiếp trong serving-layer/evidence, ví dụ team_demo_overview.png. Test log ở logs/test_m5.log. Không cần chạy tests lại mỗi lần chỉ mở UI.", "small"))

    page("16 / Xác định vị trí output",
         grid(["Output", "Vị trí mặc định / cách xem"], [
             ("Document KPI/box", "MongoDB database aero_m5; mở Compass hoặc mongosh."),
             ("Metadata", "batch_runs, serving_state, serving_locks; theo dõi bộ nạp và active snapshot."),
             ("Dữ liệu DB trên đĩa Docker", "Volume aero-serving_m5_mongo_data, mount /data/db; không phải thư mục JSONL Windows."),
             ("Dashboard", "http://localhost:8501 trên máy chạy M5."),
             ("Log khởi động/nạp/verify", "serving-layer/logs/start_m5.log, load_m2.log, verify_m5.log."),
             ("Reports", "serving-layer/evidence/load_report.json và verify_report.json."),
             ("Tests / HDFS", "logs/test_m5.log; logs/load_hdfs.log và evidence/hdfs_load_report.json nếu đã chạy."),
             ("Ảnh / CSV từ UI", "Thư mục tải về của trình duyệt; tự chép vào evidence để đóng gói."),
             ("ZIP bàn giao", "serving-layer/evidence/M5_HANDOFF_&lt;ngày_giờ&gt;.zip sau bước tiếp theo."),
             ("Input M2", "Thư mục AeroSnapshot đã chọn. Đây là nguồn để tái nạp, không phải output mới của M5."),
         ], [.31, .69]),
         note("Giữ kết quả đúng lần chạy", "CheckOnly/load cùng ghi load_report.json; các log script có tên cố định cũng được ghi lại. Muốn giữ một lần chạy, chép report hoặc đóng gói trước lần tiếp theo. Logs/evidence/exports không tự theo Git."),
         p("Đọc một file nhanh trong PowerShell:", "small"),
         code(r"Get-Content .\evidence\verify_report.json -Raw -Encoding UTF8"))

    page("17 / Đóng gói và bàn giao",
         h("Chuẩn bị trước khi chạy script"),
         p("Đảm bảo verify thành công và ảnh/CSV/TXT muốn bàn giao nằm trực tiếp trong evidence. ZIP không tự chụp ảnh hoặc xuất dữ liệu MongoDB."),
         code(r""".\scripts\collect_evidence.ps1
Get-ChildItem .\evidence -Filter 'M5_HANDOFF_*.zip' |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1 FullName, Length, LastWriteTime"""),
         h("Script thực hiện"),
         p("Lấy trạng thái Compose → chạy verify lại → tạo thư mục có timestamp → copy logs và doc_guide → copy các file JSON/PNG/JPG/JPEG/TXT/CSV ở cấp gốc evidence → nén ZIP. Các thư mục ZIP cũ không được lồng vào bộ mới."),
         note("Kết quả cần thấy", "Dòng Evidence ZIP: ...M5_HANDOFF_&lt;ngày_giờ&gt;.zip; file tồn tại và có dung lượng. Giải nén thử để xem logs, reports, ảnh và tài liệu. Nếu verify trong script thất bại, chưa coi bộ bàn giao hoàn tất."),
         grid(["Gửi kèm", "Vì sao cần?"], [
             ("Code M5 đúng phiên bản", "Người nhận có app, loader, cấu hình và dependencies để dựng lại."),
             ("Snapshot M2", "Manifest + 20 JSONL để nạp DB mới; có thể gửi bộ M2_HANDOFF đầy đủ."),
             ("ZIP evidence M5", "Chứng minh đã chạy, đối chiếu và demo đúng bộ."),
             ("Ghi chú bàn giao", "Tên code/commit nếu có, snapshot, cổng đã đổi, giới hạn và đường dẫn hướng dẫn."),
         ], [.35, .65]),
         p("ZIP evidence không chứa volume MongoDB, toàn bộ code hoặc toàn bộ snapshot nguồn. Gửi một mình ZIP evidence chưa đủ để máy khác tự chạy.", "small"))

    page("18 / Dừng và chạy lại hôm sau",
         h("Dừng bình thường, giữ dữ liệu"),
         code(r".\scripts\stop_m5.ps1"),
         p("Script gọi compose stop cho M5. Dữ liệu vẫn ở volume MongoDB. Không dùng down -v để dừng thông thường vì tùy chọn đó xóa volume."),
         h("Lần sau trên cùng máy"),
         p("Mở Docker Desktop. Trong terminal mới, khai báo lại đường dẫn ở trang 6 để Set-Location đúng serving-layer, rồi chạy:"),
         code(r""".\scripts\start_m5.ps1
.\scripts\verify_m5.ps1
Start-Process 'http://localhost:8501'"""),
         note("Kết quả cần thấy", "mongo/dashboard healthy, verify vẫn PASS và UI thấy bộ active cũ. Nếu volume vẫn có dữ liệu hợp lệ thì không bắt buộc nạp lại. Máy mới/volume mới phải làm bước load."),
         h("Cập nhật code hoặc nhận snapshot mới"),
         p("Start có --build nên rebuild image sau thay đổi code. Với nguồn mới, kiểm tra contract/coverage rồi CheckOnly, load, verify, làm mới UI và lưu evidence riêng. Giữ nguồn ETL/EDA ổn định trong lúc xuất/đọc Parquet."),
         note("Truy cập của thành viên khác", "localhost luôn là máy đang mở trình duyệt. Gửi link localhost không giúp họ xem máy bạn. Hướng dẫn này giúp họ tự dựng local; triển khai dùng chung cần host/mạng/xác thực phù hợp."),
         p("Không cần gọi spark.stop() trong PowerShell để dừng M5; Spark/HDFS thuộc stack M2 hoặc job nạp Parquet tùy chọn.", "small"))

    page("19 / Xử lý lỗi theo triệu chứng",
         grid(["Triệu chứng", "Hướng xử lý"], [
             ("AeroProject không được nhận diện", "Tên biến cần $. Khai báo lại các biến trong terminal hiện tại."),
             ("Join-Path path null / Test-Path False", "Kiểm tra Get-Location, nơi đặt repo và thư mục snapshot có manifest thật."),
             ("docker không có / daemon lỗi", "Cài hoặc mở Docker Desktop, terminal mới, kiểm tra docker version có Server."),
             (".ps1 bị chặn", "Dùng lệnh Docker tương đương ở trang 22; không cần đổi policy vĩnh viễn."),
             ("Port already allocated", "Đổi .env theo trang 8 rồi start lại; Windows dùng cổng mới."),
             ("Schema/count/coverage sai", "Nhận lại đúng export; không sửa manifest hoặc lạm dụng AllowPartial."),
             ("Another loader is running", "Chờ loader cũ; loader bị kill có lease tối đa 10 phút nếu không được gia hạn."),
             ("UI chưa có bộ mới / tổng khác mẫu", "Xem load/verify, làm mới UI, kiểm tra active snapshot và bộ lọc năm/tháng."),
             ("Compass không thấy DB", "Mongo phải healthy; URI Windows đúng port, load thành công và đúng instance."),
             ("ParserError khi gõ Python/JS", "Chọn đúng nơi nhập lệnh: PowerShell, mongosh hoặc Compass."),
             ("Streaming chờ / HDFS không resolve", "Streaming cần M4; HDFS cần output M2 và mạng. Batch JSONL không cần HDFS."),
         ], [.39, .61]),
         code(r"""docker compose -f compose.yml ps
docker compose -f compose.yml logs --tail 100 mongo dashboard
Get-Content .\logs\load_m2.log -Tail 60"""),
         p("File log chỉ có sau khi chạy script tương ứng. Lệnh Docker trực tiếp ở trang 22 không tự tạo log wrapper. Đọc lỗi cuối của lần chạy hiện tại trước khi chuyển bước.", "small"))

    page("20 / Khi script PowerShell bị chặn",
         p("Nhánh thay thế cho start/check/load/verify; khai báo AeroSnapshot và đứng tại serving-layer trước. Chạy từng khối, giữ dấu backtick cuối dòng. Dừng nếu lệnh báo lỗi."),
         code('''docker compose -f compose.yml config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Compose config failed.' }
docker compose -f compose.yml up -d --build --wait `
  --wait-timeout 180 mongo dashboard
if ($LASTEXITCODE -ne 0) { throw 'M5 startup failed.' }'''),
         code('''docker compose -f compose.yml run --rm --build --no-deps `
  --volume "${AeroSnapshot}:/data/snapshot:ro" `
  loader python -m m5.load_batch --snapshot /data/snapshot --check-only
if ($LASTEXITCODE -ne 0) { throw 'Input check failed.' }
docker compose -f compose.yml run --rm --build `
  --volume "${AeroSnapshot}:/data/snapshot:ro" `
  loader python -m m5.load_batch --snapshot /data/snapshot
if ($LASTEXITCODE -ne 0) { throw 'M5 load failed.' }'''),
         code('''docker compose -f compose.yml run --rm --build `
  loader python -m m5.verify_batch
if ($LASTEXITCODE -ne 0) { throw 'M5 verify failed.' }
Start-Process 'http://localhost:8501' '''.rstrip()),
         p("Ngoặc ${AeroSnapshot} giúp hiểu đúng dấu : của tham số volume. Reports vẫn ghi vào evidence; các lệnh trên không tự lưu logs wrapper. Khi kết thúc demo, dùng docker compose -f compose.yml stop để giữ volume."),
         p("Để test/đóng gói, sau khi đọc script có thể đặt policy cho riêng tiến trình chạy script. Policy do tổ chức quản lý có thể vẫn chặn; khi đó cần môi trường được phép chạy script, không coi thiếu log wrapper là lỗi ingest.", "small"),
         code(r"""powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\test_m5.ps1
if ($LASTEXITCODE -ne 0) { throw 'M5 tests failed.' }
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\collect_evidence.ps1
if ($LASTEXITCODE -ne 0) { throw 'Evidence collection failed.' }"""))

    page("21 / Tùy chọn: nạp từ HDFS",
         note("Điều kiện trước khi chạy", "Máy có batch stack thật và đủ 13 KPI + 7 box trên HDFS. Giữ ETL/EDA dừng trong cả lần nạp. Chỉ copy JSONL, code hoặc cleaned Parquet sang máy khác không tự phục hồi aggregate HDFS.", "amber"),
         code(r"""Set-Location (Join-Path $AeroProject 'batch-layer')
docker compose up -d
docker compose exec namenode hdfs dfs -ls /aero/analytics/eda/kpi
docker compose exec namenode hdfs dfs -ls /aero/analytics/eda/box
Set-Location $AeroServing
.\scripts\load_hdfs.ps1
.\scripts\verify_m5.ps1"""),
         h("Job đọc gì và chạy như thế nào?"),
         p("compose.hdfs.yml nối hdfs-loader vào mạng serving và mạng batch. Dockerfile.spark-loader dùng Spark 3.5.3 + PyMongo. load_parquet.py đọc aggregate KPI/box, stage JSONL tạm rồi gọi cùng writer MongoDB. Không đọc /aero/processed từng chuyến, không cần MongoDB Spark Connector JAR."),
         grid(["Điểm kiểm tra", "Mong đợi"], [
             ("Mạng", "Mặc định batch-layer_default. Nếu đổi project name, đặt M5_BATCH_NETWORK trong .env theo docker network ls."),
             ("Kết quả", "Load/verify PASS. Nếu nội dung schema/giá trị giống JSONL, cùng fingerprint và nhận diện bộ đã có."),
             ("Output riêng", "logs/load_hdfs.log; evidence/hdfs_load_report.json."),
         ], [.27, .73]),
         p("Luồng này chứng minh sơ đồ KPI Parquet HDFS → M5 → MongoDB. Luồng JSONL vẫn đủ để người nhận mở dashboard khi không có HDFS. Không bắt buộc làm cả hai.", "small"))

    page("22 / Streaming: phần cần nối M4",
         note("Trạng thái hiện tại", "Đã có stream_writer.py, contract đề xuất và tests guards. Chưa có bằng chứng tích hợp M3/Kafka/M4 thật, nên chưa nghiệm thu end-to-end streaming hoặc tuyên bố realtime.", "amber"),
         grid(["Bước tích hợp", "M4 và M5 cần làm"], [
             ("1. Chốt record", "Full aggregate window: pipeline_id, source, window_start/end có timezone, dimensions, metrics, revision."),
             ("2. Chốt update semantics", "Revision tăng bền vững qua restart cho cùng khóa. Không gửi delta nếu chưa thiết kế adapter/dedup riêng."),
             ("3. Nối sink", "M4 gọi writer phù hợp từ sink/foreachBatch hoặc bàn giao JSONL đã commit theo contract; kiểm tra output mode và retry."),
             ("4. Chạy dữ liệu thật của luồng", "M3 phát event có source đúng → Kafka → M4 aggregate → MongoDB stream_window_kpi → trang Streaming."),
             ("5. Kiểm thử", "Replay cùng version, version cũ, xung đột cùng version, late update và restart không làm đếm trùng/ghi lùi."),
             ("6. Đo độ mới", "Đối chiếu event time, ingested_at, trigger M4 và nhịp UI; dừng nguồn để quan sát stale."),
         ], [.28, .72]),
         p("UI hiện refresh 10 giây và stale sau 60 giây; cần điều chỉnh và đo khi tích hợp. Replay không được làm ingested_at mới giả. API và simulated phải gắn nguồn chính xác; không ghép BTS với API nếu thiếu khóa đáng tin cậy."),
         p("Đọc serving-layer/contracts/M4_TO_M5.md trước khi sửa m5/stream_writer.py. Fixtures tests không được đưa vào database demo rồi gọi đó là live.", "small"))

    page("23 / Kubernetes: lộ trình triển khai",
         p("Đây là phương án tiếp theo, chưa có manifests hoặc bằng chứng chạy Kubernetes trong repo. Không cần làm bước này để hoàn tất demo batch local hiện tại."),
         base.Diagram("k8s", 462),
         p("Sơ đồ đề xuất dùng lại image từ Dockerfile. Deployment/Service cho dashboard; StatefulSet/Service/PVC cho MongoDB; Job cho loader/verifier; cấu hình qua ConfigMap/Secret theo môi trường."),
         note("Cách chuyển theo từng mốc", "Dựng M5 riêng trên cluster → đưa JSONL vào → load/verify → so UI → tạo lại Pod và kiểm tra persistence → sau đó nối HDFS/M4. Cần xử lý registry, storage, probes, resources và truy cập. Volume/mạng Compose không tự chuyển sang Kubernetes."),
         p("Bắt đầu một replica dashboard và một MongoDB instance; chưa có HA. Scale Streamlit cần session affinity; HDFS cần kết nối được cả NameNode và DataNode. Sơ đồ không xác nhận đã có cloud deployment.", "small"))

    page("24 / Giải thích code từ đầu đến cuối",
         grid(["Nhóm file", "Luồng chạy / vai trò"], [
             ("compose.yml, Dockerfiles", "Định nghĩa môi trường MongoDB, app, loader; ports, network, volume và dependencies."),
             ("scripts/common.ps1", "Tìm Docker, gọi Compose trong đúng thư mục, ghi log và kiểm tra exit code."),
             ("scripts/start/load/verify", "Các lệnh thao tác có thể lặp lại cho thành viên, không cần gõ Python thủ công."),
             ("m5/config.py, mongo.py", "Đọc URI/database từ biến môi trường, tạo PyMongo client và ping."),
             ("m5/load_batch.py, contracts.py", "CLI CheckOnly/load và kiểm tra danh mục 20 bảng, schema, keys, coverage, digests."),
             ("m5/batch_writer.py", "Lease, unique index, bulk upsert, verify và publish active pointer."),
             ("m5/verify_batch.py", "Chọn snapshot active/published, so digest/index, ghi report."),
             ("app.py, queries.py, metrics.py", "Nhận bộ lọc, giữ snapshot_id cho lượt chạy, truy vấn đúng chiều, gộp count/sum."),
             ("charts.py, dashboard.css", "Biểu đồ tương tác và giao diện; không sửa giá trị nguồn để trang trí."),
             ("load_parquet.py / stream_writer.py", "Nhánh nạp aggregate HDFS / nhánh nhận window M4 theo contract."),
             ("tests/ và doc_guide/", "Kiểm tra hành vi, hướng dẫn, demo và biên bản nghiệm thu."),
         ], [.45, .55]),
         note("Thứ tự trình bày gợi ý", "Mở Compose → script load → contracts → writer → MongoDB document/index → queries/metrics → app/charts → report và tests. Giải thích đầu vào/đầu ra mỗi lớp trước khi đọc chi tiết từng hàm."))

    page("25 / Checklist và nguồn tham khảo",
         grid(["Đã đạt?", "Điều kiện hoàn tất luồng batch M5"], [
             ("[  ]", "Code + snapshot thật; đường dẫn đúng, đủ manifest và 20 JSONL."),
             ("[  ]", "Docker có Server; mongo/dashboard healthy; cổng truy cập đúng."),
             ("[  ]", "CheckOnly PASS, load PASS, verify đủ 20 collection PASS."),
             ("[  ]", "Nạp lại cùng bộ không tăng document; bộ mẫu 74.921 document."),
             ("[  ]", "Compass/mongosh xem được active snapshot, tháng mẫu và unique index."),
             ("[  ]", "Dashboard đúng phạm vi, chỉ số/mẫu số/đơn vị; tests nghiệm thu đạt."),
             ("[  ]", "Có ảnh, log/report đúng lần chạy; ZIP evidence + code + snapshot đã bàn giao."),
             ("[  ]", "Stop/start giữ dữ liệu; người nhận biết vị trí output và cách chạy lại."),
             ("[  ]", "Ghi rõ streaming chờ M4 và Kubernetes chưa triển khai."),
         ], [.16, .84]),
         h("Tài liệu đi kèm trong repo"),
         p("HUONG_DAN_CHAY_TU_DAU_DEN_OUTPUT_M5.md: lệnh thực hành và phụ lục đầy đủ.<br/>KICH_BAN_TRINH_BAY_VA_GIAI_THICH_M5.md: lời dẫn demo cho team.<br/>MONGODB_COLLECTIONS_QUERIES.md: collections, indexes và queries.<br/>KET_QUA_KIEM_THU_M5.md: biên bản thực tế của bản code local.<br/>contracts/M4_TO_M5.md: hợp đồng streaming cần xác nhận."),
         h("Tài liệu chính thức để cài đặt / triển khai"),
         p('<link href="https://docs.docker.com/desktop/setup/install/windows-install/" color="#2563eb">Docker Desktop Windows</link> · '
           '<link href="https://learn.microsoft.com/en-us/windows/wsl/install" color="#2563eb">Microsoft WSL</link> · '
           '<link href="https://www.mongodb.com/docs/compass/connect/" color="#2563eb">Compass connection</link><br/>'
           '<link href="https://kubernetes.io/docs/concepts/workloads/" color="#2563eb">Kubernetes Workloads</link> · '
           '<link href="https://kubernetes.io/docs/concepts/storage/persistent-volumes/" color="#2563eb">Persistent Volumes</link> · '
           '<link href="https://docs.streamlit.io/develop/concepts/architecture/architecture" color="#2563eb">Streamlit architecture</link>', "small"),
         p("Tài liệu được đối chiếu với script/contract trong workspace, số liệu manifest và biên bản kiểm thử ngày 07/11/2026. Ảnh dashboard là evidence thực tế; sơ đồ Kubernetes là đề xuất. Việc tạo PDF không chạy lại pipeline hoặc triển khai hạ tầng.", "small"))


def validate():
    doc = fitz.open(PDF)
    assert len(doc) == len(PAGES), (len(doc), len(PAGES))
    assert len(doc.get_toc()) == len(PAGES) - 1
    for number, ((title, _), pdfpage) in enumerate(zip(PAGES, doc), 1):
        text = pdfpage.get_text()
        if number > 1:
            assert title in re.sub(r"\s+", " ", text), (number, title)
        assert "\ufffd" not in text and "\u25a0" not in text, number
        for block in pdfpage.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    x0, y0, x1, y1 = span["bbox"]
                    assert x0 >= 0 and y0 >= 0 and x1 <= W + .5 and y1 <= H + .5, (number, span["text"])
        pdfpage.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False).save(OUT / f"page_{number:02d}.png")
    # TOC links should resolve to real pages, with no missing destination.
    toc_links = doc[1].get_links()
    assert len(toc_links) == 8
    for link, target in zip(toc_links, (3, 8, 12, 15, 19, 21, 23, 26)):
        destination = re.search(r"/Dest\s*\[\s*(\d+)\s+0\s+R", doc.xref_object(link["xref"]))
        assert destination and int(destination.group(1)) == doc[target - 1].xref
    manifest_file = ROOT.parent / "batch-layer/spark_jobs/export/m2_to_m5/20261107T042703414867Z/manifest.json"
    reference = "not present on this machine"
    if manifest_file.exists():
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        assert len(manifest["tables"]) == 20
        assert sum(t["rows"] for t in manifest["tables"]) == 74921
        assert manifest["coverage"]["month_count"] == 51
        assert manifest["coverage"]["total_flights"] == 29328846
        reference = "PASS"
    report = {"result": "PASS", "pages": len(doc), "bookmarks": len(doc.get_toc()),
              "contents_links": len(toc_links), "code_blocks": len(COMMANDS),
              "powershell_blocks": sum(x["language"] == "powershell" for x in COMMANDS),
              "reference_manifest": reference, "bytes": PDF.stat().st_size,
              "checks": ["pagination", "Vietnamese text", "no replacement glyphs", "page boundaries",
                         "all chapter headings", "code width", "contents destinations"],
              "scope": "Documentation only; operational commands were not executed"}
    (ASSETS / "walkthrough_validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "command_blocks.json").write_text(json.dumps(COMMANDS, ensure_ascii=False), encoding="utf-8")
    doc.close()
    print(json.dumps(report, ensure_ascii=False))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    content()
    for title, items in PAGES:
        height = sum(item.wrap(CW, 1000)[1] + item.getSpaceBefore() + item.getSpaceAfter()
                     for item in items)
        if height > 736:
            raise ValueError(f"Section too tall: {title}: {height:.1f}pt")
    doc = base.Document(str(PDF), pagesize=base.A4,
                        title="M5 — Hướng dẫn thực hành từ đầu đến cuối",
                        author="AERO Project Team",
                        subject="Mục đích, thao tác, code, kiểm tra và bàn giao M5")
    doc.addPageTemplates([PageTemplate(id="walkthrough", frames=[Frame(44, 49, CW, 740,
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)], onPage=decorate)])
    story = []
    for i, (_, items) in enumerate(PAGES):
        if i:
            story.append(PageBreak())
        story.extend(items)
    doc.build(story)
    validate()


if __name__ == "__main__":
    main()
