# Dùng AI

| # | Ai dùng | Công cụ | Prompt (tóm tắt) | AI sai ở đâu | Nhóm kiểm lại thế nào |
|---|---|---|---|---|---|
| 1 | Nguyễn Đăng Khoa | Codex | Hướng dẫn các công đoạn theo phần việc đã ghi trong TEAM.md. | AI dùng thông tin cũ và hướng dẫn nhầm phần validator lỗi luật. | Khoa nhắc đọc lại TEAM.md. AI đã đọc lại và sửa hướng dẫn sang đối chiếu detection và panoptic. |
| 2 | Nguyễn Đăng Khoa | Codex | “Được, bạn hỗ trợ viết mã , và ghi promp”. Viết phần đối chiếu detection–panoptic và công cụ review theo phần việc của Khoa. | Điều kiện nghi ngờ instance_merge ban đầu quá rộng, tạo 179 ứng viên loại này trên lô 4007. AI đã bổ sung điều kiện phủ segment và loại trường hợp một box phủ gần toàn bộ segment. Ngưỡng hiện vẫn cần nhóm kiểm chứng bằng ảnh. | AI chạy kiểm tra tổng hợp cho các trường hợp sạch, khác lớp, box lệch, thiếu box và gộp segment. Chạy thật trên seed 4007 được 10 ứng viên thuộc 9 ảnh, 1 cảnh báo nhãn không hợp lệ. Lô sạch seed 5 có 50 ảnh, 0 ứng viên và 0 cảnh báo. Trang review đã được tạo và kiểm tra cú pháp JavaScript. Thành viên nhóm chưa xác nhận review ảnh hoặc F1. |

## Mã được AI hỗ trợ trong yêu cầu 2

### Hiệu chỉnh sau review của nhóm

Khoa báo Lượng đã có `validator/validate.py`. AI kiểm tra thấy file có kiểm lỗi luật và thuật toán sinh ứng viên riêng, nhưng dùng định dạng `image/reasons` khác với công cụ review ban đầu. AI bổ sung bộ chuyển đổi trong `review_candidates.py` để đọc cả hai định dạng, giữ tham chiếu box theo dòng nhãn gốc và chạy kiểm tra trên đầu ra riêng tại `runs/r4007/integration_check/`. Nhóm cần kiểm tra các ứng viên mới trước khi dùng kết quả thuật toán mới để chốt bài.

Khoa xác nhận đã dùng confirmed để duyệt nhãn đúng trong file `D:/review_log.csv`. AI đã đảo hai giá trị verdict trong bản `runs/r4007/review_log.csv` dựa trên CSV gốc, giữ nguyên ghi chú và loại lỗi. Trang review được bổ sung diễn giải tiếng Việt cho hai lựa chọn. Nhóm cần kiểm tra lại loại lỗi ở các dòng có ghi chú chưa đủ rõ trước khi gộp errors.json. Việc đảo verdict dựa trên giải thích của người review, chưa xác minh lại nội dung ảnh.

- `validator/cross_check.py` đọc dữ liệu trong delivery, ghép box–segment và xuất ứng viên cần người kiểm tra.
- `validator/review_candidates.py` tạo trang HTML offline để xem box/mask và nhập kết luận review.
- Ngưỡng khởi đầu do AI chọn là match IoU 0.3, tỷ lệ pixel segment trong box 0.8, diện tích segment tối thiểu bằng giá trị lớn hơn giữa 100 pixel và 0.1% diện tích ảnh.
- Điều kiện nghi gộp dùng hai box cùng lớp có IoU dưới 0.2, mỗi box chứa 20–85% pixel segment, tổng tỷ lệ ít nhất 80%, và không có box nào chứa trên 90% pixel segment. Tổng hai tỷ lệ có thể chứa pixel giao nhau, nên đây là tín hiệu ứng viên cần xem ảnh.
- Số ứng viên không phải số lỗi đã xác nhận. Kết quả trên lô sạch chưa chứng minh khả năng bắt đủ lỗi.
- Chưa tích hợp vào `validator/validate.py` của người phụ trách lỗi luật. Chưa kiểm tra tương tác trang review bằng trình duyệt.
- Nhóm cần trực tiếp xem ảnh, ghi người review và bằng chứng, kiểm tra các trường hợp bị bỏ sót, và bổ sung kết quả đánh giá vào báo cáo.
