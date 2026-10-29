# Tài liệu kỹ thuật Spark trong `eda_lite.ipynb`

> **Mục đích:** giải thích từng kỹ thuật xử lý Spark có trong notebook: dùng kỹ thuật gì, hoạt động ra sao, vì sao phù hợp, và bằng chứng chạy thật ở đâu. Phân loại theo 5 nhóm yêu cầu của milestone.
>
> **Cách đọc:** "cell N" là cell **code** thứ N (không đếm cell markdown): 1 = cấu hình, 2 = nạp và chuẩn hóa, 3 = lõi KPI, 4 = box-plot, 5 = pipeline, 6 = chạy, 7 = hàm phân tích, 8 = xem kết quả, 9 = kỹ thuật đặc biệt và bằng chứng.
>
> **Số liệu minh họa** lấy từ lần chạy thật của nhóm trên 51 tháng (khoảng 29 triệu dòng). Các con số thời gian chỉ mang tính tham khảo, vì mỗi lần đo chạy một lượt trên một máy.
>
> **Phạm vi:** notebook này chỉ có **batch**. Nhóm 5 (Streaming) chưa có trong code, nên phần đó chỉ giải thích khái niệm và thiết kế dự kiến (xem mục 5).

## Bảng tổng hợp

| Nhóm | Kỹ thuật | Hàm (cell) | Trạng thái |
|---|---|---|---|
| **1. Complex Aggregations** | Window functions, aggregation nâng cao | `monthly_trend`, `daily_anomalies`, `day_in_month`, `carrier_ranking`, `concentration` (7); `box_from_hist` (4); `_add_exprs`, `rollup` (3) | Đã chạy |
| | Pivot và unpivot | `month_matrix`, `carrier_matrix`, `unpivot_causes` (7) | Đã chạy |
| | Custom aggregation | `trimmed_mean` (9); `rollup` + `finalize` (3); `box_from_hist` (4) | Đã chạy (pandas UDF cần `pandas` + `pyarrow`) |
| **2. Advanced Transformations** | Nhiều giai đoạn biến đổi | `prepare` (2), `kpi_base → rollup → finalize` (3, 5), `build_hist → box_from_hist` (4, 5) | Đã chạy |
| | Chuỗi thao tác phức tạp | `finalize` (3), `prepare` (2), `box_from_hist` (4) | Đã chạy |
| | UDF cho logic nghiệp vụ | `severity_udf` (9), `is_late` trong `evidence_optimization` (9) | Đã chạy |
| **3. Join Operations** | Broadcast join | `carrier_ranking`, `daily_anomalies`, `holiday_effect`, `enrich_routes` (7); `box_from_hist` (4) | Đã chạy |
| | Sort-merge join | `route_excess_delay(hint="merge")` (7) | Đã chạy |
| | Tối ưu nhiều join | `enrich_routes`, `carrier_yoy`, `concentration` (7) | Đã chạy |
| **4. Performance Optimization** | Partition pruning và bucketing | `load_months` (2), `evidence_pruning`, `evidence_bucketing` (9) | Đã chạy |
| | Cache và persistence | `build_month` (5), `evidence_cache` (9) | Đã chạy |
| | Tối ưu truy vấn, execution plan | `plan_text`, `evidence_joins`, `evidence_optimization` (9) | Đã chạy |
| **5. Streaming Processing** | Output modes, watermark, state, exactly-once | — | **Chưa có trong notebook**, thuộc phạm vi M4 |

Mỗi bằng chứng trong cell 9 có thể chạy lại riêng: `evidence_pruning()`, `evidence_joins()`, `evidence_cache(df_demo)`, `evidence_bucketing(df_demo)`, `evidence_optimization()`. Plan chi tiết lưu ở `spark_jobs\evidence\*.txt`.

---

## 1. Complex Aggregations

### 1.1. Window functions và advanced aggregation functions

**Window function** tính giá trị cho mỗi dòng dựa trên một nhóm dòng liên quan ("khung"), nhưng **không gộp dòng** như `groupBy`. Một window gồm ba phần: `partitionBy` (chia nhóm), `orderBy` (sắp xếp trong nhóm) và khung (`rowsBetween` theo vị trí hoặc `rangeBetween` theo giá trị).

**a) Trung bình trượt 3 tháng: `monthly_trend` (cell 7)**

```python
t = F.col("year") * 12 + F.col("month")                 # số tháng liên tục
F.avg(metric).over(Window.orderBy("t").rangeBetween(-2, 0))
```

