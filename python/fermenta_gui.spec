# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the fermenta Tkinter app.
#   build:  pyinstaller fermenta_gui.spec        (or run build_app.bat)
#   output: dist/fermenta.exe   (single-file, windowed)
import os
from PyInstaller.utils.hooks import collect_all

here = os.path.abspath(os.getcwd())            # the python/ folder
cpp_dir = os.path.abspath(os.path.join(here, "..", "cpp"))

# --- bundle the JUCE C++ templates so "Export plugin project" works frozen ---
datas = []
if os.path.isdir(cpp_dir):
    for fn in os.listdir(cpp_dir):
        fp = os.path.join(cpp_dir, fn)
        if os.path.isfile(fp):
            datas.append((fp, "cpp_templates"))   # -> _MEIPASS/cpp_templates/<fn>

# --- matplotlib needs its data files + tk backend at runtime ---
mpl_datas, mpl_bins, mpl_hidden = collect_all("matplotlib")
datas += mpl_datas

hiddenimports = mpl_hidden + [
    "matplotlib.backends.backend_tkagg",
    "numpy",
]

a = Analysis(
    ["app_launcher.py"],
    pathex=[here],
    binaries=mpl_bins,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["PyQt5", "PyQt6", "PySide2", "PySide6", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="fermenta",
    debug=False,
    strip=False,
    upx=True,
    console=False,          # windowed app (no console)
    disable_windowed_traceback=False,
    icon=None,
)
