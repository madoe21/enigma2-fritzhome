# -*- coding: utf-8 -*-
"""
FritzHome – Fritz!Box AHA (AVM Home Automation) API client.

Uses the Fritz!Box HTTP-based AHA interface (port 80) to query smart home
devices – temperature sensors, humidity sensors, smart plugs and heating
thermostats – and to issue control commands.

Authentication uses AVM's MD5 challenge-response scheme (Fritz!OS 6+).

This module is intentionally kept free of any Enigma2 / Kodi imports so
that it can be reused as-is in a Kodi addon or any other Python environment.
"""
from __future__ import absolute_import

import hashlib
import time

try:
    from urllib2 import urlopen, Request, HTTPError, URLError
    from urllib import urlencode
    from urllib import quote as _url_quote
except ImportError:
    from urllib.request import urlopen, Request
    from urllib.error import HTTPError, URLError
    from urllib.parse import urlencode
    from urllib.parse import quote as _url_quote

try:
    from xml.etree import cElementTree as ET
except ImportError:
    from xml.etree import ElementTree as ET

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_LOGIN_PATH = "/login_sid.lua"
_AHA_PATH = "/webservices/homeautoswitch.lua"
_SID_ZERO = "0000000000000000"
_SID_TTL = 1080  # renew SID after 18 min (Fritz!Box invalidates after 20 min)

# Fritz!Box AHA functionbitmask bit values
FUNC_SOCKET = 64          # bit 6: switchable socket / on-off device
FUNC_DIMMABLE = 128       # bit 7: dimmable device
FUNC_COLOR = 256          # bit 8: color light
FUNC_BLIND = 512          # bit 9: blind / roller shutter
FUNC_HUMIDITY = 1024      # bit 10: humidity sensor
FUNC_TEMPERATURE = 2048   # bit 11: temperature sensor
FUNC_POWERMETER = 4096    # bit 12: energy / power meter
FUNC_THERMOSTAT = 8192    # bit 13: thermostat / Heizkörperregler (HKR)
FUNC_ALARM = 16384        # bit 14: alarm sensor

# Thermostat special values
HKR_OFF = 253   # param value meaning "thermostat off"
HKR_MAX = 254   # param value meaning "maximum heat"
HKR_MIN_DEG = 8.0   # 16 / 2
HKR_MAX_DEG = 28.0  # 56 / 2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _md5_challenge_response(challenge, password):
    """Return <challenge>-<md5> string (Fritz!Box MD5 login scheme)."""
    raw = (challenge + "-" + password).encode("utf-16-le")
    return challenge + "-" + hashlib.md5(raw).hexdigest()


def _elem_text(parent, tag, default=""):
    """Return stripped text of first child element with the given local tag."""
    child = parent.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return default


