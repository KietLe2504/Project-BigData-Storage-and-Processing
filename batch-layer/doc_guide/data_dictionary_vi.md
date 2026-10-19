# AERO — Từ điển dữ liệu (Data Dictionary)

## 1. Mục đích và phạm vi

Tài liệu này giải thích ý nghĩa của các trường quan trọng trong tập dữ liệu BTS On-Time Reporting được AERO sử dụng.

**Lưu ý quan trọng về schema:** đầu ra xác minh của dự án báo cáo 38 cột cho dữ liệu đã xử lý được kiểm tra. Bảng dưới đây ghi lại các trường cốt lõi được ETL hiện tại tham chiếu và các trường phân tích chuyến bay phổ biến khi áp dụng được. Trước khi coi đây là từ điển đầy đủ cho cả 38 cột, hãy đối chiếu từng mục với schema và tên trường thực tế trong dữ liệu Parquet đã xử lý hiện tại. Đừng giả định rằng các trường BTS có tên tương tự đều tồn tại nếu chúng không được chọn trong CSV nguồn.

## 2. Các trường cốt lõi được ETL hiện tại sử dụng

| Tên trường | Ý nghĩa | Kiểu / cách biểu diễn kỳ vọng | Ghi chú chất lượng dữ liệu |
|---|---|---|---|
| `FL_DATE` | Ngày bay | Date hoặc chuỗi biểu diễn ngày, tùy theo schema của pipeline | Bắt buộc theo ETL hiện tại; verifier kiểm tra ngày không hợp lệ/null và sự lệch giữa ngày và phân vùng |
| `ORIGIN` | Mã sân bay xuất phát | String | Bắt buộc theo ETL hiện tại; cần trim khoảng trắng và kiểm tra giá trị null/rỗng |
| `DEST` | Mã sân bay đến | String | Bắt buộc theo ETL hiện tại; cần trim khoảng trắng và kiểm tra giá trị null/rỗng |
| `OP_CARRIER` | Mã hãng vận hành, nếu có trong schema nguồn đã chọn | String | Xác nhận tên trường chính xác trong schema thực tế |
| `OP_UNIQUE_CARRIER` | Mã hãng vận hành duy nhất, nếu có | String | Có thể dùng làm định danh hãng tùy theo schema nguồn |
| `OP_CARRIER_FL_NUM` | Số hiệu chuyến bay của hãng vận hành, nếu có | Số hoặc chuỗi, tùy theo quá trình nạp/schema | Xác nhận trường và kiểu chính xác trước khi dùng làm khóa loại trùng |
| `year` | Giá trị phân vùng năm suy ra từ thư mục đầu ra | Integer hoặc string, tùy theo cách Spark suy luận phân vùng | Lấy từ `year=YYYY` trong đường dẫn processed; không nhất thiết là cột gốc của BTS |
| `month` | Giá trị phân vùng tháng suy ra từ thư mục đầu ra | Integer hoặc string, tùy theo cách Spark suy luận phân vùng | Lấy từ `month=MM` trong đường dẫn processed; không nhất thiết là cột gốc của BTS |

ETL hiện tại kiểm tra các trường `FL_DATE`, `ORIGIN` và `DEST`. Nó chọn các trường khóa hãng bay và số hiệu chuyến bay từ các tên ứng viên có trong dữ liệu. Hãy tham khảo `06_batch_process_all.py` để biết khóa loại trùng chính xác được dùng trong phiên bản đã chạy.

## 3. Các trường phân tích chuyến bay phổ biến — chỉ đưa vào nếu có trong schema thực tế

Các trường sau thường gặp trong dữ liệu BTS On-Time Reporting và có thể hữu ích cho phân tích của Thành viên 2. Đây **không phải khẳng định rằng mọi trường đều có trong 38 cột đã chọn hiện tại**.

