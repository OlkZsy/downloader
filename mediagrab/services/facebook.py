from .base import ServicePlugin


class Facebook(ServicePlugin):
    id = "facebook"
    name = "Facebook"
    url_patterns = [r"(www\.|m\.|web\.)?facebook\.com/", r"fb\.watch/"]
    supported_formats = ("mp3", "mp4")
    order = 40
    error_hint = (
        "Facebook specifics: public videos download right away. Videos "
        "from closed groups or with privacy restrictions require "
        "signing in — connect your browser cookies (a facebook.txt "
        "file, see docs/COOKIES.md).")


PLUGIN = Facebook()
