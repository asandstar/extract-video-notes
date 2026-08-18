---
name: extract-video-notes
description: Extract user-provided macOS or Windows screen recordings into deduplicated note pages, local OCR text, optional Ollama-corrected prose, and academic-content assessments. Use for common local video formats containing image-heavy notes or document browsing; do not use it to scrape social platforms from account URLs.
---

# Extract Video Notes

Turn local screen recordings into auditable, research-ready material while avoiding direct platform scraping.

## Choose the mode

- For one recording, run `scripts/process_video.py` with that file.
- For a batch, pass all video paths in one command; the script creates one result folder per video plus `batch_index.md`.
- Use `--skip-ollama` when the user wants only deterministic extraction and OCR.
- Use the default local Ollama pass when the user wants cleaned prose and academic screening. Never represent the local model's corrections as exact quotations without checking them against raw OCR or extracted pages.

Before the first run, execute `scripts/setup_runtime.py` with the platform's system Python. It creates an isolated `.venv` inside the skill folder and verifies the required backend. After setup, prefer `scripts/run_pipeline.py` so every run uses that environment.

Read [references/pipeline.md](references/pipeline.md) before running or tuning the pipeline. Read [references/ocr-and-academic-rules.md](references/ocr-and-academic-rules.md) when interpreting OCR, correcting text, or assessing academic depth.

For setup or troubleshooting, read only the relevant platform guide:

- macOS: [references/install-macos.md](references/install-macos.md)
- Windows: [references/install-windows.md](references/install-windows.md)

## Operating constraints

- Work only from recordings or images the user supplied or explicitly placed in scope. Do not log into, crawl, or rapidly browse Xiaohongshu as a substitute.
- Keep the original recording untouched. Put intermediate frames under a work directory and user-facing artifacts under an output directory.
- Prefer deterministic extraction and the platform-native default OCR backend: Apple Vision on macOS, RapidOCR with ONNX Runtime on Windows. Use the local model only for language cleanup and assessment, not for inventing missing passages.
- If text is unreadable, preserve the uncertain wording or mark it `[无法确认]`; do not silently reconstruct it.
- The clean full-text document must use semantic titles found in the note when available. Do not manufacture `第 X 页` headings. Page markers are allowed only in raw audit files.
- Preserve names, dates, numbers, paper titles, URLs, citations, formulas, and technical terms exactly unless the page image supports a correction.
- In Codex's filesystem sandbox, macOS Vision can fail with `nilError` or a `CVPixelBuffer` error even when the OCR code is valid. If that occurs, request approval and rerun the same pipeline command outside the sandbox; do not replace it with platform scraping.

## Run

From the user's workspace, use:

```bash
python3 <skill-dir>/scripts/run_pipeline.py \
  <video.mp4> \
  --work-dir <workspace>/work/video-notes \
  --output-dir <workspace>/outputs/video-notes
```

On Windows, replace `python3` with `py` and use PowerShell path syntax.

For multiple recordings, add more paths before the options. Use absolute paths when recordings come from application temporary folders.

The script selects backends automatically. On macOS it uses AVFoundation for batches containing only MP4/MOV/M4V and FFmpeg when any extended container is present; OCR remains Apple Vision. Override only for testing or troubleshooting with `--frame-backend` and `--ocr-backend`.

## Verify before handoff

1. Inspect `pages_contact_sheet.jpg` for missing pages, scrolling blur, duplicated screens, and bad cropping.
2. Compare a sample of `ocr_clean.md` against `ocr_raw.md` and the corresponding images.
3. Check that the clean document has no page-number headings and that the academic assessment distinguishes source evidence from model inference.
4. Report page count, OCR/model mode, any uncertain sections, and links to the useful deliverables.
