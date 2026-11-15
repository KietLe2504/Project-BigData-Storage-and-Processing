# AERO — M3 AviationStack API + Kafka: hướng dẫn chạy, xử lý lỗi và bàn giao M4

> **Phạm vi:** Tài liệu dành cho thành viên phụ trách API/Kafka (trong một số trao đổi gọi là M6). Mô tả kiến trúc toàn dự án để phối hợp M2/M5, nhưng **không** thay thế hướng dẫn chi tiết của hai nhóm. Kiểm tra theo GitHub `main` ngày 15/11/2026 và bằng chứng terminal do người thực hiện cung cấp. `streaming-layer` hiện là code trên máy/branch `feature/api-kafka-ingestion`, **chưa được xác minh trên GitHub `main`**; lệnh dưới đây dựa vào các tên file và hành vi đã được người thực hiện chạy thành công. Không coi các ví dụ output là log kiểm thử mới.

## 1. Mục tiêu và kiến trúc tổng thể

```text
                   LAMBDA ARCHITECTURE
BTS On-Time Performance CSV
  └─ M1: tải dữ liệu, HDFS /aero/raw/bts
       └─ M2: Spark Batch → /aero/processed → KPI/box Parquet trên HDFS
            └─ Export 20 bảng JSONL/CSV + manifest hoặc M5 đọc HDFS trực tiếp
                 └─ M5: MongoDB aero_m5 → Streamlit Dashboard :8501

AviationStack /v1/flights (dữ liệu thật; giới hạn theo gói)
  └─ M3: api_client.py → flight_schema.py → producer.py
       └─ Kafka topic flight-realtime (JSON message, 3 partitions)
            └─ M4: Spark Structured Streaming (CHƯA xác minh triển khai)
                 └─ event-time, dedup, watermark, window KPI, checkpoint
                      └─ M5: stream_writer.write_window → MongoDB stream_window_kpi
                           └─ Dashboard tab Streaming
```

**Quan hệ đầu vào/đầu ra:** M3 **không lấy dữ liệu từ M5**. M3 đọc AviationStack và bàn giao Kafka events cho M4. M5 đã có sẵn **đích nhận kết quả của M4** (`stream_writer.py`, contract, dashboard), chứ không gửi một bộ JSON đầu vào cho M3. Batch và Streaming chỉ hội tụ ở MongoDB/dashboard. Không tự join BTS với AviationStack theo flight number đơn lẻ: khác thời gian, nguồn và ngữ nghĩa.

### Hiện trạng đã xác minh

- Batch: người thực hiện đã chạy đến `06_batch_process_all.py`, `eda_lite.ipynb`; dashboard lịch sử đã mở. M2 trên GitHub xuất 13 KPI + 7 box, 51 tháng 2022-01 đến 2026-03. M5 README kỳ vọng 74.921 documents dữ liệu, 29.328.846 chuyến sau cleaning, 20 collections (metadata riêng).
- Serving: `mongo` + `dashboard` chạy và người thực hiện đã xem dashboard ở `http://localhost:8501`. Writer streaming có code và unit tests theo tài liệu, **chưa có bằng chứng M4 → M5 chạy thật**.
- M3: `aero-kafka` đã chạy; topic `flight-realtime` có 3 partitions; Python mock Producer/Consumer đã thành công; sau đó API Key hợp lệ được dùng và Consumer đã đọc **10 messages**, trong đó có `source: aviationstack`, `schema_version: 1`, `event_type: flight_status_observation`, `flight_iata`, `flight_key`, `observed_at`, `state_fingerprint`, `event_id`, Kafka offset 8 và 9 trong ảnh. Điều này xác nhận luồng API → Kafka → Consumer thực tế; chưa chứng minh retry/recovery/duplicate hay Spark sink.

## 2. Môi trường và cấu trúc thư mục

