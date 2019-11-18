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

from gi.repository import WebKit2, Gtk, Gdk

from time import time
from uuid import uuid4
from urllib.parse import urlparse

from eolie.helper_passwords import PasswordsHelper
from eolie.define import App
from eolie.utils import get_baseuri
from eolie.logger import Logger


class WebViewCredentials:
    """
        Implement WebView credentials
    """

    def __init__(self):
        """
            Init credentials
        """
        self.__uuid = ""
        self.__in_secrets_user_form_name = ""
        self.__user_form_name = ""
        self.__user_form_value = ""
        self.__pass_form_name = ""
        self.__uri = ""
        self.__form_uri = ""
        self.__ctime = 0
        self.__helper = PasswordsHelper()

    def add_credentials(self, message):
        """
            Add credential to webview
            @param message as str
        """
        try:
            split = message.split("\n")
            if split[1] != "undefined":
                self.__user_form_name = split[1]
                self.__user_form_value = split[2]
                self.__pass_form_name = split[3]
                self.__pass_form_value = split[4]
                self.__form_uri = get_baseuri(split[5])
                self.__hostname = get_baseuri(self.uri)
                self.__ctime = int(time())
                self.__helper.get(self.__hostname,
                                  self.__user_form_name,
                                  self.__pass_form_name,
                                  self.__on_get_password)
        except Exception as e:
            Logger.error("WebViewCredentials::add_credentials(): %s", e)

    def save_credentials(self):
        """
            Save credentials to secrets
        """
        try:
            # Store a new password if non exists or if login is different
            if not self.__uuid or\
                    self.__in_secrets_login != self.__user_form_value:
                self.__uuid = str(uuid4())
                self.__helper.store(self.__user_form_name,
                                    self.__user_form_value,
                                    self.__pass_form_name,
                                    self.__pass_form_value,
                                    self.__hostname,
                                    self.__form_uri,
                                    self.__uuid,
                                    None)
            else:
                self.__helper.clear(self.__uuid,
                                    self.__helper.store,
                                    self.__user_form_name,
                                    self.__user_form_value,
                                    self.__pass_form_name,
                                    self.__pass_form_value,
                                    self.__hostname,
                                    self.__form_uri,
                                    self.__uuid,
                                    None)
            if App().sync_worker is not None:
                App().sync_worker.push_password(self.__user_form_name,
                                                self.__user_form_value,
                                                self.__pass_form_name,
                                                self.__pass_form_value,
                                                self.__hostname,
                                                self.__form_uri,
                                                self.__uuid)
        except Exception as e:
            Logger.error("WebViewCredentials::save_credentials(): %s", e)
        self.__in_secrets_login = ""

    def show_form_menu(self, message):
        """
            Show form menu for message
            @param message as str
        """
        try:
            from eolie.menu_form import FormMenu
            split = message.split("\n")
            user_form_name = split[1]
            menu = FormMenu(self, self.window)
            self.__helper.get(get_baseuri(self.uri), user_form_name, None,
                              self.__on_menu_get_password,
                              menu,
                              user_form_name)
        except Exception as e:
            Logger.error("WebViewCredentials::show_form_menu(): %s", e)

    @property
    def credentials_uri(self):
        """
            Get credentials URI
            @return str
        """
        return self.__hostname

    @property
    def ctime(self):
        """
            Get credentials creation time
            @return int
        """
        return self.__ctime

#######################
# PROTECTED           #
#######################
    def _on_load_changed(self, webview, event):
        """
            Run JS helper
            @param webview as WebView
            @param event as WebKit2.LoadEvent
        """
        if event == WebKit2.LoadEvent.FINISHED:
            self.run_javascript_from_gresource(
                "/org/gnome/Eolie/javascript/Submit.js", None, None)

#######################
# PRIVATE             #
#######################
    def __on_get_password(self, attributes, password, uri, index, count):
        """
            Update uuid
            @param attributes as {}
            @param password as str
            @param uri as str
            @param index as int
            @param count as int
        """
        try:
            if attributes is None:
                return
            if attributes["login"] != self.__user_form_value and\
                    password != self.__pass_form_value:
                self.__in_secrets_login = attributes["login"]
                self.__uuid = attributes["uuid"]
            else:
                self.__ctime = 0
        except Exception as e:
            Logger.error("WebViewCredentials::__on_get_password(): %s", e)

    def __on_menu_get_password(self, attributes, password,
                               uri, index, count, menu, user_form_name):
        """
            Append to menu
            @param attributes as {}
            @param password as str
            @param uri as str
            @param index as int
            @param count as int
            @param menu as FormMenu
            @param user_form_name as str
        """
        try:
            parsed = urlparse(uri)
            if attributes is not None and (
                    count > 0 or parsed.scheme == "http"):
                menu.add_attributes(attributes, uri)
                if index == 0:
                    popover = Gtk.Popover.new_from_model(self, menu)
                    popover.set_modal(False)
                    self.window.register(popover)
                    rect = Gdk.Rectangle()
                    rect.x = self._last_click_event_x
                    rect.y = self._last_click_event_y - 10
                    rect.width = rect.height = 1
                    popover.set_pointing_to(rect)
                    popover.popup()
        except Exception as e:
            Logger.error("WebViewCredentials::__on_get_password(): %s", e)
