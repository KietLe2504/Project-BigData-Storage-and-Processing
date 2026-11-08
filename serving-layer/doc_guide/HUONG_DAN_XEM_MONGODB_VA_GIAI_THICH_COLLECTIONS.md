# M5 — Mở MongoDB, xem collection và đọc các trường dữ liệu

Tài liệu dành cho thành viên muốn xem trực tiếp dữ liệu M5, hiểu mỗi collection
lưu gì và giải thích các con số trên dashboard. Đối chiếu với code và bộ M2
mẫu `20261107T042703414867Z`, bảng hãng–tuyến `20261108T060505228918Z`.

Nếu chưa dựng hoặc chưa nạp M5, làm theo
[hướng dẫn chạy từ đầu](HUONG_DAN_CHAY_TU_DAU_DEN_OUTPUT_M5.md) trước.
Các thao tác tra cứu trong tài liệu này chỉ đọc dữ liệu.

## Mục lục

1. [Hiểu database, collection, document và snapshot](#1-hiểu-database-collection-document-và-snapshot)
2. [Mở MongoDB bằng Compass](#2-mở-mongodb-bằng-compass)
3. [Xem bằng terminal với mongosh](#3-xem-bằng-terminal-với-mongosh)
4. [Bảng giải thích 25 collection](#4-bảng-giải-thích-25-collection)
5. [Trường định danh và thời gian](#5-trường-định-danh-và-thời-gian)
6. [Các trường trong collection KPI](#6-các-trường-trong-collection-kpi)
7. [Các trường trong collection box](#7-các-trường-trong-collection-box)
8. [Các trường trong bảng hãng–tuyến](#8-các-trường-trong-bảng-hãngtuyến)
9. [Các trường quản lý nạp và công bố dữ liệu](#9-các-trường-quản-lý-nạp-và-công-bố-dữ-liệu)
10. [Ví dụ đọc dữ liệu và liên hệ dashboard](#10-ví-dụ-đọc-dữ-liệu-và-liên-hệ-dashboard)
11. [Lỗi thường gặp và những cách hiểu cần tránh](#11-lỗi-thường-gặp-và-những-cách-hiểu-cần-tránh)

## 1. Hiểu database, collection, document và snapshot

| Khái niệm | Ý nghĩa trong project |
|---|---|
| Database `aero_m5` | Cơ sở dữ liệu chứa các collection phục vụ M5. Có thể đổi tên bằng `M5_DATABASE`. |
| Collection | Nhóm document cùng mục đích, có thể liên tưởng như một bảng. Ví dụ `kpi_month_carrier`. |
| Document | Một bản ghi BSON, thường được xem dưới dạng JSON trong Compass. Với bảng tổng hợp, một document đại diện cho một nhóm chuyến bay. |
| Field / trường | Thuộc tính trong document, ví dụ `year`, `carrier`, `flights`. |
| Snapshot | Một bộ dữ liệu M2 được nhận diện từ nội dung bằng fingerprint, lưu trong trường `snapshot_id`. |
| Phiên bản bổ sung | Bảng hãng–tuyến được nhận diện bằng `data_version` và gắn với một snapshot M2. |

Ví dụ: document của `kpi_month_carrier` với `year=2025, month=1, carrier=AA`
là thống kê của **hãng AA trong tháng 01/2025**, không phải một chuyến bay.

Bộ mẫu có 20 bảng M2, tổng 74.921 document mô tả 29.328.846 chuyến sau cleaning.
Bảng hãng–tuyến bổ sung có 63.440 document. Các collection quản lý được tính
riêng; số document vật lý sẽ lớn hơn nếu lưu nhiều snapshot/phiên bản.

`snapshot_id` là chuỗi hash từ nội dung, **khác tên thư mục timestamp** như
`20261107T042703414867Z`. Khi tra cứu, lấy mã đang sử dụng từ `serving_state`.

## 2. Mở MongoDB bằng Compass

### 2.1. Kiểm tra MongoDB của project đang chạy

Mở Docker Desktop, chờ engine sẵn sàng. Mở **PowerShell Windows** hoặc terminal
PowerShell của VS Code. Thay đường dẫn đầu theo máy của bạn:

```powershell
$AeroProject = 'F:\Project-BigData-Storage-and-Processing'
Set-Location (Join-Path $AeroProject 'serving-layer')
docker compose -f compose.yml ps
```

Service `mongo` cần có trạng thái healthy. Nếu M5 đang dừng, chạy:

```powershell
.\scripts\start_m5.ps1
```

MongoDB Server đã chạy trong container; không cần cài thêm MongoDB Server
riêng trên Windows. Compass là ứng dụng giao diện để kết nối và xem server đó.

### 2.2. Mở Compass và kết nối

1. Nếu chưa có Compass, cài theo [hướng dẫn MongoDB chính thức](https://www.mongodb.com/docs/compass/install/).
2. Mở **MongoDB Compass** → **Add New Connection**.
3. Nhập URI `mongodb://localhost:27017`.
4. Có thể đặt tên kết nối **AERO M5 Local**, rồi chọn **Connect** hoặc **Save & Connect** tùy phiên bản.
5. Trong danh sách database, mở **`aero_m5`**.
6. Chọn một collection, ví dụ **`kpi_month_overall`**, rồi mở tab **Documents**.
7. Chuyển kiểu xem JSON, danh sách hoặc bảng nếu muốn; mở rộng các trường/object để đọc chi tiết.

Cấu hình local trong `compose.yml` hiện không đặt tài khoản MongoDB. Nếu
nhóm đã đổi cấu hình, sử dụng URI và thông tin kết nối tương ứng.

| Kết nối từ đâu? | URI mặc định | Giải thích |
|---|---|---|
| Compass trên Windows | `mongodb://localhost:27017` | Cổng MongoDB được Docker publish về máy Windows. |
| Dashboard/loader trong mạng Compose | `mongodb://mongo:27017` | `mongo` là tên service trong mạng Docker. |

Nếu đã đổi `M5_MONGO_PORT` trong `.env`, đọc cột PORTS của `docker compose ps`
và dùng cổng mới trong Compass. Ví dụ publish 27018 thì URI là
`mongodb://localhost:27018`. Nếu đổi `M5_DATABASE`, chọn database theo tên mới.

### 2.3. Tìm đúng snapshot đang được dashboard sử dụng

1. Mở collection **`serving_state`** → **Documents**.
2. Trong ô **Filter**, nhập:

```json
{ "_id": "historical" }
```

3. Chọn **Find**. Sao chép giá trị chuỗi **`snapshot_id`** trong document.
4. Mở **`kpi_month_overall`**. Nhập bộ lọc sau, thay chuỗi mẫu bằng mã vừa sao chép:

```json
{
  "snapshot_id": "DAN_SNAPSHOT_ID_THUC_TE_VAO_DAY",
  "year": 2025,
  "month": 1
}
```

5. Chọn **Find**, đọc các trường `flights`, `on_time`, `delayed15`,
   `cancelled`, `otp_operated`, `avg_arr_delay_net`.
6. Mở tab **Indexes** để xem khóa duy nhất `snapshot_business_key`.

Với bộ mẫu, kết quả là một document cho tháng 01/2025 của snapshot đang chọn.
Ô Filter của Compass nhận **document điều kiện**, không nhận toàn bộ lệnh
`db.collection.find(...)`. Giữ các trường số như `year`, `month` ở kiểu số.

### 2.4. Xem box và bảng hãng–tuyến

Trong **`box_year_carrier`**, lọc phân bố delay đến của AA năm 2025, toàn bộ
quan sát hợp lệ:

```json
{
  "snapshot_id": "DAN_SNAPSHOT_ID_THUC_TE_VAO_DAY",
  "year": 2025,
  "carrier": "AA",
  "var": "arr",
  "population": "all"
}
```

Với **`route_carrier_counts`**, trước hết mở **`route_carrier_state`**, tìm
document có `_id` bằng snapshot đang dùng và `status` bằng `ready`. Sao chép
**`data_version`** của document đó. Sau đó lọc:

```json
{
  "snapshot_id": "DAN_SNAPSHOT_ID_THUC_TE_VAO_DAY",
  "data_version": "DAN_DATA_VERSION_THUC_TE_VAO_DAY",
  "year": 2022,
  "origin": "ALS",
  "dest": "DEN"
}
```

Bộ mẫu trả về hãng `OO`, `flights=261` cho chiều ALS → DEN năm 2022.
Chiều DEN → ALS là document khác với `flights=260`. Khi dùng bảng bổ sung,
lọc cả snapshot và phiên bản đã được công bố để tránh cộng nhiều phiên bản.

## 3. Xem bằng terminal với mongosh

Không cần Compass hoặc cài mongosh riêng lên Windows vì image MongoDB đã có
mongosh. **Dòng sau chạy trong PowerShell tại `serving-layer`:**

```powershell
docker compose -f compose.yml exec mongo mongosh aero_m5
```

Nếu database đã đổi tên, thay `aero_m5` bằng tên thực tế. Khi vào được shell
MongoDB, dấu nhắc thường là `aero_m5>`, không còn là `PS F:\...>`.

**Từ đây, các khối JavaScript chạy trong mongosh, không dán vào PowerShell.**

```javascript
db.getName();
db.getCollectionNames().sort();

var activeM5 = db.serving_state.findOne({ _id: "historical" });
if (!activeM5) { throw new Error("Chua co snapshot active. Nap M2 truoc."); }
var sidM5 = activeM5.snapshot_id;
print(sidM5);

db.kpi_month_overall.findOne({ snapshot_id: sidM5, year: 2025, month: 1 });
db.kpi_month_overall.countDocuments({ snapshot_id: sidM5 });
db.kpi_month_overall.getIndexes();

db.kpi_month_overall.aggregate([
  { $match: { snapshot_id: sidM5 } },
  { $group: { _id: null, total_flights: { $sum: "$flights" } } }
]);
```

Với bộ mẫu: `countDocuments` trả **51**, `total_flights` là **29328846**.
Số document theo snapshot ở 20 bảng được liệt kê trong mục 4.

Xem KPI tuyến và phân bố hãng hai chiều ALS ↔ DEN:

```javascript
db.kpi_year_route.find(
  { snapshot_id: sidM5, year: 2022, origin: "ALS", dest: "DEN" },
  { _id: 0, year: 1, origin: 1, dest: 1, flights: 1, on_time: 1, delayed15: 1, cancelled: 1 }
);

var supplementM5 = db.route_carrier_state.findOne({ _id: sidM5, status: "ready" });
if (!supplementM5) { throw new Error("Chua nap bang hang-tuyen cho snapshot nay."); }
var versionM5 = supplementM5.data_version;

db.route_carrier_counts.find({
  snapshot_id: sidM5,
  data_version: versionM5,
  year: 2022,
  $or: [{ origin: "ALS", dest: "DEN" }, { origin: "DEN", dest: "ALS" }]
}, { _id: 0, snapshot_id: 0, data_version: 0 });

db.route_carrier_counts.countDocuments({ snapshot_id: sidM5, data_version: versionM5 });
```

Count bảng bổ sung của bộ mẫu là **63440**. Gõ `exit` để trở lại PowerShell.
Các biến ở đây dùng `var` để có thể chạy lại trong cùng phiên mongosh.

## 4. Bảng giải thích 25 collection

Phạm vi bảng: **25 collection đã triển khai cho luồng lịch sử M2 → M5**.
Collection streaming có thể được tạo thêm khi tích hợp M4; không thuộc bộ
25 collection dưới đây. Các số lượng là mốc của bộ mẫu, không phải hằng số
cho mọi dữ liệu tương lai hoặc tổng của tất cả snapshot.

### 4.1. Mười ba collection KPI

Các khóa trong bảng là khóa nghiệp vụ. MongoDB còn ghép thêm `snapshot_id`
trong unique index để phân biệt các bộ dữ liệu.

| Collection | Khóa nghiệp vụ / một document đại diện cho | Nội dung và ứng dụng | Document bộ mẫu |
|---|---|---|---:|
| `kpi_day_overall` | `year, month, day`: một ngày cụ thể | KPI toàn hệ thống trong ngày, dùng xem nhịp bay và độ trễ từng ngày. | 1.551 |
| `kpi_calendar_day_overall` | `month, day`: một ngày/tháng, gộp các năm có dữ liệu | Ví dụ gộp ngày 01/01 qua các năm; dùng heatmap lịch và phân tích ngày đặc biệt. | 366 |
| `kpi_month_overall` | `year, month`: một tháng cụ thể | KPI tổng quan theo tháng, ví dụ riêng tháng 01/2025. | 51 |
| `kpi_month_of_year_overall` | `month`: một tháng trong năm, gộp các năm | Ví dụ tất cả tháng 1 có dữ liệu; dùng phân tích mùa vụ. | 12 |
| `kpi_year_overall` | `year`: một năm | Tổng chuyến và hiệu suất toàn hệ thống theo năm. | 5 |
| `kpi_month_carrier` | `year, month, carrier`: một hãng trong một tháng cụ thể | Lưu lượng theo tháng và KPI của từng hãng. | 771 |
| `kpi_month_of_year_carrier` | `month, carrier`: một hãng và một tháng trong năm, gộp các năm | Mùa vụ riêng của hãng, ví dụ AA trong tất cả tháng 1 có dữ liệu. | 204 |
| `kpi_year_carrier` | `year, carrier`: một hãng trong một năm | So sánh quy mô, đúng giờ, trễ và hủy giữa các hãng. | 74 |
| `kpi_month_origin` | `year, month, origin`: một sân bay xuất phát trong một tháng cụ thể | Thống kê các chuyến xuất phát từ sân bay đó. | 17.491 |
| `kpi_year_origin` | `year, origin`: một sân bay xuất phát trong một năm | Xếp hạng sân bay xuất phát theo năm. | 1.768 |
| `kpi_year_route` | `year, origin, dest`: một tuyến có chiều trong một năm | Lưu lượng, đúng giờ, trễ, hủy trên tuyến; dùng bản đồ và thống kê cặp sân bay. | 33.373 |
| `kpi_year_carrier_origin` | `year, carrier, origin`: một hãng tại một sân bay xuất phát trong một năm | Cơ cấu hãng tại sân bay, Top sân bay xuất phát của hãng; bảng này không có chiều `dest`. | 8.559 |
| `kpi_hour_overall` | `dep_hour`: một giờ khởi hành theo lịch, gộp toàn kỳ | Khung 0–23 giờ, dùng polar/chart lưu lượng và độ trễ theo giờ. | 24 |

Tổng KPI: **64.249 document**. Trong bảng `origin`, delay đến mô tả độ trễ
khi kết thúc các chuyến **xuất phát từ sân bay đó**, không đại diện cho mọi
chuyến bay đến sân bay đó. Trong bảng `route`, JFK → LAX và LAX → JFK là
hai nhóm khác nhau. Giờ của `kpi_hour_overall` lấy từ `CRS_DEP_TIME` trong
nguồn BTS, không phải giờ nạp dữ liệu vào MongoDB.

### 4.2. Bảy collection phân bố độ trễ

Mỗi khóa bên dưới còn kèm **`var, population`** và `snapshot_id`. Các mức
thống kê giống tên collection KPI nhưng lưu phân vị, râu và ngoại lệ.

| Collection | Các chiều chia nhóm ngoài `var, population` | Nội dung | Document bộ mẫu |
|---|---|---|---:|
| `box_day_overall` | `year, month, day` | Phân bố delay của một ngày cụ thể, toàn hệ thống. | 6.204 |
| `box_month_overall` | `year, month` | Phân bố delay của một tháng cụ thể, toàn hệ thống. | 204 |
| `box_month_carrier` | `year, month, carrier` | Phân bố delay của một hãng trong một tháng cụ thể. | 3.084 |
| `box_month_of_year_overall` | `month` | Phân bố delay của một tháng trong năm, gộp các năm. | 48 |
| `box_month_of_year_carrier` | `month, carrier` | Phân bố delay của một hãng trong một tháng trong năm, gộp các năm. | 816 |
| `box_year_overall` | `year` | Phân bố delay của một năm, toàn hệ thống. | 20 |
| `box_year_carrier` | `year, carrier` | Phân bố delay của một hãng trong một năm. | 296 |

Tổng box: **10.672 document**. Cùng một nhóm thời gian/hãng có thể có các
document khác nhau cho delay đến/khởi hành và toàn bộ quan sát/chỉ chuyến trễ.

### 4.3. Hai collection hãng–tuyến bổ sung

| Collection | Một document chứa gì? | Dùng ở đâu? |
|---|---|---|
| `route_carrier_counts` | Số chuyến của một tổ hợp `year, origin, dest, carrier` trong một phiên bản bổ sung. | Phân bố hãng của cặp sân bay trên bản đồ và Top sân bay điểm đến của từng hãng. Bộ mẫu có 63.440 document. |
| `route_carrier_state` | Con trỏ và báo cáo xác minh của bảng bổ sung cho một snapshot M2. | Chọn đúng `data_version` đã kiểm tra để dashboard sử dụng. |

`route_carrier_counts` chỉ chứa số chuyến theo hãng–tuyến, không có đủ các
chỉ số trễ/hủy/box. Thống kê trạng thái chuyến của cặp lấy từ `kpi_year_route`.

### 4.4. Ba collection quản lý hệ thống

| Collection | Một document chứa gì? | Vai trò |
|---|---|---|
| `batch_runs` | Hồ sơ của một snapshot: nguồn, manifest, digest, trạng thái, thời gian và báo cáo kiểm tra. | Truy vết bộ dữ liệu nạp và kết quả công bố. Nạp lại cùng nội dung dùng cùng fingerprint. |
| `serving_state` | Document `_id="historical"` chứa `snapshot_id` đang được phục vụ. | Giữ các biểu đồ của một lượt chạy đọc cùng một bộ dữ liệu đã kiểm tra. |
| `serving_locks` | Khóa loader tạm thời: chủ sở hữu và thời điểm hết hạn. | Ngăn hai loader chính chạy đồng thời; có thể rỗng khi không nạp dữ liệu. |

## 5. Trường định danh và thời gian

| Trường | Kiểu / giá trị | Ý nghĩa |
|---|---|---|
| `_id` | ObjectId hoặc chuỗi, tùy collection | Khóa của MongoDB. Các bảng dữ liệu thường được MongoDB sinh ObjectId; collection trạng thái dùng chuỗi có ý nghĩa riêng. |
| `snapshot_id` | Chuỗi hash | Bộ dữ liệu M2 của document; dùng lọc để không cộng lẫn snapshot. |
| `data_version` | Chuỗi hash | Phiên bản bảng hãng–tuyến, bao gồm ràng buộc với snapshot M2. |
| `year` | Số nguyên | Năm của nhóm dữ liệu. |
| `month` | Số nguyên 1–12 | Tháng; có/không có `year` tùy mức tổng hợp. |
| `day` | Số nguyên ngày trong tháng | Đi cùng `month`; collection ngày cụ thể có thêm `year`. |
| `dep_hour` | Số nguyên 0–23 | Giờ khởi hành theo lịch, ví dụ 8 đại diện khoảng 08:00–08:59. |
| `carrier` | Chuỗi, ví dụ `AA`, `9E`, `OO` | Mã hãng được M2 chuẩn hóa từ cột hãng vận hành trong nguồn. Không tự gộp hãng vùng vào thương hiệu bán vé. |
| `origin` | Chuỗi, ví dụ `JFK` | Sân bay xuất phát. |
| `dest` | Chuỗi, ví dụ `LAX` | Sân bay đích theo lịch. |
| `n_days` | Số nguyên, nếu collection có trường này | Số ngày có dữ liệu trong nhóm, dùng nhận biết mức bao phủ; không mặc định là số ngày lịch trọn kỳ. |

Năm 2026 trong bộ mẫu chỉ có tháng 1–3. Tên đầy đủ của hãng, tên sân bay và
tọa độ được tra từ CSV trong `assets/`; không có collection danh bạ riêng
trong bộ 25 collection này.

## 6. Các trường trong collection KPI

Các collection KPI dùng chung bộ chỉ số dưới đây; các trường định danh có
mặt tùy mức tổng hợp. Số đếm lưu kiểu số nguyên; tổng/giá trị trung bình/tỷ
lệ lưu kiểu số; giá trị thiếu giữ `null`. Tỷ lệ lưu ở thang **0–1**.

### 6.1. Số đếm và tổng cộng được

| Trường | Đơn vị | Nội dung |
|---|---|---|
| `flights` | Chuyến | Tổng bản ghi chuyến sau cleaning trong nhóm, gồm chuyến hủy theo lịch. |
| `cancelled` | Chuyến | Số chuyến hủy. |
| `diverted` | Chuyến | Số chuyến chuyển hướng. |
| `arr_n` | Chuyến | Số chuyến có delay đến hợp lệ sau khi loại chuyến hủy/chuyển hướng khỏi quần thể giờ đến. |
| `on_time` | Chuyến | Delay đến dưới 15 phút, gồm đến sớm và chậm dưới 15 phút. |
| `delayed15` | Chuyến | Delay đến từ 15 phút trở lên. |
| `delayed60` | Chuyến | Delay đến từ 60 phút trở lên; đã nằm trong `delayed15`. |
| `sum_arr_delay` | Phút | Tổng delay đến hợp lệ, giữ cả số âm. |
| `sum_arr_delay_pos` | Phút | Tổng phần delay đến dương; đến sớm đóng góp 0. |
| `sum_arr_delay_late` | Phút | Tổng delay đến của riêng chuyến trễ từ 15 phút trở lên. |
| `dep_n` | Chuyến | Số chuyến có delay khởi hành hợp lệ; không lấy chuyến hủy làm delay 0. |
| `dep_delayed15` | Chuyến | Số chuyến khởi hành trễ từ 15 phút trở lên. |
| `sum_dep_delay_pos` | Phút | Tổng phần delay khởi hành dương. |
| `gain_n` | Chuyến | Số chuyến có cả delay khởi hành và delay đến hợp lệ để tính mức bù giờ. |
| `sum_air_gain` | Phút | Tổng `delay khởi hành - delay đến` trên các chuyến đủ điều kiện; dương là bù được giờ. |

### 6.2. Các tỷ lệ và giá trị trung bình

| Trường | Công thức trong project | Cách hiểu |
|---|---|---|
| `cancel_rate` | `cancelled / flights` | Tỷ lệ hủy trên tổng chuyến theo lịch sau cleaning. |
| `divert_rate` | `diverted / flights` | Tỷ lệ chuyển hướng trên tổng chuyến. |
| `otp_operated` | `on_time / arr_n` | Tỷ lệ đúng giờ trong quần thể đo được giờ đến hợp lệ. |
| `otp_scheduled` | `on_time / flights` | Tỷ lệ đúng giờ trên toàn bộ chuyến theo lịch sau cleaning. |
| `delay15_rate` | `delayed15 / arr_n` | Tỷ lệ đến trễ từ 15 phút trong quần thể giờ đến hợp lệ. |
| `severe60_rate` | `delayed60 / arr_n` | Tỷ lệ đến trễ từ 60 phút trong cùng quần thể. |
| `avg_arr_delay_net` | `sum_arr_delay / arr_n` | Delay đến trung bình, có thể âm do đến sớm bù trừ. |
| `avg_arr_delay_pos` | `sum_arr_delay_pos / arr_n` | Phần delay dương trung bình trên toàn bộ quần thể giờ đến hợp lệ, không chỉ riêng chuyến trễ. |
| `avg_delay_when_late` | `sum_arr_delay_late / delayed15` | Delay đến trung bình của riêng chuyến trễ từ 15 phút. |
| `dep_delay15_rate` | `dep_delayed15 / dep_n` | Tỷ lệ khởi hành trễ từ 15 phút trong quần thể giờ khởi hành hợp lệ. |
| `avg_dep_delay_pos` | `sum_dep_delay_pos / dep_n` | Phần delay khởi hành dương trung bình trên quần thể giờ khởi hành hợp lệ. |
| `avg_air_gain` | `sum_air_gain / gain_n` | Số phút bù được trung bình trên chuyến có đủ hai loại delay. |
| `reliability_score` | Công thức bên dưới | Điểm tự định nghĩa của nhóm, thang 0–100. |

```text
reliability_score = clamp(
  100 × (1 − 0.50 × delay15_rate
           − 0.20 × severe60_rate
           − 0.25 × cancel_rate
           − 0.05 × divert_rate),
  0, 100
)
```

`clamp` giới hạn kết quả trong khoảng 0–100. Công thức hiện dùng 0 cho thành
phần tỷ lệ thiếu khi tính điểm; vẫn cần đọc số mẫu và các tỷ lệ gốc. Đây là
chỉ số của project, không phải chứng nhận/chỉ số xếp hạng chính thức của BTS.

Ví dụ: `delay15_rate=0.2` hiển thị 20%; `avg_arr_delay_net=-5` nghĩa là đến
sớm trung bình 5 phút trong quần thể đang xét. Mẫu số bằng 0 thì tỷ lệ/trung
bình tương ứng là `null`, không tự diễn giải thành 0% hoặc 0 phút.

### 6.3. Số phút trễ theo nguyên nhân

| Trường | Đơn vị | Nội dung |
|---|---|---|
| `cause_carrier` | Phút | Tổng phút trễ được nguồn ghi nhận do hãng. |
| `cause_weather` | Phút | Tổng phút trễ do thời tiết. |
| `cause_nas` | Phút | Tổng phút trễ do NAS/hệ thống không lưu. |
| `cause_security` | Phút | Tổng phút trễ do an ninh. |
| `cause_late_aircraft` | Phút | Tổng phút trễ do máy bay đến muộn từ chặng trước. |
| `cause_total` | Phút | Tổng của năm trường `cause_*` phía trên. |
| `cause_carrier_share` | Tỷ lệ 0–1 | `cause_carrier / cause_total`. |
| `cause_weather_share` | Tỷ lệ 0–1 | `cause_weather / cause_total`. |
| `cause_nas_share` | Tỷ lệ 0–1 | `cause_nas / cause_total`. |
| `cause_security_share` | Tỷ lệ 0–1 | `cause_security / cause_total`. |
| `cause_late_aircraft_share` | Tỷ lệ 0–1 | `cause_late_aircraft / cause_total`. |

Đây là số **phút theo nguyên nhân**, không phải số chuyến. Tổng phút nguyên
nhân không đồng nghĩa `sum_arr_delay`, vì `sum_arr_delay` giữ cả đến sớm và
dùng quần thể khác. Khi `cause_total=0`, các tỷ trọng tương ứng là `null`.

### 6.4. Số chuyến hủy theo nguyên nhân

| Trường | Đơn vị / công thức | Nội dung |
|---|---|---|
| `cancel_a` | Chuyến | Hủy mã A: do hãng. |
| `cancel_b` | Chuyến | Hủy mã B: do thời tiết. |
| `cancel_c` | Chuyến | Hủy mã C: do NAS. |
| `cancel_d` | Chuyến | Hủy mã D: do an ninh. |
| `cancel_share_carrier` | `cancel_a / cancelled` | Tỷ trọng hủy do hãng trong tất cả chuyến hủy. |
| `cancel_share_weather` | `cancel_b / cancelled` | Tỷ trọng hủy do thời tiết. |
| `cancel_share_nas` | `cancel_c / cancelled` | Tỷ trọng hủy do NAS. |
| `cancel_share_security` | `cancel_d / cancelled` | Tỷ trọng hủy do an ninh. |

`cancel_share_*` khác `cancel_rate`: mẫu số lần lượt là số chuyến hủy và
tổng số chuyến. Nguồn thiếu mã hủy có thể làm tổng các nhóm mã nhỏ hơn
`cancelled`; không tự suy ra nguyên nhân cho phần thiếu.

## 7. Các trường trong collection box

### 7.1. Chọn đúng quần thể

| Trường | Giá trị | Ý nghĩa |
|---|---|---|
| `var` | `arr` | Phân bố delay đến. |
| `var` | `dep` | Phân bố delay khởi hành. |
| `population` | `all` | Mọi quan sát có delay hợp lệ của loại đang xét. |
| `population` | `late` | Chỉ quan sát của loại đang xét có delay từ 15 phút trở lên. |

`all` không có nghĩa là điền 0 cho chuyến hủy/thiếu giờ. Ví dụ một document
`box_year_carrier` có `year=2025, carrier=AA, var=arr, population=late` là
phân bố delay đến của các chuyến AA trễ từ 15 phút trong năm 2025.

### 7.2. Bảng các trường thống kê

Ngoài khóa thời gian/hãng, `var`, `population`, `_id`, `snapshot_id`, các
document box có những trường sau. Thống kê được M2 tính từ histogram delay
làm tròn tới phút nguyên, với phân vị theo hạng gần nhất trong mã notebook.

| Trường | Đơn vị / kiểu | Ý nghĩa |
|---|---|---|
| `n` | Số quan sát | Số chuyến có giá trị delay thuộc quần thể đang xét. |
| `min` | Phút | Delay nhỏ nhất. |
| `max` | Phút | Delay lớn nhất. |
| `p05` | Phút | Phân vị 5%. |
| `q1` | Phút | Phân vị 25%; cạnh dưới hộp. |
| `median` | Phút | Phân vị 50%; trung vị. |
| `q3` | Phút | Phân vị 75%; cạnh trên hộp. |
| `p90` | Phút | Phân vị 90%. |
| `p95` | Phút | Phân vị 95%. |
| `p99` | Phút | Phân vị 99%. |
| `mean` | Phút | Trung bình delay của quần thể. |
| `std` | Phút | Độ lệch chuẩn theo công thức quần thể của M2. |
| `iqr` | Phút | `q3 - q1`; độ rộng của 50% quan sát ở giữa. |
| `fence_low` | Phút | Hàng rào dưới Tukey: `q1 - 1.5 × iqr`. |
| `fence_high` | Phút | Hàng rào trên Tukey: `q3 + 1.5 × iqr`. |
| `whisker_low` | Phút | Giá trị quan sát nhỏ nhất còn nằm trong hàng rào dưới. |
| `whisker_high` | Phút | Giá trị quan sát lớn nhất còn nằm trong hàng rào trên. |
| `n_out_low` | Số quan sát | Số giá trị thấp hơn `fence_low`. |
| `n_out_high` | Số quan sát | Số giá trị cao hơn `fence_high`. |
| `out_high_rate` | Tỷ lệ 0–1 | `n_out_high / n`. |
| `reliable` | Boolean | Có đạt ngưỡng mẫu để xem thống kê ổn định hơn hay không; cấu hình M2 hiện tại là `n >= 30`. |

Ví dụ thực tế, chọn một phần trường của `box_month_carrier`:

```json
{
  "year": 2022,
  "month": 1,
  "carrier": "9E",
  "var": "arr",
  "population": "all",
  "n": 20259,
  "q1": -19,
  "median": -10,
  "q3": 3,
  "iqr": 22
}
```

Nghĩa là 20.259 quan sát delay đến hợp lệ của 9E trong tháng 01/2022; trung
vị đến sớm 10 phút. Hai mốc Q1/Q3 giới hạn 50% quan sát ở giữa, không phải
min/max. Ngoại lệ là quan sát xa phân bố theo quy tắc thống kê, chưa tự động
chứng minh đó là lỗi dữ liệu. Box không lưu danh sách từng chuyến ngoại lệ.

## 8. Các trường trong bảng hãng–tuyến

### 8.1. `route_carrier_counts`

| Trường | Kiểu | Nội dung |
|---|---|---|
| `_id` | ObjectId | Mã document do MongoDB sinh. |
| `snapshot_id` | Chuỗi | Snapshot M2 tương ứng. |
| `data_version` | Chuỗi | Phiên bản bổ sung đã được xác minh. |
| `year` | Số nguyên | Năm. |
| `origin` | Chuỗi | Sân bay xuất phát. |
| `dest` | Chuỗi | Sân bay đích theo lịch. |
| `carrier` | Chuỗi | Mã hãng. |
| `flights` | Số nguyên | Số chuyến thuộc đúng tổ hợp năm–hãng–chiều tuyến. |

Khóa duy nhất của bảng bổ sung là `data_version, year, origin, dest, carrier`.
`data_version` được tính kèm ràng buộc snapshot. Dashboard còn lọc rõ
`snapshot_id` và phiên bản được chọn trong `route_carrier_state`.

### 8.2. `route_carrier_state`

| Trường | Kiểu | Nội dung |
|---|---|---|
| `_id` | Chuỗi | Chính là `snapshot_id` của bộ M2 được bổ sung. |
| `status` | Chuỗi | `ready` khi bảng bổ sung đã nạp và đọc lại đối chiếu đạt. |
| `data_version` | Chuỗi | Phiên bản bổ sung dashboard được phép sử dụng. |
| `rows` | Số nguyên | Tổng document của phiên bản bổ sung, bộ mẫu 63.440. |
| `flights` | Số nguyên | Tổng chuyến của bảng bổ sung, bộ mẫu 29.328.846. |
| `verified_routes` | Số nguyên | Số nhóm năm–tuyến được đối chiếu với M2, bộ mẫu 33.373. |
| `verified_at` | BSON Date | Thời điểm hoàn tất xác minh. |
| `source` | Object | Manifest nguồn của bảng bổ sung. |

Các trường trong `source` của bộ bổ sung hiện tại:

| Trường | Nội dung |
|---|---|
| `format_version`, `kind` | Phiên bản định dạng và loại `route_carrier_supplement`. |
| `rows`, `flights` | Số document và tổng chuyến nguồn. |
| `file`, `sha256` | Tên file JSONL và hash kiểm tra file. |
| `base_route_file_sha256` | Hash file tuyến M2 dùng đối chiếu khi tạo bảng bổ sung. |
| `coverage` | Danh sách tháng thuộc bộ dữ liệu. |
| `processed_source` | Đường dẫn cleaned Parquet dùng tính bảng bổ sung. |
| `exported_at_utc` | Thời điểm xuất nguồn, dạng chuỗi UTC. |
| `reconciled_year_routes` | Số nhóm năm–tuyến đã so khớp lúc xuất. |
| `reconciled_year_carrier_origins` | Số nhóm năm–hãng–sân bay xuất phát đã so khớp lúc xuất. |

## 9. Các trường quản lý nạp và công bố dữ liệu

### 9.1. `batch_runs`

| Trường | Nội dung |
|---|---|
| `_id` | Fingerprint/snapshot_id của bộ dữ liệu M2. |
| `status` | `loading`, `published` hoặc `failed`, tùy giai đoạn. |
| `manifest` | Mô tả bộ nguồn: schema, bảng, khóa, số dòng, coverage và nguồn xuất. |
| `digests` | Kết quả kiểm tra nội dung từng bảng: hash, số bản ghi; bảng tháng tổng có thêm tổng chuyến và danh sách tháng. |
| `source` | Nguồn nạp, thường có `format`, `path`; adapter HDFS có thể bổ sung thông tin nguồn. |
| `started_at` | Thời điểm bắt đầu nạp, BSON Date. |
| `verified_at` | Thời điểm xác minh thành công, nếu có. |
| `report` | Báo cáo so khớp MongoDB với nguồn, có khi công bố thành công. |
| `previous_snapshot_id` | Snapshot đang phục vụ trước lúc công bố bộ này; có thể là `null` ở lần đầu. |
| `activation_pending` | Có đang còn bước hoàn tất chuyển con trỏ hay không; giúp phục hồi khi tiến trình gián đoạn ở bước công bố. |
| `error`, `failed_at` | Lý do và thời điểm thất bại, chỉ có khi lần nạp tương ứng gặp lỗi. |

Các object lồng nhau thường thấy:

| Đường dẫn trường | Nội dung |
|---|---|
| `manifest.format_version`, `manifest.source`, `manifest.exported_at_utc` | Định dạng, mô tả nguồn và thời điểm export nếu nguồn có ghi. |
| `manifest.analytics_root` | Thư mục analytics nguồn, nếu manifest có trường này. |
| `manifest.coverage.months`, `month_count`, `total_flights` | Danh sách tháng, số tháng và tổng chuyến của snapshot. |
| `manifest.coverage.matches_project_period_2022_01_to_2026_03` | Cờ kiểm tra phạm vi dự án. |
| `manifest.tables[]` | Mỗi phần tử mô tả một bảng: `group`, `name`, `keys`, `rows`, `suggested_collection`, `jsonl`, `spark_schema`; có thể thêm `csv`, `source_path`. |
| `manifest.tables[].spark_schema.fields[]` | Mỗi trường có `name`, `type`, `nullable`, `metadata`. |
| `digests.<collection>.rows`, `sha256` | Số bản ghi và fingerprint nội dung của bảng đó; kèm `total_flights`, `months` theo cách tính của verifier. |
| `report.result`, `snapshot_id`, `checked_at` | Kết quả, bộ dữ liệu và thời điểm kiểm tra trong báo cáo. |
| `report.total_documents`, `coverage`, `tables[]` | Tổng document 20 bảng, coverage và các kết quả đối chiếu từng bảng. |

Các tên ngắn trong một hàng vẫn thuộc object ở đầu hàng: ví dụ
`month_count` ở hàng coverage là `manifest.coverage.month_count`.
Không phải mọi trường trạng thái đều tồn tại ngay từ khi bắt đầu nạp.

### 9.2. `serving_state`

| Trường | Nội dung |
|---|---|
| `_id` | `historical`, định danh trạng thái phục vụ lịch sử. |
| `snapshot_id` | Snapshot đã công bố mà dashboard phải truy vấn. |
| `activated_at` | Thời điểm chuyển con trỏ, BSON Date. |

Khi nạp B mới, dashboard vẫn dùng A đã công bố. B chỉ được chọn sau khi
kiểm tra đạt; lượt làm mới tiếp theo của dashboard đọc con trỏ B. Nếu B
thất bại, A vẫn được phục vụ. Bộ cũ không tự bị xóa. Lần đầu chưa có A,
dashboard báo chưa có snapshot đến khi bộ đầu tiên công bố thành công.

### 9.3. `serving_locks`

| Trường | Nội dung |
|---|---|
| `_id` | `batch_loader`, tên khóa của loader chính. |
| `owner` | Mã ngẫu nhiên của tiến trình đang giữ khóa. |
| `expires_at` | Thời điểm hết hạn lease, BSON Date; hiện gia hạn theo khoảng 10 phút trong code. |

Loader gia hạn khóa trong lúc nạp/kiểm tra và xóa khóa của chính nó khi kết
thúc. Không có document trong collection này khi loader đã xong là bình thường.

## 10. Ví dụ đọc dữ liệu và liên hệ dashboard

### 10.1. Cùng là tháng 1 nhưng hai ý nghĩa khác nhau

| Collection và điều kiện | Cách đọc |
|---|---|
| `kpi_month_overall`, `year=2025, month=1` | Chỉ tháng 01/2025. |
| `kpi_month_of_year_overall`, `month=1` | Gộp các tháng 1 trong những năm có dữ liệu của snapshot. |
| `kpi_day_overall`, `year=2025, month=1, day=1` | Chỉ ngày 01/01/2025. |
| `kpi_calendar_day_overall`, `month=1, day=1` | Gộp các ngày 01/01 trong snapshot. |

Không lọc `year` lên collection đã gộp mất chiều năm để suy ra một năm riêng.
Để xem dữ liệu đúng năm, chọn collection có trường/khóa năm phù hợp.

### 10.2. Bấm ALS ↔ DEN trên bản đồ thì dữ liệu từ đâu?

Với toàn bộ giai đoạn của bộ mẫu, cặp ALS ↔ DEN có **521 chuyến**:

| Thông tin hiển thị | Nguồn và phép tính |
|---|---|
| ALS → DEN: 261 chuyến | `kpi_year_route`, lọc `origin=ALS, dest=DEN`, gộp các năm đang chọn. |
| DEN → ALS: 260 chuyến | Cùng bảng nhưng đổi chiều. |
| Tổng hai chiều: 521 | Cộng hai chiều một lần; số này điều khiển độ dày/màu đường của bản đồ kết nối sân bay. |
| Đúng giờ/trễ dưới 15 phút: 424 | Cộng `on_time` của các dòng KPI tuyến được chọn. |
| Trễ từ 15 phút: 51 | Cộng `delayed15`. |
| Hủy: 46 | Cộng `cancelled`. |
| Chuyển hướng: 0 | Cộng `diverted`. |
| Hãng OO: 521 chuyến | `route_carrier_counts`, lọc snapshot + phiên bản + đúng cặp/chiều/năm, group theo `carrier`. |

Các số 424 + 51 + 46 + 0 bằng 521. Với cặp khác có thể còn nhóm thiếu giờ
đến hợp lệ; phải giữ nhóm đó khi vẽ cơ cấu. Không cộng `delayed60` thêm vào
`delayed15` vì sẽ đếm trùng. Đây là số chuyến, không phải số hành khách.

### 10.3. Gộp KPI đúng cách

Ví dụ minh họa: nhóm 1 có 10 chuyến trễ/100 chuyến đến hợp lệ (10%), nhóm 2
có 9/10 (90%). Tỷ lệ chung là **19/110 ≈ 17,27%**, không phải (10%+90%)/2.
Khi gộp, cộng các số đếm/tổng rồi tính lại tỷ lệ. Không cộng hoặc lấy trung
bình trực tiếp các median/Q1/Q3 để tạo box mới; M2 dùng histogram để tính
đúng phân vị ở từng mức.

## 11. Lỗi thường gặp và những cách hiểu cần tránh

| Tình huống | Kiểm tra / cách hiểu |
|---|---|
| Compass không kết nối được | Mở Docker Desktop, kiểm tra `docker compose ps`, service `mongo` và cổng publish. |
| Kết nối được nhưng không thấy `aero_m5` | Kiểm tra URI/cổng và `M5_DATABASE`; có thể đang kết nối MongoDB khác hoặc chưa nạp M2. |
| Không có document `serving_state` với `_id=historical` | Chưa có snapshot công bố; xem log nạp và chạy theo hướng dẫn chính. |
| Query không ra kết quả | Kiểm tra đúng collection, snapshot, kiểu số/chuỗi, phạm vi năm; với box còn có `var`, `population`. |
| Một nhóm xuất hiện nhiều document | Có thể khác snapshot, chiều tuyến, `var`, `population` hoặc phiên bản; kiểm tra đủ khóa trước khi kết luận trùng. |
| Count trong Compass lớn hơn số mẫu | Count cả collection có thể gồm nhiều snapshot/phiên bản. Dùng bộ lọc hoặc `countDocuments` với đúng mã đang phục vụ. |
| `serving_locks` rỗng | Bình thường khi loader chính không hoạt động. |
| Chưa có hai collection hãng–tuyến | Nạp bảng bổ sung theo mục 7.4 của hướng dẫn chính; 20 bảng M2 vẫn tồn tại độc lập. |
| Thấy `null` hoặc số delay âm | `null` là thiếu/không có mẫu số; số âm có thể là đến sớm, không tự đổi thành 0. |
| Tưởng tổng mọi collection là số chuyến | KPI/box là nhiều cách tổng hợp cùng dữ liệu; cộng tất cả sẽ đếm lặp. |
| Tưởng MongoDB lưu từng chuyến bay thô | Luồng lịch sử M5 này lưu aggregate từ M2; dữ liệu raw/cleaned từng chuyến ở HDFS. |
| Chỉ clone GitHub rồi mở Compass chưa có dữ liệu | Export gửi ngoài Git; cần nhận/nạp snapshot M2 và bảng bổ sung. |

## 12. Căn cứ và tài liệu tham khảo

- [Hướng dẫn M5 từ đầu đến dashboard](HUONG_DAN_CHAY_TU_DAU_DEN_OUTPUT_M5.md).
- [Catalog, khóa và schema M2](../m5/contracts.py).
- [Công thức tổng hợp KPI](../m5/metrics.py).
- [Loader, index, khóa nạp và công bố snapshot](../m5/batch_writer.py).
- [Bảng hãng–tuyến và chọn phiên bản](../m5/route_carriers.py).
- [Nguồn tính KPI/box của M2](../../batch-layer/spark_jobs/eda_lite.ipynb).
- [Cấu hình MongoDB/Docker của project](../compose.yml).
- [MongoDB: cài Compass](https://www.mongodb.com/docs/compass/install/),
  [kết nối Compass](https://www.mongodb.com/docs/compass/connect/),
  [lọc document trong Compass](https://www.mongodb.com/docs/compass/query/filter/).

Các mốc dữ liệu minh họa được kiểm tra theo bộ mẫu của project; khi thay
snapshot, lấy manifest và trạng thái đang công bố làm căn cứ cho số lượng.
