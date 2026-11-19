#!/usr/bin/env python3
"""Người 3 — Truy vết ticket của team AI -> trace.json.

  python tools/trace_query.py runs/r4007/delivery --out runs/r4007/trace.json
  python tools/trace_query.py delivery --out submission/de_an/trace.json          # đề ẩn

Đọc incoming/ticket.md (cảnh team AI nêu), guideline/changelog.md (lớp bị đổi quy tắc ở v1.3),
jobs.csv, metadata.json, labels/ và classes.txt.

  tier_a : ảnh trong các cảnh ticket nêu, thuộc JOB theo guideline cũ (theo jobs.csv),
           có >= 1 box detection của lớp bị đổi quy tắc trong labels/
  tier_b : các ảnh khác cùng điều kiện (job guideline cũ, có lớp đó) mà chưa ai báo
  notify : người gán + người kiểm của các job chứa ảnh tầng a và b

Guideline lấy theo job, KHÔNG theo guideline_version của từng ảnh (đó có thể là lỗi guideline_mismatch).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="Truy vết ticket")
    ap.add_argument("delivery")
    ap.add_argument("--out", required=True)
    ap.add_argument("--rule-class", help="ghi đè lớp bị đổi quy tắc nếu đọc changelog không ra")
    ap.add_argument("--old", default="v1.2", help="phiên bản guideline cũ")
    args = ap.parse_args()
    d = Path(args.delivery)

    changelog = (d / "guideline" / "changelog.md").read_text(encoding="utf-8")
    ticket = (d / "incoming" / "ticket.md").read_text(encoding="utf-8")
    if args.rule_class:
        rule_class = args.rule_class
    else:
        # lớp nằm trong `...` ở mục v1.3 của changelog
        sec = changelog.split("## v1.3", 1)[-1].split("\n## ", 1)[0]
        found = re.findall(r"`([^`]+)`", sec)
        if not found:
            raise SystemExit("Không đọc được lớp bị đổi quy tắc trong changelog; dùng --rule-class")
        rule_class = found[0]
    scenes = sorted(set(re.findall(r"scene_\w+", ticket)))

    names = {}
    for ln in (d / "classes.txt").read_text(encoding="utf-8").splitlines():
        if ln.strip():
            i, n = ln.split(" ", 1)
            names[int(i)] = n.strip()
    if rule_class not in names.values():
        raise SystemExit(f"lớp '{rule_class}' không có trong classes.txt")
    with (d / "jobs.csv").open(encoding="utf-8", newline="") as f:
        jobs = {r["job_id"]: r for r in csv.DictReader(f)}
    meta = json.loads((d / "metadata.json").read_text(encoding="utf-8"))["items"]

    def has_class(stem: str) -> bool:
        p = d / "labels" / f"{stem}.txt"
        if not p.is_file():
            return False
        for ln in p.read_text(encoding="utf-8").splitlines():
            parts = ln.split()
            if parts:
                try:
                    c = int(float(parts[0]))
                except ValueError:
                    continue
                if names.get(c) == rule_class:
                    return True
        return False

    hit = [m for m in meta if jobs[m["job_id"]]["guideline"] == args.old and has_class(m["image"])]
    tier_a = sorted(m["image"] for m in hit if m["scene_id"] in scenes)
    tier_b = sorted(m["image"] for m in hit if m["scene_id"] not in scenes)
    job_ids = sorted({m["job_id"] for m in hit})
    notify = sorted({jobs[j]["annotator"] for j in job_ids} | {jobs[j]["reviewer"] for j in job_ids})

    out = {"tier_a": tier_a, "tier_b": tier_b, "notify": notify}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    old_jobs = [j for j, r in jobs.items() if r["guideline"] == args.old]
    print(f"lớp đổi quy tắc: {rule_class} | cảnh ticket nêu: {scenes} | job guideline {args.old}: {old_jobs}")
    print(f"tier_a {len(tier_a)} ảnh, tier_b {len(tier_b)} ảnh, notify {notify} (job {job_ids}) -> {args.out}")
    if not tier_a:
        print("!! tier_a rỗng: kiểm lại tên cảnh trong ticket / phiên bản guideline cũ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
