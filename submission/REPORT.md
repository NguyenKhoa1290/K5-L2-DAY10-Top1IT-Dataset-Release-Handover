# Báo cáo nhóm <NHOMTop1IT>

## 1. Số liệu luyện tập
- Seed 4007 có F1 lỗi luật ≈ 1.0, F1 đối chiếu và review ≈ 0.4,
  F1 tổng ≈ 0.8. Số liệu được lấy từ score_findings.py, làm tròn một chữ số.
- Lô sạch gồm 50 ảnh có 0 ứng viên. Lô luyện tập có 10 ứng viên
  thuộc 9 ảnh. Sau review, nhóm xác nhận 4 lỗi gán nhãn.
- Ngưỡng đối chiếu ban đầu gồm IoU ghép box-segment >= 0.3 và
  nghi ngờ box lệch khi tỷ lệ pixel segment nằm trong box dưới 0.8.
  Với kiểm tra thiếu box và gộp segment, diện tích segment tối thiểu
  là 100px.
- Các ngưỡng được AI đề xuất dựa trên tín hiệu hình học và kiểm tra
  trên lô sạch. Nhóm chưa tối ưu ngưỡng hoặc đo trên seed luyện tập thứ hai.
  Kết quả lô sạch có 0 ứng viên chưa chứng minh khả năng bắt đủ lỗi.

## 2. Vì sao báo hết ứng viên làm F1 giảm?
Ứng viên là trường hợp hai nguồn nhãn có dấu hiệu bất đồng.
Detection và panoptic của COCO có thể khác nhau tự nhiên do
vật bị che khuất, cách phân chia đối tượng hoặc phạm vi nhãn.
Vì vậy, ứng viên cần được xem ảnh trước khi kết luận.

Trên seed 4007, công cụ tạo 10 ứng viên thuộc 9 ảnh. Sau review
và hợp nhất dòng trùng, nhóm xác nhận 4 lỗi và bác bỏ 5 nghi ngờ.
Nếu đưa toàn bộ ứng viên vào errors.json, những trường hợp
nhóm đã bác bỏ cũng bị báo thành lỗi, có thể làm tăng false
positive và giảm precision.

F1 phụ thuộc cả precision và recall, nên báo nhiều lỗi hơn
không bảo đảm F1 cao hơn. Bản chốt của nhóm có F1 lỗi gán nhãn
xấp xỉ 0.4. Nhóm chưa đo F1 của phương án báo hết ứng viên,
nên chưa có số liệu xác định mức chênh lệch giữa hai phương án.

## 3. Quyết định và lineage
- QC lô v1 `lab250_d0b5af9eb610` (seed `4007`) ghi nhận 15/250 ảnh hoặc cảnh lỗi, tương đương 6,0%. Nhóm ghi quyết định HOLD vì tỷ lệ vượt ngưỡng 2%.
- Kết quả truy vấn lineage: `R-021: affected=True action=review_or_retrain`.
- R-021 đã train trên v1. Nhóm cần đánh giá lại kết quả của run và train lại trên dữ liệu đã kiểm định nếu cần, vì mô hình hiện tại vẫn giữ các trọng số học từ v1.

## 4. Hash chứng minh gì, không chứng minh gì?
SHA-256 giúp kiểm tra tính toàn vẹn của file. Khi hash tính lại
khớp với manifest đáng tin cậy, nhóm có cơ sở xác nhận nội dung
file giống bản đã ghi nhận. Nếu hash khác, file hoặc giá trị
hash trong manifest cần được kiểm tra.

Hash không chứng minh nhãn đúng, ảnh đúng lớp, box đúng vị trí
hay dữ liệu đủ điều kiện phát hành. Một file gán nhãn sai vẫn
có hash hợp lệ. Nếu cả file và manifest cùng bị sửa, việc hai
hash khớp nhau cũng không chứng minh nguồn dữ liệu đáng tin.

Vì vậy, nhóm cần kết hợp kiểm tra hash với validator, đối chiếu
detection–panoptic và review ảnh. Sau khi hoàn thiện v2, nhóm
lập manifest và đóng gói lại để ghi nhận hash của bản bàn giao.

## 5. Truy vết
Ticket của team AI báo model bỏ sót `wine glass` bị che hoặc ở mép ảnh
trong hai cảnh `scene_156` và `scene_643`. Changelog v1.3 yêu cầu vẫn
gán box cho các vật này, trong khi v1.2 cho phép bỏ qua.

- Tầng a gồm các ảnh thuộc hai cảnh được báo, có job dùng guideline
  v1.2 và có ít nhất một box detection lớp `wine glass` trong nhãn được giao.
  Kết quả có 4 ảnh, gồm `000000002157`, `000000002431`,
  `000000007574` và `000000007818`.
- Tầng b mở rộng sang các ảnh ngoài hai cảnh trên, cũng thuộc job
  dùng v1.2 và có box detection lớp `wine glass`. Kết quả có 3 ảnh,
  gồm `000000002685`, `000000003934` và `000000004134`.
- Người cần thông báo là annotator `A01` và reviewer `Q03`, lấy từ
  các job chứa ảnh thuộc cả hai tầng. Kết quả được ghi trong
  `submission/r4007/trace.json`.

Nhóm lấy phiên bản guideline theo `jobs.csv` vì đó là quy tắc áp dụng
cho job.

## 6. Bug hoặc điểm chưa rõ trong lab (nếu có)
Không có.
