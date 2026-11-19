#!/usr/bin/env python3
"""Người 3 — Bàn giao: dựng lô v2 từ delivery v1 + errors.json đã chốt (KHÔNG sửa delivery/).

  python tools/build_v2.py --run runs/r4007                        # xem trước quyết định, không ghi gì
  python tools/build_v2.py --run runs/r4007 --write                # dựng handover/<release_id>_v2/
  python tools/build_v2.py --run runs/r4007 --write --broken-hash 000000001234   # ảnh wrong_hash mở ra bị hỏng -> rework

Ghi vào runs/r<seed>/handover/<release_id>_v2/:
  images/, labels/        bản sao NGUYÊN BYTE của v1, trừ ảnh phải gán lại
  rework_queue.csv        image,type,annotator,reviewer,action (người theo jobs.csv)
  manifest.csv            file,sha256 cho mọi file trong images/ và labels/
  label_summary.csv       class,count (tên theo classes.txt, chỉ lớp có nhãn) + dòng TOTAL
  truyvet.csv             image,scene_id,split,job_id,annotator,reviewer,guideline (guideline theo JOB, split theo cảnh)
  README.txt              theo templates/README.txt

Chỉ dùng thư viện chuẩn. Không đọc _private/. Sau khi chạy: pack_release.py rồi check_handover.py.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

THRESHOLD = 0.02  # Day 7: > 2% ảnh lỗi thì không Release
# Lỗi ở nhãn detection hoặc thiếu file: ảnh vào rework_queue và rời v2.
DET_REWORK = {"missing_image", "invalid_class", "bbox_out_of_bounds", "duplicate_box", "class_swap", "bbox_drift", "missing_box"}
# Sửa được ngay trong v2, không cần gán lại.
FIX_IN_V2 = {"wrong_hash", "guideline_mismatch", "scene_leak"}
# Lỗi chỉ ở panoptic: nhãn detection vẫn đúng, ảnh ở lại v2, báo team panoptic.
PANOPTIC_ONLY = {"invalid_category_id", "thing_overlap", "category_swap", "instance_merge"}
ACTION = {
    "missing_image": "thiếu file ảnh: nộp lại ảnh gốc rồi kiểm lại nhãn",
    "invalid_class": "class_id ngoài 0-79: gán lại lớp đúng",
    "bbox_out_of_bounds": "box tràn khỏi ảnh: vẽ lại box trong khung ảnh",
    "duplicate_box": "box lặp: xoá box thừa",
    "class_swap": "gán nhầm lớp: sửa lớp theo vật trong ảnh",
    "bbox_drift": "box lệch khỏi vật: vẽ lại box ôm sát vật",
    "missing_box": "thiếu box cho vật đáng kể: bổ sung box",
    "wrong_hash": "ảnh hỏng khi mở kiểm: lấy lại ảnh gốc, kiểm nhãn",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def jpeg_looks_ok(path: Path) -> bool:
    """Kiểm thô (thư viện chuẩn): có SOI ở đầu và EOI ở cuối. Vẫn phải MỞ ẢNH bằng mắt."""
    data = path.read_bytes()
    return data[:2] == b"\xff\xd8" and data.rstrip(b"\x00")[-2:] == b"\xff\xd9"


def job_ranges(jobs: list[dict], version: str) -> str:
    ids = [j["job_id"] for j in jobs if j["guideline"] == version]
    if not ids:
        return ""
    return f"{version} ({ids[0]}-{ids[-1]})" if len(ids) > 1 else f"{version} ({ids[0]})"


def main() -> int:
    ap = argparse.ArgumentParser(description="Dựng lô v2 (Người 3)")
    ap.add_argument("--run", required=True, help="runs/r<seed>")
    ap.add_argument("--write", action="store_true", help="ghi thư mục v2 (mặc định chỉ in kế hoạch)")
    ap.add_argument("--broken-hash", nargs="*", default=[], help="ảnh wrong_hash đã mở và thấy HỎNG -> đưa vào rework")
    ap.add_argument("--v2-decision", default="Release", choices=["Release", "Hold", "Rework"])
    args = ap.parse_args()

    run = Path(args.run)
    d = run / "delivery"
    rid = json.loads((d / "release.json").read_text(encoding="utf-8"))["release_id"]
    man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))["items"]
    meta = {m["image"]: m for m in json.loads((d / "metadata.json").read_text(encoding="utf-8"))["items"]}
    jobs_list = read_csv(d / "jobs.csv")
    jobs = {j["job_id"]: j for j in jobs_list}
    names80 = [ln.split(" ", 1)[1].strip() for ln in (d / "classes.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
    errors = json.loads((run / "errors.json").read_text(encoding="utf-8"))["errors"]

    # ---------------- Pha 3: tỉ lệ lỗi v1 (mỗi ảnh / mỗi cảnh scene_leak tính một lần)
    targets = {e["target"] for e in errors}
    n_bad, n_all = len(targets), len(man)
    rate = n_bad / n_all
    decision_v1 = "Hold" if rate > THRESHOLD else "Release"
    by_type = Counter(e["type"] for e in errors)

    # ---------------- phân loại lỗi theo ảnh
    err_of = {}  # image -> type (mỗi ảnh tối đa một lỗi)
    leaked_scenes = set()
    for e in errors:
        if e["type"] == "scene_leak":
            leaked_scenes.add(e["target"])
        elif e["target"] in man:
            err_of[e["target"]] = e["type"]
    unknown = sorted(t for t in targets if t not in man and not t.startswith("scene_"))
    if unknown:
        raise SystemExit(f"errors.json có target không thuộc lô: {unknown[:5]}")

    rework = {n: t for n, t in err_of.items() if t in DET_REWORK}
    for n in args.broken_hash:
        if err_of.get(n) != "wrong_hash":
            raise SystemExit(f"--broken-hash {n}: ảnh này không có lỗi wrong_hash trong errors.json")
        rework[n] = "wrong_hash"
    hash_fixed = sorted(n for n, t in err_of.items() if t == "wrong_hash" and n not in rework)
    guideline_fixed = sorted(n for n, t in err_of.items() if t == "guideline_mismatch")
    panoptic_keep = sorted((n, t) for n, t in err_of.items() if t in PANOPTIC_ONLY)

    # ---------------- sửa split: mỗi cảnh về split đa số (hoà thì train)
    scene_imgs = {}
    for n, m in meta.items():
        scene_imgs.setdefault(m["scene_id"], []).append(n)
    split_fix = {}
    for sc, imgs in scene_imgs.items():
        votes = Counter(meta[n]["split"] for n in imgs)
        if len(votes) > 1:
            target = "val" if votes["val"] > votes["train"] else "train"
            moved = sorted(n for n in imgs if meta[n]["split"] != target)
            split_fix[sc] = (target, moved)
    missed_leak = sorted(set(split_fix) - leaked_scenes)

    # ảnh hợp lệ vào v2: có file ảnh, không trong rework
    keep = sorted(n for n, it in man.items() if (d / it["image"]).is_file() and n not in rework)

    # kiểm thô ảnh wrong_hash
    hash_warn = [n for n in hash_fixed if not jpeg_looks_ok(d / man[n]["image"])]

    # ---------------- in kế hoạch
    print(f"Release v1: {rid}")
    print(f"QC v1: {n_bad}/{n_all} = {rate:.1%}  =>  Kết luận v1: {decision_v1} (ngưỡng 2%)")
    print("Lỗi theo loại:", dict(sorted(by_type.items())))
    print(f"Rework (rời v2): {len(rework)} ảnh -> {dict(sorted(Counter(rework.values()).items()))}")
    print(f"Sửa trong v2: hash {len(hash_fixed)}, guideline {len(guideline_fixed)}, cảnh rò {len(split_fix)}")
    print(f"Lỗi panoptic (ở lại v2, báo team panoptic): {len(panoptic_keep)}")
    print(f"v2: {len(keep)} ảnh")
    if missed_leak:
        print(f"!! CẢNH BÁO: cảnh rò train/val chưa có trong errors.json: {missed_leak} -> báo người làm validator")
    if hash_fixed:
        print(f"!! MỞ ẢNH kiểm bằng mắt trước khi chốt: {hash_fixed} (ảnh hỏng thì chạy lại với --broken-hash <tên>)")
    if hash_warn:
        print(f"!! Thiếu marker JPEG (khả năng hỏng): {hash_warn}")
    if not args.write:
        print("\n(chưa ghi gì; thêm --write để dựng thư mục v2)")
        return 0

    # ---------------- ghi v2
    v2 = run / "handover" / f"{rid}_v2"
    if v2.exists():
        shutil.rmtree(v2)
    for z in (v2.with_suffix(".zip"), v2.with_suffix(".sha256")):
        z.unlink(missing_ok=True)  # đóng gói cũ không còn đúng
    (v2 / "images").mkdir(parents=True)
    (v2 / "labels").mkdir()
    for n in keep:
        shutil.copyfile(d / man[n]["image"], v2 / "images" / f"{n}.jpg")
        shutil.copyfile(d / man[n]["label"], v2 / "labels" / f"{n}.txt")

    # rework_queue.csv
    rows = []
    for n in sorted(rework):
        job = jobs[meta[n]["job_id"]]
        rows.append([n, rework[n], job["annotator"], job["reviewer"], ACTION[rework[n]]])
    write_csv(v2 / "rework_queue.csv", ["image", "type", "annotator", "reviewer", "action"], rows)

    # manifest.csv
    files = sorted(p for sub in ("images", "labels") for p in (v2 / sub).iterdir() if p.is_file())
    write_csv(v2 / "manifest.csv", ["file", "sha256"], [[p.relative_to(v2).as_posix(), sha(p)] for p in files])

    # label_summary.csv (chỉ lớp có nhãn, theo thứ tự classes.txt)
    counts = Counter()
    for n in keep:
        for ln in (v2 / "labels" / f"{n}.txt").read_text(encoding="utf-8").splitlines():
            if ln.strip():
                c = int(float(ln.split()[0]))
                counts[names80[c] if 0 <= c < len(names80) else str(c)] += 1
    order = [c for c in names80 if counts[c]] + sorted(c for c in counts if c not in names80)
    total = sum(counts.values())
    write_csv(v2 / "label_summary.csv", ["class", "count"], [[c, counts[c]] for c in order] + [["TOTAL", total]])

    # truyvet.csv: guideline theo job, split đã sửa theo cảnh
    fixed_split = {n: tgt for sc, (tgt, _) in split_fix.items() for n in scene_imgs[sc]}
    rows = []
    for n in keep:
        m, job = meta[n], jobs[meta[n]["job_id"]]
        rows.append([n, m["scene_id"], fixed_split.get(n, m["split"]), m["job_id"], job["annotator"], job["reviewer"], job["guideline"]])
    write_csv(v2 / "truyvet.csv", ["image", "scene_id", "split", "job_id", "annotator", "reviewer", "guideline"], rows)

    # README.txt
    guideline_line = ", ".join(x for x in (job_ranges(jobs_list, "v1.2"), job_ranges(jobs_list, "v1.3")) if x)
    who = Counter((jobs[meta[n]["job_id"]]["annotator"], jobs[meta[n]["job_id"]]["reviewer"]) for n in rework)
    who_txt = "; ".join(f"{a}/{r}: {k} ảnh" for (a, r), k in sorted(who.items())) or "không có"
    split_txt = "; ".join(f"{sc} về {tgt} (chuyển {', '.join(mv)})" for sc, (tgt, mv) in sorted(split_fix.items())) or "không có"
    pan_txt = "; ".join(f"{n} ({t})" for n, t in panoptic_keep) or "không có"
    hash_txt = ", ".join(hash_fixed) or "không có"
    gl_txt = ", ".join(guideline_fixed) or "không có"
    v2_reason = {
        "Release": f"tách {len(rework)} ảnh lỗi nhãn detection/thiếu file sang rework_queue; sửa hash, guideline, split; "
                   f"còn {len(keep)} ảnh nhãn detection giữ nguyên như v1",
        "Hold": "chưa phát hành, chờ xử lý thêm (xem Ghi chú)",
        "Rework": "chờ gán lại các ảnh trong rework_queue",
    }[args.v2_decision]
    pct = f"{rate * 100:.1f}".replace(".", ",")
    verdict = "vượt ngưỡng 2%, không được train/phát hành" if decision_v1 == "Hold" else "không vượt ngưỡng 2%"
    readme = (
        f"Release: {rid}_v2\n"
        f"Parent: {rid}\n"
        f"Số ảnh: {len(keep)}\n"
        f"Số nhãn: {total}\n"
        f"Guideline: {guideline_line}\n"
        f"QC v1: {n_bad}/{n_all} = {pct}%\n"
        f"Kết luận v1: {decision_v1} — {n_bad}/{n_all} = {pct}% {verdict}\n"
        f"Kết luận v2: {args.v2_decision} — {v2_reason}\n"
        f"Ghi chú: (1) Hash: {hash_txt} — đã mở ảnh kiểm, ảnh còn nguyên nên chỉ manifest v1 ghi sai; manifest.csv v2 tính lại sha256 trên bytes thật. "
        f"(2) Guideline: {gl_txt} — metadata ảnh ghi sai phiên bản; truyvet.csv lấy guideline theo job trong jobs.csv. "
        f"(3) Split: {split_txt} — đưa cả cảnh về một split (đa số) để không rò train/val. "
        f"(4) Rework giao lại đúng người gán/kiểm theo jobs.csv: {who_txt}. "
        f"(5) Lỗi chỉ ở panoptic, nhãn detection vẫn đúng nên ảnh ở lại v2, báo team panoptic: {pan_txt}. "
        f"(6) Nhãn trong v2 không sửa tay; v1 ({rid}) giữ nguyên.\n"
    )
    (v2 / "README.txt").write_text(readme, encoding="utf-8")
    print(f"\nĐã ghi {v2}")
    print("Tiếp theo:")
    print(f"  python scripts/pack_release.py {v2.as_posix()}")
    print(f"  python scripts/lineage.py record --event release --release-id {rid}_v2 --parent {rid}")
    print(f"  python scripts/check_handover.py --run {run.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
