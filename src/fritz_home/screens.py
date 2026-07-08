# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os
import time

from Components.ActionMap import ActionMap
from Components.ConfigList import ConfigListScreen
from Components.Label import Label
from Components.MenuList import MenuList
from Components.MultiContent import MultiContentEntryText
from Components.Pixmap import Pixmap
from Components.ScrollLabel import ScrollLabel
from Components.Sources.StaticText import StaticText
from Components.config import config, configfile, getConfigListEntry
from Screens.ChoiceBox import ChoiceBox
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Tools.Directories import SCOPE_PLUGINS, resolveFilename

try:
    from enigma import (
        RT_HALIGN_LEFT,
        RT_HALIGN_RIGHT,
        RT_HALIGN_CENTER,
        RT_VALIGN_CENTER,
        eListboxPythonMultiContent,
        gFont,
    )
except Exception:
    RT_HALIGN_LEFT = 0
    RT_HALIGN_RIGHT = 0
    RT_HALIGN_CENTER = 0
    RT_VALIGN_CENTER = 0
    eListboxPythonMultiContent = None
    gFont = None

try:
    from Components.Input import Input
    from Screens.InputBox import InputBox
except Exception:
    Input = None
    InputBox = None

from . import _

SUPPORT_LINE = "Buy me a coffee: https://buymeacoffee.com/madoe21"

# ---------------------------------------------------------------------------
# Column layout constants (pixels, relative to list widget left edge)
# ---------------------------------------------------------------------------
_COL_NAME_X = 0
_COL_NAME_W = 280
_COL_STATUS_X = 284
_COL_STATUS_W = 160
_COL_TEMP_X = 448
_COL_TEMP_W = 250
_COL_HUM_X = 702
_COL_HUM_W = 150
_COL_EXTRA_X = 856
_COL_EXTRA_W = 284
_ROW_H = 38

# Colours
_COL_ON = 0x00CC44      # green - switch on / present
_COL_OFF = 0x888888     # grey  - switch off / absent
_COL_WARM = 0xFF8800    # orange - thermostat / heating
_COL_COOL = 0x4499FF    # blue  - temperature / sensor
_COL_TEXT = 0xFFFFFF    # default text
_COL_RED = 0xFF4444     # red - alert / low battery

# Filter mode constants
_FILTER_ALL = 0
_FILTER_SWITCH = 1
_FILTER_SENSOR = 2
_FILTER_THERMOSTAT = 3
_FILTER_LABELS = ["Alle", "Steckdosen", "Sensoren", "Thermostate"]


def _fmt_temp(celsius):
    if celsius is None:
        return "-"
    return "%.1f \u00b0C" % celsius


def _fmt_humidity(pct):
    if pct is None:
        return "-"
    return "%d %% rF" % pct


def _fmt_power(watt):
    if watt is None:
        return ""
    if watt >= 1000:
        return "%.1f kW" % (watt / 1000.0)
    return "%.1f W" % watt


def _status_text(device):
    """Return human-readable status text for the device."""
    if not device.get("present"):
        return _("nicht verbunden")
    if device.get("has_switch"):
        state = device.get("switch_state")
        if state is True:
            return _("ein")
        if state is False:
            return _("aus")
        return _("unbekannt")
    if device.get("has_thermostat"):
        if device.get("boost_active"):
            return _("Boost")
        if device.get("window_open"):
            return _("Window open")
        return _("verbunden")
    return _("verbunden")


def _status_color(device):
    if not device.get("present"):
        return _COL_OFF
    if device.get("has_switch"):
        return _COL_ON if device.get("switch_state") else _COL_OFF
    if device.get("has_thermostat"):
        if device.get("boost_active"):
            return _COL_WARM
        if device.get("window_open"):
            return _COL_COOL
        return _COL_ON
    if device.get("has_temperature") or device.get("has_humidity"):
        return _COL_ON
    return _COL_TEXT


def _temp_column(device):
    """Build temperature column text: IST / SOLL for thermostats, IST for sensors."""
    if not device.get("present"):
        return ""
    parts = []
    if device.get("has_thermostat"):
        ist = device.get("thermostat_current")
        soll = device.get("thermostat_target")
        parts.append("IST %s" % _fmt_temp(ist))
        if soll is not None:
            parts.append(u"SOLL %s" % _fmt_temp(soll))
        else:
            parts.append("SOLL: aus")
        return u"  \u2502  ".join(parts)
    if device.get("has_temperature") and device.get("temperature_celsius") is not None:
        return _fmt_temp(device["temperature_celsius"])
    return ""


def _hum_column(device):
    if not device.get("present"):
        return ""
    if device.get("has_humidity") and device.get("humidity_pct") is not None:
        return _fmt_humidity(device["humidity_pct"])
    return ""


def _extra_column(device):
    """Extra info: power, battery, etc."""
    if not device.get("present"):
        return ""
    parts = []
    if device.get("has_powermeter") and device.get("power_w") is not None:
        parts.append(_fmt_power(device["power_w"]))
    if device.get("battery_pct") is not None:
        parts.append("Bat %d%%" % device["battery_pct"])
    return "  ".join(parts)


def _extra_color(device):
    if device.get("battery_low"):
        return _COL_RED
    return _COL_TEXT


# ===========================================================================
# Main screen
# ===========================================================================

