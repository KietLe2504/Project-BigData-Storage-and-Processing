# AERO — Kiểm kê dữ liệu (Data Inventory)

## 1. Mục đích

Tài liệu này kiểm kê dữ liệu chuyến bay BTS được sử dụng bởi pipeline batch của AERO. Tài liệu ghi lại nguồn, phạm vi thời gian, cách bố trí lưu trữ, đầu ra xử lý và kết quả kiểm tra, để các thành viên khác trong dự án có thể tìm và tái sử dụng dữ liệu.

## 2. Tổng quan tập dữ liệu

| Thuộc tính | Chi tiết |
|---|---|
| Dự án | AERO — Air Traffic Exploration & Real-time Orchestration |
| Tập dữ liệu | BTS On-Time Reporting — Carrier On-Time Performance |
| Tổ chức nguồn | Cục Thống kê Vận tải Hoa Kỳ (BTS) |
| Định dạng nguồn | Các file CSV theo tháng |
| Phạm vi thời gian | Tháng 1/2022 – Tháng 3/2026 (bao gồm cả hai đầu) |
| Số file theo tháng dự kiến | 51 |
| Dung lượng CSV đã giải nén trên máy cục bộ (xấp xỉ) | 5,2–5,3 GB |
| Framework xử lý | Apache Spark |
| Lưu trữ phân tán | HDFS, triển khai bằng Docker Compose |
| Định dạng đầu ra đã xử lý | Parquet |
| Phân vùng đầu ra | `year=YYYY/month=MM` |
| Tổng số dòng đã xử lý theo báo cáo xác minh | 29,328,846 |
| Trạng thái xác minh | PASS đối với các kiểm tra được cài đặt trong `08_verify_partition.py` |

> Dung lượng CSV cục bộ chỉ là giá trị xấp xỉ. Đây không phải dung lượng dữ liệu trên HDFS hay đầu ra Parquet đã xử lý. Số dòng đầu ra được báo cáo không phải là một phép đối soát độc lập giữa nguồn và đầu ra.

## 3. Phạm vi thời gian

Phạm vi theo tháng dự kiến:

- 2022: Tháng 1–Tháng 12 (12 tháng)
- 2023: Tháng 1–Tháng 12 (12 tháng)
- 2024: Tháng 1–Tháng 12 (12 tháng)
- 2025: Tháng 1–Tháng 12 (12 tháng)
- 2026: Tháng 1–Tháng 3 (3 tháng)

**Tổng: 12 + 12 + 12 + 12 + 3 = 51 tháng.**

## 4. Bố trí lưu trữ

### Thư mục đầu vào cục bộ

```text
G:\Downloads_2\Batch_Layer\BTS_ZIP\
```

Thư mục này chứa các file CSV theo tháng đã được giải nén. Tên thư mục có chữ `ZIP`, nhưng các file đầu vào thực tế là file CSV.

### Tầng raw trên HDFS

```text
/aero/raw/bts/On_Time_Reporting_{year}_{month}.csv
```

Đây là mẫu đường dẫn file raw được script xử lý batch sử dụng. Hãy xác nhận đủ 51 file nguồn dự kiến đã có trong HDFS trước khi coi việc nạp dữ liệu tầng raw là đã được kiểm toán đầy đủ.

### Tầng processed trên HDFS

```text
/aero/processed/year=YYYY/month=MM/
```

Mỗi phân vùng tháng được kỳ vọng chứa các file part Parquet và metadata đầu ra của Spark như `_SUCCESS`.

Ví dụ:

```text
/aero/processed/
├── year=2022/
│   ├── month=01/
│   ├── month=02/
│   └── ...
├── year=2023/
├── year=2024/
├── year=2025/
└── year=2026/
    ├── month=01/
    ├── month=02/
    └── month=03/
```

## 5. Pipeline xử lý

Pipeline batch hiện tại gồm các bước:

1. Tải và giải nén các file CSV BTS theo tháng.
2. Lưu các file CSV nguồn vào tầng raw của HDFS.
3. Chạy `06_batch_process_all.py` bằng Spark.
4. Đọc từng file CSV theo tháng và kiểm tra các cột bắt buộc, gồm `FL_DATE`, `ORIGIN` và `DEST`.
5. Áp dụng các quy tắc làm sạch cơ bản đã cài đặt, gồm lọc các bản ghi thiếu giá trị bắt buộc, cắt khoảng trắng (trim) mã sân bay, và loại bỏ trùng lặp dựa trên các cột khóa sẵn có.
6. Ghi từng tháng vào đường dẫn processed trên HDFS ở định dạng Parquet.
7. Chạy `08_verify_partition.py` để kiểm tra đầu ra đã xử lý theo từng tháng.

