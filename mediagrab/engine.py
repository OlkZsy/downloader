"""Download engine: a wrapper around yt-dlp running in background threads.

The GUI submits jobs via DownloadManager.submit() and consumes progress
events from the DownloadManager.events queue (tuples of
(task_id, event, payload)):

    ("queued", None)       — job added to the queue
    ("start", None)        — download started
    ("progress", 42.5)     — download percentage
    ("processing", None)   — conversion (ffmpeg)
    ("retry", (2, 4))      — attempt 2 of 4 with different options
    ("done", "/full/path/to/file.mp3") — finished
    ("error", {"message", "hint", "report", "report_path"}) — failed

Metadata is fetched before downloading; it is used to build an
"Artist - Title" file name (when the metadata allows it), and name
clashes get an index appended: "Title (2)".
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
    """Cookie file for a service: <id>.txt, with all.txt as fallback."""
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
MP4_QUALITIES = ("360p", "480p", "720p", "1080p", "Max")


def build_options(fmt: str, quality: str, outdir: str) -> dict:
    """Build the yt-dlp options dict for a format and quality."""
    opts = {
        # replaced with the exact file name in _worker after metadata probe
        "outtmpl": os.path.join(outdir, "%(title)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        # services occasionally reject single requests (HTTP 403 and the
        # like); retrying the request usually gets through
        "retries": 10,
        "fragment_retries": 10,
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
        # Prefer mp4 video + m4a (AAC) audio: such a file plays with
        # sound in any player. Other combinations (e.g. Opus audio)
        # produce a "silent" mp4 in stock Windows players — for those
        # _worker enables audio transcoding to AAC.
        opts["format"] = (
            f"bestvideo{h}[ext=mp4]+bestaudio[ext=m4a]/"
            f"bestvideo{h}+bestaudio/best{h}/best"
        )
        opts["merge_output_format"] = "mp4"
    return opts


def display_title(info: dict, fmt: str) -> str:
    """File name as "Artist - Title" when the metadata allows it."""
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
    """A free file name: "Title.mp3", "Title (2).mp3", …"""
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


# --- hints for typical errors (shown to the user) -----------------------
_HINTS = (
    (("ffmpeg",),
     "ffmpeg was not found — without it neither mp3 nor video merging "
     "works. Install it following README.md (the section for your OS) "
     "and retry the download."),
    (("unsupported url",),
     "This link is not supported. Check that it points to a specific "
     "video or track rather than a profile, search results or the "
     "service's home page."),
    (("403", "forbidden", "nsig", "signature extraction",
      "player response", "precondition check failed"),
     "The service refused the download (HTTP 403). This is almost "
     "always the site changing something on its side, not your "
     "connection. Update the download library: the “Update yt-dlp” "
     "button in the 👤 profile window (or run update.bat / "
     "./update.sh), then retry. If it still fails, connect your "
     "browser cookies — see docs/COOKIES.md."),
    (("age-restricted", "age restricted", "age_limit", "private",
      "login", "sign in", "logged in", "nsfw", "authentication",
      "account", "cookies"),
     "The content is private or age-restricted — the service requires "
     "signing in. If this is your account, connect your browser "
     "cookies: see docs/COOKIES.md (the cookies folder opens via the "
     "👤 button → “Cookies folder”)."),
    (("429", "too many requests", "rate limit"),
     "The service has temporarily rate-limited requests. Wait a few "
     "minutes and try again."),
    (("geo", "not available in your country", "region"),
     "The content is not available in your region."),
    (("unable to download", "tunnel", "proxy", "getaddrinfo",
      "timed out", "connection", "network", "ssl"),
     "Looks like a network problem. Check your internet connection "
     "and try again."),
    (("video unavailable", "removed", "deleted", "not exist",
      "no longer available"),
     "The video/track was removed or is no longer available."),
)

# errors worth retrying with different service options (see
# ServicePlugin.retry_variants): the site refused this particular
# request rather than the content being unavailable
_RETRY_MARKERS = (
    "403", "forbidden", "fragment", "unable to download video data",
    "nsig", "signature", "player response", "precondition check failed",
    "throttl", "timed out", "connection reset",
)


def is_retryable(exc: Exception) -> bool:
    low = str(exc).lower()
    return any(marker in low for marker in _RETRY_MARKERS)


_DEFAULT_HINT = (
    "Services change their sites all the time, and the downloader "
    "keeps up through updates. First update yt-dlp: run update.bat "
    "(Windows) or ./update.sh (macOS/Linux) and retry. If that does "
    "not help — send the report file to the developer (the "
    "“Copy report” button)."
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
        ytdlp_version = "not installed"
    message = short_error(exc)
    report = "\n".join([
        "MediaGrab — download error report",
        f"Time:    {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Link:    {url}",
        f"Service: {plugin.name if plugin else 'Auto'}",
        f"Format:  {fmt}, quality: {quality}",
        f"OS:      {platform.platform()}",
        f"Python:  {sys.version.split()[0]}",
        f"yt-dlp:  {ytdlp_version}",
        "",
        "Error:",
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
                import yt_dlp  # noqa: F401 — checked here, used below
            except ImportError as exc:
                self.events.put((task_id, "error", {
                    "message": "yt-dlp is not installed",
                    "hint": "Install the dependencies: run install.bat "
                            "(Windows) or ./install.sh (macOS/Linux).",
                    "report": str(exc),
                    "report_path": "",
                }))
                return
            self.events.put((task_id, "start", None))

            # A service may refuse one particular request (HTTP 403 is
            # the usual one on YouTube) while the very same download
            # succeeds with different service options, so every variant
            # the plugin offers is tried before giving up.
            variants = list(plugin.retry_variants()) if plugin else [{}]
            last_exc = None
            for attempt, extra in enumerate(variants, start=1):
                if attempt > 1:
                    self.events.put(
                        (task_id, "retry", (attempt, len(variants))))
                try:
                    path = self._download_once(
                        task_id, url, plugin, fmt, quality, outdir, extra)
                    self.events.put((task_id, "done", path))
                    return
                except Exception as exc:  # noqa: BLE001 — reported in the UI
                    last_exc = exc
                    if attempt >= len(variants) or not is_retryable(exc):
                        break
            self.events.put((task_id, "error", make_error_report(
                last_exc, task_id=task_id, url=url, plugin=plugin,
                fmt=fmt, quality=quality)))

    def _download_once(self, task_id, url, plugin, fmt, quality, outdir,
                       extra_options):
        import yt_dlp
        from yt_dlp.utils import sanitize_filename

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

        os.makedirs(outdir, exist_ok=True)
        real_url = plugin.prepare(url) if plugin else url
        opts = build_options(fmt, quality, outdir)
        if plugin:
            opts = plugin.tweak_options(opts, fmt)
        opts.update(extra_options)
        cookie_file = find_cookie_file(plugin)
        if cookie_file:
            opts["cookiefile"] = str(cookie_file)

        # 1) metadata — used for the file name and format choice
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
                raise RuntimeError("nothing was found for this link")
            info = entries[0]
        if not info:
            raise RuntimeError("could not fetch data for this link")

        # 2) file name: "Artist - Title", duplicates get " (2)"
        ext = "mp3" if fmt == "mp3" else "mp4"
        base = sanitize_filename(display_title(info, fmt))
        final_path = unique_path(outdir, base, ext)
        stem = os.path.splitext(final_path)[0]
        # % is special in the outtmpl template — escape it
        opts["outtmpl"] = stem.replace("%", "%%") + ".%(ext)s"

        # 3) if a non-AAC audio codec (e.g. Opus) is being merged
        # into mp4, transcode it: stock Windows players would
        # otherwise play the file without sound
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
            # safety net: look the file up by its name stem
            import glob
            matches = glob.glob(glob.escape(stem) + ".*")
            if matches:
                final_path = matches[0]
        return final_path
