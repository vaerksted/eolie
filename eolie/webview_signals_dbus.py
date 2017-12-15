# Copyright (c) 2017 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from gi.repository import Gtk, Gdk, GLib

from urllib.parse import urlparse

from eolie.menu_form import FormMenu
from eolie.helper_passwords import PasswordsHelper
from eolie.define import El


class WebViewDBusSignals:
    """
        Handle webview DBus signals
    """

    def __init__(self):
        """
            Init class
        """
        pass

#######################
# PROTECTED           #
#######################
    def _on_map(self, webview):
        """
            Connect all signals
            @param webview as WebView
        """
        page_id = webview.get_page_id()
        El().helper.connect(None,
                            lambda a, b, c, d, e, f:
                            WebViewDBusSignals.__on_signal(self, e, f),
                            page_id)

    def _on_unmap(self, webview):
        """
            Disconnect all signals
            @param webview as WebView
        """
        page_id = webview.get_page_id()
        El().helper.disconnect(page_id)

#######################
# PRIVATE             #
#######################
    def __on_signal(self, signal, params):
        """
            Handle proxy signals
            @param signal as str
            @params as []
        """
        if signal == "UnsecureFormFocused":
            self._window.toolbar.title.show_input_warning(self)
        elif signal == "AskSaveCredentials":
            (uuid, user_form_name, user_form_value,
             pass_form_name, uri, form_uri) = params[0]
            self._window.close_popovers()
            self._window.toolbar.title.show_password(
                                             uuid,
                                             user_form_name,
                                             user_form_value,
                                             pass_form_name,
                                             uri,
                                             form_uri,
                                             self.get_page_id())
        elif signal == "ShowCredentials":
            (userform, form_uri) = params
            model = FormMenu(self.get_page_id(), self._window)
            helper = PasswordsHelper()
            helper.get(form_uri, userform, None, self.__on_password, model)

    def __on_password(self, attributes, password, uri, index, count, model):
        """
            Show form popover
            @param attributes as {}
            @param password as str
            @param uri as str
            @param index as int
            @param count as int
            @param model as FormMenu
        """
        parsed = urlparse(uri)
        if attributes is not None and (count > 1 or
                                       parsed.scheme == "http"):
            model.add_attributes(attributes, uri)
            if index == 0:
                popover = Gtk.Popover.new_from_model(self, model)
                popover.set_modal(False)
                self._window.register(popover)
                rect = Gdk.Rectangle()
                rect.x = self._last_click_event_x
                rect.y = self._last_click_event_y - 10
                rect.width = rect.height = 1
                popover.set_pointing_to(rect)
                popover.connect("closed", self.__on_form_popover_closed, model)
                popover.popup()

    def __on_form_popover_closed(self, popover, model):
        """
            Clean model
            @param popover as Gtk.Popover
            @param model as FormMenu
        """
        # Let model activate actions, idle needed to action activate
        GLib.idle_add(model.clean)
