from .base import ServicePlugin


class Facebook(ServicePlugin):
    id = "facebook"
    name = "Facebook"
    url_patterns = [r"(www\.|m\.|web\.)?facebook\.com/", r"fb\.watch/"]
    supported_formats = ("mp3", "mp4")
    order = 40
    error_hint = (
        "Особенности Facebook: скачиваются только публичные видео. "
        "Видео из закрытых групп и с ограничениями приватности "
        "требуют входа и не поддерживаются.")


PLUGIN = Facebook()
