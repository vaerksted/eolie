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
from eolie.define import App, COLORS


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
                self.__load_user_css(self.__cached_css[encoded])
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
        else:
            self.__loaded_css = []
            self.get_user_content_manager().remove_all_style_sheets()

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
    def __get_color_from_rule(self, rule):
        """
            Get RGBA color from rule
            @param rule as str containing #FFFFFFFF or rgb() or rgba ()
            @return (r, g, b, a) as (int, int, int, int)
        """
        # Extract values from rgb() and rgba()
        found = re.findall('rgb.?\(([^\)]*)', rule)
        if found:
            values = found[0].split(",")
            rgb = ()
            for i in (0, 1, 2):
                value = values[i]
                if value.find("%") != -1:
                    rgb += (int(int(value[:-1]) / 100 * 255),)
                else:
                    rgb += (int(value),)
            a = 1
            if len(values) == 4:
                a = float(values[3])
            return rgb + (a,)
        # Extract values from hexadecimal notation
        found = re.search('#([0-9A-Fa-f]{8}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})',
                          rule)
        if found is not None:
            hexa = found[0][1:]
            a = 1
            # Translate short version of hexa string
            if len(hexa) == 3:
                _hexa = ""
                for letter in hexa:
                    _hexa += letter + letter
                hexa = _hexa
            rgb = tuple(int(hexa[i:i+2], 16) for i in (0, 2, 4))
            if len(hexa) == 8:
                a = round(255 / int(hexa[6, 8], 16))
            return rgb + (a,)
        # Extract values from named colors, not very good has only
        # handling color only values
        for color in COLORS.keys():
            if rule.find(color) != -1:
                return COLORS[color]
        return None

    def __should_ignore_color(self, rule):
        """
            True if color should be ignored
            @param rule as str
            @return bool
        """
        values = ["inherit", "transparent", "none", "unset", "currentcolor"]
        for value in values:
            if rule.find(value) != -1:
                return True
        return False

    def __should_override(self, rule):
        """
            True if color should be overrided
        """
        values = ["initial", "var(", "linear-", "radial-", "-"]
        for value in values:
            if rule.startswith(value):
                return True
        return False

    def __is_greyscale_color(self, rgb):
        """
            True if RGB color is grayscale
            @param rgb (int, int, int)
            @return bool
        """
        rgb_ratio1 = (rgb[0] + 0.1) / (rgb[1] + 0.1)
        rgb_ratio2 = (rgb[1] + 0.1) / (rgb[2] + 0.1)
        greyscale = rgb_ratio1 > 0.8 and\
            rgb_ratio1 < 1.2 and\
            rgb_ratio2 > 0.8 and\
            rgb_ratio2 < 1.2
        return greyscale

    def __is_dark_color(self, rgb):
        """
            True if RGB color is dark
            @param rgb as (int, int, int)
            @return bool
        """
        # http://www.w3.org/TR/AERT#color-contrast
        brightness = (rgb[0] * 299 + rgb[1] * 587 + rgb[2] * 114) / 1000
        return brightness < 100

    def __set_color_brightness(self, rgb, diff):
        """
            Set color brightness value +/- diff
            @param rgb as (int, int, int) + optional a (int,)
            @return rgb as (int, int, int) + optional a (int,)
        """
        new_rgb = (min(255, max(0, rgb[0] + diff)),
                   min(255, max(0, rgb[1] + diff)),
                   min(255, max(0, rgb[2] + diff)))
        if len(rgb) == 4:
            new_rgb += (rgb[3],)
        return new_rgb

    def __handle_background_color(self, match):
        """
            Handle background color rule
            @param match as re.Match
            @return new color string as str
        """
        if match is None:
            return None

        rule = match[0]

        if self.__should_ignore_color(rule):
            return None

        # Override gradients
        if self.__should_override(rule):
            return "background-color: #353535 !important;"

        rgba = self.__get_color_from_rule(rule)
        if self.__is_greyscale_color(rgba) or\
                self.__is_dark_color(rgba):
            return "background-color: #353535 !important;"

        rgba = self.__set_color_brightness(rgba, -50)
        return "background-color: rgba%s !important;" % str(rgba)

    def __handle_background(self, match, background_color_set):
        """
            Handle background rule
            @param match as re.Match
            @param background_color_set as bool
            @return new color string as str
        """
        if match is None:
            return None

        rule = match[0]
        if self.__should_ignore_color(rule):
            return None

        if self.__should_override(rule) or background_color_set:
            return "background: none !important;"
        elif rule.find("url(") != -1:
            return None

        rgba = self.__get_color_from_rule(rule)

        if self.__is_greyscale_color(rgba) or\
                self.__is_dark_color(rgba):
            return "background: #353535 !important;"

        rgba = self.__set_color_brightness(rgba, -50)
        return "background: rgba%s !important;" % str(rgba)

    def __handle_background_image(self, match, background_color_set):
        """
            Handle background image rule
            @param match as re.Match
            @param background_color_set as bool
            @return new color string as str
        """
        if match is None:
            return None

        rule = match[0]
        if self.__should_ignore_color(rule):
            return None

        if self.__should_override(rule) or background_color_set:
            return "background-image: none !important;"
        return None

    def __handle_color(self, match):
        """
            Handle color rule
            @param match as re.Match
            @return new color string as str
        """
        if match is None:
            return None

        rule = match[0]

        if self.__should_ignore_color(rule):
            return None

        if self.__should_override(rule):
            return "color: #EAEAEA !important;"

        rgba = self.__get_color_from_rule(rule)
        if rgba is None:
            return None
        elif self.__is_greyscale_color(rgba):
            return "color: #EAEAEA !important;"
        else:
            rgba = self.__set_color_brightness(rgba, 127)
            return "color: rgba%s !important;" % str(rgba)

    def __apply_night_mode(self, css, encoded):
        """
            Apply night mode on CSS
            @param css as str
            @param encoded as str
        """
        split = css.replace("\n", "").split("}")
        for index, rules in enumerate(split):
            error = None
            try:
                if rules == "":
                    continue
                color = re.search('[^-^a-z^A-Z]color[ ]*:[^;]*', rules)
                background = re.search('background[^-: ]*:[ ]*[^;]*', rules)
                background_color = re.search('background-color[ ]*:[^;]*',
                                             rules)
                background_image = re.search('background-image[ ]*:[^;]*',
                                             rules)
                if background_color is None and background is None and\
                        background_image is None and color is None:
                    split[index] = None
                    continue

                new_rules = re.search('.*{', rules)[0]
                error = "background-color"
                background_color_str = self.__handle_background_color(
                    background_color)
                if background_color_str is not None:
                    new_rules += background_color_str
                error = "background"
                background_str = self.__handle_background(
                    background, background_color_str is not None)
                if background_str is not None:
                    new_rules += background_str
                error = "background-image"
                background_image_str = self.__handle_background_image(
                    background_image, background_color_str is not None)
                if background_image_str is not None:
                    new_rules += background_image_str
                error = "color"
                color_str = self.__handle_color(color)
                if color_str is not None:
                    new_rules += color_str
                split[index] = new_rules
            except Exception as e:
                Logger.warning(
                    "WebViewNightMode::__apply_night_mode(): %s: %s", e, error)
        css = "}".join([v for v in split if v is not None])
        if encoded is not None:
            self.__cached_css[encoded] = css
        self.__load_user_css(css)

    def __reset(self):
        """
            Add default CSS rule
        """
        content_manager = self.get_user_content_manager()
        content_manager.remove_all_style_sheets()
        user_style_sheet = WebKit2.UserStyleSheet(
                     "body {\
                        color: #EAEAEA !important;\
                        background-color: #353535 !important\
                      }\
                      * {\
                        border-color: #454545 !important\
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
        content_manager.add_style_sheet(user_style_sheet)

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
        except Exception as e:
            Logger.error("WebViewNightMode::__on_load_uri_content(): %s", e)
        if self.__loading_uris == 0:
            GLib.timeout_add(250, self.set_opacity, 1)
