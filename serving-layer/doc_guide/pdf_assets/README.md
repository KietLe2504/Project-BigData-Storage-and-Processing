# Nguồn minh họa và cách xuất lại PDF M5

## Bản tài liệu học tập dạng paper

[M5_TAI_LIEU_HOC_TAP_THEO_TASK.pdf](../M5_TAI_LIEU_HOC_TAP_THEO_TASK.pdf)
là bản trình bày theo yêu cầu paper: A4 một cột, Times New Roman 12 pt,
giãn dòng 18 pt (1,5), căn đều hai lề, lề trái 30 mm và các lề còn lại 25 mm.
Các mục lớn tương ứng 10 task thành phần của M5; không chia cột hoặc dùng bảng/cards.
Nội dung liên tục, không ngắt trang cố định sau mỗi task. Sơ đồ được vẽ vector
đen trắng với Times New Roman, ảnh dashboard giữ nguồn evidence thực tế.

Nguồn nội dung: [TAI_LIEU_HOC_TAP_M5_THEO_TASK.md](../TAI_LIEU_HOC_TAP_M5_THEO_TASK.md).
Nguồn xuất: [build_m5_learning_paper_pdf.py](../../scripts/build_m5_learning_paper_pdf.py).
Dependencies dùng chung requirements.txt bên dưới. Times New Roman lấy từ Windows
Fonts trên máy, nhúng subset vào PDF; không sao chép các file font vào repo.
Có thể đặt `M5_PAPER_FONT_DIR` tới thư mục chứa `times.ttf`, `timesbd.ttf`,
`timesi.ttf` và `timesbi.ttf`. Mã lệnh phụ lục dùng Consolas.

Xuất lại trong PowerShell tại `serving-layer` sau khi cài dependencies biên soạn:

```powershell
.\.venv-pdf\Scripts\python.exe .\scripts\build_m5_learning_paper_pdf.py
```

Preview ở `logs/m5_learning_paper_pdf/`; báo cáo xuất file ở
`pdf_assets/learning_paper_validation.json`. Script không chạy các lệnh vận hành.

## Các bản tổng quan và thực hành trước đó

Tài liệu chính: [M5_TASK_OBJECTIVES_INPUT_OUTPUT_HA_TANG.pdf](../M5_TASK_OBJECTIVES_INPUT_OUTPUT_HA_TANG.pdf),
17 trang, tiếng Việt, dành cho thành viên trong team.

Bản thực hành đầy đủ:
[HUONG_DAN_M5_TU_DAU_DEN_CUOI_CHI_TIET.pdf](../HUONG_DAN_M5_TU_DAU_DEN_CUOI_CHI_TIET.pdf),
27 trang với 25 mục, lệnh thao tác và kết quả kiểm tra. Nguồn dựng là
[build_m5_walkthrough_pdf.py](../../scripts/build_m5_walkthrough_pdf.py), dùng chung
styles/font với script mô tả tổng quan. Xuất lại tại `serving-layer` bằng:

```powershell
.\.venv-pdf\Scripts\python.exe .\scripts\build_m5_walkthrough_pdf.py
```

Dependencies cài theo mục dưới. Preview và danh sách khối lệnh nằm trong
`logs/m5_walkthrough_pdf/`; báo cáo dựng PDF ở `pdf_assets/walkthrough_validation.json`.
Lệnh vận hành trong tài liệu chỉ được xuất thành văn bản, không được script tạo PDF thực thi.

## Nguồn hình

- `so_do_batch.png`: vẽ lại chuỗi BTS/HDFS → M2 → KPI Parquet → M5 → MongoDB → dashboard
  theo hai ảnh sơ đồ batch người dùng gửi trong hội thoại.
- `so_do_team.png`: vẽ lại ảnh phân công M1–M5 do người dùng gửi; đổi bố cục thành hai nhánh
  song song, giữ luồng bàn giao và trách nhiệm.
- `so_do_docker.png`: sơ đồ giải thích cấu hình Compose thực tế của repo.
- `so_do_k8s.png`: kiến trúc Kubernetes đề xuất, chưa phải bằng chứng triển khai.
- `dashboard_thuc_te.png`: bản sao nguyên ảnh `evidence/dashboard_visual_overview.png`
  của lần kiểm thử giao diện 07/11/2026. Không chỉnh sửa số liệu ảnh.

Ảnh gốc đính kèm trong hội thoại không có file trong workspace; PDF ghi rõ hai sơ đồ
đầu là bản vẽ lại, không trình bày chúng như ảnh gốc. Sơ đồ trong PDF dùng vector để
chữ rõ khi zoom; các PNG ở đây là bản xuất thêm để tái sử dụng.

## Sửa nội dung và xuất lại

Nội dung/lập trang: [build_m5_overview_pdf.py](../../scripts/build_m5_overview_pdf.py).
Không cần các thư viện PDF để vận hành dashboard; chúng chỉ phục vụ biên soạn tài liệu.

Ví dụ trong **PowerShell**, tại thư mục `serving-layer`, máy có Python:

```powershell
py -3.12 -m venv .venv-pdf
.\.venv-pdf\Scripts\python.exe -m pip install -r .\doc_guide\pdf_assets\requirements.txt
.\.venv-pdf\Scripts\python.exe .\scripts\build_m5_overview_pdf.py
```

Script dùng DejaVu Sans trên Linux hoặc Arial/Consolas có sẵn trên Windows.
Có thể đặt biến môi trường `M5_PDF_FONT_DIR` tới thư mục chứa `DejaVuSans.ttf`,
`DejaVuSans-Bold.ttf`, `DejaVuSansMono.ttf` để dùng cùng font với bản PDF này.
Nếu đổi font/nội dung làm tràn trang, script sẽ báo lỗi để điều chỉnh trước khi bàn giao.

Script xuất PDF, bốn sơ đồ PNG, `validation.json` và các trang preview tại
`serving-layer/logs/pdf_preview/`. Kiểm tra trực quan các trang sau mỗi lần thay đổi.
Script chỉ đọc đầu vào và ghi tài liệu; không khởi động container, ghi MongoDB hoặc
triển khai Kubernetes. Nếu snapshot mẫu có sẵn, script đối chiếu thêm các số trong
manifest. Không cần truyền snapshot vào để xuất lại khi tài liệu/ảnh đã có đủ.
