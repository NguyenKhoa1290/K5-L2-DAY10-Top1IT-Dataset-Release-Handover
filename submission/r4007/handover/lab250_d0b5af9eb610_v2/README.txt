Release: lab250_d0b5af9eb610_v2
Parent: lab250_d0b5af9eb610
Số ảnh: 243
Số nhãn: 1696
Guideline: v1.2 (J01, J02, J03, J04), v1.3 (J05, J06, J07, J08, J09, J10)
QC v1: 15/250 = 6,0%
Kết luận v1: Hold vì tỷ lệ lỗi vượt ngưỡng 2%.
Kết luận v2: Release lô detection sau khi tách 7 ảnh cần làm lại và xử lý các lỗi bàn giao đã ghi nhận.
Ghi chú: Đã mở kiểm ảnh 000000009772, 000000019042 và xác nhận byte khớp ảnh COCO đã tải. Manifest v2 ghi SHA-256 thực tế. Đồng bộ guideline theo job cho 000000016502, 000000017899. Chốt split theo đa số ảnh trong cảnh: scene_933 -> train. Giao ảnh làm lại cho annotator và reviewer ghi trong rework_queue.csv. Giữ ảnh chỉ lỗi panoptic trong v2 và báo đội panoptic: 000000002153 (instance_merge), 000000005600 (invalid_category_id), 000000002685 (thing_overlap).
