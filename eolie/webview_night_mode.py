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

import re
from hashlib import md5

from eolie.helper_task import TaskHelper
from eolie.logger import Logger
from eolie.define import App


class WebViewNightMode:
    """
        Night mode for webview
    """

    def __init__(self):
        """
            Init night mode
        """
        self.__loading_uris = 0
        self.__loaded_css = []
        self.__cached_css = {}
        self.__task_helper = TaskHelper()
        self.__cancellable = Gio.Cancellable.new()

    def load_css_uri(self, message):
        """
            Load CSS URI as user style
            @param message as str
        """
        uri = message.replace("@EOLIE_CSS_URI@", "")
        encoded = md5(uri.encode("utf-8")).hexdigest()
        if encoded not in self.__loaded_css:
            if encoded in self.__cached_css.keys():
                print("cache")
                self.__apply_night_mode(self.__cached_css[encoded], None)
            else:
                self.__loading_uris += 1
                self.__loaded_css.append(encoded)
                self.__task_helper.load_uri_content(uri, self.__cancellable,
                                                    self.__on_load_uri_content,
                                                    encoded)

    def load_css_text(self, message):
        """
            Load CSS text as user style
        """
        css = message.replace("@EOLIE_CSS_TEXT@", "")
        encoded = md5(css.encode("utf-8")).hexdigest()
        if encoded not in self.__loaded_css:
            self.__loaded_css.append(encoded)
            self.__apply_night_mode(css, encoded)

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

#######################
# PROTECTED           #
#######################
    def _on_load_changed(self, webview, event):
        """
            Run JS helpers
            @param webview as WebView
            @param event as WebKit2.LoadEvent
        """
        if event == WebKit2.LoadEvent.STARTED:
            self.__loaded_css = []
            self.set_opacity(0)
            self.__reset()
            self.__cancellable.cancel()
            self.__cancellable = Gio.Cancellable.new()
        elif event == WebKit2.LoadEvent.COMMITTED:
            self.night_mode()
        elif event == WebKit2.LoadEvent.FINISHED:
            if self.__loading_uris == 0:
                GLib.timeout_add(250, self.set_opacity, 1)

#######################
# PRIVATE             #
#######################
    def __reset(self):
        """
            Add default CSS rule
        """
        App().content_manager.remove_all_style_sheets()
        user_style_sheet = WebKit2.UserStyleSheet(
                     "body {\
                        color: #EAEAEA !important;\
                        background-color: #353535 !important\
                      }\
                      * {\
                        border-color: #555555 !important\
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
        App().content_manager.add_style_sheet(user_style_sheet)

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
        App().content_manager.add_style_sheet(user_style_sheet)

    def __apply_night_mode(self, css, encoded):
        """
            Apply night mode on CSS
            @param css as str
            @param encoded as str
        """
        split = css.replace("\n", "").split("}")
        for index, rules in enumerate(split):
            if rules == "":
                continue
            color = re.search('[^-]color[ ]*:[^;]*;', rules)
            background = re.search('background[^- ]*:[^;]*;', rules)
            background_color = re.search('background-color[ ]*:[^;]*;',
                                         rules)
            background_image = re.search('background-image[ ]*:[^;]*;',
                                         rules)
            if background_color is None and background is None and\
                    background_image is None and color is None:
                split[index] = None
                continue
            new_rules = re.search('.*{', rules)[0]
            if background_color is not None:
                new_rules += "background-color: #353535 !important;"
            if background is not None:
                new_rules += "background: #353535 !important;"
            if background_image is not None:
                new_rules += "background-image: none !important;"
            if color is not None:
                new_rules += "color: #EAEAEA !important;"
            split[index] = new_rules
        css = "}".join([v for v in split if v is not None])
        if encoded is not None:
            self.__cached_css[encoded] = css
        self.__load_user_css(css)

    def __on_load_uri_content(self, uri, status, contents, encoded):
        """
            Inject CSS in page
            @param uri as str
            @param status as bool
            @param content as bytes
            @param encoded as str
        """
        try:
            self.__loading_uris -= 1
            if status:
                self.__apply_night_mode(contents.decode("utf-8"), encoded)
            if self.__loading_uris == 0:
                GLib.timeout_add(250, self.set_opacity, 1)
        except Exception as e:
            Logger.error("WebViewNightMode::__on_load_uri_content(): %s", e)