- Khung `rangeBetween(-2, 0)` là khung **theo giá trị**: lấy các dòng có `t` nằm trong `[t-2, t]`. Khác với `rowsBetween` (theo vị trí), nó vẫn đúng khi thiếu một tháng.
- Không có `partitionBy` nên mọi dòng vào một partition. Chấp nhận được vì chỉ có 51 dòng (Spark có thể in cảnh báo, vô hại).
- So cùng kỳ năm trước làm bằng **self-join** trên `t + 12` thay vì `lag(12)`, để vẫn đúng nếu thiếu tháng.

**b) Nền trượt 28 ngày và z-score: `daily_anomalies` (cell 7)**

```python
w = Window.orderBy("dn").rangeBetween(-28, -1)          # dn = số ngày từ 1970-01-01
z = (F.col(metric) - F.avg(metric).over(w)) / F.stddev(metric).over(w)
```

Khung kết thúc ở `-1` nên **không gồm ngày hiện tại**. Nếu gồm, một ngày bất thường sẽ tự kéo lệch nền của chính nó. Ngày có `|z|` lớn nhất được xếp lên đầu và gắn nhãn ngày lễ (broadcast join).

**c) Xếp hạng và "top-1 mỗi nhóm": `carrier_ranking`, `day_in_month`, `concentration` (cell 7)**

- `dense_rank()` với `partitionBy("year").orderBy(desc("reliability_score"))` xếp hạng hãng trong từng năm. `dense_rank` không bỏ số khi đồng hạng (khác `rank`).
- `row_number()` với `partitionBy("year", "origin").orderBy(desc("share"))` rồi `where rk = 1` lấy **hãng chiếm ưu thế** tại mỗi sân bay. Đây là mẫu "top-N mỗi nhóm".

**d) Tần suất tích lũy để tính phân vị: `box_from_hist` (cell 4)**

```python
d = d.withColumn("cum",   F.sum("n").over(Window.partitionBy(*g).orderBy("v")))   # tích lũy
d = d.withColumn("total", F.sum("n").over(Window.partitionBy(*g)))                # tổng nhóm
q = lambda p: F.min(F.when(F.col("cum") >= F.greatest(F.lit(1), F.ceil(F.col("total") * p - 1e-9)), F.col("v")))
```

`cum` là số chuyến có delay ≤ v. Phân vị `p` là giá trị `v` nhỏ nhất mà `cum` đạt tới hạng `ceil(total × p)` (phương pháp hạng gần nhất). Vì delay là số phút nguyên và mỗi `v` chỉ một dòng, kết quả **chính xác**, không phải xấp xỉ (đã đối chiếu với numpy trên dữ liệu thử, khớp mọi giá trị).

**Advanced aggregation functions** dùng trong code:

| Hàm | Dùng ở | Tác dụng |
|---|---|---|
| Aggregation có điều kiện `F.sum(F.when(cond, 1).otherwise(0))` | `_add_exprs` (3) | Tính 24 cột đếm/tổng cộng được trong **một lượt** `groupBy` |
| `F.countDistinct("year","month","day")` | `rollup` (3) | Số ngày có dữ liệu (`n_days`) |
| `F.sum(F.col("share") ** 2)` | `concentration` (7) | Chỉ số tập trung HHI |
| Tổng bình phương `sum(v²·n)` | `box_from_hist` (4) | Độ lệch chuẩn chính xác từ biểu đồ tần suất |
| `F.first` | `pivot` (7) | Lấy giá trị duy nhất của ô |

**Vì sao dùng ở đây:** một lượt quét dữ liệu thô cho nhiều chỉ số, và window giúp tính xu hướng, xếp hạng, nền trượt mà không phải gộp dòng rồi join lại.

**Ví dụ kết quả** (box-plot delay đến, mọi chuyến đã bay, theo năm): năm 2022 có `q1 = -14`, `median = -5`, `q3 = 10`, `whisker_high = 46`, `p99 = 199`.

### 1.2. Pivot và unpivot

**Pivot** xoay giá trị của một cột thành các cột. **Unpivot** làm ngược lại.

**Pivot: `month_matrix`, `carrier_matrix` (cell 7)**

```python
k.groupBy("month").pivot("year", years).agg(F.first(metric))
```

- Truyền sẵn danh sách `years`. Nếu không, Spark phải chạy thêm một job để dò các giá trị phân biệt.
- Dùng `F.first` vì mỗi ô `(month, year)` chỉ có đúng một giá trị.
- Kết quả: ma trận tháng × năm (so cùng tháng qua các năm), hoặc hãng × năm.

