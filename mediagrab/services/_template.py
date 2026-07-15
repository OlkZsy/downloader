"""TEMPLATE for a new service plugin (files starting with "_" are not loaded).

How to add a new service:

1. Copy this file under a new name, e.g. soundcloud.py
   (no leading "_"!).
2. Fill in id, name and url_patterns.
3. If the service needs special logic — override prepare()
   or tweak_options() (see base.py and spotify.py).
4. Restart the application — the service shows up in the sidebar
   automatically, no registration needed anywhere.

Details: docs/ADDING_SERVICES.md
"""

from .base import ServicePlugin


class MyService(ServicePlugin):
    id = "myservice"                      # latin letters, no spaces
    name = "Мой сервис"                   # name shown in the sidebar
    url_patterns = [r"myservice\.com/"]   # regexes for the service's links
    supported_formats = ("mp3", "mp4")    # what the service supports
    order = 50                            # position in the list

    # def prepare(self, url: str) -> str:
    #     """E.g. turn a short link into a full one."""
    #     return url

    # def tweak_options(self, options: dict, fmt: str) -> dict:
    #     """E.g. pass special headers:
    #     options["http_headers"] = {"Referer": "https://myservice.com"}
    #     """
    #     return options


PLUGIN = MyService()
