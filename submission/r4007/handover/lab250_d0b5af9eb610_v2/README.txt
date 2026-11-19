Release: lab250_d0b5af9eb610_v2
Parent: lab250_d0b5af9eb610
Số ảnh: 243
Số nhãn: 1696
Guideline: v1.2 (J01-J04), v1.3 (J05-J10)
QC v1: 15/250 = 6,0%
Kết luận v1: Hold — 15/250 = 6,0% vượt ngưỡng 2%, không được train/phát hành
Kết luận v2: Release — tách 7 ảnh lỗi nhãn detection/thiếu file sang rework_queue; sửa hash, guideline, split; còn 243 ảnh nhãn detection giữ nguyên như v1
Ghi chú: (1) Hash: 000000009772, 000000019042 — đã mở ảnh kiểm, ảnh còn nguyên nên chỉ manifest v1 ghi sai; manifest.csv v2 tính lại sha256 trên bytes thật. (2) Guideline: 000000016502, 000000017899 — metadata ảnh ghi sai phiên bản; truyvet.csv lấy guideline theo job trong jobs.csv. (3) Split: scene_933 về train (chuyển 000000013004) — đưa cả cảnh về một split (đa số) để không rò train/val. (4) Rework giao lại đúng người gán/kiểm theo jobs.csv: A01/Q03: 2 ảnh; A04/Q01: 2 ảnh; A04/Q02: 3 ảnh. (5) Lỗi chỉ ở panoptic, nhãn detection vẫn đúng nên ảnh ở lại v2, báo team panoptic: 000000002153 (instance_merge); 000000002685 (thing_overlap); 000000005600 (invalid_category_id). (6) Nhãn trong v2 không sửa tay; v1 (lab250_d0b5af9eb610) giữ nguyên.
