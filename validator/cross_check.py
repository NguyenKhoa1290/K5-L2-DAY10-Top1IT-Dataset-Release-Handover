"""Cross-check delivery labels using only the Python standard library.

Integration: from validator.cross_check import find_candidates
result = find_candidates(delivery_path)
Candidates require human review before entering errors.json.
"""
from __future__ import annotations

import argparse
from array import array
from collections import Counter
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.pngutil import read_rgb


def iou(first, second):
    overlap = max(0, min(first[2], second[2]) - max(first[0], second[0])) * max(
        0, min(first[3], second[3]) - max(first[1], second[1]))
    area_a = max(0, first[2] - first[0]) * max(0, first[3] - first[1])
    area_b = max(0, second[2] - second[0]) * max(0, second[3] - second[1])
    union = area_a + area_b - overlap
    return overlap / union if union else 0.0


def load_delivery(delivery):
    delivery = Path(delivery)
    panoptic = json.loads((delivery / 'panoptic.json').read_text(encoding='utf-8'))
    classes = {}
    for line in (delivery / 'classes.txt').read_text(encoding='utf-8').splitlines():
        if line.strip():
            number, name = line.split(maxsplit=1)
            classes[int(number)] = name
    return panoptic, classes


def load_boxes(path, classes, width, height):
    boxes, warnings = [], []
    if not path.is_file():
        return boxes, [f'Missing label file: {path.name}']
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            continue
        try:
            class_id, center_x, center_y, box_w, box_h = map(float, line.split())
            if not all(map(math.isfinite, (class_id, center_x, center_y, box_w, box_h))):
                raise ValueError('non-finite value')
            if not class_id.is_integer() or int(class_id) not in classes or box_w <= 0 or box_h <= 0:
                raise ValueError('invalid class or size')
            boxes.append({'line': number, 'class': classes[int(class_id)], 'bbox': [
                (center_x - box_w / 2) * width, (center_y - box_h / 2) * height,
                (center_x + box_w / 2) * width, (center_y + box_h / 2) * height]})
        except ValueError as error:
            warnings.append(f'{path.name}:{number}: {error}')
    return boxes, warnings


