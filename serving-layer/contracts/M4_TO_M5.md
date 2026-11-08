# Contract đề xuất M4 → M5 (v1)

Trạng thái: **đã có writer M5 và kiểm thử; chưa xác nhận tương thích output M4**.
Chỉ nghiệm thu integration sau khi M4 chấp nhận contract hoặc adapter được sửa
theo output thật. Không tự gửi fixture vào database phục vụ dashboard.

Writer `m5.stream_writer.write_window(db, record)` nhận **aggregate đầy đủ của
một cửa sổ**, không phải delta. Một record JSON có đúng các trường:

```json
{
  "pipeline_id": "m4-flight-status-v1",
  "source": "simulated",
  "window_start": "2026-11-07T00:00:00Z",
  "window_end": "2026-11-07T00:05:00Z",
  "revision": 1,
  "dimensions": {"carrier": "AA", "origin": "JFK"},
  "metrics": {"flights": 100, "arr_n": 90, "on_time": 70, "delayed15": 20, "cancelled": 10}
}
```

- `source`: `aviationstack` hoặc `simulated`; phải phản ánh nguồn thực tế.
- Window chứa timezone, được chuẩn hóa UTC, start < end. M4 quyết định event
  time và watermark; M5 không tự gán ingestion time làm event time.
- `dimensions`: object gồm các chiều `carrier`, `origin`, `dest` thực có;
  `{}` dành cho overall. Không gộp các mức khác nhau rồi cộng trùng.
- `metrics`: bắt buộc `flights`; các trường thêm được chấp nhận là `cancelled`,
  `diverted`, `arr_n`, `on_time`, `delayed15`, `delayed60`, `sum_arr_delay`.
  Counts là integer không âm. Đơn vị delay là phút.
- Khóa logic: source + pipeline_id + window_start + window_end + toàn bộ
  dimensions. Writer tạo `_id` xác định từ tổ hợp đó.
- `revision`: integer không âm, **tăng bền vững cho cùng khóa qua cả restart**.
  M4 phải cam kết cách phát sinh revision. Không lấy batch_id của checkpoint
  mới thay cho version cũ khi counter có thể quay về 0.
- Replay cùng revision/payload được bỏ qua; revision cũ bị bỏ qua; cùng
  revision nhưng payload khác báo lỗi. Revision mới thay toàn bộ giá trị.
- Thời gian `ingested_at` là lúc M5 thật sự nhận một bản cập nhật mới, replay
  không làm dữ liệu trông mới hơn. Dashboard refresh 10 giây, đánh dấu stale
  sau 60 giây; cần điều chỉnh theo trigger thực tế khi tích hợp.
- Không có tuyên bố exactly-once end-to-end. M4 giữ checkpoint và retry;
  M5 cung cấp upsert/version guards. Chỉ tăng đếm bằng delta sau khi thiết kế
  ledger/dedup riêng và có test delivery semantics.

M4 có thể gọi writer trong sink `foreachBatch` sau khi chuyển aggregate sang
kiểu Python tương ứng; hoặc bàn giao JSONL đã commit để chạy CLI:

```text
python -m m5.stream_writer --input /data/m4/windows.jsonl
```

Đây là lệnh trong môi trường Python/container có package `m5`, không phải
đoạn Python để dán vào PowerShell. Cần thống nhất thêm kênh ghi, nhịp trigger,
late updates, provenance và test M3 → M4 → MongoDB → dashboard.