- Windows 11, PowerShell trong VS Code, Docker Desktop (Linux containers), Python venv.
- Thư mục repo của người thực hiện: `C:\Users\Acer\Project-BigData-Storage-and-Processing-1`.
- Batch Compose: `batch-layer/docker-compose.yml`; Serving Compose: `serving-layer/compose.yml`; Streaming Compose (trên branch làm việc): `streaming-layer/compose.yml`.
- Streaming file đã thấy: `.env.example`, `.gitignore`, `api_client.py`, `flight_schema.py`, `producer.py`, `consumer.py`, `tests/`, `compose.yml`.
- Kafka **Windows host**: `127.0.0.1:29092`; **giữa containers**: `kafka:9092`. Đừng thay một địa chỉ bằng địa chỉ kia một cách tùy tiện.
- `batch-layer_default` là network Compose thực tế người thực hiện đã nhìn thấy. Tên network có thể khác khi Compose project name đổi.

### Khởi động lại sau khi tắt máy

Trong **PowerShell VS Code**, ở thư mục repo:

```powershell
Set-Location 'C:\Users\Acer\Project-BigData-Storage-and-Processing-1'
docker version                     # phải có Client và Server
docker compose -f .\batch-layer\docker-compose.yml up -d
docker compose -f .\serving-layer\compose.yml up -d mongo dashboard
docker compose -f .\streaming-layer\compose.yml up -d kafka

docker compose -f .\batch-layer\docker-compose.yml ps
docker compose -f .\serving-layer\compose.yml ps
docker compose -f .\streaming-layer\compose.yml ps
```

Không cần tải lại 51 tháng BTS hoặc nạp lại MongoDB nếu HDFS/Mongo volumes vẫn còn và bộ dữ liệu đã được nghiệm thu. **Không chạy `docker compose down -v`** để dừng thông thường vì có thể xóa dữ liệu. Chỉ khởi động Jupyter khi thực sự cần chạy batch/EDA; M3 không cần Jupyter.

## 3. Dòng Batch M2 → M5 (để hiểu luồng, không phải phần cần chạy lại)

Theo `batch-layer/doc_guide/HUONG_DAN_BAN_GIAO_M2_M5.md`:

1. M1 tải BTS CSV và nạp HDFS `/aero/raw/bts`.
2. M2 chạy `06_batch_process_all.py`, `08_verify_partition.py` và build KPI bằng `eda_lite.ipynb`. Chỉ chạy `06` **chưa** tạo đủ KPI bàn giao.
3. HDFS tạo `kpi/` (13 bảng) và `box/` (7 bảng). M2 dùng `09_export_m2_outputs.py` tạo `batch-layer/spark_jobs/export/m2_to_m5/<UTC timestamp>/` gồm **20 CSV, 20 JSONL, 1 manifest.json**. Hoặc M5 dùng HDFS Spark adapter đọc Parquet trực tiếp.
4. M5 chạy `load_m2.ps1 -SnapshotPath <đường dẫn snapshot thật> -CheckOnly`, rồi load và `verify_m5.ps1`; MongoDB `aero_m5` cung cấp dữ liệu lịch sử cho dashboard.
5. Truy cập `http://localhost:8501`; tab Streaming **không tự xuất hiện dữ liệu live** nếu chưa có M4.

Ví dụ kiểm tra dữ liệu đầu vào M5 (chạy ở repo root):

```powershell
Get-ChildItem .\batch-layer\spark_jobs\export\m2_to_m5 -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 5 Name,FullName
# Chỉ chọn thư mục có manifest.json, không chọn thư mục cha
```

**Đầu ra M5 mà M3 có thể sử dụng:** một MongoDB/dashboard **đã sẵn sàng làm sink phục vụ**, cùng tài liệu hợp đồng `serving-layer/contracts/M4_TO_M5.md` và writer `serving-layer/m5/stream_writer.py`. M3 không nhận JSONL của M2 làm input; chỉ cần thống nhất schema với M4. Không ghi trực tiếp raw AviationStack event vào collection `stream_window_kpi` vì writer này nhận **full window aggregates**.

## 4. Chuẩn bị M3: Git, môi trường Python, Kafka

### 4.1. Branch an toàn

```powershell
Set-Location 'C:\Users\Acer\Project-BigData-Storage-and-Processing-1'
git branch --show-current
# Kỳ vọng: feature/api-kafka-ingestion
git status --short
```

