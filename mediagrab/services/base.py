"""Base class ("blueprint") for a service plugin."""

import re


class ServicePlugin:
    """Subclass this to add support for a new service.

    A minimal plugin only sets id, name and url_patterns — the actual
    downloading is done by yt-dlp, which supports hundreds of sites on
    its own. Override prepare() and tweak_options() when a service
    needs special handling (see spotify.py for an example).
    """

    #: short identifier (latin letters, no spaces)
    id = "base"
    #: name shown in the application sidebar
    name = "Base"
    #: regular expressions that match this service's links
    url_patterns: list = []
    #: formats the service supports
    supported_formats = ("mp3", "mp4")
    #: position in the list and in auto-detection (lower — earlier)
    order = 100
    #: hint appended to download error messages
    error_hint = ""

    def matches(self, url: str) -> bool:
        return any(re.search(p, url, re.IGNORECASE)
                   for p in self.url_patterns)

    def prepare(self, url: str) -> str:
        """Return what should actually be downloaded.

        Usually the same URL. May also return a yt-dlp search query
        like "ytsearch1:title" — that is how the Spotify plugin works.
        Runs in a background thread, so network requests are fine here.
        """
        return url

    def tweak_options(self, options: dict, fmt: str) -> dict:
        """Adjust yt-dlp options for this service's quirks."""
        return options
