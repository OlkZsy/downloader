from .base import ServicePlugin


class XTwitter(ServicePlugin):
    id = "x"
    name = "X (Twitter)"
    url_patterns = [r"(www\.|mobile\.)?(twitter\.com|x\.com)/"]
    supported_formats = ("mp3", "mp4")
    order = 30
    error_hint = (
        "Особенности X (Twitter): без входа скачиваются только видео из "
        "публичных постов. Для постов 18+ и закрытых аккаунтов подключите "
        "cookies своего браузера — файл x.txt в папке cookies (кнопка 👤 → "
        "«Папка cookies», инструкция в docs/COOKIES.md). Ссылка должна "
        "вести на сам пост с видео (…/status/…), а не на профиль.")


PLUGIN = XTwitter()
