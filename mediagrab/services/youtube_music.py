from .base import ServicePlugin


class YouTubeMusic(ServicePlugin):
    id = "youtube_music"
    name = "YouTube Music"
    url_patterns = [r"music\.youtube\.com/"]
    supported_formats = ("mp3", "mp4")
    order = 11


PLUGIN = YouTubeMusic()
