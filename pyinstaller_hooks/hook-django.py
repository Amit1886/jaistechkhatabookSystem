"""
Custom PyInstaller hook for Django.

Goal: avoid shipping readable `.py` sources as *data files* (PyInstaller's stock
hook uses `collect_all('django')`, which includes hundreds of `.py` files).

We still collect:
- Django's non-Python data files (templates, locale, etc.)
- Django submodules (bytecode goes into PYZ archive by default)
- Optional project settings imports (best-effort, same as upstream hook)
"""

from __future__ import annotations

import glob
import os

from PyInstaller import log as logging
from PyInstaller.utils import hooks
from PyInstaller.utils.hooks import django as django_utils
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

logger = logging.getLogger(__name__)


# Collect non-Python data only (templates, locale, etc.). Do NOT include `.py`.
datas = collect_data_files("django", include_py_files=False)
binaries = collect_dynamic_libs("django")

# Collect Django modules as importable bytecode (goes into PYZ by default).
# Ignore errors for optional components (similar to upstream behavior).
hiddenimports = collect_submodules("django", on_error="ignore")


# Best-effort: include project-related imports that Django settings may reference.
root_dir = django_utils.django_find_root_dir()
if root_dir:
    logger.info("Django root directory %s", root_dir)

    try:
        settings_py_imports = django_utils.django_dottedstring_imports(root_dir)
    except Exception:
        settings_py_imports = []

    for submod in settings_py_imports:
        hiddenimports.append(submod)
        try:
            hiddenimports += hooks.collect_submodules(submod, on_error="ignore")
        except Exception:
            pass

    # Include main project modules - settings.py, urls.py, wsgi.py.
    package_name = os.path.basename(root_dir)
    default_settings_module = f"{package_name}.settings"
    settings_module = os.environ.get("DJANGO_SETTINGS_MODULE", default_settings_module)

    hiddenimports += [
        settings_module,
        package_name + ".urls",
        package_name + ".wsgi",
        "http.cookies",
        "html.parser",
    ]

    # Include data files from your Django project (non-Python only).
    try:
        datas += hooks.collect_data_files(package_name, include_py_files=False)
    except Exception:
        pass

    # Include database file if using sqlite (best-effort).
    root_dir_parent = os.path.dirname(root_dir)
    for pattern in ("*.db", "db.*"):
        for f in glob.glob(os.path.join(root_dir_parent, pattern)):
            datas.append((f, "."))
else:
    logger.warning("No django root directory could be found!")

