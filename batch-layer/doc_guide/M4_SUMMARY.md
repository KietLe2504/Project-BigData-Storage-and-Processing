# M4 — Spark Structured Streaming: Kafka → MongoDB

**Dự án:** AERO — Big Data Storage and Processing  
**Mã xử lý:** `batch-layer/spark_jobs/m4_flight_status.py`  
**Runtime:** Apache Spark 3.5.3  
**Kafka connector:** `org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.3`  
**MongoDB:** database `aero_m5`, collection `stream_window_kpi`  
**Phạm vi tài liệu:** triển khai, chạy, kiểm tra và vận hành M4. Tài liệu giả định Kafka đã có flight observations hợp lệ; không hướng dẫn khởi động hoặc cấu hình các bước trước M4.

---

## 1. Mục tiêu và luồng xử lý

M4 đọc JSON flight-status observations từ Kafka, parse và lọc sự kiện, gán event time, tổng hợp KPI theo cửa sổ thời gian và các cấp dimension, sau đó ghi **full aggregate** vào MongoDB thông qua writer của M5.

```text
Kafka: flight-realtime
        |
        v
M4 — Spark Structured Streaming 3.5.3
  1. Đọc Kafka value và parse JSON
  2. Lọc event hợp lệ và source được cho phép
  3. Dùng observed_at làm event time
  4. Watermark + tumbling window 5 phút
  5. Mở rộng 8 grouping sets
  6. Chọn observation mới nhất theo flight_key
  7. Tính full-window KPI
  8. Tạo revision bền vững qua MongoDB
        |
        v
M5: m5.stream_writer.write_window(...)
        |
        v
MongoDB: aero_m5.stream_window_kpi
        |
        v
M5 Dashboard — trang Streaming
```

M4 không ghi raw Kafka messages vào MongoDB và không gửi delta. Mỗi document là aggregate đầy đủ cho một `source` + window + tổ hợp `dimensions`.

## 2. Đầu vào Kafka

| Thuộc tính | Giá trị |
|---|---|
| Topic | `flight-realtime` |
| Bootstrap bên trong Docker | `kafka:9092` |
| Message value | JSON UTF-8 |
| Schema version | `1` |
| Event type | `flight_status_observation` |
| Source mặc định | `aviationstack` |

M4 dùng schema tường minh để đọc các trường liên quan:

- Định danh và provenance: `schema_version`, `source`, `event_type`, `flight_key`, `event_id`.
- Thời gian: `observed_at`.
- Dimension: `airline_iata`, `departure_iata`, `arrival_iata`.
- Trạng thái và delay: `flight_status`, `departure_scheduled`, `departure_delay`.

Một record chỉ được đưa vào xử lý khi:

1. `schema_version == 1`;
2. `event_type == "flight_status_observation"`;
3. `source` nằm trong `M4_ALLOWED_SOURCES`;
4. `flight_key` không null;
5. `observed_at` parse được thành timestamp;
6. `departure_iata` và `arrival_iata` không null.

`M4_ALLOWED_SOURCES=aviationstack` chỉ xử lý dữ liệu AviationStack, không trộn record mô phỏng `simulated` vào kết quả live.

### Event time

M4 lấy `observed_at` làm `event_time`. Đây là thời điểm quan sát/poll dữ liệu, không nhất thiết là thời điểm trạng thái chuyến bay thay đổi ngoài thực tế. Spark session timezone được đặt thành UTC; `window_start` và `window_end` được ghi sang MongoDB dưới dạng ISO timestamp UTC có hậu tố `Z`.

## 3. Cấu hình streaming

Các biến môi trường trong M4:

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `M4_PIPELINE_ID` | `m4-flight-status-v1` | Định danh pipeline lưu trong MongoDB |
| `M4_WINDOW_DURATION` | `5 minutes` | Độ dài tumbling event-time window |
| `M4_WATERMARK_DELAY` | `10 minutes` | Watermark dùng quản lý state và sự kiện đến muộn |
| `M4_PROCESSING_TIME` | `10 seconds` | Chu kỳ trigger micro-batch |
| `M4_CHECKPOINT` | `hdfs://aero-namenode:9000/aero/checkpoints/m4/flight-status-v1` | Checkpoint HDFS |
| `M4_KAFKA_BOOTSTRAP` | `kafka:9092` | Kafka broker trong Docker network |
| `M4_KAFKA_TOPIC` | `flight-realtime` | Kafka input topic |
| `M4_ALLOWED_SOURCES` | `aviationstack` | Source được phép; nhiều giá trị phân tách bằng dấu phẩy |
| `M4_SHUFFLE_PARTITIONS` | `3` | Số Spark shuffle partitions |

