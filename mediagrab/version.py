"""Application version and update checks against GitHub.

The version number is stored in the VERSION file at the project root.
On startup the app compares it in the background with VERSION on the
main branch on GitHub and, when a newer one exists, suggests running
update.bat/update.sh.
"""

import re
import urllib.request
from pathlib import Path

REPO = "OlkZsy/downloader"
VERSION_URL = f"https://raw.githubusercontent.com/{REPO}/main/VERSION"

_ROOT = Path(__file__).resolve().parent.parent


def local_version() -> str:
    try:
        return (_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        from . import __version__
        return __version__


def _parse(value: str) -> tuple:
    numbers = re.findall(r"\d+", value)
    return tuple(int(n) for n in numbers[:4]) if numbers else (0,)


def check_remote(timeout: int = 6):
    """Return the newer version number from GitHub, or None.

    Network errors propagate — the caller silences them so that having
    no internet connection never disturbs the app.
    """
    request = urllib.request.Request(
        VERSION_URL, headers={"User-Agent": "MediaGrab"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        remote = response.read().decode("utf-8", "replace").strip()
    if remote and _parse(remote) > _parse(local_version()):
        return remote
    return None
