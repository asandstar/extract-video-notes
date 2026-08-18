# Cross-platform local video-note pipeline

## Platform routing

| Platform | Frame extraction | OCR |
| --- | --- | --- |
| macOS, MP4/MOV/M4V batch | Swift + AVFoundation | Apple Vision |
| macOS, batch containing an extended format | FFmpeg | Apple Vision |
| Windows | FFmpeg | RapidOCR + ONNX Runtime |

Shared Python code handles stable-page selection, deduplication, cropping, PDF output, OCR cleanup, and Ollama review.

## Requirements

- Python 3.9 or newer.
- Pillow on both platforms.
- macOS: Swift, AVFoundation, and Vision supplied by macOS/Xcode Command Line Tools. FFmpeg is additionally required for extended containers.
- Windows: FFmpeg on `PATH`, plus `rapidocr` and `onnxruntime`.
- Ollama and the requested local model only when model-assisted cleanup is enabled. The default is `qwen3.5:9b`.

No network access or social-platform login is required.

## Input formats

Supported extensions are MP4, MOV, M4V, MKV, AVI, WebM, WMV, MPG, MPEG, TS, MTS, M2TS, 3GP, FLV, OGV, and VOB.

An extension identifies the container, not whether every codec inside it can be decoded. FFmpeg handles the extended containers. Encrypted, DRM-protected, corrupted, or unusual-codec files can still fail and should be converted to MP4/H.264 before retrying.

## Outputs per recording

- `pages/`: cropped, deduplicated note images.
- `full_frames/`: uncropped selected frames for audit.
- `pages_contact_sheet.jpg`: fast visual QA.
- `pages.pdf`: extracted note images in reading order.
- `ocr_pages/`: one raw OCR text file per page.
- `ocr_raw.md`: page-separated audit transcription.
- `ocr_clean.md`: continuous cleaned text without artificial page titles.
- `academic_assessment.md`: local-model screening, omitted with `--skip-ollama`.
- `manifest.csv` and `run_summary.json`: timestamps, parameters, and processing status.

## Useful options

```text
--step 0.25               sample every 0.25 seconds
--stable-threshold 0.010  lower values reject more motion
--dedup-threshold 0.018   lower values retain more similar pages
--crop-top 0.165          crop normalized top edge
--crop-bottom 0.903       crop normalized bottom edge
--crop-left 0.0
--crop-right 1.0
--ollama-model qwen3.5:9b
--skip-ollama
--frame-backend auto      auto | avfoundation | ffmpeg
--ocr-backend auto        auto | vision | rapidocr
--ffmpeg ffmpeg           executable name or full path
```

The crop defaults reproduce the tested vertical Xiaohongshu recording layout. Inspect the contact sheet and adjust cropping for other interfaces.

## Tuning symptoms

- Missing pages: decrease `--step`, increase `--stable-threshold`, or ask the user to pause longer while recording.
- Too many transitional frames: decrease `--stable-threshold`.
- Duplicate pages: increase `--dedup-threshold` slightly.
- Similar pages incorrectly merged: decrease `--dedup-threshold`.
- UI chrome in OCR: adjust the four crop values.
- Ollama unavailable: rerun with `--skip-ollama`; deterministic OCR deliverables remain valid.
- Vision reports `nilError` or cannot create `CVPixelBuffer`: this is commonly a Codex sandbox restriction. Request approval and rerun the pipeline outside the sandbox.
- Windows reports that FFmpeg is missing: install FFmpeg, open a new PowerShell window, and verify `ffmpeg -version`.
- macOS reports that FFmpeg is missing for MKV or another extended container: install FFmpeg, then run `scripts/doctor.py --extended-formats --skip-ollama`.
- Windows reports missing RapidOCR modules: install `requirements-windows.txt` with the same Python interpreter used to run the pipeline.

## Batch use

Pass multiple paths:

```bash
python3 <skill-dir>/scripts/run_pipeline.py video01.mp4 video02.mkv \
  --work-dir ./work/video-notes \
  --output-dir ./outputs/video-notes
```

Do not run many Ollama generations concurrently on a memory-constrained laptop. The batch driver processes videos sequentially.

## Dependency check

Run `scripts/setup_runtime.py` once, then use `scripts/run_pipeline.py` for processing. The setup command creates an isolated `.venv` and runs `scripts/doctor.py --skip-ollama`. Remove `--skip-ollama` from later doctor checks when local model review is required.
