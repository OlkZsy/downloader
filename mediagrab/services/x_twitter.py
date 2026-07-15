from .base import ServicePlugin


class XTwitter(ServicePlugin):
    id = "x"
    name = "X (Twitter)"
    url_patterns = [r"(www\.|mobile\.)?(twitter\.com|x\.com)/"]
    supported_formats = ("mp3", "mp4")
    order = 30
    error_hint = (
        "X (Twitter) specifics: without signing in only videos from "
        "public posts can be downloaded. For 18+ posts and private "
        "accounts connect your browser cookies — an x.txt file in the "
        "cookies folder (the 👤 button → “Cookies folder”, guide in "
        "docs/COOKIES.md). The link must point to the post with the "
        "video itself (…/status/…), not to a profile.")


PLUGIN = XTwitter()