**Unpivot: `unpivot_causes` (cell 7)**

```python
stack(5, 'carrier', cause_carrier, 'weather', cause_weather, 'nas', cause_nas,
         'security', cause_security, 'late_aircraft', cause_late_aircraft) as (cause, minutes)
```

- `stack(n, tên1, cột1, ...)` biến 5 cột nguyên nhân (dạng rộng) thành 5 dòng `(cause, minutes)` (dạng dài), rồi tính `share = minutes / cause_total`.
- Dạng dài là dạng thư viện vẽ (biểu đồ cột chồng, tỷ trọng) cần. Từ Spark 3.4 cũng có `DataFrame.unpivot`, nhưng `stack` chạy được ở mọi phiên bản 3.x.

### 1.3. Custom aggregation functions

Spark không có UDAF thuần Python kiểu cũ. Cách làm hiện nay là **pandas grouped-aggregate UDF** (nhận một `pd.Series` cho mỗi nhóm, trả về một số). Notebook có ba kiểu "tự định nghĩa phép gộp":

**a) Trung bình cắt `trimmed_mean` (cell 9)**

```python
@F.pandas_udf("double")
def trimmed_mean(v: pd.Series) -> float:
    v = v.dropna()
    lo, hi = v.quantile(0.01), v.quantile(0.99)
    return float(v[(v >= lo) & (v <= hi)].mean())
```

- Dữ liệu mỗi nhóm được chuyển sang Python theo lô Arrow. Mỗi nhóm phải vừa RAM, ở đây chỉ gồm một hãng trong một năm.
- Hạn chế: **không trộn được** với hàm gộp thường trong cùng một `agg`, nên tính riêng rồi `join`.
- Lý do nghiệp vụ: delay có đuôi dài nên trung bình bị kéo lệch. Ví dụ B6 năm 2022: `mean = 18,72`, `median = -2`, `trimmed_mean = 15,01`. Trung bình cắt nằm giữa hai số kia và bền hơn với ngoại lệ.

**b) Phép gộp "cộng được": `rollup` và `finalize` (cell 3)**

Đây là phép gộp tự định nghĩa quan trọng nhất của notebook. Mỗi chỉ số được tách thành các thành phần **cộng được** (đếm, tổng), rồi:
- `rollup(base, keys)` cộng các thành phần theo khóa thô hơn (ngày → tháng → năm).
- `finalize` tính tỷ lệ từ tổng.

Ví dụ: tỷ lệ đúng giờ của cả năm là `sum(on_time) / sum(flights)`, **không** phải trung bình của 12 tỷ lệ tháng (sai khi các tháng có số chuyến khác nhau).

**c) Phân vị từ biểu đồ tần suất: `box_from_hist` (cell 4)**

Phân vị không cộng được, nhưng "số chuyến có delay đúng v phút" thì cộng được. Nên mỗi tháng chỉ tính biểu đồ tần suất một lần (`build_hist`), còn mọi mức ngày, tháng, năm chỉ cần cộng rồi đọc phân vị. Cách này thay cho `percentile_approx` quét lại toàn bộ dữ liệu thô ở mỗi mức.

**d) Chỉ số tự định nghĩa `reliability_score` (cell 3)**

```python
100 * (1 - (0.50 * delay15_rate + 0.20 * severe60_rate + 0.25 * cancel_rate + 0.05 * divert_rate))
```

Kẹp trong 0 đến 100. Đây là biểu thức cột tổng hợp nhiều tỷ lệ, không phải chuẩn ngành. Trọng số chỉnh ở cell 1.

---

## 2. Advanced Transformations

### 2.1. Nhiều giai đoạn biến đổi

Luồng dữ liệu của notebook là một chuỗi giai đoạn, mỗi giai đoạn **ghi kết quả trung gian** xuống Parquet:

```text
Parquet thô ─ prepare ─► kpi_base ─► [ghi base/]  ─ rollup ─► finalize ─► [ghi kpi/]
                    └──► build_hist ─► [ghi base/hist] ─ box_from_hist ─► [ghi box/]
```

| Giai đoạn | Việc làm | Hàm (cell) |
|---|---|---|
| 1. Chuẩn hóa | Chọn cột, ép kiểu, xử lý null, tạo cột dẫn xuất | `prepare` (2) |
| 2. Tổng hợp cơ sở | `groupBy` các cột cộng được theo từng khóa | `kpi_base` (3) |
| 3. Cuộn lên | Cộng lại theo khóa thô hơn | `rollup` (3) |
| 4. Tính tỷ lệ | Chia tổng cho tổng | `finalize` (3) |
| 5. Box-plot | Window → aggregate → join → aggregate → union | `box_from_hist` (4) |

