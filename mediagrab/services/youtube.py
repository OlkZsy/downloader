from .base import ServicePlugin

# YouTube serves its pages to several "player clients" (the TV app, the
# mobile site, Safari…) and hands out download links that are only valid
# for the client that asked for them. When it refuses one of them the
# download fails with "HTTP Error 403: Forbidden" while another client
# works fine — so each retry asks as a different client.
PLAYER_CLIENTS = (
    None,                      # whatever yt-dlp picks by default
    ("tv",),
    ("web_safari", "web"),
    ("android_vr",),
    ("ios",),
)


class YouTube(ServicePlugin):
    id = "youtube"
    name = "YouTube"
    url_patterns = [r"(www\.|m\.)?youtube\.com/", r"youtu\.be/"]
    supported_formats = ("mp3", "mp4")
    order = 10
    error_hint = (
        "YouTube specifics: “HTTP Error 403: Forbidden” means the site "
        "refused this request — it does not mean your connection is "
        "broken. Update the download library (the “Update yt-dlp” "
        "button in the 👤 profile window); if that does not help, "
        "connect your browser cookies — see docs/COOKIES.md.")

    def matches(self, url: str) -> bool:
        # music.youtube.com is handled by a separate plugin
        if "music.youtube.com" in url.lower():
            return False
        return super().matches(url)

    def retry_variants(self) -> list:
        variants = []
        for clients in PLAYER_CLIENTS:
            if clients is None:
                variants.append({})
            else:
                variants.append({"extractor_args": {
                    "youtube": {"player_client": list(clients)}}})
        return variants


PLUGIN = YouTube()
