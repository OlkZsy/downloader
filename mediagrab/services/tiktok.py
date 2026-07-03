from .base import ServicePlugin


class TikTok(ServicePlugin):
    id = "tiktok"
    name = "TikTok"
    url_patterns = [r"(www\.|vm\.|vt\.)?tiktok\.com/"]
    supported_formats = ("mp3", "mp4")
    order = 20


PLUGIN = TikTok()
