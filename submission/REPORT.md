# Báo cáo nhóm <<XX>>

## 1. Số liệu luyện tập
- F1 theo seed (rule / cross_check / overall): <<seed: ... / ... / ...>>
- Số ứng viên trên lô sạch (`--no-faults`): <<...>>; hàng đợi trên seed luyện tập: <<... ảnh>>
- Ngưỡng đã chọn và cách chọn (không dùng `_private`): <<...>>

## 2. Vì sao báo hết ứng viên làm F1 giảm?
<<Trả lời bằng số của nhóm.>>

## 3. Quyết định và lineage
- QC lô v1 `lab250_d0b5af9eb610` (seed `4007`) ghi nhận 15/250 ảnh hoặc cảnh lỗi, tương đương 6,0%. Nhóm ghi quyết định HOLD vì tỷ lệ vượt ngưỡng 2%.
- Kết quả truy vấn lineage: `R-021: affected=True action=review_or_retrain`.
- R-021 đã train trên v1. Nhóm cần đánh giá lại kết quả của run và train lại trên dữ liệu đã kiểm định nếu cần, vì mô hình hiện tại vẫn giữ các trọng số học từ v1.

## 4. Hash chứng minh gì, không chứng minh gì?
<<>>

## 5. Truy vết
<<Tiêu chí tầng a/b, vì sao lấy guideline theo job.>>

## 6. Bug hoặc điểm chưa rõ trong lab (nếu có)
<<>>
