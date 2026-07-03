"""Версия приложения и проверка обновлений на GitHub.

Номер версии хранится в файле VERSION в корне проекта. При запуске
приложение в фоне сравнивает его с VERSION в ветке main на GitHub и,
если там новее, показывает подсказку обновиться (update.bat/update.sh).
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
    """Вернуть номер новой версии с GitHub или None, если обновлений нет.

    Сетевые ошибки пробрасываются — вызывающий код глушит их сам,
    чтобы отсутствие интернета не мешало работе приложения.
    """
    request = urllib.request.Request(
        VERSION_URL, headers={"User-Agent": "MediaGrab"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        remote = response.read().decode("utf-8", "replace").strip()
    if remote and _parse(remote) > _parse(local_version()):
        return remote
    return None
