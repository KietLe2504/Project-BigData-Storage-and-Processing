# AERO — Chạy từ đầu đến đầy đủ output M2

Tài liệu dành cho **Windows + PowerShell + Docker Desktop dùng WSL 2**. Quy trình
đi từ chuẩn bị CSV BTS đến Parquet sạch, KPI lịch sử, box-plot, bằng chứng Spark
và bộ file bàn giao M5. Các đường dẫn, tên service và tên script được đối chiếu
với code hiện có trong repository.

**Nếu đã tải đủ 51 CSV như ảnh SUMMARY, bắt đầu từ mục 4. Không cần tải lại.**
Vẫn đọc mục 2 để khai báo đường dẫn. Nếu đã có Parquet và verifier đạt, chuyển
đến mục 9; nếu đã có đầy đủ KPI/box, chuyển đến mục 12–13 để kiểm tra và xuất.

## 1. Kết quả cần đạt và thứ tự chạy

```text
batch_data_bureau.ipynb             Tải và chuẩn hóa CSV nguồn
                ↓
BTS_ZIP trên Windows
                ↓ hdfs dfs -put
/aero/raw/bts trên HDFS
                ↓ 06_batch_process_all.py
/aero/processed/year=YYYY/month=MM  Parquet từng chuyến bay đã làm sạch
                ↓ 08_verify_partition.py
RESULT: PASS                       Kiểm tra đủ kỳ và ngày/phân vùng
                ↓ eda_lite.ipynb
/aero/analytics/eda/base            Bảng tổng hợp trung gian
/aero/analytics/eda/kpi             13 bảng KPI lịch sử
/aero/analytics/eda/box             7 bảng thống kê box-plot
spark_jobs/evidence                Execution plans và tóm tắt kỹ thuật
                ↓ 09_export_m2_outputs.py
spark_jobs/export/m2_to_m5/...      CSV + JSONL + manifest để bàn giao M5
```

Phạm vi dữ liệu hiện tại là **2022-01 đến 2026-03, tổng cộng 51 tháng**. Một số
đoạn README/PDF còn nhắc giai đoạn mẫu 2020-01; hướng dẫn này dùng phạm vi của
script hiện tại.

| Nhóm đầu ra M2 | Nơi lưu | Dấu hiệu hoàn thành |
|---|---|---|
| Dữ liệu sạch | HDFS `/aero/processed` | 51 tháng, verifier báo `PASS` |
| KPI lịch sử | HDFS `/aero/analytics/eda/kpi` | Đủ 13 bảng của notebook lite |
| Thống kê box-plot | HDFS `/aero/analytics/eda/box` | Đủ 7 bảng của notebook lite |
| Kết quả phân tích | Notebook đã chạy | Các bảng phân tích có output mới |
| Bằng chứng kỹ thuật | `spark_jobs/evidence` | 5 nhóm evidence, plans và summary |
| Bộ bàn giao M5 | `spark_jobs/export/m2_to_m5/<UTC timestamp>` | 20 CSV + 20 JSONL + manifest |
| Bằng chứng vận hành | `logs` | Log ETL, verifier, export và log EDA nếu chạy terminal |

MongoDB, dashboard và Kubernetes/Cloud là các công việc tiếp theo. Chạy đến
output M2 bằng cấu hình local hiện tại không cần cài chúng.

## 2. Chuẩn bị môi trường và quy ước terminal

### 2.1. Phần mềm và tài nguyên

| Chuẩn bị | Khi nào dùng |
|---|---|
| Docker Desktop đang chạy, có WSL 2 backend | HDFS, Spark và Jupyter cho EDA |
| Python trên Windows có lệnh `py -3` | Khi tải BTS bằng notebook trên Windows |
| Trình duyệt | Jupyter và giao diện HDFS |
| VS Code | Tùy chọn, để sửa cấu hình notebook và đọc code |
| Internet | Tải dữ liệu, images và thư viện |
| Dung lượng trống | CSV đã chọn khoảng 5,2–5,3 GB; cần thêm chỗ cho HDFS, Docker images, Parquet và export |

Dự phòng vài chục GB trống trên ổ chứa project và ổ chứa dữ liệu Docker.
Spark trong hướng dẫn dùng `local[2]` và driver 2 GB; Docker còn phải đủ RAM cho
HDFS và các tiến trình Python. Chạy ETL, verifier, EDA, export lần lượt.

### 2.2. Nơi chạy lệnh

- Khối `powershell`: dán vào PowerShell trên Windows.
- Khối `python` trong mục notebook: chạy trong cell notebook được chỉ định.
- Lệnh `docker compose exec ...` tự chạy phần sau trong container; không cần
  mở shell container rồi dán lại nguyên lệnh.
- Trong lệnh PowerShell nhiều dòng, ký tự backtick ở cuối dòng phải là ký tự
  cuối cùng; không thêm dấu cách phía sau.

Sử dụng hai cửa sổ khi chạy Jupyter:

- **Terminal A:** các bước kiểm tra, Docker, ETL, verifier, export.
- **Terminal B:** giữ Jupyter chạy, không đóng khi notebook còn làm việc.

### 2.3. Khai báo đường dẫn

Chạy trong Terminal A. Nếu thư mục của bạn khác, sửa dòng đầu tiên:

```powershell
$AeroProject = 'F:\Project-BigData-Storage-and-Processing'
$AeroBatch = Join-Path $AeroProject 'batch-layer'
Set-Location $AeroBatch

Test-Path .\docker-compose.yml
Test-Path .\spark_jobs\06_batch_process_all.py
Test-Path .\spark_jobs\08_verify_partition.py
Test-Path .\spark_jobs\eda_lite.ipynb
Test-Path .\spark_jobs\09_export_m2_outputs.py

New-Item -ItemType Directory -Force .\logs | Out-Null
```

Cả 5 kết quả `Test-Path` phải là `True`. Nếu vừa mở cửa sổ PowerShell mới, chạy
lại ba dòng khai báo đường dẫn trước khi dùng các biến `$AeroProject`/`$AeroBatch`.

Kiểm tra Docker:

```powershell
docker version
docker compose version
```

`docker version` cần đọc được cả Client và Server. Nếu không kết nối được Server,
mở Docker Desktop và chờ engine sẵn sàng.

## 3. Tải CSV BTS nếu chưa có dữ liệu

Nếu đã có 51 CSV thành công, chuyển sang mục 4.

### 3.1. Tạo môi trường Python tải dữ liệu trên Windows

Chạy trong Terminal A:

```powershell
Set-Location $AeroProject
py -3 --version
py -3 -m venv .\batch-layer\.venv

.\batch-layer\.venv\Scripts\python.exe -m pip install jupyterlab ipykernel requests pandas tqdm

.\batch-layer\.venv\Scripts\python.exe -m ipykernel install --sys-prefix --name aero-download --display-name 'AERO Download (Windows)'

.\batch-layer\.venv\Scripts\python.exe -m jupyterlab --port=8889
```

