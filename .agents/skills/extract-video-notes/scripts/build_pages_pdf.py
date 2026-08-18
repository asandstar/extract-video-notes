#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a compact image PDF from extracted note pages.")
    parser.add_argument("images_dir", type=Path)
    parser.add_argument("output_pdf", type=Path)
    args = parser.parse_args()

    paths = sorted(args.images_dir.glob("*.jpg"))
    if not paths:
        raise SystemExit(f"no JPG pages found in {args.images_dir}")

    images = []
    for path in paths:
        with Image.open(path) as image:
            images.append(image.convert("RGB").copy())

    args.output_pdf.parent.mkdir(parents=True, exist_ok=True)
    first, rest = images[0], images[1:]
    first.save(args.output_pdf, "PDF", save_all=True, append_images=rest, resolution=150.0)
    for image in images:
        image.close()
    print(args.output_pdf)


if __name__ == "__main__":
    main()
