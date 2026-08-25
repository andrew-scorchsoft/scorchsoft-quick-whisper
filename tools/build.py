#!/usr/bin/env python3
"""
Build Quick Whisper standalone executables with PyInstaller.

Usage:
    python tools/build.py              # windowed release build
    python tools/build.py --console    # console-enabled diagnostic build

Output names follow the GitHub release pattern, using the same version as the app:
    dist/quick_whisper-2.2.1-windows-x86_64.exe
    dist/quick_whisper-2.2.1-windows-x86_64-console_enabled.exe
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description="Build Quick Whisper with PyInstaller")
    parser.add_argument(
        "--console",
        action="store_true",
        help="Build a console-enabled diagnostic executable",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean PyInstaller cache before building",
    )
    args = parser.parse_args()

    env = os.environ.copy()
    env["QW_CONSOLE"] = "1" if args.console else "0"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        str(PROJECT_ROOT / "quick_whisper.spec"),
    ]
    if args.clean:
        cmd.insert(-1, "--clean")

    raise SystemExit(subprocess.call(cmd, cwd=PROJECT_ROOT, env=env))


if __name__ == "__main__":
    main()