**Vì sao ghi trung gian:** mỗi giai đoạn sau chỉ đọc bảng nhỏ vừa ghi. Nhờ đó thêm một tháng mới chỉ tốn công của đúng tháng đó, và chạy lại được sau khi bị ngắt.

### 2.2. Chuỗi thao tác phức tạp

- **`finalize` (cell 3):** tạo một `dict` gồm 16 biểu thức tỷ lệ (sau đó thêm 5 tỷ trọng nguyên nhân) rồi gọi **một lần** `df.select("*", *[v.alias(k) for k, v in rates.items()])`. Cách này gọn hơn nhiều so với hàng chục `withColumn` nối tiếp, vì mỗi `withColumn` thêm một nút vào plan và làm bước phân tích chậm đi.
- **`prepare` (cell 2):** chuỗi `withColumn` dùng `F.when` không có `otherwise` (cho ra `null` khi sai điều kiện). Đây là chỗ cài đặt quy tắc null:

```python
.withColumn("arr_delay_ok", F.when(F.col("operated") == 1, F.col("arr_delay")))   # hủy/chuyển hướng → null
```

- **`box_from_hist` (cell 4):** window → `groupBy` → `withColumn` (hàng rào Tukey) → `join` (broadcast) → `groupBy` (đầu râu, ngoại lệ) → `join` → `unionByName` (hai tập `all` và `late`).
- **`build_hist` (cell 4):** `unionByName` hai luồng `arr` và `dep` rồi `groupBy` đếm theo giá trị.
- **Bộ dò tên cột (cell 2):** dict `COLS` khai báo các tên ứng viên cho mỗi trường logic, nên tên cột khác nhau giữa các lần tải vẫn chạy được.

### 2.3. Custom UDFs cho logic nghiệp vụ

**Python UDF `severity_udf` (cell 9)** phân mỗi chuyến vào tầng mức độ nghiêm trọng (`1_cancelled`, `2_diverted`, `3_early`, `4_ontime`, `5_minor`, `6_moderate`, `7_major`, `8_severe`).

Cách kiểm tra đúng đắn: so với biểu thức Spark tham chiếu `severity_expr()` làm bằng `F.when(...)`. Kết quả lần chạy của nhóm: **0 dòng lệch / 537.902 dòng**.

**Cách UDF hoạt động và cái giá:**
- Spark gửi từng dòng sang tiến trình Python, tính, rồi gửi kết quả về JVM. Tốn chi phí chuyển đổi dữ liệu.
- Bộ tối ưu Catalyst **không nhìn thấy bên trong** UDF, nên không đẩy bộ lọc xuống Parquet được.

**Bằng chứng (`evidence_optimization`, cell 9):** cùng một bộ lọc "chuyến trễ từ 15 phút":

| | Bộ lọc bằng biểu thức Spark | Bộ lọc bằng UDF |
|---|---|---|
| `PushedFilters` trong plan | `[IsNotNull(ARR_DELAY), GreaterThanOrEqual(ARR_DELAY,15.0)]` | `[]` (rỗng) |
| Kết quả | 97.052 chuyến | 97.052 chuyến (giống hệt) |
| Thời gian (1 tháng) | 1,77 giây | 1,71 giây |

Thời gian gần bằng nhau vì chỉ một tháng. Khác biệt thật nằm ở plan: UDF buộc đọc toàn bộ dữ liệu, và sẽ lộ rõ khi dữ liệu lớn hơn.

**Nguyên tắc:** ưu tiên hàm có sẵn của Spark; chỉ dùng UDF khi logic không biểu diễn được bằng biểu thức. Nếu phải dùng, ưu tiên pandas UDF (vector hóa qua Arrow) thay vì UDF theo từng dòng.

---

## 3. Join Operations

**Chọn chiến lược join.** Spark chọn một trong các chiến lược chính: `BroadcastHashJoin`, `SortMergeJoin`, `ShuffledHashJoin`, `BroadcastNestedLoopJoin`. Việc chọn dựa vào kích thước bảng (ngưỡng `spark.sql.autoBroadcastJoinThreshold`, mặc định 10 MB) và các gợi ý (hint) trong code. Khi chạy thực tế, AQE có thể đổi chiến lược lúc chạy. Vì vậy `evidence_joins` **tắt AQE tạm thời** để plan hiển thị đúng chiến lược đã chọn.

