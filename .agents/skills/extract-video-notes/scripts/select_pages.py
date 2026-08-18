#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat


RESAMPLE = getattr(Image, "Resampling", Image).LANCZOS
TIME_RE = re.compile(r"_(\d+(?:\.\d+)?)\.jpe?g$", re.IGNORECASE)


def normalized_crop(image: Image.Image, left: float, top: float, right: float, bottom: float) -> Image.Image:
    width, height = image.size
    return image.crop((
        int(width * left),
        int(height * top),
        int(width * right),
        int(height * bottom),
    ))


def signature(image: Image.Image, crop: tuple[float, float, float, float]) -> Image.Image:
    area = normalized_crop(image, *crop)
    return area.convert("L").resize((64, 96), RESAMPLE)


def mean_difference(left: Image.Image, right: Image.Image) -> float:
    return float(ImageStat.Stat(ImageChops.difference(left, right)).mean[0] / 255.0)


def sharpness(sig: Image.Image) -> float:
    width, height = sig.size
    horizontal = ImageChops.difference(sig.crop((1, 0, width, height)), sig.crop((0, 0, width - 1, height)))
    vertical = ImageChops.difference(sig.crop((0, 1, width, height)), sig.crop((0, 0, width, height - 1)))
    return float(ImageStat.Stat(horizontal).mean[0] + ImageStat.Stat(vertical).mean[0])


def frame_time(path: Path, fallback: float) -> float:
    match = TIME_RE.search(path.name)
    return float(match.group(1)) if match else fallback


def make_contact_sheet(paths: list[Path], output: Path) -> None:
    thumb_width, thumb_height, label_height = 180, 300, 26
    columns = 6
    rows = max(1, (len(paths) + columns - 1) // columns)
    sheet = Image.new("RGB", (columns * thumb_width, rows * (thumb_height + label_height)), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=15)
    for index, path in enumerate(paths):
        with Image.open(path) as source:
            thumb = source.convert("RGB")
            thumb.thumbnail((thumb_width, thumb_height), RESAMPLE)
        x0 = (index % columns) * thumb_width
        y0 = (index // columns) * (thumb_height + label_height)
        sheet.paste(thumb, (x0 + (thumb_width - thumb.width) // 2, y0))
        draw.text((x0 + 6, y0 + thumb_height + 3), f"page {index + 1:02d}", fill="black", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=92)


def main() -> None:
    parser = argparse.ArgumentParser(description="Select stable, non-duplicate pages from sampled video frames.")
    parser.add_argument("frames_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--step", type=float, default=0.25)
    parser.add_argument("--stable-threshold", type=float, default=0.010)
    parser.add_argument("--dedup-threshold", type=float, default=0.018)
    parser.add_argument("--crop-top", type=float, default=0.165)
    parser.add_argument("--crop-bottom", type=float, default=0.903)
    parser.add_argument("--crop-left", type=float, default=0.0)
    parser.add_argument("--crop-right", type=float, default=1.0)
    args = parser.parse_args()

    crop = (args.crop_left, args.crop_top, args.crop_right, args.crop_bottom)
    if not (0 <= crop[0] < crop[2] <= 1 and 0 <= crop[1] < crop[3] <= 1):
        raise SystemExit("crop values must satisfy 0 <= left < right <= 1 and 0 <= top < bottom <= 1")

    paths = sorted(args.frames_dir.glob("*.jpg"))
    if not paths:
        raise SystemExit(f"no JPG frames found in {args.frames_dir}")

    rows: list[dict] = []
    previous = None
    differences: list[float] = []
    for index, path in enumerate(paths):
        with Image.open(path) as image:
            sig = signature(image, crop)
        difference = 0.0 if previous is None else mean_difference(sig, previous)
        differences.append(difference)
        rows.append({
            "index": index,
            "path": path,
            "time_seconds": frame_time(path, index * args.step),
            "difference": difference,
            "sharpness": sharpness(sig),
            "signature": sig,
        })
        previous = sig

    stable_indices: list[int] = []
    for index in range(len(rows)):
        left_stable = index == 0 or differences[index] < args.stable_threshold
        right_stable = index == len(rows) - 1 or differences[index + 1] < args.stable_threshold
        if left_stable and right_stable:
            stable_indices.append(index)

    groups: list[list[int]] = []
    for index in stable_indices:
        if not groups or index > groups[-1][-1] + 1:
            groups.append([index])
        else:
            groups[-1].append(index)

    if not groups:
        stride = max(1, round(1.0 / args.step))
        groups = [[index] for index in range(0, len(rows), stride)]

    candidates = [max(group, key=lambda index: rows[index]["sharpness"]) for group in groups]
    selected: list[tuple[int, list[int]]] = []
    for candidate, group in zip(candidates, groups):
        if selected:
            previous_candidate = selected[-1][0]
            duplicate_difference = mean_difference(
                rows[candidate]["signature"], rows[previous_candidate]["signature"]
            )
            if duplicate_difference < args.dedup_threshold:
                if rows[candidate]["sharpness"] > rows[previous_candidate]["sharpness"]:
                    selected[-1] = (candidate, group)
                continue
        selected.append((candidate, group))

    pages_dir = args.output_dir / "pages"
    full_dir = args.output_dir / "full_frames"
    pages_dir.mkdir(parents=True, exist_ok=True)
    full_dir.mkdir(parents=True, exist_ok=True)

    manifest: list[dict] = []
    page_paths: list[Path] = []
    for page_number, (chosen, group) in enumerate(selected, start=1):
        source = rows[chosen]["path"]
        full_output = full_dir / f"page_{page_number:03d}.jpg"
        page_output = pages_dir / f"page_{page_number:03d}.jpg"
        shutil.copy2(source, full_output)
        with Image.open(source) as image:
            cropped = normalized_crop(image, *crop).convert("RGB")
            cropped.save(page_output, quality=95)
        page_paths.append(page_output)
        manifest.append({
            "page": page_number,
            "source_frame": source.name,
            "time_seconds": f"{rows[chosen]['time_seconds']:.3f}",
            "stable_run_start": group[0],
            "stable_run_end": group[-1],
            "sharpness": f"{rows[chosen]['sharpness']:.4f}",
        })

    with (args.output_dir / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest[0]))
        writer.writeheader()
        writer.writerows(manifest)

    make_contact_sheet(page_paths, args.output_dir / "pages_contact_sheet.jpg")
    summary = {
        "sampled_frames": len(rows),
        "stable_runs": len(groups),
        "selected_pages": len(selected),
        "step_seconds": args.step,
        "stable_threshold": args.stable_threshold,
        "dedup_threshold": args.dedup_threshold,
        "crop": {"left": crop[0], "top": crop[1], "right": crop[2], "bottom": crop[3]},
    }
    (args.output_dir / "selection_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