### Cách hoạt động

- **Window 5 phút:** mỗi event được gán vào một tumbling window theo `observed_at`.
- **Watermark 10 phút:** giúp Spark giới hạn state. Event đến trễ hơn watermark hiện tại có thể không còn được đưa vào kết quả.
- **Trigger 10 giây:** Spark cố gắng chạy micro-batch theo nhịp này; thời lượng thực tế phụ thuộc thời gian xử lý.
- **`outputMode("update")`:** sink nhận các window/group có thay đổi trong micro-batch.
- **`foreachBatch(write_batch)`:** chuyển kết quả mỗi micro-batch sang Python và ghi qua M5 writer.
- **Checkpoint HDFS:** lưu tiến độ và trạng thái xử lý của Structured Streaming.

**Quy tắc checkpoint:** khi restart cùng một query, giữ nguyên `M4_CHECKPOINT`. Không xóa checkpoint để xử lý lỗi khởi động thông thường. Khi thay đổi cấu trúc stateful aggregation hoặc muốn chạy một pipeline độc lập, tạo checkpoint path mới và lưu ý query mới có thể đọc lại Kafka từ offset khởi đầu.

## 4. Đếm chuyến và chọn observation mới nhất

Đơn vị đếm là một `flight_key` trong cùng `source`, event-time window và dimension group.

Một chuyến có thể phát nhiều observations trong cùng window. Hàm `latest_by_flight()` chỉ giữ observation có thứ tự lớn nhất theo:

```text
(event_time, event_id)
```

`event_id` dùng để phân định ổn định nếu hai observations có cùng timestamp. Status và delay của observation mới nhất được sử dụng để tính KPI.

Lưu ý:

- Nhiều observations của một `flight_key` trong cùng window không làm tăng `flights` nhiều lần.
- Một chuyến có thể xuất hiện ở các window 5 phút khác nhau; M4 không khử trùng xuyên suốt toàn bộ vòng đời chuyến bay.
- Đây là đếm flight instance trong từng window, không phải số lượng Kafka messages.

## 5. Tám cấp dimension grouping

Mỗi event được mở rộng thành tối đa tám grouping sets trên ba dimension:

- `carrier` ← `airline_iata`
- `origin` ← `departure_iata`
- `dest` ← `arrival_iata`

| Scope nội bộ | Object `dimensions` được ghi sang M5 |
|---|---|
| `all` | `{}` |
| `carrier` | `{"carrier": "..."}` |
| `dest` | `{"dest": "..."}` |
| `origin` | `{"origin": "..."}` |
| `carrier_dest` | `{"carrier": "...", "dest": "..."}` |
| `carrier_origin` | `{"carrier": "...", "origin": "..."}` |
| `origin_dest` | `{"origin": "...", "dest": "..."}` |
| `carrier_origin_dest` | `{"carrier": "...", "origin": "...", "dest": "..."}` |

Dimension rỗng được chuẩn hóa thành null. Nếu một grouping cần dimension mà event không có, grouping đó bị bỏ qua. Ví dụ event thiếu carrier vẫn có thể đóng góp vào grouping `all`, `origin`, `dest`, `origin_dest`, nhưng không thể đóng góp vào grouping cần `carrier`.

`scope` là thông tin nội bộ để kiểm tra/log; M5 không cần trường top-level `scope`. Cấp grouping được thể hiện bởi các key hiện diện trong `dimensions`.

## 6. Định nghĩa KPI

Sau khi giữ observation mới nhất cho mỗi `flight_key`, M4 tính các metric:

| Metric | Định nghĩa |
|---|---|
| `flights` | Số `flight_key` phân biệt trong source/window/group |
| `cancelled` | Số chuyến có status `cancelled` hoặc `canceled` |
| `diverted` | Số chuyến có status `diverted` |
| `on_time` | Số chuyến có `departure_scheduled` hợp lệ và `departure_delay < 15` phút |
| `delayed15` | Số chuyến có `departure_scheduled` hợp lệ và `departure_delay >= 15` phút |
| `delayed60` | Số chuyến có `departure_scheduled` hợp lệ và `departure_delay >= 60` phút |
| `sum_dep_delay` | Tổng số phút departure delay dương; delay âm/đến sớm đóng góp 0 |

