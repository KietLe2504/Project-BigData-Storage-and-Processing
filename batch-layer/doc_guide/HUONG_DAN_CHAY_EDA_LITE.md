# Hướng dẫn chạy `eda_lite.ipynb` và sử dụng kết quả

> **Mục đích:** chạy notebook phân tích Spark trên dữ liệu BTS đã xử lý (`/aero/processed`), tạo các bảng KPI và thống kê box-plot nhỏ trong `/aero/analytics/eda`, rồi hướng dẫn người sau dùng các bảng này (đọc lại, xuất CSV, làm dashboard, thêm tháng mới).
>
> **Điều kiện trước:** Phase 1 đã xong. HDFS có đủ 51 phân vùng `/aero/processed/year=YYYY/month=MM/` và `08_verify_partition.py` báo `RESULT: PASS`.
>
> **Môi trường:** Windows + PowerShell + Docker Desktop + VS Code.

| | |
|---|---|
| **Đầu vào** | Parquet đã làm sạch: `/aero/processed/year=YYYY/month=MM/` |
| **Đầu ra** | `/aero/analytics/eda/{base,kpi,box}/` (trên HDFS) và `spark_jobs\evidence\` (plan thực thi, trên máy Windows) |
| **Thời gian tham chiếu** | Lần chạy của nhóm (2 tháng đã build sẵn, 49 tháng build mới, cộng bước cuộn lên và box-plot): khoảng **593 giây**, tức khoảng 9 giây mỗi tháng sau khi JVM khởi động. Thời gian trên máy khác có thể khác. |

---

## 1. Chuẩn bị môi trường

Tất cả lệnh `docker compose` phải chạy **trong thư mục có `docker-compose.yml`**. Nếu không, Docker báo `no configuration file provided: not found`.

### Bước 1. Mở cổng 8888 cho service `spark`

Thêm `ports` vào service `spark` trong `docker-compose.yml`:

```yaml
  spark:
    image: apache/spark:3.5.3
    container_name: aero-spark
    depends_on:
      - namenode
      - datanode
    ports:
      - "8888:8888"          # <-- thêm dòng này
    volumes:
      - ./spark_jobs:/opt/spark_jobs
      - ./BTS_ZIP:/data/input:ro
    entrypoint: ["/bin/bash", "-lc", "sleep infinity"]
```

### Bước 2. Cập nhật container

```powershell
docker compose up -d
docker compose ps
```

Lệnh này chỉ tạo lại container `spark`. Dữ liệu HDFS nằm trong volume nên **không mất**. Nhưng mọi thư viện đã `pip install` trong container `spark` sẽ mất, nên phải cài lại ở bước 3.

### Bước 3. Cài Jupyter và thư viện cho Spark

```powershell
docker compose exec -u root spark bash -lc "python3 -m pip install jupyterlab pandas pyarrow"
```

Nếu báo thiếu `pip`:

```powershell
docker compose exec -u root spark bash -lc "apt-get update && apt-get install -y python3-pip"
```

Nếu notebook in ra hai phiên bản khác nhau (ví dụ `pyspark 3.5.9 | Spark 3.5.3`), cài đúng phiên bản của Spark trong image:

```powershell
docker compose exec -u root spark bash -lc "python3 -m pip install pyspark==3.5.3"
```

Cần `pandas` và `pyarrow` cho phần *custom aggregation* (pandas UDF), cho PageRank sân bay (`airport_network`) và cho hàm `peek()` hiển thị bảng. Thiếu `pandas`, cell hiển thị bảng vẫn chạy (rơi về `show()`), nhưng `airport_network` sẽ lỗi. Thiếu `pyarrow`, phần pandas UDF bị bỏ qua.

### Bước 4. Khởi động Jupyter

Giữ cửa sổ PowerShell này **mở** trong suốt quá trình làm việc, vì đóng cửa sổ là server tắt:

```powershell
docker compose exec -u root spark bash -lc "jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --allow-root --notebook-dir=/opt/spark_jobs"
```

Trong log, copy URL có token, ví dụ `http://127.0.0.1:8888/lab?token=...`. Đừng đăng token này ra ngoài.