### 3.1. Broadcast join (bảng lệch kích thước)

**Cách hoạt động:** bảng nhỏ được gửi nguyên bản đến mọi executor và nạp vào bảng băm trong bộ nhớ. Bảng lớn **không bị shuffle**, mỗi partition của nó tra bảng băm cục bộ.

**Dùng ở đâu:**

| Bảng nhỏ | Bảng lớn | Hàm |
|---|---|---|
| Tên hãng (`carrier_lookup`) | KPI hãng theo năm | `carrier_ranking` (7) |
| Lịch ngày lễ (`holiday_df`) | KPI theo ngày | `daily_anomalies`, `holiday_effect` (7) |
| Nhóm sân bay (`tier`) | Bảng tuyến | `enrich_routes` (7) |
| Hàng rào Tukey (`fences`, mỗi nhóm một dòng) | Biểu đồ tần suất | `box_from_hist` (4) |

```python
r.join(F.broadcast(tier), "origin")      # gợi ý broadcast tường minh
```

**Giới hạn:** bảng được broadcast phải vừa bộ nhớ của driver và executor. Broadcast một bảng lớn sẽ gây hết bộ nhớ.

### 3.2. Sort-merge join (dữ liệu lớn)

**Cách hoạt động:** (1) shuffle **cả hai** bảng theo khóa join, (2) sắp xếp mỗi partition theo khóa, (3) duyệt song song hai phía đã sắp xếp để ghép. Không cần nạp bảng nào vào bộ nhớ, và có thể ghi tạm xuống đĩa. Đó là lý do nó chịu được hai bảng đều lớn.

**Dùng ở đâu:** `route_excess_delay(hint="merge")` (cell 7). Ghép KPI tuyến theo năm với KPI sân bay đi theo năm trên khóa `(year, origin)`, để tìm tuyến trễ **nhiều hơn mức nền** của sân bay xuất phát:

```python
r.hint("merge").join(o.hint("merge"), ["year", "origin"])
excess_delay = route_delay - origin_baseline
```

**Bằng chứng (`evidence_joins`, cell 9):**

| Chiến lược | Số dòng | Thời gian |
|---|---|---|
| `BroadcastHashJoin` | 21.477 | 0,37 giây |
| `SortMergeJoin` | 21.477 | 0,55 giây |

Hai chiến lược cho **cùng số dòng**. Với bảng nhỏ như ở đây broadcast nhanh hơn. Sort-merge chỉ có lợi khi **cả hai** bảng đều lớn (ví dụ ghép hai bảng sự kiện hàng chục triệu dòng). Plan chi tiết ở `evidence\join_broadcast.txt` và `evidence\join_merge.txt`.

### 3.3. Tối ưu nhiều join

`enrich_routes` (cell 7) ghép liên tiếp ba bảng vào bảng tuyến: tier sân bay đi, tier sân bay đến, mức nền sân bay đi.

Các nguyên tắc áp dụng:
1. **Join sau khi đã tổng hợp.** Các bảng ghép (`year_route`, `year_origin`) đã là KPI theo năm (hàng chục nghìn dòng), không phải 29 triệu dòng thô.
2. **Hai bảng tra nhỏ dùng broadcast** (không tốn shuffle), chỉ phép ghép còn lại dùng shuffle join.
3. **Kiểm tra không nhân bản dòng.** Hàm đếm số dòng trước và sau join, nếu khác nhau thì cảnh báo. Join lệch khóa (khóa trùng ở bảng phải) âm thầm nhân dòng, làm sai mọi tổng sau đó:

```python
print(f"enrich_routes: {n0} dòng trước join, {n1} sau join → {'OK, không nhân bản' if n0 == n1 else 'CẢNH BÁO'}")
```

4. **Self-join thay cho `lag`** khi cần so với kỳ trước mà có thể thiếu kỳ: `carrier_yoy` ghép bảng với chính nó trên `year + 1`, `monthly_trend` trên `t + 12`.
5. **Tổng rồi join ngược** để tính tỷ trọng: `concentration` tính tổng chuyến của sân bay, join ngược vào từng hãng để ra `share`, rồi mới tính HHI.
6. `crossJoin` chỉ dùng với bảng **một dòng** (giá trị toàn kỳ ở `seasonality`, nền "ngày thường" ở `holiday_effect`), nên không gây bùng nổ dòng.

