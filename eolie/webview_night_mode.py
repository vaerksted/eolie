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

from gi.repository import WebKit2, Gio, GLib

from eolie.helper_task import TaskHelper
from eolie.define import App, EolieLoadEvent
from eolie.css_stylesheet import StyleSheet


class WebViewNightMode:
    """
        Night mode for webview
    """

    def __init__(self):
        """
            Init night mode
        """
        self.__loading_css = 0
        self.__load_finished = False
        self.__stylesheets = []
        self.__task_helper = TaskHelper()
        self.__cancellable = Gio.Cancellable.new()
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
        self.__loading_css += 1
        uri = message.replace("@EOLIE_CSS_URI@", "")
        for stylesheet in self.__stylesheets:
            if stylesheet.uri == uri:
                return
        stylesheet = StyleSheet(uri=uri)
        stylesheet.connect("populated", self.__on_stylesheet_populated)
        self.__task_helper.run(stylesheet.populate)

    def load_css_text(self, message):
        """
            Load CSS text as user style
        """
        content = message.replace("@EOLIE_CSS_TEXT@", "")
        if content:
            self.__loading_css += 1
            stylesheet = StyleSheet(content=content)
            stylesheet.connect("populated", self.__on_stylesheet_populated)
            self.__task_helper.run(stylesheet.populate)
        else:
            self.emit("load-changed", EolieLoadEvent.LOADED_CSS)

    def night_mode(self):
        """
            Handle night mode
        """
        night_mode = App().settings.get_value("night-mode")
        netloc_night_mode = App().websettings.get("night_mode", self.uri)
        if (night_mode and netloc_night_mode is not False) or\
                netloc_night_mode:
            self.run_javascript_from_gresource(
                    "/org/gnome/Eolie/javascript/GetCSS.js", None, None)
        else:
            self.__stylesheets = []
            self.get_user_content_manager().remove_all_style_sheets()

    @property
    def loading_css(self):
        """
            Get loading CSS count
            @return int
        """
        return self.__loading_css

#######################
# PROTECTED           #
#######################
    def _on_load_changed(self, webview, event):
        """
            Run JS helpers
            @param webview as WebView
            @param event as EolieLoadEvent
        """
        if event == EolieLoadEvent.STARTED:
            self.__load_finished = False
            self.set_opacity(0)
            content_manager = self.get_user_content_manager()
            content_manager.remove_all_style_sheets()
            content_manager.add_style_sheet(self.__default_stylesheet)
            self.__cancellable.cancel()
            self.__cancellable = Gio.Cancellable.new()
        elif event == EolieLoadEvent.COMMITTED:
            self.night_mode()
        elif event == EolieLoadEvent.FINISHED:
            self.__load_finished = True
            if self.__loading_css == 0:
                self.emit("load-changed", EolieLoadEvent.LOADED_CSS)
                GLib.timeout_add(250, self.set_opacity, 1)

#######################
# PRIVATE             #
#######################
    def __load_user_css(self, css):
        """
            Load CSS as user style
        """
        user_style_sheet = WebKit2.UserStyleSheet(
                     css,
                     WebKit2.UserContentInjectedFrames.ALL_FRAMES,
                     WebKit2.UserStyleLevel.USER,
                     None,
                     None)
        content_manager = self.get_user_content_manager()
        content_manager.add_style_sheet(user_style_sheet)
        if self.__loading_css == 0:
            if self.__load_finished:
                self.emit("load-changed", EolieLoadEvent.LOADED_CSS)
            GLib.timeout_add(250, self.set_opacity, 1)

    def __on_stylesheet_populated(self, stylesheet):
        """
            Load stylesheet
            @param stylesheet as StyleSheet
        """
        self.__loading_css -= 1
        css_rules = stylesheet.css_rules
        if css_rules is not None:
            self.__load_user_css(css_rules.css_text)
