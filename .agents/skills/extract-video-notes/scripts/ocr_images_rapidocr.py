#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
from typing import Any


def as_list(value: Any) -> list:
    if value is None:
        return []
    if hasattr(value, "tolist"):
        return value.tolist()
    return list(value)


def reading_position(box: Any) -> tuple[float, float]:
    points = as_list(box)
    if not points:
        return (float("inf"), float("inf"))
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    return (min(ys), min(xs))


def main() -> None:
    parser = argparse.ArgumentParser(description="OCR image pages with RapidOCR and ONNX Runtime.")
    parser.add_argument("images_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    try:
        from rapidocr import RapidOCR
    except ImportError as error:
        raise SystemExit(
            "RapidOCR is required. Install Windows dependencies with: "
            "py -m pip install -r requirements-windows.txt"
        ) from error

    image_paths = sorted(
        path for path in args.images_dir.iterdir()
        if path.suffix.lower() in {".jpg", ".jpeg", ".png"}
    )
    if not image_paths:
        raise SystemExit(f"no images found in {args.images_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    engine = RapidOCR()
    metadata: list[dict] = []
    failures: list[str] = []
    processed = 0

    for image_path in image_paths:
        try:
            result = engine(str(image_path), use_det=True, use_cls=True, use_rec=True)
            texts = [str(item) for item in as_list(getattr(result, "txts", None))]
            scores = [float(item) for item in as_list(getattr(result, "scores", None))]
            boxes = as_list(getattr(result, "boxes", None))

            records = []
            for index, text in enumerate(texts):
                score = scores[index] if index < len(scores) else 0.0
                box = boxes[index] if index < len(boxes) else None
                records.append((reading_position(box), text, score))
            records.sort(key=lambda item: item[0])

            text = "\n".join(record[1] for record in records)
            output_path = args.output_dir / f"{image_path.stem}.txt"
            output_path.write_text(text, encoding="utf-8")
            average = sum(record[2] for record in records) / len(records) if records else 0.0
            metadata.append({
                "image": image_path.name,
                "lines": len(records),
                "average_confidence": average,
            })
            processed += 1
        except Exception as error:
            failures.append(f"{image_path.name}: {error}")

    payload = {
        "backend": "rapidocr",
        "rapidocr_version": importlib.metadata.version("rapidocr"),
        "images_processed": processed,
        "images_failed": len(failures),
        "failures": failures,
        "pages": metadata,
    }
    (args.output_dir / "ocr_metadata.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({
        "backend": "rapidocr",
        "images_processed": processed,
        "images_failed": len(failures),
    }, ensure_ascii=False))
    if processed == 0:
        raise SystemExit("all RapidOCR requests failed; inspect ocr_metadata.json")


if __name__ == "__main__":
    main()
