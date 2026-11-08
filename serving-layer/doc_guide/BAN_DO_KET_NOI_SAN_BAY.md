# Bản đồ kết nối của từng sân bay

Mở **Danh mục hãng bay & sân bay → Sân bay**, chọn sân bay trong ô hồ sơ.

## Thao tác

1. Bản đồ tự lấy vị trí sân bay đang chọn (vàng) và **tất cả sân bay có
   chuyến đi hoặc đến** trong phạm vi năm đang chọn (xanh). Từ khóa và vùng
   chỉ lọc danh sách hồ sơ, không cắt bớt các sân bay kết nối trên bản đồ.
2. Mỗi đường nối là một cặp sân bay, gộp cả hai chiều. Độ dày và thang màu
   xanh dương → ngọc → vàng → hồng biểu thị **tổng số chuyến hai chiều**.
   Hai thang dùng căn bậc hai để các kết nối ít chuyến vẫn nhìn thấy được.
   Chú giải ghi giá trị min/max thực tế của mạng đang xem; các sân bay khác
   nhau có thể có thang khác nhau. Tooltip ghi chính xác số chuyến từng chiều.
3. Bấm một điểm sân bay để chuyển hồ sơ và mở mạng kết nối của sân bay đó.
   Nếu sân bay nằm ngoài kết quả tìm kiếm/vùng hiện tại, bộ lọc danh sách
   được xóa để hồ sơ vừa chọn có thể hiển thị.
4. Bấm một đường để mở thống kê cặp sân bay ở ngay dưới bản đồ. Có thể
   chọn cặp bằng danh sách nếu các đường nằm sát nhau hoặc dùng bàn phím.
5. Chọn **Cả hai chiều** hoặc một chiều để xem số chuyến, đúng giờ/trễ
   dưới 15 phút, trễ từ 15 phút, hủy và chuyển hướng; biểu đồ hãng; cơ cấu
   trạng thái; bảng số liệu và CSV. Phân bố hãng phải cộng đúng tổng chuyến.

Đây là kết nối lịch sử, không phải đường bay thực tế của từng chuyến hay vị
trí máy bay trực tiếp. Bản đồ tự bao toàn bộ các sân bay liên quan, gồm
Alaska/Hawaii/lãnh thổ nếu có kết nối. Các mã thiếu tọa độ được báo và vẫn
giữ trong danh sách chọn thống kê. Năm 2026 chỉ có quý I.

## Thống kê và ý nghĩa

Các KPI tổng và từng chiều lấy từ `kpi_year_route` của snapshot active,
tính lại từ tổng số đếm. Chuyến hủy không bị tính vào đúng giờ. Trễ từ 60
phút là tập con của trễ từ 15 phút, không tạo thêm nhóm cộng trùng trong
biểu đồ cơ cấu. Những chuyến không đủ giờ đến hợp lệ được giữ thành nhóm
riêng; tỷ lệ trễ và delay trung bình chỉ dùng `arr_n` hợp lệ.

Bảng `kpi_year_carrier_origin` **không có sân bay đến**, nên không thể suy
ra phân bố hãng trên từng cặp từ bảng đó. Chức năng này dùng bảng bổ sung
`year, origin, dest, carrier, flights`, được Spark đếm trực tiếp từ Parquet
M2 đã làm sạch. Đây là đếm chuyến, không phải số hành khách hoặc ghế.

## Tạo và bàn giao bảng hãng theo tuyến

Giữ nguyên snapshot M2 20 bảng hiện có. Trên máy có HDFS và dữ liệu đã
làm sạch, chạy trong **PowerShell tại thư mục project**:

```powershell
docker compose -f .\batch-layer\docker-compose.yml up -d spark
docker compose -f .\batch-layer\docker-compose.yml exec -T -u root spark /opt/spark/bin/spark-submit --master 'local[2]' --driver-memory 2g /opt/spark_jobs/10_export_route_carriers.py --base-snapshot /opt/spark_jobs/export/m2_to_m5/20261107T042703414867Z
if ($LASTEXITCODE -ne 0) { throw 'Xuat bang hang theo tuyen chua thanh cong' }
```

Thay đường dẫn snapshot cho đúng bộ M2 của nhóm. Script chỉ đọc các tháng
trong manifest, group đúng theo năm và bốn mã liên quan, rồi kiểm tra:

- Tổng hãng trên **mọi tuyến từng năm** bằng `kpi__year_route.jsonl`.
- Tổng tuyến theo **mọi hãng–sân bay xuất phát từng năm** bằng
  `kpi__year_carrier_origin.jsonl`.

Chỉ sau khi cả hai đối chiếu đạt mới công bố thư mục timestamp dưới
`batch-layer/spark_jobs/export/m2_route_carriers/`, gồm `route_carrier.jsonl`
và `manifest.json` với SHA-256, coverage và nguồn. Chuyển **cả thư mục** cho
thành viên chạy M5. Không cần chuyển raw hoặc cleaned Parquet nếu chỉ dùng
dashboard đã có bảng bổ sung.

## Nạp vào MongoDB

Chạy trong **PowerShell tại `serving-layer`**:

```powershell
.\scripts\start_m5.ps1
.\scripts\load_route_carriers.ps1 -SupplementPath '..\batch-layer\spark_jobs\export\m2_route_carriers\20261108T060505228918Z' -BaseSnapshotPath '..\batch-layer\spark_jobs\export\m2_to_m5\20261107T042703414867Z'
```

Thay hai timestamp theo thư mục thực tế. Loader kiểm tra file hash, khóa
duy nhất, phạm vi và các số đếm so với snapshot MongoDB đang active; ghi
`route_carrier_counts` theo phiên bản; đọc lại so khớp toàn bộ rồi mới đổi
con trỏ `route_carrier_state`. Nạp lại không nhân đôi. Bản lỗi không thay
phân bố đang phục vụ. Hai collection bổ sung được tách khỏi 20 bảng chuẩn
M2. Đổi snapshot M2 phải tạo/nạp bổ sung tương ứng, không dùng lẫn dữ liệu.

Sau nạp, nhấn **Làm mới dữ liệu** trong dashboard. Nếu chưa có bảng bổ
sung, KPI tuyến vẫn xem được và trang báo rõ phần phân bố hãng còn thiếu.
Báo cáo nạp: `evidence/route_carrier_load.json`; log:
`logs/load_route_carriers.log`.

## Kiểm tra

Với snapshot `20261107T042703414867Z`, bảng bổ sung có **63.440 nhóm**, phủ
**33.373 tuyến từng năm**, **8.559 nhóm hãng–sân bay xuất phát từng năm**,
và tổng **29.328.846 chuyến**. ALS có một sân bay kết nối DEN, tổng 521
chuyến hai chiều trên toàn giai đoạn; JFK có 85 sân bay kết nối.

Kiểm tra bấm điểm, bấm đường, chọn lại năm/sân bay và tách chiều; tổng
hãng, cơ cấu trạng thái và bảng phải khớp thẻ tổng chuyến của cặp đang xem.
Kiểm thử tự động chạy qua `scripts/test_m5.ps1` trong database test riêng.

API tương tác: [Streamlit 1.50 PyDeck selections](https://docs.streamlit.io/1.50.0/develop/api-reference/charts/st.pydeck_chart).