class FritzHomeMainScreen(Screen):
    CACHE_MAX_AGE = 300

    skin = """
        <screen name="FritzHomeMainScreen" position="center,90" size="1180,640" title="FritzHome">
            <widget source="title"       render="Label" position="20,10"  size="1140,36" font="Regular;30" />
            <widget name="updated"       position="20,52"  size="560,28" font="Regular;22" />
            <widget name="filter_mode"   position="600,52" size="560,28" font="Regular;22" halign="right" />
            <widget name="header_name"   position="20,84"  size="280,28" font="Regular;20" />
            <widget name="header_status" position="304,84" size="160,28" font="Regular;20" />
            <widget name="header_temp"   position="468,84" size="250,28" font="Regular;20" />
            <widget name="header_hum"    position="722,84" size="150,28" font="Regular;20" />
            <widget name="header_extra"  position="876,84" size="284,28" font="Regular;20" />
            <widget name="list" position="20,116" size="1140,436" scrollbarMode="showOnDemand" />
            <widget source="support" render="Label" position="20,558" size="1140,24" font="Regular;18" foregroundColor="#666666" transparent="1" />
            <ePixmap pixmap="skin_default/buttons/red.png"    position="20,585"  size="220,30" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/green.png"  position="250,585" size="220,30" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/yellow.png" position="480,585" size="220,30" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/blue.png"   position="710,585" size="220,30" alphatest="on" />
            <widget source="key_red"    render="Label" position="20,585"  size="220,30" font="Regular;22" halign="center" valign="center" transparent="1" />
            <widget source="key_green"  render="Label" position="250,585" size="220,30" font="Regular;22" halign="center" valign="center" transparent="1" />
            <widget source="key_yellow" render="Label" position="480,585" size="220,30" font="Regular;22" halign="center" valign="center" transparent="1" />
            <widget source="key_blue"   render="Label" position="710,585" size="220,30" font="Regular;22" halign="center" valign="center" transparent="1" />
        </screen>
    """

    def __init__(self, session, app):
        Screen.__init__(self, session)
        self.app = app
        self._all_devices = []
        self._filter_mode = _FILTER_ALL
        self._use_multicontent = eListboxPythonMultiContent is not None

        self["title"] = StaticText(_("FritzHome - Smart Home"))
        self["updated"] = Label(_("Updated") + ": -")
        self["filter_mode"] = Label("")
        self["header_name"] = Label(_("Name"))
        self["header_status"] = Label(_("Status"))
        self["header_temp"] = Label(_("Temperature"))
        self["header_hum"] = Label(_("Humidity"))
        self["header_extra"] = Label(_("Extra"))

        if self._use_multicontent:
            self["list"] = MenuList([], content=eListboxPythonMultiContent)
        else:
            self["list"] = MenuList([])

        if gFont is not None:
            try:
                self["list"].l.setFont(0, gFont("Regular", 22))
                self["list"].l.setItemHeight(_ROW_H)
            except Exception:
                pass

        self["support"] = StaticText(SUPPORT_LINE)
        self["key_red"] = StaticText(_("Close"))
        self["key_green"] = StaticText(_("Refresh"))
        self["key_yellow"] = StaticText(_("Settings"))
        self["key_blue"] = StaticText(_("Information"))

        self["actions"] = ActionMap(
            ["ColorActions", "OkCancelActions", "DirectionActions", "MenuActions"],
            {
                "ok": self._open_detail,
                "cancel": self.close,
                "red": self.close,
                "green": self.action_refresh,
                "yellow": self.open_settings,
                "blue": self.open_info,
                "left": self._filter_prev,
                "right": self._filter_next,
                "menu": self.open_main_menu,
            },
            -1,
        )

        self._initial_load_done = False
        self.onShow.append(self._on_show)

    def _on_show(self):
        if not self._initial_load_done:
            self._initial_load_done = True
            self.load_initial_data()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def load_initial_data(self):
        if not self.app.settings_complete():
            self.session.open(FritzHomeSettingsScreen, self.app, True)
            return

        cache = self.app.store.load()
        cached = cache.get("devices") or []
        if cached:
            self._all_devices = cached
            self._render()
            self._set_updated(cache.get("updated"))
            try:
                age = max(0, int(time.time()) - int(cache.get("updated") or 0))
            except Exception:
                age = self.CACHE_MAX_AGE + 1
            if age <= self.CACHE_MAX_AGE:
                return

        self.action_refresh(show_cache_info=False)

    def action_refresh(self, show_cache_info=True):
        if not self.app.settings_complete():
            self.session.open(FritzHomeSettingsScreen, self.app, True)
            return

        self["updated"].setText(_("Loading..."))
        result = self.app.refresh_devices()
        self._all_devices = result.get("devices") or []
        self._render()
        self._set_updated(result.get("updated"))

        if show_cache_info and result.get("from_cache"):
            msg = _("Using cached data")
            if result.get("error"):
                msg = "%s\n(%s)" % (msg, result["error"])
            self.session.open(MessageBox, msg, MessageBox.TYPE_INFO, timeout=5)
        elif result.get("error") and not self._all_devices:
            self.session.open(
                MessageBox,
                _("Error") + ": " + str(result["error"]),
                MessageBox.TYPE_ERROR,
                timeout=6,
            )

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _visible_devices(self):
        devices = list(self._all_devices)
        if self._filter_mode == _FILTER_SWITCH:
            devices = [d for d in devices if d.get("has_switch") and not d.get("has_thermostat")]
        elif self._filter_mode == _FILTER_SENSOR:
            devices = [d for d in devices if (d.get("has_temperature") or d.get("has_humidity")) and not d.get("has_switch") and not d.get("has_thermostat")]
        elif self._filter_mode == _FILTER_THERMOSTAT:
            devices = [d for d in devices if d.get("has_thermostat")]
        return devices

    def _render(self):
        devices = self._visible_devices()
        devices.sort(key=lambda d: (
            0 if d.get("present") else 1,
            (d.get("group") or "").lower(),
            (d.get("name") or "").lower(),
        ))
        self._rendered_devices = devices
        self._update_filter_label()

        if not devices:
            empty_label = _("No devices found")
            if self._use_multicontent:
                self["list"].setList([self._empty_item(empty_label)])
            else:
                self["list"].setList([empty_label])
            return

        if self._use_multicontent:
            self["list"].setList([self._build_item(d) for d in devices])
        else:
            self["list"].setList([self._format_plain(d) for d in devices])

    def _empty_item(self, label):
        return [
            None,
            MultiContentEntryText(
                pos=(0, 0),
                size=(1140, _ROW_H),
                font=0,
                flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                text=label,
                color=_COL_OFF,
            ),
        ]

    def _build_item(self, device):
        name = (device.get("name") or "-")[:28]
        status = _status_text(device)[:16]
        s_color = _status_color(device)
        temp = _temp_column(device)[:28]
        hum = _hum_column(device)[:14]
        extra = _extra_column(device)[:28]
        e_color = _extra_color(device)
        text_color = _COL_TEXT if device.get("present") else _COL_OFF

        return [
            device,
            MultiContentEntryText(
                pos=(_COL_NAME_X, 0), size=(_COL_NAME_W, _ROW_H),
                font=0, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                text=name, color=text_color,
            ),
            MultiContentEntryText(
                pos=(_COL_STATUS_X, 0), size=(_COL_STATUS_W, _ROW_H),
                font=0, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                text=status, color=s_color,
            ),
            MultiContentEntryText(
                pos=(_COL_TEMP_X, 0), size=(_COL_TEMP_W, _ROW_H),
                font=0, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                text=temp, color=_COL_WARM if device.get("has_thermostat") else _COL_COOL,
            ),
            MultiContentEntryText(
                pos=(_COL_HUM_X, 0), size=(_COL_HUM_W, _ROW_H),
                font=0, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                text=hum, color=_COL_COOL,
            ),
            MultiContentEntryText(
                pos=(_COL_EXTRA_X, 0), size=(_COL_EXTRA_W, _ROW_H),
                font=0, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER,
                text=extra, color=e_color,
            ),
        ]

    def _format_plain(self, device):
        name = (device.get("name") or "-")[:24]
        status = _status_text(device)[:14]
        temp = _temp_column(device)[:22]
        hum = _hum_column(device)[:10]
        return u"%-24s  %-14s  %-22s  %s" % (name, status, temp, hum)

    def _set_updated(self, ts):
        if not ts:
            self["updated"].setText(_("Updated") + ": -")
            return
        try:
            formatted = time.strftime("%d.%m.%Y %H:%M:%S", time.localtime(int(ts)))
        except Exception:
            formatted = str(ts)
        total = len(self._all_devices)
        present = sum(1 for d in self._all_devices if d.get("present"))
        self["updated"].setText(
            _("Updated") + ": %s  |  %d/%d %s"
            % (formatted, present, total, _("verbunden"))
        )

    def _update_filter_label(self):
        label = _FILTER_LABELS[self._filter_mode]
        self["filter_mode"].setText(_("Filter") + ": " + label)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _get_selected_device(self):
        if not hasattr(self, "_rendered_devices") or not self._rendered_devices:
            return None
        try:
            index = int(self["list"].getSelectionIndex())
        except Exception:
            try:
                index = int(self["list"].getSelectedIndex())
            except Exception:
                index = 0
        if index < 0 or index >= len(self._rendered_devices):
            return None
        return self._rendered_devices[index]

    def _open_detail(self):
        device = self._get_selected_device()
        if not device:
            self.session.open(
                MessageBox, _("No devices found"), MessageBox.TYPE_INFO, timeout=3
            )
            return
        if device.get("has_thermostat"):
            self.session.openWithCallback(
                lambda *_args: self.action_refresh(show_cache_info=False),
                FritzHomeThermostatScreen,
                device,
                self.app,
            )
        elif device.get("has_switch"):
            self.session.openWithCallback(
                lambda *_args: self.action_refresh(show_cache_info=False),
                FritzHomeSwitchScreen,
                device,
                self.app,
            )
        else:
            self.session.openWithCallback(
                lambda *_args: self.action_refresh(show_cache_info=False),
                FritzHomeSensorScreen,
                device,
                self.app,
            )

    def _filter_next(self):
        self._filter_mode = (self._filter_mode + 1) % len(_FILTER_LABELS)
        self._render()

    def _filter_prev(self):
        self._filter_mode = (self._filter_mode - 1) % len(_FILTER_LABELS)
        self._render()

    def open_settings(self):
        self.session.openWithCallback(
            lambda *_args: self.load_initial_data(),
            FritzHomeSettingsScreen,
            self.app,
            False,
        )

    def open_info(self):
        self.session.open(FritzHomeInfoScreen)

    def open_main_menu(self):
        options = [
            (_("Close"), "close"),
            (_("Refresh"), "refresh"),
            (_("Filter") + ": " + _("All"), "filter_all"),
            (_("Filter") + ": " + _("Switches"), "filter_switch"),
            (_("Filter") + ": " + _("Sensors"), "filter_sensor"),
            (_("Filter") + ": " + _("Thermostats"), "filter_thermo"),
            (_("Settings"), "settings"),
            (_("Information"), "info"),
        ]
        self.session.openWithCallback(
            self._on_menu_choice,
            ChoiceBox,
            title=_("Main menu"),
            list=options,
        )

    def _on_menu_choice(self, choice=None):
        if not choice:
            return
        action = choice[1]
        if action == "close":
            self.close()
        elif action == "refresh":
            self.action_refresh()
        elif action == "filter_all":
            self._filter_mode = _FILTER_ALL
            self._render()
        elif action == "filter_switch":
            self._filter_mode = _FILTER_SWITCH
            self._render()
        elif action == "filter_sensor":
            self._filter_mode = _FILTER_SENSOR
            self._render()
        elif action == "filter_thermo":
            self._filter_mode = _FILTER_THERMOSTAT
            self._render()
        elif action == "settings":
            self.open_settings()
        elif action == "info":
            self.open_info()


