"""ШАБЛОН нового плагина сервиса (файл с "_" в начале не загружается).

Как добавить новый сервис:

1. Скопируйте этот файл под новым именем, например soundcloud.py
   (без "_" в начале!).
2. Заполните id, name и url_patterns.
3. Если сервису нужна особая логика — переопределите prepare()
   или tweak_options() (см. base.py и spotify.py).
4. Перезапустите приложение — сервис появится в боковой панели
   автоматически, регистрировать его нигде не нужно.

Подробности: docs/ADDING_SERVICES.md
"""

from .base import ServicePlugin


class MyService(ServicePlugin):
    id = "myservice"                      # латиницей, без пробелов
    name = "Мой сервис"                   # имя в боковой панели
    url_patterns = [r"myservice\.com/"]   # регулярки для ссылок сервиса
    supported_formats = ("mp3", "mp4")    # что умеет сервис
    order = 50                            # позиция в списке

    # def prepare(self, url: str) -> str:
    #     """Например, превратить короткую ссылку в полную."""
    #     return url

    # def tweak_options(self, options: dict, fmt: str) -> dict:
    #     """Например, передать особые заголовки:
    #     options["http_headers"] = {"Referer": "https://myservice.com"}
    #     """
    #     return options


PLUGIN = MyService()
