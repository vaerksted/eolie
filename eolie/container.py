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

from gi.repository import Gtk, GLib, Gdk

from gettext import gettext as _
from random import randint

from eolie.view import View
from eolie.popover_webview import WebViewPopover
from eolie.define import App
from eolie.container_sidebar import SidebarContainer
from eolie.container_expose import ExposeContainer
from eolie.container_view import ViewContainer


class Container(Gtk.Overlay, ViewContainer, SidebarContainer, ExposeContainer):
    """
        Main Eolie view
    """

    __DONATION = 1

    def __init__(self, window):
        """
            Ini.container
            @param window as Window
        """
        Gtk.Overlay.__init__(self)
        self._window = window
        SidebarContainer.__init__(self)
        ViewContainer.__init__(self)
        ExposeContainer.__init__(self)
        self.__popover = WebViewPopover(window)
        self.add(self._paned)
        # Show donation notification after one hour
        if App().settings.get_value("donation").get_int32() != self.__DONATION:
            GLib.timeout_add_seconds(randint(3600, 7200),
                                     self.__show_donation)

    def load_uri(self, uri):
        """
            Load uri in current view
            @param uri as str
        """
        if self.current is not None:
            self.current.webview.load_uri(uri)

    def popup_webview(self, webview, destroy):
        """
            Show webview in popopver
            @param webview as WebView
            @param destroy webview when popover hidden
        """
        view = View(webview, self._window, True)
        view.show()
        self.__popover.add_view(view, destroy)
        if not self.__popover.is_visible():
            self.__popover.set_relative_to(self._window.toolbar)
            self.__popover.set_position(Gtk.PositionType.BOTTOM)
            self.__popover.popup()

#######################
# PRIVATE             #
#######################
    def __show_donation(self):
        """
            Show a notification telling user to donate a little
        """
        from eolie.app_notification import AppNotification
        notification = AppNotification(
            _("Please consider a donation to the project"),
            [_("PayPal"), _("Patreon")],
            [lambda: Gtk.show_uri_on_window(
                App().active_window,
                "https://www.paypal.me/lollypopgnome",
                Gdk.CURRENT_TIME),
             lambda: Gtk.show_uri_on_window(
                App().active_window,
                "https://www.patreon.com/gnumdk",
                Gdk.CURRENT_TIME)])
        self.add_overlay(notification)
        notification.show()
        notification.set_reveal_child(True)
        App().settings.set_value("donation",
                                 GLib.Variant("i", self.__DONATION))
