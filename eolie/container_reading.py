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

from gi.repository import Gio

from gettext import gettext as _
from base64 import b64decode

from eolie.utils import emit_signal
from eolie.webview import WebView
from eolie.logger import Logger


class ReadingContainer:
    """
        Reading management for container
    """

    def __init__(self):
        """
            Init container
        """
        self._reading_webview = None
        self.__related_webview = None
        self.__related_webview_id = None

    def toggle_reading(self):
        """
            Toggle reading mode
            @return status as bool
        """
        if self._reading_webview is None:
            js1 = Gio.File.new_for_uri(
                "resource:///org/gnome/Eolie/Readability.js")
            js2 = Gio.File.new_for_uri(
                "resource:///org/gnome/Eolie/Readability_get.js")
            (status, content1, tags) = js1.load_contents()
            (status, content2, tags) = js2.load_contents()
            script = content1.decode("utf-8") + content2.decode("utf-8")
            self.webview.run_javascript(script, None,
                                        self.__on_readability_content)
            self.__related_webview = self.webview
            return True
        else:
            if self.__related_webview_id is not None:
                self.__related_webview.disconnect(self.__related_webview_id)
            self.__related_webview = None
            self.__related_webview_id = None
            self._reading_webview.destroy()
            self._reading_webview = None
            return False

    def set_visible_webview(self, webview):
        """
            Set visible webview
            @param webview as WebView
        """
        if self.reading:
            self.toggle_reading()
        emit_signal(webview, "readability-status", webview.readability_status)
        webview.check_readability()

    @property
    def reading(self):
        """
            True if reading
            @return bool
        """
        return self._reading_webview is not None

#######################
# PRIVATE             #
#######################
    def __on_decide_policy(self, webview, decision, decision_type):
        """
            Load link inside main view
            @param webview as WebKit2.WebView
            @param decision as WebKit2.NavigationPolicyDecision
            @param decision_type as WebKit2.PolicyDecisionType
            @return bool
        """
        navigation_action = decision.get_navigation_action()
        navigation_uri = navigation_action.get_request().get_uri()
        if navigation_uri == "about:blank":  # load_html()
            decision.use()
            return True
        else:
            self.webview.load_uri(navigation_uri)
            webview.destroy()
            return False

    def __on_readability_content(self, webview, result):
        """
            Show reading content
            @param webview as WebView
            @param result as Gio.AsyncResult
        """
        try:
            data = webview.run_javascript_from_gresource_finish(result)
            bytes = data.get_js_value().to_string_as_bytes()
            content = b64decode(bytes.get_data()).decode("utf-8")
        except Exception as e:
            Logger.error("ReadingContainer::__on_readability_content(): %s", e)
            content = _("Nothing to display")
        system = Gio.Settings.new("org.gnome.desktop.interface")
        document_font_name = system.get_value("document-font-name").get_string(
        )
        document_font_size = str(int(document_font_name[-2:]) * 1.3) + "pt"
        if self._reading_webview is None:
            self._reading_webview = WebView.new(webview.window)
            self._reading_webview.set_zoom_level(webview.get_zoom_level())
            self._reading_webview.connect("decide-policy",
                                          self.__on_decide_policy)
            self._reading_webview.show()
            self.overlay.add_overlay(self._reading_webview)
            html = "<html><head>\
                    <style type='text/css'>\
                    *:not(img) {font-size: %s;\
                        background-color: #333333;\
                        color: #e6e6e6;\
                        margin-left: auto;\
                        margin-right: auto;\
                        width: %s}\
                    </style></head>" % (document_font_size,
                                        self.get_allocated_width() / 1.5)
            html += "<title>%s</title>" % webview.title
            html += content
            html += "</html>"
            self._reading_webview.load_html(html, None)
