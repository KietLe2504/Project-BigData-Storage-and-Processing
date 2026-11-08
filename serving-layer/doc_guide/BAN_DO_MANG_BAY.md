# Bản đồ mạng đường bay

Mở **Tuyến bay → Bản đồ mạng bay** tại `http://localhost:8501`.
Bản đồ hiển thị KPI tuyến lịch sử từ `kpi_year_route` của snapshot active.

- Mỗi đường nối là một chiều sân bay đi → sân bay đến. Đường dày hơn tương ứng
  nhiều chuyến hơn; thang căn bậc hai giúp tuyến nhỏ vẫn nhìn thấy được.
- Màu đường biểu thị một chỉ tiêu được chọn: tỷ lệ trễ ≥15 phút, delay đến
  trung bình hoặc tỷ lệ hủy. Chú giải giữ thang cố định giữa các bộ lọc/năm.
  Giá trị thiếu có màu xám, delay âm vẫn là giá trị hợp lệ.
- Điểm sân bay lớn hơn tương ứng nhiều lượt đi + đến trong các tuyến đang vẽ.
  Không cộng số lượt của mọi sân bay thành tổng chuyến: mỗi chuyến có hai đầu.
- Rê chuột để xem hai đầu tuyến, số chuyến, trễ, delay trung bình, đúng giờ và
  hủy. Rê vào sân bay để xem số lượt đi/đến. Kéo, zoom hoặc bật góc nhìn 3D.
- Chọn một sân bay để xem các đường nối cả hai chiều; chọn Toàn bộ tuyến hoặc
  chế độ Top, đặt số chuyến tối thiểu và xem tỷ trọng chuyến thực sự được vẽ.
  Mặc định dùng Top 150 để dễ đọc và tránh các đường che nhau; có thể chuyển
  sang Toàn bộ tuyến trong phần tùy chỉnh.
  Với hơn 1.000 tuyến, đường nối thẳng được dùng để vẽ đủ mạng với ít hình học
  hơn; chế độ Top hoặc một sân bay dùng các cung để tách hai chiều dễ nhìn.
- Góc nhìn **Toàn mạng đang chọn** tự bao các sân bay, kể cả Alaska, Hawaii và
  các lãnh thổ qua đường đổi ngày. Góc nhìn Hoa Kỳ lục địa giúp đọc mạng chính.
- Bảng chi tiết bên dưới có thể tải CSV cho chính các tuyến đang vẽ.

Các KPI ở bốn thẻ phía trên bản đồ chỉ thuộc **các tuyến đang vẽ**, tính lại
từ số đếm (`sum(delayed15)/sum(arr_n)`), không lấy trung bình tỷ lệ từng tuyến.
Các tab Sankey/xếp hạng/tương quan vẫn dùng bộ lọc tuyến chung ở đầu trang;
bộ lọc bổ sung bên trong tab bản đồ áp dụng riêng cho bản đồ.

Đây là đường nối minh họa trên địa lý, không phải quỹ đạo thực tế hay vị trí
máy bay theo thời gian thực. Nguồn hiện có mức năm; 2026 chỉ gồm tháng 1–3.

## Tọa độ và nguồn

Tọa độ từ [OurAirports](https://ourairports.com/data/), phát hành Public Domain,
được lưu cục bộ trong `assets/airport_coordinates.csv`. Có 380 mã sân bay,
phủ toàn bộ các mã xuất hiện trong snapshot M2 `20261107T042703414867Z`.
KPI vẫn lấy từ M2, không lấy lưu lượng hay độ trễ từ nguồn tọa độ.
Ngày tải, SHA-256 và alias có trong `airport_coordinates.source.json`.

Mã PBI trong giai đoạn BTS lịch sử được ghép rõ ràng tới OurAirports ident
KPBI dù danh bạ hiện tại đổi mã. Giữ nguyên PBI trong dữ liệu M2; không sửa
khóa nghiệp vụ. [FAA AIP 2024](https://www.faa.gov/air_traffic/publications/media/AIP_Basic_dtd_3-21-24_POST.pdf)
đối chứng tên/mã lịch sử. Các mã mới chưa có tọa độ được báo số tuyến và số
chuyến bị bỏ khỏi bản đồ; không đặt điểm giả hoặc bỏ âm thầm.

Muốn cập nhật lookup, tải `airports.csv` theo link nguồn rồi chạy Python:

```text
python scripts/build_airport_lookup.py --airports-csv airports.csv --routes-jsonl <snapshot>/kpi__year_route.jsonl
```

Script dừng nếu còn mã chưa được ghép, thay vì đoán tọa độ. Bản đồ nền dùng
CARTO và cần Internet từ trình duyệt; không cần đăng ký Mapbox token.

## Chạy và kiểm tra

Sau khi cập nhật code, chạy ở PowerShell trong `serving-layer`:

```powershell
.\scripts\start_m5.ps1
```

Script build lại image, chờ dịch vụ healthy; dữ liệu volume MongoDB được giữ.
Không cần nạp lại M2. Kiểm tra một sân bay, chế độ toàn mạng/Top, tooltip,
đổi màu chỉ tiêu, góc nhìn 3D và bảng CSV. Chạy kiểm thử theo script `test_m5.ps1`.

Triển khai sử dụng [PyDeck ArcLayer](https://deckgl.readthedocs.io/en/latest/gallery/arc_layer.html)
và [Streamlit 1.50 st.pydeck_chart](https://docs.streamlit.io/1.50.0/develop/api-reference/charts/st.pydeck_chart).
