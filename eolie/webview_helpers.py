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

from gi.repository import WebKit2, Gio

from urllib.parse import urlparse

from eolie.helper_passwords import PasswordsHelper


class WebViewHelpers:
    """
        JS helpers for webview
    """

    def __init__(self):
        """
            Init credentials
        """
        self.__helper = PasswordsHelper()

#######################
# PROTECTED           #
#######################
    def _on_load_changed(self, webview, event):
        """
            Update internals
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
        # First get passwords for URI
        self.__helper.get_by_uri(self.__get_hostname_uri(uri),
                                 self.__on_password)

    def __get_hostname_uri(self, uri):
        """
            Get form uri for page
            @param uri as str
            @return str
        """
        parsed = urlparse(uri)
        return "%s://%s" % (parsed.scheme, parsed.netloc)

    def __on_password(self, attributes, password, uri, index, count):
        """
            Set login/password input
            @param attributes as {}
            @param password as str
            @param uri as str
            @param index as int
            @param count as int
        """
        if attributes is None:
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