Các phép biến đổi cụ thể và khóa dùng để loại trùng cần được lấy từ phiên bản hiện tại của `06_batch_process_all.py` khi ghi tài liệu cho một phiên bản mã nguồn hoặc khi bàn giao pipeline cho thành viên khác.

## 6. Tóm tắt kiểm tra

Lần chạy xác minh toàn bộ phân vùng đã báo cáo:

| Kiểm tra | Kết quả |
|---|---:|
| Số tháng dự kiến | 51 |
| Số tháng có dòng đầu ra | 51 |
| Tổng số dòng đã xử lý | 29,328,846 |
| Ngày bay không hợp lệ hoặc null mà verifier phát hiện | 0 |
| Số trường hợp lệch ngày/phân vùng mà verifier phát hiện | 0 |
| Số tháng thiếu kết quả | 0 |
| Kết quả chung | PASS |

### Kết quả này xác lập được điều gì

Job xác minh đọc được đầu ra Parquet đã xử lý, cả 51 nhóm tháng dự kiến đều có mặt, và các kiểm tra được cài đặt trong `08_verify_partition.py` đều đạt.

### Bản thân kết quả này không xác lập được điều gì

- Rằng cả 51 file CSV raw đã được đối soát độc lập với bản sao trên HDFS.
- Rằng số dòng đầu vào và đầu ra khớp chính xác.
- Rằng không còn bản ghi trùng lặp nào sau khi làm sạch.
- Rằng mọi trường nguồn đều không bị thay đổi hoặc mọi phép biến đổi đều đúng về mặt ngữ nghĩa.
- Rằng schema giống hệt nhau trên cả 51 tháng.

Những điều này cần được kiểm tra riêng nếu dự án cần bằng chứng chất lượng dữ liệu mạnh hơn.

## 7. Các script chính

| Script | Mục đích |
|---|---|
| `02_inspect_bts.py` | Kiểm tra một file CSV nguồn mẫu, các cột, schema và bản ghi mẫu |
| `03_clean_bts.py` | Bản mẫu làm sạch một tháng ở giai đoạn đầu; không phải pipeline chính cho 51 tháng |
| `04_validate_parquet.py` | Kiểm tra Parquet cho một phân vùng ở giai đoạn đầu |
| `05_quality_check.py` | Các kiểm tra chất lượng bổ sung cho một phân vùng |
| `06_batch_process_all.py` | ETL batch Spark chính cho khoảng 51 tháng |
| `07_retry_2022_01.py` | Script khôi phục cho tháng 1/2022; chỉ chạy khi phân vùng đó cần khôi phục |
| `08_verify_partition.py` | Xác minh các phân vùng đã xử lý theo tháng và tính nhất quán giữa ngày/phân vùng |

## 8. Cách chạy

Chạy các lệnh từ PowerShell trong thư mục dự án:

```powershell
Set-Location G:\Downloads_2\Batch_Layer
docker compose ps
```

Chạy job xác minh:

```powershell
docker compose exec spark /opt/spark/bin/spark-submit --master 'local[*]' --conf spark.hadoop.fs.defaultFS=hdfs://namenode:9000 /opt/spark_jobs/08_verify_partition.py
```

Chỉ chạy ETL chính khi chủ ý xử lý hoặc dựng lại đầu ra:

```powershell
docker compose exec spark /opt/spark/bin/spark-submit --master 'local[*]' --conf spark.hadoop.fs.defaultFS=hdfs://namenode:9000 /opt/spark_jobs/06_batch_process_all.py
```

> Script ETL có thể ghi đè các phân vùng đã xử lý theo tháng. Hãy kiểm tra chế độ ghi (write mode) hiện tại và trạng thái đầu ra trước khi chạy lại.

## 9. Ghi chú bàn giao

- Thành viên 1 phụ trách kiểm kê dữ liệu nguồn, bố trí nạp/lưu trữ và tài liệu bàn giao.
- Script ETL hiện tại đã thực hiện làm sạch cơ bản và loại trùng. Hãy phối hợp với Thành viên 2 để tránh lặp lại các phép biến đổi này.
- Thành viên 2 có thể xây dựng thêm phân tích và tối ưu hóa trên dữ liệu Parquet đã xử lý, theo phân công công việc đã thống nhất của nhóm.
- Hãy cập nhật tài liệu này nếu khoảng thời gian, các trường nguồn, đường dẫn HDFS hoặc logic xác minh thay đổi.
