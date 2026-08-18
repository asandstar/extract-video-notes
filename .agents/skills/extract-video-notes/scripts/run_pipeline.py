#!/usr/bin/env python3
from __future__ import annotations

import os
import platform
import sys
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent.parent
VENV_DIR = SKILL_DIR / ".venv"


def venv_python() -> Path:
    if platform.system() == "Windows":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def main() -> None:
    python = venv_python()
    if not python.exists():
        setup = SKILL_DIR / "scripts" / "setup_runtime.py"
        command = f'py "{setup}"' if platform.system() == "Windows" else f'python3 "{setup}"'
        raise SystemExit(f"Skill runtime is not installed. Run: {command}")
    process = SKILL_DIR / "scripts" / "process_video.py"
    os.execv(str(python), [str(python), str(process), *sys.argv[1:]])


if __name__ == "__main__":
    main()