Không cần activate virtual environment; gọi trực tiếp `python.exe` như trên sẽ
tránh vướng Execution Policy của PowerShell.

Mở URL có token được in ra, chọn `batch_data_bureau.ipynb` ở thư mục gốc project.
Chọn kernel **AERO Download (Windows)**. Đây là notebook tải CSV; kernel Python
Windows dùng được cho bước này. Các gói tải đã được cài bằng lệnh trên; có thể
bỏ qua cell đầu `!pip ...` và chạy cell chứa code downloader sau khi sửa cấu hình.

### 3.2. Sửa nơi lưu trước khi tải

Trong cell cấu hình của notebook, thay đường dẫn mặc định Kaggle bằng:

```python
OUTPUT_DIR = Path(
    r"F:\Project-BigData-Storage-and-Processing\batch-layer\BTS_ZIP"
)
```

Nếu project nằm nơi khác, thay đúng đường dẫn Windows. Giữ:

```python
START_YEAR, START_MONTH = 2022, 1
END_YEAR, END_MONTH = 2026, 3
```

Chạy các cell từ trên xuống và chờ SUMMARY. Notebook tải ZIP theo tháng, chọn
38 trường, chuẩn hóa tên cột, ghi CSV và xóa ZIP tạm sau khi xử lý.

Điều kiện tiếp tục:

```text
SUCCESS + SKIPPED = 51
NOT_AVAILABLE: 0
FAILED: 0
CSV count: 51
```

`SKIPPED` nghĩa là file đã có và vượt qua kiểm tra cơ bản của downloader; không
phải lỗi. Nếu có tháng thất bại, xem lỗi và chạy lại downloader sau khi xử lý
nguyên nhân. Kiểm tra skip chỉ gồm header và có dòng mẫu, không phải đối soát
toàn bộ file.

### 3.3. Nếu đã tải vào đường dẫn Kaggle mặc định

Trong chính kernel đã tải, chạy:

```python
print(OUTPUT_DIR.resolve())
```

- Nếu notebook thực sự chạy trên Kaggle, tải các CSV và manifest về Windows.
- Nếu chạy trên Windows nhưng giữ `Path('/kaggle/working/BTS_ZIP')`, kết quả có
  thể nằm ở thư mục `\kaggle\working\BTS_ZIP` trên ổ đĩa của kernel. Dùng đúng
  đường dẫn `resolve()` in ra để mở File Explorer.

Copy 51 CSV và `manifest.json` vào `batch-layer\BTS_ZIP`. Không cần tải lại.

Khi đã có dữ liệu, tắt server Jupyter tải CSV bằng `Ctrl+C` trong terminal chạy
server, xác nhận tắt nếu được hỏi, rồi chuyển lại thư mục batch:

```powershell
Set-Location $AeroBatch
```

## 4. Đặt đúng CSV và kiểm tra đủ tên file

### 4.1. Cấu trúc thư mục

```text
Project-BigData-Storage-and-Processing/
├── batch_data_bureau.ipynb
└── batch-layer/
    ├── docker-compose.yml
    ├── BTS_ZIP/
    │   ├── On_Time_Reporting_2022_1.csv
    │   ├── On_Time_Reporting_2022_2.csv
    │   ├── ...
    │   ├── On_Time_Reporting_2026_3.csv
    │   └── manifest.json
    └── spark_jobs/
        ├── 06_batch_process_all.py
        ├── 08_verify_partition.py
        ├── 09_export_m2_outputs.py
        └── eda_lite.ipynb
```

CSV nằm trực tiếp trong `BTS_ZIP`, không lồng thành `BTS_ZIP\BTS_ZIP`. Tên CSV
đầu vào dùng tháng **không thêm số 0**: `2022_1.csv`, không phải `2022_01.csv`.
Thư mục output Parquet dùng `month=01` là đúng; đó là quy ước khác của đầu ra.

### 4.2. Kiểm tra đủ 51 file dự kiến, không chỉ đếm số file

Chạy trong Terminal A:

```powershell
Set-Location $AeroBatch

$AeroExpectedNames = @(
    foreach ($AeroYear in 2022..2026) {
        $AeroLastMonth = if ($AeroYear -eq 2026) { 3 } else { 12 }
        foreach ($AeroMonth in 1..$AeroLastMonth) {
            "On_Time_Reporting_${AeroYear}_${AeroMonth}.csv"
        }
    }
)

$AeroMissingNames = @(
    $AeroExpectedNames | Where-Object {
        -not (Test-Path (Join-Path '.\BTS_ZIP' $_))
    }
)

if ($AeroMissingNames.Count -gt 0) {
    $AeroMissingNames
    throw 'Chua du 51 CSV dung ten. Sua lai truoc khi chay ETL.'
}

$AeroEmptyFiles = @(Get-ChildItem .\BTS_ZIP -Filter *.csv | Where-Object Length -eq 0)
if ($AeroEmptyFiles.Count -gt 0) {
    $AeroEmptyFiles.Name
    throw 'Co CSV rong.'
}

(Get-ChildItem .\BTS_ZIP -Filter *.csv).Count
Get-Content .\BTS_ZIP\On_Time_Reporting_2022_1.csv -TotalCount 1
```

Cần đủ 51 tên dự kiến. Nếu số lượng lớn hơn 51, kiểm tra các file thừa trước khi
nạp vì lệnh glob bên dưới có thể lấy cả các file cùng mẫu. Header từ downloader
gồm 38 trường, có `FL_DATE`, `ORIGIN`, `DEST`, `OP_CARRIER`, `DEP_DELAY`,
`ARR_DELAY`, `CANCELLED`…

ZIP BTS gốc có tên cột khác CSV chuẩn hóa; dùng CSV do downloader của project
tạo ra để khớp ETL hiện tại.

## 5. Khởi động và kiểm tra HDFS/Spark

### 5.1. Dựng các container

```powershell
Set-Location $AeroBatch
docker compose config
docker compose up -d
docker compose ps
```

Compose hiện có 3 service `namenode`, `datanode`, `spark`. Cổng Jupyter `8888`
đã có trong file Compose hiện tại; không cần thêm lần nữa.

### 5.2. Kiểm tra DataNode và safe mode

```powershell
docker compose exec -u root namenode hdfs dfsadmin -report
docker compose exec -u root namenode hdfs dfsadmin -safemode get
```

Chỉ nạp/ghi dữ liệu khi có **1 Live DataNode** và **Safe mode OFF**. Lúc mới
khởi động, chờ service sẵn sàng rồi kiểm tra lại. Không tắt safe mode cưỡng bức
để bỏ qua lỗi DataNode.

Xem giao diện HDFS tại `http://localhost:9870`.

