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

from gi.repository import GLib

from gettext import gettext as _

from eolie.define import El


class WebViewJsSignals:
    """
        Handle webview scripts signals
    """

    def __init__(self):
        """
            Init class
        """
        self.__js_timeout_id = None
        self.__reset_js_blocker()
        self.connect("script-dialog", self.__on_script_dialog)

#######################
# PROTECTED           #
#######################
    def _on_map(self, webview):
        """
            Connect all signals
            @param webview as WebView
        """
        self.connect("resource-load-started",
                     self.__on_resource_load_started)

    def _on_unmap(self, webview):
        """
            Disconnect all signals
            @param webview as WebView
        """
        self.disconnect_by_func(self.__on_resource_load_started)

#######################
# PRIVATE             #
#######################
    def __reset_js_blocker(self):
        """
            Reset js blocker
        """
        self.__js_dialog_type = None
        self.__js_dialog_message = None

    def __on_script_dialog(self, webview, dialog):
        """
            Show message to user
            @param webview as WebView
            @param dialog as WebKit2.ScriptDialog
        """
        message = dialog.get_message()
        # Reader js message
        if message.startswith("@EOLIE_READER@"):
            self._readable_content = message.replace("@EOLIE_READER@", "")
            self.emit("readable")
        # Populars view message
        elif message.startswith("@EOLIE_HIDE_BOOKMARK_POPULARS@"):
            uri = message.replace("@EOLIE_HIDE_BOOKMARK_POPULARS@", "")
            El().bookmarks.reset_popularity(uri)
        # Populars view message
        elif message.startswith("@EOLIE_HIDE_HISTORY_POPULARS@"):
            uri = message.replace("@EOLIE_HIDE_HISTORY_POPULARS@", "")
            El().history.reset_popularity(uri)
        # Here we handle JS flood
        elif message == self.__js_dialog_message and\
                dialog.get_dialog_type() == self.__js_dialog_type:
            self._window.toolbar.title.show_message(
                   _("Eolie is going to close this page because it is broken"))
            self._window.container.pages_manager.close_view(self, False)
        # Webpage message
        else:
            self.__js_dialog_type = dialog.get_dialog_type()
            self.__js_dialog_message = dialog.get_message()
            self._window.toolbar.title.show_javascript(dialog)
            GLib.timeout_add(1000, self.__reset_js_blocker)
        return True

    def __on_resource_load_started(self, webview, resource, request):
        """
            Listen to off loading events
            @param webview as WebView
            @param resource WebKit2.WebResource
            @param request as WebKit2.URIRequest
        """
        # Javascript execution happened
        if not self.is_loading():
            if self.__js_timeout_id is not None:
                GLib.source_remove(self.__js_timeout_id)
            self.__js_timeout_id = GLib.timeout_add(500,
                                                    self.__on_js_timeout,
                                                    webview)

    def __on_js_timeout(self, webview):
        """
            Tell webpage to update credentials
            @param webview as WebView
        """
        self.__js_timeout_id = None
        page_id = self.get_page_id()
        El().helper.call("SetCredentials",
                         GLib.Variant("(i)", (page_id,)),
                         None,
                         page_id)