# ===========================================================================
# Switch detail screen
# ===========================================================================

class FritzHomeSwitchScreen(Screen):
    """Detail screen for switchable sockets (FRITZ!DECT 200/210)."""

    skin = """
        <screen name="FritzHomeSwitchScreen" position="center,80" size="1000,580" title="FritzHome - Steckdose">
            <widget source="title"    render="Label" position="20,10"  size="960,44" font="Regular;34" />
            <widget source="subtitle" render="Label" position="20,60"  size="960,30" font="Regular;24" foregroundColor="#888888" />
            <widget name="body"       position="20,100" size="960,390" font="Regular;26" scrollbarMode="showOnDemand" />
            <widget source="support"  render="Label" position="20,500" size="960,24" font="Regular;18" foregroundColor="#666666" transparent="1" />
            <ePixmap pixmap="skin_default/buttons/red.png"    position="20,530"  size="220,34" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/green.png"  position="250,530" size="220,34" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/yellow.png" position="480,530" size="220,34" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/blue.png"   position="710,530" size="220,34" alphatest="on" />
            <widget source="key_red"    render="Label" position="20,530"  size="220,34" font="Regular;22" halign="center" valign="center" transparent="1" />
            <widget source="key_green"  render="Label" position="250,530" size="220,34" font="Regular;22" halign="center" valign="center" transparent="1" />
            <widget source="key_yellow" render="Label" position="480,530" size="220,34" font="Regular;22" halign="center" valign="center" transparent="1" />
            <widget source="key_blue"   render="Label" position="710,530" size="220,34" font="Regular;22" halign="center" valign="center" transparent="1" />
        </screen>
    """

    def __init__(self, session, device, app):
        Screen.__init__(self, session)
        self._device = dict(device) if device else {}
        self.app = app

        name = (self._device.get("name") or _("n/a")).strip()
        product = (self._device.get("product") or "").strip()

        self["title"] = StaticText(name)
        self["subtitle"] = StaticText(product)
        self["body"] = ScrollLabel(self._build_text())
        self["support"] = StaticText(SUPPORT_LINE)

        state = self._device.get("switch_state")
        present = self._device.get("present")
        if present:
            self["key_red"] = StaticText(_("Turn off") if state else _("Turn on"))
            self["key_green"] = StaticText(_("Toggle"))
        else:
            self["key_red"] = StaticText("")
            self["key_green"] = StaticText("")
        self["key_yellow"] = StaticText(_("Refresh"))
        self["key_blue"] = StaticText(_("Close"))

        self["scrollActions"] = ActionMap(
            ["DirectionActions"],
            {
                "up": self["body"].pageUp,
                "down": self["body"].pageDown,
                "left": self["body"].pageUp,
                "right": self["body"].pageDown,
            },
            -2,
        )

        self["actions"] = ActionMap(
            ["OkCancelActions", "ColorActions"],
            {
                "ok": self._action_toggle,
                "cancel": self.close,
                "red": self._action_switch,
                "green": self._action_toggle,
                "yellow": self._do_refresh,
                "blue": self.close,
            },
            -1,
        )

    def _build_text(self):
        d = self._device
        na = _("n/a")
        state = d.get("switch_state")
        if state is True:
            state_str = _("ein")
        elif state is False:
            state_str = _("aus")
        else:
            state_str = _("unbekannt")

        present_str = _("verbunden") if d.get("present") else _("nicht verbunden")
        locked_str = _("Yes") if d.get("switch_locked") else _("No")

        lines = [
            u"\u250c\u2500 %s \u2500" % _("Device info"),
            u"\u2502  %s:  %s" % (_("Name"), d.get("name") or na),
            u"\u2502  %s:  %s" % (_("Product"), d.get("product") or na),
            u"\u2502  %s:  %s" % ("AIN", d.get("ain_display") or d.get("ain") or na),
            u"\u2502  %s:  %s" % (_("Firmware"), d.get("fwversion") or na),
            u"\u2502  %s:  %s" % (_("Group"), d.get("group") or "-"),
            u"\u2502  %s:  %s" % (_("Connection"), present_str),
            u"\u2514\u2500\u2500\u2500",
            "",
            u"\u250c\u2500 %s \u2500" % _("Switch state"),
            u"\u2502  %s:  %s" % (_("Status"), state_str.upper()),
            u"\u2502  %s:  %s" % (_("Locked"), locked_str),
        ]

        if d.get("has_powermeter"):
            lines.append(u"\u2514\u2500\u2500\u2500")
            lines.append("")
            lines.append(u"\u250c\u2500 %s \u2500" % _("Energy metering"))
            if d.get("power_w") is not None:
                lines.append(u"\u2502  %s:  %s" % (_("Power"), _fmt_power(d["power_w"])))
            if d.get("energy_wh") is not None:
                lines.append(u"\u2502  %s:  %d Wh" % (_("Consumption"), d["energy_wh"]))

        if d.get("has_temperature") and d.get("temperature_celsius") is not None:
            lines.append(u"\u2514\u2500\u2500\u2500")
            lines.append("")
            lines.append(u"\u250c\u2500 %s \u2500" % _("Temperature"))
            lines.append(u"\u2502  %s:  %s" % (_("Current"), _fmt_temp(d["temperature_celsius"])))

        if d.get("has_humidity") and d.get("humidity_pct") is not None:
            lines.append(u"\u2502  %s:  %s" % (_("Humidity"), _fmt_humidity(d["humidity_pct"])))

        lines.append(u"\u2514\u2500\u2500\u2500")
        return "\n".join(lines)

    def _refresh_display(self):
        self["body"].setText(self._build_text())
        state = self._device.get("switch_state")
        present = self._device.get("present")
        if present:
            self["key_red"].setText(_("Turn off") if state else _("Turn on"))
        else:
            self["key_red"].setText("")

    def _action_toggle(self):
        if not self._device.get("present"):
            return
        ain = self._device.get("ain") or ""
        ok, error = self.app.api.toggle_switch(ain)
        if ok:
            state = self._device.get("switch_state")
            self._device["switch_state"] = not state if state is not None else True
            self._refresh_display()
        else:
            self.session.open(
                MessageBox, _("Error") + ": " + str(error),
                MessageBox.TYPE_ERROR, timeout=5,
            )

    def _action_switch(self):
        if not self._device.get("present"):
            return
        state = self._device.get("switch_state")
        target = not state if state is not None else True
        ain = self._device.get("ain") or ""
        ok, error = self.app.api.set_switch(ain, target)
        if ok:
            self._device["switch_state"] = target
            self._refresh_display()
        else:
            self.session.open(
                MessageBox, _("Error") + ": " + str(error),
                MessageBox.TYPE_ERROR, timeout=5,
            )

    def _do_refresh(self):
        self["body"].setText(_("Loading..."))
        result = self.app.refresh_devices()
        ain = self._device.get("ain")
        for dev in (result.get("devices") or []):
            if dev.get("ain") == ain:
                self._device = dev
                self._refresh_display()
                return
        if result.get("error"):
            self.session.open(
                MessageBox, _("Error") + ": " + str(result["error"]),
                MessageBox.TYPE_ERROR, timeout=5,
            )
        else:
            self["body"].setText(self._build_text())