### Bước 5. Đặt notebook vào thư mục `spark_jobs\`

Copy `eda_lite.ipynb` vào `spark_jobs\` trên máy Windows. Thư mục này được mount thành `/opt/spark_jobs` trong container, nên Jupyter sẽ thấy file ngay.

### Bước 6. Mở notebook (chọn một cách)

- **Trình duyệt:** mở URL ở bước 4, chọn `eda_lite.ipynb`.
- **VS Code:** mở `eda_lite.ipynb` → **Select Kernel** → **Existing Jupyter Server** → dán URL có token → chọn **Python 3 (ipykernel)**.

### Bước 7. Kiểm tra kernel đúng chỗ

Chạy thử một cell:

```python
import sys, os
print(sys.executable)                 # mong đợi: /usr/bin/python3
print(os.path.exists("/opt/spark"))   # mong đợi: True
```

Nếu `sys.executable` bắt đầu bằng `C:\...` thì kernel đang là Python của Windows, **không** đọc được HDFS. Hãy chọn lại kernel ở bước 6.

---

## 2. Chạy notebook

### Lần đầu: chạy thử 3 tháng

Ở cell 1 (cấu hình), đổi dòng `MONTHS` để chạy thử:

```python
MONTHS = month_range((2022, 1), (2022, 3))
```

Chạy lần lượt từ trên xuống. Khi kết quả đúng, đổi lại thành toàn bộ dữ liệu (các cell tính từ cell **code** đầu tiên, không đếm cell markdown):

```python
MONTHS = month_range((2022, 1), (2026, 3))
```

### Các cell làm gì

| Cell | Nội dung | Ghi chú |
|---|---|---|
| 1 | Môi trường, cấu hình, quy ước chỉ số, tạo Spark session | Đổi `MONTHS` ở đây |
| 2 | Nạp dữ liệu theo tháng và chuẩn hóa (`prepare`) | Tên cột được dò tự động |
| 3 | Lõi KPI: cột cộng được, `rollup`, `finalize` | Không chạy gì nặng |
| 4 | Box-plot từ biểu đồ tần suất | Không chạy gì nặng |
| 5 | Định nghĩa pipeline (`build_month`, `build_kpis`, `build_boxes`) | Chỉ định nghĩa hàm |
| 6 | **Chạy pipeline** (3 bước) | Cell nặng nhất |
| 7 | Các hàm phân tích | Chỉ định nghĩa hàm |
| 8 | Xem kết quả | Đọc các bảng nhỏ nên nhanh |
| 9 | Kỹ thuật đặc biệt và bằng chứng Spark | Chạy trên 1 tháng |

Cell 6 gồm ba bước:

1. **Từng tháng:** đọc dữ liệu thô một lần, ghi 5 bảng KPI cơ sở và 1 biểu đồ tần suất.
2. **Cuộn lên:** cộng các bảng cơ sở thành 13 bảng KPI ở mọi mức.
3. **Box-plot:** tính 7 bảng box-plot từ biểu đồ tần suất.

### Dấu hiệu chạy đúng

- Cell 1 in một dòng dạng `pyspark ... | Spark 3.5.3 | python 3.8.x | 51 tháng: 2022-01 → 2026-03`.
- Cell 6 in từng tháng (`2022-01: 5xx,xxx dòng | ~9s`) và kết thúc bằng `Hoàn tất sau ...s → /aero/analytics/eda`.
- Cell 9 in kết quả bằng chứng. Tham chiếu từ lần chạy của nhóm:
  - `scan_partitions_no_filter: 329` giảm còn `scan_partitions_with_filter: 7`.
  - Broadcast join và sort-merge join cùng số dòng (`same_rowcount: true`).
  - Bucketing: số `Exchange` giảm từ 2 xuống 0.
  - UDF vs biểu thức tham chiếu: `0 / <tổng số dòng>` (không lệch dòng nào).

### Chạy lại và ngắt giữa chừng

- Build **tiếp tục được**: tháng nào đã có biểu đồ tần suất trong `base/hist` sẽ được bỏ qua (`↷ Đã build trước đó`).
- Nếu Docker Desktop tắt giữa chừng hoặc máy hết RAM, chỉ cần mở lại, khởi động lại Jupyter và chạy lại cell 6.
- Muốn tính lại **tất cả** tháng, đặt `FORCE_REBUILD = True` ở cell 1.

### Giải phóng RAM

Session Spark trong notebook giữ RAM. Trước khi chạy `spark-submit` (ETL hoặc verify) ở cửa sổ khác, hãy chạy `spark.stop()` hoặc tắt kernel.

---

## 3. Kết quả nằm ở đâu

```text
/aero/analytics/eda/                  (HDFS)
├── base/    bảng cơ sở, cộng được, phân vùng theo year=/month=
│   ├── day_carrier              (year, month, day, carrier)
│   ├── day_origin               (year, month, day, origin)
│   ├── month_carrier_origin     (year, month, carrier, origin)
│   ├── month_route              (year, month, origin, dest)
│   ├── prof_hour                (year, month, dep_hour)
│   └── hist                     biểu đồ tần suất delay (year, month, day, carrier, var, v, n)
├── kpi/     bảng KPI đã tính tỷ lệ (nhỏ, dùng trực tiếp)
└── box/     thống kê box-plot (nhỏ, dùng trực tiếp)