Các quy tắc:

1. Các metric đúng giờ/trễ sử dụng **departure delay**, không phải arrival delay.
2. Chỉ tính nhóm punctuality khi `departure_scheduled` parse được và `departure_delay` là số hữu hạn, không null.
3. `departure_actual` không được dùng trong phép tính hiện tại.
4. Các ngưỡng là cumulative: delay từ 60 phút trở lên cũng được tính vào `delayed15`.
5. Delay âm hoặc bằng 0 được tính là `on_time`.
6. `flights` bao gồm chuyến hủy/chuyển hướng; `cancelled` và `diverted` là các nhóm con.
7. `on_time + delayed15` có thể nhỏ hơn `flights` do thiếu scheduled departure hợp lệ hoặc thiếu delay.
8. `sum_dep_delay` chỉ cộng phần delay dương, không trừ phút bay sớm.

Các metric trên phản ánh departure delay trong stream; không nên diễn giải chúng thành arrival-delay KPI của dữ liệu BTS lịch sử.

## 7. Hợp đồng output M4 → M5 và revision

Mỗi window/group được ghi thành record có đúng bảy trường top-level:

```json
{
  "pipeline_id": "m4-flight-status-v1",
  "source": "aviationstack",
  "window_start": "<UTC ISO timestamp>",
  "window_end": "<UTC ISO timestamp>",
  "revision": 1,
  "dimensions": {"carrier": "AA", "origin": "JFK"},
  "metrics": {
    "flights": 12,
    "cancelled": 1,
    "diverted": 0,
    "on_time": 7,
    "delayed15": 3,
    "delayed60": 1,
    "sum_dep_delay": 82.0
  }
}
```

Số liệu chỉ minh họa cấu trúc. Với grouping `all`, `dimensions` là `{}`.

### 7.1. Sinh revision

`write_full_window_with_revision()` thực hiện:

1. Gọi `normalize()` với revision tạm `0` để lấy logical `_id` ổn định từ `source`, `pipeline_id`, window và toàn bộ `dimensions`.
2. Tìm document hiện tại trong `stream_window_kpi` theo `_id`.
3. Nếu payload nghiệp vụ không đổi, trả `unchanged`, không ghi lại.
4. Nếu chưa có document, dùng revision `1`.
5. Nếu payload thay đổi, lấy revision hiện tại cộng `1`.
6. Gọi `write_window()` của M5 để thực hiện insert/update và version guard.

`batch_id` của Spark chỉ phục vụ log; không được dùng làm revision bền vững. Đây là thiết kế full-aggregate có kiểm soát replay/revision; chưa nên tuyên bố exactly-once end-to-end khi chưa kiểm thử restart, replay, late event, lỗi sink và concurrent writer.

## 8. Điều kiện cần có trước khi chạy M4

Các service liên quan cần đang chạy và có các kết nối sau:

| Thành phần | Tên/địa chỉ mà M4 sử dụng |
|---|---|
| Kafka | `kafka:9092` |
| MongoDB | `mongo:27017` |
| HDFS NameNode | `aero-namenode:9000` theo checkpoint trong lệnh chạy hiện tại |
| Script M4 | `/opt/spark_jobs/m4_flight_status.py` |
| Package M5 | `/opt/serving-layer`, được thêm vào `PYTHONPATH` |

Spark container cần:

- có Kafka connector đúng phiên bản Spark 3.5.3 (được nạp bằng `--packages` trong lệnh chạy);
- cài PyMongo trong Python environment mà `spark-submit` sử dụng;
- mount source code M5 tại `/opt/serving-layer`;
- cùng Docker network với Kafka và MongoDB.

Nếu mount M5 chưa được cấu hình, thêm dòng sau vào `volumes` của service `spark` trong `batch-layer/docker-compose.yml`:

```yaml
      - ../serving-layer:/opt/serving-layer:ro
```

Sau đó tạo lại riêng Spark để mount có hiệu lực:

```bash
docker compose -f batch-layer/docker-compose.yml up -d --force-recreate spark
```

Cài PyMongo nếu chưa có:

```bash
docker exec -u root aero-spark \
  python3 -m pip install --no-cache-dir 'pymongo>=4,<5'
```

Cài trực tiếp vào container phù hợp để kiểm thử nhanh; package có thể mất khi container được tạo lại. Khi ổn định, nên đưa dependency vào custom Spark image.

