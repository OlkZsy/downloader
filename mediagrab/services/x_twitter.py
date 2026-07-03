from .base import ServicePlugin


class XTwitter(ServicePlugin):
    id = "x"
    name = "X (Twitter)"
    url_patterns = [r"(www\.|mobile\.)?(twitter\.com|x\.com)/"]
    supported_formats = ("mp3", "mp4")
    order = 30
    error_hint = (
        "Особенности X (Twitter): скачиваются только видео из публичных "
        "постов. Посты с пометкой 18+ и из закрытых аккаунтов требуют "
        "входа и не поддерживаются. Ссылка должна вести на сам пост с "
        "видео (…/status/…), а не на профиль.")


PLUGIN = XTwitter()
