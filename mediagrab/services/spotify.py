"""Spotify plugin.

Spotify content is DRM-protected and cannot be downloaded directly.
This plugin works differently: it fetches the track title via Spotify's
public oEmbed API and then finds and downloads that track on YouTube
(the yt-dlp search query "ytsearch1:..."). That is why only mp3 is
available.
"""

import json
import urllib.parse
import urllib.request

from .base import ServicePlugin

OEMBED_URL = "https://open.spotify.com/oembed?url={}"


class Spotify(ServicePlugin):
    id = "spotify"
    name = "Spotify"
    url_patterns = [r"open\.spotify\.com/(intl-[a-z\-]+/)?track/"]
    supported_formats = ("mp3",)
    order = 15
    error_hint = (
        "Особенности Spotify: ссылка должна вести на один трек "
        "(open.spotify.com/track/…). Плейлисты и альбомы пока не "
        "поддерживаются.")

    def prepare(self, url: str) -> str:
        request = urllib.request.Request(
            OEMBED_URL.format(urllib.parse.quote(url, safe="")),
            headers={"User-Agent": "Mozilla/5.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                data = json.load(response)
        except Exception as exc:
            raise RuntimeError(
                f"Spotify: не удалось получить данные трека ({exc})"
            ) from exc
        title = (data.get("title") or "").strip()
        if not title:
            raise RuntimeError(
                "Spotify: не удалось определить название трека. "
                "Проверьте, что ссылка ведёт на трек (…/track/…).")
        return f"ytsearch1:{title}"


PLUGIN = Spotify()