Nếu chưa sẵn sàng:

```powershell
docker compose logs --tail 100 namenode datanode
```

### 5.3. Kiểm tra mount và Spark

```powershell
docker compose exec namenode bash -lc 'ls -lh /data/input/On_Time_Reporting_2022_1.csv'
docker compose exec spark bash -lc 'ls -l /opt/spark_jobs/06_batch_process_all.py /opt/spark_jobs/09_export_m2_outputs.py'
docker compose exec -u root spark /opt/spark/bin/spark-submit --version
```

Spark image của repo là **3.5.3**. Nếu không thấy CSV/script, kiểm tra vị trí file
trên Windows và mount trong Compose trước khi sửa đường dẫn HDFS.

## 6. Nạp CSV vào HDFS raw

Mount `/data/input` chỉ cho container nhìn thấy file Windows. ETL chính đọc
`hdfs://namenode:9000/aero/raw/bts`, nên cần bước nạp riêng.

### 6.1. Tạo thư mục HDFS

```powershell
docker compose exec -u root namenode hdfs dfs -mkdir -p /aero/raw/bts /aero/processed /aero/analytics /aero/warehouse
```

Các lệnh Spark/Jupyter trong hướng dẫn cũng dùng `-u root` để thống nhất user
ghi trong môi trường local này. Không cần mở quyền toàn bộ HDFS bằng `chmod 777`.

### 6.2. Lần nạp đầu tiên

```powershell
docker compose exec -T -u root namenode bash -c 'hdfs dfs -put /data/input/On_Time_Reporting_*.csv /aero/raw/bts/'
if ($LASTEXITCODE -ne 0) { throw 'Nap HDFS chua thanh cong. Kiem tra log.' }
```

Dùng `bash -c` để mở rộng mẫu `*.csv` trong container và giữ `PATH` được
container cấu hình. Không đổi thành `bash -lc`: login shell có thể đặt lại
`PATH`, gây lỗi `bash: hdfs: command not found` dù gọi trực tiếp `namenode hdfs`
vẫn chạy được. Nếu gặp lỗi này, chạy lại khối lệnh đã sửa ở trên; lần gọi bị lỗi
chưa thực thi `hdfs`, nên chưa nạp CSV từ lần gọi đó.

Nếu báo `File exists`, không thêm `-f` một cách tự động. Nếu trước đó đã nạp
đủ và xác nhận dữ liệu đúng, bỏ qua bước nạp. Nếu lần nạp bị ngắt và cần bổ sung
các file còn thiếu, dùng đoạn sau thay cho lệnh nạp toàn bộ:

```powershell
Set-Location $AeroBatch
foreach ($AeroCsv in Get-ChildItem .\BTS_ZIP -Filter 'On_Time_Reporting_*.csv') {
    $AeroRawPath = '/aero/raw/bts/' + $AeroCsv.Name
    docker compose exec -T -u root namenode hdfs dfs -test -e $AeroRawPath
    if ($LASTEXITCODE -eq 0) {
        Write-Host ('SKIP existing: ' + $AeroCsv.Name)
    } else {
        docker compose exec -T -u root namenode hdfs dfs -put ('/data/input/' + $AeroCsv.Name) /aero/raw/bts/
        if ($LASTEXITCODE -ne 0) { throw ('Nap that bai: ' + $AeroCsv.Name) }
    }
}
```

Đoạn bổ sung chỉ kiểm tra file đã tồn tại; nếu nghi file bị thiếu nội dung,
phải đối soát file đó và quyết định cách thay thế trước khi chạy ETL.

### 6.3. Kiểm tra sau khi nạp

```powershell
docker compose exec namenode hdfs dfs -ls /aero/raw/bts
docker compose exec namenode hdfs dfs -count /aero/raw/bts
```

Kết quả `-count` có các cột `DIR_COUNT FILE_COUNT CONTENT_SIZE PATH`;
`FILE_COUNT` cần là **51** nếu chỉ nạp 51 CSV theo hướng dẫn.

## 7. Chạy batch ETL cho 51 tháng

### 7.1. Chạy ETL và lưu log

Terminal A, thư mục `batch-layer`:

```powershell
New-Item -ItemType Directory -Force .\logs | Out-Null

docker compose exec -T -u root spark /opt/spark/bin/spark-submit `
  --master 'local[2]' `
  --driver-memory 2g `
  --conf spark.sql.shuffle.partitions=8 `
  --conf spark.hadoop.fs.defaultFS=hdfs://namenode:9000 `
  /opt/spark_jobs/06_batch_process_all.py 2>&1 |
  Tee-Object -FilePath .\logs\06_batch_process_all.log

if ($LASTEXITCODE -ne 0) { throw 'ETL that bai. Doc logs\06_batch_process_all.log.' }
```

Script đọc lần lượt 51 tháng, kiểm tra cột bắt buộc, lọc dữ liệu thiếu, trim mã
sân bay, loại trùng theo khóa sẵn có và ghi Parquet. Mỗi tháng in `Input rows`,
`Output rows`, `Removed rows` và `Dedup keys`; giữ log này để giải thích cleaning.

Điều kiện tiếp tục:

```text
Successful: 51 / 51
Failed    : 0 / 51
```

Log Spark có thể chứa WARN dù job thành công. Đánh giá cùng exit code và phần
summary, không chỉ dựa vào màu chữ của PowerShell.

### 7.2. Kiểm tra một phân vùng

```powershell
docker compose exec namenode hdfs dfs -ls /aero/processed/year=2022/month=01
```

Cần thấy file part Parquet và thông thường có `_SUCCESS`. Script ETL dùng
`overwrite` theo từng tháng; chạy lại sẽ dựng lại các phân vùng tháng.

Không cần chạy tuần tự các script `02`, `03`, `04`, `05`: chúng là tiện ích giai
đoạn đầu, nhiều script cố định tháng 2023-01. `07_retry_2022_01.py` chỉ dành cho
khôi phục tháng 2022-01 khi có lỗi được xác định.

## 8. Xác minh dữ liệu sạch trên toàn bộ kỳ

```powershell
docker compose exec -T -u root spark /opt/spark/bin/spark-submit `
  --master 'local[2]' `
  --driver-memory 2g `
  --conf spark.sql.shuffle.partitions=8 `
  --conf spark.hadoop.fs.defaultFS=hdfs://namenode:9000 `
  /opt/spark_jobs/08_verify_partition.py 2>&1 |
  Tee-Object -FilePath .\logs\08_verify_partition.log

