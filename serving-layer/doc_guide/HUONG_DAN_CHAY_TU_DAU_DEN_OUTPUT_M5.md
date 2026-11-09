# M5 — Cài đặt, chạy từ đầu và bàn giao MongoDB & Dashboard

Đây là tài liệu thao tác chính có trong repo. Các bản PDF/PowerPoint xuất
thêm phục vụ trình bày có thể được bàn giao riêng, không cần để chạy M5.

Tài liệu dành cho thành viên nhận code M5 và dữ liệu M2 trên **máy Windows**.
Làm theo thứ tự 1 → 11 để có MongoDB, dashboard và bộ evidence. Mục 12 là
luồng Parquet/HDFS tùy chọn; mục 13 giải thích code; mục 14 xử lý lỗi.
Khi trình bày cho team, dùng thêm [tài liệu mô tả task M5](TaskM5.pdf).
Để có đầy đủ phân bố hãng theo tuyến và thống kê điểm đến của hãng,
nhận thêm bảng hãng–tuyến ở mục 2.4 và nạp theo mục 7.4 trước khi dùng dashboard.

## 1. Hiểu đầu vào, xử lý và kết quả M5

```text
M2: CSV chuyến bay → Spark làm sạch → KPI/box Parquet trên HDFS
                                        │
                      export JSONL + manifest.json
                                        ↓
M5: kiểm tra đầu vào → nạp MongoDB → đối chiếu dữ liệu → dashboard
```

M2 đã tính các thống kê. M5 nhận bảng tổng hợp, lưu thành document có khóa,
truy vấn và hiển thị. Một document KPI tháng đại diện cho **một tháng**,
không đại diện cho một chuyến bay. Vì vậy 74.921 document có thể mô tả
29.328.846 chuyến bay; hai số này đo hai thứ khác nhau.

| Thành phần | Chạy ở đâu? | Vai trò |
|---|---|---|
| PowerShell | Windows | Gõ các lệnh trong hướng dẫn |
| Docker Desktop | Windows | Chạy các container M5 |
| MongoDB server | Container `mongo` | Lưu dữ liệu và indexes |
| Batch loader | Container dùng một lần `loader` | Đọc, kiểm tra và nạp M2 |
| Streamlit + Plotly | Container `dashboard` | Truy vấn MongoDB và vẽ biểu đồ |
| Trình duyệt | Windows | Xem `http://localhost:8501` |
| MongoDB Compass, tùy chọn | Windows | Xem document và indexes qua giao diện |

**Không cần cài MongoDB Server hoặc Python riêng trên Windows cho luồng này.**
Docker tải MongoDB và cài dependencies Python theo các file của dự án.
Compass là ứng dụng kết nối đến MongoDB đang chạy; mở Compass không thay
thế bước khởi động server.

Phạm vi đã có: batch lịch sử M2 → M5. M5 có writer và contract đề xuất cho
streaming, nhưng vẫn cần M4 tích hợp và kiểm thử toàn luồng. Trang Streaming
chờ dữ liệu không có nghĩa là phần lịch sử bị lỗi.

## 2. Thành viên khác phải nhận những gì?

### 2.1. Code

Nhận bản code có thư mục `serving-layer`, qua repo của team hoặc bản sao dự án.
Không cần clone lại nếu đã có đúng bản code này. Cần giữ cả các file ẩn như
`.streamlit/config.toml` và `.env.example` khi sao chép.

```text
Project-BigData-Storage-and-Processing/
├── serving-layer/
│   ├── compose.yml, Dockerfile, requirements.txt, constraints.txt
│   ├── app.py, assets/, .streamlit/
│   ├── m5/, scripts/, tests/, contracts/, doc_guide/
│   └── .env.example
└── batch-layer/spark_jobs/export/m2_to_m5/
    └── 20261107T042703414867Z/
        ├── manifest.json
        ├── kpi__month_overall.jsonl
        └── ...các JSONL/CSV còn lại...
```

### 2.2. Dữ liệu M2, gửi riêng ngoài code

Các thư mục export không được đưa lên Git. **Chỉ nhận/clone code thì chưa có
dữ liệu để nạp.** Chọn một trong hai bộ đầu vào sau:

| Bộ nhận được | Thư mục truyền cho `-SnapshotPath` |
|---|---|
| Snapshot export gốc | `batch-layer\spark_jobs\export\m2_to_m5\20261107T042703414867Z` |
| ZIP bàn giao M2 đã giải nén | Thư mục `data` bên trong `M2_HANDOFF_20261107T042703414867Z` |

Thư mục được chọn phải chứa trực tiếp `manifest.json` và **20 file JSONL**.
Bộ đầy đủ hiện tại có thêm 20 CSV, tổng cộng 41 file. Loader dùng JSONL;
CSV để đọc/đối chiếu thuận tiện. Không truyền đường dẫn file ZIP hoặc thư
mục cha đang chứa nhiều snapshot.

Nếu nhận ZIP, mở bằng File Explorer → **Extract All / Giải nén tất cả**,
rồi tìm đúng thư mục `data`. Có thể giữ `data` ở vị trí khác và truyền đường
dẫn tuyệt đối; script sẽ mount riêng thư mục đó. Compose vẫn khai báo thư
mục export gốc trong cây dự án ở trên, nên giữ cây dự án trong ổ có thể ghi.

Luồng JSONL không yêu cầu máy nhận có Hadoop/Spark của M2, raw CSV 29 triệu
dòng hay bản sao cleaned Parquet. Để chạy trực tiếp Parquet/HDFS, xem mục 12.

### 2.3. Số liệu đối chiếu của snapshot mẫu

