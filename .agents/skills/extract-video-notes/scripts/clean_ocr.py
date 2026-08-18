#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


PAGE_FILE_RE = re.compile(r"page[_-]?(\d+)", re.IGNORECASE)
SPACE_RE = re.compile(r"[ \t\u3000]+")
CHINESE_RE = re.compile(r"[\u3400-\u9fff]")
SENTENCE_END = set("。！？!?；;：:…")
LIST_RE = re.compile(r"^(?:[-*•·]|\d+[.)、]|[一二三四五六七八九十]+[、.])\s*")


def page_number(path: Path) -> int:
    match = PAGE_FILE_RE.search(path.stem)
    return int(match.group(1)) if match else 10**9


def normalize_line(line: str) -> str:
    return SPACE_RE.sub(" ", line.strip())


def is_heading(line: str) -> bool:
    if not line or len(line) > 34 or LIST_RE.match(line):
        return False
    return line[-1] not in SENTENCE_END and not line.endswith((",", "，", "."))


def should_join(previous: str, current: str) -> bool:
    if not previous or not current:
        return False
    if previous[-1] in SENTENCE_END or LIST_RE.match(current) or is_heading(previous):
        return False
    return True


def join_lines(text: str) -> str:
    raw_lines = [normalize_line(line) for line in text.replace("\r\n", "\n").split("\n")]
    paragraphs: list[str] = []
    current = ""
    for line in raw_lines:
        if not line:
            if current:
                paragraphs.append(current)
                current = ""
            continue
        if not current:
            current = line
        elif should_join(current, line):
            separator = "" if CHINESE_RE.search(current[-1:]) or CHINESE_RE.search(line[:1]) else " "
            current += separator + line
        else:
            paragraphs.append(current)
            current = line
    if current:
        paragraphs.append(current)
    return "\n\n".join(paragraphs)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create raw and deterministic clean OCR documents.")
    parser.add_argument("ocr_dir", type=Path)
    parser.add_argument("--raw-out", type=Path, required=True)
    parser.add_argument("--clean-out", type=Path, required=True)
    parser.add_argument("--title", default="录屏笔记 OCR 全文")
    args = parser.parse_args()

    paths = sorted(args.ocr_dir.glob("page*.txt"), key=page_number)
    if not paths:
        raise SystemExit(f"no page OCR text found in {args.ocr_dir}")

    raw_sections = [f"# {args.title}（原始识别）"]
    clean_sections = [f"# {args.title}"]
    for index, path in enumerate(paths, start=1):
        text = path.read_text(encoding="utf-8").strip()
        raw_sections.append(f"## 原图页 {index}\n\n{text}")
        cleaned = join_lines(text)
        if cleaned:
            clean_sections.append(cleaned)

    args.raw_out.parent.mkdir(parents=True, exist_ok=True)
    args.clean_out.parent.mkdir(parents=True, exist_ok=True)
    args.raw_out.write_text("\n\n".join(raw_sections).rstrip() + "\n", encoding="utf-8")
    args.clean_out.write_text("\n\n".join(clean_sections).rstrip() + "\n", encoding="utf-8")
    print(f"pages={len(paths)} raw={args.raw_out} clean={args.clean_out}")


if __name__ == "__main__":
    main()
