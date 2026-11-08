# Xuất kết quả M2 để phát triển M5

M2 tạo Parquet sạch và các bảng phân tích trên HDFS. M5 nhận các bảng tổng hợp,
nạp vào MongoDB và xây dashboard truy vấn MongoDB. Script
`spark_jobs/09_export_m2_outputs.py` xuất một bộ dữ liệu bàn giao từ kết quả thật
của `eda_lite.ipynb`; script không tạo dữ liệu giả và không nạp MongoDB.

## 1. Điều kiện trước khi xuất

1. Đã nạp CSV vào `/aero/raw/bts`.
2. Đã chạy `06_batch_process_all.py` và `08_verify_partition.py` báo `PASS`.
3. Đã chạy cell cấu hình đến cell build (cell code 6) của `eda_lite.ipynb`.
   Chỉ chạy ETL `06` chưa tạo được KPI cho M5.
4. Để bàn giao đủ phạm vi dự án, notebook phải build 51 tháng 2022-01 đến 2026-03.
   Bản chạy thử 3 tháng có thể dùng để phát triển nhưng phải ghi rõ phạm vi.
5. Chờ ETL/EDA ghi xong trước khi xuất. Không chạy job ghi vào các bảng nguồn
   trong khi xuất. Chạy `spark.stop()` trong notebook hoặc tắt kernel để giải
   phóng RAM trước khi chạy `spark-submit`.

Các lệnh PowerShell dưới đây chạy tại thư mục `batch-layer`:

```powershell
Set-Location F:\Project-BigData-Storage-and-Processing\batch-layer
docker compose ps
docker compose exec namenode hdfs dfs -ls /aero/analytics/eda/kpi
docker compose exec namenode hdfs dfs -ls /aero/analytics/eda/box
```

## 2. Chạy script xuất

```powershell
docker compose exec -u root spark /opt/spark/bin/spark-submit `
  --master 'local[2]' `
  --driver-memory 2g `
  --conf spark.sql.shuffle.partitions=8 `
  --conf spark.hadoop.fs.defaultFS=hdfs://namenode:9000 `
  /opt/spark_jobs/09_export_m2_outputs.py
```

Script chỉ đọc 13 bảng `kpi/` và 7 bảng `box/` của notebook bản lite, không đọc
29 triệu chuyến bay hay bảng `base/hist`. Không cần cài pandas cho bước xuất.
Script kiểm tra cột bắt buộc, bảng rỗng và khóa trùng trong từng bảng; mỗi bảng
có giới hạn mặc định 200.000 dòng. Đây là kiểm tra bàn giao, không thay thế
việc đối soát nguồn, kiểm tra công thức hay verifier của M2.

Mỗi lần chạy tạo một thư mục mới. Khi đủ tất cả bảng, terminal in
`EXPORT COMPLETE` và đường dẫn bộ kết quả. Nếu lỗi, thư mục tạm bị bỏ đi và các
bộ xuất thành công trước đó được giữ lại.

## 3. Lấy file trên Windows

Compose mount `./spark_jobs` thành `/opt/spark_jobs`. Do đó đầu ra mặc định:

```text
Trong container: /opt/spark_jobs/export/m2_to_m5/<UTC timestamp>/
Trên Windows:   batch-layer\spark_jobs\export\m2_to_m5\<UTC timestamp>\
```

Không cần `docker cp` với cấu hình mount hiện tại.

```text
<UTC timestamp>/
├── manifest.json
├── kpi__month_overall.csv
├── kpi__month_overall.jsonl
├── kpi__year_overall.csv
├── kpi__year_overall.jsonl
├── ...                         # đủ 13 bảng KPI, mỗi bảng có CSV + JSONL
├── box__year_overall.csv
├── box__year_overall.jsonl
└── ...                         # đủ 7 bảng box, mỗi bảng có CSV + JSONL
```

Tổng cộng 41 file: 20 CSV, 20 JSONL và 1 manifest. Gửi toàn bộ thư mục cho M5.
CSV dùng để xem nhanh. JSONL có một object JSON trên mỗi dòng và giữ kiểu số,
boolean, null, phù hợp để M5 viết chương trình nạp MongoDB.

## 4. Kiểm tra và đọc thử bằng Python của M5

Không cần Spark, HDFS hay pandas để đọc bộ JSONL đã xuất:

```python
import json
from pathlib import Path

# Sửa thành đường dẫn bộ xuất thực tế, không để nguyên <UTC timestamp>.
folder = Path(r"F:\Project-BigData-Storage-and-Processing\batch-layer\spark_jobs\export\m2_to_m5\<UTC timestamp>")
manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
print(manifest["coverage"])