| Chỉ tiêu | Giá trị của `20261107T042703414867Z` |
|---|---:|
| Bảng KPI | 13 |
| Bảng phân phối box | 7 |
| Tổng bảng/collections dữ liệu | 20 |
| Document KPI | 64.249 |
| Document box | 10.672 |
| Tổng document cho snapshot | 74.921 |
| Coverage | 51 tháng, 2022-01 → 2026-03 |
| Tổng `flights` trong bảng KPI tháng | 29.328.846 |

Đây là mốc của **bộ mẫu này**, không phải số cố định cho mọi export tương lai.
Các collections metadata được tính riêng. Nếu giữ nhiều snapshot, tổng
document vật lý có thể lớn hơn; phải lọc `snapshot_id` khi đối chiếu.

### 2.4. Bảng hãng–tuyến bổ sung cho dashboard hiện tại

Ngoài snapshot 20 bảng, nhận thêm **cả thư mục timestamp** trong
`batch-layer/spark_jobs/export/m2_route_carriers/`, chứa `manifest.json` và
`route_carrier.jsonl`. Đây là bảng đếm theo `year, origin, dest, carrier`,
dùng cho phân bố hãng khi bấm đường trên bản đồ và Top sân bay điểm đến
của mỗi hãng. Không được suy ra các số này từ bảng chỉ có hãng–sân bay đi.

Bộ mẫu là `20261108T060505228918Z`, có 63.440 nhóm và 29.328.846 chuyến,
đã đối chiếu với snapshot M2 mẫu ở trên. Dữ liệu export được gửi riêng,
không nằm trong Git. Thành viên chỉ chạy serving nhận hai bộ export là đủ,
không cần tải raw hoặc dựng HDFS.

