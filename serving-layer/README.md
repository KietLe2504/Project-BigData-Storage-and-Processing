# AERO M5 — MongoDB & Dashboard

**Hướng dẫn chính để cài đặt và chạy từ đầu:**
[HUONG_DAN_CHAY_TU_DAU_DEN_OUTPUT_M5.md](doc_guide/HUONG_DAN_CHAY_TU_DAU_DEN_OUTPUT_M5.md).
Bao gồm nhận dữ liệu M2, Docker, nạp/kiểm tra MongoDB, bảng hãng–tuyến,
mở dashboard, xử lý lỗi và bàn giao.

**Tài liệu học tập theo từng task lớn:**
[TAI_LIEU_HOC_TAP_M5_THEO_TASK.md](doc_guide/TAI_LIEU_HOC_TAP_M5_THEO_TASK.md).
Nội dung trình bày lý thuyết, cách thực hiện và kết quả cần đạt của M5.
Bản PDF task đã có trên repo: [TaskM5.pdf](doc_guide/TaskM5.pdf).

M5 nạp 13 bảng KPI và 7 bảng box của M2 vào MongoDB, kiểm tra toàn bộ giá trị,
rồi phục vụ dashboard Streamlit. Hỗ trợ cả JSONL export và đọc trực tiếp KPI
Parquet trên HDFS. Writer streaming có contract đề xuất; cần M4 tích hợp và
kiểm thử end-to-end trước khi nghiệm thu streaming.

**Cài đặt và chạy từ đầu trên máy thành viên khác:**
[HUONG_DAN_CHAY_TU_DAU_DEN_OUTPUT_M5.md](doc_guide/HUONG_DAN_CHAY_TU_DAU_DEN_OUTPUT_M5.md).
Tài liệu có bước nhận dữ liệu ngoài Git, cài Docker, nạp/kiểm tra MongoDB,
thao tác dashboard, vị trí output và đóng gói bàn giao.

**Trình bày cho team:**
[Kịch bản giải thích và demo M5](doc_guide/KICH_BAN_TRINH_BAY_VA_GIAI_THICH_M5.md).
Tra cứu lệnh ngắn tại [HUONG_DAN_CHAY_M5.md](doc_guide/HUONG_DAN_CHAY_M5.md).

Các script `scripts/build_m5_*` phục vụ biên soạn PDF/PowerPoint, không cần
chạy để vận hành dashboard. File trình bày xuất ra, ảnh evidence và template
PowerPoint gốc được bàn giao riêng khi cần; không nằm trong bộ code vận hành.

Chạy trong **PowerShell Windows**, Docker Desktop đang hoạt động:

```powershell
Set-Location F:\Project-BigData-Storage-and-Processing\serving-layer
.\scripts\start_m5.ps1
.\scripts\load_m2.ps1 -SnapshotPath '..\batch-layer\spark_jobs\export\m2_to_m5\20261107T042703414867Z'
.\scripts\verify_m5.ps1
Start-Process 'http://localhost:8501'
```

Nếu PowerShell chặn script `.ps1`, dùng các lệnh Docker Compose tương đương
trong hướng dẫn; không dán Python notebook vào PowerShell.

Kỳ vọng với bộ M2 hiện tại: **20 collections, 74.921 document dữ liệu** cho một
snapshot, **51 tháng**, tổng KPI tháng **29.328.846 chuyến sau cleaning**.
Collections metadata được tính riêng. Nạp lại cùng dữ liệu không làm tăng
document; run lỗi không thay snapshot đang phục vụ.

```text
M2 HDFS aggregate Parquet → JSONL + manifest ─┐
M2 HDFS aggregate Parquet → M5 Spark adapter ├→ validate → MongoDB → dashboard
M4 full window aggregates → versioned writer┘                    (chờ tích hợp M4)
```

- Dashboard: http://localhost:8501.
- MongoDB từ Windows: `mongodb://localhost:27017`, database `aero_m5`.
- MongoDB giữa các container serving: `mongodb://mongo:27017`.
- Mặc định dành cho local: MongoDB/dashboard chỉ publish cổng trên loopback.
  Triển khai lên máy dùng chung/cloud cần cấu hình xác thực và mạng phù hợp.
- `scripts/stop_m5.ps1` dừng riêng M5, giữ volume MongoDB.
- Logs: `logs/`; báo cáo đối chiếu: `evidence/`.

Các trang: tổng quan, thời gian/mùa vụ, hãng, sân bay xuất phát, tuyến theo
năm, danh mục hãng bay/sân bay, box-plot, trạng thái streaming và dữ liệu/vận hành. Filter chỉ được bật
cho các chiều thật sự có trong bảng. KPI lịch sử không được gắn nhãn live.

Giao diện có area/cột lưu lượng, donut cơ cấu chuyến đến, cột chồng 100%,
heatmap ngày lịch, đồng hồ polar 24 giờ, bubble chart, treemap thị phần,
bản đồ mạng đường bay, Sankey luồng tuyến và box-plot nhiều màu. Tab bản đồ
cho đổi màu theo trễ/hủy, xem lưu lượng qua độ dày đường và quy mô sân bay
qua kích thước điểm; có bộ lọc một sân bay, toàn mạng/Top và góc nhìn 3D.
Trang hãng/sân bay có tab
**▶ Diễn biến theo năm** với nút Phát/Dừng. Trục giữ cố định và chỉ chạy các
nhóm được quan sát qua mọi năm của animation, không điền số 0 cho nhóm thiếu.
2026 chỉ có quý 1, cần chọn cùng kỳ khi so sánh.

Màu KPI thống nhất: xanh dương = lưu lượng, xanh ngọc = đúng giờ, vàng = trễ,
đỏ = hủy/trễ nặng. Biểu đồ phân nhóm có chú giải riêng. Hover để xem số liệu,
click chú giải để ẩn/hiện chuỗi, kéo để zoom; nút camera trên biểu đồ xuất PNG.

Tài liệu:

- [Bản đồ mạng bay: cách đọc, bộ lọc và nguồn tọa độ](doc_guide/BAN_DO_MANG_BAY.md)
- [Danh mục hãng bay và sân bay: tra cứu hồ sơ, vị trí và thống kê](doc_guide/DANH_MUC_HANG_BAY_SAN_BAY.md)
- [Bản đồ kết nối sân bay: bấm điểm, bấm tuyến và xem phân bố hãng](doc_guide/BAN_DO_KET_NOI_SAN_BAY.md)
- [Collections, indexes và queries](doc_guide/MONGODB_COLLECTIONS_QUERIES.md)
- [Demo và nghiệm thu](doc_guide/KICH_BAN_DEMO_M5.md)
- [Kết quả kiểm thử thực tế](doc_guide/KET_QUA_KIEM_THU_M5.md)
- [Contract đề xuất M4 → M5](contracts/M4_TO_M5.md)
- [Kế hoạch và phạm vi](doc_guide/KE_HOACH_IMPLEMENT_M5.md)

Kiểm thử ngay bằng Docker, không cần cài Python Windows:

```powershell
.\scripts\test_m5.ps1
```

Hoặc kiểm thử phát triển dùng Python 3.12 và MongoDB test riêng:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:M5_TEST_MONGO_URI = 'mongodb://localhost:27017'
.\.venv\Scripts\python.exe -m pytest -q
```

Tests tạo/xóa database tên ngẫu nhiên `aero_m5_test_*`, không dùng database
phục vụ. Khi không đặt `M5_TEST_MONGO_URI`, các integration tests được đánh
dấu SKIP; unit tests vẫn chạy. Không ghi fixture mô phỏng vào database demo.
