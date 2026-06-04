from __future__ import annotations

import atexit
import hashlib
import json
import logging
import os
import shutil
import signal
import socket
import sys
import tempfile
import threading
import time
import webbrowser
import subprocess
import traceback
import zipfile
from pathlib import Path

import requests


_LOCAL_HTTP_SESSION = requests.Session()
# Never route local-loopback health checks via environment proxies.
_LOCAL_HTTP_SESSION.trust_env = False


def _local_http_get(url: str, **kwargs):
    kwargs.setdefault("allow_redirects", False)
    return _LOCAL_HTTP_SESSION.get(url, **kwargs)


def _tail_file_for_dialog(path: Path, *, max_bytes: int = 12_000, max_chars: int = 1400) -> str:
    try:
        if not path.exists() or not path.is_file():
            return ""
        size = path.stat().st_size
        start = max(0, size - max_bytes)
        with open(path, "rb") as f:
            if start:
                f.seek(start)
            data = f.read()
        try:
            text = data.decode("utf-8", errors="replace")
        except Exception:
            text = data.decode("cp1252", errors="replace")
        text = (text or "").strip().replace("\r\n", "\n")
        if len(text) > max_chars:
            text = text[-max_chars:]
        return text
    except Exception:
        return ""


DEFAULT_HOSTS = ("127.0.0.1",)
DEFAULT_PORT = 8000
LANDING_PATH = "/"
LOGIN_PATH = "/accounts/login/"
HEALTH_PATH = "/health/"
LATEST_RELEASE_PATH = "/api/v1/desktop/releases/latest/"
DESKTOP_APP_VERSION = "1.0.4"


logger = logging.getLogger("desktop")


_MUTEX_HANDLE = None
_FAULTHANDLER_STREAM = None
_UPDATE_RESTART_EVENT = threading.Event()
_PENDING_UPDATE_EXE: Path | None = None


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _meipass_dir() -> Path | None:
    meipass = getattr(sys, "_MEIPASS", None)
    return Path(meipass) if meipass else None


def _desktop_data_dir() -> Path:
    base = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or str(Path.cwd())
    return Path(base) / "JaisTechKhataBook"


def _acquire_single_instance_mutex(*, name: str) -> bool:
    """
    Prevent multiple desktop instances from running heavy startup (migrations/sync) concurrently.

    Returns True if acquired; False if another instance already exists.
    """
    global _MUTEX_HANDLE

    if os.name != "nt":
        return True

    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        handle = kernel32.CreateMutexW(None, False, name)
        if not handle:
            return True

        err = ctypes.get_last_error()
        ERROR_ALREADY_EXISTS = 183
        if err == ERROR_ALREADY_EXISTS:
            try:
                kernel32.CloseHandle(handle)
            except Exception:
                pass
            return False

        _MUTEX_HANDLE = handle

        def _release() -> None:
            global _MUTEX_HANDLE
            h = _MUTEX_HANDLE
            _MUTEX_HANDLE = None
            if not h:
                return
            try:
                kernel32.CloseHandle(h)
            except Exception:
                pass

        atexit.register(_release)
        return True
    except Exception:
        # Best-effort; if mutex fails, continue rather than blocking app start.
        return True


def setup_desktop_logging(data_dir: Path) -> Path:
    def _candidates() -> list[Path]:
        items: list[Path] = []
        env_path = (os.getenv("KP_DESKTOP_LOG_FILE") or os.getenv("DESKTOP_LOG_FILE") or "").strip()
        if env_path:
            try:
                expanded = os.path.expandvars(env_path)
                items.append(Path(expanded).expanduser().resolve())
            except Exception:
                pass
        items.append((data_dir / "logs" / "desktop.log").resolve())
        try:
            items.append((Path(tempfile.gettempdir()) / "JaisTechKhataBook" / "logs" / "desktop.log").resolve())
        except Exception:
            pass
        try:
            items.append((Path.cwd() / "desktop.log").resolve())
        except Exception:
            pass
        # De-dup while preserving order
        seen: set[str] = set()
        dedup: list[Path] = []
        for p in items:
            key = str(p).lower()
            if key in seen:
                continue
            seen.add(key)
            dedup.append(p)
        return dedup

    log_file: Path | None = None
    for candidate in _candidates():
        try:
            candidate.parent.mkdir(parents=True, exist_ok=True)
            # Ensure it's writable and exists.
            with open(candidate, "a", encoding="utf-8"):
                pass
            log_file = candidate
            break
        except Exception:
            continue

    if log_file is None:
        # Worst-case fallback: use current directory (may still be unwritable).
        log_file = (Path.cwd() / "desktop.log").resolve()
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(log_file, "a", encoding="utf-8"):
                pass
        except Exception:
            pass

    # Expose the log path for Django/admin views (override so the chosen path wins).
    try:
        os.environ["KP_DESKTOP_LOG_FILE"] = str(log_file)
    except Exception:
        pass

    root = logging.getLogger()
    try:
        for h in root.handlers:
            if isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", None):
                try:
                    if Path(h.baseFilename).resolve() == log_file:
                        return log_file
                except Exception:
                    continue
    except Exception:
        pass

    # Ensure stdout/stderr exist in windowed EXE mode (avoid logging crashing on None streams).
    try:
        if getattr(sys, "stdout", None) is None:
            sys.stdout = open(os.devnull, "w", encoding="utf-8", buffering=1)
        if getattr(sys, "stderr", None) is None:
            sys.stderr = open(os.devnull, "w", encoding="utf-8", buffering=1)
    except Exception:
        pass

    # Capture native crashes (e.g., access violation) into the desktop log.
    # Keep the stream alive globally so faulthandler can keep writing.
    try:
        import faulthandler

        global _FAULTHANDLER_STREAM
        if _FAULTHANDLER_STREAM is None:
            _FAULTHANDLER_STREAM = open(log_file, "a", encoding="utf-8", buffering=1)
        faulthandler.enable(file=_FAULTHANDLER_STREAM, all_threads=True)
    except Exception:
        try:
            import faulthandler

            faulthandler.enable(all_threads=True)
        except Exception:
            pass

    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    try:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(fmt))
        if root.handlers:
            root.addHandler(file_handler)
            root.setLevel(logging.INFO)
        else:
            logging.basicConfig(level=logging.INFO, format=fmt, handlers=[file_handler])
    except Exception:
        pass
    return log_file


