"""Реестр плагинов сервисов.

Каждый файл в этой папке (кроме начинающихся с "_" и base.py) — плагин
одного сервиса. Файл должен определять переменную PLUGIN — экземпляр
подкласса ServicePlugin. Плагины подхватываются автоматически: чтобы
добавить новый сервис, достаточно положить сюда новый файл
(см. _template.py и docs/ADDING_SERVICES.md).
"""

import importlib
import pkgutil

from .base import ServicePlugin  # noqa: F401 — реэкспорт для плагинов

_plugins: list | None = None


def all_plugins() -> list:
    """Список всех обнаруженных плагинов, отсортированный по приоритету."""
    global _plugins
    if _plugins is None:
        found = []
        for mod_info in pkgutil.iter_modules(__path__):
            name = mod_info.name
            if name.startswith("_") or name == "base":
                continue
            module = importlib.import_module(f"{__name__}.{name}")
            plugin = getattr(module, "PLUGIN", None)
            if isinstance(plugin, ServicePlugin):
                found.append(plugin)
        found.sort(key=lambda p: (p.order, p.name.lower()))
        _plugins = found
    return _plugins


def detect(url: str):
    """Найти плагин, которому принадлежит ссылка (или None)."""
    for plugin in all_plugins():
        if plugin.matches(url):
            return plugin
    return None


def by_id(plugin_id: str):
    for plugin in all_plugins():
        if plugin.id == plugin_id:
            return plugin
    return None
