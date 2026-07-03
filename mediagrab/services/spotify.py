"""Плагин Spotify.

Контент Spotify защищён DRM, и скачать его напрямую невозможно.
Плагин работает иначе: через открытый oEmbed-API Spotify получает
название трека, а затем ищет и скачивает этот трек на YouTube
(поисковый запрос yt-dlp "ytsearch1:..."). Поэтому доступен только mp3.
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
