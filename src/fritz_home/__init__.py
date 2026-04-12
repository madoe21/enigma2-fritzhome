# -*- coding: utf-8 -*-
from __future__ import absolute_import

import gettext

from Components.Language import language
from Tools.Directories import SCOPE_PLUGINS, resolveFilename

PLUGIN_DOMAIN = "fritz_home"
PLUGIN_PATH = "Extensions/fritz_home/locale"

_DE_FALLBACK = {
    # General
    "Close": "Schließen",
    "Cancel": "Abbrechen",
    "Save": "Speichern",
    "Refresh": "Aktualisieren",
    "Settings": "Einstellungen",
    "Information": "Information",
    "Back": "Zurück",
    "Main menu": "Hauptmenü",
    "Error": "Fehler",
    "Loading...": "Wird geladen...",
    "Settings saved": "Einstellungen gespeichert",
    "Please configure the Fritz!Box connection first": "Bitte zuerst die Fritz!Box-Verbindung konfigurieren",
    "Using cached data": "Nutze zwischengespeicherte Daten",
    "Connection test successful": "Verbindungstest erfolgreich",
    "Connection test failed": "Verbindungstest fehlgeschlagen",
    "Test connection": "Verbindung testen",
    # Main screen
    "FritzHome - Smart Home Overview": "FritzHome – Smart Home Übersicht",
    "Devices": "Geräte",
    "present": "vorhanden",
    "All": "Alle",
    "Switches": "Steckdosen",
    "Sensors": "Sensoren",
    "Thermostats": "Heizkörper",
    "Filter": "Filter",
    "Updated": "Stand",
    "No devices found": "Keine Geräte gefunden",
    "Name": "Name",
    "Room": "Raum",
    "Status / Value": "Status / Wert",
    "Extra": "Extra",
    "on": "an",
    "off": "aus",
    "active": "aktiv",
    "inactive": "inaktiv",
    "unknown": "unbekannt",
    "Not present": "Nicht vorhanden",
    # Detail screen
    "Device Details": "Gerätedetails",
    "Toggle": "Umschalten",
    "Turn On": "Einschalten",
    "Turn Off": "Ausschalten",
    "Temperature": "Temperatur",
    "Humidity": "Luftfeuchtigkeit",
    "Target temperature": "Zieltemperatur",
    "Current temperature": "Aktuelle Temperatur",
    "Power": "Leistung",
    "Energy": "Energie",
    "Voltage": "Spannung",
    "Present": "Vorhanden",
    "AIN": "Gerätekennung",
    "Product": "Produkt",
    "Firmware": "Firmware",
    "Type": "Typ",
    "Increase temperature": "Temperatur erhöhen",
    "Decrease temperature": "Temperatur senken",
    "Switch state": "Schaltzustand",
    "Locked": "Gesperrt",
    "Group": "Gruppe",
    "n/a": "k.A.",
    # Settings screen
    "Fritz!Box Settings": "Fritz!Box-Einstellungen",
    "Fritz!Box Host/IP": "Fritz!Box Host/IP",
    "Port": "Port",
    "Username": "Benutzername",
    "Password": "Passwort",
    "Enter Fritz!Box hostname or IP address": "Hostname oder IP-Adresse der Fritz!Box eingeben",
    "Enter the web interface port (default: 80)": "Weboberflächen-Port eingeben (Standard: 80)",
    "Enter Fritz!Box username (leave empty for default)": "Fritz!Box-Benutzername (ggf. leer lassen)",
    "Enter Fritz!Box password": "Fritz!Box-Passwort eingeben",
    # Info screen
    "FritzHome Information": "FritzHome Information",
    "Data source": "Datenquelle",
}


def localeInit():
    gettext.bindtextdomain(PLUGIN_DOMAIN, resolveFilename(SCOPE_PLUGINS, PLUGIN_PATH))
    try:
        gettext.bind_textdomain_codeset(PLUGIN_DOMAIN, "UTF-8")
    except Exception:
        pass


def _(txt):
    translated = gettext.dgettext(PLUGIN_DOMAIN, txt)
    if translated != txt:
        return translated

    try:
        lang = language.getLanguage()[:2]
    except Exception:
        lang = "en"

    if lang == "de":
        return _DE_FALLBACK.get(txt, txt)
    return txt


localeInit()
try:
    language.addCallback(localeInit)
except Exception:
    pass
