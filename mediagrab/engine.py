"""Движок загрузки: обёртка над yt-dlp, работающая в фоновых потоках.

GUI кладёт задачи через DownloadManager.submit() и забирает события
прогресса из очереди DownloadManager.events (кортежи
(task_id, event, payload)):

    ("queued", None)       — задача поставлена в очередь
    ("start", None)        — загрузка началась
    ("progress", 42.5)     — процент загрузки
    ("processing", None)   — конвертация (ffmpeg)
    ("done", "/полный/путь/к/файлу.mp3") — готово
    ("error", {"message", "hint", "report", "report_path"}) — ошибка

Перед загрузкой запрашиваются метаданные, из них строится имя файла
«Автор - Название» (когда метаданные это позволяют), а при совпадении
имён добавляется индекс: «Название (2)».
"""

import itertools
import os
import platform
import queue
import sys
import threading
import time
import traceback

from .config import CONFIG_DIR, COOKIES_DIR

LOGS_DIR = CONFIG_DIR / "logs"


def find_cookie_file(plugin):
    """Файл cookies для сервиса: <id>.txt, иначе общий all.txt."""
    candidates = []
    if plugin is not None:
        candidates.append(COOKIES_DIR / f"{plugin.id}.txt")
    candidates.append(COOKIES_DIR / "all.txt")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None

MP4_HEIGHTS = {"360p": 360, "480p": 480, "720p": 720, "1080p": 1080}
MP3_BITRATES = ("128", "192", "320")
MP4_QUALITIES = ("360p", "480p", "720p", "1080p", "Максимум")


def build_options(fmt: str, quality: str, outdir: str) -> dict:
    """Собрать словарь опций yt-dlp для формата и качества."""
    opts = {
        # заменяется на точное имя файла в _worker после чтения метаданных
        "outtmpl": os.path.join(outdir, "%(title)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    if fmt == "mp3":
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": quality,
        }]
    else:
        height = MP4_HEIGHTS.get(quality)
        h = f"[height<={height}]" if height else ""
        # Сначала пытаемся взять видео mp4 + звук m4a (AAC): такой файл
        # играет со звуком в любом плеере. Прочие комбинации (например,
        # звук Opus) дают «немой» mp4 в стандартных плеерах Windows —
        # для них в _worker включается перекодировка звука в AAC.
        opts["format"] = (
            f"bestvideo{h}[ext=mp4]+bestaudio[ext=m4a]/"
            f"bestvideo{h}+bestaudio/best{h}/best"
        )
        opts["merge_output_format"] = "mp4"
    return opts


def display_title(info: dict, fmt: str) -> str:
    """Имя файла «Автор - Название», когда метаданные это позволяют."""
    artist = (info.get("artist") or info.get("creator") or "").strip()
    track = (info.get("track") or "").strip()
    if artist and track:
        return f"{artist} - {track}"
    title = (info.get("title") or "download").strip()
    if fmt == "mp3" and " - " not in title:
        uploader = (info.get("uploader") or info.get("channel") or "").strip()
        for suffix in (" - Topic", " – Topic"):
            if uploader.endswith(suffix):
                uploader = uploader[: -len(suffix)].strip()
        if uploader and uploader.lower() not in title.lower():
            return f"{uploader} - {title}"
    return title


def unique_path(outdir: str, base: str, ext: str) -> str:
    """Свободное имя файла: «Название.mp3», «Название (2).mp3», …"""
    candidate = os.path.join(outdir, f"{base}.{ext}")
    counter = 2
    while os.path.exists(candidate):
        candidate = os.path.join(outdir, f"{base} ({counter}).{ext}")
        counter += 1
    return candidate


def short_error(exc: Exception) -> str:
    text = str(exc)
    if text.startswith("ERROR: "):
        text = text[len("ERROR: "):]
    return text.splitlines()[0][:300] if text else exc.__class__.__name__


# --- подсказки по типовым ошибкам ---------------------------------------
_HINTS = (
    (("ffmpeg",),
     "Не найден ffmpeg — без него не работают mp3 и склейка видео. "
     "Установите его по инструкции из README.md (раздел вашей ОС) "
     "и повторите загрузку."),
    (("unsupported url",),
     "Эта ссылка не поддерживается. Проверьте, что она ведёт на "
     "конкретное видео или трек, а не на профиль, поиск или главную "
     "страницу сервиса."),
    (("private", "login", "sign in", "logged in", "age", "nsfw",
      "authentication", "account", "cookies"),
     "Контент приватный или с возрастным ограничением — сервис требует "
     "вход в аккаунт. Если это ваш аккаунт, подключите cookies браузера: "
     "инструкция в docs/COOKIES.md (папка cookies открывается через "
     "кнопку 👤 → «Папка cookies»)."),
    (("429", "too many requests", "rate limit"),
     "Сервис временно ограничил количество запросов. Подождите "
     "несколько минут и попробуйте снова."),
    (("geo", "not available in your country", "region"),
     "Контент недоступен в вашем регионе."),
    (("unable to download", "tunnel", "proxy", "getaddrinfo",
      "timed out", "connection", "network", "ssl"),
     "Похоже на проблему с сетью. Проверьте интернет-соединение и "
     "повторите попытку."),
    (("video unavailable", "removed", "deleted", "not exist",
      "no longer available"),
     "Видео/трек удалён или больше недоступен на сервисе."),
)

_DEFAULT_HINT = (
    "Сервисы часто меняют свои сайты, и загрузчик за ними обновляется. "
    "Сначала обновите yt-dlp: запустите update.bat (Windows) или "
    "./update.sh (macOS/Linux) и повторите загрузку. Если не помогло — "
    "отправьте разработчику файл отчёта (кнопка «Скопировать отчёт»)."
)


