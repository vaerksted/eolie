# Copyright (c) 2017-2019 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gio, GLib, Gtk

from eolie.logger import Logger


class NightApplication:
    """
        Auto switch to night mode base on GSD state
    """

    def __init__(self):
        """
            Initiate connexion to DBus
        """
        try:
            self.__on_night_mode_changed(self.settings)
            self.settings.connect("changed::night-mode",
                                  self.__on_night_mode_changed)
            Gio.bus_get(Gio.BusType.SESSION, None, self.__on_get_bus)
            self.__wanted_temperature = None
            settings = Gio.Settings.new(
                "org.gnome.settings-daemon.plugins.color")
            self.__wanted_temperature = settings.get_value(
                "night-light-temperature").get_uint32()
        except Exception as e:
            Logger.error("NightApplication::__init__(): %s", e)

#######################
# PRIVATE             #
#######################
    def __on_get_bus(self, source, result):
        """
            Get bus and set proxy
            @param source as GObject.Object
            @param result as Gio.AsyncResult
        """
        try:
            bus = Gio.bus_get_finish(result)
            Gio.DBusProxy.new(
                bus,
                Gio.DBusProxyFlags.GET_INVALIDATED_PROPERTIES,
                None,
                "org.gnome.SettingsDaemon.Color",
                "/org/gnome/SettingsDaemon/Color",
                "org.gnome.SettingsDaemon.Color",
                None,
                self.__on_get_proxy)
        except Exception as e:
            Logger.error("NightApplication::__on_get_bus(): %s", e)

    def __on_get_proxy(self, source, result):
        """
            Get proxy and connect signal
            @param source as GObject.Object
            @param result as Gio.AsyncResult
        """
        try:
            self.__proxy = source.new_finish(result)
            self.__proxy.connect("g-properties-changed",
                                 self.__on_property_changed)
            if self.settings.get_value("auto-night-mode"):
                value = self.__proxy.get_cached_property(
                    "Temperature").get_uint32()
                self.__on_property_changed(self.__proxy,
                                           {"Temperature": value},
                                           [])
        except Exception as e:
            Logger.error("NightApplication::__on_get_bus(): %s", e)

    def __on_property_changed(self, proxy, changed_properties,
                              invalidated_properties):
        """
            Set Eolie night mode based on current temperature
            @param proxy as Gio.DBusProxy
            @param changed_properties as {}
            @param invalidated_properties as [str]
        """
        if not self.settings.get_value("auto-night-mode"):
            return
        if "Temperature" in changed_properties.keys():
            temperature = changed_properties["Temperature"]
            night_mode = self.settings.get_value("night-mode")
            new_night_mode = temperature < self.__wanted_temperature + 100
            if night_mode != new_night_mode:
                self.settings.set_value("night-mode",
                                        GLib.Variant("b", new_night_mode))

    def __on_night_mode_changed(self, settings, *ignore):
        """
            Update GTK style
            @param settings as Settings
        """
        night_mode = settings.get_value("night-mode")
        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-application-prefer-dark-theme", night_mode)
        for window in self.windows:
            GLib.idle_add(window.toolbar.title.entry.update_style)
            for webview in window.container.webviews:
                webview.night_mode()