# ===========================================================================
# Thermostat detail screen
# ===========================================================================

class FritzHomeThermostatScreen(Screen):
    """Detail screen for thermostats (FRITZ!DECT 300/301/302)."""

    THERMO_STEP = 0.5

    skin = """
        <screen name="FritzHomeThermostatScreen" position="center,80" size="1000,580" title="FritzHome - Thermostat">
            <widget source="title"    render="Label" position="20,10"  size="960,44" font="Regular;34" />
            <widget source="subtitle" render="Label" position="20,60"  size="960,30" font="Regular;24" foregroundColor="#888888" />
            <widget name="body"       position="20,100" size="960,390" font="Regular;26" scrollbarMode="showOnDemand" />
            <widget source="support"  render="Label" position="20,500" size="960,24" font="Regular;18" foregroundColor="#666666" transparent="1" />
            <ePixmap pixmap="skin_default/buttons/red.png"    position="20,530"  size="220,34" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/green.png"  position="250,530" size="220,34" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/yellow.png" position="480,530" size="220,34" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/blue.png"   position="710,530" size="220,34" alphatest="on" />
            <widget source="key_red"    render="Label" position="20,530"  size="220,34" font="Regular;22" halign="center" valign="center" transparent="1" />
            <widget source="key_green"  render="Label" position="250,530" size="220,34" font="Regular;22" halign="center" valign="center" transparent="1" />
            <widget source="key_yellow" render="Label" position="480,530" size="220,34" font="Regular;22" halign="center" valign="center" transparent="1" />
            <widget source="key_blue"   render="Label" position="710,530" size="220,34" font="Regular;22" halign="center" valign="center" transparent="1" />
        </screen>
    """

    def __init__(self, session, device, app):
        Screen.__init__(self, session)
        self._device = dict(device) if device else {}
        self.app = app

        name = (self._device.get("name") or _("n/a")).strip()
        product = (self._device.get("product") or "").strip()

        self["title"] = StaticText(name)
        self["subtitle"] = StaticText(product)
        self["body"] = ScrollLabel(self._build_text())
        self["support"] = StaticText(SUPPORT_LINE)

        present = self._device.get("present")
        if present:
            self["key_red"] = StaticText(u"\u2212 0.5\u00b0C")
            self["key_green"] = StaticText(u"\u002b 0.5\u00b0C")
        else:
            self["key_red"] = StaticText("")
            self["key_green"] = StaticText("")
        self["key_yellow"] = StaticText(_("Refresh"))
        self["key_blue"] = StaticText(_("Close"))

        self["scrollActions"] = ActionMap(
            ["DirectionActions"],
            {
                "up": self["body"].pageUp,
                "down": self["body"].pageDown,
                "left": self["body"].pageUp,
                "right": self["body"].pageDown,
            },
            -2,
        )

        self["actions"] = ActionMap(
            ["OkCancelActions", "ColorActions"],
            {
                "ok": self._action_ok,
                "cancel": self.close,
                "red": self._action_temp_down,
                "green": self._action_temp_up,
                "yellow": self._do_refresh,
                "blue": self.close,
            },
            -1,
        )

    def _build_text(self):
        d = self._device
        na = _("n/a")
        present_str = _("verbunden") if d.get("present") else _("nicht verbunden")

        lines = [
            u"\u250c\u2500 %s \u2500" % _("Device info"),
            u"\u2502  %s:  %s" % (_("Name"), d.get("name") or na),
            u"\u2502  %s:  %s" % (_("Product"), d.get("product") or na),
            u"\u2502  %s:  %s" % ("AIN", d.get("ain_display") or d.get("ain") or na),
            u"\u2502  %s:  %s" % (_("Firmware"), d.get("fwversion") or na),
            u"\u2502  %s:  %s" % (_("Group"), d.get("group") or "-"),
            u"\u2502  %s:  %s" % (_("Connection"), present_str),
            u"\u2514\u2500\u2500\u2500",
            "",
            u"\u250c\u2500 %s \u2500" % _("Temperature"),
            u"\u2502  %s (IST):   %s" % (_("Measured"), _fmt_temp(d.get("thermostat_current"))),
            u"\u2502  %s (SOLL):  %s" % (_("Target"), _fmt_temp(d.get("thermostat_target"))),
        ]

        if d.get("has_temperature") and d.get("temperature_celsius") is not None:
            lines.append(u"\u2502  %s:    %s" % (_("Room temperature"), _fmt_temp(d["temperature_celsius"])))

        if d.get("has_humidity") and d.get("humidity_pct") is not None:
            lines.append(u"\u2502  %s:  %s" % (_("Humidity"), _fmt_humidity(d["humidity_pct"])))

        lines.append(u"\u2514\u2500\u2500\u2500")
        lines.append("")

        # Battery & status
        lines.append(u"\u250c\u2500 %s \u2500" % _("Battery & status"))
        if d.get("battery_pct") is not None:
            bat_warn = "  (!)" if d.get("battery_low") else ""
            lines.append(u"\u2502  %s:  %d%%%s" % (_("Battery"), d["battery_pct"], bat_warn))
        else:
            lines.append(u"\u2502  %s:  %s" % (_("Battery"), na))

        if d.get("boost_active"):
            lines.append(u"\u2502  %s:  %s" % (_("Boost"), _("active")))
        if d.get("window_open"):
            lines.append(u"\u2502  %s:  %s" % (_("Window open"), _("Yes")))

        lines.append(u"\u2514\u2500\u2500\u2500")

        # Holiday / vacation schedules
        holidays = d.get("holidays") or []
        if holidays:
            lines.append("")
            lines.append(u"\u250c\u2500 %s \u2500" % _("Vacation schedules"))
            for h in holidays:
                end_ts = h.get("end", "")
                temp = h.get("temp")
                try:
                    end_str = time.strftime("%d.%m.%Y %H:%M", time.localtime(int(end_ts)))
                except Exception:
                    end_str = str(end_ts)
                temp_str = _fmt_temp(temp) if temp is not None else _("aus")
                lines.append(u"\u2502  %s: %s  (%s)" % (h.get("name", "?"), end_str, temp_str))
            lines.append(u"\u2514\u2500\u2500\u2500")

        return "\n".join(lines)

    def _refresh_display(self):
        self["body"].setText(self._build_text())

    def _action_ok(self):
        self["body"].pageDown()

    def _action_temp_up(self):
        if not self._device.get("present"):
            return
        self._adjust_thermostat(+self.THERMO_STEP)

    def _action_temp_down(self):
        if not self._device.get("present"):
            return
        self._adjust_thermostat(-self.THERMO_STEP)

    def _adjust_thermostat(self, delta):
        current_target = self._device.get("thermostat_target")
        if current_target is None:
            current_target = 20.0
        new_target = round(current_target + delta, 1)
        new_target = max(8.0, min(28.0, new_target))

        ain = self._device.get("ain") or ""
        ok, error = self.app.api.set_thermostat_temp(ain, new_target)
        if ok:
            self._device["thermostat_target"] = new_target
            self._refresh_display()
        else:
            self.session.open(
                MessageBox, _("Error") + ": " + str(error),
                MessageBox.TYPE_ERROR, timeout=5,
            )

    def _do_refresh(self):
        self["body"].setText(_("Loading..."))
        result = self.app.refresh_devices()
        ain = self._device.get("ain")
        for dev in (result.get("devices") or []):
            if dev.get("ain") == ain:
                self._device = dev
                self._refresh_display()
                return
        if result.get("error"):
            self.session.open(
                MessageBox, _("Error") + ": " + str(result["error"]),
                MessageBox.TYPE_ERROR, timeout=5,
            )
        else:
            self["body"].setText(self._build_text())


