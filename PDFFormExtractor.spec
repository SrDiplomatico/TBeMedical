# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for PDF Form Data Extractor (Windows, one-folder build).

Build with:   pyinstaller PDFFormExtractor.spec --noconfirm
Output:       dist/PDFFormExtractor/PDFFormExtractor.exe  (+ _internal/ folder)

Google Chrome must be installed on the target machine; Playwright's Chromium is
deliberately NOT bundled (saves ~150 MB and a download step).
"""

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).resolve()
APP_NAME = "PDFFormExtractor"

# --- Third-party packages that need their data/binaries collected ---------------
datas, binaries, hiddenimports = [], [], []
for pkg in ("playwright", "pymupdf", "fitz"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# PyMuPDF 2.x ships an optional ML layout engine (~80 MB with onnxruntime) that this app
# never uses; its imports are try/except-guarded upstream, so dropping it is safe.
_DROP = ("pymupdf/layout", "pymupdf\\layout", "pymupdf/mupdf-devel", "pymupdf\\mupdf-devel")
datas = [(src, dst) for (src, dst) in datas if not any(k in dst for k in _DROP)]
binaries = [(src, dst) for (src, dst) in binaries if not any(k in dst for k in _DROP)]
hiddenimports = [h for h in hiddenimports if not h.startswith(("pymupdf.layout", "pymupdf_layout", "pymupdf4llm"))]

# Playwright's Node driver is loaded by path at runtime; make sure the whole tree ships.
import playwright as _pw

driver_dir = Path(_pw.__file__).parent / "driver"
datas.append((str(driver_dir), "playwright/driver"))

# --- Application package and bundled resources -----------------------------------
hiddenimports += collect_submodules("src")
datas += [
    (str(ROOT / "Truly unlocked_i-693.pdf"), "."),
    (str(ROOT / "src" / "automation" / "dropdown_options.json"), "src/automation"),
    (str(ROOT / "src" / "automation" / "discovered_selectors.json"), "src/automation"),
]

block_cipher = None

a = Analysis(
    [str(ROOT / "src" / "main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Dev-only / unused heavy modules
        "pytest", "IPython", "matplotlib", "numpy", "PIL", "pandas",
        # Optional PyMuPDF add-ons not used by this app
        "pymupdf.layout", "pymupdf_layout", "pymupdf4llm", "onnxruntime",
        "networkx", "tabulate", "scipy",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # GUI app: no console window (output goes to %LOCALAPPDATA% logs)
    disable_windowed_traceback=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name=APP_NAME,
)