Kiểm tra MongoDB và package M5 từ Spark:

```bash
docker exec \
  -e PYTHONPATH=/opt/serving-layer \
  -e M5_MONGO_URI=mongodb://mongo:27017 \
  -e M5_DATABASE=aero_m5 \
  aero-spark \
  python3 -c 'from m5.mongo import connect; import pymongo; import m5.stream_writer as w; c, db = connect(); print("M5_REACHABLE", db.name, "PyMongo", pymongo.version, "WRITER", w.__file__); c.close()'
```

## 9. Chạy M4

Chạy từ thư mục gốc project với đúng command đang dùng:

```bash
docker exec \
  -e PYTHONPATH=/opt/serving-layer \
  -e M5_MONGO_URI=mongodb://mongo:27017 \
  -e M5_DATABASE=aero_m5 \
  -e M4_ALLOWED_SOURCES=aviationstack \
  -e M4_CHECKPOINT=hdfs://aero-namenode:9000/aero/checkpoints/m4/flight-status-v1 \
  aero-spark \
  /opt/spark/bin/spark-submit \
    --conf spark.jars.ivy=/tmp/.ivy2 \
    --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.3 \
    /opt/spark_jobs/m4_flight_status.py
```

Các tham số trong command:

| Tham số | Giá trị |
|---|---|
| `PYTHONPATH` | `/opt/serving-layer` để import package `m5` |
| `M5_MONGO_URI` | `mongodb://mongo:27017` |
| `M5_DATABASE` | `aero_m5` |
| `M4_ALLOWED_SOURCES` | `aviationstack` |
| `M4_CHECKPOINT` | `hdfs://aero-namenode:9000/aero/checkpoints/m4/flight-status-v1` |
| Kafka bootstrap/topic | `kafka:9092` / `flight-realtime` (giá trị mặc định trong code) |
| Kafka connector | `spark-sql-kafka-0-10_2.12:3.5.3` |

Khi query bắt đầu, log dự kiến có `M4_STARTED` cùng thông tin topic, bootstrap, source filter, window, watermark và checkpoint. Khi một aggregate được ghi, log `M4_WINDOW` thể hiện source, thời gian window, dimensions và trạng thái ghi như `inserted`, `updated` hoặc `unchanged`.

`docker exec` chạy query ở foreground. Dùng `Ctrl+C` để dừng tiến trình M4. Khi muốn kiểm tra dữ liệu mới, để M4 tiếp tục chạy trong terminal này và đảm bảo Kafka nhận được observations mới. Nếu producer không publish record mới (ví dụ state không đổi), M4 có thể không tạo batch aggregate mới.

## 10. Kiểm tra MongoDB

Mở terminal khác và chạy:

```bash
docker exec aero-serving-mongo-1 mongosh --quiet --eval '
const dbTest = db.getSiblingDB("aero_m5");
dbTest.stream_window_kpi.find(
  {},
  {
    _id: 0,
    pipeline_id: 1,
    source: 1,
    window_start: 1,
    window_end: 1,
    revision: 1,
    dimensions: 1,
    metrics: 1
  }
).sort({window_end: -1}).limit(10).forEach(printjson);
'
```

Lưu ý: lệnh trên truy vấn database `aero_m5`; tên biến `dbTest` chỉ là biến JavaScript, không có nghĩa dữ liệu nằm trong database test riêng.

Kiểm tra:

- Collection `stream_window_kpi` có document từ M4.
- `source` là `aviationstack` với cấu hình chạy hiện tại.
- Document có đúng bảy trường top-level: `pipeline_id`, `source`, `window_start`, `window_end`, `revision`, `dimensions`, `metrics`.
- `window_start` và `window_end` có timezone UTC, `window_start < window_end`.
- `dimensions` phù hợp với một trong tám grouping levels.
- `metrics` có `flights`, `cancelled`, `diverted`, `on_time`, `delayed15`, `delayed60`, `sum_dep_delay`.
- Khi cùng logical window/group thay đổi, revision tăng; khi payload không đổi, M4 bỏ qua lần ghi đó.

Để dùng database riêng khi thử nghiệm, đổi `M5_DATABASE` trong lệnh chạy sang database test (ví dụ `aero_m5_m4_test`) và đổi tên database trong lệnh `mongosh` cho khớp. Không dùng database dashboard cho fixture thử nghiệm nếu không muốn chúng xuất hiện trên giao diện.