def _run_powershell(command: str) -> subprocess.CompletedProcess:
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.run(  # noqa: S603
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True,
        text=True,
        creationflags=creationflags,
        check=False,
    )


def get_windows_desktop_dir() -> Path:
    """
    Resolve the current user's Desktop folder (handles OneDrive redirection).
    """
    if os.name != "nt":
        return (Path.home() / "Desktop").resolve()

    try:
        res = _run_powershell("[Environment]::GetFolderPath('Desktop')")
        p = (res.stdout or "").strip().strip('"')
        if p:
            return Path(p).resolve()
    except Exception:
        pass

    return (Path(os.path.expanduser("~")) / "Desktop").resolve()


def ensure_desktop_shortcut(*, name: str = "JaisTech KhataBook") -> None:
    """
    Create/refresh a Desktop shortcut to the currently running EXE.

    NOTE: If the EXE is built with `uac_admin=True`, launching via shortcut will
    still show a UAC prompt.
    """
    if os.name != "nt" or not _is_frozen():
        return

    try:
        desktop_dir = get_windows_desktop_dir()
        desktop_dir.mkdir(parents=True, exist_ok=True)

        exe_path = Path(sys.executable).resolve()
        lnk_path = (desktop_dir / f"{name}.lnk").resolve()

        def esc(s: str) -> str:
            return s.replace("'", "''")

        ps = (
            "$WshShell = New-Object -ComObject WScript.Shell;"
            f"$Shortcut = $WshShell.CreateShortcut('{esc(str(lnk_path))}');"
            f"$Shortcut.TargetPath = '{esc(str(exe_path))}';"
            f"$Shortcut.WorkingDirectory = '{esc(str(exe_path.parent))}';"
            f"$Shortcut.IconLocation = '{esc(str(exe_path))},0';"
            "$Shortcut.Save();"
        )

        res = _run_powershell(ps)
        if res.returncode != 0:
            logger.warning("Shortcut create failed: %s", (res.stderr or "").strip())
        else:
            logger.info("Desktop shortcut ready: %s", lnk_path)
    except Exception:
        logger.exception("Failed to create desktop shortcut")


def _endpoint_file(data_dir: Path) -> Path:
    return (data_dir / "server_endpoint.json").resolve()


def _read_last_endpoint_info(data_dir: Path) -> dict | None:
    path = _endpoint_file(data_dir)
    try:
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8") or "{}")
        host = str(payload.get("host") or "").strip()
        port = int(payload.get("port") or 0)
        pid = int(payload.get("pid") or 0)
        ts = int(payload.get("ts") or 0)
        if not host or not port:
            return None
        return {"host": host, "port": port, "pid": pid, "ts": ts}
    except Exception:
        return None


def _read_last_endpoint(data_dir: Path) -> tuple[str, int] | None:
    info = _read_last_endpoint_info(data_dir)
    if not info:
        return None
    return str(info["host"]), int(info["port"])


def _write_last_endpoint(data_dir: Path, *, host: str, port: int, pid: int | None = None) -> None:
    path = _endpoint_file(data_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {"host": host, "port": int(port), "pid": int(pid or os.getpid()), "ts": int(time.time())},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass


def _copy_if_missing(src: Path, dst: Path) -> None:
    if dst.exists() or not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _copytree_if_missing(src: Path, dst: Path) -> None:
    if dst.exists() or not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, dirs_exist_ok=True)


