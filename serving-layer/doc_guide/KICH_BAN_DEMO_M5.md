# Kịch bản demo và nghiệm thu M5

Checklist này dùng khi nghiệm thu. Để hướng dẫn thành viên mới, dùng
[kịch bản trình bày có lời dẫn](KICH_BAN_TRINH_BAY_VA_GIAI_THICH_M5.md)
và [hướng dẫn cài đặt, chạy từ đầu](HUONG_DAN_CHAY_TU_DAU_DEN_OUTPUT_M5.md).

## Batch đã có thể demo

1. Chạy `scripts/start_m5.ps1`, kiểm tra MongoDB/dashboard healthy.
2. Nạp snapshot M2 bằng `scripts/load_m2.ps1 -SnapshotPath <đường dẫn thật>`.
3. Chạy `scripts/verify_m5.ps1`: 20 bảng PASS, 74.921 document với bộ hiện tại.
4. Mở `http://localhost:8501`; tổng quan toàn kỳ có 29.328.846 chuyến sau
   cleaning. Thử lọc riêng năm 2025 và tháng 1–3.
5. Mở hãng/sân bay/tuyến, đổi bộ lọc và so một hàng với JSONL/CSV tương ứng.
   Trang tuyến chỉ có năm; 2026 chỉ có quý 1.
6. Mở box-plot, đổi arr/dep và all/late; đối chiếu phân vị/râu với bảng M2.
7. Nạp lại cùng snapshot: `ALREADY LOADED`, không tăng document.
8. Dừng/start M5, mở lại dashboard: dữ liệu còn nguyên.
9. Giữ EDA/ETL dừng, bật HDFS, chạy `scripts/load_hdfs.ps1`: đọc aggregate
   Parquet thực tế và kiểm tra fingerprint/giá trị với JSONL nếu cùng lần build.
10. Chụp ảnh bộ lọc/KPI, trang data status, log verify và đóng gói evidence.

## Các test tự động

Trong PowerShell tại `serving-layer`, có thể chạy toàn bộ tests trong container:

```powershell
.\scripts\test_m5.ps1
```

Script mount source chỉ đọc, cài dependency test trong container dùng một lần
và kết nối MongoDB qua mạng serving. Không cần Python Windows. Hoặc dùng
Python 3.12 trên Windows:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:M5_TEST_MONGO_URI = 'mongodb://localhost:27017'
.\.venv\Scripts\python.exe -m pytest -q
```

Integration tests dùng database test riêng và tự xóa, gồm nạp/verify,
idempotency, unique index, tamper detection, lỗi giữa chừng, snapshot cũ/mới,
unsupported filter, Streamlit AppTest và streaming replay/version guards.
Unit tests bao gồm dữ liệu hỏng và weighted rollup/null/negative delay.

## Streaming cần demo sau khi M4 tích hợp

- Đẩy sự kiện qua M3/Kafka/M4, quan sát aggregate trong MongoDB và UI.
- Chứng minh nguồn `aviationstack` hoặc `simulated` được gắn nhãn đúng.
- Replay cùng payload/version không tăng đếm hoặc cập nhật thời gian giả.
- Late update có revision mới cập nhật đúng cửa sổ.
- Update cũ không ghi đè giá trị mới; restart không làm version quay lui.
- Dừng nguồn, quan sát trạng thái stale và kiểm tra refresh interval thực tế.

Test writer bằng fixture không thay cho demo M3 → M4 thật. Kubernetes/Cloud
là mốc triển khai riêng cần môi trường đã chốt và bằng chứng chạy thực tế.
