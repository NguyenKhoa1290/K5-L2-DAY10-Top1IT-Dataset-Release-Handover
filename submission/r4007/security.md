# Bảo mật khi làm việc

> Gắn với lô seed 4007: v1 `lab250_d0b5af9eb610` (Hold), v2 `lab250_d0b5af9eb610_v2` (243 ảnh COCO có người thật).

## 1. Ca USB: hết giờ, muốn chép lô về nhà làm tiếp
Không chép lô ra USB hay về máy cá nhân. Lô `lab250_d0b5af9eb610` có ảnh người thật nhìn rõ mặt (ví dụ `000000019924`, `000000008532`) và nhãn chưa phát hành (v1 đang Hold). Mang ra ngoài là dữ liệu rời khỏi hệ thống được kiểm soát: mất USB thì lộ dữ liệu cá nhân, và không còn ai truy được ai đã giữ bản nào. Gửi qua email cá nhân cũng sai vì dữ liệu nằm trên máy chủ ngoài công ty. Nhờ người khác làm hộ cũng sai vì người đó không được giao job, nên lineage và `truyvet.csv` sẽ ghi sai người gán và người kiểm. Cách đúng: dừng ở chỗ đang làm, ghi lại tiến độ (ví dụ đã chốt `errors.json`, còn lại `security.md`), commit phần mã và tài liệu không chứa ảnh lên repo nhóm, hôm sau làm tiếp trên máy được cấp. Nếu thật sự cần làm từ xa thì xin quyền truy cập từ xa (VPN, máy ảo công ty) qua người phụ trách.

## 2. Năm việc: được hay không
- **Mở job được giao trên máy công ty:** được. Đây là đúng quyền và đúng nơi; mọi thao tác được ghi lại theo tài khoản của mình, đúng với `jobs.csv`.
- **Chụp màn hình gửi người quen:** không. Ảnh chụp màn hình cũng là dữ liệu (mặt người, nhãn chưa phát hành) và rời khỏi hệ thống mà không ai kiểm soát được. Cần hỏi thì hỏi người phụ trách qua kênh nội bộ, mô tả bằng tên ảnh (ví dụ `000000017379`) chứ không gửi ảnh.
- **Chép lô ra USB:** không, lý do như ca 1. Lô bàn giao chỉ đi theo đường chính thức: thư mục `handover/` kèm `manifest.csv` và `.sha256`.
- **Dán nhãn thật lên chatbot:** không. Chatbot ngoài là bên thứ ba và có thể lưu dữ liệu. Nhóm chỉ dùng AI để hỏi về cách viết code và quy trình (ghi trong `prompts.md`), không dán ảnh hay nhãn của lô.
- **Đưa tài khoản CVAT cho đồng nghiệp:** không. Một tài khoản phải ứng với một người, thì `rework_queue.csv` mới giao đúng người và lineage mới truy được ai đã gán. Đồng nghiệp cần quyền thì xin cấp tài khoản riêng.

## 3. Ca khuôn mặt: thấy mặt người rõ trong lô, guideline yêu cầu làm mờ
Trong lô có ảnh chân dung nhìn rõ mặt chưa được làm mờ: `000000019924` (phụ nữ đội mũ rộng vành, cận mặt), `000000021604` (người đàn ông đeo kính, mặc vest), `000000008532` (người đàn ông đội mũ, đeo kính, ảnh chụp ngoài trời). Cả ba hiện đang nằm trong v2. Việc cần làm là **Hold** lô và báo ngay cho người phụ trách dữ liệu (data owner hoặc trưởng nhóm), kèm danh sách tên ảnh. Không tự làm mờ, vì làm mờ là sửa ảnh: hash trong `manifest.csv` sẽ đổi, ảnh không còn khớp với nhãn và với v1, và mỗi người sẽ làm mờ theo một kiểu, không theo quy trình chung. Cũng không tự xoá ảnh, vì xoá làm mất dấu vết, sai số liệu trong `README.txt` và `label_summary.csv`, và người phụ trách không biết đã có vấn đề. Người phụ trách sẽ quyết định cách xử lý (làm mờ bằng công cụ chuẩn hoặc loại ảnh), rồi phát hành một lô mới có lineage ghi rõ lô cha.