def _copytree_merge(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copytree(src, dst, dirs_exist_ok=True)
    except Exception:
        # Best-effort; desktop should still run even if static sync fails.
        pass


def _read_json(path: Path) -> dict:
    try:
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8") or "{}")
    except Exception:
        return {}


def _write_json(path: Path, payload: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def prepare_desktop_files() -> Path:
    """
    Ensure persistent desktop files exist in a writable location:
    - `.env` (user-editable)
    - `db.sqlite3` (persistent SQLite database)
    """
    data_dir = _desktop_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)

    meipass = _meipass_dir()
    project_root = Path(__file__).resolve().parent

    # Prefer bundled resources (PyInstaller), fallback to project root (dev).
    env_src = (meipass / ".env") if meipass else (project_root / ".env")
    db_src = (meipass / "db.sqlite3") if meipass else (project_root / "db.sqlite3")
    static_src = (meipass / "static") if meipass else (project_root / "static")

    _copy_if_missing(env_src, data_dir / ".env")
    _copy_if_missing(db_src, data_dir / "db.sqlite3")
    static_dst = data_dir / "static"

    # Keep static assets fresh across app updates.
    # We use a small stamp file so we don't re-copy the whole tree on every launch.
    static_stamp_path = (data_dir / "static_sync.json").resolve()
    src_mtime = 0
    try:
        if static_src.exists():
            src_mtime = int(static_src.stat().st_mtime)
    except Exception:
        src_mtime = 0

    stamp = _read_json(static_stamp_path)
    build_id = ""
    try:
        if _is_frozen():
            exe = Path(sys.executable).resolve()
            st = exe.stat()
            build_id = f"{st.st_mtime_ns}:{st.st_size}"
        else:
            build_id = f"dev:{int(time.time() // 3600)}"
    except Exception:
        build_id = ""

    stamp_ok = bool(static_dst.exists() and int(stamp.get("src_mtime") or 0) == src_mtime and src_mtime > 0)
    build_ok = (not build_id) or (str(stamp.get("build_id") or "") == build_id)

    if not static_dst.exists():
        _copytree_if_missing(static_src, static_dst)
        _write_json(static_stamp_path, {"src_mtime": src_mtime, "build_id": build_id})
    elif (not stamp_ok) or (not build_ok):
        # If build changed, do a clean refresh to avoid stale/cached JS in embedded webview.
        if not build_ok:
            try:
                shutil.rmtree(static_dst, ignore_errors=True)
            except Exception:
                pass

        if not static_dst.exists():
            _copytree_if_missing(static_src, static_dst)
        else:
            # Merge everything (covers css/js/vendor + any new folders like libs/images).
            _copytree_merge(static_src, static_dst)

        _write_json(static_stamp_path, {"src_mtime": src_mtime, "build_id": build_id})

    # Ensure common branding files exist even if `static` was partially copied.
    _copy_if_missing(static_src / "img" / "logo.png", static_dst / "img" / "logo.png")
    _copy_if_missing(static_src / "img" / "favicon.ico", static_dst / "img" / "favicon.ico")

    return data_dir


def _load_env_file(path: Path) -> None:
    """
    Minimal .env loader for the desktop wrapper process.

    Django loads .env inside `khatapro/settings.py`, but the wrapper process reads
    env vars too (ex: DESKTOP_UI). Keep this dependency-free so the EXE can
    start even if optional packages are missing.
    """
    try:
        if not path.exists():
            return
        for raw_line in (path.read_text(encoding="utf-8", errors="ignore") or "").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.lower().startswith("export "):
                line = line[7:].strip()
            if "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            if not key:
                continue
            val = val.strip()
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            # Only set if not already provided by the OS/environment.
            os.environ.setdefault(key, val)
    except Exception:
        # Best-effort: never crash the desktop app because of a malformed .env.
        pass


def _is_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _find_free_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def choose_host_and_port() -> tuple[str, int]:
    env_host = (os.getenv("DESKTOP_HOST") or "").strip()
    # Prefer the standard loopback host for maximum compatibility with Windows/browser proxy bypass lists.
    preferred_host = env_host or "127.0.0.1"

    try:
        preferred_port = int((os.getenv("DESKTOP_PORT") or str(DEFAULT_PORT)).strip())
    except Exception:
        preferred_port = DEFAULT_PORT

    # Keep host stable; if 8000 is busy, pick a free port on the same host instead of switching IPs.
    try:
        if _is_port_available(preferred_host, preferred_port):
            return preferred_host, preferred_port
        return preferred_host, _find_free_port(preferred_host)
    except Exception:
        # If a custom host is invalid/unbindable, fall back to localhost.
        fallback_host = "127.0.0.1"
        if preferred_host != fallback_host:
            try:
                if _is_port_available(fallback_host, preferred_port):
                    return fallback_host, preferred_port
                return fallback_host, _find_free_port(fallback_host)
            except Exception:
                pass
        return fallback_host, preferred_port


def wait_for_http_ok(url: str, timeout_seconds: int = 60) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            resp = requests.get(url, timeout=1.5, allow_redirects=False)
            if resp.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(0.25)
    return False


def open_url(url: str) -> None:
    """
    Open URL as reliably as possible on Windows, including when the EXE is elevated.

    Some browsers (notably Chrome) refuse to start as Administrator, so launching
    via the shell (explorer) can be more reliable than `webbrowser.open()` alone.
    """
    try:
        if webbrowser.open(url):
            return
    except Exception:
        pass

    if os.name != "nt":
        return

    # ShellExecute via startfile
    try:
        os.startfile(url)  # noqa: S606
        return
    except Exception:
        pass

    # Fallback: ask explorer.exe to open the URL using the default handler.
    try:
        subprocess.Popen(["explorer.exe", url], close_fds=True)  # noqa: S603
    except Exception:
        pass


def open_in_desktop_app(url: str) -> bool:
    """
    Prefer embedded desktop window (pywebview) so the URL is not visible.

    Falls back to the system browser if webview cannot start.
    """
    ui = (os.getenv("DESKTOP_UI") or "webview").strip().lower()
    if ui in {"browser", "external"}:
        open_url(url)
        # Keep the local server alive until the user exits the wrapper,
        # otherwise the browser will show "site can't be reached".
        _messagebox_info(
            "Running in Browser",
            "The app is running in your default browser.\n\n"
            "When you are done, click OK to stop the local server and close the desktop app.",
        )
        return False

    try:
        import webview  # pywebview

        try:
            settings = getattr(webview, "settings", None)
            if isinstance(settings, dict):
                settings.setdefault("OPEN_EXTERNAL_LINKS_IN_BROWSER", True)
        except Exception:
            pass

        def _update_watcher(window) -> None:
            try:
                _UPDATE_RESTART_EVENT.wait()
            except Exception:
                return

            # Best-effort: close the embedded window so the main process can
            # exit cleanly and let the updater restart the app.
            try:
                destroy = getattr(window, "destroy", None)
                if callable(destroy):
                    destroy()
                    return
            except Exception:
                pass
            try:
                webview.destroy_window()
            except Exception:
                pass

        confirm_close_env = (os.getenv("DESKTOP_CONFIRM_CLOSE") or "").strip().lower()
        confirm_close = confirm_close_env not in {"0", "false", "no", "off"}
        if not _is_frozen() and not confirm_close_env:
            confirm_close = False

        window_kwargs = {
            "width": 1200,
            "height": 800,
            "resizable": True,
        }
        if confirm_close:
            window_kwargs["confirm_close"] = True

        try:
            window = webview.create_window("JaisTech KhataBook", url, **window_kwargs)
        except TypeError:
            window_kwargs.pop("confirm_close", None)
            window = webview.create_window("JaisTech KhataBook", url, **window_kwargs)

        try:
            webview.start(_update_watcher, args=(window,), debug=False)
        except TypeError:
            # Compatibility with older pywebview signatures.
            webview.start(_update_watcher, (window,), debug=False)
        return True
    except Exception:
        logger.exception("Failed to start embedded webview")
        _messagebox_info(
            "Desktop UI Error",
            "Embedded desktop window could not start.\n\n"
            "Install requirements, then try again:\n"
            "1) Microsoft Edge WebView2 Runtime\n"
            "2) Microsoft .NET Desktop Runtime (6+)\n\n"
            "Temporary workaround:\n"
            "Set DESKTOP_UI=browser in:\n"
            "%LOCALAPPDATA%\\JaisTechKhataBook\\.env",
        )
        # Automatic fallback: open in browser and keep server alive until user exits.
        open_url(url)
        _messagebox_info(
            "Running in Browser",
            "Opened the app in your default browser.\n\n"
            "When you are done, click OK to stop the local server and close the desktop app.",
        )
        return False


def _create_no_window_creationflags() -> int:
    if os.name != "nt":
        return 0
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _server_command(host: str, port: int) -> list[str]:
    if _is_frozen():
        return [str(Path(sys.executable).resolve()), "--server", host, str(int(port))]
    return [sys.executable, str(Path(__file__).resolve()), "--server", host, str(int(port))]


def start_server_subprocess(*, host: str, port: int) -> subprocess.Popen:
    """
    Start the Django server in a separate process to prevent native SQLite crashes
    from taking down the UI (pywebview) process.
    """
    cmd = _server_command(host, port)
    env = os.environ.copy()
    env.setdefault("DESKTOP_MODE", "True")
    env.setdefault("DESKTOP_SERVER", "1")
    creationflags = _create_no_window_creationflags()
    return subprocess.Popen(  # noqa: S603
        cmd,
        env=env,
        close_fds=True,
        creationflags=creationflags,
    )


def backup_sqlite(*, data_dir: Path) -> None:
    src = (data_dir / "db.sqlite3").resolve()
    if not src.exists():
        return

    backups_dir = (data_dir / "backups").resolve()
    backups_dir.mkdir(parents=True, exist_ok=True)

    # Avoid creating backups too frequently.
    try:
        existing = sorted(backups_dir.glob("db-*.sqlite3"), key=lambda p: p.stat().st_mtime, reverse=True)
        if existing:
            age = time.time() - existing[0].stat().st_mtime
            if age < 60 * 10:  # 10 minutes
                return
    except Exception:
        pass

    ts = time.strftime("%Y%m%d-%H%M%S")
    dst = (backups_dir / f"db-{ts}.sqlite3").resolve()
    try:
        shutil.copy2(src, dst)
        logger.info("DB backup created: %s", dst)
    except Exception:
        logger.exception("DB backup failed")

    # Keep last 30 backups.
    try:
        all_baks = sorted(backups_dir.glob("db-*.sqlite3"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in all_baks[30:]:
            try:
                old.unlink(missing_ok=True)
            except Exception:
                pass
    except Exception:
        pass


def _show_native_splash(*, title: str, logo_path: Path | None, timeout_seconds: int, ready_event: threading.Event) -> None:
    """
    Best-effort native splash window (shows immediately on EXE open).

    - Closes automatically when `ready_event` is set or timeout happens.
    - Falls back silently if Tk isn't available.
    """
    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception:
        # Even if we can't show a splash window, still wait for readiness so the app
        # doesn't immediately report a false startup failure.
        try:
            ready_event.wait(timeout_seconds)
        except Exception:
            time.sleep(timeout_seconds)
        return

    try:
        root = tk.Tk()
        root.title(title)
        root.configure(bg="#0b1220")
    except Exception:
        # If Tk initializes but cannot create a window (missing Tcl/Tk assets),
        # fall back to a silent wait.
        try:
            ready_event.wait(timeout_seconds)
        except Exception:
            time.sleep(timeout_seconds)
        return

    # Borderless + topmost for "splash" feel.
    try:
        root.overrideredirect(True)
        root.attributes("-topmost", True)
    except Exception:
        pass

    container = ttk.Frame(root, padding=18)
    container.pack(fill="both", expand=True)

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass

    style.configure("Splash.TFrame", background="#0b1220")
    style.configure("Splash.TLabel", background="#0b1220", foreground="#e5e7eb", font=("Segoe UI", 11))
    style.configure("SplashSub.TLabel", background="#0b1220", foreground="#94a3b8", font=("Segoe UI", 9))
    container.configure(style="Splash.TFrame")

    img = None
    if logo_path and logo_path.exists():
        try:
            img = tk.PhotoImage(file=str(logo_path))
        except Exception:
            img = None

    if img is not None:
        logo_label = ttk.Label(container, image=img, style="Splash.TLabel")
        logo_label.image = img  # keep alive
        logo_label.pack(padx=10, pady=(8, 10))
    else:
        ttk.Label(container, text="JAIS TECH", style="Splash.TLabel").pack(padx=10, pady=(18, 6))

    ttk.Label(container, text="Starting…", style="Splash.TLabel").pack(padx=10, pady=(0, 2))
    status = ttk.Label(container, text="Launching local server", style="SplashSub.TLabel")
    status.pack(padx=10, pady=(0, 8))

    started_at = time.time()

    # Center on screen
    root.update_idletasks()
    w = max(420, root.winfo_reqwidth())
    h = max(240, root.winfo_reqheight())
    x = int((root.winfo_screenwidth() - w) / 2)
    y = int((root.winfo_screenheight() - h) / 2)
    root.geometry(f"{w}x{h}+{x}+{y}")

    # Subtle "highlight" pulse via alpha (no PIL needed).
    alpha = 0.90
    alpha_dir = 1

    def _tick() -> None:
        nonlocal alpha, alpha_dir

        if ready_event.is_set():
            try:
                root.destroy()
            except Exception:
                pass
            return

        if (time.time() - started_at) > timeout_seconds:
            try:
                root.destroy()
            except Exception:
                pass
            return

        # Update text + pulse.
        dots = "." * (int((time.time() - started_at) * 2) % 4)
        try:
            status.configure(text=f"Launching local server{dots}")
        except Exception:
            pass

        try:
            alpha += 0.01 * alpha_dir
            if alpha >= 1.0:
                alpha = 1.0
                alpha_dir = -1
            if alpha <= 0.88:
                alpha = 0.88
                alpha_dir = 1
            root.attributes("-alpha", alpha)
        except Exception:
            pass

        root.after(90, _tick)

    root.after(50, _tick)

    # Allow exit by ESC (optional)
    try:
        root.bind("<Escape>", lambda _e: root.destroy())
    except Exception:
        pass

    try:
        root.mainloop()
    except Exception:
        pass


def _splash_logo_path() -> Path | None:
    meipass = _meipass_dir()
    project_root = Path(__file__).resolve().parent

    candidates: list[Path] = []
    if meipass:
        candidates.append(meipass / "static" / "img" / "logo.png")
    candidates.append(project_root / "static" / "img" / "logo.png")

    for p in candidates:
        try:
            if p.exists():
                return p
        except Exception:
            continue

    return None


def start_django_server(host: str, port: int) -> None:
    from django.core.management import call_command

    call_command(
        "runserver",
        f"{host}:{port}",
        use_reloader=False,
        # Desktop: reduce thread/concurrency to avoid native sqlite crashes seen on some Windows setups.
        use_threading=False,
        verbosity=1,
    )


def server_main(host: str, port: int) -> None:
    """
    Server-only entrypoint (runs in a child process when desktop UI is active).
    """
    data_dir = prepare_desktop_files()
    log_file = setup_desktop_logging(data_dir)
    logger.info("Desktop server starting (pid=%s) on %s:%s", os.getpid(), host, port)
    logger.info("Logs: %s", log_file)

    # Ensure desktop behavior is enabled as early as possible.
    os.environ.setdefault("DESKTOP_MODE", "True")
    os.environ.setdefault("AUTOBAHN_USE_NVX", "0")
    os.environ.setdefault("DEBUG", "False")
    # Wrapper-supplied app version must override any stale value in user .env.
    os.environ["DESKTOP_APP_VERSION_CODE"] = DESKTOP_APP_VERSION
    os.environ["DESKTOP_APP_VERSION"] = DESKTOP_APP_VERSION
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "khatapro.settings")
    os.environ.setdefault("SQLITE_PATH", str((data_dir / "db.sqlite3").resolve()))

    import django
    from django.core.management import call_command

    logger.info("Django setup starting...")
    django.setup()
    logger.info("Running migrations...")
    call_command("migrate", interactive=False, verbosity=1)
    logger.info("Migrations complete.")

    # Hybrid Desktop -> Cloud sync:
    # - Requires CLOUD_API_URL + CLOUD_API_TOKEN (desktop) and SYNC_API_TOKEN (cloud).
    # - Disabled by default unless cloud config is present (or user explicitly enables it).
    # - Can be force-disabled via DESKTOP_ENABLE_SYNC=False (stability).
    sync_flag = (os.getenv("DESKTOP_ENABLE_SYNC") or "").strip().lower()
    explicit_enable = sync_flag in {"1", "true", "yes", "on"}
    explicit_disable = sync_flag in {"0", "false", "no", "off"}

    cloud_url = (os.getenv("CLOUD_API_URL") or "").strip()
    cloud_token = (os.getenv("CLOUD_API_TOKEN") or "").strip()
    cloud_configured = bool(cloud_url and cloud_token)

    enable_sync = (explicit_enable or cloud_configured) and not explicit_disable

    if enable_sync and cloud_configured:
        try:
            from sync_service import start_sync_service

            interval = int(os.getenv("DESKTOP_SYNC_INTERVAL", "30"))
            logger.info("Starting cloud sync service (interval=%ss, cloud=%s)", interval, cloud_url)
            start_sync_service(interval_seconds=interval)
        except Exception:
            logger.exception("Failed to start sync service")
    else:
        if explicit_disable:
            logger.info("Cloud sync disabled via DESKTOP_ENABLE_SYNC=False")
        elif not cloud_configured:
                 logger.info(
                 "Cloud sync not configured (set CLOUD_API_URL and CLOUD_API_TOKEN in %s)",
                str((data_dir / ".env").resolve()),
            )
        else:
            logger.info("Cloud sync configured but not enabled (set DESKTOP_ENABLE_SYNC=True)")

    logger.info("Starting runserver...")
    start_django_server(host, port)


def _extract_token(auth_header: str | None) -> str:
    if not auth_header:
        return ""
    auth_header = auth_header.strip()
    if auth_header.lower().startswith("token "):
        return auth_header[6:].strip()
    return auth_header


def _version_tuple(v: str) -> tuple[int, ...]:
    # Minimal semver-ish parser: "1.2.3" -> (1,2,3)
    parts = []
    for raw in (v or "").strip().split("."):
        try:
            parts.append(int(raw))
        except Exception:
            break
    return tuple(parts)


def _messagebox_yes_no(title: str, text: str) -> bool:
    # Windows-native prompt without tkinter.
    if os.name == "nt":
        try:
            import ctypes

            MB_YESNO = 0x00000004
            MB_ICONQUESTION = 0x00000020
            IDYES = 6
            res = ctypes.windll.user32.MessageBoxW(0, text, title, MB_YESNO | MB_ICONQUESTION)
            return res == IDYES
        except Exception:
            pass
    # Fallback (console environments)
    return False


def _messagebox_info(title: str, text: str) -> None:
    if os.name == "nt":
        try:
            import ctypes

            MB_OK = 0x00000000
            MB_ICONINFORMATION = 0x00000040
            ctypes.windll.user32.MessageBoxW(0, text, title, MB_OK | MB_ICONINFORMATION)
            return
        except Exception:
            pass


def _ps_escape_single_quotes(s: str) -> str:
    return (s or "").replace("'", "''")


def _request_restart_into_update(exe_path: Path) -> None:
    global _PENDING_UPDATE_EXE
    try:
        _PENDING_UPDATE_EXE = Path(exe_path).resolve()
    except Exception:
        _PENDING_UPDATE_EXE = exe_path
    _UPDATE_RESTART_EVENT.set()


def _spawn_windows_update_restart(*, update_exe: Path) -> None:
    """
    Restart the desktop app into the given update EXE.

    Uses a detached PowerShell helper to avoid mutex conflicts (the new EXE waits
    until the current PID exits).
    """
    if os.name != "nt":
        return

    try:
        parent_pid = int(os.getpid())
    except Exception:
        parent_pid = 0

    creationflags = _create_no_window_creationflags()
    ps = (
        f"$ParentPid={parent_pid};"
        f"$Exe='{_ps_escape_single_quotes(str(update_exe))}';"
        "try { if ($ParentPid -gt 0) { Wait-Process -Id $ParentPid -Timeout 600 } } catch { };"
        "try { Start-Process -FilePath $Exe } catch { };"
    )
    subprocess.Popen(  # noqa: S603
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
        close_fds=True,
        creationflags=creationflags,
    )


def _safe_extract_zip(src_zip: Path, dst_dir: Path) -> None:
    dst_dir.mkdir(parents=True, exist_ok=True)
    base = dst_dir.resolve()
    with zipfile.ZipFile(src_zip) as z:
        for info in z.infolist():
            name = str(getattr(info, "filename", "") or "")
            if not name:
                continue
            rel = Path(name)
            if rel.is_absolute() or ".." in rel.parts:
                continue
            out_path = (base / rel).resolve()
            if base not in out_path.parents and out_path != base:
                continue
            if info.is_dir():
                out_path.mkdir(parents=True, exist_ok=True)
                continue
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(out_path, "wb") as dst:
                shutil.copyfileobj(src, dst)


def _prepare_zip_update(*, zip_path: Path, data_dir: Path, version: str) -> Path | None:
    extract_root = (data_dir / "updates" / f"JaisTechKhataBookDesktop-{version}").resolve()
    try:
        shutil.rmtree(extract_root, ignore_errors=True)
    except Exception:
        pass
    try:
        _safe_extract_zip(zip_path, extract_root)
    except Exception:
        return None

    expected = (extract_root / "dist" / "JaisTechKhataBookDesktop" / "JaisTechKhataBookDesktop.exe").resolve()
    if expected.exists():
        return expected

    try:
        candidates = list(extract_root.rglob("JaisTechKhataBookDesktop.exe"))
        return candidates[0].resolve() if candidates else None
    except Exception:
        return None


def _download_with_sha256(url: str, dst: Path, timeout_seconds: int = 120) -> str:
    dst.parent.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    with requests.get(url, stream=True, timeout=timeout_seconds) as r:
        r.raise_for_status()
        with open(dst, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                f.write(chunk)
                h.update(chunk)
    return h.hexdigest()


def check_for_updates_and_prompt(*, data_dir: Path) -> None:
    """
    Desktop update flow:
    - If online + CLOUD_API_URL configured, fetch latest release metadata.
    - If new version available, prompt user to download.
    - Download EXE to a persistent folder and verify sha256 if provided.
    - Optionally restart the app to apply the update immediately.
    """
    from hybrid_mode import is_internet_available

    if not is_internet_available():
        return

    base = (os.getenv("CLOUD_API_URL") or "").strip().rstrip("/")
    token = (os.getenv("CLOUD_API_TOKEN") or "").strip()
    if not base or not token:
        return

    auto_update = (os.getenv("DESKTOP_AUTO_UPDATE") or "").strip().lower() in {"1", "true", "yes", "on"}

    current_version = (os.getenv("DESKTOP_APP_VERSION") or "0.0.0").strip()
    if os.getenv("DESKTOP_APP_VERSION_CODE"):
        current_version = (os.getenv("DESKTOP_APP_VERSION_CODE") or current_version).strip()
    latest_url = f"{base}{LATEST_RELEASE_PATH}"

    try:
        resp = requests.get(
            latest_url,
            headers={"Authorization": f"Token {token}"},
            timeout=10,
        )
        if resp.status_code == 401:
            return
        resp.raise_for_status()
        payload = resp.json()
    except Exception:
        return

    if not payload or not payload.get("published"):
        return

    latest_version = (payload.get("version") or "").strip()
    if not latest_version:
        return

    if _version_tuple(latest_version) <= _version_tuple(current_version):
        return

    download_url = (payload.get("download_url") or "").strip()
    expected_sha = (payload.get("sha256") or "").strip().lower()
    if not download_url:
        return

    if not auto_update:
        ok = _messagebox_yes_no(
            "Update Available",
            f"New desktop version {latest_version} is available.\n"
            f"Current version: {current_version}\n\n"
            f"Download now?",
        )
        if not ok:
            return

    download_filename = str(payload.get("download_filename") or "").strip()
    if not download_filename:
        download_filename = f"JaisTechKhataBookDesktop-{latest_version}.exe"
    dst = (data_dir / "updates" / download_filename).resolve()
    try:
        actual_sha = _download_with_sha256(download_url, dst)
    except Exception:
        _messagebox_info("Update Failed", "Download failed. Please try again later.")
        return

    if expected_sha and actual_sha.lower() != expected_sha:
        try:
            dst.unlink(missing_ok=True)
        except Exception:
            pass
        _messagebox_info("Update Failed", "Downloaded file checksum mismatch. Download was discarded.")
        return

    launch_exe = dst
    open_folder = dst.parent
    is_zip = str(dst.suffix or "").lower() == ".zip"
    if not is_zip:
        try:
            with open(dst, "rb") as f:
                is_zip = (f.read(4) == b"PK\x03\x04")
        except Exception:
            is_zip = False

    if is_zip:
        extracted_exe = _prepare_zip_update(zip_path=dst, data_dir=data_dir, version=latest_version)
        if not extracted_exe:
            _messagebox_info("Update Failed", "Downloaded update could not be extracted.")
            return
        launch_exe = extracted_exe
        open_folder = extracted_exe.parent

    if auto_update:
        _request_restart_into_update(launch_exe)
        try:
            import webview  # noqa: WPS433

            try:
                webview.destroy_window()
            except Exception:
                pass
        except Exception:
            pass
        return

    try:
        restart_now = _messagebox_yes_no(
            "Update Downloaded",
            f"New version {latest_version} downloaded:\n{dst}\n\n"
            "Restart the desktop app now to apply the update?",
        )
    except Exception:
        restart_now = False

    if restart_now:
        _request_restart_into_update(launch_exe)
        # Best-effort: close the embedded UI if running (webview mode).
        try:
            import webview  # noqa: WPS433

            try:
                webview.destroy_window()
            except Exception:
                pass
        except Exception:
            pass
        return

    # Open folder for convenience (user can run the downloaded EXE later).
    try:
        if os.name == "nt":
            os.startfile(str(open_folder))  # noqa: S606
    except Exception:
        pass


def main() -> None:
    data_dir = prepare_desktop_files()
    log_file = setup_desktop_logging(data_dir)
    logger.info("Desktop app starting (pid=%s, frozen=%s)", os.getpid(), _is_frozen())
    logger.info("Logs: %s", log_file)
    ensure_desktop_shortcut()

    # Load user-editable env early so wrapper options like DESKTOP_UI take effect.
    _load_env_file((data_dir / ".env").resolve())

    # Single-instance guard (prevents concurrent migrations/DB access across processes).
    allow_multi = (os.getenv("DESKTOP_ALLOW_MULTI_INSTANCE") or "").strip().lower() in {"1", "true", "yes", "on"}
    if not allow_multi:
        username = (os.getenv("USERNAME") or "user").strip()
        safe_user = "".join([c for c in username if (c.isalnum() or c in {"_", "-"})]) or "user"
        mutex_name = f"Local\\JaisTechKhataBookDesktop-{safe_user}"
        if not _acquire_single_instance_mutex(name=mutex_name):
            logger.info("Another desktop instance is already running.")
            _messagebox_info("Already Running", "JaisTech KhataBook is already running.\n\nPlease check the taskbar.")
            return

    # Ensure desktop behavior is enabled as early as possible.
    # NOTE: In PyInstaller builds, Django settings may be imported by runtime hooks.
    os.environ.setdefault("DESKTOP_MODE", "True")

    # Autobahn NVX uses CFFI wrapper modules that expect source files at runtime,
    # which can break in PyInstaller one-folder/one-file layouts. For desktop mode,
    # disable NVX and use the pure-Python fallback implementations.
    os.environ.setdefault("AUTOBAHN_USE_NVX", "0")

    # Desktop mode overrides: secure defaults without breaking localhost HTTP.
    os.environ.setdefault("DEBUG", "False")
    # Wrapper-supplied app version must override any stale value in user .env.
    os.environ["DESKTOP_APP_VERSION_CODE"] = DESKTOP_APP_VERSION
    os.environ["DESKTOP_APP_VERSION"] = DESKTOP_APP_VERSION
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "khatapro.settings")
    os.environ.setdefault("SQLITE_PATH", str((data_dir / "db.sqlite3").resolve()))

    backup_sqlite(data_dir=data_dir)

    # Update check (non-blocking).
    threading.Thread(
        target=check_for_updates_and_prompt,
        kwargs={"data_dir": data_dir},
        name="desktop-updater",
        daemon=True,
    ).start()

    # If a stale server process exists from a previous crash, try to stop it to avoid
    # orphaned runservers holding onto the SQLite file.
    existing = _read_last_endpoint_info(data_dir)
    if existing and int(existing.get("pid") or 0) > 0:
        try:
            os.kill(int(existing["pid"]), signal.SIGTERM)
        except Exception:
            pass

    host, port = choose_host_and_port()
    # Make BASE_URL accurate for this desktop session (helps absolute URL generation in templates/APIs).
    try:
        os.environ["BASE_URL"] = f"http://{host}:{port}"
    except Exception:
        pass
    server_proc = start_server_subprocess(host=host, port=port)
    _write_last_endpoint(data_dir, host=host, port=port, pid=int(server_proc.pid))

    # Show native splash immediately (best-effort), then open browser splash once server is responsive.
    health_url = f"http://{host}:{port}{HEALTH_PATH}"
    ready_event = threading.Event()
    server_failed_event = threading.Event()
    last_health_detail: dict[str, str] = {"text": ""}

    try:
        startup_timeout = int((os.getenv("DESKTOP_STARTUP_TIMEOUT") or "180").strip())
    except Exception:
        startup_timeout = 180
    startup_timeout = max(30, min(startup_timeout, 600))

    def _waiter() -> None:
        deadline = time.time() + startup_timeout
        while time.time() < deadline:
            try:
                if server_proc.poll() is not None:
                    server_failed_event.set()
                    return
            except Exception:
                pass

            try:
                resp = _local_http_get(health_url, timeout=1.5)
                detail = f"Last /health response: HTTP {resp.status_code}"
                if resp.status_code == 200:
                    last_health_detail["text"] = detail
                    ready_event.set()
                    return
                try:
                    snippet = (resp.text or "").strip().replace("\r\n", "\n")
                    if snippet:
                        detail = f"{detail}\n{snippet[:300]}"
                except Exception:
                    pass
                last_health_detail["text"] = detail
            except requests.RequestException as e:
                msg = (str(e) or "").strip().replace("\r\n", "\n")
                if len(msg) > 220:
                    msg = msg[:220] + "..."
                last_health_detail["text"] = f"Last /health error: {type(e).__name__}: {msg}"

            time.sleep(0.25)

    threading.Thread(target=_waiter, name="desktop-ready-waiter", daemon=True).start()

    _show_native_splash(
        title="JaisTech KhataBook",
        logo_path=_splash_logo_path(),
        timeout_seconds=startup_timeout,
        ready_event=ready_event,
    )

    try:
        if not ready_event.is_set():
            if server_failed_event.is_set():
                code = None
                try:
                    code = server_proc.poll()
                except Exception:
                    code = None
                tail = _tail_file_for_dialog(log_file)
                extra = f"\n\nLast logs:\n{tail}" if tail else ""
                _messagebox_info(
                    "App Start Failed",
                    "Local server exited while starting.\n\n"
                    f"Exit code: {code}\n\n"
                    f"Logs: {log_file}"
                    f"{extra}",
                )
                return

            detail = (last_health_detail.get("text") or "").strip()
            tail = _tail_file_for_dialog(log_file)
            extra = ""
            if detail:
                extra += f"\n\n{detail}"
            if tail:
                extra += f"\n\nLast logs:\n{tail}"
            _messagebox_info(
                "App Start Failed",
                "Local server did not start in time.\n\n"
                "Try:\n"
                "1) Close any previous instance.\n"
                "2) Allow the app in Windows Firewall (if prompted).\n"
                "3) Run again.\n\n"
                f"Health URL: {health_url}\n\n"
                f"Logs: {log_file}"
                f"{extra}",
            )
            return

        open_in_desktop_app(f"http://{host}:{port}{LANDING_PATH}?t={int(time.time())}")
    finally:
        # Ensure the server does not remain running in the background after the UI closes.
        try:
            if server_proc and server_proc.poll() is None:
                server_proc.terminate()
        except Exception:
            pass

    if _UPDATE_RESTART_EVENT.is_set() and _PENDING_UPDATE_EXE:
        try:
            update_exe = Path(_PENDING_UPDATE_EXE).resolve()
        except Exception:
            update_exe = _PENDING_UPDATE_EXE

        if update_exe.exists():
            try:
                logger.info("Restarting into update: %s", update_exe)
                _spawn_windows_update_restart(update_exe=update_exe)
            except Exception:
                logger.exception("Failed to restart into update")
        try:
            if server_proc:
                server_proc.wait(timeout=5)
        except Exception:
            pass
        try:
            _endpoint_file(data_dir).unlink(missing_ok=True)
        except Exception:
            pass


if __name__ == "__main__":
    try:
        if "--server" in sys.argv:
            try:
                i = sys.argv.index("--server")
                host = sys.argv[i + 1]
                port = int(sys.argv[i + 2])
            except Exception:
                host, port = choose_host_and_port()
            server_main(host, port)
        else:
            main()
    except Exception as e:
        try:
            data_dir = _desktop_data_dir()
            log_file = setup_desktop_logging(data_dir)
            logger.exception("Fatal crash: %s", e)
            _messagebox_info(
                "Desktop App Error",
                "App crashed while starting.\n\n"
                f"Logs: {log_file}\n\n"
                f"Error: {e}\n\n"
                f"Traceback (last):\n{traceback.format_exc()[-1500:]}",
            )
        except Exception:
            pass
        raise