if ($LASTEXITCODE -ne 0) { throw 'Verifier that bai. Chua chuyen sang EDA.' }
```

Phần cuối cần có:

```text
Expected months: 51
Months with rows: 51
Invalid/null dates: 0
Date/partition mismatches: 0
Missing result months: []
RESULT: PASS
```

Lần chạy trước của nhóm ghi nhận **29.328.846 dòng**. Dùng số của lần chạy hiện
tại trong báo cáo; nếu khác, đối chiếu nguồn, log cleaning và phạm vi.

`PASS` ở đây xác nhận các kiểm tra được cài đặt: đủ phân vùng, có dòng, đọc được
Parquet và ngày khớp phân vùng. Nó chưa thay thế đối soát độc lập nguồn–đích,
kiểm tra hết trùng trên toàn kỳ hoặc kiểm thử mọi công thức KPI.

## 9. Chuẩn bị thư viện cho EDA trong container Spark

Notebook EDA cần kernel trong container. Python Windows dùng tải CSV ở mục 3
không phải môi trường chạy EDA theo cấu hình HDFS hiện tại.

### 9.1. Cài Jupyter và thư viện

```powershell
docker compose exec -u root spark python3 -m pip --version
```

Nếu thiếu pip:

```powershell
docker compose exec -u root spark bash -lc 'apt-get update && apt-get install -y python3-pip'
```

Cài thư viện:

```powershell
docker compose exec -u root spark python3 -m pip install jupyterlab nbconvert ipykernel pandas pyarrow pyspark==3.5.3

docker compose exec -u root spark python3 -m ipykernel install --sys-prefix --name aero-spark --display-name 'AERO Spark (Docker)'
```

Giữ PySpark **3.5.3** để khớp Spark image. Không dùng lệnh cài PySpark không
ghim phiên bản trong một số tài liệu cũ. pip sẽ chọn các phiên bản còn hỗ trợ
Python của container cho các thư viện không ghim.

Ghi nhận môi trường thực chạy:

```powershell
docker compose exec -u root spark python3 -m pip freeze |
  Out-File -Encoding utf8 .\logs\spark_python_packages.txt

docker compose exec -u root spark java -version
```

Thư viện cài trực tiếp trong container có thể mất khi container được tạo lại;
khi đó thực hiện lại mục 9.

### 9.2. Chọn một trong hai cách chạy EDA

- **Cách A — mục 10:** Jupyter, xem từng cell; phù hợp khi mới làm quen.
- **Cách B — mục 11:** chạy bằng terminal, lưu notebook đã thực thi tự động.

Chỉ chạy **một cách tại một thời điểm**. Cả hai dùng `eda_lite.ipynb`.
`eda.ipynb` là bản cũ, có cấu trúc output khác và dùng chung analytics root;
không chạy xen kẽ hai bản trong quy trình này.

## 10. Cách A: chạy EDA bằng Jupyter

### 10.1. Khởi động Jupyter trong Terminal B

Mở PowerShell thứ hai và chạy:

```powershell
Set-Location F:\Project-BigData-Storage-and-Processing\batch-layer

docker compose exec -u root spark bash -lc 'cd /opt/spark_jobs && jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --allow-root --notebook-dir=/opt/spark_jobs'
```

Giữ Terminal B mở. Dùng URL có token được in ra, ví dụ
`http://localhost:8888/lab?token=...`, rồi mở `eda_lite.ipynb`.
Chọn kernel **AERO Spark (Docker)**. Notebook đã ở trong thư mục mount, không
cần copy thêm.

Nếu dùng VS Code, chọn Existing Jupyter Server và URL server container này.

### 10.2. Kiểm tra kernel và cấu hình

Trong một cell kiểm tra tạm:

```python
import os
import sys

print(sys.executable)
print(os.path.isdir('/opt/spark'))
```

Dòng thứ hai phải là `True`, đường dẫn Python không bắt đầu bằng ổ Windows.

Trong **cell code đầu tiên** của notebook, kiểm tra:

```python
MONTHS = month_range((2022, 1), (2026, 3))
FORCE_REBUILD = False
EVIDENCE_DIR = '/opt/spark_jobs/evidence'
```

Dòng `EVIDENCE_DIR` thay cho dòng cấu hình hiện có để plan luôn về đúng thư mục
Windows được mount. Giữ các đường dẫn mặc định:

```text
PROCESSED = /aero/processed
ANALYTICS = /aero/analytics/eda
HDFS_URI  = hdfs://namenode:9000
```

Nếu thử trước 3 tháng, có thể dùng `month_range((2022, 1), (2022, 3))`; sau đó
phải đặt lại 51 tháng và chạy lại từ cell cấu hình đến build để có output đủ kỳ.
Kết quả 3 tháng chưa phải bộ bàn giao đầy đủ.

### 10.3. Chạy đủ 9 cell code theo thứ tự

Không đếm các cell Markdown:

| Cell code | Công việc | Output cần theo dõi |
|---|---|---|
| 1 | Cấu hình và Spark session | Spark/PySpark 3.5.3, phạm vi 51 tháng |
| 2 | Nạp và chuẩn hóa | Định nghĩa hàm |
| 3 | Tính tổng/đếm, rollup, tỷ lệ | Định nghĩa hàm KPI |
| 4 | Histogram và box-plot | Định nghĩa hàm phân phối |
| 5 | Pipeline ghi bảng | Định nghĩa hàm build |
| 6 | Chạy pipeline | Build từng tháng, KPI, box; thông báo hoàn tất |
| 7 | Hàm phân tích | Định nghĩa hàm |
| 8 | Xem phân tích | Các bảng tổng quan, xu hướng, hãng, sân bay, tuyến… |
| 9 | UDF, custom aggregation và bằng chứng Spark | Output đối chiếu, plan và evidence summary |

Cell 6 nặng nhất và cần chờ xong. Điều kiện tiếp tục:

```text
Bước 1/3 – từng tháng ...
Bước 2/3 – cuộn lên các mức KPI…
Bước 3/3 – box-plot từ biểu đồ tần suất…
Hoàn tất sau ...s → /aero/analytics/eda
```

`FORCE_REBUILD=False` bỏ qua tháng có thư mục histogram. Cơ chế này chỉ kiểm tra
thư mục tồn tại, chưa kiểm tra tính toàn vẹn mọi bảng. Nếu lần trước bị ngắt lúc
ghi hoặc đã thay dữ liệu/logic của tháng cũ, đặt `FORCE_REBUILD=True` để dựng lại
các tháng cần thiết, rồi đổi về `False`. Với bộ dữ liệu từng chạy bằng notebook
cũ, dựng lại đầy đủ 51 tháng bằng bản lite để tránh trộn schema giữa hai bản.

### 10.4. Lưu notebook có output

Sau khi cell 8 và 9 hoàn tất, dùng **Save Notebook As / Save As** để lưu bản có
output vào:

```text
/opt/spark_jobs/evidence/eda_lite.executed.ipynb
```

Tương ứng Windows:

```text
batch-layer\spark_jobs\evidence\eda_lite.executed.ipynb
```

