#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract evenly sampled JPEG frames with FFmpeg.")
    parser.add_argument("video", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("step_seconds", type=float)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args()

    if args.step_seconds <= 0:
        raise SystemExit("step_seconds must be positive")
    ffmpeg = shutil.which(args.ffmpeg) if Path(args.ffmpeg).name == args.ffmpeg else args.ffmpeg
    if not ffmpeg or not Path(ffmpeg).exists():
        raise SystemExit("FFmpeg was not found. Install it and make sure ffmpeg is on PATH.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_pattern = args.output_dir / "frame_%06d.jpg"
    sampling_fps = 1.0 / args.step_seconds
    command = [
        str(ffmpeg),
        "-hide_banner",
        "-loglevel", "error",
        "-i", str(args.video),
        "-vf", f"fps={sampling_fps:.10f}",
        "-q:v", "2",
        "-start_number", "0",
        str(output_pattern),
    ]
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or f"FFmpeg exited with code {result.returncode}")

    frames = sorted(args.output_dir.glob("frame_*.jpg"))
    if not frames:
        raise SystemExit("FFmpeg completed but produced no frames")
    summary = {
        "backend": "ffmpeg",
        "video": str(args.video.resolve()),
        "step_seconds": args.step_seconds,
        "sampling_fps": sampling_fps,
        "frames_extracted": len(frames),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
