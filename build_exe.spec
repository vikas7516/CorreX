# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for CorreX Windows executable
"""

block_cipher = None

# Collect all data files
added_files = [
    ('assets/icons/*.ico', 'assets/icons'),
    ('correX/requirements.txt', 'correX'),
]

# Hidden imports that PyInstaller might miss
hiddenimports = [
    'google.generativeai',
    'pystray',
    'PIL',
    'PIL._tkinter_finder',
    'keyboard',
    'pyperclip',
    'pywinauto',
    'win32api',
    'win32con',
    'win32gui',
    'win32clipboard',
    'pywintypes',
    'speech_recognition',
    'pyaudio',
]

# Exclude unnecessary large libraries - more aggressive
excludes = [
    'torch',
    'tensorflow',
    'matplotlib',
    'scipy',
    'pandas',
    'notebook',
    'jupyter',
    'IPython',
    'sklearn',
    'pytest',
    'numpy',
    '_pytest',
    'test',
    'tests',
    'testing',
]

a = Analysis(
    ['correX/main.py'],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='CorreX',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icons/CorreX_logo.ico',
)
