# Kết quả kiểm thử M5 — 07/11/2026

## Môi trường và phạm vi

Đã build/chạy trên Docker Desktop Windows bằng chính script PowerShell của
repo. MongoDB `8.0.16`, Python `3.12.12`, PyMongo `4.10.1`, Streamlit `1.50.0`.
Adapter HDFS dùng Spark `3.5.3`. Dependency Python được ghim trong requirements
và constraints. Đây là kiểm thử local, không phải bằng chứng deploy Cloud/K8s.

## Kết quả đã thực hiện

| Kiểm tra | Kết quả |
|---|---|
| Compose config cơ bản và HDFS override | PASS |
| Windows PowerShell parse và thực thi start/load/verify/HDFS/test | PASS |
| Build image dashboard và adapter Spark | PASS |
| MongoDB và dashboard healthcheck | Healthy |
| Nạp snapshot M2 `20261107T042703414867Z` | PASS: 20 collection, 74.921 document dữ liệu |
| Phạm vi và tổng KPI tháng | 51 tháng; 29.328.846 chuyến sau cleaning |
| Verifier toàn bộ document/digests và unique indexes | PASS |
| Đọc trực tiếp 20 bảng KPI/box Parquet từ HDFS | PASS |
| So sánh JSONL và HDFS Parquet | Cùng fingerprint schema/giá trị; không tạo snapshot hoặc document trùng |
| Kiểm thử tự động trong container dùng một lần | 21 passed; 1 DeprecationWarning từ dependency Streamlit/NumPy |
| Streamlit AppTest với dữ liệu M2 thực | Tổng quan đúng tổng chuyến; cả 8 trang không có exception |
| Trình duyệt Edge headless | Render được tổng quan và số KPI thực, đã chụp ảnh |
| Stop/start M5 và kiểm tra lại bằng container dashboard | PASS: giữ nguyên snapshot active và 74.921 document |

Fingerprint bộ hiện tại:

```text
633c62bfc5a82bc281d510787a6f7e551bd56a7d1d4813c261696f859956bdfd
```

21 tests bao gồm schema/count/coverage hỏng, trùng khóa, weighted rollup,
null/negative delay, idempotency, tamper detection, nạp lỗi giữa chừng,
recovery ở ranh giới công bố snapshot, không rollback khi nạp lại bộ cũ,
nhóm bị loại khỏi snapshot mới, lock/filter guards và streaming replay/version
conflicts. UI test đi qua các góc nhìn thời gian, ranking, tuyến và 7 mức box.
Năm test biểu đồ mới kiểm tra quần thể donut không chồng lấn, tổng treemap,
hai phía đi/đến trong Sankey, trục animation cố định và không sinh giá trị 0
cho nhóm thiếu quan sát.

Giao diện nâng cấp đã được kiểm tra bằng Edge với MongoDB phục vụ thực tế:
donut dùng 28.732.020 chuyến đến hợp lệ, animation hãng có 5 frame năm, Sankey
render được các tuyến thực. Bố cục rộng 390px không tràn ngang. Ảnh mới:
`dashboard_visual_overview.png`, `dashboard_visual_animation.png`,
`dashboard_visual_routes.png`, `dashboard_visual_mobile.png`; báo cáo
`evidence/visual_acceptance.json`.

Các integration tests chỉ tạo/xóa database tên ngẫu nhiên `aero_m5_test_*`.
Không dùng fixture mô phỏng trong database dashboard phục vụ.

## Evidence sinh khi chạy

Các file vận hành nằm trong thư mục ignored, được tạo lại bằng script:

```text
serving-layer/evidence/load_report.json
serving-layer/evidence/verify_report.json
serving-layer/evidence/hdfs_load_report.json
serving-layer/evidence/dashboard_acceptance.json
serving-layer/evidence/browser_acceptance.json
serving-layer/evidence/dashboard.png
serving-layer/logs/test_m5.log
serving-layer/logs/load_m2.log
serving-layer/logs/verify_m5.log
serving-layer/logs/load_hdfs.log
```

Kiểm tra lại bằng `scripts/test_m5.ps1` và `scripts/verify_m5.ps1`.
Chạy `scripts/collect_evidence.ps1` để gom reports, ảnh, log và tài liệu.

## Phần chưa nghiệm thu

- Writer streaming đã có kiểm thử với contract đề xuất; chưa có code/output
  M4 để xác nhận M3 → Kafka → M4 → MongoDB → dashboard hoạt động thật.
- Chưa triển khai Cloud/Kubernetes; cần môi trường và phương án của nhóm.
- Kiểm tra phục vụ chứng minh việc chuyển/lưu/query đúng output M2, không
  thay cho kiểm chứng độc lập mọi công thức Spark hay đếm lại CSV raw.