---

## 4. Performance Optimization

### 4.1. Partition pruning và bucketing

**Partition pruning.** Dữ liệu đã xử lý nằm ở `/aero/processed/year=YYYY/month=MM/`. Khi truy vấn lọc theo `year`/`month`, Spark chỉ đọc đúng thư mục tương ứng.

- `load_months` (cell 2) dựng danh sách đường dẫn thư mục theo tháng và đặt `option("basePath", ...)` để các cột `year`, `month` vẫn xuất hiện.
- `build_month` (cell 5) vì vậy chỉ đọc đúng một tháng mỗi lượt.
- Ngoài ra, Parquet là định dạng cột nên `prepare` chỉ chọn các cột cần (column pruning), và các bộ lọc đơn giản được đẩy xuống file (predicate pushdown).

**Bằng chứng (`evidence_pruning`, cell 9):**

| | Số phân vùng quét |
|---|---|
| Không lọc | 329 |
| Lọc `year = 2022 and month = 1` | 7 |

Plan có dòng `PartitionFilters: [isnotnull(year), isnotnull(month), (year = 2022), (month = 1)]`.

**Bucketing.** Dữ liệu được chia sẵn vào một số "xô" cố định theo giá trị băm của một cột, và ghi cùng thông tin xô vào metadata. Sau đó `groupBy` hoặc join trên chính cột đó **không cần shuffle**.

```python
df.write.bucketBy(8, "carrier").sortBy("carrier").saveAsTable("aero_bts_bucketed")
```

**Bằng chứng (`evidence_bucketing`, cell 9):** số `Exchange` (shuffle) trong plan của `groupBy("carrier")` giảm từ **2 xuống 0**; thời gian 2,21 giây giảm còn 0,52 giây (một lần đo, chỉ mang tính tham khảo).

| | Partitioning (`partitionBy`) | Bucketing (`bucketBy`) |
|---|---|---|
| Cột phù hợp | Ít giá trị (năm, tháng) | Nhiều giá trị (hãng, sân bay, mã chuyến) |
| Tạo ra | Thư mục theo giá trị | Số file cố định theo băm |
| Lợi ích | Bỏ qua cả thư mục khi lọc | Bỏ shuffle khi gom nhóm hoặc join theo cột đó |

**Lưu ý khi dùng bucketing:**
- Cần `saveAsTable` (có catalog). Metadata trong catalog mặc định chỉ sống trong session, nên notebook xóa bảng sau khi đo.
- Phải trả chi phí shuffle **một lần** lúc ghi. Chỉ đáng khi cùng một bảng được join hoặc gom nhóm theo cột đó nhiều lần.
- Bảng được ghi vào warehouse trên HDFS (`hdfs://namenode:9000/aero/warehouse`).

### 4.2. Cache và persistence

**Cache/persist** giữ một DataFrame trong bộ nhớ (và/hoặc đĩa) sau lần tính đầu tiên, để các action sau khỏi tính lại từ đầu. Spark tính **lười**, nên nếu không cache, mỗi action đọc lại và chuẩn hóa lại dữ liệu từ đầu.

**Dùng ở `build_month` (cell 5):**

```python
df = prepare(load_months([(y, m)])).persist(StorageLevel.MEMORY_AND_DISK)
n = df.count()                          # ép tính ngay để điền cache
# ... 5 bảng KPI cơ sở + biểu đồ tần suất cùng dùng df ...
df.unpersist()                          # giải phóng sau khi xong tháng
```

- DataFrame của một tháng được dùng cho 6 phép tổng hợp, nên cache tránh đọc và chuẩn hóa lại 6 lần.
- `MEMORY_AND_DISK`: nếu thiếu RAM thì tràn xuống đĩa thay vì tính lại.
- `unpersist()` sau mỗi tháng để tháng sau có RAM.

**Bằng chứng (`evidence_cache`, cell 9)** chạy 3 truy vấn lặp lại, 3 lần:

| | Thời gian |
|---|---|
| Không cache | 2,21 giây |
| Điền cache (một lần) | 0,12 giây |
| Có cache, 3 lần chạy | 1,38 giây |

Nhanh hơn khoảng 1,6 lần trên một tháng. Lợi ích tăng theo số lần tái sử dụng và độ tốn kém của bước tính phía trước.

**Persistence ở mức pipeline.** Các bảng `base/` được ghi xuống Parquet trên HDFS (bền vững), khác với cache (mất khi session kết thúc). Nhờ đó pipeline **chạy tiếp được sau khi bị ngắt**: `month_built` kiểm tra thư mục `base/hist/year=/month=` đã có chưa, nếu có thì bỏ qua tháng đó.