Không sửa/commit nhầm `batch_data_bureau.ipynb`, `batch-layer/docker-compose.yml`, `eda_lite.ipynb` nếu đó là thay đổi thử nghiệm của nhóm khác. Không `git add .` khi chưa kiểm tra.

### 4.2. Venv và dependency

```powershell
Set-Location .\streaming-layer
Test-Path .\.venv\Scripts\python.exe
# Nếu True, dùng venv đã có. Nếu False, tạo môi trường mới phù hợp:
# py -3.12 -m venv .venv
# .\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

File `requirements.txt` và câu lệnh cài phải kiểm tra theo **bản streaming-layer thực tế trên máy**; repo `main` chưa chứa module này. Các lần trước người thực hiện đã chạy unit tests bằng:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

### 4.3. File `.env`

```powershell
Set-Location 'C:\Users\Acer\Project-BigData-Storage-and-Processing-1\streaming-layer'
Test-Path .\.env
# Nếu False:
Copy-Item .\.env.example .\.env
notepad .\.env
```

Ví dụ (thay KEY bằng key thật **chỉ trên máy**, không chia sẻ/commit):

```dotenv
AVIATIONSTACK_API_KEY=YOUR_PRIVATE_KEY
AVIATIONSTACK_URL=https://api.aviationstack.com/v1/flights
AVIATIONSTACK_DEP_IATA=JFK
AVIATIONSTACK_LIMIT=25
KAFKA_BOOTSTRAP_SERVERS=127.0.0.1:29092
KAFKA_TOPIC=flight-realtime
POLL_INTERVAL_SECONDS=43200
```

`Test-Path .\.env` phải là `True`. Trong Windows Notepad có thể vô tình tạo `.env.txt`: kiểm tra bằng `Get-ChildItem -Force .env*`. Không đặt API Key vào `.env.example`.

### 4.4. Kafka broker, topic và listener

```powershell
Set-Location 'C:\Users\Acer\Project-BigData-Storage-and-Processing-1'
docker compose -f .\streaming-layer\compose.yml config
docker compose -f .\streaming-layer\compose.yml up -d kafka
docker compose -f .\streaming-layer\compose.yml ps
docker compose -f .\streaming-layer\compose.yml exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --describe --topic flight-realtime
Test-NetConnection 127.0.0.1 -Port 29092
```

Kỳ vọng: `aero-kafka` Running, topic 3 partitions, `TcpTestSucceeded : True`. Nếu topic chưa tồn tại, kiểm tra cấu hình/startup script trước khi tạo thủ công; lệnh tạo tương ứng:

```powershell
docker compose -f .\streaming-layer\compose.yml exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists --topic flight-realtime --partitions 3 --replication-factor 1
```

**Cực kỳ quan trọng:** Kafka có thể mở TCP nhưng Producer vẫn `NoBrokersAvailable` hoặc `Failed to update metadata` do broker quảng bá địa chỉ sai. Trong `compose.yml`, xem cấu hình `KAFKA_ADVERTISED_LISTENERS` và các listeners thực tế. Giá trị cần có ngữ nghĩa **INTERNAL = `kafka:9092`** và **EXTERNAL = `localhost:29092`** cho máy host; đừng dán `KAFKA_ADVERTISED_LISTENERS: ...` vào PowerShell vì đó là cú pháp YAML, không phải lệnh.

## 5. Chạy thử Producer → Kafka → Consumer

Ở thư mục `streaming-layer`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe producer.py --mode mock
.\.venv\Scripts\python.exe consumer.py --max-messages 10
```

Mock chỉ xác nhận đường truyền, **không phải dữ liệu AviationStack thật**.

### 5.1. Test kết nối Python Kafka trước khi gọi API

```powershell
.\.venv\Scripts\python.exe -c "from kafka import KafkaClient; c=KafkaClient(bootstrap_servers='127.0.0.1:29092'); print(c.check_version(timeout=10)); c.close()"
```

Nếu trả về version (ví dụ `(2, 6)`) thì metadata cơ bản đã thông. Nếu `producer.py` vẫn fail, kiểm tra `.env` và advertised listeners, không vội sửa thư viện.

### 5.2. API thật

```powershell
.\.venv\Scripts\python.exe producer.py --mode api
.\.venv\Scripts\python.exe consumer.py --max-messages 10
```

