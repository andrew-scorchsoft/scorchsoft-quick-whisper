#!/usr/bin/env python3
"""
Internationalization (i18n) tools for Quick Whisper.

This script provides utilities for managing translations:
- Extract translatable strings from Python source files
- Update .po files with new strings
- Compile .po files to .mo binary format

Usage:
    python tools/i18n_tools.py extract    # Extract strings to .pot template
    python tools/i18n_tools.py update     # Update all .po files from .pot
    python tools/i18n_tools.py compile    # Compile all .po files to .mo
    python tools/i18n_tools.py all        # Run all steps

Requirements:
    - gettext tools (xgettext, msgmerge, msgfmt) must be installed
    - On Ubuntu/Debian: sudo apt install gettext
    - On macOS: brew install gettext && brew link gettext --force
    - On Windows: Install gettext from https://mlocati.github.io/articles/gettext-iconv-windows.html
"""

import os
import subprocess
import sys
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
LOCALE_DIR = PROJECT_ROOT / "locale"
POT_FILE = LOCALE_DIR / "quickwhisper.pot"
DOMAIN = "quickwhisper"

# Source directories to scan
SOURCE_DIRS = [
    PROJECT_ROOT / "utils",
    PROJECT_ROOT,  # For quick_whisper.py entry point
]

# Supported languages
LANGUAGES = ["en", "fr", "de", "es", "zh_CN", "ar"]


def run_command(cmd: list, description: str) -> bool:
    """Run a command and return success status."""
    print(f"  {description}...")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )
        if result.returncode != 0:
            print(f"    Error: {result.stderr}")
            return False
        return True
    except FileNotFoundError:
        print(f"    Error: Command not found: {cmd[0]}")
        print("    Make sure gettext tools are installed.")
        return False


def extract_strings():
    """Extract translatable strings from Python source files to .pot template."""
    print("\n[1/3] Extracting translatable strings...")

    # Collect all Python files
    py_files = []
    for source_dir in SOURCE_DIRS:
        if source_dir.is_dir():
            for py_file in source_dir.glob("**/*.py"):
                # Skip __pycache__ and venv directories
                if "__pycache__" not in str(py_file) and "venv" not in str(py_file):
                    py_files.append(str(py_file.relative_to(PROJECT_ROOT)))
        elif source_dir.is_file() and source_dir.suffix == ".py":
            py_files.append(str(source_dir.relative_to(PROJECT_ROOT)))

    if not py_files:
        print("  No Python files found!")
        return False

    print(f"  Found {len(py_files)} Python files")

    # Create locale directory if it doesn't exist
    LOCALE_DIR.mkdir(parents=True, exist_ok=True)

    # Run xgettext to extract strings
    # Using _() and _n() as marker functions
    cmd = [
        "xgettext",
        "--language=Python",
        "--keyword=_",
        "--keyword=_n:1,2",
        "--keyword=gettext_func",
        "--keyword=ngettext_func:1,2",
        f"--output={POT_FILE}",
        "--from-code=UTF-8",
        "--add-comments=TRANSLATORS:",
        "--package-name=QuickWhisper",
        "--package-version=2.0",
        "--msgid-bugs-address=support@scorchsoft.com",
    ] + py_files

    success = run_command(cmd, "Running xgettext")

    if success and POT_FILE.exists():
        print(f"  Created: {POT_FILE}")
        # Count strings
        with open(POT_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
            msgid_count = content.count('msgid "') - 1  # Subtract header
            print(f"  Extracted {msgid_count} translatable strings")

    return success


def update_po_files():
    """Update all .po files from the .pot template."""
    print("\n[2/3] Updating .po files...")

    if not POT_FILE.exists():
        print(f"  Error: Template file not found: {POT_FILE}")
        print("  Run 'extract' first to create the template.")
        return False

    success = True
    for lang in LANGUAGES:
        po_dir = LOCALE_DIR / lang / "LC_MESSAGES"
        po_file = po_dir / f"{DOMAIN}.po"

        po_dir.mkdir(parents=True, exist_ok=True)

        if po_file.exists():
            # Merge with existing translations
            cmd = [
                "msgmerge",
                "--update",
                "--backup=none",
                str(po_file),
                str(POT_FILE)
            ]
            if not run_command(cmd, f"Updating {lang}"):
                success = False
        else:
            # Create new .po file from template
            cmd = [
                "msginit",
                "--input", str(POT_FILE),
                "--output-file", str(po_file),
                "--locale", lang,
                "--no-translator"
            ]
            if not run_command(cmd, f"Creating {lang}"):
                # Fallback: just copy the .pot file
                print(f"    Fallback: copying template to {po_file}")
                try:
                    import shutil
                    shutil.copy(POT_FILE, po_file)
                except Exception as e:
                    print(f"    Error: {e}")
                    success = False

    return success


def compile_po_files():
    """Compile all .po files to .mo binary format."""
    print("\n[3/3] Compiling .po files to .mo...")

    success = True
    for lang in LANGUAGES:
        po_file = LOCALE_DIR / lang / "LC_MESSAGES" / f"{DOMAIN}.po"
        mo_file = LOCALE_DIR / lang / "LC_MESSAGES" / f"{DOMAIN}.mo"

        if not po_file.exists():
            print(f"  Skipping {lang}: .po file not found")
            continue

        cmd = [
            "msgfmt",
            "--output-file", str(mo_file),
            str(po_file)
        ]

        if run_command(cmd, f"Compiling {lang}"):
            print(f"    Created: {mo_file}")
        else:
            success = False

    return success


def compile_single(lang: str):
    """Compile a single language's .po file to .mo."""
    po_file = LOCALE_DIR / lang / "LC_MESSAGES" / f"{DOMAIN}.po"
    mo_file = LOCALE_DIR / lang / "LC_MESSAGES" / f"{DOMAIN}.mo"

    if not po_file.exists():
        print(f"Error: .po file not found: {po_file}")
        return False

    cmd = [
        "msgfmt",
        "--output-file", str(mo_file),
        str(po_file)
    ]

    return run_command(cmd, f"Compiling {lang}")


def check_tools():
    """Check if required gettext tools are available."""
    tools = ["xgettext", "msgmerge", "msgfmt"]
    missing = []

    for tool in tools:
        try:
            subprocess.run([tool, "--version"], capture_output=True)
        except FileNotFoundError:
            missing.append(tool)

    if missing:
        print("Error: Missing required tools:", ", ".join(missing))
        print("\nInstall gettext tools:")
        print("  Ubuntu/Debian: sudo apt install gettext")
        print("  macOS: brew install gettext && brew link gettext --force")
        print("  Windows: https://mlocati.github.io/articles/gettext-iconv-windows.html")
        return False

    return True


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "check":
        if check_tools():
            print("All required tools are available.")
        sys.exit(0)

    if not check_tools():
        sys.exit(1)

    if command == "extract":
        success = extract_strings()
    elif command == "update":
        success = update_po_files()
    elif command == "compile":
        success = compile_po_files()
    elif command == "all":
        success = extract_strings() and update_po_files() and compile_po_files()
    elif command == "compile-single" and len(sys.argv) > 2:
        success = compile_single(sys.argv[2])
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)

    if success:
        print("\nDone!")
    else:
        print("\nCompleted with errors.")
        sys.exit(1)


if __name__ == "__main__":
    main()