**Khi không nên cache:** DataFrame chỉ dùng một lần, hoặc quá lớn so với RAM.

### 4.3. Tối ưu truy vấn và execution plan

**Đọc execution plan.** `plan_text(df)` gọi `df.explain("formatted")` và trả chuỗi (lưu vào `evidence\*.txt`). Các nút cần để ý:

| Nút trong plan | Ý nghĩa |
|---|---|
| `Scan parquet` + `PartitionFilters` | Thư mục nào được đọc |
| `PushedFilters` | Bộ lọc nào đã đẩy xuống Parquet |
| `ReadSchema` | Chỉ những cột nào được đọc |
| `Exchange` | **Shuffle**, bước tốn kém nhất, càng ít càng tốt |
| `HashAggregate` (partial/final) | Gộp hai pha để giảm dữ liệu shuffle |
| `BroadcastHashJoin` / `SortMergeJoin` | Chiến lược join |

**Các tối ưu áp dụng trong notebook:**

| # | Tối ưu | Ở đâu | Hiệu quả |
|---|---|---|---|
| 1 | Tính cột cộng được **một lần mỗi tháng**, các mức khác chỉ cộng lại | `kpi_base`, `rollup` | Mỗi tháng đọc dữ liệu thô một lần cho 5 bảng KPI cơ sở và biểu đồ tần suất |
| 2 | Phân vị từ biểu đồ tần suất thay cho quét lại dữ liệu thô | `box_from_hist` | Bỏ phần tốn nhất của bản cũ (box-plot năm và mùa vụ chiếm khoảng 1.090 giây trên tổng 1.405 giây khi chạy 3 tháng) |
| 3 | `spark.sql.shuffle.partitions = 8` (mặc định 200) | cell 1 | Ít tác vụ nhỏ hơn với dữ liệu nhỏ, `local[2]` |
| 4 | `coalesce(1)` trước khi ghi bảng nhỏ | `write_part`, `build_kpis` | Một file thay vì nhiều file nhỏ |
| 5 | `partitionOverwriteMode = dynamic` | cell 1 | Ghi lại một tháng chỉ thay đúng partition tháng đó |
| 6 | Một lần `select` thay cho nhiều `withColumn` | `finalize` | Plan gọn, phân tích nhanh hơn |
| 7 | Truyền sẵn giá trị cho `pivot` | `month_matrix` | Bỏ một job dò giá trị |
| 8 | Broadcast bảng tra nhỏ | mục 3.1 | Không shuffle bảng lớn |
| 9 | Bộ lọc bằng biểu thức Spark thay vì UDF | mục 2.3 | Giữ được pushdown |

**Kết quả tổng:** bản đầu của notebook chạy 3 tháng mất 1.405 giây. Bản gọn chạy 51 tháng (49 tháng build mới) mất khoảng 593 giây, tức khoảng 9 giây mỗi tháng. Hai số này đo ở hai lần chạy khác nhau của hai phiên bản trên cùng máy nhóm, nên là so sánh tham khảo, không phải benchmark có kiểm soát.

---

## 5. Streaming Processing

> **Trạng thái: chưa có trong notebook này.** `eda_lite.ipynb` chỉ xử lý batch. Streaming (Kafka → Spark Structured Streaming) thuộc phạm vi M3/M4. Phần dưới giải thích khái niệm và cách chúng sẽ được áp dụng trong thiết kế của nhóm, **không phải** kỹ thuật đã chạy và có bằng chứng.

### 5.1. Structured Streaming và các output mode

Structured Streaming coi luồng dữ liệu như một bảng **vô hạn, liên tục thêm dòng**, và chạy truy vấn theo từng lô nhỏ (micro-batch). **Output mode** quyết định phần kết quả nào được ghi ở mỗi lô:

| Mode | Ghi gì | Dùng khi | Dự kiến trong dự án |
|---|---|---|---|
| `append` | Chỉ các dòng **mới và đã chốt** | Sự kiện chuẩn hóa; tổng hợp theo cửa sổ thời gian khi đã có watermark (cửa sổ chỉ ghi sau khi watermark vượt qua) | Ghi sự kiện chuẩn hóa xuống HDFS |
| `update` | Chỉ các dòng **thay đổi** so với lô trước | KPI cập nhật liên tục (số chuyến, trễ trung bình đang chạy) | Cập nhật KPI vào MongoDB |
| `complete` | **Toàn bộ** bảng kết quả, mỗi lô | Bảng tổng hợp rất nhỏ | Hạn chế dùng, vì tốn bộ nhớ và ghi lại toàn bộ |

