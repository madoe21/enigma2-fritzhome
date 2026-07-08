# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os
import time

from Components.config import (
    ConfigInteger,
    ConfigSubsection,
    ConfigText,
    config,
)


class ConfigPassword(ConfigText):
    """ConfigText variant that displays asterisks instead of clear text."""

    def getText(self):
        return u"*" * len(self.value) if self.value else u""

    def getMulti(self, selected):
        mtext = u"*" * len(self.value) if self.value else u""
        if selected:
            return ("mtext", mtext + u"_")
        return ("mtext", mtext)
from Plugins.Plugin import PluginDescriptor
from Tools.Directories import SCOPE_PLUGINS, resolveFilename

from . import _
from .core.api import FritzHomeApiClient
from .screens import FritzHomeMainScreen, FritzHomeSettingsScreen
from .core.store import FritzHomeStore

SETTINGS_FILE = "/etc/enigma2/settings"
USE_ASPECT_ICON_VARIANTS = True

if not hasattr(config.plugins, "fritzhome"):
    config.plugins.fritzhome = ConfigSubsection()

config.plugins.fritzhome.host = ConfigText(default="fritz.box", fixed_size=False)
config.plugins.fritzhome.port = ConfigInteger(default=80, limits=(1, 65535))
config.plugins.fritzhome.username = ConfigText(default="", fixed_size=False)
config.plugins.fritzhome.password = ConfigPassword(default="", fixed_size=False)


class AppContext(object):
    """Central application object – holds config, store and API client.

    Kept framework-agnostic in its data layer so it can be ported to Kodi
    without changes.  Screen-level glue lives in screens.py.
    """

    def __init__(self):
        self._load_settings_from_file()
        self.store = FritzHomeStore()
        self.api = self._make_api()

    # ------------------------------------------------------------------
    # Settings helpers
    # ------------------------------------------------------------------

    def _load_settings_from_file(self):
        """Read persisted Enigma2 settings so values are available on first
        launch before the config system has fully initialised."""
        if not os.path.exists(SETTINGS_FILE):
            return
        values = {}
        try:
            with open(SETTINGS_FILE, "r") as fh:
                for raw in fh:
                    line = raw.strip()
                    if not line or not line.startswith("config.plugins.fritzhome."):
                        continue
                    if "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    values[key] = value.strip()
        except Exception:
            return

        host = values.get("config.plugins.fritzhome.host")
        port = values.get("config.plugins.fritzhome.port")
        username = values.get("config.plugins.fritzhome.username")
        password = values.get("config.plugins.fritzhome.password")

        if host:
            config.plugins.fritzhome.host.value = host
        if port:
            try:
                config.plugins.fritzhome.port.value = int(port)
            except Exception:
                pass
        if username is not None:
            config.plugins.fritzhome.username.value = username
        if password is not None:
            config.plugins.fritzhome.password.value = password

    def _make_api(self):
        return FritzHomeApiClient(
            host=self.get_host(),
            port=self.get_port(),
            username=self.get_username(),
            password=self.get_password(),
        )

    def _rebuild_api(self):
        self.api = self._make_api()

    def get_host(self):
        return (config.plugins.fritzhome.host.value or "fritz.box").strip()

    def get_port(self):
        try:
            p = int(config.plugins.fritzhome.port.value)
            return p if 1 <= p <= 65535 else 80
        except Exception:
            return 80

    def get_username(self):
        return (config.plugins.fritzhome.username.value or "").strip()

    def get_password(self):
        return (config.plugins.fritzhome.password.value or "").strip()

    def settings_complete(self):
        return bool(self.get_host())

    def cache_host_key(self):
        return "%s:%d" % (self.get_host(), self.get_port())

    # ------------------------------------------------------------------
    # Data operations
    # ------------------------------------------------------------------

    def refresh_devices(self):
        """Fetch fresh device list; fall back to cache on error.

        Returns a dict:
          {
            "devices":    list of device dicts,
            "groups":     list of group dicts,
            "updated":    unix timestamp or None,
            "error":      error string or None,
            "from_cache": bool,
          }
        """
        self._rebuild_api()
        devices, groups, error = self.api.get_devices()
        if devices is not None:
            self.store.save(devices, groups, self.cache_host_key())
            return {
                "devices": devices,
                "groups": groups,
                "updated": time.time(),
                "error": None,
                "from_cache": False,
            }

        # Fall back to cache
        cache = self.store.load()
        cached_devices = cache.get("devices") or []
        if cached_devices:
            return {
                "devices": cached_devices,
                "groups": cache.get("groups") or [],
                "updated": cache.get("updated"),
                "error": error,
                "from_cache": True,
            }

        return {
            "devices": [],
            "groups": [],
            "updated": None,
            "error": error,
            "from_cache": False,
        }

    def ping(self):
        self._rebuild_api()
        return self.api.ping()


# ---------------------------------------------------------------------------
# Enigma2 plugin entry points
# ---------------------------------------------------------------------------

_APP = None


def get_app():
    global _APP
    if _APP is None:
        _APP = AppContext()
    return _APP


def main(session, **kwargs):
    app = get_app()
    if app.settings_complete():
        session.open(FritzHomeMainScreen, app)
    else:
        session.open(FritzHomeSettingsScreen, app, True)


def _icon_file_for_aspect_ratio():
    try:
        from enigma import getDesktop

        sz = getDesktop(0).size()
        width = int(sz.width())
        height = int(sz.height())
        if height > 0:
            ratio = float(width) / float(height)
            if ratio < 1.5:
                return "plugin_4x3.png"
            if ratio < 1.7:
                return "plugin_16x10.png"
            return "plugin_16x9.png"
    except Exception:
        pass
    return "plugin_16x9.png"


def _plugin_icon():
    if not USE_ASPECT_ICON_VARIANTS:
        return resolveFilename(SCOPE_PLUGINS, "Extensions/fritz_home/res/plugin.png")
    icon_file = _icon_file_for_aspect_ratio()
    path = resolveFilename(SCOPE_PLUGINS, "Extensions/fritz_home/res/%s" % icon_file)
    if os.path.exists(path):
        return path
    return resolveFilename(SCOPE_PLUGINS, "Extensions/fritz_home/res/plugin.png")


def Plugins(**kwargs):
    return [
        PluginDescriptor(
            name="FritzHome",
            description=_("Fritz!Box Smart Home Monitor & Control"),
            where=PluginDescriptor.WHERE_PLUGINMENU,
            icon=_plugin_icon(),
            fnc=main,
        )
    ]