Tìm `"source": "aviationstack"`, `"event_type": "flight_status_observation"`, `"schema_version": 1`. Người thực hiện đã xác nhận Consumer `READ 10 message(s)` và quan sát hai event mẫu `AD7629` (JFK → MCO, delay 19.0) và `B61457` (JFK → AUA, delay 0.0) ở offsets 8–9. Không coi tất cả messages trong topic là dữ liệu API nếu còn message mock cũ. Tránh chạy chế độ polling liên tục khi quota API có hạn.

### 5.3. Cấu trúc message M3 đã quan sát

```json
{
  "schema_version": 1,
  "source": "aviationstack",
  "event_type": "flight_status_observation",
  "observed_at": "2026-11-15T09:29:05.737451Z",
  "flight_key": "<stable-flight-key>",
  "flight_date": "2026-11-15",
  "flight_iata": "AD7629",
  "airline_iata": "AD",
  "airline_name": "Azul",
  "flight_status": "scheduled",
  "departure_iata": "JFK",
  "arrival_iata": "MCO",
  "departure_scheduled": "2026-11-15T07:40:00+00:00",
  "departure_actual": null,
  "departure_delay": 19.0,
  "arrival_scheduled": "2026-11-15T10:43:00+00:00",
  "arrival_actual": null,
  "arrival_delay": null,
  "state_fingerprint": "<hash>",
  "event_id": "<hash>"
}
```

Các placeholder `<hash>` là mô tả, không phải JSON có thể dùng nguyên để chạy. Một Kafka message là JSON object serialized trong **value**; không nhất thiết có file `.json` trên ổ đĩa. Kafka `partition`/`offset` là metadata broker, không phải field JSON. `observed_at` là lúc quan sát API, **không nhất thiết là thời gian chuyến bay thực sự thay đổi**. `null` không đồng nghĩa 0. `departure_delay` tính phút theo schema đã quan sát. `flight_key`, `event_id`, `state_fingerprint` cần M4 đọc implementation `flight_schema.py` để xác nhận tính ổn định qua polling/restart.

## 6. Bàn giao M3 → M4: hợp đồng dữ liệu đầu vào

| Mục | Bàn giao | Kiểm tra |
|---|---|---|
| Topic | `flight-realtime` | `kafka-topics.sh --describe` |
| Bootstrap trong Spark container | `kafka:9092` **nếu container Spark được nối cùng Docker network với Kafka** | Test DNS/TCP bên trong Spark |
| Bootstrap Windows | `127.0.0.1:29092` | Python KafkaClient |
| Payload | UTF-8 JSON object, `schema_version=1` | Parse explicit schema; giữ `null` |
| Provenance | `source=aviationstack` hoặc `simulated` | Không gộp mock với live |
| Khóa | `flight_key`, `event_id`, `state_fingerprint` | Đọc `flight_schema.py`, test duplicate |
| Timestamp | `observed_at`, `departure_scheduled`, `arrival_scheduled` | Chốt **event time** với M4; UTC và timezone |
| Tính chất | **Flight status observations**, không phải mỗi event là một chuyến bay độc lập | Không đếm 2 lần cùng chuyến |
| Evidence | Log producer, 10 Consumer messages, topic partitions, tests | Che API Key |

**Test mạng M4:** Container Spark trong `batch-layer_default` và Kafka trong `streaming-layer` phải có network chung. `kafka:9092` chỉ dùng được khi DNS Docker resolve được hostname `kafka`. Không mặc định Spark đã kết nối; kiểm tra:

```powershell
Set-Location 'C:\Users\Acer\Project-BigData-Storage-and-Processing-1'
docker network ls
docker inspect aero-spark --format '{{json .NetworkSettings.Networks}}'
docker inspect aero-kafka --format '{{json .NetworkSettings.Networks}}'
# Khi đã có network chung:
docker compose -f .\batch-layer\docker-compose.yml exec spark bash -lc 'echo > /dev/tcp/kafka/9092 && echo KAFKA_REACHABLE'
```