# ===========================================================================
# Sensor detail screen (temp/humidity only, no control)
# ===========================================================================

class FritzHomeSensorScreen(Screen):
    """Detail screen for pure sensors (no switch, no thermostat)."""

    skin = """
        <screen name="FritzHomeSensorScreen" position="center,80" size="1000,580" title="FritzHome - Sensor">
            <widget source="title"    render="Label" position="20,10"  size="960,44" font="Regular;34" />
            <widget source="subtitle" render="Label" position="20,60"  size="960,30" font="Regular;24" foregroundColor="#888888" />
            <widget name="body"       position="20,100" size="960,390" font="Regular;26" scrollbarMode="showOnDemand" />
            <widget source="support"  render="Label" position="20,500" size="960,24" font="Regular;18" foregroundColor="#666666" transparent="1" />
            <ePixmap pixmap="skin_default/buttons/red.png"    position="20,530"  size="220,34" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/green.png"  position="250,530" size="220,34" alphatest="on" />
            <widget source="key_red"    render="Label" position="20,530"  size="220,34" font="Regular;22" halign="center" valign="center" transparent="1" />
            <widget source="key_green"  render="Label" position="250,530" size="220,34" font="Regular;22" halign="center" valign="center" transparent="1" />
        </screen>
    """

    def __init__(self, session, device, app):
        Screen.__init__(self, session)
        self._device = dict(device) if device else {}
        self.app = app

        name = (self._device.get("name") or _("n/a")).strip()
        product = (self._device.get("product") or "").strip()

        self["title"] = StaticText(name)
        self["subtitle"] = StaticText(product)
        self["body"] = ScrollLabel(self._build_text())
        self["support"] = StaticText(SUPPORT_LINE)
        self["key_red"] = StaticText(_("Close"))
        self["key_green"] = StaticText(_("Refresh"))

        self["scrollActions"] = ActionMap(
            ["DirectionActions"],
            {
                "up": self["body"].pageUp,
                "down": self["body"].pageDown,
                "left": self["body"].pageUp,
                "right": self["body"].pageDown,
            },
            -2,
        )

        self["actions"] = ActionMap(
            ["OkCancelActions", "ColorActions"],
            {
                "ok": self.close,
                "cancel": self.close,
                "red": self.close,
                "green": self._do_refresh,
            },
            -1,
        )

    def _build_text(self):
        d = self._device
        na = _("n/a")
        present_str = _("verbunden") if d.get("present") else _("nicht verbunden")

        lines = [
            u"\u250c\u2500 %s \u2500" % _("Device info"),
            u"\u2502  %s:  %s" % (_("Name"), d.get("name") or na),
            u"\u2502  %s:  %s" % (_("Product"), d.get("product") or na),
            u"\u2502  %s:  %s" % ("AIN", d.get("ain_display") or d.get("ain") or na),
            u"\u2502  %s:  %s" % (_("Firmware"), d.get("fwversion") or na),
            u"\u2502  %s:  %s" % (_("Group"), d.get("group") or "-"),
            u"\u2502  %s:  %s" % (_("Connection"), present_str),
            u"\u2514\u2500\u2500\u2500",
            "",
        ]

        if d.get("has_temperature") and d.get("temperature_celsius") is not None:
            lines.append(u"\u250c\u2500 %s \u2500" % _("Readings"))
            lines.append(u"\u2502  %s:  %s" % (_("Temperature"), _fmt_temp(d["temperature_celsius"])))
            if d.get("has_humidity") and d.get("humidity_pct") is not None:
                lines.append(u"\u2502  %s:  %s" % (_("Humidity"), _fmt_humidity(d["humidity_pct"])))
            lines.append(u"\u2514\u2500\u2500\u2500")

        return "\n".join(lines)

    def _do_refresh(self):
        result = self.app.refresh_devices()
        ain = self._device.get("ain")
        for dev in (result.get("devices") or []):
            if dev.get("ain") == ain:
                self._device = dev
                self["body"].setText(self._build_text())
                return


