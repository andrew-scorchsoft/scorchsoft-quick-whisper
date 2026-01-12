# -*- mode: python ; coding: utf-8 -*-
import platform

# Determine current platform
system = platform.system()

# Base hidden imports (cross-platform)
hidden_imports = [
    'PIL._tkinter_finder',
    'pyttsx3.drivers',
    # pynput backends
    'pynput.keyboard',
    'pynput.mouse',
]

# Platform-specific hidden imports
if system == 'Windows':
    hidden_imports.extend([
        'pystray._win32',
        'pyttsx3.drivers.sapi5',
        'pynput.keyboard._win32',
        'pynput.mouse._win32',
    ])
elif system == 'Darwin':
    hidden_imports.extend([
        'pystray._darwin',
        'pyttsx3.drivers.nsss',
        'pynput.keyboard._darwin',
        'pynput.mouse._darwin',
    ])
else:  # Linux
    hidden_imports.extend([
        'pystray._xorg',
        'pyttsx3.drivers.espeak',
        'pynput.keyboard._xorg',
        'pynput.mouse._xorg',
    ])

# Icon handling - different formats per platform
if system == 'Windows':
    icon_file = ['assets/icon.ico']
elif system == 'Darwin':
    # macOS uses .icns format; fall back to .ico if .icns doesn't exist
    import os
    if os.path.exists('assets/icon.icns'):
        icon_file = ['assets/icon.icns']
    else:
        icon_file = ['assets/icon.ico']
else:  # Linux
    # Linux typically doesn't use icon in the executable
    icon_file = []

a = Analysis(
    ['quick_whisper.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets')],
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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file if icon_file else None,
)