## 11. Kiểm tra Dashboard

Mở dashboard M5 tại:

```text
http://localhost:8501
```

Chọn trang **Streaming**. Trang này đọc collection `stream_window_kpi`, tự refresh khoảng 10 giây và hiển thị độ mới của dữ liệu. Nếu MongoDB chưa có document M4 thì dashboard chưa có aggregate streaming để hiển thị.

## 12. Dừng, restart và xử lý lỗi

### Dừng và restart

- Dừng M4 bằng `Ctrl+C` tại terminal chạy `spark-submit`.
- Khi restart cùng pipeline và không thay đổi stateful aggregation, giữ nguyên checkpoint path.
- Không xóa checkpoint để khắc phục lỗi thông thường.
- Nếu thay đổi stateful aggregation/grouping sets hoặc muốn chạy một pipeline độc lập, dùng checkpoint path mới; query mới có thể đọc lại dữ liệu từ offset ban đầu.
- Không đổi `M4_PIPELINE_ID`, database hoặc checkpoint path tùy tiện nếu muốn tiếp tục cùng pipeline logic.

Kiểm tra checkpoint trên HDFS:

```bash
docker exec aero-namenode hdfs dfs -ls -R /aero/checkpoints/m4
```

### Một số lỗi thường gặp

| Triệu chứng | Việc cần kiểm tra |
|---|---|
| Spark không resolve `kafka` | Spark và Kafka có cùng Docker network không; kiểm tra `docker inspect aero-spark` và `docker inspect aero-kafka` |
| Spark không resolve `mongo` | MongoDB có được nối vào batch network với alias `mongo` không |
| `No module named 'm5'` | Mount `/opt/serving-layer` và `PYTHONPATH` |
| `No module named 'pymongo'` | Cài PyMongo vào Python environment của Spark container |
| `Unsupported streaming metric` | Writer được import có cho phép `sum_dep_delay` không; kiểm tra `w.__file__` và hai lệnh `grep` |
| Có `M4_STARTED` nhưng không có `M4_WINDOW` | Kiểm tra Kafka có event mới, source filter, schema, `flight_key`, `observed_at` và các mã IATA |
| MongoDB có document nhưng dashboard không hiện | Xác nhận dashboard và M4 đang dùng cùng database `aero_m5`, collection `stream_window_kpi` |
| Event đến muộn không xuất hiện | Kiểm tra event time và watermark; event đã quá watermark có thể bị loại |
| Restart đọc lại hoặc ghi lại dữ liệu | Kiểm tra M4 có dùng lại đúng checkpoint không |

## 13. Checklist nghiệm thu M4

- [ ] Spark Structured Streaming khởi động và log `M4_STARTED` đúng cấu hình.
- [ ] Kafka connector Spark 3.5.3 đọc được `flight-realtime`.
- [ ] Spark import đúng M5 package và kết nối được MongoDB.
- [ ] Host writer và writer trong container đều chứa hỗ trợ `sum_dep_delay`.
- [ ] Log `M4_WINDOW` xuất hiện khi có event hợp lệ.
- [ ] MongoDB có document đúng bảy trường top-level, source, UTC window và dimensions.
- [ ] Các metric đúng theo định nghĩa departure-delay ở Mục 6.
- [ ] Tám grouping levels được tạo phù hợp với dimension có trong event.
- [ ] Replay payload không đổi không làm tăng revision; payload đổi làm revision tăng.
- [ ] Restart với checkpoint cũ phục hồi được query.
- [ ] Đã kiểm tra late event, lỗi sink và hành vi retry.
- [ ] Trang Streaming của Dashboard hiển thị dữ liệu và độ mới hợp lý.

Kafka connector smoke test đọc được 25 records trước đó chỉ chứng minh Spark có thể đọc topic bằng connector. Chỉ đánh dấu tích hợp M4 → M5 hoàn tất sau khi có log Structured Streaming, document MongoDB hợp lệ và xác nhận hiển thị ở Dashboard.

---

**Tóm tắt:** M4 là pipeline Spark Structured Streaming đọc flight observations từ Kafka, xử lý event-time theo cửa sổ 5 phút với watermark 10 phút, đếm flight instance phân biệt theo `flight_key`, tạo KPI ở tám cấp dimension, rồi ghi full-window aggregates có revision vào `aero_m5.stream_window_kpi` thông qua M5 writer.
