# Kịch bản trình bày, giải thích code và thao tác M5 cho team

Mục tiêu: sau buổi trình bày, thành viên hiểu M5 nhận gì, làm gì, dữ liệu ở
đâu và tự chạy được trên máy khác. Dùng
[hướng dẫn từ đầu đến output M5](HUONG_DAN_CHAY_TU_DAU_DEN_OUTPUT_M5.md)
để thực hành; tài liệu này là lời dẫn và thứ tự demo khoảng 12–15 phút,
không tính thời gian cài Docker/tải images lần đầu.

## 1. Chuẩn bị trước buổi demo

- Gửi code M5 và snapshot M2 thật; chỉ gửi link code không có dữ liệu export.
- Chạy thử start, load, verify theo hướng dẫn đầy đủ. Build images trước
  để buổi trình bày không phải chờ tải dependencies.
- Mở sẵn PowerShell ở `serving-layer`, VS Code, trình duyệt dashboard và
  Compass nếu muốn dùng. Kiểm tra chưa có ETL/EDA đang ghi lại bảng HDFS
  nếu định demo nhánh HDFS.
- Ghi lại tên snapshot, phiên bản code và ngày demo. Chuẩn bị ảnh kết quả
  thực tế để giải thích khi máy demo gặp vấn đề kết nối.

Trên máy đã nạp dữ liệu, thao tác load lại sẽ hiện `ALREADY LOADED`; đó là
kết quả đúng. Không xóa database/volume chỉ để tạo hiệu ứng “lần đầu”.

## 2. Phút 0–2: M5 nằm ở đâu trong dự án?

**Hiển thị sơ đồ và nói:**

> M2 dùng Spark để làm sạch và tính thống kê chuyến bay. Phần M5 của mình
> nhận các bảng thống kê đó, nạp vào MongoDB và làm dashboard để team truy
> vấn, lọc và so sánh. M5 không chạy lại toàn bộ việc làm sạch dữ liệu M2.

```text
BTS → HDFS → M2 Spark → KPI/box Parquet → JSONL + manifest
                                                  ↓
                                    M5 kiểm tra và nạp
                                                  ↓
                                              MongoDB
                                                  ↓
                                     Dashboard trên trình duyệt
```

> Bộ đang demo có 13 bảng KPI và 7 bảng phân phối, 51 tháng từ đầu 2022
> đến hết tháng 3/2026. MongoDB nhận 74.921 document tổng hợp. Tổng số
> chuyến được các KPI mô tả là 29.328.846, không phải số document MongoDB.

Nếu cần trình bày nhánh đọc trực tiếp Parquet, nói thêm: M5 có adapter Spark
đọc 20 bảng aggregate trên HDFS rồi dùng cùng writer; hướng dẫn mục 12 có
các lệnh. Demo JSONL thuận tiện cho thành viên nhận dữ liệu trên máy riêng.

## 3. Phút 2–4: Cài gì và khởi động như thế nào?

**Mở `compose.yml`, chỉ ba services và volume. Nói:**

> Máy chạy cần Docker Desktop. Compose dựng MongoDB server và dashboard;
> loader là chương trình chạy một lần mỗi khi nạp. Python và thư viện được
> cài trong image. Compass là giao diện xem database, có thể cài thêm.
> Dữ liệu MongoDB nằm trong volume để dừng container rồi mở lại vẫn còn.

**PowerShell**, dùng đường dẫn thật trên máy trình bày:

```powershell
$AeroProject = 'F:\Project-BigData-Storage-and-Processing'
$AeroServing = Join-Path $AeroProject 'serving-layer'
$AeroSnapshot = Join-Path $AeroProject 'batch-layer\spark_jobs\export\m2_to_m5\20261107T042703414867Z'
Set-Location $AeroServing
.\scripts\start_m5.ps1
docker compose -f compose.yml ps
```

Chỉ trạng thái healthy của mongo/dashboard, cổng 27017/8501. Nhắc thành
viên có ổ/path khác sửa biến đầu và thư mục snapshot; hướng dẫn đầy đủ có
cách dùng `data` trong bộ M2_HANDOFF và cách xử lý script bị chặn.

## 4. Phút 4–6: Nạp và chứng minh dữ liệu đúng

**Mở thư mục snapshot và `manifest.json`. Nói:**

> Manifest mô tả bảng, khóa, schema, số dòng và coverage. M5 đọc và kiểm
> tra cả các JSONL thật, không chỉ tin số ghi trong manifest. Mỗi document
> có snapshot_id; unique index đi kèm khóa nghiệp vụ ngăn bản ghi trùng.

**PowerShell**, chạy từng lệnh, chờ kết thúc:

```powershell
.\scripts\load_m2.ps1 -SnapshotPath $AeroSnapshot -CheckOnly
.\scripts\load_m2.ps1 -SnapshotPath $AeroSnapshot
.\scripts\verify_m5.ps1
```

Chỉ `PASS` và `ALL 20 COLLECTIONS CHECKED: PASS; 74921 documents`.
Máy đã load sẽ có `ALREADY LOADED` thay vì `LOAD COMPLETE`.

> CheckOnly chưa ghi database. Khi nạp thật, writer upsert và đối chiếu
> giá trị trước khi công bố bộ dữ liệu. Dashboard dùng snapshot đã công
> bố; lần nạp lỗi không thay bộ đang phục vụ. Verify kiểm tra dữ liệu
> chuyển sang MongoDB so với nguồn đã ghi nhận lúc ingest, không chứng
> minh lại toàn bộ công thức Spark.

Nếu cần chứng minh idempotency, chạy lại lệnh load và verify, chỉ số lượng
document không tăng. Không bắt buộc demo lần nạp thứ ba nếu đã thấy
`ALREADY LOADED` và verify đúng trong lần vừa chạy.

## 5. Phút 6–8: Mở MongoDB để team thấy document

**Thao tác Compass:** kết nối `mongodb://localhost:27017` → `aero_m5` →
`serving_state`, lấy `snapshot_id` của `_id: historical`. Mở
`kpi_month_overall`, lọc bằng snapshot đó, năm 2025/tháng 1. Mở tab Indexes
để chỉ unique index. Nếu chưa cài Compass, dùng mongosh theo mục 7.3 của
hướng dẫn đầy đủ; JavaScript chỉ dán sau khi đã vào mongosh.

**Nói:**

> Đây là một document thống kê tháng. Các trường flights, on_time, arr_n
> là số đếm; tỷ lệ là số 0–1. Khóa tháng gồm snapshot_id, year, month.
> Có thêm metadata phục vụ quản lý các lần nạp; không cộng những document
> đó vào con số 74.921 document dữ liệu của bộ này.

Chỉ thêm một collection `kpi_year_route` hoặc `box_year_carrier` để minh
họa grain khác: năm + sân bay đi/đến, hoặc năm + hãng + loại delay + quần thể.

## 6. Phút 8–11: Dashboard trả lời câu hỏi gì?

**Mở `http://localhost:8501`**, làm mới nếu cần. Chọn năm/tháng trước khi đọc
số và nói rõ phạm vi đang xem.

| Câu hỏi | Trang và thao tác | Điều cần nói |
|---|---|---|
| Toàn kỳ có bao nhiêu chuyến, đúng giờ ra sao? | Tổng quan, chọn toàn kỳ; xem KPI và donut | Tổng flights khác quần thể đến hợp lệ của OTP |
| Trễ biến động theo thời gian thế nào? | Thời gian, xem xu hướng và heatmap | Mức gộp phụ thuộc bảng nguồn |
| Hãng nào nhiều chuyến hoặc trễ cao? | Hãng bay, chọn chỉ số/ngưỡng; xem bubble/treemap | So cùng kỳ và tránh kết luận từ mẫu quá nhỏ |
| Luồng tuyến nào nổi bật? | Tuyến bay, chọn năm/top N, xem Sankey | Chỉ các top tuyến đang chọn, không phải toàn bộ mạng |
| Delay có phân phối ra sao? | Phân phối, chọn arr/dep, all/late | Box dùng phân vị M2, không dựng chuyến bay giả |
| Bộ nào đang được hiển thị? | Dữ liệu & vận hành | Snapshot, coverage và số dòng để truy vết |

Chỉ vài tương tác: hover, bật/tắt chú giải, zoom, camera PNG, tải CSV.
Có thể mở tab animation theo năm ở trang hãng/sân bay:

> Nút Phát thể hiện lịch sử qua các năm, không phải live. Năm 2026 mới có
> quý 1 nên khi đánh giá tăng/giảm cần so cùng kỳ. Tỷ lệ gộp được tính từ
> tổng count/sum; không lấy trung bình tỷ lệ của các tháng. Delay âm có
> thể là đến sớm, còn null không có nghĩa là 0.

## 7. Phút 11–13: Giải thích đường đi trong code

Mở lần lượt các file, chỉ hàm/khối chính; không đọc toàn bộ từng dòng:

| Thứ tự | File | Một câu giải thích |
|---|---|---|
| 1 | `scripts/load_m2.ps1` | Nhận đường dẫn Windows và chạy loader trong Docker |
| 2 | `m5/load_batch.py`, `m5/contracts.py` | Điểm vào chương trình và kiểm tra hợp đồng 20 bảng |
| 3 | `m5/batch_writer.py` | Upsert, quản lý snapshot, kiểm tra rồi publish |
| 4 | `m5/verify_batch.py` | Đọc MongoDB, đối chiếu giá trị và unique indexes |
| 5 | `app.py`, `m5/queries.py`, `m5/metrics.py` | Nhận bộ lọc, truy vấn active snapshot, tính KPI hiển thị |
| 6 | `m5/charts.py`, `assets/dashboard.css` | Vẽ biểu đồ tương tác và định dạng giao diện |

> M5 tách phần kiểm tra/nạp khỏi phần dashboard. Thay giao diện không cần
> viết lại dữ liệu nguồn. Khi sửa công thức KPI phải đối chiếu hợp đồng
> M2 và cách gộp trong metrics; khi sửa khóa/schema phải cập nhật contract
> và kiểm thử liên quan.

## 8. Phút 13–15: Output, bàn giao và giới hạn

**Mở `logs`, `evidence` rồi nói:**

> Kết quả chính là document trong MongoDB và dashboard. Evidence có JSON
> báo cáo, ảnh và logs. Mình gửi code, snapshot M2 và ZIP evidence để máy
> khác dựng lại. ZIP evidence không phải bản sao MongoDB và không chứa
> toàn bộ code/dữ liệu nguồn.

Lưu ảnh thực tế vào `evidence`, rồi **PowerShell**:

```powershell
.\scripts\collect_evidence.ps1
```

Chỉ đường dẫn `Evidence ZIP: ...`. Kết thúc demo có thể dừng M5:

```powershell
.\scripts\stop_m5.ps1
```

> Dừng bằng script giữ volume; lần sau start lại vẫn có dữ liệu. Với máy
> mới cần nạp snapshot. Phần streaming đã có writer và trang trạng thái,
> còn cần M4 tích hợp theo contract và bằng chứng chạy end-to-end. Phạm
> vi nghiệm thu hôm nay là dữ liệu lịch sử M2 → MongoDB → dashboard.

## 9. Câu hỏi team dễ hỏi

| Câu hỏi | Trả lời |
|---|---|
| Có cần tải MongoDB về Windows không? | Server đã được Docker chạy. Compass cài thêm nếu muốn xem bằng GUI. |
| Có cần chạy lại notebook M2 không? | Không, nếu đã nhận snapshot JSONL hoàn chỉnh. |
| Nhận code xong vì sao chưa có dữ liệu? | Exports không nằm trong Git; cần nhận snapshot ngoài code rồi nạp. |
| Tại sao không lưu 29 triệu document? | Dashboard này dùng KPI tổng hợp M2; mỗi document là một nhóm thống kê. |
| Vì sao chọn JSONL thay CSV? | JSONL giữ kiểu số, boolean và null để kiểm tra/nạp đúng schema. |
| Nạp lại có trùng không? | Cùng snapshot được nhận diện; unique key/upsert và verify ngăn tăng bản ghi. |
| Tại sao tổng collections/document lớn hơn ví dụ? | Có metadata hoặc nhiều snapshot; đối chiếu theo active snapshot. |
| Gửi link localhost để người khác xem được không? | Localhost là máy họ; cần họ tự dựng hoặc triển khai máy dùng chung riêng. |
| Animation có phải dữ liệu realtime không? | Là các khung dữ liệu lịch sử theo năm. Streaming cần luồng M4 riêng. |
| HDFS có bắt buộc chạy khi mở dashboard không? | Không với dữ liệu đã nạp MongoDB. Chỉ cần khi dùng adapter nạp trực tiếp HDFS. |
| PASS có nghĩa KPI chắc chắn đúng từ raw không? | PASS chứng minh chuyển dữ liệu/index đúng theo nguồn ingest; công thức M2 cần kiểm chứng ở M2. |
| File nộp/bàn giao ở đâu? | `serving-layer/evidence/M5_HANDOFF_<ngày_giờ>.zip`, gửi kèm code và snapshot M2. |

## 10. Bài thực hành để xác nhận thành viên đã hiểu

Cho thành viên tự thực hiện trên máy mình hoặc terminal mới: sửa đường dẫn,
kiểm tra manifest, start, load, verify, lọc tháng 1/2025, tìm cùng document
trong MongoDB, tải CSV/ảnh và chỉ đúng vị trí evidence. Yêu cầu giải thích
vì sao 51 document KPI tháng mô tả hàng triệu chuyến và vì sao không lấy
trung bình các tỷ lệ tháng. Dùng checklist mục 15 của hướng dẫn đầy đủ để
ghi nhận việc bàn giao, không chỉ xác nhận đã xem demo.