Chỉ chạy đến cell 6 là đủ tạo dữ liệu KPI/box để export. Để có output M2 phục vụ
báo cáo, tiếp tục cell 7–9 và kiểm tra bằng chứng ở mục 12.

## 11. Cách B: chạy toàn bộ EDA bằng terminal

Bỏ qua mục này nếu đã chạy Cách A. Đóng kernel Spark của cách A trước khi dùng
cách B; server Jupyter không cần chạy để `nbconvert` thực thi notebook.

### 11.1. Kiểm tra cấu hình notebook trước khi chạy

Đảm bảo cell cấu hình `eda_lite.ipynb` giữ analytics root mặc định và
`FORCE_REBUILD=False` cho lần chạy mới. Nếu cần dựng lại các tháng đã thay đổi,
chỉnh `FORCE_REBUILD=True` trước khi chạy, rồi trả về `False` khi hoàn tất.

Lệnh sau đặt phạm vi 51 tháng bằng biến môi trường mà notebook hiện đã hỗ trợ.

### 11.2. Thực thi và lưu output

Terminal A, thư mục `batch-layer`:

```powershell
docker compose exec -u root spark mkdir -p /opt/spark_jobs/evidence

docker compose exec -T -u root `
  -e AERO_MONTHS=2022-01:2026-03 `
  -e AERO_EVIDENCE=/opt/spark_jobs/evidence `
  spark bash -lc 'cd /opt/spark_jobs && python3 -m jupyter nbconvert --to notebook --execute eda_lite.ipynb --ExecutePreprocessor.kernel_name=aero-spark --ExecutePreprocessor.timeout=-1 --output eda_lite.executed.ipynb --output-dir /opt/spark_jobs/evidence' 2>&1 |
  Tee-Object -FilePath .\logs\eda_lite.log

if ($LASTEXITCODE -ne 0) { throw 'EDA that bai. Doc logs\eda_lite.log truoc khi export.' }
```

Đây là lệnh thực sự chạy lại các cell. Không chạy đồng thời ETL, verifier hay
export. Timeout `-1` cho phép cell dài chạy đến khi xong; nếu treo, dùng log và
trạng thái tài nguyên để điều tra.

Mở file sau bằng VS Code/Jupyter để xem output; không cần chạy lại các cell chỉ
để đọc kết quả đã lưu:

```text
batch-layer\spark_jobs\evidence\eda_lite.executed.ipynb
```

Notebook có một số `try/except` cho phần bằng chứng, nên exit code thành công
chưa đảm bảo đủ mọi evidence. Tiếp tục mục 12.

## 12. Kiểm tra đầy đủ kết quả EDA và bằng chứng kỹ thuật

### 12.1. Kiểm tra các thư mục HDFS

Terminal A:

```powershell
docker compose exec namenode hdfs dfs -ls /aero/analytics/eda/base
docker compose exec namenode hdfs dfs -ls /aero/analytics/eda/kpi
docker compose exec namenode hdfs dfs -ls /aero/analytics/eda/box
```

`base/` của bản lite tạo 5 bảng KPI cơ sở và 1 histogram. Các thư mục dư từ lần
chạy notebook cũ, nếu có, không được tính vào bộ 13 KPI/7 box của bản lite.

13 bảng KPI cần có:

```text
day_overall                 calendar_day_overall
month_overall               month_of_year_overall
year_overall                month_carrier
month_of_year_carrier       year_carrier
month_origin                year_origin
year_route                  year_carrier_origin
hour_overall
```

7 bảng box cần có:

```text
day_overall
month_overall
month_carrier
month_of_year_overall
month_of_year_carrier
year_overall
year_carrier
```

### 12.2. Kiểm tra evidence summary

```powershell
Set-Location $AeroBatch
Get-ChildItem .\spark_jobs\evidence

$AeroEvidence = Get-Content .\spark_jobs\evidence\summary.txt -Raw -Encoding UTF8 | ConvertFrom-Json
$AeroRequiredEvidence = @(
    'evidence_pruning',
    'evidence_joins',
    'evidence_cache',
    'evidence_bucketing',
    'evidence_optimization'
)

foreach ($AeroName in $AeroRequiredEvidence) {
    if ($AeroEvidence.PSObject.Properties.Name -notcontains $AeroName) {
        throw ('Thieu evidence: ' + $AeroName)
    }
}

if ($AeroEvidence.evidence_joins.same_rowcount -ne $true) {
    throw 'So dong hai cach join khac nhau.'
}
if ($AeroEvidence.evidence_optimization.same_result -ne $true) {
    throw 'Ket qua native filter va UDF khac nhau.'
}

$AeroEvidence | ConvertTo-Json -Depth 10
```

Các file plan kỳ vọng gồm `pruning.txt`, `join_broadcast.txt`, `join_merge.txt`,
`bucketing_plain.txt`, `bucketing_bucketed.txt`, `optimization_native_filter.txt`,
`optimization_udf_filter.txt` và `summary.txt`.

Trong output cell 9, kiểm tra thêm:

- UDF so với biểu thức tham chiếu có **0 dòng lệch**.
- Có bảng trimmed mean; không chỉ thông báo bỏ qua pandas UDF.
- Có kết quả phân tích lan truyền trễ khi dữ liệu có `TAIL_NUM`.
- Không còn thông báo `✗` ở 5 nhóm evidence.

Không yêu cầu thời gian hay số partition giống hệt máy của nhóm. So sánh join
hiện tại kiểm tra bằng số dòng, chưa chứng minh hai tập kết quả bằng nhau từng
giá trị. Các phép kiểm tra này cần được diễn giải đúng trong báo cáo.

### 12.3. Đo lại cache với bộ nhớ đệm sạch nếu dùng benchmark trong báo cáo

**Mục này là tùy chọn, chỉ cần khi dùng số đo cache làm bằng chứng hiệu năng
trong báo cáo. Đây là code Python chạy trong cell notebook, không dán vào
PowerShell.** Nếu chỉ cần bộ KPI/box và export M5, có thể chuyển đến mục 12.4;
không mô tả số đo cache cũ là benchmark đã được kiểm soát.

Cell 9 cache `df_demo` trước khi đo, có thể làm phép đo “không cache” dùng lại
cache cùng logical plan. Chờ các job khác dừng trước khi đo.

- **Nếu đã chạy Cách A và kernel vẫn còn:** thêm một cell code sau cell 9 rồi
  chạy đoạn Python bên dưới trong chính kernel đó.
- **Nếu đã chạy Cách B:** `nbconvert` kết thúc thì kernel cũng kết thúc. File
  `.executed.ipynb` giữ output đã lưu, không giữ các biến/hàm Python đang sống.
  Muốn đo lại, mở Jupyter theo mục 10.1, mở notebook gốc `eda_lite.ipynb`, chọn
  kernel **AERO Spark (Docker)**. Đặt `EVIDENCE_DIR = '/opt/spark_jobs/evidence'`
  trong cell code 1, chạy lần lượt cell code **1–5, rồi 7–9** (đếm theo bảng
  mục 10.3, không đếm cell Markdown). Bỏ qua cell 6 để không chạy lại pipeline
  ghi KPI/box. Các cell 8–9 sẽ chạy lại phần phân tích và các nhóm evidence.
  Sau đó thêm một cell code mới và chạy đoạn dưới.

```python
spark.catalog.clearCache()
EVIDENCE['evidence_cache'] = evidence_cache(df_demo)
print(json.dumps(EVIDENCE['evidence_cache'], indent=2))
save_evidence('summary', json.dumps(EVIDENCE, indent=2, ensure_ascii=False, default=str))
```

Sau khi đo lại, lưu notebook có output vào đường dẫn ở mục 10.4 để giữ cả kết
quả mới; đoạn Python trên cũng cập nhật `summary.txt`. Lưu số liệu, cấu hình và
thời điểm đo thực tế. Nếu đã mở Jupyter để đo lại sau Cách B, thực hiện bước
giải phóng Spark dành cho Cách A ở mục 12.4 trước khi export.

### 12.4. Giải phóng Spark trước khi export

Với Cách A, thêm cell cuối sau khi đã kiểm tra/lưu các kết quả:

```python
spark.stop()
```

Sau đó tắt kernel hoặc server Jupyter bằng `Ctrl+C` trong Terminal B. Với Cách B,
chờ lệnh `nbconvert` thoát; kernel của lần thực thi đó đã kết thúc.

## 13. Xuất bộ dữ liệu M2 để bàn giao M5

### 13.1. Chạy exporter

Terminal A:

```powershell
Set-Location $AeroBatch

