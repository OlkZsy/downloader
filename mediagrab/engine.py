"""Движок загрузки: обёртка над yt-dlp, работающая в фоновых потоках.

GUI кладёт задачи через DownloadManager.submit() и забирает события
прогресса из очереди DownloadManager.events (кортежи
(task_id, event, payload)):

    ("queued", None)       — задача поставлена в очередь
    ("start", None)        — загрузка началась
    ("progress", 42.5)     — процент загрузки
    ("processing", None)   — конвертация (ffmpeg)
    ("done", "файл.mp3")   — готово
    ("error", "текст")     — ошибка
"""

import itertools
import os
import queue
import threading

MP4_HEIGHTS = {"360p": 360, "480p": 480, "720p": 720, "1080p": 1080}
MP3_BITRATES = ("128", "192", "320")
MP4_QUALITIES = ("360p", "480p", "720p", "1080p", "Максимум")


def build_options(fmt: str, quality: str, outdir: str) -> dict:
    """Собрать словарь опций yt-dlp для формата и качества."""
    opts = {
        "outtmpl": os.path.join(outdir, "%(title)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": False,
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
        if height:
            opts["format"] = (
                f"bestvideo[height<={height}]+bestaudio/"
                f"best[height<={height}]/best"
            )
        else:  # «Максимум»
            opts["format"] = "bestvideo+bestaudio/best"
        opts["merge_output_format"] = "mp4"
    return opts


def short_error(exc: Exception) -> str:
    text = str(exc)
    # yt-dlp добавляет префикс "ERROR: " — убираем для чистоты
    if text.startswith("ERROR: "):
        text = text[len("ERROR: "):]
    return text.splitlines()[0][:200] if text else exc.__class__.__name__


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
            except ImportError:
                self.events.put((task_id, "error",
                                 "Не установлен yt-dlp. Выполните: "
                                 "pip install -r requirements.txt"))
                return
            self.events.put((task_id, "start", None))
            result = {"file": None}

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
                    result["file"] = os.path.basename(
                        d.get("filename") or "")
                    self.events.put((task_id, "processing", None))

            try:
                os.makedirs(outdir, exist_ok=True)
                real_url = plugin.prepare(url) if plugin else url
                opts = build_options(fmt, quality, outdir)
                if plugin:
                    opts = plugin.tweak_options(opts, fmt)
                opts["progress_hooks"] = [hook]

                def pp_hook(d):
                    info = d.get("info_dict") or {}
                    name = info.get("filepath") or info.get("_filename")
                    if name:
                        result["file"] = os.path.basename(name)

                opts["postprocessor_hooks"] = [pp_hook]
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([real_url])
                filename = result["file"]
                if filename and fmt == "mp3":
                    filename = os.path.splitext(filename)[0] + ".mp3"
                self.events.put((task_id, "done", filename))
            except Exception as exc:  # noqa: BLE001 — любой сбой показываем в UI
                self.events.put((task_id, "error", short_error(exc)))
