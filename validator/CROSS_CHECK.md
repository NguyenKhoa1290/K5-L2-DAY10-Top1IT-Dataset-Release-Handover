# Đối chiếu detection và panoptic

Chạy từ thư mục gốc, Python 3.10+, thư viện chuẩn.

```powershell
py -X utf8 validator/cross_check.py runs/r4007/delivery --candidates runs/r4007/candidates.json
py -X utf8 validator/review_candidates.py runs/r4007/delivery --candidates runs/r4007/candidates.json --out runs/r4007/review.html
```

Mở `runs/r4007/review.html` bằng trình duyệt. Chọn ứng viên, bật/tắt mask, xem tất cả box hoặc phóng to. Người xem nhập tên, loại lỗi, kết luận và bằng chứng rồi bấm lưu dòng. Xuất CSV trước khi đóng tab. Người tích hợp gộp các CSV của thành viên, xử lý trùng và bất đồng trước khi dùng `merge_review.py`.

Trang chứa ảnh và mask để xem offline. Thiếu ảnh thì trang hiển thị cảnh báo. Công cụ không tự tạo kết luận confirmed/rejected.

## Tích hợp với phần lỗi luật

Người phụ trách `validate.py` có thể gọi hàm sau rồi ghi kết quả dạng JSON vào đường dẫn nhận từ `--candidates`.

```python
from validator.cross_check import find_candidates

result = find_candidates(delivery_path)
```

Nếu chạy trực tiếp `python validator/validate.py`, dùng `from cross_check import find_candidates` vì thư mục validator nằm trên đường tìm module.

Kết quả có `parameters`, `candidates` và `warnings`. Mỗi ứng viên có `target`, `possible_types`, `reason`, `boxes`, `segments`. Khác lớp có hai khả năng class_swap/category_swap, người review quyết định nguồn sai. Một ảnh có thể có nhiều ứng viên và cần hợp nhất kết luận khi chốt errors.json.

## Cách hoạt động và giới hạn

Ghép tham lam một-một theo IoU giảm dần, giữ các cặp khác lớp. Đếm pixel segment trong mỗi box để tìm box lệch hoặc segment gộp. Bỏ segment stuff, crowd và segment không có pixel. Các segment nhỏ được loại khỏi kiểm tra thiếu box/gộp để giảm nhiễu. Nhãn lỗi cú pháp, class hoặc kích thước được cảnh báo và bỏ qua trong phần đối chiếu để phần luật xử lý.

Các ngưỡng dòng lệnh gồm `--match-iou`, `--min-coverage`, `--min-area`, `--min-area-ratio`. Giá trị mặc định là ngưỡng khởi đầu. Ghép tham lam có thể ghép nhầm khi nhiều vật chồng nhau. Box lệch mạnh, vật nhỏ hoặc các cặp có IoU thấp có thể bị bỏ sót. Ứng viên thiếu box có thể xuất hiện do một dòng nhãn bị lỗi luật. Cần xem ảnh và phối hợp với kết quả lỗi luật trước khi chốt.

Kiểm tra ban đầu có 10 ứng viên thuộc 9 ảnh trên seed 4007, một cảnh báo nhãn. Lô sạch 50 ảnh seed 5 có 0 ứng viên. Chưa đo F1 hoặc xác nhận lỗi bằng mắt. Các kiểm tra tổng hợp đã chạy qua trường hợp sạch, đổi lớp, lệch box, thiếu box và segment gộp. JavaScript của trang xuất đã qua kiểm tra cú pháp, tương tác trình duyệt chưa được kiểm tra.
