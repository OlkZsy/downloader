"""Настройки и история загрузок.

Хранятся в JSON-файле в домашней папке пользователя
(~/.mediagrab/config.json), поэтому папка загрузки, выбранный формат,
качество и история переживают закрытие приложения.
"""

import json
import time
from pathlib import Path

CONFIG_DIR = Path.home() / ".mediagrab"
CONFIG_FILE = CONFIG_DIR / "config.json"
#: cookies браузера для сервисов, требующих вход: <id сервиса>.txt
#: (например x.txt) или all.txt для всех сервисов; см. docs/COOKIES.md
COOKIES_DIR = CONFIG_DIR / "cookies"

MAX_HISTORY = 200

DEFAULTS = {
    "profile_name": "",
    "download_dir": str(Path.home() / "Downloads"),
    "format": "mp3",
    "quality": {"mp3": "192", "mp4": "720p"},
    "history": [],
}


class Config:
    def __init__(self):
        self.data = json.loads(json.dumps(DEFAULTS))  # глубокая копия
        if CONFIG_FILE.exists():
            try:
                stored = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                for key in DEFAULTS:
                    if key in stored:
                        self.data[key] = stored[key]
            except (json.JSONDecodeError, OSError):
                pass  # повреждённый конфиг — начинаем с настроек по умолчанию

    def save(self):
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            CONFIG_FILE.write_text(
                json.dumps(self.data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass  # не мешаем работе приложения, если диск недоступен

    # --- профиль ----------------------------------------------------------
    @property
    def profile_name(self) -> str:
        return self.data.get("profile_name", "")

    @profile_name.setter
    def profile_name(self, value: str):
        self.data["profile_name"] = value
        self.save()

    # --- папка загрузки -------------------------------------------------
    @property
    def download_dir(self) -> str:
        return self.data["download_dir"]

    @download_dir.setter
    def download_dir(self, value: str):
        self.data["download_dir"] = value
        self.save()

    # --- формат и качество ----------------------------------------------
    @property
    def format(self) -> str:
        return self.data["format"]

    @format.setter
    def format(self, value: str):
        self.data["format"] = value
        self.save()

    def quality_for(self, fmt: str) -> str:
        return self.data["quality"].get(fmt, DEFAULTS["quality"][fmt])

    def set_quality(self, fmt: str, value: str):
        self.data["quality"][fmt] = value
        self.save()

    # --- история ----------------------------------------------------------
    @property
    def history(self) -> list:
        return self.data["history"]

    def add_history(self, url: str, service: str, fmt: str, status: str,
                    filename: str | None = None) -> dict:
        entry = {
            "url": url,
            "service": service,
            "format": fmt,
            "status": status,
            "file": filename,
            "ts": int(time.time()),
        }
        self.data["history"].insert(0, entry)
        del self.data["history"][MAX_HISTORY:]
        self.save()
        return entry

    def update_history(self, entry: dict, status: str,
                       filename: str | None = None, *,
                       error: str | None = None,
                       hint: str | None = None,
                       report_path: str | None = None):
        entry["status"] = status
        if filename:
            entry["file"] = filename
        if error is not None:
            entry["error"] = error
        if hint is not None:
            entry["hint"] = hint
        if report_path is not None:
            entry["report_path"] = report_path
        self.save()

    def remove_history(self, entry: dict):
        try:
            self.data["history"].remove(entry)
        except ValueError:
            pass
        self.save()

    def clear_history(self, keep: list | None = None):
        """Очистить историю, сохранив записи из keep (активные загрузки)."""
        keep = keep or []
        self.data["history"] = [e for e in self.data["history"] if e in keep]
        self.save()
