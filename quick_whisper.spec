# -*- mode: python ; coding: utf-8 -*-
import platform
import os
import sys
from PyInstaller.utils.hooks import collect_submodules

# Determine current platform
system = platform.system()

# Get the spec file directory (project root)
SPEC_ROOT = os.path.abspath(SPECPATH)

# Add project root to sys.path BEFORE collecting submodules
# so PyInstaller can find the local 'utils' package
if SPEC_ROOT not in sys.path:
    sys.path.insert(0, SPEC_ROOT)

# Collect all submodules from the local utils package
utils_imports = collect_submodules('utils')
# Explicitly add utils.quick_whisper in case collect_submodules misses it
if 'utils.quick_whisper' not in utils_imports:
    utils_imports.append('utils.quick_whisper')

# Base hidden imports (cross-platform)
hidden_imports = [
    'PIL._tkinter_finder',
    'pyttsx3.drivers',
    # pynput backends
    'pynput.keyboard',
    'pynput.mouse',
    # pyautogui (lazy imported in paste methods)
    'pyautogui',
]

# Add local utils package imports
hidden_imports.extend(utils_imports)

# Platform-specific hidden imports
if system == 'Windows':
    hidden_imports.extend([
        'pystray._win32',
        'pyttsx3.drivers.sapi5',
        'pynput.keyboard._win32',
        'pynput.mouse._win32',
        'pyautogui._pyautogui_win',
    ])
elif system == 'Darwin':
    hidden_imports.extend([
        'pystray._darwin',
        'pyttsx3.drivers.nsss',
        'pynput.keyboard._darwin',
        'pynput.mouse._darwin',
        'pyautogui._pyautogui_osx',
    ])
else:  # Linux
    hidden_imports.extend([
        'pystray._xorg',
        'pyttsx3.drivers.espeak',
        'pynput.keyboard._xorg',
        'pynput.mouse._xorg',
        'pyautogui._pyautogui_x11',
    ])

# Icon handling - different formats per platform
if system == 'Windows':
    icon_file = ['assets/icon.ico']
elif system == 'Darwin':
    # macOS uses .icns format; fall back to .ico if .icns doesn't exist
    if os.path.exists('assets/icon.icns'):
        icon_file = ['assets/icon.icns']
    else:
        icon_file = ['assets/icon.ico']
else:  # Linux
    # Linux typically doesn't use icon in the executable
    icon_file = []

a = Analysis(
    ['quick_whisper.py'],
    pathex=[SPEC_ROOT],
    binaries=[],
    datas=[('assets', 'assets'), ('locale', 'locale')],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='quick_whisper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    # Set console=True temporarily to see stdout/stderr when running the EXE
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file if icon_file else None,
)