def _parse_device(elem):
    """Parse one <device> or <group> XML element into a normalised dict."""
    ain_raw = (elem.get("identifier") or "").strip()
    ain = ain_raw.replace(" ", "")

    bitmask = 0
    try:
        bitmask = int(elem.get("functionbitmask") or "0")
    except (ValueError, TypeError):
        pass

    device = {
        # Identity
        "ain": ain,
        "ain_display": ain_raw,
        "id": (elem.get("id") or "").strip(),
        "fwversion": (elem.get("fwversion") or "").strip(),
        "product": (elem.get("productname") or "").strip(),
        "manufacturer": (elem.get("manufacturer") or "").strip(),
        "functionbitmask": bitmask,
        "name": _elem_text(elem, "name", ain_raw),
        "present": _elem_text(elem, "present", "0") == "1",
        "is_group": elem.tag == "group",
        "group_members": [],   # populated for <group> elements
        "group": "",           # populated for <device> elements via group membership
        # Capability flags (may be updated during XML parsing below)
        "has_switch": bool(bitmask & FUNC_SOCKET),
        "has_temperature": bool(bitmask & FUNC_TEMPERATURE),
        "has_humidity": bool(bitmask & FUNC_HUMIDITY),
        "has_powermeter": bool(bitmask & FUNC_POWERMETER),
        "has_thermostat": bool(bitmask & FUNC_THERMOSTAT),
        # Values (None = no data available)
        "switch_state": None,
        "switch_locked": False,
        "temperature_celsius": None,
        "humidity_pct": None,
        "power_w": None,
        "energy_wh": None,
        "thermostat_current": None,
        "thermostat_target": None,
        "battery_pct": None,
        "battery_low": False,
        "window_open": False,
        "boost_active": False,
        "holidays": [],   # list of {name, start, end, temp}
    }

    # --- <switch> ---
    sw = elem.find("switch")
    if sw is not None:
        state = _elem_text(sw, "state", "")
        device["switch_state"] = (state == "1") if state in ("0", "1") else None
        device["switch_locked"] = _elem_text(sw, "lock", "0") == "1"
        device["has_switch"] = True
    else:
        # Fallback: <simpleonoff> used by some HAN-FUN devices
        soo = elem.find("simpleonoff")
        if soo is not None:
            state = _elem_text(soo, "state", "")
            device["switch_state"] = (state == "1") if state in ("0", "1") else None
            device["has_switch"] = True

    # --- <temperature> ---
    temp_elem = elem.find("temperature")
    if temp_elem is not None:
        c_raw = _elem_text(temp_elem, "celsius", "")
        off_raw = _elem_text(temp_elem, "offset", "0")
        try:
            device["temperature_celsius"] = round(
                (int(c_raw) + int(off_raw)) / 10.0, 1
            )
            device["has_temperature"] = True
        except (ValueError, TypeError):
            pass

    # --- <humidity> ---
    hum_elem = elem.find("humidity")
    if hum_elem is not None:
        h_raw = _elem_text(hum_elem, "rel_humidity", "")
        try:
            device["humidity_pct"] = int(h_raw)
            device["has_humidity"] = True
        except (ValueError, TypeError):
            pass

    # --- <powermeter> ---
    pm_elem = elem.find("powermeter")
    if pm_elem is not None:
        device["has_powermeter"] = True
        p_raw = _elem_text(pm_elem, "power", "")
        e_raw = _elem_text(pm_elem, "energy", "")
        try:
            device["power_w"] = round(int(p_raw) / 1000.0, 1)
        except (ValueError, TypeError):
            pass
        try:
            device["energy_wh"] = int(e_raw)
        except (ValueError, TypeError):
            pass

    # --- <hkr>  (Heizkörperregler / thermostat) ---
    hkr = elem.find("hkr")
    if hkr is not None:
        device["has_thermostat"] = True

        tist_raw = _elem_text(hkr, "tist", "")
        try:
            tist = int(tist_raw)
            if 16 <= tist <= 56:
                device["thermostat_current"] = tist / 2.0
            elif tist == HKR_MAX:
                device["thermostat_current"] = HKR_MAX_DEG
        except (ValueError, TypeError):
            pass

        tsoll_raw = _elem_text(hkr, "tsoll", "")
        try:
            tsoll = int(tsoll_raw)
            if 16 <= tsoll <= 56:
                device["thermostat_target"] = tsoll / 2.0
            elif tsoll == HKR_MAX:
                device["thermostat_target"] = HKR_MAX_DEG
            elif tsoll == HKR_OFF:
                device["thermostat_target"] = None  # off
        except (ValueError, TypeError):
            pass

        # Battery
        bat_raw = _elem_text(hkr, "battery", "")
        try:
            device["battery_pct"] = int(bat_raw)
        except (ValueError, TypeError):
            pass
        device["battery_low"] = _elem_text(hkr, "batterylow", "0") == "1"

        # Boost / window-open
        device["window_open"] = _elem_text(hkr, "windowopenactiv", "0") == "1"
        device["boost_active"] = _elem_text(hkr, "boostactive", "0") == "1"

        # Holiday / vacation schedules (nextchange + holiday elements)
        holidays = []
        nc = hkr.find("nextchange")
        if nc is not None:
            nc_end = _elem_text(nc, "endperiod", "")
            nc_temp_raw = _elem_text(nc, "tchange", "")
            if nc_end:
                nc_temp = None
                try:
                    t = int(nc_temp_raw)
                    if 16 <= t <= 56:
                        nc_temp = t / 2.0
                    elif t == HKR_OFF:
                        nc_temp = None
                    elif t == HKR_MAX:
                        nc_temp = HKR_MAX_DEG
                except (ValueError, TypeError):
                    pass
                holidays.append({
                    "name": "Nextchange",
                    "start": "",
                    "end": nc_end,
                    "temp": nc_temp,
                })
        device["holidays"] = holidays

    # --- <groupinfo> for <group> elements ---
    gi = elem.find("groupinfo")
    if gi is not None:
        members_raw = _elem_text(gi, "members", "")
        device["group_members"] = [m.strip() for m in members_raw.split(",") if m.strip()]

    return device


