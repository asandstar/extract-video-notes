#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def command_available(name: str) -> bool:
    return shutil.which(name) is not None


def executable_available(value: str) -> bool:
    candidate = shutil.which(value)
    if candidate is not None:
        return True
    return bool(value and Path(value).is_file())


def main() -> None:
    parser = argparse.ArgumentParser(description="Check extract-video-notes runtime dependencies.")
    parser.add_argument("--skip-ollama", action="store_true")
    parser.add_argument("--ollama-model", default="qwen3.5:9b")
    parser.add_argument("--frame-backend", choices=("auto", "avfoundation", "ffmpeg"), default="auto")
    parser.add_argument("--ocr-backend", choices=("auto", "vision", "rapidocr"), default="auto")
    parser.add_argument("--ffmpeg", default="ffmpeg", help="FFmpeg executable name or full path")
    args = parser.parse_args()

    system = platform.system()
    frame_backend = args.frame_backend
    if frame_backend == "auto":
        frame_backend = "avfoundation" if system == "Darwin" else "ffmpeg"
    ocr_backend = args.ocr_backend
    if ocr_backend == "auto":
        ocr_backend = "vision" if system == "Darwin" else "rapidocr"

    checks: list[tuple[str, bool, str]] = [
        ("Python >= 3.9", sys.version_info >= (3, 9), platform.python_version()),
        ("Pillow", module_available("PIL"), "installed" if module_available("PIL") else "pip install Pillow"),
    ]
    if frame_backend == "avfoundation":
        checks.append(("Swift / AVFoundation", command_available("swift") and system == "Darwin", "macOS only"))
    else:
        ffmpeg_ok = executable_available(args.ffmpeg)
        checks.append((
            "FFmpeg",
            ffmpeg_ok,
            args.ffmpeg if ffmpeg_ok else "install FFmpeg and add it to PATH, or pass --ffmpeg",
        ))

    if ocr_backend == "vision":
        checks.append(("Apple Vision", command_available("swift") and system == "Darwin", "macOS only"))
    else:
        checks.extend([
            (
                "RapidOCR",
                module_available("rapidocr"),
                "installed" if module_available("rapidocr") else "pip install rapidocr",
            ),
            (
                "ONNX Runtime",
                module_available("onnxruntime"),
                "installed" if module_available("onnxruntime") else "pip install onnxruntime",
            ),
        ])

    if not args.skip_ollama:
        ollama_ok = command_available("ollama")
        detail = "install Ollama or use --skip-ollama"
        if ollama_ok:
            result = subprocess.run(["ollama", "list"], text=True, capture_output=True, timeout=30, check=False)
            ollama_ok = result.returncode == 0 and args.ollama_model in result.stdout
            detail = f"required model: {args.ollama_model}"
        checks.append(("Ollama model", ollama_ok, detail))

    print(f"Platform: {system} {platform.release()}")
    print(f"Frame backend: {frame_backend}")
    print(f"OCR backend: {ocr_backend}\n")
    for label, ok, detail in checks:
        print(f"[{'OK' if ok else 'MISSING'}] {label}: {detail}")
    if not all(ok for _, ok, _ in checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
