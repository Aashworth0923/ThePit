# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for ThePit.exe
# Run:  build.bat  (or  python -m PyInstaller ThePit.spec --clean)
#
# What gets bundled:   Flask app, PyWebView, templates, static files, icon
# What stays external: metal_releases.db, .env, venv\, browsers\, fetch_releases.py
#
# The .exe expects these files to be in the same directory:
#   ThePit.exe
#   metal_releases.db   (your data)
#   .env                (your API keys)
#   fetch_releases.py   (scraper — requires system Python + Playwright)

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates',  'templates'),
        ('static',     'static'),
        ('ThePit.ico', '.'),
    ],
    hiddenimports=[
        'webview.platforms.winforms',
        'clr',
        'engineio.async_drivers.threading',
    ] + collect_submodules('webview'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'playwright',
        'pytest',
        'IPython',
        'notebook',
    ],
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
    name='ThePit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,          # no command prompt window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='ThePit.ico',      # icon embedded in the .exe
)