def _parse_device_list(xml_text):
    """Parse getdevicelistinfos XML.  Returns (devices, groups).

    Devices that belong to a group get their ``group`` field populated with
    the group's display name.
    """
    try:
        root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, type(u"")) else xml_text)
    except Exception:
        return [], []

    all_items = []
    for child in root:
        if child.tag in ("device", "group"):
            all_items.append(_parse_device(child))

    devices = [d for d in all_items if not d["is_group"]]
    groups = [d for d in all_items if d["is_group"]]

    # Propagate group name to member devices (match by device id)
    id_to_device = {d["id"]: d for d in devices if d["id"]}
    for grp in groups:
        for mid in grp["group_members"]:
            dev = id_to_device.get(mid)
            if dev and not dev["group"]:
                dev["group"] = grp["name"]

    return devices, groups


def device_type_label(device):
    """Return a short human-readable type string for the device."""
    if device.get("has_thermostat"):
        return "Thermostat"
    if device.get("has_switch") and device.get("has_powermeter"):
        return "Steckdose+"
    if device.get("has_switch"):
        return "Steckdose"
    if device.get("has_humidity") and device.get("has_temperature"):
        return "Sensor"
    if device.get("has_temperature"):
        return "Thermometer"
    if device.get("has_humidity"):
        return "Hygro"
    return "Gerät"


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------