Nếu chưa chung mạng, cần điều chỉnh Compose hoặc kết nối container vào network phù hợp một cách có kiểm soát, không thay đổi vội network của M1/M2/M5. **TCP reachable không có nghĩa Spark Structured Streaming đã đọc thành công**: M4 còn cần Kafka connector package tương thích Spark 3.5.3, schema và checkpoint.

### Tiêu chí nghiệm thu M3

- [x] Kafka chạy, topic tồn tại và có 3 partitions (theo ảnh).
- [x] Mock Producer/Consumer thành công.
- [x] API Key thật, API Producer → Kafka → Consumer nhận JSON `source=aviationstack` (theo ảnh).
- [ ] Test timeout/API error, quota, invalid record, dedup/replay/restart có bằng chứng riêng.
- [ ] Xác minh kết nối Spark container → Kafka.
- [ ] Push branch/PR, README, test log, schema sample; nhóm M4 xác nhận đã nhận bàn giao.

## 7. M4 phải xuất gì để M5 nhận được?

**Không chuyển thẳng raw event M3 sang `stream_window_kpi`.** Contract **đã có trong GitHub** `serving-layer/contracts/M4_TO_M5.md`, được M5 writer `serving-layer/m5/stream_writer.py` thực thi. M4 phải chuyển các event quan sát thành **full aggregate cho từng cửa sổ**:

```json
{
  "pipeline_id": "m4-flight-status-v1",
  "source": "aviationstack",
  "window_start": "2026-11-15T09:25:00Z",
  "window_end": "2026-11-15T09:30:00Z",
  "revision": 1,
  "dimensions": {"carrier": "AD", "origin": "JFK"},
  "metrics": {"flights": 10, "arr_n": 8, "on_time": 6, "delayed15": 2, "cancelled": 0}
}
```

**Ví dụ giả định để minh họa schema, không phải kết quả tính từ dữ liệu thực.** Contract yêu cầu **đúng 7 trường top-level** như trên. `source` chỉ `aviationstack` hoặc `simulated`. `dimensions` chỉ có `carrier`, `origin`, `dest` (hoặc `{}` cho overall). `metrics` bắt buộc `flights`, có thể thêm `cancelled`, `diverted`, `arr_n`, `on_time`, `delayed15`, `delayed60`, `sum_arr_delay`; counts integer không âm, delay phút. UTC window phải có timezone, `start < end`.

**Đặc biệt:**

1. `revision` là số nguyên tăng **bền vững qua restart** theo cùng khóa `source + pipeline_id + window_start + window_end + dimensions`. Không dùng batch id reset về 0 sau restart.
2. Writer M5 tạo `_id` xác định; replay cùng revision/payload được bỏ qua, revision cũ bị bỏ qua, revision mới **thay toàn bộ aggregate**, cùng revision nhưng payload khác bị từ chối.
3. `ingested_at` được M5 gán khi nhận cập nhật thật; không dùng thay event time.
4. Dashboard refresh 10 giây, đánh dấu stale sau 60 giây theo tài liệu M5; trigger/poll thực tế có thể dài hơn, cần nhóm thống nhất ngưỡng.
5. **Không tuyên bố exactly-once end-to-end** chỉ vì có checkpoint. Cần test retry, duplicates và sink semantics.
6. `flights` phải có định nghĩa nhất quán (unique flights hay observations). Không cộng cùng chuyến ở các lần poll. M4/M5 cần thống nhất cách tính `on_time`, `arr_n`, `delayed15` khi dữ liệu API khác BTS.

**Cách nối M4 → M5:** `foreachBatch` gọi `m5.stream_writer.write_window(db, record)` sau khi chuyển Spark Row thành Python dict; hoặc tạo JSONL full windows và chạy `python -m m5.stream_writer --input /data/m4/windows.jsonl` trong môi trường có package `m5` và MongoDB. Đây là **phương án tích hợp đề xuất trong contract**, chưa được chứng minh chạy trên hệ thống hiện tại. Cần test với database riêng trước, **không bơm fixture giả vào database demo rồi gọi là live**.

## 8. Sổ tay xử lý lỗi đã gặp

