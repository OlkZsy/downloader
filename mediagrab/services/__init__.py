"""Service plugin registry.

Every file in this package (except those starting with "_" and base.py)
is a plugin for one service. A plugin file must define a PLUGIN
variable — an instance of a ServicePlugin subclass. Plugins are picked
up automatically: to add a new service, just drop a new file in here
(see _template.py and docs/ADDING_SERVICES.md).
"""

import importlib
import pkgutil

from .base import ServicePlugin  # noqa: F401 — re-exported for plugins

_plugins: list | None = None


def all_plugins() -> list:
    """All discovered plugins, sorted by priority."""
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
    """Find the plugin a link belongs to (or None)."""
    for plugin in all_plugins():
        if plugin.matches(url):
            return plugin
    return None


def by_id(plugin_id: str):
    for plugin in all_plugins():
        if plugin.id == plugin_id:
            return plugin
    return None
