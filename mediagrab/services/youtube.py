from .base import ServicePlugin


class YouTube(ServicePlugin):
    id = "youtube"
    name = "YouTube"
    url_patterns = [r"(www\.|m\.)?youtube\.com/", r"youtu\.be/"]
    supported_formats = ("mp3", "mp4")
    order = 10

    def matches(self, url: str) -> bool:
        # music.youtube.com обрабатывает отдельный плагин
        if "music.youtube.com" in url.lower():
            return False
        return super().matches(url)


PLUGIN = YouTube()
