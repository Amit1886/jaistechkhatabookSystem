#!/usr/bin/env python
import os
import sys
import subprocess
import time
import urllib.request


def _should_disable_runserver_reloader(argv: list[str]) -> bool:
    if os.name != "nt":
        return False
    if len(argv) < 2 or argv[1] != "runserver":
        return False
    if "--noreload" in argv:
        return False
    allow_reload = (os.environ.get("DJANGO_RUNSERVER_RELOAD") or "").strip().lower()
    return allow_reload not in {"1", "true", "yes", "on"}


def _should_auto_migrate_on_runserver(argv: list[str]) -> bool:
    """
    Desktop/dev stability helper:

    When developers start the server via `python manage.py runserver` (often from VS Code),
    it's easy to forget running migrations after pulling new changes. That results in
    runtime 500s like "no such column ...".

    We auto-run `migrate` for `runserver` unless explicitly disabled.
    """
    env_value = (os.environ.get("AUTO_MIGRATE_ON_RUNSERVER") or "").strip().lower()
    if env_value in {"0", "false", "no", "off"}:
        return False

    # On Windows desktop/dev, keep runserver fast and predictable. Run migrations
    # explicitly when you actually need schema changes applied.
    if os.name == "nt":
        return env_value in {"1", "true", "yes", "on"}

    # Management options may appear before the command; keep it simple and look for runserver anywhere.
    return "runserver" in argv


def _truthy_env(name: str, default: str = "") -> bool:
    v = (os.environ.get(name) or default).strip().lower()
    return v in {"1", "true", "yes", "on"}


def _is_local_gateway_url(url: str) -> bool:
    u = (url or "").strip().lower().rstrip("/")
    return u.startswith("http://127.0.0.1:3100") or u.startswith("http://localhost:3100")


def _gateway_health_ok(base_url: str) -> bool:
    try:
        u = (base_url or "").rstrip("/") + "/health"
        req = urllib.request.Request(u, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=1.8) as resp:
            return int(getattr(resp, "status", 200) or 200) < 400
    except Exception:
        return False


def _should_autostart_gateway(argv: list[str]) -> bool:
    if os.name != "nt":
        return False
    if "runserver" not in argv:
        return False
    # Default: do NOT auto-start the local gateway unless explicitly enabled.
    # This avoids intrusive Windows popups when the local gateway service is missing.
    if not _truthy_env("WA_GATEWAY_AUTOSTART", "false"):
        return False
    base_url = os.environ.get("WA_GATEWAY_BASE_URL") or ""
    if not _is_local_gateway_url(base_url):
        return False
    return os.path.exists(os.path.join(os.path.dirname(__file__), "whatsapp_gateway", "run_forever.cmd"))


def _autostart_gateway_if_needed():
    base_url = (os.environ.get("WA_GATEWAY_BASE_URL") or "").rstrip("/")
    if not base_url:
        return

    if _gateway_health_ok(base_url):
        return

    gateway_dir = os.path.join(os.path.dirname(__file__), "whatsapp_gateway")
    cmd_path = os.path.join(gateway_dir, "run_forever.cmd")

    # If something else is already bound to 3100 (but not our gateway), avoid looping.
    # We'll still attempt to start; if it fails, Django will show "Gateway not reachable".
    try:
        # Launch the gateway supervisor directly (no Windows "start" dialog that can misinterpret the title).
        subprocess.Popen(
            [cmd_path],
            cwd=gateway_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        )
        # Give it a moment to bind.
        time.sleep(1.2)
    except Exception as exc:
        sys.stderr.write(f"\n[manage.py] WhatsApp gateway auto-start failed: {exc}\n")
        return

    if not _gateway_health_ok(base_url):
        sys.stderr.write("\n[manage.py] WhatsApp gateway did not come online (port 3100).\n")
        sys.stderr.write("[manage.py] If port 3100 is already in use, stop the other process and restart runserver.\n\n")


def main():
    # Windows desktop/dev defaults:
    # Keep *all* management commands pointed at the same local desktop data dir
    # as `runserver`, otherwise it's easy to accidentally migrate the wrong DB
    # and hit runtime errors like: "no such table: django_site".
    #
    # NOTE: These are `setdefault()` so batch scripts / CI / production env can
    # override them (e.g. `SQLITE_PATH`, `KP_APP_DATA_DIR`, `DATABASE_URL`).
    if os.name == "nt":
        os.environ.setdefault("DESKTOP_MODE", "1")
        os.environ.setdefault("LIGHTWEIGHT_DEPLOYMENT", "1")
        os.environ.setdefault("KP_APP_DATA_DIR", os.path.join(os.path.dirname(__file__), "_appdata", "Billentra"))
        os.environ.setdefault(
            "KP_DESKTOP_LOG_FILE",
            os.path.join(os.path.dirname(__file__), "_appdata", "Billentra", "logs", "desktop.log"),
        )

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'khatapro.settings')
    from django.core.management import execute_from_command_line
    argv = sys.argv[:]
    if _should_disable_runserver_reloader(argv):
        argv.append("--noreload")

    if _should_auto_migrate_on_runserver(argv):
        try:
            import django

            django.setup()
            from django.core.management import call_command

            # Keep output minimal but visible in dev consoles.
            call_command("migrate", interactive=False, verbosity=1)
        except SystemExit:
            raise
        except Exception as exc:
            sys.stderr.write(f"\n[manage.py] Auto-migrate failed: {exc}\n")
            sys.stderr.write("[manage.py] Fix migration error, then re-run runserver.\n\n")
            raise

    if _should_autostart_gateway(argv):
        _autostart_gateway_if_needed()

    execute_from_command_line(argv)
if __name__ == '__main__': main()