spark_jobs\evidence\                  (trên Windows) plan thực thi và tóm tắt bằng chứng
```

### Bảng `kpi/`

| Bảng | Khóa (mỗi dòng là) | Dùng để |
|---|---|---|
| `day_overall` | year, month, day | Chuỗi từng ngày, ngày bất thường |
| `calendar_day_overall` | month, day | Cùng ngày lịch qua các năm (ví dụ 25/12) |
| `month_overall` | year, month | Chuỗi 51 tháng, xu hướng |
| `month_of_year_overall` | month | Mùa vụ (mọi tháng 1, mọi tháng 7…) |
| `year_overall` | year | Tổng kết năm |
| `month_carrier` | year, month, carrier | Hãng theo tháng |
| `month_of_year_carrier` | month, carrier | Mùa vụ theo hãng |
| `year_carrier` | year, carrier | Xếp hạng hãng |
| `month_origin` | year, month, origin | Sân bay theo tháng |
| `year_origin` | year, origin | Xếp hạng sân bay |
| `year_route` | year, origin, dest | Tuyến bay, mạng lưới |
| `year_carrier_origin` | year, carrier, origin | Thị phần và độ tập trung hãng tại sân bay |
| `hour_overall` | dep_hour | Trễ theo giờ khởi hành |

### Bảng `box/`

Tên bảng là `<mức>_<overall|carrier>`: `day_overall`, `month_overall`, `month_carrier`, `month_of_year_overall`, `month_of_year_carrier`, `year_overall`, `year_carrier`.

Mỗi dòng là một nhóm × `var` × `population`:
- `var`: `arr` (delay đến) hoặc `dep` (delay đi).
- `population`: `all` (mọi chuyến đã bay) hoặc `late` (chỉ chuyến trễ từ 15 phút).

---

## 4. Từ điển cột và công thức

### Cột đếm và tổng (cộng được)

| Cột | Ý nghĩa |
|---|---|
| `flights` | Số chuyến lên lịch (gồm cả hủy và chuyển hướng) |
| `cancelled`, `diverted` | Số chuyến hủy, chuyển hướng |
| `arr_n` | Số chuyến có đo được giờ đến (không hủy, không chuyển hướng) |
| `on_time` | Số chuyến đến muộn dưới 15 phút (gồm cả đến sớm) |
| `delayed15`, `delayed60` | Số chuyến đến muộn từ 15, 60 phút |
| `cause_carrier`, `cause_weather`, `cause_nas`, `cause_security`, `cause_late_aircraft` | Tổng phút trễ theo nguyên nhân |
| `cancel_a` … `cancel_d` | Số chuyến hủy theo mã A (hãng), B (thời tiết), C (NAS), D (an ninh) |
| `n_days` | Số ngày có dữ liệu (năm 2026 chỉ có 90 ngày) |

### Cột tỷ lệ (đã tính sẵn)

| Cột | Công thức |
|---|---|
| `cancel_rate` | `cancelled / flights` |
| `divert_rate` | `diverted / flights` |
| `otp_operated` | `on_time / arr_n` (đúng giờ trên chuyến đo được) |
| `otp_scheduled` | `on_time / flights` (hủy và chuyển hướng tính là không đúng giờ) |
| `delay15_rate` | `delayed15 / arr_n` |
| `severe60_rate` | `delayed60 / arr_n` |
| `avg_arr_delay_net` | trung bình delay đến, **giữ số âm** (đến sớm bù trừ) |
| `avg_arr_delay_pos` | trung bình phần trễ (số âm tính là 0) |
| `avg_delay_when_late` | trung bình delay của riêng các chuyến trễ từ 15 phút |
| `avg_air_gain` | trung bình `DEP_DELAY − ARR_DELAY` (dương: bù được giờ trên không) |
| `cause_*_share` | phần trăm phút trễ do từng nguyên nhân |
| `reliability_score` | `100 × (1 − (0,50·delay15_rate + 0,20·severe60_rate + 0,25·cancel_rate + 0,05·divert_rate))`, kẹp trong 0 đến 100 |

`reliability_score` là chỉ số **tự định nghĩa của nhóm**, không phải chuẩn ngành. Trọng số nằm ở `W_DELAY`, `W_SEVERE`, `W_CANCEL`, `W_DIVERT` trong cell 1.

### Cột box-plot

`n`, `min`, `p05`, `q1`, `median`, `q3`, `p90`, `p95`, `p99`, `max`, `mean`, `std`, `iqr`, `fence_low`, `fence_high`, `whisker_low`, `whisker_high`, `n_out_low`, `n_out_high`, `out_low_rate`, `out_high_rate`, `reliable`.

- Râu theo quy ước Tukey: hàng rào là `q1 − 1,5·iqr` và `q3 + 1,5·iqr`. `whisker_*` là **giá trị thực** xa nhất còn nằm trong hàng rào.
- `n_out_*` là số chuyến nằm ngoài hàng rào. Delay có đuôi dài: ở delay đến của mọi chuyến đã bay, khoảng 9% chuyến vượt hàng rào trên (theo lần chạy của nhóm). Đó là các chuyến trễ nặng có thật, **không phải lỗi dữ liệu**.
- `reliable = false` khi nhóm có ít hơn 30 chuyến.
- Phân vị tính theo hạng gần nhất trên phút nguyên, nên các số này **chính xác** (không xấp xỉ).

### Hai quy tắc ngữ nghĩa cần nhớ

1. `ARR_DELAY`/`DEP_DELAY` null nghĩa là chuyến hủy hoặc chuyển hướng. **Không điền 0**, nếu không tỷ lệ đúng giờ sẽ cao giả.
2. Các cột nguyên nhân trễ null nghĩa là chuyến không trễ từ 15 phút, nên điền 0 là đúng.

---

## 5. Sử dụng kết quả sau khi chạy

### 5.1. Đọc lại các bảng trong một notebook mới

Dùng cùng cách tạo Spark session như cell 1, rồi:

```python
A = "/aero/analytics/eda"
kpi = lambda n: spark.read.parquet(f"{A}/kpi/{n}")
box = lambda n: spark.read.parquet(f"{A}/box/{n}")

