#!/usr/bin/env python3
"""Validator của nhóm Top1IT.

    python validator/validate.py <thư_mục_delivery> --out <errors.json> [--candidates <candidates.json>]

* --out         : 9 lỗi LUẬT (máy bắt được), dạng {"errors": [{"type", "target"}]}.
                  Đưa file này vào `scripts/merge_review.py --rules ...`.
* --candidates  : ứng viên lỗi GÁN NHÃN (đối chiếu detection <-> panoptic bằng pixel mask).
                  Đây CHỈ là hàng đợi để người mở ảnh xem; không tự đưa vào errors.json.

Ràng buộc đề bài: chỉ đọc thư mục delivery truyền vào (không đọc _private/, data_source/,
annotation COCO), không dùng mạng, chỉ thư viện chuẩn (+ scripts/pngutil.py để đọc PNG).
Không nhúng tên ảnh / id / đáp án của seed nào vào code: mọi ngưỡng dưới đây chỉ là tham số
hình học, được chọn bằng cách đo trên lô sạch (`inject_release.py --no-faults`).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pngutil  # noqa: E402  (đọc PNG bằng thư viện chuẩn, được phép dùng)

# --------------------------------------------------------------------------------------
# Tham số. Lỗi luật: dung sai chỉ để chịu làm tròn số, không phải đoán.
# --------------------------------------------------------------------------------------
BBOX_EPS = 1e-4          # YOLO ghi 6 chữ số thập phân => sai số làm tròn ~1e-6
DUP_SIZE_PX = 1.0        # hai box "cùng kích thước": chênh <= 1 pixel mỗi chiều
DUP_SHIFT_PX = 3.0       # hộp lặp lệch tâm tối đa ~2 pixel (chừa 1 pixel dự phòng)
AREA_TOL = 0             # area khai báo - số pixel thật > AREA_TOL  => thing_overlap

# Tham số đối chiếu (candidates). Xem phần "CROSS-CHECK" bên dưới.
MIN_SEG_FRAC = 0.002     # segment thing nhỏ hơn 0.2% ảnh thì không xét
MIN_SEG_PX = 300
MATCH_SEG_IN_BOX = 0.5   # >= 50% pixel của segment nằm trong box ...
MATCH_BOX_FILLED = 0.2   # ... và segment lấp >= 20% diện tích box => hai bên "ghép" được
MISSING_BOX_FRAC = 0.004  # segment không có box chỉ đáng ngờ nếu >= 0.4% ảnh (pixel mask nhỏ hơn diện tích box)
DRIFT_OUTSIDE = 0.02     # > 2% pixel segment rơi ra ngoài box cùng lớp => box lệch (tự nhiên: ~0)
DRIFT_MIN_PX = 60        # ... và phần ra ngoài phải >= 60 pixel (tránh nhiễu viền)
DRIFT_OVERFLOW = 0.04   # bbox segment tràn khỏi box > 4% cỡ box (tự nhiên: 99% cặp <= 2.1%)
MERGE_BOX_FILLED = 0.2   # box mồ côi được segment (đã ghép box khác cùng lớp) lấp >= 20%
_STATS = None            # công cụ đo ngưỡng: nếu là list thì cross_check ghi số liệu từng cặp vào đó


# --------------------------------------------------------------------------------------
# Đọc dữ liệu
# --------------------------------------------------------------------------------------
def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:  # đọc bytes, không so chuỗi
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Delivery:
    def __init__(self, root: Path):
        self.root = root
        self.manifest = read_json(root / "manifest.json")["items"]
        meta_doc = read_json(root / "metadata.json")
        self.meta = {m["image"]: m for m in meta_doc["items"]}
        self.jobs = {r["job_id"]: r for r in read_csv(root / "jobs.csv")}
        self.classes: dict[int, str] = {}
        for ln in (root / "classes.txt").read_text(encoding="utf-8").splitlines():
            if ln.strip():
                cid, name = ln.split(" ", 1)
                self.classes[int(cid)] = name.strip()
        self.num_classes = len(self.classes) or 80
        self.pan = read_json(root / "panoptic.json")
        self.cats = {c["id"]: c for c in self.pan["categories"]}
        self.pan_images = {im["id"]: im for im in self.pan["images"]}
        self.ann_by_name = {Path(a["file_name"]).stem: a for a in self.pan["annotations"]}

    def labels(self, name: str) -> list[tuple[int | None, float, float, float, float]]:
        """Các dòng YOLO của ảnh. class = None nếu không đọc được."""
        item = self.manifest[name]
        path = self.root / item["label"]
        rows = []
        if not path.is_file():
            return rows
        for ln in path.read_text(encoding="utf-8").splitlines():
            p = ln.split()
            if len(p) < 5:
                continue
            try:
                c = int(float(p[0]))
                x, y, w, h = (float(v) for v in p[1:5])
            except ValueError:
                rows.append((None, 0.0, 0.0, 0.0, 0.0))
                continue
            rows.append((c, x, y, w, h))
        return rows

    def size(self, name: str) -> tuple[int, int]:
        ann = self.ann_by_name.get(name)
        if ann:
            im = self.pan_images.get(ann["image_id"])
            if im:
                return im["width"], im["height"]
        return 640, 480


# --------------------------------------------------------------------------------------
# LỖI LUẬT (9 loại), mỗi loại một hàm. Trả về set các (type, target).
# --------------------------------------------------------------------------------------
def check_missing_image(d: Delivery) -> tuple[set, set]:
    """missing_image: manifest khai báo ảnh nhưng không có file. Trả về (lỗi, tập ảnh thiếu)."""
    out, missing = set(), set()
    for name, item in d.manifest.items():
        if not (d.root / item["image"]).is_file():
            out.add(("missing_image", name))
            missing.add(name)
    return out, missing


def check_wrong_hash(d: Delivery, missing: set) -> set:
    """wrong_hash: sha256 tính lại từ bytes của file khác sha256 ghi trong manifest."""
    out = set()
    for name, item in d.manifest.items():
        if name in missing:
            continue
        if sha256_file(d.root / item["image"]) != item["image_sha256"].strip().lower():
            out.add(("wrong_hash", name))
    return out


def check_invalid_class(d: Delivery) -> set:
    """invalid_class: class_id ngoài 0..num_classes-1 (hoặc không đọc được)."""
    out = set()
    for name in d.manifest:
        for c, *_ in d.labels(name):
            if c is None or not 0 <= c < d.num_classes:
                out.add(("invalid_class", name))
                break
    return out


def check_bbox_out_of_bounds(d: Delivery) -> set:
    """bbox_out_of_bounds: box YOLO chuẩn hoá có mép ra ngoài [0, 1] (chỉ chừa sai số làm tròn)."""
    out = set()
    for name in d.manifest:
        for c, x, y, w, h in d.labels(name):
            if c is None:
                continue
            if (x - w / 2 < -BBOX_EPS or y - h / 2 < -BBOX_EPS
                    or x + w / 2 > 1 + BBOX_EPS or y + h / 2 > 1 + BBOX_EPS):
                out.add(("bbox_out_of_bounds", name))
                break
    return out


def check_duplicate_box(d: Delivery) -> set:
    """duplicate_box: cùng lớp, CÙNG KÍCH THƯỚC, tâm lệch rất ít (1-2 pixel).

    Không dùng IoU thấp: COCO có cặp box tự nhiên chồng nhau, nhưng khác kích thước.
    """
    out = set()
    for name in d.manifest:
        W, H = d.size(name)
        rows = [r for r in d.labels(name) if r[0] is not None]
        found = False
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a, b = rows[i], rows[j]
                if a[0] != b[0]:
                    continue
                if (abs(a[3] - b[3]) * W <= DUP_SIZE_PX and abs(a[4] - b[4]) * H <= DUP_SIZE_PX
                        and abs(a[1] - b[1]) * W <= DUP_SHIFT_PX and abs(a[2] - b[2]) * H <= DUP_SHIFT_PX):
                    found = True
                    break
            if found:
                break
        if found:
            out.add(("duplicate_box", name))
    return out


def check_scene_leak(d: Delivery) -> set:
    """scene_leak: một scene_id có ảnh ở cả train và val. TARGET LÀ scene_id, không phải tên ảnh."""
    splits: dict[str, set] = {}
    for name in d.manifest:
        m = d.meta.get(name)
        if m:
            splits.setdefault(m["scene_id"], set()).add(m["split"])
    return {("scene_leak", sc) for sc, s in splits.items() if len(s) > 1}


def check_guideline_mismatch(d: Delivery) -> set:
    """guideline_mismatch: guideline của ảnh khác guideline của JOB (jobs.csv)."""
    out = set()
    for name in d.manifest:
        m = d.meta.get(name)
        if not m:
            continue
        job = d.jobs.get(m["job_id"])
        if job and m["guideline_version"] != job["guideline"]:
            out.add(("guideline_mismatch", name))
    return out


def check_invalid_category_id(d: Delivery) -> set:
    """invalid_category_id: segment có category_id không nằm trong `categories`."""
    out = set()
    for name, ann in d.ann_by_name.items():
        if any(s["category_id"] not in d.cats for s in ann["segments_info"]):
            out.add(("invalid_category_id", name))
    return out


def load_mask(d: Delivery, name: str):
    """Trả về (W, H, ids) với ids[i] = R + G*256 + B*65536, hoặc None nếu thiếu/hỏng mask."""
    item = d.manifest.get(name)
    path = d.root / (item["mask"] if item and "mask" in item else f"masks/{name}.png")
    if not path.is_file():
        return None
    try:
        W, H, px = pngutil.read_rgb(path)
    except (ValueError, OSError):
        return None
    ids = [r + g * 256 + b * 65536 for r, g, b in zip(px[0::3], px[1::3], px[2::3])]
    return W, H, ids


def check_thing_overlap(d: Delivery, name: str, mask) -> bool:
    """thing_overlap: area khai báo trong segments_info > số pixel thật của segment trong mask."""
    if mask is None:
        return False
    counts = Counter(mask[2])
    ann = d.ann_by_name[name]
    for s in ann["segments_info"]:
        cat = d.cats.get(s["category_id"])
        if not cat or not cat.get("isthing") or s.get("iscrowd"):
            continue
        if s.get("area", 0) - counts.get(s["id"], 0) > AREA_TOL:
            return True
    return False


# --------------------------------------------------------------------------------------
# CROSS-CHECK: đối chiếu detection <-> panoptic (ứng viên lỗi gán nhãn)
#
# Với mỗi cặp (segment thing, box detection) có bbox giao nhau, đếm bằng PIXEL MASK:
#   cs = (pixel của segment nằm trong box) / (pixel segment)    -> segment có "nằm trong" box
#   cb = (pixel của segment nằm trong box) / (diện tích box)    -> segment có lấp đầy box
# Một cặp "ghép" được khi cs >= 0.5 và cb >= 0.2 (vật lồng nhau, vd người trên xe, không ghép
# nhầm vì cb quá nhỏ). Từ đó:
#   - ghép được nhưng khác lớp                       -> class_swap / category_swap
#   - ghép được cùng lớp nhưng pixel rơi ra ngoài box -> bbox_drift
#   - segment lớn không ghép được với box nào         -> missing_box
#   - box mồ côi nằm gọn trong segment đã có box khác
#     cùng lớp                                       -> instance_merge
# --------------------------------------------------------------------------------------
def count_in_box(ids, W, H, sid, box) -> int:
    x0, x1 = max(0, int(box[0])), min(W, int(math.ceil(box[2])))
    y0, y1 = max(0, int(box[1])), min(H, int(math.ceil(box[3])))
    if x1 <= x0 or y1 <= y0:
        return 0
    return sum(ids[y * W + x0:y * W + x1].count(sid) for y in range(y0, y1))


def cross_check(d: Delivery, name: str, mask, skip_ids: set | None = None) -> list[dict]:
    if mask is None:
        return []
    W, H, ids = mask
    counts = Counter(ids)
    ann = d.ann_by_name.get(name)
    if ann is None:
        return []
    segs = []
    for s in ann["segments_info"]:
        cat = d.cats.get(s["category_id"])
        if not cat or not cat.get("isthing") or s.get("iscrowd"):
            continue
        area = counts.get(s["id"], 0)
        if area < max(MIN_SEG_PX, MIN_SEG_FRAC * W * H):
            continue
        bx, by, bw, bh = s["bbox"]
        segs.append({"id": s["id"], "name": cat["name"], "area": area,
                     "bbox": [bx, by, bx + bw, by + bh]})
    boxes = []
    for k, (c, x, y, w, h) in enumerate(d.labels(name)):
        if c is None or c not in d.classes:
            continue
        box = [(x - w / 2) * W, (y - h / 2) * H, (x + w / 2) * W, (y + h / 2) * H]
        boxes.append({"k": k, "name": d.classes[c], "box": box, "area": max(1.0, w * W * h * H)})

    # bảng giao pixel cho các cặp có bbox giao nhau
    pair = {}
    for si, s in enumerate(segs):
        for bi, b in enumerate(boxes):
            sb, bb = s["bbox"], b["box"]
            if sb[2] <= bb[0] or bb[2] <= sb[0] or sb[3] <= bb[1] or bb[3] <= sb[1]:
                continue
            inter = count_in_box(ids, W, H, s["id"], bb)
            if inter:
                pair[(si, bi)] = inter

    def cs(si, bi):
        return pair.get((si, bi), 0) / segs[si]["area"]

    def cb(si, bi):
        return pair.get((si, bi), 0) / boxes[bi]["area"]

    def matched(si, bi):
        return cs(si, bi) >= MATCH_SEG_IN_BOX and cb(si, bi) >= MATCH_BOX_FILLED

    reasons = []
    box_has_seg = {bi: False for bi in range(len(boxes))}
    for si, s in enumerate(segs):
        mb = [bi for bi in range(len(boxes)) if matched(si, bi)]
        for bi in mb:
            box_has_seg[bi] = True
        same = [bi for bi in mb if boxes[bi]["name"] == s["name"]]
        if same:
            bi = max(same, key=lambda i: pair[(si, i)])
            out_px = s["area"] - pair[(si, bi)]
            # phần segment tràn ra ngoài box, tính theo bbox (nhạy hơn đếm pixel với lệch nhẹ)
            sb, bb = s["bbox"], boxes[bi]["box"]
            bw, bh = max(1.0, bb[2] - bb[0]), max(1.0, bb[3] - bb[1])
            overflow = max(bb[0] - sb[0], sb[2] - bb[2], 0.0) / bw
            overflow = max(overflow, max(bb[1] - sb[1], sb[3] - bb[3], 0.0) / bh)
            if _STATS is not None:
                _STATS.append((name, s["id"], round(out_px / s["area"], 4), round(overflow, 4), s["area"]))
            if (out_px / s["area"] > DRIFT_OUTSIDE and out_px >= DRIFT_MIN_PX) or overflow > DRIFT_OVERFLOW:
                reasons.append({"type": "bbox_drift", "score": round(out_px / s["area"], 3),
                                "detail": f"{out_px}px ({out_px / s['area']:.0%}) của segment {s['name']} nằm ngoài box",
                                "segment_id": s["id"], "box_index": boxes[bi]["k"]})
        elif mb:
            bi = max(mb, key=lambda i: pair[(si, i)])
            reasons.append({"type": "class_swap", "alt": "category_swap",
                            "score": round(cs(si, bi), 3),
                            "detail": f"box ghi '{boxes[bi]['name']}' nhưng segment ghi '{s['name']}'",
                            "segment_id": s["id"], "box_index": boxes[bi]["k"]})
        else:
            # không ghép được box nào: box cùng lớp chồng một phần => box lệch xa; không có => thiếu box
            same_cls = [bi for bi in range(len(boxes)) if boxes[bi]["name"] == s["name"]]
            inside = [bi for bi in same_cls if cs(si, bi) >= MATCH_SEG_IN_BOX]  # vật nhỏ nằm gọn trong box nhóm
            part = [bi for bi in same_cls if 0.1 <= cs(si, bi) < MATCH_SEG_IN_BOX and cb(si, bi) >= 0.1]
            if inside:
                continue
            if part:
                bi = max(part, key=lambda i: pair[(si, i)])
                reasons.append({"type": "bbox_drift", "score": round(1 - cs(si, bi), 3),
                                "detail": f"box '{s['name']}' chỉ chứa {cs(si, bi):.0%} pixel segment",
                                "segment_id": s["id"], "box_index": boxes[bi]["k"]})
            elif s["area"] >= MISSING_BOX_FRAC * W * H:
                reasons.append({"type": "missing_box", "score": round(s["area"] / (W * H), 4),
                                "detail": f"segment '{s['name']}' ({s['area']}px) không có box detection nào",
                                "segment_id": s["id"]})
    # box mồ côi (không ghép được segment nào) nằm gọn trong một segment cùng lớp
    for bi, b in enumerate(boxes):
        if box_has_seg[bi]:
            continue
        for si, s in enumerate(segs):
            if s["name"] != b["name"] or cb(si, bi) < MERGE_BOX_FILLED:
                continue
            owner = [oj for oj in range(len(boxes)) if oj != bi and boxes[oj]["name"] == s["name"] and matched(si, oj)]
            if owner:
                reasons.append({"type": "instance_merge", "score": round(cb(si, bi), 3),
                                "detail": f"box '{b['name']}' #{b['k']} và box #{boxes[owner[0]]['k']} cùng nằm trong một segment",
                                "segment_id": s["id"], "box_index": b["k"]})
                break
    if skip_ids is not None:
        reasons = [r for r in reasons if r.get("segment_id") not in skip_ids]
    return reasons


# --------------------------------------------------------------------------------------
def run(delivery: Path, out: Path, cand_out: Path | None) -> int:
    d = Delivery(delivery)
    errors, missing = check_missing_image(d)
    errors |= check_wrong_hash(d, missing)
    errors |= check_invalid_class(d)
    errors |= check_bbox_out_of_bounds(d)
    errors |= check_duplicate_box(d)
    errors |= check_scene_leak(d)
    errors |= check_guideline_mismatch(d)
    errors |= check_invalid_category_id(d)

    candidates = []
    for name in d.manifest:
        mask = load_mask(d, name)
        if check_thing_overlap(d, name, mask):
            errors.add(("thing_overlap", name))
        if cand_out is not None:
            reasons = cross_check(d, name, mask)
            if reasons:
                reasons.sort(key=lambda r: -r["score"])
                candidates.append({"image": name, "type": reasons[0]["type"], "reasons": reasons})

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"errors": [{"type": t, "target": g} for t, g in sorted(errors)]}, indent=1) + "\n",
                   encoding="utf-8")
    summary = Counter(t for t, _ in errors)
    print(f"{len(errors)} lỗi luật -> {out}  " + ", ".join(f"{k}={v}" for k, v in sorted(summary.items())))
    if cand_out is not None:
        cand_out.parent.mkdir(parents=True, exist_ok=True)
        cand_out.write_text(json.dumps({"candidates": candidates}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{len(candidates)} ảnh ứng viên lỗi gán nhãn -> {cand_out}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Validator lỗi luật + ứng viên lỗi gán nhãn")
    ap.add_argument("delivery", help="thư mục delivery (chỉ đọc)")
    ap.add_argument("--out", required=True, help="errors.json (lỗi luật)")
    ap.add_argument("--candidates", help="candidates.json (ứng viên lỗi gán nhãn)")
    args = ap.parse_args()
    return run(Path(args.delivery), Path(args.out), Path(args.candidates) if args.candidates else None)


if __name__ == "__main__":
    raise SystemExit(main())
