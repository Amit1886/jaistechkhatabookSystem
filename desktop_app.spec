# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules


block_cipher = None

# Help PyInstaller hooks import Django-related modules without crashing on
# "settings are not configured" errors.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "khatapro.settings")


project_packages = [
    "khatapro",
    # Admin UI theme (templates + static). Must be bundled for PyInstaller builds.
    "jazzmin",
    "accounts",
    "khataapp",
    "core_settings",
    "sms_center",
    "mobileapi",
    "chatbot",
    "commerce",
    "ledger",
    "billing",
    "system_mode",
    # AI & automation modules (templates + static required in desktop build)
    "whatsapp",
    "ai_ocr",
    "voice",
    "ai_insights",
    "validation",
    "bank_import",
    # Customer & Supplier self-service portal
    "portal",
    # Procurement modules
    "procurement",
    # Smart Khata (credit score + reminders)
    "smart_khata",
    "users",
    "pos",
    "printer_config",
    "scanner_config",
    "warehouse",
    "products",
    "orders",
    "commission",
    "delivery",
    "payments",
    "analytics",
    "ai_engine",
    "realtime",
    "reports",
    "addons",
]


datas = [
    ("templates", "templates"),
    ("static", "static"),
    ("static/img/logo.png", "static/img"),
    ("static/img/favicon.ico", "static/img"),
    (".env", "."),
    ("db.sqlite3", "."),
]

hiddenimports = []

def _add_tcl_tk_datas(d):
    """
    Ensure Tcl/Tk script libraries are bundled for tkinter.

    Without these, the PyInstaller runtime hook `pyi_rth__tkinter.py` can crash at
    startup with:
      FileNotFoundError: Tcl data directory "...\\_internal\\_tcl_data" not found.
    """
    try:
        tcl_root = (Path(sys.base_prefix) / "tcl").resolve()
        if not tcl_root.exists():
            return d

        # Typical Windows layout:
        #   <python>\tcl\tcl8.6
        #   <python>\tcl\tk8.6
        tcl_dirs = sorted(tcl_root.glob("tcl8.*"), reverse=True)
        tk_dirs = sorted(tcl_root.glob("tk8.*"), reverse=True)
        if tcl_dirs:
            d.append((str(tcl_dirs[0]), "_tcl_data"))
        if tk_dirs:
            d.append((str(tk_dirs[0]), "_tk_data"))
    except Exception:
        pass
    return d

datas = _add_tcl_tk_datas(datas)

for pkg in project_packages:
    try:
        hiddenimports += collect_submodules(pkg)
        datas += collect_data_files(pkg, include_py_files=False)
    except Exception:
        # Package might not exist in certain deployments; ignore.
        pass

# Django admin templates/static live inside Django itself.
try:
    hiddenimports += collect_submodules("django.contrib.admin")
    datas += collect_data_files("django.contrib.admin", include_py_files=False)
except Exception:
    pass

try:
    # Embedded desktop UI (pywebview uses `webview` package name)
    hiddenimports += collect_submodules("webview")
    datas += collect_data_files("webview", include_py_files=False)
except Exception:
    pass

try:
    # Some environments pull tkinter indirectly; ensure it’s discoverable.
    hiddenimports += collect_submodules("tkinter")
except Exception:
    pass

try:
    # pywebview on Windows uses pythonnet (WinForms backend). Ensure the .NET runtime assets
    # like Python.Runtime.deps.json are bundled, otherwise the EXE may crash on fresh machines.
    hiddenimports += collect_submodules("pythonnet")
    datas += collect_data_files("pythonnet", include_py_files=False)
except Exception:
    pass


a = Analysis(
    ["run_desktop.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=["pyinstaller_hooks"],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    [],
    name="JaisTechKhataBookDesktop",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    # Windowed app (no cmd window popping + auto-closing).
    console=False,
    icon="static/img/favicon.ico",
    uac_admin=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="JaisTechKhataBookDesktop",
)
