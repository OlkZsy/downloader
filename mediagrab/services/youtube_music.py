from .base import ServicePlugin
from .youtube import YouTube


class YouTubeMusic(YouTube):
    """Same site as YouTube, so the YouTube plugin's behaviour applies —
    including its retry variants for HTTP 403."""

    id = "youtube_music"
    name = "YouTube Music"
    url_patterns = [r"music\.youtube\.com/"]
    order = 11

    def matches(self, url: str) -> bool:
        # YouTube excludes music.youtube.com links; this plugin claims them
        return ServicePlugin.matches(self, url)


PLUGIN = YouTubeMusic()