Nếu nhóm chưa có bảng bổ sung, thành viên có HDFS/cleaned Parquet chạy
`10_export_route_carriers.py` theo [mục 7.4](#route-carriers).

## 3. Cài môi trường trên máy Windows mới

### 3.1. Cài Docker Desktop

1. Mở [trang cài Docker Desktop cho Windows chính thức](https://docs.docker.com/desktop/setup/install/windows-install/),
   kiểm tra yêu cầu hệ thống và tải bản phù hợp máy.
2. Cài Docker Desktop với backend WSL 2 theo hướng dẫn của Docker. Dự án
   sử dụng **Linux containers**.
3. Nếu máy chưa có WSL, thực hiện theo [hướng dẫn WSL của Microsoft](https://learn.microsoft.com/en-us/windows/wsl/install).
   Lệnh dưới đây chỉ dành cho bước cài WSL, trong **PowerShell Run as administrator**:

```powershell
wsl --install
```

Khởi động lại Windows nếu trình cài yêu cầu, hoàn tất thiết lập WSL rồi
mở Docker Desktop. Máy đã chạy được Docker cho M2 có thể bỏ qua việc cài lại.
Yêu cầu Windows/WSL/ảo hóa cụ thể lấy theo tài liệu Docker ở trên.

### 3.2. Kiểm tra Docker hoạt động

Mở **PowerShell Windows** hoặc terminal PowerShell trong VS Code, chạy:

```powershell
docker version
docker compose version
```

`docker version` phải hiện cả **Client** và **Server**, không có lỗi kết nối
daemon. Lệnh thứ hai phải hiện phiên bản Docker Compose. Nếu vừa cài mà
`docker` chưa được nhận diện, mở lại terminal sau khi Docker Desktop hoạt động.
Lần đầu build cần Internet để tải images và dependencies.

### 3.3. Compass là tùy chọn

Muốn xem MongoDB bằng giao diện, tải/cài theo
[hướng dẫn MongoDB Compass chính thức](https://www.mongodb.com/docs/compass/install/).
Kết nối sau khi hoàn thành nạp ở mục 7. Có thể chạy đầy đủ dashboard khi
không cài Compass.

## 4. Khai báo đường dẫn và kiểm tra file

**Tất cả khối `powershell` từ đây chạy ở PowerShell Windows thông thường.**
Không sao chép dấu nhắc `PS F:\...>`; chỉ sao chép lệnh. Không thêm dấu `\`
cuối dòng. Không gõ Python như `spark.stop()` vào PowerShell.

### 4.1. Khai báo một lần trong terminal đang dùng

Sửa dòng đầu theo nơi lưu dự án trên máy nhận. Tên biến phải có dấu **`$`**.
Nếu mở terminal mới, khai báo lại các biến này.

```powershell
$AeroProject = 'F:\Project-BigData-Storage-and-Processing'
$AeroServing = Join-Path $AeroProject 'serving-layer'
$AeroSnapshot = Join-Path $AeroProject 'batch-layer\spark_jobs\export\m2_to_m5\20261107T042703414867Z'
Set-Location $AeroServing
Get-Location
```

Nếu nhận bộ bàn giao thay vì export gốc, **thay riêng giá trị `$AeroSnapshot`**
trước khi làm tiếp. Ví dụ khi giải nén vào thư mục export của dự án:

```powershell
$AeroSnapshot = Join-Path $AeroProject 'batch-layer\spark_jobs\export\M2_HANDOFF_20261107T042703414867Z\data'
```

Đây là nhánh lựa chọn, không bắt buộc chạy cả hai cách. Nếu `data` ở ổ khác,
có thể gán thẳng `$AeroSnapshot = 'D:\M2_HANDOFF_20261107T042703414867Z\data'`.

### 4.2. Kiểm tra đang đứng đúng thư mục và có đầu vào

```powershell
Test-Path .\compose.yml
Test-Path .\scripts\start_m5.ps1
Test-Path .\m5\load_batch.py
Test-Path (Join-Path $AeroSnapshot 'manifest.json')
@(Get-ChildItem -LiteralPath $AeroSnapshot -Filter '*.jsonl' -File).Count
```

Cần thấy **4 lần `True`**, sau đó **`20`**. Nếu `False`, sửa đường dẫn trước
khi tiếp tục. `Get-Location` phải là thư mục `serving-layer` của máy nhận.

Đọc nhanh manifest bằng PowerShell, không cần Python:

```powershell
$AeroManifest = Get-Content -LiteralPath (Join-Path $AeroSnapshot 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$AeroManifest.coverage
$AeroManifest.tables | Select-Object group, name, rows, suggested_collection
($AeroManifest.tables | Measure-Object -Property rows -Sum).Sum
```

Bộ mẫu phải có `month_count = 51`, `total_flights = 29328846`, 20 bảng và
tổng `rows = 74921`. Đây mới là đọc mô tả; mục 6 sẽ kiểm tra nội dung thật.

## 5. Khởi động MongoDB và dashboard

Tại `serving-layer`, chạy và chờ kết thúc:

```powershell
.\scripts\start_m5.ps1
docker compose -f compose.yml ps
```

Script kiểm tra Compose, build image ứng dụng, bật MongoDB và dashboard rồi
chờ health checks. Lần đầu có nhiều dòng tải/cài đặt; không đóng terminal
giữa lúc build. Lệnh `ps` cần có `mongo`, `dashboard` và trạng thái healthy.
`loader` không chạy thường trực nên không bắt buộc xuất hiện ở đây.

| Thành phần | Địa chỉ mặc định từ Windows |
|---|---|
| Dashboard | `http://localhost:8501` |
| MongoDB | `mongodb://localhost:27017` |
| Database | `aero_m5` |

Dashboard có thể mở trước khi ingest nhưng sẽ chưa có snapshot lịch sử.
Không phải cứ container chạy là dữ liệu đã được nạp.

### 5.1. Nếu PowerShell chặn chạy file `.ps1`

Không cần đổi policy vĩnh viễn. Dùng các lệnh tương đương ở **phụ lục A**
để khởi động, nạp và xác minh. Chọn một cách thao tác và theo hết cách đó.

### 5.2. Nếu cổng bị chiếm

Chỉ khi cần đổi cấu hình, tạo `.env` nếu chưa có rồi mở bằng Notepad:

```powershell
if (-not (Test-Path .\.env)) { Copy-Item .\.env.example .\.env }
notepad .\.env
```

Ví dụ sửa `M5_MONGO_PORT=27018`, `M5_DASHBOARD_PORT=8502`, lưu rồi chạy lại
start. Khi đó truy cập Windows qua `mongodb://localhost:27018` và
`http://localhost:8502`. Các container vẫn kết nối nội bộ `mongo:27017`;
không đổi URI nội bộ theo cổng Windows. Hướng dẫn dưới đây dùng cổng mặc định.

## 6. Kiểm tra đầu vào, rồi nạp dữ liệu M2

### 6.1. Kiểm tra trước, chưa ghi MongoDB

```powershell
.\scripts\load_m2.ps1 -SnapshotPath $AeroSnapshot -CheckOnly
```

Chế độ này đọc manifest và JSONL, kiểm tra đủ 20 bảng, schema, kiểu dữ liệu,
khóa trùng, coverage và tổng flights; tính fingerprint từ nội dung. Phần
JSON cuối lệnh cần có `"result": "PASS"`, `"total_documents": 74921`.

`-CheckOnly` không ghi MongoDB. Dòng `REPORT: /app/evidence/load_report.json`
là đường dẫn **trong container**, tương ứng file
`serving-layer\evidence\load_report.json` trên Windows.

### 6.2. Nạp thật vào MongoDB

```powershell
.\scripts\load_m2.ps1 -SnapshotPath $AeroSnapshot
```

Mỗi bảng sẽ có dòng `LOADED ...`. Với bộ mẫu, cần thấy dòng:

```text
LOAD COMPLETE: <snapshot_id>; 74921 documents; PASS
```

Và JSON cuối có `"result": "PASS"`. `snapshot_id` được tính từ nội dung,
không phải tên thư mục thời gian `20261107T042703414867Z`.

Loader tạo unique index theo `snapshot_id` + khóa nghiệp vụ, upsert dữ liệu,
đối chiếu đủ giá trị rồi mới công bố snapshot cho dashboard. Lần nạp lỗi
không thay snapshot đang phục vụ. Nếu script báo lỗi, đọc lỗi và dừng ở
bước này; không coi thông báo `REPORT` cũ còn trên ổ là lần nạp mới thành công.

### 6.3. Thử nạp lại để chứng minh không nhân bản

Sau khi nạp thành công, có thể chạy lại đúng lệnh 6.2. Cần thấy
`ALREADY LOADED` và kiểm tra PASS, không tăng document của snapshot.
Nếu đây là snapshot cũ đã xuất bản trong database có bộ mới hơn, nạp lại
bộ cũ không tự chuyển dashboard về bộ cũ.

Mặc định loader yêu cầu đủ kỳ 2022-01 → 2026-03. Không thêm `-AllowPartial`
chỉ để bỏ qua lỗi của bộ bàn giao; tùy chọn đó dành cho thử nghiệm có ghi rõ
phạm vi, vẫn yêu cầu cấu trúc 20 bảng.

## 7. Xác minh kết quả trong MongoDB

### 7.1. Chạy verifier

```powershell
.\scripts\verify_m5.ps1
Get-Content .\evidence\verify_report.json -Raw -Encoding UTF8
```

Với bộ mẫu, terminal cần in:

```text
ALL 20 COLLECTIONS CHECKED: PASS; 74921 documents
```

Verifier kiểm tra toàn bộ giá trị qua digest lưu lúc ingest và các unique
indexes của snapshot. Đây là bằng chứng dữ liệu M2 được chuyển đúng vào
MongoDB; không thay thế kiểm chứng công thức Spark hoặc đếm lại raw CSV.

### 7.2. Xem bằng Compass, tùy chọn

Hướng dẫn thao tác và bảng giải thích 25 collection, các trường KPI/box/
hãng–tuyến/trạng thái nằm trong
[tài liệu xem và đọc dữ liệu MongoDB](HUONG_DAN_XEM_MONGODB_VA_GIAI_THICH_COLLECTIONS.md).

Theo [cách kết nối Compass chính thức](https://www.mongodb.com/docs/compass/connect/):

1. Mở Compass → **Add new connection / New Connection**.
2. Nhập `mongodb://localhost:27017`, chọn **Connect**. Cấu hình local hiện
   tại không yêu cầu username/password.
3. Mở database `aero_m5` → collection `serving_state`.
4. Tìm document có `_id: "historical"`, sao chép giá trị `snapshot_id`.
5. Mở `kpi_month_overall` → Documents. Trong ô **Filter**, nhập
   `{ "snapshot_id": "GIÁ_TRỊ_VỪA_SAO_CHÉP", "year": 2025, "month": 1 }`,
   thay chuỗi mẫu bằng giá trị thật rồi chọn Find/Apply.
6. Xem `flights`, `otp_operated`, `delay15_rate`, `cancel_rate`; mở tab
   **Indexes** để xem index `snapshot_business_key` có thuộc tính unique.

Kết quả mong đợi cho tháng 1/2025 là một document của snapshot đang dùng.
Nếu đã đổi cổng MongoDB, dùng cổng mới khi kết nối. Không dùng hostname
`mongo` trong Compass trên Windows; hostname đó dành cho mạng container.

### 7.3. Xem bằng mongosh có sẵn trong container, tùy chọn

**Chạy dòng sau trong PowerShell** tại `serving-layer`:

```powershell
docker compose -f compose.yml exec mongo mongosh aero_m5
```

Khi dấu nhắc đã đổi sang **mongosh** (không còn `PS F:\...>`), mới dán
khối JavaScript dưới đây. Nếu đổi database trong `.env`, dùng tên mới.

```javascript
const active = db.serving_state.findOne({ _id: "historical" });
const sid = active.snapshot_id;
db.kpi_month_overall.countDocuments({ snapshot_id: sid });
db.kpi_month_overall.findOne({ snapshot_id: sid, year: 2025, month: 1 });
db.kpi_month_overall.getIndexes();
db.kpi_month_overall.aggregate([
  { $match: { snapshot_id: sid } },
  { $group: { _id: null, flights: { $sum: "$flights" } } }
]);
```

Với bộ mẫu: count = **51**, tổng flights = **29328846**. `getIndexes()`
hiện index có `snapshot_id`, `year`, `month`, `unique: true`.
Gõ `exit` trong mongosh để trở lại PowerShell. Không dán đoạn JavaScript
này thẳng vào PowerShell. Nếu thử lại trong cùng phiên shell, tránh khai
báo lại `const`; thoát và mở phiên mới để chạy lại nguyên khối.

<a id="route-carriers"></a>

### 7.4. Tạo/nhận và nạp bảng hãng–tuyến để mở đủ chức năng dashboard

Nếu đã nhận thư mục bổ sung ở mục 2.4, thực hiện bước nạp dưới đây.
Nếu cần tự tạo, máy có HDFS và Parquet đã làm sạch chạy khối sau trong
**PowerShell tại thư mục project**; thay timestamp snapshot theo dữ liệu thực:

```powershell
docker compose -f .\batch-layer\docker-compose.yml up -d spark
docker compose -f .\batch-layer\docker-compose.yml exec -T -u root spark /opt/spark/bin/spark-submit --master 'local[2]' --driver-memory 2g /opt/spark_jobs/10_export_route_carriers.py --base-snapshot /opt/spark_jobs/export/m2_to_m5/20261107T042703414867Z
if ($LASTEXITCODE -ne 0) { throw 'Xuat bang hang theo tuyen chua thanh cong' }
```

Script đếm theo `year, origin, dest, carrier`, đối chiếu tổng hãng trên từng
tuyến với `kpi__year_route.jsonl` và tổng tuyến theo hãng–sân bay xuất phát
với `kpi__year_carrier_origin.jsonl`. Chỉ sau khi khớp mới xuất thư mục
timestamp dưới `batch-layer/spark_jobs/export/m2_route_carriers/`.
Bàn giao cả `manifest.json` và `route_carrier.jsonl` cho máy chạy serving.

Sau khi snapshot M2 ở mục 6–7 đã PASS, chạy trong PowerShell tại
`serving-layer` (giữ các biến đường dẫn ở mục 4):

```powershell
$AeroRouteSupplement = Join-Path $AeroProject 'batch-layer\spark_jobs\export\m2_route_carriers\20261108T060505228918Z'
Test-Path (Join-Path $AeroRouteSupplement 'manifest.json')
Test-Path (Join-Path $AeroRouteSupplement 'route_carrier.jsonl')
.\scripts\load_route_carriers.ps1 -SupplementPath $AeroRouteSupplement -BaseSnapshotPath $AeroSnapshot
```

Thay timestamp hoặc gán đường dẫn tuyệt đối tới bộ bổ sung thực nhận; hai
`Test-Path` phải là `True`. Không truyền thư mục cha chứa nhiều timestamp.
Loader đối chiếu từng tuyến và từng nhóm hãng–sân bay xuất phát với snapshot
MongoDB đang active, ghi theo phiên bản rồi đọc lại xác minh trước công bố.

Kết quả của bộ mẫu phải có `status: ready`, `rows: 63440`,
`flights: 29328846`, `verified_routes: 33373`. Báo cáo tại
`evidence/route_carrier_load.json`, log tại `logs/load_route_carriers.log`.
Hai collection thêm là `route_carrier_counts` và `route_carrier_state`;
verifier mục 7.1 vẫn kiểm tra 20 bảng M2 chuẩn, không tính hai bảng bổ sung.

Nếu chưa nạp bảng này, các KPI M2 vẫn xem được nhưng phần phân bố hãng theo
tuyến và Top sân bay điểm đến sẽ báo thiếu dữ liệu. Sau nạp, nhấn
**Làm mới dữ liệu**. Mỗi bảng bổ sung gắn với snapshot M2 đã đối chiếu;
khi đổi snapshot phải nạp bộ bổ sung tương ứng. Nạp lại không nhân đôi và
lần nạp lỗi không thay phiên bản đang phục vụ.

## 8. Mở dashboard và thao tác để có kết quả

**PowerShell**:

```powershell
Start-Process 'http://localhost:8501'
```

Nếu trang đã mở trước lúc nạp, nhấn **Làm mới dữ liệu**. Chọn toàn kỳ
2022–2026 và đủ tháng để so tổng flights với mốc 29.328.846; một kỳ đang lọc
sẽ có tổng nhỏ hơn. Với dữ liệu này 2026 chỉ gồm tháng 1–3.

| Trang | Thao tác demo | Kết quả cần giải thích |
|---|---|---|
| Tổng quan | Chọn năm/tháng; đổi Diện tích/Cột | KPI, xu hướng, donut và mức trễ |
| Thời gian & mùa vụ | Đổi góc nhìn ngày/tháng/ngày lịch/giờ | Xu hướng, heatmap lịch và polar 24 giờ |
| Hãng bay | Chọn kỳ, hãng, ngưỡng số chuyến, chỉ số | Ranking, bubble, treemap; tab Phát theo năm |
| Sân bay xuất phát | Chọn origin và chỉ số | So sánh các sân bay theo chuyến xuất phát |
| Tuyến bay | Chọn năm, origin/dest, toàn mạng hoặc Top | Bản đồ địa lý, luồng Sankey và so sánh các tuyến |
| Danh mục hãng bay & sân bay | Chọn loại hồ sơ, tìm hãng/sân bay, chọn năm | Hồ sơ hãng với Top sân bay đi/đến; mạng kết nối sân bay; bấm điểm đổi sân bay, bấm đường xem thống kê cặp và phân bố hãng |
| Phân phối delay | Chọn mức, kỳ, arr/dep và all/late | Median, Q1–Q3, râu box từ thống kê M2 |
| Streaming | Xem trạng thái khi chưa tích hợp M4 | Chờ dữ liệu; chưa nghiệm thu streaming |
| Dữ liệu & vận hành | Xem snapshot, coverage và bảng | Truy xuất nguồn và trạng thái bộ đang phục vụ |

Di chuột để đọc số, click chú giải để ẩn/hiện chuỗi, kéo để zoom và nhấn đúp
để reset khi biểu đồ hỗ trợ. Nút camera xuất PNG; phần dữ liệu của trang có
tải CSV. Animation hãng/sân bay là diễn biến **lịch sử theo năm**, không
phải dữ liệu live; chỉ dùng nhóm có dữ liệu ở mọi năm trong animation.

Các điểm phải giải thích đúng khi trình bày:

- Tỷ lệ lưu 0–1; giao diện nhân 100 để hiển thị %. Gộp nhiều nhóm phải tính
  lại từ tổng số đếm, không lấy trung bình các tỷ lệ.
- Delay tính bằng phút, có thể âm khi đến sớm. `null` không tự đổi thành 0.
- Quần thể chuyến đến hợp lệ và tổng chuyến theo lịch có thể khác nhau;
  donut chuyến đến không ghép hủy/chuyển hướng vào cùng mẫu số.
- Bảng tuyến chỉ có năm nên không có lọc tháng. Các bảng mùa vụ/giờ gộp
  toàn kỳ không tự tạo thêm chiều năm.
- Không cộng/trung bình các phân vị tháng để tạo phân vị năm. Box hiển thị
  thống kê đã được M2 tính ở đúng mức.
- `reliability_score` là điểm nhóm tự định nghĩa 0–100, không phải chuẩn ngành.

### 8.1. Tra cứu hãng/sân bay và đọc bản đồ kết nối

- Chọn **Danh mục hãng bay & sân bay → Hãng bay** để tìm theo tên/mã,
  xem hồ sơ, lưu lượng theo tháng và Top 10 sân bay xuất phát/điểm đến.
  Hai bảng xếp hạng dùng cùng hãng và phạm vi năm đang chọn.
- Chọn **Sân bay** để tìm theo mã/tên/thành phố, lọc vùng và chọn hồ sơ.
  Bản đồ vẽ sân bay đang xem màu vàng và toàn bộ sân bay có chuyến đi/đến
  với nó màu xanh, kể cả ngoài kết quả tìm kiếm hoặc vùng đang lọc.
- Mỗi đường gộp hai chiều của một cặp sân bay; độ dày và thang màu theo
  tổng chuyến hai chiều. Chú giải ghi min/max của mạng đang xem; thang căn
  bậc hai giúp các đường ít chuyến vẫn nhìn thấy. Tooltip ghi số chính xác.
- Bấm một điểm để chuyển hồ sơ/mạng kết nối sang sân bay đó. Bấm đường
  hoặc chọn danh sách cặp bên dưới để xem số chuyến đúng giờ, trễ, hủy,
  chuyển hướng, phân bố hãng, cơ cấu trạng thái và tải CSV. Có bộ chọn cả
  hai chiều hoặc từng chiều. Tổng hãng phải khớp tổng chuyến của phạm vi.
- Các mã thiếu tọa độ được báo, vẫn có trong danh sách thống kê. Đây là
  đường nối minh họa dữ liệu lịch sử; bản đồ nền cần Internet.
- Trang **Tuyến bay → Bản đồ mạng bay** có chế độ Top/toàn mạng, lọc sân
  bay, đổi màu theo tỷ lệ trễ/delay trung bình/hủy và góc nhìn nghiêng 3D.

## 9. Kiểm thử, chụp bằng chứng và đóng gói output

### 9.1. Kiểm thử tự động khi nghiệm thu code

Khi cần nghiệm thu bản code, chạy tại PowerShell sau khi MongoDB đã lên:

```powershell
.\scripts\test_m5.ps1
```

Script cài dependency test trong container dùng một lần, chạy unit và
integration tests với database ngẫu nhiên `aero_m5_test_*` rồi dọn database
test; không dùng database phục vụ để ghi fixtures. Máy cần Internet nếu
chưa có các dependency test. Đọc tổng kết cuối lệnh: phải không có FAILED;
integration tests phải chạy khi nghiệm thu kết nối MongoDB, không chỉ SKIP.
Lưu kết quả terminal và `logs/test_m5.log` làm biên bản kiểm thử của lần chạy.
Không bắt buộc chạy lại tests mỗi lần chỉ mở dashboard.

### 9.2. Lưu ảnh và kết quả demo

Chụp ít nhất: terminal verify PASS, Tổng quan với kỳ đang chọn, một trang
hãng/tuyến/box, trang Dữ liệu & vận hành; có thể thêm Compass và unique index.
Lưu PNG/JPG vào `serving-layer\evidence` trước khi đóng gói. Đặt tên dễ hiểu,
ví dụ `team_demo_overview.png`, ghi rõ bộ lọc và thời điểm trong ghi chú demo.

### 9.3. Tạo bộ evidence bàn giao

```powershell
.\scripts\collect_evidence.ps1
Get-ChildItem .\evidence -Filter 'M5_HANDOFF_*.zip' | Sort-Object LastWriteTime -Descending | Select-Object -First 1 FullName, Length, LastWriteTime
```

Script chạy verify lại, chụp trạng thái containers, copy logs, tài liệu và
các file report/ảnh/CSV/TXT ở ngay trong `evidence`, rồi tạo thư mục và ZIP
`M5_HANDOFF_<ngày_giờ>`. ZIP không tự chụp màn hình.

**ZIP evidence không chứa code, snapshot M2 hoặc MongoDB volume.** Để người
khác chạy lại, gửi đủ ba phần: code `serving-layer` (kèm đường dẫn repo hoặc
bản code), snapshot JSONL + manifest M2, và ZIP evidence M5. Ghi tên phiên
bản code/commit nếu bản code đã được commit, tên snapshot, cấu hình cổng và
đường dẫn hướng dẫn này trong ghi chú bàn giao.

## 10. Toàn bộ output M5 nằm ở đâu?

| Output | Vị trí mặc định | Cách mở |
|---|---|---|
| Document KPI/box | MongoDB database `aero_m5` | Compass hoặc mongosh, mục 7 |
| Dữ liệu MongoDB trên Docker | Volume `aero-serving_m5_mongo_data`, mount `/data/db` | Docker Desktop → Volumes; không coi là thư mục JSONL Windows |
| Dashboard | `http://localhost:8501` | Trình duyệt trên máy đang chạy M5 |
| Log khởi động | `serving-layer\logs\start_m5.log` | VS Code/Notepad |
| Log nạp | `serving-layer\logs\load_m2.log` | VS Code/Notepad |
| Log verify | `serving-layer\logs\verify_m5.log` | VS Code/Notepad |
| Báo cáo nạp | `serving-layer\evidence\load_report.json` | VS Code/Notepad |
| Báo cáo verify | `serving-layer\evidence\verify_report.json` | VS Code/Notepad |
| Log tests, nếu đã chạy | `serving-layer\logs\test_m5.log` | VS Code/Notepad |
| Ảnh/CSV xuất từ UI | Nơi trình duyệt tải file; tự chép vào `evidence` để đóng gói | File Explorer |
| Bộ evidence đã đóng gói | `serving-layer\evidence\M5_HANDOFF_<ngày_giờ>\` và `.zip` | File Explorer |
| Đầu vào M2 | Thư mục `$AeroSnapshot` | Bộ nguồn để tái nạp; không phải output mới của M5 |

`-CheckOnly` và lần nạp thật cùng ghi `load_report.json`; các log theo tên
script cũng được ghi lại khi chạy lại. Muốn giữ một lần chạy, đóng gói hoặc
chép log/report trước lần tiếp theo. Thư mục logs/evidence không tự được
đưa lên Git.

## 11. Dừng và chạy lại ngày hôm sau

**PowerShell tại `serving-layer`:**

```powershell
.\scripts\stop_m5.ps1
```

Lệnh dừng M5 và giữ volume. Lần sau mở Docker Desktop, khai báo lại đường
dẫn mục 4 trong terminal mới, rồi:

```powershell
.\scripts\start_m5.ps1
.\scripts\verify_m5.ps1
Start-Process 'http://localhost:8501'
```

Nếu volume còn dữ liệu hợp lệ thì không bắt buộc nạp lại. Máy mới có volume
trống phải làm mục 6. Không dùng `docker compose down -v` để dừng thông
thường vì tùy chọn đó xóa volume dữ liệu.

`localhost` là máy hiện tại. Gửi link `localhost:8501` cho người khác không
làm họ xem được dashboard trên máy bạn. Hướng dẫn này giúp họ dựng M5 trên
máy riêng; triển khai máy dùng chung/cloud là bước cấu hình riêng.

## 12. Tùy chọn: chứng minh luồng KPI Parquet trên HDFS → MongoDB

Luồng JSONL ở trên phù hợp bàn giao nhẹ. Luồng này dành cho máy đã có các
bảng aggregate M2 trên HDFS, để trình bày đúng nhánh đọc Parquet trong sơ đồ.
Không bắt buộc làm cả hai để mở dashboard.

**Điều kiện:** Docker batch stack có dữ liệu HDFS thật, đủ 13 KPI + 7 box,
và ETL/EDA dừng trong suốt lần nạp. Copy code, ZIP JSONL hoặc thư mục
cleaned Parquet sang máy mới không tự phục hồi các bảng aggregate trên HDFS.

PowerShell, dùng lại `$AeroProject` của mục 4:

```powershell
Set-Location (Join-Path $AeroProject 'batch-layer')
docker compose up -d
docker compose exec namenode hdfs dfs -ls /aero/analytics/eda/kpi
docker compose exec namenode hdfs dfs -ls /aero/analytics/eda/box
Set-Location $AeroServing
.\scripts\load_hdfs.ps1
.\scripts\verify_m5.ps1
```

Adapter Spark đọc `/aero/analytics/eda/kpi` và `/aero/analytics/eda/box`, stage
JSONL tạm rồi gọi cùng writer MongoDB. Không đọc lại toàn bộ chuyến bay từ
`/aero/processed`, không cần MongoDB Spark Connector JAR. Khi nội dung giống
snapshot JSONL, fingerprint giống nhau và sẽ nhận diện bộ đã nạp.

Mặc định mạng batch là `batch-layer_default`; nếu Compose M2 đổi project
name, đặt `M5_BATCH_NETWORK` trong `.env` theo tên mạng thật trong
`docker network ls`. Output riêng: `logs\load_hdfs.log` và
`evidence\hdfs_load_report.json`. Muốn dựng lại nguồn trên máy khác, xem
[hướng dẫn ingestion/HDFS](../../batch-layer/doc_guide/AERO_Member1_End_to_End_Guide_vi.md),
[hướng dẫn EDA M2](../../batch-layer/doc_guide/HUONG_DAN_CHAY_EDA_LITE.md)
và [xuất dữ liệu bàn giao M2 → M5](../../batch-layer/doc_guide/HUONG_DAN_BAN_GIAO_M2_M5.md).

## 13. Mở code nào để giải thích cho team?

| File | Giải thích khi trình bày |
|---|---|
| [compose.yml](../compose.yml) | Khai báo MongoDB, dashboard, loader, ports và volume |
| [Dockerfile](../Dockerfile), [requirements.txt](../requirements.txt) | Môi trường Python và dependencies ứng dụng |
| [start_m5.ps1](../scripts/start_m5.ps1), [common.ps1](../scripts/common.ps1) | Bao lệnh Docker và dừng khi lệnh thất bại |
| [load_m2.ps1](../scripts/load_m2.ps1) | Nhận đường dẫn snapshot Windows, mount vào loader |
| [load_batch.py](../m5/load_batch.py) | Điểm vào CLI: kiểm tra hoặc nạp snapshot |
| [contracts.py](../m5/contracts.py) | Catalog 20 bảng, schema, khóa, coverage, digest |
| [batch_writer.py](../m5/batch_writer.py) | Lock, unique index, upsert, verify, công bố snapshot |
| [verify_batch.py](../m5/verify_batch.py) | Kiểm tra bộ đang phục vụ và indexes |
| [queries.py](../m5/queries.py), [metrics.py](../m5/metrics.py) | Lọc đúng chiều dữ liệu, gộp KPI từ count/sum |
| [app.py](../app.py), [charts.py](../m5/charts.py), [dashboard.css](../assets/dashboard.css) | Trang dashboard, biểu đồ và giao diện |
| [load_parquet.py](../m5/load_parquet.py) | Adapter tùy chọn đọc KPI/box Parquet trên HDFS |
| [stream_writer.py](../m5/stream_writer.py), [contract M4](../contracts/M4_TO_M5.md) | Phần tích hợp streaming chờ M4 |

Luồng đọc code dễ trình bày:
`load_m2.ps1 → load_batch.py → contracts.py → batch_writer.py → MongoDB`,
sau đó `app.py → queries.py/metrics.py → charts.py → trình duyệt`.
Collection `kpi_*` chứa số đếm và chỉ số ở các mức ngày/tháng/năm, hãng,
sân bay xuất phát hoặc tuyến; `box_*` chứa thống kê phân bố delay. Catalog
và khóa nghiệp vụ nằm trong `m5/contracts.py`. Mỗi document dữ liệu chuẩn
có `snapshot_id`; unique index ghép mã này với khóa nghiệp vụ để tránh trùng.

`batch_runs` lưu trạng thái, nguồn và kết quả đối chiếu; `serving_state`
chọn snapshot đang phục vụ; `serving_locks` ngăn hai loader chạy đồng thời.
`route_carrier_counts` bổ sung số chuyến theo hãng–tuyến và
`route_carrier_state` chọn phiên bản bổ sung đã kiểm tra. Các ví dụ xem
document/index bằng Compass hoặc mongosh ở mục 7.2–7.3.

## 14. Lỗi thường gặp và thao tác xử lý

| Hiện tượng | Nguyên nhân thường gặp | Thao tác |
|---|---|---|
| `AeroProject is not recognized` | Quên `$` trước tên biến | Khai báo lại đúng mục 4 |
| `Join-Path ... Path is null` | Biến chưa được khai báo trong terminal hiện tại | Chạy lại khối khai báo đường dẫn |
| `Test-Path` trả `False` | Đứng sai chỗ, thiếu code hoặc thiếu snapshot | Xem `Get-Location`, File Explorer và sửa đường dẫn |
| `docker` không được nhận diện | Chưa cài hoặc PATH terminal chưa cập nhật | Cài Docker Desktop/mở lại terminal |
| Không kết nối được Docker daemon | Docker Desktop chưa hoạt động | Mở Docker Desktop rồi thử `docker version` |
| Script `.ps1` bị chặn | Execution Policy của máy | Dùng phụ lục A |
| `port is already allocated` | Cổng Windows bị ứng dụng khác chiếm | Đổi `.env` theo mục 5.2 |
| Thiếu manifest/JSONL hoặc schema/count sai | Trỏ thư mục cha hoặc bộ nhận thiếu/hỏng | Nhận lại đúng snapshot, không sửa manifest để lách kiểm tra |
| `Another loader is running` | Loader trước còn chạy hoặc lease chưa hết | Chờ; lease sau loader bị kill hết hạn tối đa 10 phút |
| Dashboard chưa có snapshot | Chưa nạp thành công | Chạy 6.2, 7.1 rồi Làm mới dữ liệu |
| Dashboard có tổng khác 29.328.846 | Đang lọc kỳ/nguồn snapshot khác | Chọn toàn kỳ và xem active snapshot ở trang vận hành |
| Compass không kết nối | Sai cổng hoặc MongoDB chưa healthy | Xem `docker compose -f compose.yml ps`; dùng URI Windows |
| ParserError sau `spark.stop()`/Python | Dán sai ngôn ngữ vào PowerShell | M5 dùng các lệnh PowerShell ở đây; không cần notebook |
| HDFS thiếu bảng/không resolve hostname | Chưa có output M2 hoặc mạng sai | Kiểm tra mục 12; JSONL không cần HDFS |
| Trang Streaming chờ | Chưa tích hợp M4 | Nghiệm thu batch riêng; theo contract để nối M4 |

Đọc trạng thái/log khi cần, trong PowerShell tại `serving-layer`:

```powershell
docker compose -f compose.yml ps
docker compose -f compose.yml logs --tail 100 mongo dashboard
Get-Content .\logs\load_m2.log -Tail 60
Get-Content .\logs\verify_m5.log -Tail 60
```

Hai file log cuối chỉ có sau khi chạy script tương ứng. Dùng lệnh Docker
trực tiếp theo phụ lục A sẽ không tự tạo các log wrapper này.

## 15. Checklist hoàn tất để bàn giao

- [ ] Người nhận có code M5 và snapshot M2 thực tế ngoài Git.
- [ ] Các đường dẫn mục 4 đúng, đủ 20 JSONL và manifest.
- [ ] Docker đọc được Server; MongoDB và dashboard healthy.
- [ ] CheckOnly PASS, nạp thật PASS, verify 20 collections PASS.
- [ ] Nạp lại cùng snapshot không tăng số document.
- [ ] Dashboard lọc được dữ liệu; giải thích đúng đơn vị, kỳ và mẫu số.
- [ ] Có ảnh và log/report đúng lần chạy; đã tạo ZIP evidence.
- [ ] Người nhận biết dừng/start mà giữ dữ liệu, biết vị trí output.
- [ ] Ghi rõ streaming M4 còn chờ tích hợp; không gọi historical animation là live.

## Phụ lục A. Chạy bằng lệnh Docker nếu `.ps1` bị chặn

Khai báo biến và kiểm tra đầu vào theo mục 4 trước. Chạy **từng khối theo thứ
tự**, không tiếp tục nếu có lỗi. Các lệnh dưới chạy tại PowerShell trong
`serving-layer`, không yêu cầu đổi Execution Policy.

### A.1. Khởi động

```powershell
docker compose -f compose.yml config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Compose config failed.' }
docker compose -f compose.yml up -d --build --wait --wait-timeout 180 mongo dashboard
if ($LASTEXITCODE -ne 0) { throw 'M5 startup failed.' }
docker compose -f compose.yml ps
```

### A.2. Kiểm tra đầu vào và nạp thật

Biến `${AeroSnapshot}` có ngoặc nhọn để PowerShell hiểu đúng dấu `:` trong
tham số volume; giữ nguyên cú pháp. Docker nhận đường dẫn Windows và mount
read-only vào `/data/snapshot`.

```powershell
docker compose -f compose.yml run --rm --build --no-deps --volume "${AeroSnapshot}:/data/snapshot:ro" loader python -m m5.load_batch --snapshot /data/snapshot --check-only
if ($LASTEXITCODE -ne 0) { throw 'M2 input check failed.' }
docker compose -f compose.yml run --rm --build --volume "${AeroSnapshot}:/data/snapshot:ro" loader python -m m5.load_batch --snapshot /data/snapshot
if ($LASTEXITCODE -ne 0) { throw 'M5 load failed.' }
```

### A.3. Verify, mở dashboard và dừng

```powershell
docker compose -f compose.yml run --rm --build loader python -m m5.verify_batch
if ($LASTEXITCODE -ne 0) { throw 'M5 verify failed.' }
Start-Process 'http://localhost:8501'
```

Dừng sau buổi demo, vẫn giữ volume:

```powershell
docker compose -f compose.yml stop
```

Báo cáo JSON vẫn nằm trong `evidence`; các lệnh trực tiếp không tự lưu
`logs\start_m5.log`, `logs\load_m2.log`, `logs\verify_m5.log` như scripts.
Muốn dùng các script kiểm thử/đóng gói trên máy chặn `.ps1`, có thể gọi
PowerShell với policy chỉ cho **tiến trình đó**, sau khi đã đọc script của repo:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\test_m5.ps1
if ($LASTEXITCODE -ne 0) { throw 'M5 tests failed.' }
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\collect_evidence.ps1
if ($LASTEXITCODE -ne 0) { throw 'M5 evidence collection failed.' }
```

Chính sách do tổ chức quản lý có thể vẫn chặn cách này; khi đó dùng máy
được phép chạy script hoặc nhờ người quản lý môi trường xử lý, giữ lại
báo cáo JSON và ảnh để bàn giao. Không coi thiếu log wrapper là lỗi ingest.