| Tên trường | Ý nghĩa | Cách biểu diễn / đơn vị thường gặp | Công dụng khả dĩ |
|---|---|---|---|
| `DEP_DELAY` | Độ trễ khởi hành | Số, đơn vị phút; giá trị âm có thể cho biết khởi hành sớm | Độ trễ khởi hành trung bình, tỷ lệ khởi hành trễ |
| `ARR_DELAY` | Độ trễ đến | Số, đơn vị phút; giá trị âm có thể cho biết đến sớm | Độ trễ đến trung bình, tỷ lệ đến trễ |
| `DEP_DEL15` | Chỉ báo trễ khởi hành từ 15 phút trở lên | Thường là 0/1 | Tính tỷ lệ trễ khởi hành |
| `ARR_DEL15` | Chỉ báo trễ đến từ 15 phút trở lên | Thường là 0/1 | Tính tỷ lệ trễ khi đến |
| `CANCELLED` | Cho biết chuyến bay có bị hủy hay không | Thường là 0/1 | Số lượng và tỷ lệ hủy chuyến |
| `CANCELLATION_CODE` | Mã lý do hủy chuyến, khi có | Mã phân loại | Phân tích lý do hủy chuyến |
| `DIVERTED` | Cho biết chuyến bay có bị chuyển hướng hay không | Thường là 0/1 | Số lượng và tỷ lệ chuyển hướng |
| `DISTANCE` | Khoảng cách chuyến bay được báo cáo | Thường là dặm (miles) trong dữ liệu BTS | Phân tích tuyến bay và khoảng cách |
| `CRS_DEP_TIME` | Giờ khởi hành theo lịch | Thường là số dạng HHMM | So sánh giờ theo lịch với mẫu hình trễ chuyến |
| `CRS_ARR_TIME` | Giờ đến theo lịch | Thường là số dạng HHMM | So sánh giờ theo lịch với mẫu hình trễ chuyến |
| `CARRIER_DELAY` | Số phút trễ do hãng bay, khi được báo cáo | Số, đơn vị phút | Phân tích nguyên nhân trễ |
| `WEATHER_DELAY` | Số phút trễ do thời tiết, khi được báo cáo | Số, đơn vị phút | Phân tích nguyên nhân trễ |
| `NAS_DELAY` | Số phút trễ do Hệ thống Không phận Quốc gia (NAS), khi được báo cáo | Số, đơn vị phút | Phân tích nguyên nhân trễ |
| `SECURITY_DELAY` | Số phút trễ do an ninh, khi được báo cáo | Số, đơn vị phút | Phân tích nguyên nhân trễ |
| `LATE_AIRCRAFT_DELAY` | Số phút trễ do máy bay đến muộn, khi được báo cáo | Số, đơn vị phút | Phân tích nguyên nhân trễ |

## 4. Diễn giải các giá trị thường gặp

- **Thiếu / null:** không có giá trị nào được ghi nhận hoặc cung cấp cho trường đó. Giá trị null không tự động tương đương với số không.
- **Giá trị độ trễ:** các trường độ trễ nhìn chung được đo bằng phút. Giá trị âm có thể cho biết sự kiện xảy ra sớm hơn lịch.
- **Trường chỉ báo:** các giá trị như `0` và `1` thường lần lượt biểu thị sai/không và đúng/có; hãy xác minh cách mã hóa thực tế và hành vi với null trong tập dữ liệu đã chọn.
- **Mã sân bay:** coi `ORIGIN` và `DEST` là định danh, không phải đại lượng số.
- **Trường phân vùng:** `year` và `month` được suy ra từ cấu trúc thư mục. Hãy đối chiếu chúng với `FL_DATE`, như script xác minh đã làm.

## 5. Danh sách kiểm tra hoàn thiện schema

Trước khi nộp tài liệu này như từ điển cuối cùng:

- [ ] Trích xuất danh sách cột chính xác từ schema Parquet đã xử lý.
- [ ] Đưa vào mọi cột có trong tập dữ liệu 38 cột đã chọn, đúng chính tả và chữ hoa/thường.
- [ ] Ghi lại kiểu dữ liệu Spark thực tế của từng cột; đừng suy ra kiểu chỉ từ tên trường.
- [ ] Thêm định nghĩa nghiệp vụ ngắn gọn và đơn vị cho từng trường khi áp dụng được.
- [ ] Kiểm tra xem schema có nhất quán trên 51 phân vùng tháng hay không.
- [ ] Phân biệt các trường nguồn với các trường phân vùng được suy ra như `year` và `month`.

## 6. Quan hệ với pipeline

- `06_batch_process_all.py` là nguồn chính cho các cột bắt buộc, quy tắc làm sạch và logic khóa loại trùng.
- `08_verify_partition.py` kiểm tra độ phủ theo tháng của đầu ra, số dòng, tính hợp lệ của ngày, và sự nhất quán giữa ngày bay với năm/tháng của phân vùng.
- Kết quả xác minh hiện tại tự nó không xác lập được rằng mọi cột có kiểu giống hệt nhau trên cả 51 tháng, hay rằng không còn bản ghi trùng lặp nào.
