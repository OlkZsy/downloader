"""Базовый класс («blueprint») плагина сервиса."""

import re


class ServicePlugin:
    """Наследуйте этот класс, чтобы добавить поддержку нового сервиса.

    Минимальный плагин задаёт только id, name и url_patterns — загрузку
    выполняет yt-dlp, который сам умеет сотни сайтов. Методы prepare()
    и tweak_options() переопределяются, когда сервису нужна особая
    обработка (пример — spotify.py).
    """

    #: короткий идентификатор (латиницей, без пробелов)
    id = "base"
    #: имя, отображаемое в боковой панели приложения
    name = "Base"
    #: регулярные выражения, по которым ссылка относится к сервису
    url_patterns: list = []
    #: какие форматы сервис поддерживает
    supported_formats = ("mp3", "mp4")
    #: порядок в списке и при автоопределении (меньше — раньше)
    order = 100

    def matches(self, url: str) -> bool:
        return any(re.search(p, url, re.IGNORECASE)
                   for p in self.url_patterns)

    def prepare(self, url: str) -> str:
        """Вернуть то, что реально скачивать.

        Обычно это тот же URL. Может вернуть и поисковый запрос yt-dlp
        вида "ytsearch1:название" — так работает плагин Spotify.
        Вызывается в фоновом потоке, поэтому здесь можно делать
        сетевые запросы.
        """
        return url

    def tweak_options(self, options: dict, fmt: str) -> dict:
        """Подправить опции yt-dlp под особенности сервиса."""
        return options
