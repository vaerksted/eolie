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

from gi.repository import GLib, WebKit2

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
        self.__google_fix_count = 0
        self.__js_blocker_count = 0
        self.__js_blocker_timeout_id = None
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
        # Reader js message
        if message.startswith("@EOLIE_READER@"):
            self._readable_content = message.replace("@EOLIE_READER@", "")
            self.emit("readable")
        # OpenSearch message
        elif message.startswith("@EOLIE_OPENSEARCH@"):
            uri = message.replace("@EOLIE_OPENSEARCH@", "")
            El().search.install_engine(uri, self._window)
        # Populars view message
        elif message.startswith("@EOLIE_HIDE_BOOKMARK_POPULARS@"):
            uri = message.replace("@EOLIE_HIDE_BOOKMARK_POPULARS@", "")
            El().bookmarks.reset_popularity(uri)
        # Populars view message
        elif message.startswith("@EOLIE_HIDE_HISTORY_POPULARS@"):
            uri = message.replace("@EOLIE_HIDE_HISTORY_POPULARS@", "")
            El().history.reset_popularity(uri)
        # Here we handle JS flood
        elif self.__js_blocker_count > 5:
            self.__js_blocker_count = 0
            self._window.toolbar.title.show_message(
                   _("Eolie is going to close this page because it is broken"))
            self._window.container.close_view(self.view)
        # Webpage message
        else:
            self._window.toolbar.title.show_javascript(dialog)
            self.__js_blocker_count += 1
            self.__js_blocker_timeout_id = GLib.timeout_add(
                                                       1000,
                                                       self.__reset_js_blocker)
        return True

    def __on_resource_load_started(self, webview, resource, request):
        """
            Listen to off loading events
            @param webview as WebView
            @param resource WebKit2.WebResource
            @param request as WebKit2.URIRequest
        """
        # Javascript execution happened
        if self.current_event == WebKit2.LoadEvent.FINISHED:
            # Special google notifications fix
            # https://bugs.webkit.org/show_bug.cgi?id=175189
            # https://bugzilla.gnome.org/show_bug.cgi?id=792130
            # TODO Remove this, fixed soon in libsoup
            storage = El().settings.get_enum("cookie-storage")
            # WebKit2.CookieAcceptPolicy.NO_THIRD_PARTY
            if storage == 2:
                uri = resource.get_uri()
                if uri.startswith("https://notifications.google.com/"):
                    self.__google_fix_count += 1
                    resource.connect("finished",
                                     self.__on_resource_load_finished)
                    cookie_manager = self.get_context().get_cookie_manager()
                    cookie_manager.set_accept_policy(0)

    def __on_resource_load_finished(self, resource):
        """
            Restore cookie storage default behaviour
            @param resource as WebKit2.WebResource
        """
        self.__google_fix_count -= 1
        if self.__google_fix_count == 0:
            cookie_manager = self.get_context().get_cookie_manager()
            storage = El().settings.get_enum("cookie-storage")
            cookie_manager.set_accept_policy(storage)