# ===========================================================================
# Settings screen
# ===========================================================================

class FritzHomeSettingsScreen(Screen, ConfigListScreen):
    skin = """
        <screen name="FritzHomeSettingsScreen" position="center,100" size="980,560" title="FritzHome Einstellungen">
            <widget source="title"  render="Label" position="20,10"  size="940,36" font="Regular;30" />
            <widget name="config"   position="20,56"  size="940,330" scrollbarMode="showOnDemand" />
            <widget source="hint"   render="Label" position="20,396" size="940,60"  font="Regular;20" />
            <widget source="support" render="Label" position="20,464" size="940,24" font="Regular;18" foregroundColor="#666666" transparent="1" />
            <ePixmap pixmap="skin_default/buttons/red.png"    position="20,500"  size="220,30" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/green.png"  position="250,500" size="220,30" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/yellow.png" position="480,500" size="220,30" alphatest="on" />
            <widget source="key_red"    render="Label" position="20,500"  size="220,30" font="Regular;22" halign="center" valign="center" transparent="1" />
            <widget source="key_green"  render="Label" position="250,500" size="220,30" font="Regular;22" halign="center" valign="center" transparent="1" />
            <widget source="key_yellow" render="Label" position="480,500" size="220,30" font="Regular;22" halign="center" valign="center" transparent="1" />
        </screen>
    """

    _HELP = {
        "host": "Enter Fritz!Box hostname or IP address",
        "port": "Enter the web interface port (default: 80)",
        "username": "Enter Fritz!Box username (leave empty for default)",
        "password": "Enter Fritz!Box password",
    }

    def __init__(self, session, app, open_main_on_save):
        Screen.__init__(self, session)
        self.app = app
        self.open_main_on_save = bool(open_main_on_save)

        self["title"] = StaticText(_("Fritz!Box Settings"))
        self["hint"] = StaticText("")
        self["support"] = StaticText(SUPPORT_LINE)
        self["key_red"] = StaticText(_("Cancel"))
        self["key_green"] = StaticText(_("Save"))
        self["key_yellow"] = StaticText(_("Test connection"))

        self._entries = [
            getConfigListEntry(_("Fritz!Box Host/IP"), config.plugins.fritzhome.host),
            getConfigListEntry(_("Port"), config.plugins.fritzhome.port),
            getConfigListEntry(_("Username"), config.plugins.fritzhome.username),
            getConfigListEntry(_("Password"), config.plugins.fritzhome.password),
        ]
        ConfigListScreen.__init__(self, self._entries, session=session)

        try:
            self["config"].onSelectionChanged.append(self._update_hint)
        except Exception:
            pass
        self._update_hint()

        self["actions"] = ActionMap(
            ["SetupActions", "ColorActions", "OkCancelActions", "WizardActions"],
            {
                "save": self.key_green,
                "cancel": self.key_red,
                "green": self.key_green,
                "red": self.key_red,
                "yellow": self.key_yellow,
                "ok": self.key_ok,
                "back": self.key_red,
            },
            -2,
        )

    # ------------------------------------------------------------------
    # Key handlers
    # ------------------------------------------------------------------

    def key_ok(self):
        if Input is None or InputBox is None:
            try:
                ConfigListScreen.keyOK(self)
            except Exception:
                pass
            return

        current = self["config"].getCurrent()
        if not current:
            return
        cfg_item = current[1]

        if cfg_item is config.plugins.fritzhome.host:
            self.session.openWithCallback(
                lambda v: self._on_text_input(v, config.plugins.fritzhome.host),
                InputBox, title=_("Fritz!Box Host/IP"),
                text=config.plugins.fritzhome.host.value or "",
                maxSize=64, type=Input.TEXT,
            )
        elif cfg_item is config.plugins.fritzhome.username:
            self.session.openWithCallback(
                lambda v: self._on_text_input(v, config.plugins.fritzhome.username),
                InputBox, title=_("Username"),
                text=config.plugins.fritzhome.username.value or "",
                maxSize=64, type=Input.TEXT,
            )
        elif cfg_item is config.plugins.fritzhome.password:
            self.session.openWithCallback(
                lambda v: self._on_text_input(v, config.plugins.fritzhome.password),
                InputBox, title=_("Password"),
                text=config.plugins.fritzhome.password.value or "",
                maxSize=64, type=Input.TEXT,
            )
        elif cfg_item is config.plugins.fritzhome.port:
            self.session.openWithCallback(
                self._on_port_input,
                InputBox, title=_("Port"),
                text=str(config.plugins.fritzhome.port.value or "80"),
                maxSize=5, type=Input.NUMBER,
            )
        else:
            try:
                ConfigListScreen.keyOK(self)
            except Exception:
                pass

    def key_green(self):
        host = (config.plugins.fritzhome.host.value or "").strip()
        if not host:
            self.session.open(
                MessageBox,
                _("Please configure the Fritz!Box connection first"),
                MessageBox.TYPE_ERROR,
                timeout=5,
            )
            return

        for entry in self["config"].list:
            entry[1].save()
        config.plugins.fritzhome.save()
        try:
            configfile.save()
        except Exception:
            pass

        self.session.open(
            MessageBox, _("Settings saved"), MessageBox.TYPE_INFO, timeout=3
        )

        if self.open_main_on_save:
            from .plugin import get_app
            self.session.open(FritzHomeMainScreen, get_app())
        self.close()

    def key_red(self):
        for entry in self["config"].list:
            try:
                entry[1].cancel()
            except Exception:
                pass
        self.close()

    def key_yellow(self):
        host = (config.plugins.fritzhome.host.value or "").strip()
        port = 80
        try:
            port = int(config.plugins.fritzhome.port.value or 80)
        except Exception:
            pass
        username = (config.plugins.fritzhome.username.value or "").strip()
        password = (config.plugins.fritzhome.password.value or "").strip()

        from .core.api import FritzHomeApiClient
        client = FritzHomeApiClient(host=host, port=port, username=username, password=password)
        ok, error = client.ping()
        if ok:
            self.session.open(
                MessageBox,
                _("Connection test successful"),
                MessageBox.TYPE_INFO,
                timeout=4,
            )
        else:
            self.session.open(
                MessageBox,
                _("Connection test failed") + ":\n" + str(error),
                MessageBox.TYPE_ERROR,
                timeout=6,
            )

    # ------------------------------------------------------------------
    # Input callbacks
    # ------------------------------------------------------------------

    def _on_text_input(self, value, cfg_entry):
        if value is None:
            return
        cfg_entry.value = str(value).strip()

    def _on_port_input(self, value=None):
        if value is None:
            return
        digits = "".join(ch for ch in str(value) if ch.isdigit())
        if not digits:
            return
        try:
            config.plugins.fritzhome.port.value = int(digits)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Help text
    # ------------------------------------------------------------------

    def _update_hint(self):
        current = self["config"].getCurrent()
        if not current:
            return
        item = current[1]
        key = None
        if item is config.plugins.fritzhome.host:
            key = "host"
        elif item is config.plugins.fritzhome.port:
            key = "port"
        elif item is config.plugins.fritzhome.username:
            key = "username"
        elif item is config.plugins.fritzhome.password:
            key = "password"
        if key:
            self["hint"].setText(_(self._HELP[key]))