docker compose exec -T -u root spark /opt/spark/bin/spark-submit `
  --master 'local[2]' `
  --driver-memory 2g `
  --conf spark.sql.shuffle.partitions=8 `
  --conf spark.hadoop.fs.defaultFS=hdfs://namenode:9000 `
  /opt/spark_jobs/09_export_m2_outputs.py 2>&1 |
  Tee-Object -FilePath .\logs\09_export_m2_outputs.log

if ($LASTEXITCODE -ne 0) { throw 'Export that bai. Chua ban giao bo du lieu nay.' }
```

Script đọc 13 bảng KPI và 7 bảng box, kiểm tra cột bắt buộc, khóa trùng, bảng
rỗng và giới hạn số dòng. Mỗi bảng được xuất CSV + JSONL. Manifest được ghi kèm
schema thực tế, số dòng, khóa, nguồn và phạm vi tháng. Script không tạo dữ liệu
giả và không nạp MongoDB.

Điều kiện tiếp tục:

```text
EXPORT COMPLETE: /opt/spark_jobs/export/m2_to_m5/<UTC timestamp>
Coverage: 51 months; ... flights
```

Nếu phạm vi chưa đủ, exporter có thể vẫn xuất thành công và in NOTE. Phải kiểm
tra manifest ở bước tiếp theo để nghiệm thu bộ **đủ 51 tháng**.

### 13.2. Tìm kết quả trên Windows

Compose mount `./spark_jobs` vào `/opt/spark_jobs`, nên bộ xuất xuất hiện tại:

```text
F:\Project-BigData-Storage-and-Processing\batch-layer\spark_jobs\export\m2_to_m5\<UTC timestamp>\
```

Không cần `docker cp` cho các file này. Lấy bộ hoàn tất mới nhất:

```powershell
$AeroExportRoot = Join-Path $AeroBatch 'spark_jobs\export\m2_to_m5'
$AeroSnapshot = Get-ChildItem $AeroExportRoot -Directory |
    Where-Object { Test-Path (Join-Path $_.FullName 'manifest.json') } |
    Sort-Object Name -Descending |
    Select-Object -First 1

if ($null -eq $AeroSnapshot) { throw 'Chua co bo export hoan tat.' }

