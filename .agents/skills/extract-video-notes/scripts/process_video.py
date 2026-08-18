#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


SCRIPT_DIR = Path(__file__).resolve().parent
AVFOUNDATION_SUFFIXES = {".mp4", ".mov", ".m4v"}
VIDEO_SUFFIXES = AVFOUNDATION_SUFFIXES | {
    ".3gp",
    ".avi",
    ".flv",
    ".m2ts",
    ".mkv",
    ".mpg",
    ".mpeg",
    ".mts",
    ".ogv",
    ".ts",
    ".vob",
    ".webm",
    ".wmv",
}


def run(command: list[str], env: Optional[dict[str, str]] = None) -> str:
    printable = " ".join(command)
    print(f"\n$ {printable}", flush=True)
    result = subprocess.run(command, text=True, capture_output=True, env=env, check=False)
    if result.stdout.strip():
        print(result.stdout.rstrip(), flush=True)
    if result.stderr.strip():
        print(result.stderr.rstrip(), file=sys.stderr, flush=True)
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, command, output=result.stdout, stderr=result.stderr
        )
    return result.stdout


def safe_name(stem: str) -> str:
    cleaned = re.sub(r"[^\w\-\u3400-\u9fff]+", "-", stem, flags=re.UNICODE).strip("-_")
    return (cleaned or "video-note")[:80]


def unique_directory(root: Path, name: str) -> Path:
    candidate = root / name
    counter = 2
    while candidate.exists():
        candidate = root / f"{name}-{counter:02d}"
        counter += 1
    candidate.mkdir(parents=True)
    return candidate


def ensure_pillow_python() -> None:
    try:
        __import__("PIL")
        return
    except ImportError:
        pass

    candidates = [
        Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3",
    ]
    for executable_name in ("python3.12", "python3.11", "python3.10"):
        executable = shutil.which(executable_name)
        if executable:
            candidates.append(Path(executable))
    for candidate in candidates:
        if not candidate.exists() or candidate.resolve() == Path(sys.executable).resolve():
            continue
        probe = subprocess.run(
            [str(candidate), "-c", "import PIL"], text=True, capture_output=True, check=False
        )
        if probe.returncode == 0:
            os.execv(str(candidate), [str(candidate), str(Path(__file__).resolve()), *sys.argv[1:]])
    raise RuntimeError("Pillow is required; install it with: python3 -m pip install Pillow")


def resolve_executable(value: str) -> Optional[str]:
    candidate = Path(value)
    if candidate.parent != Path(".") or candidate.is_absolute():
        return str(candidate.resolve()) if candidate.exists() else None
    return shutil.which(value)


def resolve_backends(args: argparse.Namespace, videos: list[Path]) -> tuple[str, str]:
    system = platform.system()
    frame_backend = args.frame_backend
    if frame_backend == "auto":
        use_native_macos = system == "Darwin" and all(
            video.suffix.lower() in AVFOUNDATION_SUFFIXES for video in videos
        )
        frame_backend = "avfoundation" if use_native_macos else "ffmpeg"
    ocr_backend = args.ocr_backend
    if ocr_backend == "auto":
        ocr_backend = "vision" if system == "Darwin" else "rapidocr"

    if frame_backend == "avfoundation" and system != "Darwin":
        raise RuntimeError("the AVFoundation frame backend is available only on macOS")
    if ocr_backend == "vision" and system != "Darwin":
        raise RuntimeError("the Apple Vision OCR backend is available only on macOS")
    return frame_backend, ocr_backend


def ensure_dependencies(args: argparse.Namespace, frame_backend: str, ocr_backend: str) -> None:
    if sys.version_info < (3, 9):
        raise RuntimeError("Python 3.9 or newer is required")
    if frame_backend == "avfoundation" or ocr_backend == "vision":
        if shutil.which("swift") is None:
            raise RuntimeError("Swift is required for the selected macOS backend")
    if frame_backend == "ffmpeg" and resolve_executable(args.ffmpeg) is None:
        raise RuntimeError(
            "FFmpeg is required for the selected frame backend; install it and add ffmpeg to PATH, "
            "or pass --ffmpeg with the executable's full path"
        )
    if ocr_backend == "rapidocr":
        missing = [name for name in ("rapidocr", "onnxruntime") if importlib.util.find_spec(name) is None]
        if missing:
            raise RuntimeError(
                "missing RapidOCR dependencies: " + ", ".join(missing)
                + ". Run: py -m pip install -r requirements-windows.txt"
            )
    if not args.skip_ollama and shutil.which("ollama") is None:
        raise RuntimeError("Ollama is required unless --skip-ollama is used")


