from .base import ServicePlugin


class XTwitter(ServicePlugin):
    id = "x"
    name = "X (Twitter)"
    url_patterns = [r"(www\.|mobile\.)?(twitter\.com|x\.com)/"]
    supported_formats = ("mp3", "mp4")
    order = 30


PLUGIN = XTwitter()
