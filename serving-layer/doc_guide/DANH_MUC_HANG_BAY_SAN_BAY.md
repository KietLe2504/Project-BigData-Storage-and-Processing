# Danh mục hãng bay và sân bay

Mở `http://localhost:8501`, chọn **Danh mục hãng bay & sân bay** ở thanh bên.
Mặc định tra cứu toàn bộ giai đoạn M2. Snapshot hiện có 17 mã hãng và 380 mã
sân bay; chọn năm để thu hẹp về các đơn vị có bản ghi trong năm đó.

## Hãng bay

- Tìm theo mã hoặc một phần tên; chọn hãng để xem hồ sơ.
- Hồ sơ gồm tên đầy đủ, mã hãng M2, tháng đầu/cuối có bản ghi, số tháng quan
  sát, số chuyến, tỷ lệ đúng giờ, trễ ≥15 phút và hủy chuyến.
- Biểu đồ cho biết lưu lượng theo tháng; hai bảng xếp hạng đặt cạnh nhau
  thể hiện các sân bay xuất phát và các sân bay điểm đến nhiều chuyến nhất
  của hãng (Top 10). Cả hai dùng cùng phạm vi năm của hồ sơ. Điểm đến được
  cộng từ mọi sân bay xuất phát trong bảng hãng–tuyến đã kiểm tra; tổng phải
  khớp tổng chuyến của hãng trước khi hiển thị. Sân bay đích là điểm đến theo
  lịch, gồm cả chuyến hủy trong dữ liệu sau cleaning. Khoảng tháng thiếu
  được để trống, không dựng dữ liệu.
- Danh sách đầy đủ theo bộ lọc có thể tải CSV.

Tên hãng đối chiếu [BTS Airline Codes](https://www.bts.gov/topics/airlines-and-airports/airline-codes),
lưu tại `assets/airline_reference.csv`; ngày đối chiếu và hash trong file
`.source.json`. Mã hãng lịch sử được giữ nguyên. Tháng có bản ghi không phải
ngày thành lập/đóng cửa; thông tin này không khẳng định tình trạng hoạt động
hiện nay hoặc suy diễn quan hệ giữa hãng vùng và thương hiệu bán vé.

## Sân bay

- Tìm theo mã, tên hoặc thành phố; lọc thêm bang/vùng lãnh thổ.
- Hồ sơ gồm mã M2, ICAO nếu có, tên, thành phố, quốc gia, vùng, phân loại,
  độ cao (ft), tọa độ và đường dẫn tham chiếu/website nếu nguồn có cung cấp.
- Bản đồ hiển thị sân bay đang xem (vàng) và toàn bộ sân bay có chuyến đi/đến
  với nó (xanh), kể cả ngoài bộ lọc tìm kiếm. Độ dày/màu đường theo tổng
  chuyến hai chiều; bấm điểm để đổi sân bay, bấm đường để xem thống kê cặp.
- Thống kê gồm chuyến đi/đến theo lịch, số sân bay kết nối và tỷ lệ trễ của
  chuyến đến. Có biểu đồ các hãng xuất phát tại sân bay và tuyến nhiều chuyến
  nhất, phân biệt chiều đi/đến bằng tên tuyến.
- Danh mục lấy hợp cả `origin` và `dest`, bao gồm sân bay chỉ có chuyến đến.
  Mã thiếu thông tin tham chiếu vẫn xuất hiện; không đoán tên hay tọa độ.

Xem [hướng dẫn bản đồ kết nối và bảng hãng theo tuyến](BAN_DO_KET_NOI_SAN_BAY.md)
để tạo/nạp nguồn phân bố hãng chính xác và sử dụng thống kê khi bấm đường.

Tên/tọa độ giữ cách ghép mã lịch sử của `airport_coordinates.csv`; phần hồ
sơ bổ sung từ [OurAirports](https://ourairports.com/data/) (Public Domain)
được lưu tại `assets/airport_details.csv` và metadata đi kèm. Thông tin tham
chiếu phản ánh lần tải danh mục, có thể khác giai đoạn KPI. Bản đồ nền cần
Internet để tải.

Để cập nhật hồ sơ sau khi cập nhật lookup tọa độ, tải CSV từ nguồn rồi chạy:

```text
python scripts/build_airport_details.py --source airports.csv
```

## Cách hiểu số liệu

Số chuyến và hiệu suất luôn lấy từ snapshot MongoDB đang active. Hồ sơ hãng
dùng `kpi_month_carrier`; lượt sân bay và tuyến dùng `kpi_year_route`;
các hãng/sân bay xuất phát dùng `kpi_year_carrier_origin`. Không suy diễn
tuyến theo hãng từ bảng tuyến vốn không có chiều hãng.

KPI tính lại từ tổng số đếm, không lấy trung bình các tỷ lệ. Chuyến theo
lịch gồm chuyến hủy sau cleaning; tỷ lệ trễ chỉ tính trên `arr_n` hợp lệ.
Không có mẫu số thì hiển thị “—”. Mỗi chuyến có một sân bay đi và đến, vì vậy
không cộng lượt mọi sân bay thành tổng số chuyến của mạng. Năm 2026 chỉ có
tháng 1–3; chọn cùng kỳ khi cần so sánh năm.

Chạy `scripts/start_m5.ps1` để build dashboard sau cập nhật code. Không cần
nạp lại M2; các bảng tham chiếu được đóng gói trong image, không sửa MongoDB.
