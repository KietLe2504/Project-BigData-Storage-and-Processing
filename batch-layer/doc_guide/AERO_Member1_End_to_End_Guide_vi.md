# AERO Batch Layer — Hướng dẫn toàn trình cho Thành viên 1

> **Mục đích:** Hướng dẫn quy trình làm việc của Phase 1: Chuẩn bị dữ liệu BTS theo tháng, Khởi động Docker/HDFS, chạy ETL batch Spark, Xác minh các phân vùng đã xử lý, và bàn giao kết quả cho bước tiếp theo.
>
> **Môi trường:** Windows + PowerShell + Docker Desktop + VS Code
> 
> **Thư mục dự án:** `G:\Downloads_2\Batch_Layer` ( Ở đây do máy local thành viên 1 có thư mục gốc là như vậy, mọi người lên github thì git clone về máy của mình.
>
> **Link Dataset** https://www.kaggle.com/datasets/anhdnghng/us-bts-2026
>
> **Hướng dẫn tải** Vào output trên đường dẫn Kaggle, tải file dataset về local rồi giải nén ra
> 
> **Phạm vi dữ liệu:** Tháng 1/2022 đến tháng 3/2026 (51 tháng)

**Quan trọng:** Các lệnh và đường dẫn phản ánh cấu hình dự án hiện tại được thảo luận trong quá trình triển khai. Hãy kiểm tra `docker-compose.yml` và các script thực tế trước khi thay đổi tên service, đường dẫn mount hoặc hành vi ghi đè.

---
------------------------------------------------------------------------

## Bắt đầu nhanh: người mới clone repository lần đầu

Thực hiện các bước theo thứ tự này trên Windows PowerShell. Ví dụ dưới
đây dùng thư mục `G:\Downloads_2\Batch_Layer`; nếu bạn clone ở nơi khác,
hãy đổi đường dẫn tương ứng.

### A. Clone đúng repository và nhánh

``` powershell
Set-Location G:\Downloads_2\Batch_Layer
git clone -b feature/aero-batch-layer https://github.com/KietLe2504/Project-BigData-Storage-and-Processing.git
Set-Location .\Project-BigData-Storage-and-Processing\batch-layer
```

Nếu repository đã được clone trước đó, không clone lặp lại; hãy
`Set-Location` vào thư mục `batch-layer` hiện có.


## 1. Phạm vi và kết quả đã ghi nhận

Ở Phase 1:

1. Thu thập dataset BTS On-Time Reporting.
2. Chuẩn bị môi trường HDFS cục bộ bằng Docker Compose.
3. Đưa các CSV nguồn trong folder BTS_ZIP theo tháng vào tầng lưu trữ raw của HDFS.
4. Chạy pipeline batch Spark để tạo đầu ra Parquet theo tháng.
5. Xác minh các phân vùng đã xử lý theo tháng.
6. Ghi tài liệu kiểm kê dữ liệu, từ điển dữ liệu, lệnh chạy và ghi chú bàn giao.

Lần chạy xác minh đầy đủ đã được ghi nhận báo cáo:

| Kiểm tra | Kết quả |
|---|---:|
| Số tháng dự kiến | 51 |
| Số tháng có dòng dữ liệu | 51 |
| Tổng số dòng đã xử lý | 29,328,846 |
| Ngày không hợp lệ/null mà verifier phát hiện | 0 |
| Số trường hợp lệch ngày/phân vùng mà verifier phát hiện | 0 |
| Số tháng thiếu kết quả | 0 |
| Kết quả xác minh | `PASS` |

Điều này xác minh các kiểm tra được cài đặt trong `08_verify_partition.py`. Nó **không** tự chứng minh được việc đối soát chính xác số dòng giữa nguồn và đầu ra, việc không còn bất kỳ bản trùng lặp nào, hay việc bảo toàn từng byte của mọi trường nguồn.

---

## 2. Cấu trúc dự án lẫn quy trình trước khi bắt đầu
### Yêu cầu trước khi bắt đầu
- Windows 10/11, PowerShell.
- Docker Desktop đã cài và đang chạy (kiểm tra biểu tượng cá voi ở khay hệ thống).
- Đủ RAM và dung lượng ổ đĩa: CSV nguồn khoảng 5,3 GB, cộng với dữ liệu HDFS và Parquet sinh ra. Nên dành thêm dung lượng trống đáng kể so với 5,3 GB.
- VS Code (tùy chọn, để sửa file).
- Git (chỉ cần cho mục 14).

Kiểm tra Docker:

```
docker version
docker compose version
```

Nếu một trong hai lệnh báo lỗi, hãy mở Docker Desktop và chờ nó hoàn tất khởi động rồi thử lại.

Ví dụ ở Local của máy cá nhân là đường dẫn `G:\Downloads_2\Batch_Layer` (tùy vào mỗi người mà có local khác nhau). Sau khi giải nén dataset ta có folder `BTS_ZIP`, ta đưa toàn bộ folder trên vào trong đường dân 'G:\Downloads_2\Batch_Layer\Project-BigData-Storage-and-Processing\'. Dự án đang hoạt động hiện có dạng:

``` text
Project-BigData-Storage-and-Processing\
├── BTS_ZIP\                     # Các file CSV nguồn theo tháng đã giải nén
│   ├── manifest.json       
│   ├── On_Time_Reporting_2022_1.csv   # Hệ thống file csv sau khi được giải nén ra         
│   ├── On_Time_Reporting_2022_2.csv
│   ├── On_Time_Reporting_2022_3.csv
│   ├── On_Time_Reporting_2022_4.csv
│   ├── ...
│   └── On_Time_Reporting_2026_3.csv
├── spark_jobs\
│   ├── 02_inspect_bts.py        # Tiện ích kiểm tra một file ban đầu  (Kiểm tra 1 tháng demo - Optional )
│   ├── 03_clean_bts.py          # Bản mẫu làm sạch một tháng ở giai đoạn đầu (Optional)
│   ├── 04_validate_parquet.py   # Kiểm tra một phân vùng ở giai đoạn đầu (Optional)
│   ├── 05_quality_check.py      # Các kiểm tra tùy chọn cho một phân vùng (Optional)
│   ├── 06_batch_process_all.py  # ETL Spark chính cho 51 tháng   (Quan trọng, chạy chính: Xử lý tất ca các tháng)
│   ├── 07_retry_2022_01.py      # Script khôi phục cho tháng 1/2022 ( Trong trường hợp máy cá nhân bị lỗi ở tải tháng đầu - Optional)
│   └── 08_verify_partition.py   # Xác minh toàn bộ khoảng thời gian (Quan trọng, chạy chính: Kiểm tra xác minh kết quả)
├── check_partitions.ps1         # Script PowerShell kiểm tra phân vùng (tùy chọn)
├── docker-compose.yml
└── docs\
    ├── data_inventory.md
    └── data_dictionary.md
```

File Compose có thể mount `spark_jobs` vào container Spark tại `/opt/spark_jobs`. Hãy xác nhận ánh xạ này trong `docker-compose.yml`; các lệnh bên dưới giả định nó tồn tại.

### Các script tối thiểu, bắt buộc phải chạy trong repository công khai

- `06_batch_process_all.py` — ETL chính.
- `08_verify_partition.py` — xác minh toàn bộ khoảng thời gian.

Các script ban đầu `02_inspect_bts.py`, `03_clean_bts.py` và `04_validate_parquet.py` là các tiện ích phát triển hoặc ví dụ đã bị thay thế. `05_quality_check.py`, `07_retry_2022_01.py` — script khôi phục tùy là tùy chọn. Đừng xóa bản gốc cho đến khi phiên bản đơn giản hóa đã được kiểm thử riêng.

---

## 3. Nguồn dữ liệu và chuẩn bị cục bộ

- **Nguồn:** Cục Thống kê Vận tải Hoa Kỳ (BTS), On-Time Reporting / Carrier On-Time Performance.
- **Phạm vi:** `2022-01` đến `2026-03`, bao gồm cả hai đầu.
- **Số file:** 51 CSV theo tháng.
- **Dung lượng:** 5,2 GB.
- **Thư mục cục bộ sau khi giải nén và đưa vào cấu trúc thư mục file project:** `G:\Downloads_2\Batch_Layer\BTS_ZIP\`

Tên thư mục có chữ `ZIP`, nhưng các file thực tế là CSV đã giải nén.

### Kiểm tra các file cục bộ trong PowerShell

``` powershell
Set-Location "G:\Downloads_2\Batch_Layer\Project-BigData-Storage-and-Processing\batch-layer"  # đổi theo đường dẫn clone của bạn

Get-ChildItem .\BTS_ZIP -Filter *.csv |
    Sort-Object Name |
    Select-Object Name, Length

(Get-ChildItem .\BTS_ZIP -Filter *.csv).Count
```

Số lượng kỳ vọng: `51`, giả sử không có file CSV thừa.
---

## 4. Khởi động và kiểm tra các service Docker
Sau khi kiếm tra số file đầy đủ xong, mở Docker Desktop và chờ đến khi nó vào trang chủ (kiểm tra biểu tượng cá voi ở khay hệ thống), chú ý luôn luôn phải để Docker Desktop chạy trong quá trình running code, tránh để Docker tắt gây ảnh hưởng quá trình spark hay các bước khác thực hiện

Chạy từ thư mục dự án:

``` powershell
Set-Location "G:\Downloads_2\Batch_Layer\Project-BigData-Storage-and-Processing\batch-layer"  # đổi theo đường dẫn clone của bạn
docker compose config
docker compose up -d
docker compose ps
```

-   `docker compose config` xác thực và hiển thị cấu hình Compose.
-   `docker compose up -d` khởi động các service ở chế độ nền.
-   `docker compose ps` hiển thị trạng thái các service.

Output mong đợi: các service namenode, datanode, spark ở trạng thái
running (hoặc Up).

Thiết lập này gồm các service/container như `namenode` /
`aero-namenode`, `datanode` / `aero-datanode` và một service Spark.
**Tên service trong Compose** là tên mà `docker compose exec` sử dụng.
Kiểm tra bằng:

``` powershell
docker compose config --services
```

Nếu trường hợp container chạy chưa ổn định, xem log:

``` powershell
docker compose logs --tail 100 namenode
docker compose logs --tail 100 datanode
docker compose ps
```

Nếu service Spark có tên `spark`:

``` powershell
docker compose logs --tail 100 spark
```

------------------------------------------------------------------------

## 5. Xác nhận các file nguồn hiển thị trong container

Thiết lập trước đây đã mount `BTS_ZIP` cục bộ vào container NameNode tại
`/data/input`. Hãy xác nhận đường dẫn này trong cấu hình Compose hiện
tại:

``` powershell
docker compose exec namenode bash -lc "ls -lh /data/input | head"
docker compose exec namenode bash -lc "find /data/input -maxdepth 1 -type f -name '*.csv' | wc -l"
```

Số lượng kỳ vọng: `51`.

Nếu `/data/input` không tồn tại, hãy kiểm tra mục `volumes:` của
`docker-compose.yml` và dùng đường dẫn container đã cấu hình. Đừng thay
đổi đường dẫn trong script cho đến khi việc mount đã được xác nhận.

------------------------------------------------------------------------

## 6. Tạo thư mục HDFS, nạp dữ liệu nguồn và kiểm tra

### Mẫu đường dẫn raw kỳ vọng

Script ETL đã dùng mẫu đầu vào sau:

``` text
/aero/raw/bts/On_Time_Reporting_{year}_{month}.csv
```

Ví dụ:

``` text
/aero/raw/bts/On_Time_Reporting_2022_1.csv
/aero/raw/bts/On_Time_Reporting_2026_3.csv
```

Hãy khớp đúng định dạng tháng mà script hiện tại và các file nguồn đang
dùng.

### Mẫu đường dẫn processed

``` text
/aero/processed/year=YYYY/month=MM/
```

Ví dụ:

``` text
/aero/processed/year=2022/month=01/
/aero/processed/year=2026/month=03/
```

Các thư mục tháng nên chứa các file part Parquet và thường có
`_SUCCESS`.

### Bước 6.1 — Tạo các thư mục HDFS trước khi nạp dữ liệu

Đây là các thư mục trong **HDFS**, không phải thư mục trên Windows hay
đường dẫn bên trong container. Chạy các lệnh sau từ PowerShell tại thư
mục có `docker-compose.yml`:

``` powershell
docker compose exec namenode hdfs dfs -mkdir -p /aero/raw/bts
docker compose exec namenode hdfs dfs -mkdir -p /aero/processed
docker compose exec namenode hdfs dfs -mkdir -p /aero/analytics
```

`-mkdir -p` tạo thư mục nếu chưa tồn tại và không báo lỗi chỉ vì thư mục
đã có sẵn. Các thư mục partition như `year=2022/month=01` sẽ được Spark
tạo trong quá trình ghi kết quả, nên không cần tạo thủ công từng tháng.

### Bước 6.2 — Nạp CSV nguồn vào HDFS

Trước tiên, xác nhận container nhìn thấy dữ liệu nguồn ở
`/data/input/BTS_ZIP/` như đã kiểm tra tại mục 5. Sau đó chạy:

``` powershell
docker compose exec namenode sh -lc 'hdfs dfs -put -f /data/input/BTS_ZIP/*.csv /aero/raw/bts/'
```

Lệnh `-put -f` sao chép CSV từ filesystem của container vào HDFS và ghi
đè file cùng tên nếu đã tồn tại. Chỉ chạy lại khi bạn chủ động muốn đồng
bộ lại dữ liệu nguồn.

### Bước 6.3 — Kiểm tra dữ liệu đã nằm trong HDFS

``` powershell
docker compose exec namenode hdfs dfs -ls /
docker compose exec namenode hdfs dfs -ls /aero
docker compose exec namenode hdfs dfs -count /aero/raw/bts
docker compose exec namenode hdfs dfs -ls /aero/raw/bts
docker compose exec namenode hdfs dfs -ls /aero/processed
```

Kỳ vọng có 51 file CSV trong `/aero/raw/bts`. Đối chiếu tên file với
mẫu mà `06_batch_process_all.py` đọc:
`On_Time_Reporting_{year}_{month}.csv`. Chỉ chuyển sang chạy ETL khi
đã xác nhận các file nguồn thực sự có trong HDFS.

Kiểm tra xem tháng 1/2022 có file đánh dấu thành công hay không:

``` powershell
docker compose exec namenode hdfs dfs -test -e /aero/processed/year=2022/month=01/_SUCCESS
if ($LASTEXITCODE -eq 0) {
    "2022-01 _SUCCESS exists"
} else {
    "2022-01 _SUCCESS is missing"
}
```

`_SUCCESS` là bằng chứng hữu ích rằng Spark đã đánh dấu một job ghi là
thành công, nhưng nó không phải là một kiểm tra chất lượng dữ liệu hoàn
chỉnh. Hãy chạy cả verifier.

### Lưu ý về tầng raw

Việc mount cục bộ tại `/data/input` tự nó không chứng minh rằng mọi file nguồn đã được sao chép vào HDFS. Hãy hoàn tất các bước 6.1–6.3 và xác nhận có 51 file CSV trong `/aero/raw/bts/` trước khi chạy ETL.

------------------------------------------------------------------------

## 7. Chạy ETL batch đầy đủ

### Script chính

`spark_jobs/06_batch_process_all.py`

Pipeline hiện tại duyệt qua các tháng dự kiến, đọc từng CSV theo tháng từ tầng raw trên HDFS, kiểm tra các cột bắt buộc như `FL_DATE`, `ORIGIN` và `DEST`, thực hiện làm sạch cơ bản, loại bỏ trùng lặp bằng các trường khóa sẵn có, và ghi đầu ra Parquet theo tháng.

Khóa loại trùng chính xác và chế độ ghi được định nghĩa trong script. Hãy xem lại chúng trước khi chạy lại vì job có thể ghi đè đầu ra theo tháng đã có.

### Gửi job bằng Spark

``` powershell
Set-Location "G:\Downloads_2\Batch_Layer\Project-BigData-Storage-and-Processing\batch-layer"  # đổi theo đường dẫn clone của bạn

docker compose exec spark /opt/spark/bin/spark-submit `
  --master 'local[*]' `
  --conf spark.hadoop.fs.defaultFS=hdfs://namenode:9000 `
  /opt/spark_jobs/06_batch_process_all.py
```

Lệnh này giả định service Compose có tên `spark` và các script được
mount tại `/opt/spark_jobs`. Chỉ điều chỉnh nếu cấu hình Compose thực tế
khác.

### Lời khuyên vận hành

-   Chỉ chạy ETL khi chủ ý xử lý hoặc dựng lại đầu ra.
-   Nếu thất bại, hãy lưu lại exception có ý nghĩa đầu tiên và các log
    container liên quan trước khi thử lại.
-   Việc một thư mục tồn tại không chứng minh đầu ra của nó hợp lệ.
-   Dự án trước đây từng gặp lỗi ghi HDFS/DataNode đối với `2022-01`;
    phân vùng đó sau đó đã tồn tại và vượt qua verifier đã cài đặt. Đừng
    chạy script khôi phục trừ khi bước xác minh hoặc log cho thấy có vấn
    đề thực sự.

------------------------------------------------------------------------

## 8. Xác minh tất cả các phân vùng đã xử lý

### Script xác minh

`spark_jobs/08_verify_partition.py`

Verifier hiện tại kiểm tra độ phủ các tháng dự kiến, đọc dữ liệu Parquet
đã xử lý, nhóm theo năm/tháng của phân vùng, và báo cáo số dòng theo
tháng, ngày không hợp lệ/null, sự lệch phân vùng và khoảng ngày.

Chạy bằng:

``` powershell
Set-Location "G:\Downloads_2\Batch_Layer\Project-BigData-Storage-and-Processing\batch-layer"  # đổi theo đường dẫn clone của bạn

docker compose exec spark /opt/spark/bin/spark-submit `
  --master 'local[*]' `
  --conf spark.hadoop.fs.defaultFS=hdfs://namenode:9000 `
  /opt/spark_jobs/08_verify_partition.py
```

Tóm tắt thành công đã ghi nhận:

``` text
Expected months: 51
Months with rows: 51
Total rows: 29,328,846
Invalid/null dates: 0
Date/partition mismatches: 0
Missing result months: []
RESULT: PASS
```

Đây là kết quả của lần chạy đã ghi nhận, không phải giá trị được đảm bảo
cho mọi lần chạy trong tương lai. Hãy chạy lại bước xác minh sau khi
thay đổi mã hoặc dữ liệu.

### Kiểm tra nhanh sự tồn tại của 51 marker `_SUCCESS` (PowerShell)

Đây là kiểm tra nhẹ, không đọc/đếm toàn bộ dữ liệu Parquet. Đặt nội dung
sau vào `check_partitions.ps1` trong thư mục `batch-layer`, hoặc chạy
trực tiếp trong PowerShell:

``` powershell
$ok = 0
$fail = 0
$missing = @()

for ($year = 2022; $year -le 2026; $year++) {
    $endMonth = if ($year -eq 2026) { 3 } else { 12 }

    for ($month = 1; $month -le $endMonth; $month++) {
        $mm = "{0:D2}" -f $month
        $path = "/aero/processed/year=$year/month=$mm"

        docker compose exec -T namenode hdfs dfs -test -e "$path/_SUCCESS" 2>$null

        if ($LASTEXITCODE -eq 0) {
            $ok++
        } else {
            $fail++
            $missing += "$year-$mm"
        }
    }
}

Write-Host "SUCCESS=$ok FAILED=$fail TOTAL=$($ok + $fail)"
if ($missing.Count -gt 0) {
    Write-Host "Missing partitions: $($missing -join ', ')"
}
```

Kết quả kỳ vọng: `SUCCESS=51 FAILED=0 TOTAL=51`. Chỉ kết luận 51 marker
tồn tại khi script đúng logic `if/else` này cho ra kết quả như trên.
Kiểm tra `_SUCCESS` là kiểm tra sự tồn tại marker, không thay thế
`08_verify_partition.py`.

------------------------------------------------------------------------

### `PASS` có nghĩa là gì

Các kiểm tra do verifier cài đặt đã đạt. Nó không tự chứng minh được
việc đối soát chính xác số dòng đầu vào--đầu ra, việc không còn bản
trùng lặp nào, việc 38 cột có kiểu giống hệt nhau trên mọi tháng, hay
việc bằng nhau từng byte với các file nguồn đã tải.

------------------------------------------------------------------------

## 9. Các script tùy chọn và khôi phục

  ---------------------------------------------------------------------------
  Script                      Vai trò                 Giữ trong đường chạy
                                                      tối thiểu?
  --------------------------- ----------------------- -----------------------
  `02_inspect_bts.py`         Kiểm tra một CSV nguồn, Không; tiện ích phát
                              các cột, schema, dữ     triển
                              liệu mẫu                

  `03_clean_bts.py`           Bản mẫu làm sạch một    Không; đã được ETL
                              tháng ở giai đoạn đầu   chính thay thế

  `04_validate_parquet.py`    Kiểm tra một phân vùng  Không; đã được thay thế
                              ở giai đoạn đầu         cho các kiểm tra thường
                                                      lệ

  `05_quality_check.py`       Các kiểm tra chất lượng Tùy chọn
                              bổ sung cho một phân    
                              vùng                    

  `06_batch_process_all.py`   ETL Spark chính cho 51  **Có**
                              tháng                   

  `07_retry_2022_01.py`       Khôi phục cho tháng     Tùy chọn, giữ riêng
                              1/2022                  

  `08_verify_partition.py`    Xác minh đầu ra toàn bộ **Có**
                              khoảng thời gian        
  ---------------------------------------------------------------------------
---
## 10. Kiểm kê dữ liệu và Từ điển dữ liệu

Giữ các tài liệu bàn giao này trong `docs/`:

``` text
docs/
├── data_inventory.md
└── data_dictionary.md
```

`data_inventory.md` nên ghi lại nguồn, khoảng thời gian, số file dự
kiến, dung lượng cục bộ xấp xỉ, các đường dẫn HDFS, script, kết quả xác
minh và giới hạn của các kiểm tra.

`data_dictionary.md` nên ghi lại tên trường chính xác, kiểu dữ liệu
Spark thực tế, ý nghĩa bằng ngôn ngữ thông thường, đơn vị/ví dụ và ghi
chú về giá trị thiếu.

Đừng trình bày một danh sách đoán mò như từ điển chính thức cho cả 38
cột. Hãy trích xuất schema thực tế và xác nhận tính nhất quán giữa các
phân vùng theo tháng.

Giữ file Compose và mọi file cấu hình mà nó tham chiếu. Nếu Compose mount toàn bộ thư mục `spark_jobs/`, hãy giữ nguyên tên thư mục đó hoặc cập nhật đồng thời việc mount và các lệnh.

`.gitignore` đề xuất:

```gitignore
# Large source and generated data
BTS_ZIP/
data/
raw/
processed/
*.csv
*.parquet
*.zip

# Logs and temporary files
logs/
*.log
tmp/
_temp/

# Python
__pycache__/
*.py[cod]
.venv/
venv/

# Local secrets and editor settings
.env
.env.*
.vscode/
```

Hãy xem lại `.gitignore` trước khi commit. Đừng ignore mã nguồn, file Compose/cấu hình hoặc tài liệu cần thiết. Tuyệt đối không commit mật khẩu, access token hoặc API key.

Trước khi công khai, hãy xác nhận rằng Compose chỉ tham chiếu các file có trong repository, các đường dẫn mount khớp với README, và không có CSV raw/đầu ra Parquet hay nội dung Docker volume nào bị đưa vào.

---

## 12. Các lệnh GitHub: đẩy dự án lên và tiếp nối

### 12.1. Đẩy dự án lên GitHub lần đầu (Thành viên 1)

Tạo trước một repository rỗng trên GitHub (không tick "Add README" để tránh xung đột), sau đó chạy từ thư mục dự án:

```powershell
Set-Location G:\Downloads_2\Batch_Layer

# Khởi tạo repo cục bộ
git init
git branch -M main

# Tạo .gitignore trước khi add (xem mục 11)
# Kiểm tra các thư mục dữ liệu lớn đã bị ignore chưa
git check-ignore -v BTS_ZIP
```

Cấu hình danh tính nếu máy chưa có (chỉ làm một lần):

```powershell
git config --global user.name "Ten cua ban"
git config --global user.email "email@example.com"
```

Thêm file và kiểm tra **trước khi** commit:

```powershell
git add .
git status

# Đảm bảo KHÔNG có CSV/Parquet/zip/.env nào được theo dõi
git ls-files | Select-String -Pattern "\.csv$|\.parquet$|\.zip$|\.env"
```

Nếu lệnh `Select-String` in ra bất kỳ dòng nào, dừng lại: gỡ file đó khỏi staging bằng `git rm --cached <file>` và bổ sung vào `.gitignore` trước khi commit.

Commit và đẩy lên:

```powershell
git commit -m "Add AERO batch layer: ETL, verifier, docker compose, docs"
git remote add origin https://github.com/<tai-khoan>/AERO-Batch-Layer.git
git push -u origin main
```

Kiểm tra lại bằng:

```powershell
git remote -v
git log --oneline
```

> Nếu lỡ commit nhầm file lớn hoặc file chứa mật khẩu/token, **đừng chỉ xóa file ở commit sau**: nội dung vẫn nằm trong lịch sử Git. Hãy xử lý trước khi `push`, và nếu đã push thì phải đổi (revoke) mọi token/mật khẩu đã lộ.


## 11. Bàn giao cho Thành viên 2

Script batch hiện tại đã thực hiện làm sạch cơ bản và loại bỏ trùng lặp trước khi ghi Parquet. Hãy cho Thành viên 2 biết:

- những quy tắc làm sạch nào được áp dụng;
- script hiện tại thực sự dùng khóa loại trùng nào;
- các phân vùng đã xử lý được lưu ở đâu;
- những kiểm tra xác minh nào đã đạt và chúng không chứng minh được điều gì.

Khi đó Thành viên 2 có thể triển khai các phân tích downstream, các phép biến đổi thêm và các thử nghiệm hiệu năng đã thống nhất mà không vô tình lặp lại ETL hiện có.

---

## 12. Danh sách kiểm tra cuối cùng

- [ ] Có đủ 51 CSV theo tháng ở máy cục bộ từ `2022-01` đến `2026-03`.
- [ ] Cấu hình Docker Compose hợp lệ.
- [ ] Các service NameNode, DataNode và Spark đang chạy.
- [ ] Tất cả file nguồn dự kiến đã có trong tầng raw của HDFS.
- [ ] `06_batch_process_all.py` hoàn tất mà không còn lỗi tháng nào chưa giải quyết.
- [ ] `08_verify_partition.py` hoàn tất với `RESULT: PASS`.
- [ ] Bản tóm tắt xác minh đã được ghi vào `docs/data_inventory.md`.
- [ ] `docs/data_dictionary.md` khớp với schema và kiểu dữ liệu thực tế.
- [ ] GitHub chứa mã/cấu hình/tài liệu, không chứa dữ liệu raw hay Parquet được sinh ra.
- [ ] Đã chạy `git ls-files` và xác nhận không có CSV/Parquet/zip/`.env` nào được theo dõi trước khi `push`.
- [ ] Repository đã được `push` lên `main` và `git clone` thử sang thư mục khác thành công.
- [ ] Người tiếp theo biết cần tự đặt CSV vào `BTS_ZIP\` (trường hợp máy mới) và làm theo mục 12.2.
- [ ] Thành viên 2 biết những bước làm sạch và loại trùng nào đã diễn ra trong ETL.

**Việc bàn giao của Thành viên 1 sẵn sàng khi dữ liệu có thể truy cập, các kiểm tra đã ghi nhận đạt, và một thành viên khác trong nhóm có thể hiểu cách bố trí lưu trữ và chạy lại quy trình đã được ghi tài liệu.**
