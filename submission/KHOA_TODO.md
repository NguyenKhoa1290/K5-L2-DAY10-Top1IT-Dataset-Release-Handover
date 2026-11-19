# Công việc của Nguyễn Đăng Khoa — Bản nháp

- Nhóm Top1IT
- Phần phụ trách là đối chiếu detection và panoptic.
- Seed luyện tập là `4007`.
- Dữ liệu đầu vào nằm tại `runs/r4007/delivery/`.
- Tài liệu chính là [GUIDE.md — Pha 2](../GUIDE.md#pha-2--đối-chiếu-detection--panoptic-xem-ảnh-55-phút) và [DELIVERY.md](../docs/DELIVERY.md).

## 1. Thống nhất với nhóm

- [ ] Thống nhất với Lê Đức Lượng cách tích hợp phần đối chiếu vào `validator/validate.py`, tránh sửa chồng cùng đoạn mã.
- [ ] Giữ giao diện validator theo đề, có tùy chọn `--candidates` để xuất ứng viên.
- [ ] Thống nhất cấu trúc `candidates.json`, gồm ảnh, loại lỗi nghi ngờ, lý do và box/segment liên quan để hỗ trợ review. Đây là cấu trúc nhóm cần thống nhất.
- [ ] Thống nhất với Phạm Văn Hùng cách bàn giao ứng viên và nhật ký review để tổng hợp bài nộp.

## 2. Đọc và quy đổi nhãn

- [ ] Đọc `classes.txt` và nhãn YOLO trong `labels/`.
- [ ] Đọc kích thước ảnh, categories và segments từ `panoptic.json`.
- [ ] Đọc mask trong `masks/`, có thể dùng hàm của `scripts/pngutil.py`.
- [ ] Đổi box YOLO sang tọa độ pixel theo kích thước ảnh.
- [ ] Ghép lớp detection với panoptic qua tên lớp. Detection dùng ID 0–79, panoptic dùng category ID gốc COCO.
- [ ] Kiểm tra trực quan một ảnh để xác nhận box và mask nằm đúng vị trí.

## 3. Ghép box với segment và sinh ứng viên

- [ ] Ghép box detection với segment `thing` dựa trên vị trí, lớp và IoU.
- [ ] Xử lý segment `iscrowd` để giảm ứng viên do crowd.
- [ ] Kết hợp pixel mask, đặc biệt tỷ lệ pixel segment nằm trong box.
- [ ] Tìm ứng viên `class_swap` hoặc `category_swap` khi hai nguồn trùng vị trí nhưng khác lớp. Kết luận nguồn sai sau khi xem ảnh.
- [ ] Tìm ứng viên `bbox_drift` khi box lệch khỏi segment cùng lớp.
- [ ] Tìm ứng viên `missing_box` khi segment vật thể đáng kể chưa có box tương ứng.
- [ ] Tìm ứng viên `instance_merge` khi một segment phủ nhiều box cùng lớp.
- [ ] Xuất `runs/r4007/candidates.json` với thông tin đủ để mở lại và kiểm tra từng trường hợp.

## 4. Đo trên lô sạch và chọn ngưỡng

- [ ] Tạo lô sạch bằng lệnh dưới đây nếu nhóm chưa tạo.

```powershell
$env:PYTHONUTF8='1'
py scripts/inject_release.py --seed 5 --no-faults --out runs/clean
```

- [ ] Chạy phần đối chiếu trên `runs/clean/delivery/` và ghi số ứng viên.
- [ ] Chạy trên lô `4007`, ghi số ứng viên và số ảnh cần xem.
- [ ] Điều chỉnh ngưỡng dựa trên tín hiệu của hai nguồn và khả năng review của nhóm.
- [ ] Ghi ngưỡng, lý do chọn và số ứng viên vào `submission/REPORT.md`.

Lô sạch có thể có ứng viên do detection và panoptic của COCO lệch nhau tự nhiên. Cần xem ảnh để phân biệt với lỗi gán nhãn.

## 5. Chuẩn bị công cụ review

- [ ] Hiển thị ảnh với box detection, tên lớp và segment panoptic.
- [ ] Hỗ trợ phóng to hoặc cắt vùng quanh vật thể để xem ảnh nhỏ.
- [ ] Hiển thị lý do một trường hợp được đưa vào hàng đợi.
- [ ] Kiểm tra công cụ sử dụng được với tên ảnh bất kỳ để chuẩn bị đề ẩn.

Công cụ xem ảnh được dùng Pillow. Phần validator chỉ dùng thư viện chuẩn và có thể import hàm đọc PNG từ `scripts/pngutil.py`.

## 6. Review cùng nhóm và chốt lỗi

- [ ] Chia hàng đợi ứng viên cho cả bốn thành viên.
- [ ] Mỗi người mở ảnh mình phụ trách và ghi `review_log.csv` theo mẫu `templates/review_log.csv`.
- [ ] Mỗi dòng có `image,type,verdict,note`, với verdict là `confirmed` hoặc `rejected`.
- [ ] Ghi rõ người xem và quan sát thực tế trong note. Ghi chú cần cụ thể, ít nhất 20 ký tự và tránh sao chép giống nhau.
- [ ] Với bất đồng lớp, dùng hình ảnh để xác định detection sai hay panoptic sai.
- [ ] Bảo đảm mọi lỗi gán nhãn đưa vào `errors.json` đều có dòng `confirmed` tương ứng.
- [ ] Bàn giao nhật ký review cho người tích hợp để gộp với lỗi luật bằng `scripts/merge_review.py`.

Kết luận review phải do thành viên nhóm xem ảnh. Ghi việc sử dụng AI, chỗ AI sai và cách kiểm lại vào `submission/prompts.md` theo `RULES.md`.

## 7. Sản phẩm cần bàn giao

- [ ] Mã đối chiếu đã tích hợp với validator và hỗ trợ `--candidates`.
- [ ] Công cụ hiển thị ảnh để review.
- [ ] `runs/r4007/candidates.json`.
- [ ] Các dòng review được giao trong `runs/r4007/review_log.csv`.
- [ ] Số liệu ứng viên trên lô sạch và lô luyện tập, ngưỡng cùng lý do chọn cho `REPORT.md`.
- [ ] Ghi chép dùng AI trong `prompts.md`.
- [ ] Ít nhất hai commit có nội dung, mang tên và email của mình.
- [ ] Có thể giải thích cách ghép box–segment và một kết luận review khi vấn đáp.

## Quy tắc cần tuân thủ

- Validator chỉ đọc thư mục `delivery/` được truyền vào, dùng thư viện chuẩn và không dùng mạng.
- Giữ nguyên dữ liệu trong `delivery/`.
- Không đọc `_private/`, dùng annotation gốc hay dò đáp án qua biến động điểm.
- Dùng `score_findings.py` để đo kết quả tổng thể theo quy định của lab.
- Không commit `runs/`, `data_source/`, file ZIP hoặc secret. Người tích hợp xuất bài làm sang `submission/` bằng script được cung cấp.

## Thứ tự bắt đầu

1. Thống nhất giao diện với Lượng.
2. Hiển thị đúng box và mask của một ảnh.
3. Viết phần ghép và sinh ứng viên.
4. Đo trên lô sạch, điều chỉnh ngưỡng.
5. Chia nhóm review và bàn giao kết quả.

Nguồn yêu cầu là [GUIDE.md](../GUIDE.md), [RULES.md](../RULES.md), [SUBMISSION.md](../SUBMISSION.md) và [scripts/README.md](../scripts/README.md). File này là checklist nháp, cập nhật theo tiến độ thực tế của nhóm.
