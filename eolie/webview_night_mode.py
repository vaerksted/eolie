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

from gi.repository import WebKit2, Gio

from time import time

from eolie.define import App
from eolie.css_stylesheets import StyleSheets


class WebViewNightMode:
    """
        Night mode for webview
    """

    def __init__(self):
        """
            Init night mode
        """
        self.__night_mode = False
        self.__started_time = 0
        self.__css_uri = None
        self.__cancellable = Gio.Cancellable.new()
        self.__stylesheets = StyleSheets()
        self.__stylesheets.set_cancellable(self.__cancellable)
        self.__stylesheets.connect("not-cached",
                                   self.__on_stylesheets_not_cached)
        self.__stylesheets.connect("populated",
                                   self.__on_stylesheets_populated)
        self.get_style_context().add_class("night-mode")
        self.__default_stylesheet = WebKit2.UserStyleSheet(
                     "body {\
                        color: #EAEAEA !important;\
                        background-color: #353535 !important\
                      }\
                      a {\
                        color: #F0FFFE !important;\
                      }\
                      a:hover {\
                        color: white !important;\
                      }",
                     WebKit2.UserContentInjectedFrames.ALL_FRAMES,
                     WebKit2.UserStyleLevel.USER,
                     None,
                     None)

    def load_css_uri(self, message):
        """
            Load CSS URI as user style
            @param message as str
        """
        self.__css_uri = self.uri
        self.__stylesheets.load_css_uri(message, self.__started_time)

    def load_css_text(self, message):
        """
            Load CSS text as user style
            @param message as str
        """
        self.__css_uri = self.uri
        self.__stylesheets.load_css_text(message,
                                         self.uri,
                                         self.__started_time)

    def night_mode(self):
        """
            Handle night mode
        """
        self.__stylesheets.reset()
        self.__css_uri = None
        if self.__should_apply_night_mode():
            self.run_javascript_from_gresource(
                "/org/gnome/Eolie/javascript/GetCSS.js", None, None)
        else:
            self.get_user_content_manager().remove_all_style_sheets()

    def remove_night_mode_cache(self):
        """
            Remove cache for current stylesheets
        """
        self.__stylesheets.remove_cache()

    @property
    def stylesheets(self):
        """
            Get stylesheets object
            @return StyleSheets
        """
        return self.__stylesheets

#######################
# PROTECTED           #
#######################
    def _on_load_changed(self, webview, event):
        """
            Run JS helpers
            @param webview as WebView
            @param event as WebKit2.LoadEvent
        """
        if not self.__should_apply_night_mode():
            self.get_user_content_manager().remove_all_style_sheets()
            return
        if event == WebKit2.LoadEvent.STARTED:
            self.__css_uri = None
            self.__started_time = int(time())
            self.__cancellable.cancel()
            self.__cancellable = Gio.Cancellable.new()
            self.__stylesheets.set_cancellable(self.__cancellable)
        elif event == WebKit2.LoadEvent.REDIRECTED:
            self.__css_uri = None
        elif webview.uri != self.__css_uri:
            self.run_javascript_from_gresource(
                "/org/gnome/Eolie/javascript/GetCSS.js", None, None)

#######################
# PRIVATE             #
#######################
    def __should_apply_night_mode(self):
        """
            True if night mode should be applied
            @return bool
        """
        night_mode = App().settings.get_value("night-mode")
        netloc_night_mode = App().websettings.get("night_mode", self.uri)
        return night_mode and netloc_night_mode in [1, None]

    def __on_stylesheets_not_cached(self, stylesheets):
        """
            Apply stylesheets
            @param stylesheets as StyleSheets
        """
        self.run_javascript("""
                    html = document.querySelector("html");
                    if (html !== null) {
                        html.style.display = "none";
                    }""", None, None)

    def __on_stylesheets_populated(self, stylesheets):
        """
            Apply stylesheets
            @param stylesheets as StyleSheets
        """
        content_manager = self.get_user_content_manager()
        content_manager.remove_all_style_sheets()
        content_manager.add_style_sheet(self.__default_stylesheet)
        user_style_sheet = WebKit2.UserStyleSheet(
                 stylesheets.get_css_text(self.__started_time),
                 WebKit2.UserContentInjectedFrames.ALL_FRAMES,
                 WebKit2.UserStyleLevel.USER,
                 None,
                 None)
        content_manager.add_style_sheet(user_style_sheet)
        self.run_javascript("""
            html = document.querySelector("html");
            if (html !== null) {
                html.style.display = "block";
            }""", None, None)
