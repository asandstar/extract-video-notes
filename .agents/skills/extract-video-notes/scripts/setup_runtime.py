#!/usr/bin/env python3
from __future__ import annotations

import argparse
import platform
import subprocess
import sys
import venv
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent.parent
VENV_DIR = SKILL_DIR / ".venv"


def venv_python() -> Path:
    if platform.system() == "Windows":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def run(command: list[str]) -> None:
    print("$ " + " ".join(command), flush=True)
    subprocess.run(command, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create an isolated Python runtime for extract-video-notes."
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="clear and recreate the virtual environment without deleting other skill files",
    )
    args = parser.parse_args()

    if sys.version_info < (3, 9):
        raise SystemExit("Python 3.9 or newer is required")

    requirements_name = (
        "requirements-windows.txt" if platform.system() == "Windows" else "requirements-macos.txt"
    )
    requirements = SKILL_DIR / requirements_name
    if not requirements.exists():
        raise SystemExit(f"requirements file is missing: {requirements}")

    print(f"Creating runtime at: {VENV_DIR}")
    builder = venv.EnvBuilder(with_pip=True, clear=args.recreate)
    builder.create(VENV_DIR)
    python = venv_python()
    if not python.exists():
        raise SystemExit(f"virtual-environment Python was not created: {python}")

    run([str(python), "-m", "pip", "install", "-r", str(requirements)])
    run([str(python), str(SKILL_DIR / "scripts" / "doctor.py"), "--skip-ollama"])
    print("Runtime is ready. Ollama remains optional.")


if __name__ == "__main__":
    main()
