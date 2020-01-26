# Copyright (c) 2017-2020 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from gi.repository import Gio, WebKit2

from urllib.parse import urlparse

from eolie.helper_passwords import PasswordsHelper
from eolie.utils import get_baseuri
from eolie.logger import Logger


class WebViewHelpers:
    """
        JS helpers for webview
    """

    def __init__(self):
        """
            Init helpers
        """
        self.__passwords_helper = PasswordsHelper()

    def set_forms_content(self, uuid):
        """
            Set input forms for uuid
            @parma uuid as str
        """
        self.__passwords_helper.get_by_uuid(uuid, self.__on_get_password_by)

#######################
# PROTECTED           #
#######################
    def _on_load_changed(self, webview, event):
        """
            Run JS helpers
            @param webview as WebView
            @param event as WebKit2.LoadEvent
        """
        if event == WebKit2.LoadEvent.FINISHED:
            self.__run_insecure(webview.uri)
            self.__run_set_forms(webview.uri)

#######################
# PRIVATE             #
#######################
    def __run_insecure(self, uri):
        """
            Run a script checking for password inputs while in http
            @parma uri as str
        """
        parsed = urlparse(uri)
        if parsed.scheme == "http":
            self.run_javascript_from_gresource(
                "/org/gnome/Eolie/javascript/Insecure.js", None, None)

    def __run_set_forms(self, uri):
        """
            Set input forms for current uri
            @parma uri as str
        """
        self.run_javascript_from_gresource(
                "/org/gnome/Eolie/javascript/FormMenu.js",
                None, self.__on_get_forms)

    def __on_get_forms(self, source, result):
        """
            Start search with selection
            @param source as GObject.Object
            @param result as Gio.AsyncResult
        """
        try:
            data = source.run_javascript_from_gresource_finish(result)
            message = data.get_js_value().to_string()
            split = message.split("\n")
            for user_form_name in split:
                self.__passwords_helper.get(get_baseuri(self.uri),
                                            user_form_name,
                                            None,
                                            self.__on_get_password_by)
        except Exception as e:
            Logger.warning("WebViewHelpers::__on_get_forms(): %s", e)

    def __on_get_password_by(self, attributes, password,
                             ignored, index, count):
        """
            Set login/password input
            @param attributes as {}
            @param password as str
            @param ignored
            @param index as int
            @param count as int
        """
        if attributes is None or count > 1:
            return
        f = Gio.File.new_for_uri(
            "resource:///org/gnome/Eolie/javascript/SetForms.js")
        (status, contents, tags) = f.load_contents(None)
        js = contents.decode("utf-8")
        js = js.replace("@INPUT_NAME@", attributes["userform"])
        js = js.replace("@INPUT_PASSWORD@", attributes["passform"])
        js = js.replace("@USERNAME@", attributes["login"])
        js = js.replace("@PASSWORD@", password)
        self.run_javascript(js, None, None)
