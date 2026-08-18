# macOS setup

## Install

1. Use macOS with Xcode Command Line Tools so `swift` is available.
2. From the skill directory, create the isolated runtime and install its dependency:

```bash
python3 scripts/setup_runtime.py
```

3. Optional: install Ollama and pull the configured model for local cleanup and assessment.
4. To process MKV, AVI, WebM, WMV, MPEG/TS, or other extended containers, install FFmpeg and make sure `ffmpeg` is on `PATH`. MP4/MOV/M4V do not require it.

## Check

```bash
.venv/bin/python scripts/doctor.py --skip-ollama
```

Remove `--skip-ollama` when Ollama and `qwen3.5:9b` are installed.

Check extended-format support separately:

```bash
.venv/bin/python scripts/doctor.py --extended-formats --skip-ollama
```

## Run

```bash
python3 scripts/run_pipeline.py /absolute/path/video.mp4 \
  --work-dir ./work/video-notes \
  --output-dir ./outputs/video-notes
```

If Apple Vision fails with `nilError` or a `CVPixelBuffer` error inside Codex, approve running the same command outside the sandbox. The recording remains local.

If `swift` is missing, run `xcode-select --install`, finish the installer, and retry the setup check.