for table in manifest["tables"]:
    with (folder / table["jsonl"]).open(encoding="utf-8") as handle:
        rows = sum(1 for line in handle if line.strip())
    assert rows == table["rows"], table["name"]

with (folder / "kpi__month_overall.jsonl").open(encoding="utf-8") as handle:
    first_document = json.loads(next(handle))
print(first_document)
```

Kiểm tra `coverage.month_count` là 51 và
`matches_project_period_2022_01_to_2026_03` là `true` khi bàn giao toàn bộ kỳ.
`total_flights` là tổng từ KPI tháng được xuất, không phải phép đếm độc lập CSV.
Thời điểm `exported_at_utc` chỉ là lúc xuất; chưa có metadata thời điểm build
upstream trong pipeline hiện tại.

## 5. Hợp đồng nạp MongoDB cho M5

`manifest.json` có schema Spark thực tế, số dòng, đường dẫn nguồn, tên collection
đề xuất và khóa định danh của từng bảng. Ví dụ:

| JSONL | Collection đề xuất | Khóa upsert / unique index |
|---|---|---|
| `kpi__month_overall.jsonl` | `kpi_month_overall` | `year, month` |
| `kpi__year_overall.jsonl` | `kpi_year_overall` | `year` |
| `kpi__month_carrier.jsonl` | `kpi_month_carrier` | `year, month, carrier` |
| `kpi__year_origin.jsonl` | `kpi_year_origin` | `year, origin` |
| `kpi__year_route.jsonl` | `kpi_year_route` | `year, origin, dest` |
| `box__year_carrier.jsonl` | `box_year_carrier` | `year, carrier, var, population` |

Không trộn file KPI và box cùng tên vào một collection. Với bảng box, `var`
(`arr`/`dep`) và `population` (`all`/`late`) là một phần của khóa. Giá trị null
ở chiều nhóm tùy chọn, nếu có, được giữ nguyên và cần quy ước khi hiển thị.

M5 thực hiện tiếp:

1. Dựng MongoDB và lưu dữ liệu bền vững.
2. Tạo unique index theo `keys` của từng collection.
3. Đọc từng dòng JSONL; upsert document theo khóa đó. Nạp lại cùng bộ xuất
   không làm tăng số document.
4. Đối chiếu số document và giá trị KPI với file xuất.
5. Viết dashboard truy vấn MongoDB, có bộ lọc năm/tháng/hãng/sân bay.
6. Khi có bộ xuất mới, chạy loader lại và kiểm tra độ mới dữ liệu. Upsert không
   tự xóa document thuộc kỳ/nhóm đã bị loại khỏi nguồn; phải quy định cách đồng
   bộ/xóa dữ liệu cũ nếu phạm vi bộ xuất thay đổi.

MongoDB và dashboard chưa có trong Compose hiện tại. Bộ xuất giúp phát triển
M5 trên máy khác mà không cần truy cập HDFS. Khi tích hợp, loader cần lấy kết
quả từ các lần chạy M2 thực tế, và hiển thị rõ đây là dữ liệu lịch sử BTS.

## 6. Các quy tắc KPI cần giữ

| Trường | Ý nghĩa / cách dùng |
|---|---|
| `flights` | Số chuyến lên lịch, gồm cả hủy và chuyển hướng |
| `cancel_rate` | `cancelled / flights` |
| `otp_scheduled` | `on_time / flights` |
| `otp_operated` | `on_time / arr_n`; `arr_n` đếm chuyến có arrival delay hợp lệ sau lọc |
| `delay15_rate` | `delayed15 / arr_n` |
| `avg_arr_delay_net` | Phút; giữ giá trị âm do đến sớm |
| `reliability_score` | Điểm tự định nghĩa của nhóm, 0–100 |

- Tỷ lệ lưu dạng 0–1; `0.05` hiển thị thành `5%`.
- JSON null không tự động đổi thành 0.
- Gộp nhiều nhóm: cộng các số đếm/tổng rồi tính tỷ lệ, không lấy trung bình tỷ lệ.
- Năm 2026 chỉ có quý 1 trong phạm vi dự án; ghi rõ khi so sánh với năm đủ 12 tháng.
- Schema JSONL xuất theo code hiện tại; các field như `out_low_rate` được liệt
  kê trong tài liệu cũ có thể không có trong notebook lite. Dùng schema thực
  tế trong manifest khi viết code.

Tham khảo thêm `HUONG_DAN_CHAY_EDA_LITE.md`, mục 3–5, và PDF phân công trang 4,
7, 8 về đầu ra M2, trách nhiệm M5 và hợp đồng bàn giao.
