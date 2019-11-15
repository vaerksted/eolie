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

from gi.repository import WebKit2

from time import time
from uuid import uuid4

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
            self.__user_form_name = split[1]
            self.__user_form_value = split[2]
            self.__pass_form_name = split[3]
            self.__pass_form_value = split[4]
            self.__form_uri = get_baseuri(split[5])
            self.__hostname = get_baseuri(self.uri)
            self.__ctime = int(time())
            self.__helper.get_by_uri(self.__hostname, self.__on_password)
        except Exception as e:
            Logger.error("WebViewCredentials::add_credentials(): %s", e)

    def save_credentials(self):
        """
            Save credentials to secrets
        """
        try:
            if not self.__uuid:
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
    def __on_password(self, attributes, password, uri, index, count):
        """
            Set login/password input
            @param attributes as {}
            @param password as str
            @param uri as str
            @param index as int
            @param count as int
        """
        try:
            if attributes is None:
                return
            if attributes["formSubmitURL"] == self.__form_uri:
                self.__uuid = attributes["uuid"]
        except Exception as e:
            Logger.error("WebViewCredentials::__on_password(): %s", e)
