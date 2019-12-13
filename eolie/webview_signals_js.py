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

from gettext import gettext as _

from eolie.define import App


class WebViewJsSignals:
    """
        Handle webview scripts signals
    """

    def __init__(self):
        """
            Init class
        """
        self.__js_blocker_count = 0
        self.__js_blocker_timeout_id = None
        self.connect("script-dialog", self.__on_script_dialog)

#######################
# PROTECTED           #
#######################

#######################
# PRIVATE             #
#######################
    def __reset_js_blocker(self):
        """
            Reset js blocker
        """
        self.__js_blocker_count = 0
        self.__js_blocker_timeout_id = None

    def __on_script_dialog(self, webview, dialog):
        """
            Show message to user
            @param webview as WebView
            @param dialog as WebKit2.ScriptDialog
        """
        if self.__js_blocker_timeout_id is not None:
            GLib.source_remove(self.__js_blocker_timeout_id)
            self.__js_blocker_timeout_id = None
        message = dialog.get_message()
        if message.startswith("@EOLIE_CSS_URI@"):
            webview.load_css_uri(message)
        elif message.startswith("@EOLIE_CSS_TEXT@"):
            webview.load_css_text(message)
        # Credentials message
        elif message.startswith("@EOLIE_SUBMIT@"):
            webview.add_credentials(message)
        # Input menu message
        elif message.startswith("@EOLIE_FORM_MENU_MESSAGE@"):
            webview.show_form_menu(message)
        # Focus message
        elif message.startswith("@EOLIE_FOCUS_MESSAGE@"):
            self.window.toolbar.title.show_input_warning(self)
        # Reader js message
        elif message.startswith("@EOLIE_READER@"):
            self.emit("readability-content",
                      message.replace("@EOLIE_READER@", ""))
        elif message.startswith("@EOLIE_READERABLE@"):
            self._readability = True
            self.emit("readability-status", True)
        # OpenSearch message
        elif message.startswith("@EOLIE_OPENSEARCH@"):
            uri = message.replace("@EOLIE_OPENSEARCH@", "")
            App().search.install_engine(uri, self.window)
        # Populars view message
        elif message.startswith("@EOLIE_HIDE_BOOKMARK_POPULARS@"):
            uri = message.replace("@EOLIE_HIDE_BOOKMARK_POPULARS@", "")
            App().bookmarks.reset_popularity(uri)
        # Populars view message
        elif message.startswith("@EOLIE_HIDE_HISTORY_POPULARS@"):
            uri = message.replace("@EOLIE_HIDE_HISTORY_POPULARS@", "")
            App().history.reset_popularity(uri)
        # Here we handle JS flood
        elif self.__js_blocker_count > 5:
            self.__js_blocker_count = 0
            self.window.toolbar.title.show_message(
                _("Eolie is going to close this page because it is broken"))
            self.window.container.close_webview(self.view)
        # Webpage message
        else:
            self.window.toolbar.title.show_javascript(dialog)
            self.__js_blocker_count += 1
            self.__js_blocker_timeout_id = GLib.timeout_add(
                1000,
                self.__reset_js_blocker)
        return True
