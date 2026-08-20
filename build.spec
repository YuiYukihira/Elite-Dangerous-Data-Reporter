# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src/eddr/__init__.py'],
    pathex=[],
    binaries=[],
    datas=[('src/eddr/plugins', 'plugins'), ('src/eddr/JournalReader.py', 'eddr')],
    hiddenimports=['sv_ttk', 'humanize', 'requests'],
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
    [],
    exclude_binaries=True,
    name='Elite Dangerous Data Reporter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Elite Dangerous Data Reporter',
)