def find_candidates(delivery, *, match_iou=0.3, min_coverage=0.8, min_area=100, min_area_ratio=0.001):
    delivery = Path(delivery)
    panoptic, classes = load_delivery(delivery)
    categories = {entry['id']: entry for entry in panoptic['categories']}
    images = {entry['id']: entry for entry in panoptic['images']}
    result = {'parameters': {'match_iou': match_iou, 'min_coverage': min_coverage,
                            'min_area': min_area, 'min_area_ratio': min_area_ratio},
              'candidates': [], 'warnings': []}
    for annotation in panoptic['annotations']:
        image = images[annotation['image_id']]
        target = Path(image['file_name']).stem
        width, height = image['width'], image['height']
        boxes, warnings = load_boxes(delivery / 'labels' / (target + '.txt'), classes, width, height)
        result['warnings'].extend(warnings)
        try:
            mask_width, mask_height, rgb = read_rgb(delivery / 'masks' / annotation['file_name'])
            if (mask_width, mask_height) != (width, height):
                raise ValueError('mask and image dimensions differ')
        except (OSError, ValueError) as error:
            result['warnings'].append(f'{target}: {error}')
            continue
        ids = array('I', (rgb[index] + rgb[index + 1] * 256 + rgb[index + 2] * 65536
                          for index in range(0, len(rgb), 3)))
        areas = Counter(ids)
        inside = []
        for box in boxes:
            x1, y1, x2, y2 = box['bbox']
            counts = Counter()
            for y in range(max(0, math.ceil(y1 - 0.5)), min(height, math.ceil(y2 - 0.5))):
                left = max(0, min(width, math.ceil(x1 - 0.5)))
                right = max(left, min(width, math.ceil(x2 - 0.5)))
                counts.update(ids[y * width + left:y * width + right])
            inside.append(counts)
        segments = []
        for segment in annotation['segments_info']:
            category = categories.get(segment['category_id'], {})
            if not category.get('isthing') or segment.get('iscrowd') or not areas[segment['id']]:
                continue
            x, y, box_w, box_h = segment['bbox']
            segments.append({**segment, 'class': category['name'], 'bbox': [x, y, x + box_w, y + box_h]})

        def add(types, reason, box_indices, segment_indices):
            result['candidates'].append({'target': target, 'possible_types': types, 'reason': reason,
                'boxes': [boxes[index] for index in box_indices],
                'segments': [{'id': segments[index]['id'], 'class': segments[index]['class'],
                              'bbox': segments[index]['bbox']} for index in segment_indices]})

        pairs = sorted(((iou(box['bbox'], segment['bbox']), bi, si)
                        for bi, box in enumerate(boxes) for si, segment in enumerate(segments)), reverse=True)
        matched_boxes, matched_segments = set(), set()
        for overlap, bi, si in pairs:
            if overlap < match_iou or bi in matched_boxes or si in matched_segments:
                continue
            matched_boxes.add(bi)
            matched_segments.add(si)
            box, segment = boxes[bi], segments[si]
            coverage = inside[bi][segment['id']] / areas[segment['id']]
            if box['class'] != segment['class']:
                add(['class_swap', 'category_swap'], f'Class disagreement; IoU={overlap:.3f}, mask coverage={coverage:.3f}', [bi], [si])
            elif coverage < min_coverage:
                add(['bbox_drift'], f'Mask coverage={coverage:.3f}, IoU={overlap:.3f}', [bi], [si])
        for si, segment in enumerate(segments):
            segment_id = segment['id']
            if areas[segment_id] < max(min_area, min_area_ratio * width * height):
                continue
            coverage = [counts[segment_id] / areas[segment_id] for counts in inside]
            if si not in matched_segments:
                same_class = [bi for bi, box in enumerate(boxes) if box['class'] == segment['class']]
                nearby = sorted(same_class, key=lambda bi: coverage[bi], reverse=True)
                if nearby and coverage[nearby[0]] >= 0.2:
                    add(['bbox_drift'], f'Unmatched segment, best same-class mask coverage={coverage[nearby[0]]:.3f}', nearby[:1], [si])
                elif max(coverage, default=0) < 0.5:
                    add(['missing_box'], f'Unmatched thing segment; actual area={areas[segment_id]} pixels', [], [si])
            supported = [bi for bi, box in enumerate(boxes)
                         if box['class'] == segment['class'] and 0.2 <= coverage[bi] <= 0.85]
            separated = [(a, b) for n, a in enumerate(supported) for b in supported[n + 1:]
                         if iou(boxes[a]['bbox'], boxes[b]['bbox']) < 0.2
                         and coverage[a] + coverage[b] >= 0.8
                         and max(coverage, default=0) <= 0.9]
            if separated:
                add(['instance_merge'], 'Two separated same-class boxes each cover 20-85% of a segment and together cover at least 80%; no box covers over 90%', sorted({bi for pair in separated for bi in pair}), [si])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('delivery', type=Path)
    parser.add_argument('--candidates', required=True, type=Path)
    parser.add_argument('--match-iou', type=float, default=0.3)
    parser.add_argument('--min-coverage', type=float, default=0.8)
    parser.add_argument('--min-area', type=int, default=100)
    parser.add_argument('--min-area-ratio', type=float, default=0.001)
    args = parser.parse_args()
    if not 0 < args.match_iou <= 1 or not 0 < args.min_coverage <= 1 or args.min_area < 0 or not 0 <= args.min_area_ratio <= 1:
        parser.error('Invalid threshold range')
    result = find_candidates(args.delivery, match_iou=args.match_iou, min_coverage=args.min_coverage,
                             min_area=args.min_area, min_area_ratio=args.min_area_ratio)
    args.candidates.parent.mkdir(parents=True, exist_ok=True)
    args.candidates.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Candidates: {len(result['candidates'])}; images: {len({c['target'] for c in result['candidates']})}; warnings: {len(result['warnings'])}")


if __name__ == '__main__':
    main()