kpi("year_carrier").where("flights >= 200").orderBy("year", "carrier").show()
box("year_overall").where("var = 'arr' and population = 'all'").show()
```

Không cần chạy lại pipeline. Các bảng `kpi/` và `box/` rất nhỏ nên đọc gần như tức thì.

### 5.2. Xuất CSV cho người không dùng Spark

Thêm một cell vào cuối notebook (đã chạy thử trên dữ liệu thử). Các file CSV sẽ xuất hiện trong `spark_jobs\export\` trên Windows:

```python
EXPORT_DIR = os.environ.get("AERO_EXPORT", "/opt/spark_jobs/export")
def export_tables(subs=("kpi", "box")):
    os.makedirs(EXPORT_DIR, exist_ok=True)
    for sub in subs:
        path, fs = _hpath(f"{ANALYTICS}/{sub}")
        for st in fs.listStatus(path):
            name = st.getPath().getName()
            pdf = spark.read.parquet(f"{ANALYTICS}/{sub}/{name}").toPandas()
            pdf.to_csv(os.path.join(EXPORT_DIR, f"{sub}__{name}.csv"), index=False)
            print(f"{sub}/{name}: {len(pdf):,} dòng")
export_tables()
```

Không xuất `base/` (đặc biệt `hist` rất lớn).

### 5.3. Làm dashboard

Gợi ý ánh xạ trang dashboard sang bảng:

| Trang | Bảng | Ghi chú |
|---|---|---|
| Tổng quan | `kpi/year_overall` | KPI chính theo năm |
| Xu hướng | `kpi/month_overall` | Có thể thêm trung bình trượt và so cùng kỳ (hàm `monthly_trend` trong notebook) |
| Lịch ngày | `kpi/day_overall` | Dạng heatmap lịch theo `delay15_rate` hoặc `cancel_rate` |
| Hãng bay | `kpi/year_carrier`, `kpi/month_carrier` | Xếp hạng theo `reliability_score` |
| Sân bay | `kpi/year_origin`, `kpi/year_carrier_origin` | Sân bay trễ nhiều, độ tập trung hãng |
| Mạng lưới | `kpi/year_route` | Cạnh = tuyến, trọng số = `flights` |
| Phân phối delay | `box/*` | Vẽ box-plot trực tiếp từ thống kê (ví dụ bên dưới) |

**Vẽ box-plot từ thống kê có sẵn, không cần dữ liệu thô** (Plotly nhận trực tiếp `q1`, `median`, `q3`, `lowerfence`, `upperfence`; đã chạy thử việc dựng biểu đồ):

```python
import pandas as pd, plotly.graph_objects as go
b = pd.read_csv("export/box__year_carrier.csv")
b = b[(b["var"] == "arr") & (b["population"] == "late") & (b["year"] == 2025) & b["reliable"]]
fig = go.Figure(go.Box(x=b["carrier"], q1=b["q1"], median=b["median"], q3=b["q3"],
                       lowerfence=b["whisker_low"], upperfence=b["whisker_high"], mean=b["mean"]))
fig.show()
```

**Nạp vào MongoDB (theo kiến trúc của nhóm).** Các bảng `kpi/` đủ nhỏ để nạp bằng upsert theo khóa tự nhiên. Đây là **mẫu chưa chạy thử**, vì `docker-compose.yml` hiện chưa có MongoDB. Cần `pip install pymongo` và sửa địa chỉ theo compose của M5:

```python
from pymongo import MongoClient, UpdateOne
client = MongoClient("mongodb://localhost:27017")

def push(name, keys, db="aero"):
    pdf = kpi(name).toPandas()
    pdf = pdf.astype(object).where(pdf.notna(), None)          # NaN → null
    ops = [UpdateOne({k: r[k] for k in keys}, {"$set": r}, upsert=True) for r in pdf.to_dict("records")]
    client[db][f"kpi_{name}"].bulk_write(ops, ordered=False)

push("year_carrier", ["year", "carrier"])
push("month_overall", ["year", "month"])
```

Quy ước đề xuất: mỗi bảng thành một collection `kpi_<tên bảng>`, khóa upsert là các cột khóa ở bảng mục 3. Làm vậy nạp lại nhiều lần không sinh bản trùng. Giữ dữ liệu lịch sử (batch) và dữ liệu streaming ở hai collection riêng.

### 5.4. Khi có dữ liệu mới hoặc thay dữ liệu

1. Chạy ETL (`06_batch_process_all.py`) và verify (`08_verify_partition.py`) cho tháng mới.
2. Mở rộng `MONTHS` ở cell 1 (ví dụ thêm đến `(2026, 4)`) rồi chạy lại cell 6. Chỉ tháng chưa build được xử lý, còn các bảng KPI và box-plot được cuộn lên lại từ các bảng cơ sở.
3. Nếu **thay dữ liệu của tháng đã build**, đặt `MONTHS = [(năm, tháng)]` và `FORCE_REBUILD = True`, chạy cell 6, rồi đặt lại như cũ. Bước 2 và 3 của cell 6 luôn đọc toàn bộ bảng cơ sở nên kết quả vẫn đầy đủ.

### 5.5. Lưu ý khi dùng

- Muốn gộp nhiều hàng (ví dụ nhiều hãng hoặc nhiều tháng), **cộng các cột đếm rồi chia**. Ví dụ `otp_scheduled = sum(on_time) / sum(flights)`. Đừng lấy trung bình của các cột tỷ lệ.
- Năm 2026 chỉ có 90 ngày (quý 1). Khi so sánh năm, hãy xem `n_days` hoặc so cùng kỳ.
- Bảng tuyến (`year_route`) chỉ có mức năm. Phần tháng chỉ có ở `base/month_route` (chưa tính tỷ lệ).
- Tên hãng lấy từ bảng tra `CARRIERS` trong notebook. Mã chưa có trong bảng sẽ hiện mã gốc.

---

## 6. Sự cố thường gặp

| Triệu chứng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `no configuration file provided: not found` | Đang đứng sai thư mục | `Set-Location` vào thư mục có `docker-compose.yml`, hoặc dùng `docker exec aero-spark ...` |
| `sys.executable` là `C:\...\python.exe`, `/opt/spark` là `False` | Kernel là Python của Windows | Chọn lại kernel qua Existing Jupyter Server (mục 1, bước 6) |
| `ModuleNotFoundError: No module named 'pyspark'` | Thiếu thư viện trong kernel | Cell 1 tự thêm đường dẫn `/opt/spark/python`. Nếu vẫn lỗi: `pip install pyspark==3.5.3` trong container |
| Không mở được `http://127.0.0.1:8888` | Chưa thêm `ports` hoặc chưa `docker compose up -d` lại | Làm lại bước 1 và 2 |
| Jupyter biến mất sau khi sửa compose | Container `spark` bị tạo lại, mất thư viện | Cài lại bước 3, chạy lại bước 4 và lấy token mới |
| Phiên bản `pyspark` khác `Spark` | pip cài bản khác với Spark trong image | `pip install pyspark==3.5.3` |
| Cảnh báo `COLUMN_ALREADY_EXISTS ... month` | Nhiều khả năng file Parquet vẫn chứa cột `MONTH` trùng với cột phân vùng `month` | Vô hại, vì notebook tự tính `year`/`month` từ `FL_DATE` |
| `⚠ Không chạy được pandas UDF` | Thiếu `pandas`/`pyarrow`, hoặc Java 21 trở lên | Cài lại bước 3. Phần còn lại vẫn chạy bình thường |
| Treo hoặc chậm, container bị kill | Hết RAM | Tắt ứng dụng nặng khác. Chạy ít tháng hơn một lượt (đặt `MONTHS` nhỏ lại rồi nới dần) |
| `⚠ Thiếu N tháng` | Partition tháng đó chưa có trong `/aero/processed` | Chạy ETL (`06`) cho tháng đó |
| Docker Desktop tắt giữa chừng | | Mở lại, khởi động lại Jupyter, chạy lại cell 6 (tự bỏ qua tháng đã xong) |

---

## 7. Checklist

- [ ] HDFS có đủ 51 phân vùng và `08_verify_partition.py` báo `PASS`.
- [ ] Đã thêm `ports: "8888:8888"` cho service `spark`, đã `docker compose up -d`.
- [ ] Đã cài `jupyterlab pandas pyarrow` trong container `spark`.
- [ ] Jupyter đang chạy và kernel nằm trong container (`sys.executable` là `/usr/bin/python3`).
- [ ] Đã chạy thử 3 tháng, kết quả đúng, rồi mới chạy 51 tháng.
- [ ] Cell 6 kết thúc bằng `Hoàn tất ...` và có đủ thư mục `base`, `kpi`, `box`.
- [ ] Cell 9 in đủ 5 bằng chứng kỹ thuật, `spark_jobs\evidence\` có file plan.
- [ ] Đã (nếu cần) xuất CSV hoặc nạp MongoDB cho M5.
- [ ] Đã ghi lại thời gian chạy và số dòng từng tháng vào báo cáo.
