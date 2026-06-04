from __future__ import annotations

import logging
import os
import socket
import subprocess
import sys
import time
import shutil
from pathlib import Path
from typing import Optional

from django.conf import settings

_GATEWAY_PROC: Optional[subprocess.Popen] = None
logger = logging.getLogger(__name__)


def _is_truthy(value: str) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _parse_host_port(base_url: str) -> tuple[str, int]:
    """
    Very small parser for known local URLs like:
      http://127.0.0.1:3100
      http://localhost:3100
    """
    raw = (base_url or "").strip().lower()
    raw = raw.replace("http://", "").replace("https://", "")
    host = raw.split("/", 1)[0].strip()
    if ":" in host:
        h, p = host.rsplit(":", 1)
        try:
            return (h.strip() or "127.0.0.1", int(p))
        except Exception:
            return (h.strip() or "127.0.0.1", 3100)
    return (host or "127.0.0.1", 80)


def _is_port_open(host: str, port: int, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except Exception:
        return False


def _detect_chrome_exe() -> str:
    # Common Windows Chrome installs
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    try:
        local = os.environ.get("LOCALAPPDATA") or ""
        if local:
            candidates.append(str(Path(local) / "Google" / "Chrome" / "Application" / "chrome.exe"))
    except Exception:
        pass

    for p in candidates:
        try:
            if p and Path(p).exists():
                return p
        except Exception:
            continue
    return ""


def _detect_node_exe() -> str:
    # Prefer PATH
    try:
        p = shutil.which("node")
        if p and Path(p).exists():
            return p
    except Exception:
        pass

    # Common Windows install path
    candidates = [
        r"C:\Program Files\nodejs\node.exe",
        r"C:\Program Files (x86)\nodejs\node.exe",
    ]
    for p in candidates:
        try:
            if p and Path(p).exists():
                return p
        except Exception:
            continue
    return ""


def _should_autostart_now() -> bool:
    # Only during `manage.py runserver`
    if "runserver" not in sys.argv:
        return False

    # Avoid starting in the Django autoreloader parent (prevents repeated start/stop).
    # - With autoreload: child process has RUN_MAIN=true
    # - With --noreload: RUN_MAIN may be unset, so allow.
    if "--noreload" not in sys.argv:
        run_main = (os.environ.get("RUN_MAIN") or "").strip().lower()
        if run_main != "true":
            return False

    return bool(getattr(settings, "WA_GATEWAY_AUTOSTART", False))


def ensure_gateway_running() -> None:
    """
    Starts the bundled Node gateway automatically during `manage.py runserver`,
    so users don't have to run `npm run start` manually.

    This is intended for local/dev/desktop setups only.
    """
    global _GATEWAY_PROC

    try:
        if not _should_autostart_now():
            return
    except Exception:
        return

    base_url = str(getattr(settings, "WA_GATEWAY_BASE_URL", "") or "").strip()
    if not base_url:
        logger.debug("WA_GATEWAY_BASE_URL not set; skipping autostart")
        return

    host, port = _parse_host_port(base_url)
    if _is_port_open(host, port):
        return

    repo_root = Path(getattr(settings, "BASE_DIR", Path.cwd()))
    gw_dir = repo_root / "whatsapp_gateway"
    if not gw_dir.exists():
        logger.debug("whatsapp_gateway dir missing; skipping autostart")
        return

    # If already started in this process, don't spawn again.
    if _GATEWAY_PROC and _GATEWAY_PROC.poll() is None:
        return

    node_exe = _detect_node_exe()
    if not node_exe:
        logger.warning("Node.js not found; WhatsApp gateway autostart disabled")
        return

    # Cross-process start lock to avoid double-spawning during Django autoreload.
    lock_dir = gw_dir / ".sessions"
    try:
        lock_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        lock_dir = gw_dir
    lock_path = lock_dir / "gateway_autostart.lock"

    lock_fd = None
    try:
        lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(lock_fd, f"pid={os.getpid()} time={time.time()}\n".encode("utf-8"))
    except FileExistsError:
        return
    except Exception:
        return

    env = os.environ.copy()

    # If Puppeteer cannot launch its bundled Chromium on some Windows setups,
    # using system Chrome often fixes it.
    if not env.get("PUPPETEER_EXECUTABLE_PATH"):
        chrome = _detect_chrome_exe()
        if chrome:
            env["PUPPETEER_EXECUTABLE_PATH"] = chrome

    try:
        # Start in background (no extra terminal windows).
        flags = 0
        flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        flags |= getattr(subprocess, "DETACHED_PROCESS", 0)

        log_dir = gw_dir / "logs"
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            log_dir = gw_dir
        out_path = log_dir / "gateway_autostart.log"
        out = open(out_path, "a", encoding="utf-8", errors="ignore")

        _GATEWAY_PROC = subprocess.Popen(
            [node_exe, "src\\server.js"],
            cwd=str(gw_dir),
            env=env,
            stdout=out,
            stderr=out,
            creationflags=flags,
        )

        # Wait briefly so the port opens before releasing the lock (prevents duplicate spawns).
        deadline = time.time() + 6.0
        while time.time() < deadline:
            if _is_port_open(host, port, timeout=0.25):
                break
            time.sleep(0.25)
    except Exception:
        _GATEWAY_PROC = None
        return
    finally:
        try:
            if lock_fd is not None:
                os.close(lock_fd)
        except Exception:
            pass
        try:
            if lock_path.exists():
                lock_path.unlink(missing_ok=True)  # type: ignore[arg-type]
        except Exception:
            pass

    # Important: do NOT auto-terminate the gateway on Django autoreload.
    # Keeping it running avoids repeated QR failures and "gateway offline" during code reloads.


def _is_local_gateway(base_url: str) -> bool:
    u = (base_url or "").strip().lower()
    return u.startswith(("http://127.0.0.1", "http://localhost", "https://127.0.0.1", "https://localhost"))


def restart_local_gateway() -> bool:
    """
    Best-effort local restart for the bundled gateway (Windows).

    - Kills the process listening on WA_GATEWAY_BASE_URL port (if owned by current user)
    - Starts gateway again

    Returns True if a restart was triggered.
    """
    base_url = str(getattr(settings, "WA_GATEWAY_BASE_URL", "") or "").strip()
    if not base_url or not _is_local_gateway(base_url):
        return False

    host, port = _parse_host_port(base_url)

    # Find PID via netstat (no admin required)
    pid = ""
    try:
        out = subprocess.check_output(["cmd.exe", "/c", f"netstat -ano | findstr :{int(port)} | findstr LISTENING"], text=True, errors="ignore")
        for line in (out or "").splitlines():
            parts = [p for p in line.split(" ") if p.strip()]
            if parts and parts[-1].isdigit():
                pid = parts[-1]
                break
    except Exception:
        pid = ""

    if pid:
        try:
            subprocess.check_call(["cmd.exe", "/c", f"taskkill /PID {pid} /F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            # If we can't kill it, don't attempt to start another on the same port.
            return False

    # Wait briefly for port to free
    deadline = time.time() + 6.0
    while time.time() < deadline:
        if not _is_port_open(host, port, timeout=0.2):
            break
        time.sleep(0.25)

    ensure_gateway_running()
    return True
