# Copyright (c) 2017-2018 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from gi.repository import Gtk

from gettext import gettext as _

from eolie.define import App, Indicator


class GeolocationPopover(Gtk.Popover):
    """
        Show JavaScript message
        @warning: will block current execution
    """

    def __init__(self, uri, request, window):
        """
            Init popover
            @param uri as str
            @param request as WebKit2.PermissionRequest
            @param window as window
        """
        Gtk.Popover.__init__(self)
        self.set_modal(False)
        window.register(self)
        self.__uri = uri
        self.__request = request
        self.__window = window
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/PopoverGeolocation.ui")
        builder.connect_signals(self)
        self.__switch = builder.get_object("switch")
        widget = builder.get_object("widget")
        label = builder.get_object("label")
        label.set_text(_("Grant this page access to your location?"))
        self.add(widget)

#######################
# PROTECTED           #
#######################
    def _on_ok_button_clicked(self, button):
        """
            Pass ok to js
            @param button as Gtk.Button
        """
        self.__request.allow()
        self.hide()
        if self.__switch.get_active():
            App().websettings.allow_geolocation(self.__uri, True)
            self.__window.toolbar.title.show_indicator(Indicator.GEOLOCATION)

    def _on_cancel_button_clicked(self, button):
        """
            Pass ok to js
            @param button as Gtk.Button
        """
        self.__request.deny()
        self.hide()

#######################
# PRIVATE             #
#######################