# ===========================================================================
# Info / About screen
# ===========================================================================

class FritzHomeInfoScreen(Screen):
    skin = """
        <screen name="FritzHomeInfoScreen" position="center,90" size="1000,620" title="FritzHome Info">
            <widget source="title"  render="Label" position="20,10"  size="960,44" font="Regular;34" />
            <widget name="body"     position="20,64"  size="680,490" font="Regular;24" scrollbarMode="showOnDemand" />
            <widget name="qr"       position="720,100" size="240,240" alphatest="blend" />
            <widget source="support" render="Label" position="20,562" size="960,26" font="Regular;20" foregroundColor="#555555" transparent="1" />
            <ePixmap pixmap="skin_default/buttons/red.png" position="20,592" size="220,30" alphatest="on" />
            <widget source="key_red" render="Label" position="20,592" size="220,30" font="Regular;24" halign="center" valign="center" transparent="1" />
        </screen>
    """

    def __init__(self, session):
        Screen.__init__(self, session)
        self["title"] = StaticText(_("FritzHome Information"))
        self["key_red"] = StaticText(_("Close"))
        self["support"] = StaticText(SUPPORT_LINE)
        self["body"] = ScrollLabel(self._build_text())
        self["qr"] = Pixmap()

        self["actions"] = ActionMap(
            ["OkCancelActions", "ColorActions", "DirectionActions"],
            {
                "ok": self.close,
                "cancel": self.close,
                "red": self.close,
                "up": self["body"].pageUp,
                "down": self["body"].pageDown,
                "left": self["body"].pageUp,
                "right": self["body"].pageDown,
            },
            -1,
        )

        self.onLayoutFinish.append(self._load_qr)

    def _build_text(self):
        lines = [
            "FritzHome v1.1",
            "",
            _("Data source") + ": AVM AHA HTTP API (Fritz!Box Smart Home)",
            "Port: 80 (HTTP)",
            "",
            u"Zeigt alle FRITZ!DECT Smart-Home-Ger\u00e4te:",
            u"  \u2022 Schaltbare Steckdosen (FRITZ!DECT 200/210)",
            u"  \u2022 Heizk\u00f6rperregler (FRITZ!DECT 300/301/302)",
            u"  \u2022 Temperatur- & Luftfeuchtigkeitssensoren",
            u"  \u2022 Energiemessung (Leistung, Verbrauch)",
            u"  \u2022 Batteriestatus & Urlaubsschaltungen",
            "",
            "Navigation:",
            u"  OK          \u2192 Details / Steuerung",
            u"  Links/Rechts \u2192 Filter umschalten",
            u"  Gr\u00fcn        \u2192 Aktualisieren",
            u"  Gelb        \u2192 Einstellungen",
            u"  Blau        \u2192 Diese Info-Seite",
            "",
            "Steuerung (Steckdose):",
            u"  OK/Gr\u00fcn     \u2192 Umschalten",
            u"  Rot         \u2192 Ein/Aus setzen",
            "",
            "Steuerung (Thermostat):",
            u"  Hoch/Gr\u00fcn   \u2192 Temperatur +0,5\u00b0C",
            u"  Runter/Rot  \u2192 Temperatur -0,5\u00b0C",
            "",
            "Buy me a coffee: https://buymeacoffee.com/madoe21",
            "GitHub: https://github.com/madoe21/enigma2-fritzhome",
        ]
        return "\n".join(lines)

    def _load_qr(self):
        candidates = [
            resolveFilename(SCOPE_PLUGINS, "Extensions/fritz_home/res/qr_buymeacoffee.png"),
            os.path.join(os.path.dirname(__file__), "res", "qr_buymeacoffee.png"),
        ]
        for path in candidates:
            if os.path.exists(path):
                try:
                    self["qr"].instance.setPixmapFromFile(path)
                    return
                except Exception:
                    pass
