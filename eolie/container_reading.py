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


class ReadingContainer:
    """
        Reading management for container
    """

    def __init__(self):
        """
            Init container
        """
        self.__reading_view = None
        self.__reading_webview = None
        self.__reading_webview_id = None

    def toggle_reading(self):
        """
            Toggle reading mode
            @return status as bool
        """
        if self.__reading_view is None:
            js1 = Gio.File.new_for_uri(
                "resource:///org/gnome/Eolie/Readability.js")
            js2 = Gio.File.new_for_uri(
                "resource:///org/gnome/Eolie/Readability_get.js")
            (status, content1, tags) = js1.load_contents()
            (status, content2, tags) = js2.load_contents()
            script = content1.decode("utf-8") + content2.decode("utf-8")
            self.webview.run_javascript(script, None, None)
            self.__reading_webview = self.webview
            self.__reading_webview_id = self.__reading_webview.connect(
                "readability-content", self.__on_readability_content)
            return True
        else:
            if self.__reading_webview_id is not None:
                self.__reading_webview.disconnect(self.__reading_webview_id)
            self.__reading_webview = None
            self.__reading_webview_id = None
            self.__reading_view.destroy()
            self.__reading_view = None
            return False

    @property
    def reading(self):
        """
            True if reading
            @return bool
        """
        return self.__reading_view is not None

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

    def __on_readability_content(self, webview, content):
        """
            Show reading view
            @param webview as WebView
            @param content as str
        """
        system = Gio.Settings.new("org.gnome.desktop.interface")
        document_font_name = system.get_value("document-font-name").get_string(
        )
        document_font_size = str(int(document_font_name[-2:]) * 1.3) + "pt"
        if self.__reading_view is None:
            self.__reading_view = WebKit2.WebView.new()
            self.__reading_view.connect("decide-policy",
                                        self.__on_decide_policy)
            self.__reading_view.show()
            self.add_overlay(self.__reading_view)
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
            self.__reading_view.load_html(html, None)