$AeroSnapshot.FullName
Get-ChildItem $AeroSnapshot.FullName
```

### 13.3. Kiểm tra manifest và đủ file

```powershell
$AeroManifest = Get-Content (Join-Path $AeroSnapshot.FullName 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json

if ($AeroManifest.coverage.month_count -ne 51) { throw 'Bo export chua du 51 thang.' }
if ($AeroManifest.coverage.matches_project_period_2022_01_to_2026_03 -ne $true) {
    throw 'Pham vi export khong khop 2022-01 den 2026-03.'
}
if (@($AeroManifest.tables).Count -ne 20) { throw 'Chua du 20 bang.' }
if (@($AeroManifest.tables | Where-Object group -eq 'kpi').Count -ne 13) { throw 'Chua du 13 KPI.' }
if (@($AeroManifest.tables | Where-Object group -eq 'box').Count -ne 7) { throw 'Chua du 7 box.' }

foreach ($AeroTable in $AeroManifest.tables) {
    if ($AeroTable.rows -le 0) { throw ('Bang rong: ' + $AeroTable.name) }
    foreach ($AeroFile in @($AeroTable.csv, $AeroTable.jsonl)) {
        if (-not (Test-Path (Join-Path $AeroSnapshot.FullName $AeroFile))) {
            throw ('Thieu file: ' + $AeroFile)
        }
    }
}

$AeroManifest.coverage | ConvertTo-Json -Depth 5
$AeroManifest.tables | Select-Object group, name, rows, suggested_collection | Format-Table
(Get-ChildItem $AeroSnapshot.FullName -File).Count
```

Bộ xuất mặc định có **41 file**: 20 CSV, 20 JSONL và 1 manifest. `total_flights`
lấy từ KPI tháng, cần đối chiếu với tổng output verifier; nó không phải phép
đếm CSV độc lập. `exported_at_utc` là thời gian xuất, không phải thời điểm dữ
liệu được thu thập hay lần build upstream.

### 13.4. Kiểm tra số dòng thực tế của JSONL và CSV

Đoạn PowerShell sau gửi Python vào container Spark; không cần Python Windows:

```powershell
$AeroContainerSnapshot = '/opt/spark_jobs/export/m2_to_m5/' + $AeroSnapshot.Name

@'
import csv
import json
import sys
from pathlib import Path

folder = Path(sys.argv[1])
manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
for table in manifest['tables']:
    keys_seen = set()
    count = 0
    with (folder / table['jsonl']).open(encoding='utf-8') as handle:
        for line in handle:
            row = json.loads(line)
            key = json.dumps([row[k] for k in table['keys']], sort_keys=True)
            assert key not in keys_seen, (table['name'], 'duplicate key')
            keys_seen.add(key)
            count += 1
    assert count == table['rows'], (table['name'], 'JSONL row count')
    with (folder / table['csv']).open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        expected_columns = [field['name'] for field in table['spark_schema']['fields']]
        assert reader.fieldnames == expected_columns, (table['name'], 'CSV header')
        assert sum(1 for _ in reader) == count, (table['name'], 'CSV row count')
    print('OK', table['group'], table['name'], count)
print('ALL 20 TABLES CHECKED')
'@ | docker compose exec -T -u root spark python3 - $AeroContainerSnapshot

if ($LASTEXITCODE -ne 0) { throw 'Kiem tra file export that bai.' }
```

Đây là kiểm tra tính toàn vẹn cơ bản của bộ xuất, không chứng minh mọi công
thức KPI đúng. Kết quả cuối cần là `ALL 20 TABLES CHECKED`.

## 14. Đóng gói output M2

### 14.1. Bộ bàn giao M5 tối thiểu

Gửi toàn bộ thư mục `$AeroSnapshot.FullName`, cùng tài liệu
`HUONG_DAN_BAN_GIAO_M2_M5.md`. M5 sử dụng JSONL và `manifest.json` để viết loader,
unique index, upsert và dashboard. Không cần gửi 29 triệu dòng raw để bắt đầu
phát triển các trang KPI này.

| Ví dụ file | Ý nghĩa | Khóa định danh |
|---|---|---|
| `kpi__month_overall.jsonl` | KPI theo tháng | `year, month` |
| `kpi__year_carrier.jsonl` | KPI hãng theo năm | `year, carrier` |
| `kpi__year_origin.jsonl` | KPI sân bay theo năm | `year, origin` |
| `kpi__year_route.jsonl` | KPI tuyến theo năm | `year, origin, dest` |
| `box__year_carrier.jsonl` | Phân phối delay theo hãng/năm | `year, carrier, var, population` |

Tỷ lệ lưu 0–1, hiển thị phần trăm bằng nhân 100. Null không tự đổi thành 0;
độ trễ đo bằng phút; `avg_arr_delay_net` có thể âm. `reliability_score` là điểm
tự định nghĩa của nhóm. Khi gộp nhiều nhóm, cộng đếm/tổng rồi tính lại tỷ lệ.

### 14.2. Bộ output M2 có log, notebook và evidence

Sau khi hoàn thành mục 12–13, chạy trong Terminal A:

```powershell
$AeroHandoff = Join-Path $AeroBatch ('spark_jobs\export\M2_HANDOFF_' + $AeroSnapshot.Name)
New-Item -ItemType Directory -Force $AeroHandoff | Out-Null

Copy-Item -LiteralPath $AeroSnapshot.FullName -Destination (Join-Path $AeroHandoff 'data') -Recurse
Copy-Item -LiteralPath (Join-Path $AeroBatch 'spark_jobs\evidence') -Destination (Join-Path $AeroHandoff 'evidence') -Recurse
Copy-Item -LiteralPath (Join-Path $AeroBatch 'logs') -Destination (Join-Path $AeroHandoff 'logs') -Recurse
Copy-Item -LiteralPath (Join-Path $AeroBatch 'doc_guide\HUONG_DAN_BAN_GIAO_M2_M5.md') -Destination $AeroHandoff
Copy-Item -LiteralPath (Join-Path $AeroBatch 'doc_guide\HUONG_DAN_CHAY_TU_DAU_DEN_OUTPUT_M2.md') -Destination $AeroHandoff
Copy-Item -LiteralPath (Join-Path $AeroBatch 'doc_guide\TAI_LIEU_KY_THUAT_SPARK.md') -Destination $AeroHandoff

@'
Raw HDFS: hdfs://namenode:9000/aero/raw/bts
Cleaned HDFS: hdfs://namenode:9000/aero/processed
Analytics HDFS: hdfs://namenode:9000/aero/analytics/eda
Period: 2022-01 through 2026-03 (51 months)
These HDFS names are reachable inside the local Compose network.
For transfer to another machine, copy the data or rebuild the pipeline there.
'@ | Set-Content -Encoding UTF8 (Join-Path $AeroHandoff 'HDFS_OUTPUT_PATHS.txt')

Compress-Archive -Path (Join-Path $AeroHandoff '*') -DestinationPath ($AeroHandoff + '.zip')
$AeroHandoff
```

Chạy đoạn đóng gói một lần cho snapshot đó; nếu chạy lại cùng snapshot và thư
mục đích đã tồn tại, chọn tên thư mục mới để tránh trộn file. Kiểm tra notebook
đã lưu và evidence thuộc đúng lần chạy đang báo cáo.

Các log `06`/`08`/`09` trong hướng dẫn dùng tên cố định và sẽ được ghi lại ở lần
chạy sau; copy/đóng gói log trước khi rerun nếu cần giữ bằng chứng lần trước.

### 14.3. Tùy chọn: lấy cả Parquet sạch về Windows

Parquet sạch vẫn là một đầu ra M2 nằm trên HDFS. Nếu người nhận dùng cùng HDFS,
bàn giao đường dẫn và schema là đủ để truy cập. Nếu cần bản vật lý trên máy
khác hoặc bản sao lưu, có thể xuất thêm. Bước này cần thêm dung lượng ở Docker
và Windows; không bắt buộc cho loader KPI của M5.

```powershell
$AeroCopyTag = Get-Date -Format 'yyyyMMdd_HHmmss'
$AeroTempHdfsCopy = '/tmp/aero_m2_' + $AeroCopyTag

docker compose exec -u root namenode mkdir -p $AeroTempHdfsCopy
docker compose exec -u root namenode hdfs dfs -get /aero/processed ($AeroTempHdfsCopy + '/processed')
if ($LASTEXITCODE -ne 0) { throw 'Lay Parquet tu HDFS that bai.' }

docker compose cp ('namenode:' + $AeroTempHdfsCopy + '/processed') ('.\spark_jobs\export\cleaned_parquet_' + $AeroCopyTag)
if ($LASTEXITCODE -ne 0) { throw 'Copy Parquet ve Windows that bai.' }
```

Thư mục Windows này chứa Parquet và cấu trúc phân vùng, tách khỏi bộ 41 file KPI.
Đường dẫn `hdfs://namenode:9000` là tên mạng trong Compose; gửi chuỗi đường dẫn
đó cho máy khác chưa có cùng hệ thống không làm dữ liệu tự xuất hiện ở máy đó.

## 15. Dừng và tiếp tục lần sau

Sau khi đã `spark.stop()`/tắt kernel, tắt server Jupyter bằng `Ctrl+C`, rồi:

```powershell
Set-Location $AeroBatch
docker compose stop
```

Mở lại lần sau:

```powershell
Set-Location F:\Project-BigData-Storage-and-Processing\batch-layer
docker compose start
docker compose ps
docker compose exec namenode hdfs dfsadmin -report
docker compose exec namenode hdfs dfs -ls /aero/analytics/eda/kpi
```

Nếu containers đã bị xóa nhưng volumes còn, dùng `docker compose up -d`.
Khi dữ liệu còn nguyên và verifier đạt, không cần tải CSV/nạp raw/chạy lại ETL
chỉ để xuất KPI. Dùng exporter đọc lại kết quả đã có.

Không dùng `docker compose down -v` để dừng thông thường: `-v` có thể xóa các
volume HDFS. Dữ liệu Windows `BTS_ZIP` và file export là bind mount, khác với
volume HDFS.

## 16. Lỗi thường gặp và bước cần quay lại

| Hiện tượng | Cách kiểm tra / xử lý |
|---|---|
| `no configuration file provided` | Chuyển về `batch-layer`, nơi có Compose |
| Không kết nối được Docker Server | Mở Docker Desktop, chờ engine; kiểm tra `docker version` |
| Container không thấy CSV | Kiểm tra `batch-layer\BTS_ZIP` và mount `/data/input` |
| ETL báo thiếu file `2022_1.csv` | Kiểm tra đúng tên file và đã `hdfs dfs -put`; xem mục 4 và 6 |
| `bash: hdfs: command not found` khi nạp raw | Dùng `bash -c` thay cho `bash -lc` như mục 6.2 để giữ `PATH` của container |
| `File exists` khi nạp raw | Kiểm tra HDFS đang có gì; dùng nhánh bổ sung file thiếu, không tự ghi đè |
| HDFS còn safe mode / 0 live DataNode | Xem `docker compose logs --tail 100 namenode datanode` và `dfsadmin -report` |
| `Permission denied` trên HDFS | Dùng cùng user `-u root` trong môi trường local hướng dẫn; kiểm tra owner và đường dẫn |
| `No module named pip` | Chạy lệnh apt ở mục 9 rồi cài lại thư viện |
| PySpark/Spark khác phiên bản | Cài `pyspark==3.5.3` trong container, restart kernel |
| `/opt/spark` là False trong notebook | Đang dùng kernel Windows; chọn Jupyter server container |
| Không mở được cổng 8888 | Kiểm tra `docker compose ps`, cổng trong Compose và server Jupyter đã chạy |
| Container Spark bị tạo lại, mất Jupyter | Cài lại mục 9; lấy URL/token mới khi mở server |
| Thiếu pandas/pyarrow, trimmed mean bị bỏ qua | Cài đúng môi trường container, restart kernel và chạy lại phần cần thiết |
| Verifier báo FAIL | Xử lý lỗi phân vùng/ngày trước khi chạy EDA; xem log `08` |
| EDA thông báo thiếu tháng | Đối chiếu `/aero/processed`; chạy ETL/verify cho dữ liệu thiếu |
| Có `COLUMN_ALREADY_EXISTS` với month/year | CSV/Parquet có cột nguồn trùng tên phân vùng theo cách Spark so tên; kiểm tra schema và verifier, không bỏ qua nếu job thực sự lỗi |
| Đã có histogram nhưng KPI nghi thiếu/sai sau lỗi | Resume chỉ dựa vào thư mục; dựng lại tháng bị ảnh hưởng với `FORCE_REBUILD=True` |
| `Missing .../kpi/...` khi export | Chạy EDA build, không chỉ chạy ETL `06` |
| Export báo duplicate key / empty table | Kiểm tra bảng M2 và schema; không bỏ kiểm tra để lấy file |
| Export vượt `--max-rows=200000` | Kiểm tra đang đọc bảng tổng hợp đúng; chỉ tăng giới hạn nếu quy mô mới đã được xác minh |
| Export thành công nhưng chỉ 3 tháng | Build đủ 51 tháng và xuất snapshot mới; xem coverage trong manifest |
| Chậm, hết RAM, container bị kill | Tắt kernel/job Spark khác, kiểm tra tài nguyên Docker; chạy tuần tự |

## 17. Checklist nhận output đầy đủ M2

- [ ] Có đủ 51 CSV đúng tên cho 2022-01 đến 2026-03, không có tháng download lỗi.
- [ ] HDFS raw chứa các file dự kiến; có thể truy cập bằng Spark.
- [ ] ETL báo 51 thành công, 0 thất bại; đã giữ input/output/removed counts.
- [ ] Verifier báo `PASS`, 51 tháng có dòng, không lỗi ngày/phân vùng.
- [ ] EDA build đủ kỳ, có 13 KPI và 7 box theo notebook lite.
- [ ] Có output các phân tích cell 8 và bản notebook đã thực thi.
- [ ] Cell 9 có UDF đối chiếu 0 lệch, trimmed mean và 5 nhóm evidence.
- [ ] Đã lưu plans, summary, cấu hình và giới hạn của phép đo hiệu năng.
- [ ] Exporter báo hoàn tất; manifest khớp đủ 51 tháng và có 20 bảng.
- [ ] Đã kiểm tra 20 CSV + 20 JSONL, header, số dòng và khóa.
- [ ] Đã đối chiếu tổng flights của bộ xuất với tổng output verifier.
- [ ] Đã đóng gói dữ liệu, manifest, notebook, evidence, logs và tài liệu.
- [ ] M5 biết khóa từng bảng, schema thực tế, đơn vị đo, công thức và phạm vi.

Checklist trên xác định output của code hiện tại. Theo PDF, nghiệm thu M2 còn
cần giải thích số dòng sau cleaning và kiểm thử các biến đổi quan trọng. Giữ
các giới hạn kiểm tra đã nêu; không coi đủ 41 file hay `PASS` của verifier là
bằng chứng đầy đủ cho mọi yêu cầu chất lượng dữ liệu.

## 18. Các tài liệu liên quan

- [Bàn giao M2 → M5](HUONG_DAN_BAN_GIAO_M2_M5.md): hợp đồng file, MongoDB keys và quy tắc KPI.
- [Hướng dẫn EDA lite](HUONG_DAN_CHAY_EDA_LITE.md): bảng kết quả và cách sử dụng.
- [Tài liệu kỹ thuật Spark](TAI_LIEU_KY_THUAT_SPARK.md): các kỹ thuật và giới hạn.
- [Data inventory](data_inventory_vi.md): nguồn, phạm vi và kết quả đã ghi nhận.
- [Data dictionary](data_dictionary_vi.md): các trường nguồn và phần cần hoàn thiện schema.
- [PDF kế hoạch 5 thành viên](../../Big_Data_Project_Plan_5_Members.pdf): trang 4 về M2, trang 7 về M5, trang 8 về hợp đồng bàn giao.

Tài liệu đã được đối chiếu với code và cấu hình. Việc chạy lại toàn bộ dữ liệu
phụ thuộc Docker/HDFS trên máy thực thi; các con số tham chiếu trong tài liệu
không thay thế kết quả của lần chạy hiện tại.