class FritzHomeApiClient(object):
    """AVM AHA HTTP client for Fritz!Box Smart Home devices."""

    def __init__(self, host="fritz.box", port=80, username="", password=""):
        self.host = (host or "fritz.box").strip()
        self.port = int(port) if port else 80
        self.username = (username or "").strip()
        self.password = (password or "").strip()
        self._sid = None
        self._sid_acquired = 0.0

    # ------------------------------------------------------------------
    # Internal plumbing
    # ------------------------------------------------------------------

    def _base_url(self):
        if self.port == 80:
            return "http://%s" % self.host
        return "http://%s:%d" % (self.host, self.port)

    def _http_get(self, path, params=None, timeout=10):
        url = self._base_url() + path
        if params:
            url = url + "?" + urlencode(params)
        response = urlopen(Request(url), timeout=timeout)
        raw = response.read()
        return raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw

    def _http_post(self, path, data_dict, timeout=10):
        url = self._base_url() + path
        body = urlencode(data_dict)
        if isinstance(body, type(u"")):
            body = body.encode("utf-8")
        req = Request(url, data=body)
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        response = urlopen(req, timeout=timeout)
        raw = response.read()
        return raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw

    def _parse_sid_xml(self, xml_text):
        """Return (sid, challenge) from login_sid.lua response."""
        try:
            root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, type(u"")) else xml_text)
        except Exception:
            return _SID_ZERO, ""
        sid_elem = root.find("SID")
        ch_elem = root.find("Challenge")
        sid = (sid_elem.text or _SID_ZERO).strip() if sid_elem is not None else _SID_ZERO
        challenge = (ch_elem.text or "").strip() if ch_elem is not None else ""
        return sid, challenge

    def _login(self):
        """Run the challenge-response login flow.  Returns SID string or raises."""
        try:
            xml = self._http_get(_LOGIN_PATH)
        except Exception as exc:
            raise Exception("Verbindung fehlgeschlagen: %s" % exc)

        sid, challenge = self._parse_sid_xml(xml)
        if sid != _SID_ZERO:
            return sid   # already authenticated (unlikely for fresh call)

        if not challenge:
            raise Exception("Kein Challenge vom Fritz!Box empfangen")

        response = _md5_challenge_response(challenge, self.password)
        post_data = {"response": response}
        if self.username:
            post_data["username"] = self.username

        try:
            xml2 = self._http_post(_LOGIN_PATH, post_data)
        except Exception as exc:
            raise Exception("Login-Anfrage fehlgeschlagen: %s" % exc)

        sid2, _ = self._parse_sid_xml(xml2)
        if sid2 == _SID_ZERO:
            raise Exception("Authentifizierung fehlgeschlagen – Passwort prüfen")
        return sid2

    def _get_sid(self, force_new=False):
        """Return a valid SID, re-authenticating when the session has expired."""
        now = time.time()
        if (not force_new) and self._sid and self._sid != _SID_ZERO:
            if (now - self._sid_acquired) < _SID_TTL:
                return self._sid
        sid = self._login()
        self._sid = sid
        self._sid_acquired = now
        return sid

    def _aha(self, cmd, ain=None, param=None):
        """Issue one AHA command; retries once after re-authenticating on 403."""
        for attempt in range(2):
            sid = self._get_sid(force_new=(attempt > 0))
            params = {"switchcmd": cmd, "sid": sid}
            if ain is not None:
                params["ain"] = ain
            if param is not None:
                params["param"] = param
            try:
                return self._http_get(_AHA_PATH, params).strip()
            except HTTPError as exc:
                if exc.code == 403 and attempt == 0:
                    self._sid = None   # invalidate, force re-login on retry
                    continue
                raise
        return ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_devices(self):
        """Fetch all AHA smart home devices and groups.

        Returns:
            (devices, groups, error)
            - devices: list of device dicts, or None on fatal error
            - groups:  list of group dicts, or None on fatal error
            - error:   human-readable error string, or None on success
        """
        try:
            xml = self._aha("getdevicelistinfos")
            devices, groups = _parse_device_list(xml)
            return devices, groups, None
        except URLError as exc:
            return None, None, "Netzwerkfehler: %s" % exc
        except HTTPError as exc:
            if exc.code == 403:
                return None, None, "Zugriff verweigert – Passwort prüfen (HTTP 403)"
            return None, None, "HTTP Fehler %d" % exc.code
        except Exception as exc:
            return None, None, "Fehler: %s" % exc

    def set_switch(self, ain, state):
        """Turn a socket/switch on (True) or off (False).

        Returns (ok, error).
        """
        cmd = "setswitchon" if state else "setswitchoff"
        try:
            self._aha(cmd, ain=ain)
            return True, None
        except Exception as exc:
            return False, str(exc)

    def toggle_switch(self, ain):
        """Toggle a socket/switch state.

        Returns (ok, error).
        """
        try:
            self._aha("setswitchtoggle", ain=ain)
            return True, None
        except Exception as exc:
            return False, str(exc)

    def set_thermostat_temp(self, ain, temp_celsius):
        """Set thermostat target temperature.

        temp_celsius: float in range 8.0–28.0 (step 0.5).
                      Pass None to turn the thermostat off.

        Returns (ok, error).
        """
        try:
            if temp_celsius is None:
                param = HKR_OFF
            else:
                t = max(HKR_MIN_DEG, min(HKR_MAX_DEG, float(temp_celsius)))
                param = int(round(t * 2))
                param = max(16, min(56, param))
            self._aha("sethkrtsoll", ain=ain, param=param)
            return True, None
        except Exception as exc:
            return False, str(exc)

    def ping(self):
        """Quick connectivity and auth check.

        Returns (ok, error).
        """
        try:
            self._get_sid(force_new=True)
            return True, None
        except URLError as exc:
            return False, "Netzwerkfehler: %s" % exc
        except HTTPError as exc:
            if exc.code == 403:
                return False, "Zugriff verweigert – Passwort prüfen (HTTP 403)"
            return False, "HTTP Fehler %d: %s" % (exc.code, getattr(exc, "reason", "") or "")
        except Exception as exc:
            return False, str(exc)