def create_research_package(result_dir: Path, title: str) -> None:
    clean = (result_dir / "ocr_clean.md").read_text(encoding="utf-8").strip()
    assessment_path = result_dir / "academic_assessment.md"
    assessment = assessment_path.read_text(encoding="utf-8").strip() if assessment_path.exists() else "尚未运行本地模型初筛。"
    content = f"""# {title}：深入研究材料

## 给研究模型的任务

请把下面的 OCR 正文当作待核验材料，而不是已经证实的事实：

1. 先概括作者的核心论点和论证结构。
2. 区分原文陈述、可核查事实、价值判断和你的推断。
3. 找出文中明确出现的作者、书目、论文、机构和术语，并建议优先核验顺序。
4. 指出论证缺口、可能的反例以及值得深入讨论的问题。
5. 如果能够联网研究，请使用一手论文、原著或机构资料，并给出链接；不要把 OCR 错字当成确定术语。

## 本地模型初筛

{assessment}

## OCR 整理正文

{clean}
"""
    (result_dir / "research_package.md").write_text(content.rstrip() + "\n", encoding="utf-8")


def process_one(video: Path, args: argparse.Namespace, frame_backend: str, ocr_backend: str) -> dict:
    if not video.exists() or not video.is_file():
        raise FileNotFoundError(video)
    if video.suffix.lower() not in VIDEO_SUFFIXES:
        supported = ", ".join(sorted(VIDEO_SUFFIXES))
        raise ValueError(f"unsupported video format: {video.suffix}; supported: {supported}")

    name = safe_name(video.stem)
    result_dir = unique_directory(args.output_dir, name)
    work_dir = args.work_dir / result_dir.name
    frames_dir = work_dir / "sampled_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    swift_env = None
    if frame_backend == "avfoundation" or ocr_backend == "vision":
        swift_cache = work_dir / ".swift-module-cache"
        swift_cache.mkdir(parents=True, exist_ok=True)
        swift_env = os.environ.copy()
        swift_env["SWIFT_MODULECACHE_PATH"] = str(swift_cache)
        swift_env["CLANG_MODULE_CACHE_PATH"] = str(swift_cache)

    if frame_backend == "avfoundation":
        run([
            "swift", str(SCRIPT_DIR / "extract_video_frames.swift"),
            str(video.resolve()), str(frames_dir), str(args.step),
        ], env=swift_env)
    else:
        run([
            sys.executable, str(SCRIPT_DIR / "extract_video_frames_ffmpeg.py"),
            str(video.resolve()), str(frames_dir), str(args.step),
            "--ffmpeg", str(resolve_executable(args.ffmpeg)),
        ])

    run([
        sys.executable, str(SCRIPT_DIR / "select_pages.py"),
        str(frames_dir), str(result_dir),
        "--step", str(args.step),
        "--stable-threshold", str(args.stable_threshold),
        "--dedup-threshold", str(args.dedup_threshold),
        "--crop-top", str(args.crop_top),
        "--crop-bottom", str(args.crop_bottom),
        "--crop-left", str(args.crop_left),
        "--crop-right", str(args.crop_right),
    ])

    ocr_dir = result_dir / "ocr_pages"
    if ocr_backend == "vision":
        run([
            "swift", str(SCRIPT_DIR / "ocr_images.swift"),
            str(result_dir / "pages"), str(ocr_dir),
        ], env=swift_env)
    else:
        run([
            sys.executable, str(SCRIPT_DIR / "ocr_images_rapidocr.py"),
            str(result_dir / "pages"), str(ocr_dir),
        ])

    raw_path = result_dir / "ocr_raw.md"
    draft_path = result_dir / "ocr_draft.md"
    clean_path = result_dir / "ocr_clean.md"
    title = video.stem
    run([
        sys.executable, str(SCRIPT_DIR / "clean_ocr.py"), str(ocr_dir),
        "--raw-out", str(raw_path),
        "--clean-out", str(draft_path),
        "--title", title,
    ])

    if not args.skip_pdf:
        run([
            sys.executable, str(SCRIPT_DIR / "build_pages_pdf.py"),
            str(result_dir / "pages"), str(result_dir / "pages.pdf"),
        ])

    model_status = "skipped"
    if args.skip_ollama:
        shutil.copy2(draft_path, clean_path)
    else:
        try:
            run([
                sys.executable, str(SCRIPT_DIR / "ollama_review.py"), str(ocr_dir),
                "--clean-out", str(clean_path),
                "--assessment-out", str(result_dir / "academic_assessment.md"),
                "--model", args.ollama_model,
                "--timeout", str(args.ollama_timeout),
                "--title", title,
            ])
            model_status = f"completed: {args.ollama_model}"
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            shutil.copy2(draft_path, clean_path)
            model_status = f"failed, deterministic draft used: {error}"
            (result_dir / "academic_assessment.md").write_text(
                "# 学术价值评估\n\n本地模型处理失败，尚未完成自动初筛。\n\n"
                f"错误：`{error}`\n",
                encoding="utf-8",
            )

    create_research_package(result_dir, title)
    selection = json.loads((result_dir / "selection_summary.json").read_text(encoding="utf-8"))
    summary = {
        "source_video": str(video.resolve()),
        "result_directory": str(result_dir.resolve()),
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "selected_pages": selection["selected_pages"],
        "sampled_frames": selection["sampled_frames"],
        "ocr_characters": len(clean_path.read_text(encoding="utf-8")),
        "ollama": model_status,
        "platform": platform.system(),
        "frame_backend": frame_backend,
        "ocr_backend": ocr_backend,
        "parameters": {
            "step": args.step,
            "stable_threshold": args.stable_threshold,
            "dedup_threshold": args.dedup_threshold,
            "crop": [args.crop_left, args.crop_top, args.crop_right, args.crop_bottom],
        },
    }
    (result_dir / "run_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract stable pages, OCR text, and research notes from screen recordings.")
    parser.add_argument("videos", nargs="+", type=Path)
    parser.add_argument("--work-dir", type=Path, default=Path("work/video-notes"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/video-notes"))
    parser.add_argument("--step", type=float, default=0.25)
    parser.add_argument("--stable-threshold", type=float, default=0.010)
    parser.add_argument("--dedup-threshold", type=float, default=0.018)
    parser.add_argument("--crop-top", type=float, default=0.165)
    parser.add_argument("--crop-bottom", type=float, default=0.903)
    parser.add_argument("--crop-left", type=float, default=0.0)
    parser.add_argument("--crop-right", type=float, default=1.0)
    parser.add_argument("--ollama-model", default="qwen3.5:9b")
    parser.add_argument("--ollama-timeout", type=int, default=600)
    parser.add_argument("--frame-backend", choices=("auto", "avfoundation", "ffmpeg"), default="auto")
    parser.add_argument("--ocr-backend", choices=("auto", "vision", "rapidocr"), default="auto")
    parser.add_argument("--ffmpeg", default="ffmpeg", help="FFmpeg executable name or full path")
    parser.add_argument("--skip-ollama", action="store_true")
    parser.add_argument("--skip-pdf", action="store_true")
    args = parser.parse_args()

    if args.step <= 0:
        parser.error("--step must be positive")
    args.work_dir = args.work_dir.resolve()
    args.output_dir = args.output_dir.resolve()
    unsupported = sorted({video.suffix.lower() or "[no extension]" for video in args.videos} - VIDEO_SUFFIXES)
    if unsupported:
        parser.error(
            "unsupported video format(s): " + ", ".join(unsupported)
            + "; supported: " + ", ".join(sorted(VIDEO_SUFFIXES))
        )
    ensure_pillow_python()
    args.work_dir.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    frame_backend, ocr_backend = resolve_backends(args, args.videos)
    ensure_dependencies(args, frame_backend, ocr_backend)

    results: list[dict] = []
    errors: list[tuple[Path, str]] = []
    for index, video in enumerate(args.videos, start=1):
        print(f"\n=== Video {index}/{len(args.videos)}: {video} ===", flush=True)
        try:
            results.append(process_one(video, args, frame_backend, ocr_backend))
        except Exception as error:
            errors.append((video, str(error)))
            print(f"ERROR: {video}: {error}", file=sys.stderr, flush=True)

    index_lines = ["# 录屏笔记批处理索引", ""]
    for item in results:
        result_path = Path(item["result_directory"])
        relative = result_path.relative_to(args.output_dir)
        index_lines.extend([
            f"## {relative.name}", "",
            f"- 提取页面：{item['selected_pages']}",
            f"- OCR 字符：{item['ocr_characters']}",
            f"- 运行平台：{item['platform']}",
            f"- 后端：{item['frame_backend']} + {item['ocr_backend']}",
            f"- 本地模型：{item['ollama']}",
            f"- 研究材料：[{relative.name}/research_package.md]({relative.name}/research_package.md)",
            f"- 整理全文：[{relative.name}/ocr_clean.md]({relative.name}/ocr_clean.md)",
            "",
        ])
    if errors:
        index_lines.extend(["## 处理失败", ""])
        index_lines.extend(f"- `{video}`：{message}" for video, message in errors)
        index_lines.append("")
    (args.output_dir / "batch_index.md").write_text("\n".join(index_lines), encoding="utf-8")

    print(f"\nCompleted {len(results)} video(s); failed {len(errors)}. Index: {args.output_dir / 'batch_index.md'}")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