| Triệu chứng | Nguyên nhân / cách xác minh | Cách khắc phục an toàn |
|---|---|---|
| Docker `failed to connect ... dockerDesktopLinuxEngine` | Docker Desktop chưa chạy/daemon chưa sẵn | Mở Docker Desktop, đợi Engine running, kiểm tra `docker version` có Server |
| `open ... streaming-layer\batch-layer\docker-compose.yml: no such file` | Đang đứng trong `streaming-layer` nhưng dùng đường dẫn của repo root | `cd ..` rồi dùng `.\batch-layer\docker-compose.yml`, hoặc từ streaming dùng `..\batch-layer\docker-compose.yml` |
| `NoBrokersAvailable` | Kafka advertised listeners/DNS/port sai; không chỉ do Python | `docker compose ps`, `Test-NetConnection`, `KafkaClient.check_version`, kiểm tra `compose.yml` advertised INTERNAL/EXTERNAL, restart broker sau khi sửa |
| `KafkaTimeoutError: Failed to update metadata after 30.0 secs` | TCP thông nhưng broker quảng bá host không thể kết nối hoặc topic/metadata lỗi | Kiểm tra `kafka-topics.sh --describe`, Kafka logs, listener external `localhost:29092` và `kafka:9092` nội bộ |
| Gõ `KAFKA_ADVERTISED_LISTENERS: ...` trong PowerShell báo command not found | Đã dán dòng cấu hình YAML vào terminal | Mở `streaming-layer/compose.yml` trong VS Code để sửa đúng block `environment`, không chạy YAML như lệnh |
| `Test-Path .\.env` = False | File ở thư mục khác hoặc bị Notepad lưu `.env.txt` | `pwd`, `Get-ChildItem -Force .env*`, `Copy-Item .env.example .env`, `notepad .env`; kiểm tra True |
| Producer fail dù Kafka Running | `.env` bootstrap khác test, Python client/metadata khác, broker advertise sai | In riêng giá trị `KAFKA_BOOTSTRAP_SERVERS` (không in key), chạy `KafkaClient.check_version` và thử lại |
| Jupyter URL `http://3cd...:8888` không mở trên Windows | Hostname container chỉ resolve trong Docker | Dùng `http://127.0.0.1:8888/...` với port publish đúng, token thật; không dùng hostname container trên Chrome Windows |
| Jupyter VS Code `Forbidden`/connection failure | URL token cũ/sai, nhiều server 8888/8890, chọn local kernel | Dùng `docker compose exec -u root spark jupyter server list`, chọn token/port thật, chọn kernel `AERO Spark (Docker)`; không dán placeholder `TOKEN_CUA_SERVER` |
| Jupyter `Permission denied: /home/spark` | Chạy Jupyter bằng user không có quyền ghi runtime | Dùng `docker compose exec -u root spark ...` khi cần; không mở thêm nhiều server trùng port |
| Notebook in Python Windows và `/opt/spark` = False | VS Code đang dùng kernel local Python | Chọn remote Jupyter kernel trong container; kỳ vọng `/usr/bin/python3`, `/opt/spark` True |
| VS Code `Failed to save ... file newer` | Notebook được sửa bởi cả VS Code và JupyterLab | So sánh bản mới trước khi Overwrite/Revert; tránh mở/sửa đồng thời hai nơi |
| `TqdmWarning: IProgress not found` | Thiếu widget progress của Jupyter | Thường chỉ là cảnh báo; tiến trình tải BTS vẫn chạy, không phải lỗi dữ liệu |
| HDFS `/aero/analytics/eda/kpi` không tồn tại | M2 chưa build EDA KPI hoặc chưa chạy đúng HDFS | Chạy `eda_lite.ipynb` đến cell build; xác minh 13 KPI + 7 box trước khi export |
| M5 `-SnapshotPath` empty string | Biến `$AeroSnapshot` chưa có giá trị | Dùng `Get-ChildItem ..\batch-layer\spark_jobs\export\m2_to_m5 -Directory`, chọn đúng thư mục có `manifest.json`, kiểm tra `Test-Path` rồi mới load |
| Dashboard chạy nhưng tab Streaming trống | M5 chỉ có writer/contract, chưa nối M4 | Không coi là lỗi M3; cần M4 ghi full window aggregate hợp lệ vào MongoDB |

