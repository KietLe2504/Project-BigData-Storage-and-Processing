# MongoDB collections, indexes và queries

Database mặc định `aero_m5`. Dữ liệu lịch sử giữ nguyên các trường M2 và thêm
`snapshot_id`. Giữ số, boolean và null từ JSONL; không tự đổi tỷ lệ thành phần
trăm trong storage.

- 13 collection `kpi_<table>` và 7 collection `box_<table>` theo manifest.
- Unique index `snapshot_business_key`: `snapshot_id` + toàn bộ `keys` trong
  manifest. Khóa box luôn gồm cả `var` và `population`.
- Index filter thêm cho carrier/origin/dest; giải thích hiệu năng cần dựa
  trên `explain` và workload thực tế, không tuyên bố mọi sort đều dùng index.
- `batch_runs`: manifest, digests, provenance, trạng thái, report và thời gian.
- `serving_state`: document `_id=historical` trỏ snapshot active.
- `serving_locks`: lease loader 10 phút, được gia hạn theo lô/bảng.
- `stream_window_kpi`: full aggregate của M4 sau khi nối contract.

Loader kiểm tra toàn bộ nguồn trước khi ghi, ghi theo lô 1.000 thao tác upsert,
đọc lại toàn bộ dữ liệu để so digest rồi công bố con trỏ active. Snapshot đã
công bố không sửa tại chỗ. Các lần nạp cùng nội dung dùng chung fingerprint;
quá trình thất bại có thể retry. Không tự xóa snapshot cũ.

Dashboard lấy con trỏ một lần cho lượt chạy và luôn lọc snapshot đó. Snapshot
mới không kế thừa document cũ bị loại khỏi nguồn. Nạp lại snapshot cũ đã công
bố không tự chuyển con trỏ về quá khứ.

Đọc MongoDB shell từ PowerShell:

```powershell
docker compose exec mongo mongosh aero_m5
```

**Các lệnh dưới chạy trong `mongosh`, không dán vào PowerShell:**

```javascript
const sid = db.serving_state.findOne({_id: "historical"}).snapshot_id;
db.kpi_month_overall.find({snapshot_id: sid, year: 2026}, {_id: 0}).sort({month: 1});
db.kpi_year_route.find({snapshot_id: sid, year: 2025, origin: "JFK"}, {_id: 0}).limit(10);
db.box_year_carrier.find({snapshot_id: sid, year: 2025, var: "arr", population: "late"}, {_id: 0});
db.kpi_month_overall.getIndexes();
db.kpi_month_overall.find({snapshot_id: sid, year: 2025}).explain("executionStats");
exit
```

Tên/mã hãng, sân bay là các giá trị thực trong BTS. Query ví dụ có thể không
có dòng nếu snapshot khác phạm vi. Dữ liệu lịch sử chỉ gộp từ một bảng đúng
mức, không cộng cùng lúc các bảng overall/carrier/origin để tránh đếm lặp.

Verifier mặc định so sánh chính xác digest scalar JSON đã lưu ở ingest, không
dùng float tolerance ngầm. Chuỗi/số/bool/null và schema phải được giữ nguyên.
Đối chiếu này chứng minh tính toàn vẹn của serving; công thức và chất lượng
upstream vẫn thuộc kiểm chứng M2.
