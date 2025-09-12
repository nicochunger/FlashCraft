import os
import time
import logging
import platform
import subprocess
import shutil
import requests
from typing import Optional, Tuple

from dotenv import load_dotenv

load_dotenv()

ANKI_CONNECT_URL = os.getenv("ANKI_CONNECT_URL")
ANKI_API_KEY = os.getenv("ANKI_API_KEY")


def _is_wsl() -> bool:
    return bool(
        os.environ.get("WSL_DISTRO_NAME")
        or "microsoft" in platform.release().lower()
        or "microsoft" in platform.version().lower()
    )


def _anki_connect_ok(url: str = ANKI_CONNECT_URL, timeout: float = 3.0) -> bool:
    headers = {}
    if ANKI_API_KEY:
        headers["Anki-Connect-Key"] = ANKI_API_KEY
    try:
        r = requests.post(
            url,
            json={"action": "version", "version": 6},
            headers=headers,
            timeout=timeout,
        )
        return r.status_code == 200
    except requests.RequestException:
        return False


def _prepare_gui_env(env: dict) -> dict:
    """
    Make GUI env sane for both native Linux and WSLg, especially for cron/systemd.
    We don't clobber valid values supplied by WSLg (WAYLAND_DISPLAY / DISPLAY).
    """
    # Provide a minimal GUI fallback if nothing is set
    if not env.get("WAYLAND_DISPLAY") and not env.get("DISPLAY"):
        # WSLg usually injects WAYLAND_DISPLAY; if it's missing (cron), XWayland fallback works.
        env.setdefault("DISPLAY", ":0")

    # Wayland/X need a runtime dir; non-interactive shells often lack it
    if not env.get("XDG_RUNTIME_DIR"):
        xdg = f"/run/user/{os.getuid()}"
        try:
            os.makedirs(xdg, exist_ok=True)
        except Exception:
            pass
        env["XDG_RUNTIME_DIR"] = xdg

    # Optional: if you hit GPU glitches, uncomment the next line to force software rendering
    # env["QSG_RHI_BACKEND"] = "software"

    return env


def _find_anki_binary() -> Optional[str]:
    for candidate in (
        shutil.which("anki"),
        "/usr/local/bin/anki",
        "/usr/bin/anki",
        os.path.expanduser("~/.local/bin/anki"),
    ):
        if candidate and os.path.exists(candidate):
            return candidate
    return None


def _start_linux_anki(env: dict) -> Optional[subprocess.Popen]:
    anki_cmd = _find_anki_binary()
    if not anki_cmd:
        logging.error(
            "Could not find 'anki' executable on PATH or in common locations."
        )
        return None
    try:
        logf = open("anki_output.log", "ab", buffering=0)
        proc = subprocess.Popen(
            [anki_cmd],
            stdout=logf,
            stderr=logf,
            env=env,
            close_fds=True,
        )
        logging.info("Starting Anki (Linux): %s", anki_cmd)
        return proc
    except Exception as e:
        logging.exception("Failed to start Anki: %s", e)
        return None


def ensure_anki_running(
    timeout_seconds: int = 60,
) -> Tuple[bool, Optional[subprocess.Popen]]:
    """
    Ensure Anki (Linux) is running and AnkiConnect is responding at ANKI_CONNECT_URL.
    Works on native Linux and on Ubuntu under WSLg. Will NEVER try to start Windows Anki.
    Returns: (ok, proc_started_or_None)
    """
    env = _prepare_gui_env(dict(os.environ))

    # 1) Fast path: already up and responding
    if _anki_connect_ok(ANKI_CONNECT_URL):
        logging.info("AnkiConnect already responding at %s", ANKI_CONNECT_URL)
        return True, None

    # 2) Not responding -> start Linux Anki (on both native + WSL)
    proc = _start_linux_anki(env)
    if proc is None:
        return False, None

    # 3) Wait for AnkiConnect (add-on must be installed/enabled in this profile)
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if _anki_connect_ok(ANKI_CONNECT_URL):
            logging.info("AnkiConnect is ready at %s.", ANKI_CONNECT_URL)
            return True, proc
        time.sleep(1)

    logging.error(
        "Timed out waiting for AnkiConnect at %s. Make sure the AnkiConnect add-on is installed and enabled.",
        ANKI_CONNECT_URL,
    )
    # Only terminate what we started
    try:
        proc.terminate()
    except Exception:
        pass
    return False, None