### 5.2. Watermark và dữ liệu đến muộn

Sự kiện có thể đến **muộn** hơn thời điểm xảy ra (event time) vì mạng chậm hoặc API trễ. **Watermark** là ngưỡng chấp nhận trễ: `max(event time đã thấy) − độ trễ cho phép`.

```python
events.withWatermark("event_time", "10 minutes")
```

- Sự kiện có event time **cũ hơn watermark** có thể bị bỏ qua.
- Cửa sổ thời gian nào đã hoàn toàn nằm trước watermark thì được chốt và Spark **dọn trạng thái** của nó.
- Đánh đổi: ngưỡng lớn thì ít mất dữ liệu muộn nhưng giữ trạng thái lâu, tốn bộ nhớ và chậm chốt kết quả; ngưỡng nhỏ thì ngược lại.

### 5.3. State management

Các phép tổng hợp theo cửa sổ và `dropDuplicates` là **có trạng thái**: Spark phải nhớ các tổng/khóa đã thấy giữa các lô.

- Trạng thái nằm trong bộ nhớ executor và được **checkpoint** định kỳ xuống `checkpointLocation` (dự kiến trên HDFS), để khôi phục khi job khởi động lại.
- Nếu **không có watermark**, trạng thái của tổng hợp theo cửa sổ **tăng vô hạn**. Watermark chính là cơ chế giới hạn trạng thái.
- Kích thước trạng thái là thứ cần theo dõi khi kiểm thử trên máy RAM hạn chế.

### 5.4. Đảm bảo exactly-once

Exactly-once là kết quả cuối **không mất và không trùng** dù job bị lỗi rồi chạy lại. Nó **không tự có** chỉ vì bật checkpoint, mà cần cả ba điều kiện:

1. **Nguồn phát lại được:** Kafka giữ message theo offset; checkpoint ghi lại offset đã xử lý để chạy lại từ đúng vị trí.
2. **Xử lý xác định:** cùng đầu vào cho cùng kết quả.
3. **Đích idempotent hoặc có giao dịch:** ghi file của Spark dùng commit log nên an toàn khi chạy lại. Với MongoDB, ghi bằng **upsert theo khóa tự nhiên** (ví dụ mã chuyến + thời điểm sự kiện) để ghi lại lô cũ không sinh bản trùng.

Nếu producer gửi trùng message, cần thêm khử trùng (`dropDuplicates` theo mã sự kiện kèm watermark).

**Cách chứng minh (kế hoạch kiểm thử cho M4):** dừng job giữa chừng, khởi động lại, rồi đối chiếu số bản ghi và kiểm tra không có khóa trùng trong đích.

### 5.5. Phác thảo thiết kế (chưa chạy thử)

Chỉ để M4 tham khảo cấu trúc, **chưa kiểm thử**. Cần nạp gói Kafka khi `spark-submit` (ví dụ `--packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.3`):

```python
events = (spark.readStream.format("kafka")
          .option("kafka.bootstrap.servers", "kafka:9092")
          .option("subscribe", "flight-realtime").load())
# ... parse JSON → cột event_time, carrier, delay_minutes ...
agg = (events.withWatermark("event_time", "10 minutes")
       .groupBy(F.window("event_time", "5 minutes"), "carrier")
       .agg(F.count("*").alias("flights"), F.avg("delay_minutes").alias("avg_delay")))

def upsert_to_mongo(batch_df, batch_id):
    ...   # upsert theo (window.start, carrier): idempotent khi lô chạy lại

(agg.writeStream.outputMode("update").foreachBatch(upsert_to_mongo)
    .option("checkpointLocation", "hdfs://namenode:9000/aero/checkpoints/flight_kpi").start())
```

---

## Ghi chú trung thực về phạm vi

- **PageRank sân bay** (`airport_network`) tính ở **driver** bằng numpy trên đồ thị nhỏ (khoảng vài trăm nút), không phải thuật toán đồ thị phân tán. GraphFrames **chưa dùng**.
- **MLlib** chưa có trong notebook này.
- **Streaming** chưa có (mục 5).
- Các số thời gian chỉ mang tính tham khảo. Khi đưa vào báo cáo, nên chạy lại bằng chứng ở cell 9 và dùng đúng số của lần chạy cuối.
