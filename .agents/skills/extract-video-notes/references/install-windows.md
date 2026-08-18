# Windows setup

## Install

1. Install 64-bit Python 3.9 or newer and enable its launcher (`py`).
2. Install FFmpeg and add its `bin` directory to `PATH`. Use a Windows build linked from <https://ffmpeg.org/download.html>.
3. From the skill directory, create the isolated runtime and install the Windows dependencies:

```powershell
py scripts\setup_runtime.py
```

4. Optional: install Ollama and pull the configured model for local cleanup and assessment.

Open a new PowerShell window after changing `PATH`.

## Check

```powershell
ffmpeg -version
.venv\Scripts\python.exe scripts\doctor.py --skip-ollama
```

Remove `--skip-ollama` when Ollama and `qwen3.5:9b` are installed.

## Run

```powershell
py scripts\run_pipeline.py "D:\Videos\note.mp4" `
  --work-dir ".\work\video-notes" `
  --output-dir ".\outputs\video-notes"
```

For OCR without Ollama cleanup, add `--skip-ollama`.

## Backend behavior

Windows automatically uses FFmpeg for sampling and RapidOCR with ONNX Runtime for Chinese/English OCR. Use `--ffmpeg "C:\path\to\ffmpeg.exe"` only when FFmpeg is not on `PATH`.

`setup_runtime.py` keeps Python packages inside the Skill directory's `.venv`; it does not modify the global Python installation. Package installation needs internet access, while ordinary OCR runs stay local.
