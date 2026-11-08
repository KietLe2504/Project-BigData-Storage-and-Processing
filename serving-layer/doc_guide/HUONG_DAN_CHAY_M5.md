# Chạy M5 từ output M2 đến MongoDB và Dashboard

Đây là hướng dẫn tra cứu ngắn. Nếu cài trên máy mới hoặc hướng dẫn thành
viên khác, đọc [hướng dẫn từ đầu đến output M5](HUONG_DAN_CHAY_TU_DAU_DEN_OUTPUT_M5.md)
và [tài liệu mô tả task M5](TaskM5.pdf).

## 1. Chỗ chạy lệnh và đầu vào

**Tất cả khối `powershell` trong tài liệu chạy tại PowerShell Windows.** Không
cần mở notebook, không chạy `spark.stop()` hoặc Python vào dấu nhắc `PS`.
Các script gọi Docker/container giúp bạn và dừng khi exit code thất bại.

Chuẩn bị Docker Desktop đang chạy và bộ export M2 đã hoàn tất. Dữ liệu dùng
trong ví dụ:

```text
F:\Project-BigData-Storage-and-Processing\batch-layer\spark_jobs\export\m2_to_m5\20261107T042703414867Z
```

Nếu dùng bộ khác, thay tên thư mục thời gian bằng tên thực tế. Có thể dùng
thư mục `data` trong bộ `M2_HANDOFF_*`, miễn chứa manifest và 20 JSONL.

```powershell
Set-Location F:\Project-BigData-Storage-and-Processing\serving-layer
docker version
docker compose version
Test-Path '..\batch-layer\spark_jobs\export\m2_to_m5\20261107T042703414867Z\manifest.json'
```

`docker version` phải đọc được Server, `Test-Path` phải trả `True`.
Không cần chạy lại ETL/EDA để dùng bộ JSONL đã xuất.

## 2. Khởi động M5

```powershell
.\scripts\start_m5.ps1
```

Lần đầu Docker tải MongoDB, build image Python và cài dependencies. Chờ script
kết thúc. `mongo` và `dashboard` cần healthy; dashboard mở tại
`http://localhost:8501`. Trước khi nạp, trang tổng quan hiện chưa có snapshot.

Nếu PowerShell báo không cho chạy script, chạy các lệnh tương đương:

```powershell
docker compose -f compose.yml config --quiet
docker compose -f compose.yml up -d --build --wait --wait-timeout 180 mongo dashboard
docker compose -f compose.yml ps
```

Không cần đổi Execution Policy vĩnh viễn. Nếu cổng 27017/8501 đã được dùng,
copy `.env.example` thành `.env`, đổi `M5_MONGO_PORT`/`M5_DASHBOARD_PORT`, rồi
chạy start lại. Xem cổng thật bằng `docker compose ps`; URI trong container
vẫn dùng `mongo:27017`.

## 3. Kiểm tra đầu vào và nạp M2

Có thể kiểm tra file trước khi nạp:

```powershell
.\scripts\load_m2.ps1 -SnapshotPath '..\batch-layer\spark_jobs\export\m2_to_m5\20261107T042703414867Z' -CheckOnly
```

Kiểm tra đọc đủ JSONL, schema/kiểu dữ liệu, khóa trùng, coverage, tổng flights
và fingerprint; chế độ CheckOnly không ghi MongoDB. Sau đó nạp:

```powershell
.\scripts\load_m2.ps1 -SnapshotPath '..\batch-layer\spark_jobs\export\m2_to_m5\20261107T042703414867Z'
```

Lệnh Docker tương đương, nếu dùng bộ export gốc được mount sẵn:

```powershell
docker compose -f compose.yml run --rm --build loader python -m m5.load_batch --snapshot /data/m2/20261107T042703414867Z
if ($LASTEXITCODE -ne 0) { throw 'M5 load failed. Read the error before continuing.' }
```

Mỗi bảng in `LOADED ...`. Với snapshot hiện tại, phần cuối cần:

```text
LOAD COMPLETE: <snapshot_id>; 74921 documents; PASS
```

Nạp lại cùng nội dung sẽ in `ALREADY LOADED`, kiểm tra lại giá trị và giữ
snapshot active hiện tại. Điều này tránh vô tình quay về bộ cũ khi nạp lại
file cũ. Metadata được tính riêng, nên tổng toàn database lớn hơn 74.921.

`--allow-partial` / `-AllowPartial` chỉ dành cho thử nghiệm có ghi rõ phạm vi;
mặc định bộ nghiệm thu phải đủ 51 tháng 2022-01..2026-03.

## 4. Xác minh MongoDB

```powershell
.\scripts\verify_m5.ps1
```

Hoặc:

```powershell
docker compose -f compose.yml run --rm --build loader python -m m5.verify_batch
if ($LASTEXITCODE -ne 0) { throw 'M5 verify failed.' }
```

Kết quả cần là `ALL 20 COLLECTIONS CHECKED: PASS; 74921 documents` với bộ hiện
tại. Verifier đối chiếu digest của toàn bộ giá trị theo khóa với nguồn đã
kiểm tra ở lúc ingest, đồng thời kiểm tra unique indexes. Báo cáo:

```text
serving-layer\evidence\load_report.json
serving-layer\evidence\verify_report.json
serving-layer\logs\load_m2.log
serving-layer\logs\verify_m5.log
```

Điều kiện này xác nhận việc chuyển dữ liệu sang MongoDB; không thay thế kiểm
chứng mọi công thức Spark hoặc đếm độc lập CSV raw.

## 5. Mở dashboard

```powershell
Start-Process 'http://localhost:8501'
```

Nhấn **Làm mới dữ liệu** nếu trang đã mở trước khi ingest. Các trang gồm:

| Trang | Thao tác và lưu ý |
|---|---|
| Tổng quan | Chọn năm/tháng; xem số chuyến, OTP, delay, hủy và xu hướng |
| Thời gian & mùa vụ | Ngày theo kỳ hoặc các bảng mùa vụ/giờ đã gộp toàn kỳ |
| Hãng bay | Chọn kỳ/hãng, ngưỡng số chuyến, chỉ số xếp hạng |
| Sân bay xuất phát | Chọn kỳ/origin; không gọi là tổng đến + đi |
| Tuyến bay | Chọn năm, origin/dest; bộ hiện tại chưa có KPI tuyến theo tháng |
| Phân phối delay | Chọn mức, kỳ, arr/dep, all/late; mỗi nhóm là một box |
| Streaming | Chưa có M4 thì hiện trạng thái chờ, không tự tạo dữ liệu live |
| Dữ liệu & vận hành | Kiểm tra active snapshot, coverage, số dòng và thời điểm kiểm tra |

Mỗi bảng có nút tải CSV của dữ liệu đang xem. Tỷ lệ lưu 0–1; delay tính bằng
phút và có thể âm. Khi gộp, ứng dụng tính lại từ tổng số đếm. Năm 2026 chỉ có
quý 1. Không lấy trung bình phân vị để gộp box-plot qua nhiều tháng.

Các góc nhìn tương tác bổ sung:

- **Tổng quan:** đổi Diện tích/Cột, xem donut chuyến đến và cột chồng theo
  mức trễ. Donut/cột chồng dùng quần thể chuyến đến hợp lệ, không trộn hủy
  hoặc chuyển hướng vào cùng mẫu số.
- **Thời gian:** heatmap ngày lịch, mùa vụ và đồng hồ polar 24 giờ. Màu biểu
  thị mức trễ; các bảng gộp toàn kỳ không nhận thêm bộ lọc năm.
- **Hãng/sân bay:** chuyển các tab xếp hạng, bong bóng, treemap và
  **▶ Diễn biến theo năm**. Nút Phát chạy dữ liệu lịch sử qua các năm; không
  phải cập nhật live. Animation chỉ dùng nhóm có dữ liệu ở mọi năm hiển thị.
- **Tuyến:** Sankey cho thấy luồng sân bay đi → đến. Độ rộng theo số chuyến
  của top tuyến đang chọn, không phải toàn bộ mạng bay. Hai tab khác so sánh
  lưu lượng và tỷ lệ trễ của cùng top tuyến.
- **Phân phối:** box nhiều màu, khoảng Q1–Q3 và tỷ lệ ngoại lệ nếu có đủ số
  đếm. Các phân vị được lấy nguyên từ M2, không dựng dữ liệu chuyến bay giả.

Di chuột lên biểu đồ để xem chi tiết, click chú giải để bật/tắt chuỗi, kéo
để zoom và nhấn đúp để reset. Nút camera trên thanh công cụ xuất PNG độ phân
giải cao; CSV vẫn có trong phần mở rộng dữ liệu ở từng trang.

## 6. Tùy chọn: nạp trực tiếp KPI Parquet từ HDFS

Bước này chứng minh luồng HDFS KPI Parquet → M5 loader → MongoDB. **Giữ
ETL/EDA dừng trong cả lần nạp** để các bảng aggregate không bị thay đổi.

Khởi động batch stack nếu đang dừng (PowerShell cửa sổ khác):

```powershell
Set-Location F:\Project-BigData-Storage-and-Processing\batch-layer
docker compose up -d
docker compose exec namenode hdfs dfs -ls /aero/analytics/eda/kpi
docker compose exec namenode hdfs dfs -ls /aero/analytics/eda/box
```

Quay về serving rồi chạy:

```powershell
Set-Location F:\Project-BigData-Storage-and-Processing\serving-layer
.\scripts\load_hdfs.ps1
.\scripts\verify_m5.ps1
```

Lệnh tương đương nếu script bị chặn:

```powershell
docker compose -f compose.yml -f compose.hdfs.yml --profile hdfs run --rm --build hdfs-loader
if ($LASTEXITCODE -ne 0) { throw 'HDFS loader failed.' }
```

Job dùng Spark 3.5.3 đọc trực tiếp 20 bảng KPI/box trên HDFS, stage JSONL tạm
trong container và dùng chung writer. Không đọc Parquet chuyến bay ở
`/aero/processed`. Không cần MongoDB Spark Connector/JAR.

Mặc định mạng batch là `batch-layer_default`; nếu project name của bạn khác,
đặt `M5_BATCH_NETWORK` trong `.env` bằng tên mạng thực tế. Xem bằng
`docker network ls`. Khi Parquet và JSONL cùng schema/giá trị, fingerprint
giống nhau và loader xác nhận bộ đã có. Báo cáo tại
`evidence\hdfs_load_report.json`; log tại `logs\load_hdfs.log`.

## 7. Streaming: việc đã có và việc cần M4

Đã có writer kiểm tra full window aggregate, version guard/replay protection,
trang hiển thị refresh 10 giây và contract đề xuất tại
[`M4_TO_M5.md`](../contracts/M4_TO_M5.md). Chưa thể tự nghiệm thu M3/M4 khi
chưa có code/sink thật được nối vào.

M4 cần bàn giao schema, update semantics, khóa và revision bền vững qua restart.
Nếu M4 gửi delta hoặc schema khác, sửa adapter theo hợp đồng trước khi nạp.
Không chạy fixture giả vào database phục vụ rồi gọi đó là near-real-time API.

## 8. Dừng, tiếp tục và bàn giao

```powershell
.\scripts\stop_m5.ps1
```

Dữ liệu MongoDB giữ trong named volume `aero-serving_m5_mongo_data`. Lần sau
chạy start rồi mở dashboard; không bắt buộc nạp lại. Không dùng
`docker compose down -v` để dừng thông thường vì có thể xóa volume.

Đóng gói log/report và tài liệu:

```powershell
.\scripts\collect_evidence.ps1
```

ZIP nằm trong `serving-layer\evidence\M5_HANDOFF_<thời gian>.zip`. Thêm ảnh
chụp dashboard thực tế và kết quả demo vào bộ bàn giao. ZIP evidence không
chứa MongoDB volume; gửi kèm bộ snapshot M2 nguồn để máy khác có thể tái nạp.
Code và dependencies nằm trong `serving-layer` của repo.

Sao lưu MongoDB ra archive riêng (PowerShell):

```powershell
docker compose exec -T mongo mongodump --db aero_m5 --archive=/tmp/aero_m5.archive.gz --gzip
docker compose cp mongo:/tmp/aero_m5.archive.gz .\evidence\aero_m5.archive.gz
```

Nếu đổi `M5_DATABASE`, thay tên trong lệnh. Có thể khôi phục bằng `mongorestore`
vào database mới để kiểm tra, hoặc dựng MongoDB trống và nạp lại snapshot M2.

## 9. Lỗi thường gặp

| Hiện tượng | Xử lý |
|---|---|
| Không có Compose config | Chuyển vào `serving-layer`, hoặc dùng script bằng đường dẫn đầy đủ |
| Script bị Execution Policy chặn | Dùng lệnh Docker tương đương trong tài liệu |
| Không thấy manifest/JSONL | Trỏ `SnapshotPath` tới đúng thư mục chứa file, không phải thư mục export cha |
| Wrong keys/schema/count | Không bỏ kiểm tra; đối chiếu bộ export và manifest M2 |
| Another loader is running | Chờ loader cũ; nếu bị kill, lease tự hết sau tối đa 10 phút |
| Cổng đã dùng | Đổi cổng trong `.env`, rồi chạy start lại |
| Dashboard chưa thấy bộ mới | Nhấn Làm mới dữ liệu; kiểm tra loader đã PASS và con trỏ active |
| MongoDB unavailable | `docker compose ps`, `docker compose logs --tail 100 mongo dashboard` |
| HDFS hostname không resolve | Batch stack phải chạy và `M5_BATCH_NETWORK` phải đúng |
| HDFS báo thiếu bảng | Hoàn tất EDA M2 và kiểm tra đủ 13 KPI + 7 box |
| Streaming chưa có dữ liệu | Cần tích hợp M4; đây không phải lỗi của batch loader |

Nếu image được build lại sau sửa code, chạy lại start với `--build` (script
đã có). Không cần thay đổi các file notebook M2 để vận hành M5.