## 9. Kiểm thử cuối, evidence, Git và PR

**Trước commit:**

```powershell
Set-Location 'C:\Users\Acer\Project-BigData-Storage-and-Processing-1'
git branch --show-current
git status --short
Get-Content .\streaming-layer\.gitignore
# .env, .venv/, __pycache__/, *.pyc, *.log phải được ignore
git add streaming-layer
git diff --cached --name-only
git diff --cached --stat
```

Không stage `.env`, key, venv, log chứa bí mật, raw dữ liệu lớn. Nếu đã stage nhầm: `git restore --staged -- <path>`. `git add streaming-layer` không sửa `main`, nhưng có thể đưa cả file bí mật vào stage nếu `.gitignore` sai. Chỉ commit sau khi kiểm tra:

```powershell
git commit -m "feat(streaming): ingest AviationStack flight observations into Kafka"
git push -u origin feature/api-kafka-ingestion
```

Tạo Pull Request **base `main` ← compare `feature/api-kafka-ingestion`**; yêu cầu review, không merge trực tiếp khi M4 chưa xác nhận contract.

**Bộ bàn giao tối thiểu:** code `streaming-layer`, `.env.example` không có key, README này, unit-test result, ảnh Producer API + Consumer `source=aviationstack`, topic/partition evidence, schema mẫu (đã xóa dữ liệu nhạy cảm), mô tả retry/dedup, hướng dẫn restart và bảng công việc chưa kiểm thử. Có thể lưu ảnh trong `streaming-layer/evidence/` nếu không quá lớn và không chứa token.

### Checklist tích hợp M4 → M5 (chưa nghiệm thu)

- [ ] Spark đọc Kafka JSON bằng schema explicit, phân biệt simulated/aviationstack.
- [ ] Chốt event-time, watermark, dedup theo flight/event/state.
- [ ] Chốt cách tính full window KPI và revision bền vững.
- [ ] Checkpoint và replay sau restart không tạo KPI sai.
- [ ] Writer M5 nhận record hợp lệ, insert/update/replay đúng.
- [ ] Dashboard tab Streaming hiển thị dữ liệu thật, stale logic phù hợp poll interval.
- [ ] Có ảnh/log/test E2E M3 → M4 → MongoDB → dashboard; không trộn lịch sử BTS với live.

## 10. Nguồn tài liệu dự án (đã đối chiếu)

- [Repository README](https://github.com/KietLe2504/Project-BigData-Storage-and-Processing/blob/main/README.md)
- [M2 → M5 handoff](https://github.com/KietLe2504/Project-BigData-Storage-and-Processing/blob/main/batch-layer/doc_guide/HUONG_DAN_BAN_GIAO_M2_M5.md)
- [M2 chạy từ đầu](https://github.com/KietLe2504/Project-BigData-Storage-and-Processing/blob/main/batch-layer/doc_guide/HUONG_DAN_CHAY_TU_DAU_DEN_OUTPUT_M2.md)
- [M5 README](https://github.com/KietLe2504/Project-BigData-Storage-and-Processing/blob/main/serving-layer/README.md)
- [M5 hướng dẫn vận hành](https://github.com/KietLe2504/Project-BigData-Storage-and-Processing/blob/main/serving-layer/doc_guide/HUONG_DAN_CHAY_M5.md)
- [M4 → M5 contract](https://github.com/KietLe2504/Project-BigData-Storage-and-Processing/blob/main/serving-layer/contracts/M4_TO_M5.md)
- [M5 streaming writer](https://github.com/KietLe2504/Project-BigData-Storage-and-Processing/blob/main/serving-layer/m5/stream_writer.py)

**Giới hạn xác minh:** Code `streaming-layer` hiện không có trên GitHub `main` ở lần kiểm tra này, nên tài liệu M3 căn cứ vào tên file, lệnh và log/ảnh từ quá trình chạy của người thực hiện. Khi module được push, cần đối chiếu lại CLI flags, cách load `.env`, `flight_key`/`event_id` implementation, retry/dedup, network config và bổ sung test evidence. Những mục chưa kiểm thử được ghi rõ, không được đánh dấu PASS tùy tiện.
