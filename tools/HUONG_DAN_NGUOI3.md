# Người 3 — Bàn giao và truy vết (seed 4007)

Chạy mọi lệnh từ **thư mục gốc repo**. Windows: thay `python3` bằng `py -X utf8`, chạy từng lệnh riêng.
Đặt `tools/build_v2.py` và `tools/trace_query.py` vào repo (KHÔNG sửa gì trong `scripts/`).

## 0. Điều kiện để bắt đầu
- `runs/r4007/delivery/` đã có (`python3 scripts/run_lab.py --seeds 4007`, chỉ chạy **một lần**).
- Người 1–2 đã chốt `runs/r4007/errors.json` (lỗi luật + lỗi gán nhãn `confirmed`) và `runs/r4007/review_log.csv`.
- Lấy release_id v1: `python3 -c "import json;print(json.load(open('runs/r4007/delivery/release.json'))['release_id'])"`
  Bên dưới gọi là `<RID>`.

## 1. Truy vết (làm được NGAY, không cần chờ errors.json)
```bash
python3 tools/trace_query.py runs/r4007/delivery --out runs/r4007/trace.json
```
Script đọc lớp bị đổi quy tắc từ `guideline/changelog.md`, cảnh team AI nêu từ `incoming/ticket.md`, rồi:
- `tier_a` = ảnh trong cảnh ticket nêu + job guideline **v1.2 theo `jobs.csv`** + có ≥1 box lớp đó trong `labels/`
- `tier_b` = các ảnh khác cùng điều kiện
- `notify` = annotator + reviewer của các job chứa ảnh tầng a, b

Tự kiểm: mở `jobs.csv` xem job nào v1.2; mở 1–2 file `labels/` trong tier_a xem có class_id của lớp đó không.

## 2. Quyết định QC + lineage (Pha 3)
```bash
python3 tools/build_v2.py --run runs/r4007          # chỉ in kế hoạch: QC v1 a/250, Hold/Release, rework, sửa gì
python3 scripts/lineage.py record --event decision --release-id <RID> --decision HOLD
python3 scripts/lineage.py impact --release-id <RID>    # mong đợi: R-021: affected=True action=review_or_retrain
```
Chỉ ghi HOLD khi tỉ lệ > 2% (gần như chắc chắn, lô có ~15–25 lỗi). **Không ghi lineage hai lần.**

## 3. Mở ảnh wrong_hash trước khi dựng v2
Kế hoạch ở bước 2 in dòng `!! MỞ ẢNH kiểm ...`. Mở từng ảnh trong `delivery/images/`:
- Ảnh mở được, đúng nội dung ⇒ chỉ manifest sai, v2 ghi hash mới (mặc định).
- Ảnh hỏng ⇒ thêm `--broken-hash <tên>` ở bước 4 để đưa vào rework.

## 4. Dựng lô v2 (Pha 4)
```bash
python3 tools/build_v2.py --run runs/r4007 --write [--broken-hash <tên> ...]
```
Tạo `runs/r4007/handover/<RID>_v2/` gồm `images/ labels/ rework_queue.csv manifest.csv label_summary.csv truyvet.csv README.txt`.
- Lỗi nhãn detection/thiếu file → `rework_queue.csv`, rời v2, giao đúng annotator/reviewer của job.
- `wrong_hash`, `guideline_mismatch`, `scene_leak` → sửa trong v2 (hash mới, guideline theo job, cả cảnh về split đa số).
- Lỗi chỉ panoptic → ảnh ở lại v2, ghi vào Ghi chú README.
- Đọc lại `README.txt`, sửa câu chữ nếu muốn (giữ nguyên các dòng `Release/Parent/Số ảnh/Số nhãn/QC v1/Kết luận`).

## 5. Đóng gói, ghi release, kiểm
```bash
python3 scripts/pack_release.py runs/r4007/handover/<RID>_v2
python3 scripts/lineage.py record --event release --release-id <RID>_v2 --parent <RID>
python3 scripts/check_handover.py --run runs/r4007
python3 scripts/score_findings.py --run runs/r4007
```
Sửa file nào trong v2 (kể cả README) ⇒ **chạy lại `pack_release.py`** (H15).
Nếu errors.json thay đổi ⇒ chạy lại bước 4 rồi bước 5 (không ghi lại lineage release).
H17 là `security.md` — báo người phụ trách điền.

## 6. Nộp
```bash
python3 scripts/export_submission.py --run runs/r4007
git add tools submission && git commit -m "P4-P5: ban giao v2, trace"
```
Commit ít nhất 2 lần có nội dung (vd. một commit trace, một commit handover).

## 7. Đề ẩn (40 phút) — phần của bạn
Sau khi nhóm chạy validator trên `delivery/`:
```bash
python3 tools/trace_query.py delivery --out submission/de_an/trace.json
```

## 8. Gợi ý viết REPORT.md (mục 3–5) — thay số thật của nhóm
**3. Quyết định và lineage.** QC v1 = a/250 = x% > 2% ⇒ Hold. Đã ghi `decision HOLD` cho `<RID>`; `impact` trả `R-021: affected=True action=review_or_retrain`. R-021 đã train trên v1 có nhãn sai (box lệch, sai lớp, thiếu box, rò train/val làm số đo val bị thổi phồng). Đổi dataset không sửa trọng số đã học, nên phải đánh giá lại R-021 trên v2 hoặc train lại.

**4. Hash.** sha256 trong `manifest.csv` + `.sha256` của zip chứng minh: byte của file không đổi kể từ lúc đóng gói, v1 không bị ghi đè (release_id tính từ manifest+metadata), ai cũng tái lập được cùng zip. Hash **không** chứng minh nhãn đúng, ảnh đúng nội dung, hay split/guideline hợp lý — file sai mà được băm thì hash vẫn khớp.

**5. Truy vết.** Lớp đổi quy tắc ở v1.3: `<lớp>`; cảnh ticket nêu: `<scene…>`. Tầng a: ảnh trong các cảnh đó, job guideline v1.2, có box `<lớp>`; tầng b: các ảnh còn lại cùng điều kiện. Lấy guideline theo **job** (`jobs.csv`) vì người gán làm theo phiên bản phát cho job; `guideline_version` của từng ảnh có thể sai (chính là lỗi `guideline_mismatch`).