def hint_for(message: str, plugin) -> str:
    low = message.lower()
    hint = _DEFAULT_HINT
    for keywords, text in _HINTS:
        if any(k in low for k in keywords):
            hint = text
            break
    extra = getattr(plugin, "error_hint", "") if plugin else ""
    if extra:
        hint = f"{hint}\n\n{extra}"
    return hint


def make_error_report(exc: Exception, *, task_id: int, url: str, plugin,
                      fmt: str, quality: str) -> dict:
    try:
        import yt_dlp
        ytdlp_version = yt_dlp.version.__version__
    except Exception:
        ytdlp_version = "не установлен"
    message = short_error(exc)
    report = "\n".join([
        "MediaGrab — отчёт об ошибке загрузки",
        f"Время:   {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Ссылка:  {url}",
        f"Сервис:  {plugin.name if plugin else 'Авто'}",
        f"Формат:  {fmt}, качество: {quality}",
        f"ОС:      {platform.platform()}",
        f"Python:  {sys.version.split()[0]}",
        f"yt-dlp:  {ytdlp_version}",
        "",
        "Ошибка:",
        str(exc),
        "",
        "Traceback:",
        traceback.format_exc(),
    ])
    report_path = ""
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        name = time.strftime(f"error-%Y%m%d-%H%M%S-{task_id}.txt")
        path = LOGS_DIR / name
        path.write_text(report, encoding="utf-8")
        report_path = str(path)
    except OSError:
        pass
    return {
        "message": message,
        "hint": hint_for(message, plugin),
        "report": report,
        "report_path": report_path,
    }


class DownloadManager:
    def __init__(self, max_parallel: int = 2):
        self.events: queue.Queue = queue.Queue()
        self._sem = threading.Semaphore(max_parallel)
        self._ids = itertools.count(1)

    def submit(self, url: str, plugin, fmt: str, quality: str,
               outdir: str) -> int:
        task_id = next(self._ids)
        self.events.put((task_id, "queued", None))
        threading.Thread(
            target=self._worker,
            args=(task_id, url, plugin, fmt, quality, outdir),
            daemon=True,
        ).start()
        return task_id

    def _worker(self, task_id, url, plugin, fmt, quality, outdir):
        with self._sem:
            try:
                import yt_dlp
                from yt_dlp.utils import sanitize_filename
            except ImportError as exc:
                self.events.put((task_id, "error", {
                    "message": "Не установлен yt-dlp",
                    "hint": "Выполните установку зависимостей: install.bat "
                            "(Windows) или ./install.sh (macOS/Linux).",
                    "report": str(exc),
                    "report_path": "",
                }))
                return
            self.events.put((task_id, "start", None))

            def hook(d):
                status = d.get("status")
                if status == "downloading":
                    total = (d.get("total_bytes")
                             or d.get("total_bytes_estimate"))
                    done = d.get("downloaded_bytes") or 0
                    if total:
                        self.events.put(
                            (task_id, "progress", done * 100.0 / total))
                elif status == "finished":
                    self.events.put((task_id, "processing", None))

            try:
                os.makedirs(outdir, exist_ok=True)
                real_url = plugin.prepare(url) if plugin else url
                opts = build_options(fmt, quality, outdir)
                if plugin:
                    opts = plugin.tweak_options(opts, fmt)
                cookie_file = find_cookie_file(plugin)
                if cookie_file:
                    opts["cookiefile"] = str(cookie_file)

                # 1) метаданные — из них имя файла и выбранные форматы
                probe = {k: v for k, v in opts.items()
                         if k not in ("postprocessors",
                                      "merge_output_format",
                                      "postprocessor_args")}
                probe["skip_download"] = True
                with yt_dlp.YoutubeDL(probe) as ydl:
                    info = ydl.extract_info(real_url, download=False)
                if info and info.get("entries") is not None:
                    entries = [e for e in list(info["entries"]) if e]
                    if not entries:
                        raise RuntimeError(
                            "по этой ссылке ничего не найдено")
                    info = entries[0]
                if not info:
                    raise RuntimeError("не удалось получить данные по ссылке")

                # 2) имя файла: «Автор - Название», дубликаты — с « (2)»
                ext = "mp3" if fmt == "mp3" else "mp4"
                base = sanitize_filename(display_title(info, fmt))
                final_path = unique_path(outdir, base, ext)
                stem = os.path.splitext(final_path)[0]
                # % — служебный символ шаблона outtmpl, экранируем
                opts["outtmpl"] = stem.replace("%", "%%") + ".%(ext)s"

                # 3) если в mp4 склеивается звук не-AAC (например Opus),
                # перекодируем его: иначе стандартные плееры Windows
                # играют такой файл без звука
                if fmt == "mp4":
                    requested = info.get("requested_formats") or [info]
                    acodecs = {f.get("acodec") for f in requested
                               if f.get("acodec") not in (None, "none")}
                    if acodecs and any(
                            not str(c).startswith(("mp4a", "aac"))
                            for c in acodecs):
                        opts["postprocessor_args"] = {"merger": [
                            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k"]}

                opts["progress_hooks"] = [hook]
                target = (info.get("webpage_url")
                          or info.get("original_url") or real_url)
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([target])

                if not os.path.exists(final_path):
                    # подстраховка: ищем файл по основе имени
                    import glob
                    matches = glob.glob(glob.escape(stem) + ".*")
                    if matches:
                        final_path = matches[0]
                self.events.put((task_id, "done", final_path))
            except Exception as exc:  # noqa: BLE001 — любой сбой показываем в UI
                self.events.put((task_id, "error", make_error_report(
                    exc, task_id=task_id, url=url, plugin=plugin,
                    fmt=fmt, quality=quality)))
