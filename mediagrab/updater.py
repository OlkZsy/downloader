"""Updating the libraries the downloader depends on (yt-dlp).

Services change their sites constantly, and almost every "it suddenly
stopped downloading" case is fixed by a newer yt-dlp. The profile window
runs update_ytdlp() so that the user does not have to open a terminal.
"""

import subprocess
import sys


def ytdlp_version() -> str:
    try:
        import yt_dlp
        return yt_dlp.version.__version__
    except Exception:  # noqa: BLE001 — any import trouble means "no library"
        return "not installed"


def _hidden_console() -> dict:
    """Keep pip from flashing a console window on Windows."""
    if sys.platform == "win32":
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {}


def update_ytdlp(timeout: int = 600) -> tuple:
    """Upgrade yt-dlp with pip. Returns (ok, message for the user)."""
    command = [sys.executable, "-m", "pip", "install", "-U",
               "--disable-pip-version-check", "yt-dlp"]
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=timeout, **_hidden_console())
    except subprocess.TimeoutExpired:
        return False, "the update took too long — check your connection"
    except Exception as exc:  # noqa: BLE001 — shown to the user as-is
        return False, str(exc)

    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
        detail = lines[-1] if lines else "pip reported an error"
        return False, detail[:200]

    for line in output.splitlines():
        if line.startswith("Successfully installed"):
            installed = line.split(" ", 2)[-1].strip()
            return True, (f"Updated: {installed}. Restart MediaGrab "
                          "for the new version to take effect.")
    if "already satisfied" in output:
        return True, f"Already the latest version ({ytdlp_version()})."
    return True, "yt-dlp is up to date."
