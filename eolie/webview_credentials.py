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

from gi.repository import GLib

from time import time

from eolie.helper_passwords import PasswordsHelper
from eolie.define import App
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

    def add_credentials(self, uuid, user_form_name, user_form_value,
                        pass_form_name, uri, form_uri):
        """
            Add credential to webview
            @param uuid as str
            @param user_form_name as str
            @param user_form_value as str
            @param pass_form_name as str
            @param uri as str
            @param form_uri as str
        """
        self.__uuid = uuid
        self.__user_form_name = user_form_name
        self.__user_form_value = user_form_value
        self.__pass_form_name = pass_form_name
        self.__uri = uri
        self.__form_uri = form_uri
        self.__ctime = int(time())

    def save_credentials(self):
        """
            Save credentials to secrets
        """
        App().helper.call("SaveCredentials", self.get_page_id(),
                          GLib.Variant("(sssss)",
                                       (self.__uuid, self.__user_form_name,
                                        self.__pass_form_name, self.__uri,
                                        self.__form_uri)),
                          self.__on_save_credentials,
                          self.__form_uri,
                          self.__user_form_name,
                          self.__pass_form_name)

    @property
    def credentials_uri(self):
        """
            Get credentials URI
            @return str
        """
        return self.__uri

    @property
    def ctime(self):
        """
            Get credentials creation time
            @return int
        """
        return self.__ctime

#######################
# PRIVATE             #
#######################
    def __on_get_password(self, attributes, password, form_uri, index, count):
        """
            Push credential to sync
            @param attributes as {}
            @param password as str
            @param form_uri as str
            @param index as int
            @param count as int
        """
        try:
            if attributes is not None and App().sync_worker is not None:
                App().sync_worker.push_password(attributes["userform"],
                                                attributes["login"],
                                                attributes["passform"],
                                                password,
                                                attributes["hostname"],
                                                attributes["formSubmitURL"],
                                                attributes["uuid"])
        except Exception as e:
            Logger.error("CredentialsPopover::__on_get_password(): %s", e)

    def __on_save_credentials(self, source, result, form_uri,
                              user_form_name, pass_form_name):
        """
            Get password and push credential to sync
            @param source as GObject.Object
            @param result as Gio.AsyncResult
            @param form_uri as str
            @param user_form_name as str
            @param pass_form_name as str
        """
        helper = PasswordsHelper()
        helper.get(form_uri, user_form_name,
                   pass_form_name, self.__on_get_password)
