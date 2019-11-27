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
from colorsys import rgb_to_hls
from urllib.parse import urlparse
from hashlib import md5
from os.path import dirname

from eolie.helper_task import TaskHelper
from eolie.logger import Logger
from eolie.define import App, COLORS, EolieLoadEvent


class WebViewNightMode:
    """
        Night mode for webview
    """

    def __init__(self):
        """
            Init night mode
        """
        self.__loading_css = 0
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
                self.__loading_css += 1
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
            self.__apply_night_mode(css, encoded, None)

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
            self.__loaded_css = []
            self.set_opacity(0)
            self.__reset()
            self.__cancellable.cancel()
            self.__cancellable = Gio.Cancellable.new()
        elif event == EolieLoadEvent.COMMITTED:
            self.night_mode()
        elif event == EolieLoadEvent.FINISHED:
            if self.__loading_css == 0:
                self.emit("load-changed", EolieLoadEvent.LOADED_CSS)
                GLib.timeout_add(250, self.set_opacity, 1)

#######################
# PRIVATE             #
#######################
    def __get_hsla_as_float(self, value):
        """
            Convert percent str to float, keep value if no percent
            @param value as str
            @return float
        """
        if value.find("%") != -1:
            return int(value[:-1]) / 100
        return float(value)

    def __get_rgba_as_int(self, value):
        """
            Convert percent str to int, keep value if no percent
            @param value as str
            @return int
        """
        if value.find("%") != -1:
            return int(value[:-1]) * 255 / 100
        return int(value)

    def __get_deg(self, deg):
        """
            Convert deg str to int
            @param deg as str
            @return int
        """
        if deg[0].find("deg") != -1:
            return deg[0][:-3]
        return deg

    def __get_split(self, line):
        """
            Split RGBA/HSLA notation (CSS3 vs CSS4 syntax)
        """
        if "," in line:
            return line.split(",")
        else:
            # Get Opacity after /
            slash_split = line.split("/")
            # Get HSL/RGB before /
            split = slash_split[0].split(" ")
            if len(slash_split) == 1:
                # HSL/RGB + no opacity
                return split + [1]
            else:
                # HSL/RGB + A
                return split + slash_split[1]

    def __get_hex_color_from_rule(self, rule):
        """
            Get RGBA color as hexa from rule
            @param rule as str
            @return (r, g, b, a) as (int, int, int, int)
        """
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
        return None

    def __get_rgba_color_from_rule(self, rule):
        """
            Get RGBA color from rule
            @param rule str
        """
        # Extract values from rgb() and rgba()
        found = re.findall('rgb.?\(([^\)]*)', rule)
        if not found:
            return None

        split = self.__get_split(found[0])
        r = self.__get_rgba_as_int(split[0])
        g = self.__get_rgba_as_int(split[1])
        b = self.__get_rgba_as_int(split[2])
        # Indentical to hsla float calculation
        a = 1
        if len(split) == 4:
            a = self.__get_hsla_as_float(split[3])
        return (r, g, b, a)

    def __get_hsla_color_from_rule(self, rule):
        """
            Get HSLA color from rule
            @param rule str
        """
        # Extract values from hsl() and hsla()
        found = re.findall('hsl.?\(([^\)]*)', rule)
        if not found:
            return None

        split = self.__get_split(found[0])
        h = self.__get_deg(split[0])
        s = self.__get_hsla_as_float(split[1])
        l = self.__get_hsla_as_float(split[2])
        a = 1
        if len(split) == 4:
            a = self.__get_hsla_as_float(split[3])
        return (h, s, l, a)

    def __get_color_from_rule(self, rule):
        """
            Get RGBA color from rule
            @param rule as str
            @return (h, s, l, a) as (int, int, int, int)
        """
        rgba = self.__get_hex_color_from_rule(rule)
        if rgba is None:
            rgba = self.__get_rgba_color_from_rule(rule)
        if rgba is None:
            for color in COLORS.keys():
                if rule.find(color) != -1:
                    rgba = COLORS[color] + (1,)
        if rgba is None:
            hsla = self.__get_hsla_color_from_rule(rule)
        else:
            (h, l, s) = rgb_to_hls(rgba[0] / 255,
                                   rgba[1] / 255,
                                   rgba[2] / 255)
            hsla = (h, s, l, rgba[3])
        return hsla

    def __get_hsla_to_css_string(self, hsla):
        """
            Convert hsla values to CSS string
            @param hsla as (int, float, float, float)
            return str
        """
        return "hsla({}, {}%, {}%, {})".format(hsla[0] * 360,
                                               hsla[1] * 100,
                                               hsla[2] * 100,
                                               hsla[3])

    def __get_background_color_for_lightness(self, l):
        """
            Get background color for lightness
            @param l as float
            return (int, float, float, float)
        """
        return (0, 0, 0.21 + l / 100, 1)

    def __should_ignore(self, rule):
        """
            True if color should be ignored
            @param rule as str
            @return bool
        """
        values = ["inherit", "transparent",
                  "none", "unset", "currentcolor"]
        for value in values:
            if rule.find(value) != -1:
                return True
        return False

    def __should_override(self, rule):
        """
            True if color should be overrided
        """
        values = ["initial", "var(", "linear-", "radial-", "repeat", "webkit"]
        for value in values:
            if rule.find(value) != -1:
                return True
        return False

    def __handle_background_color(self, match):
        """
            Handle background color rule
            @param match as re.Match
            @return new color string as str
        """
        if match is None:
            return None
        rule = match.group(1)

        if self.__should_ignore(rule):
            return None

        # Override gradients
        if self.__should_override(rule):
            return "background-color: #353535 !important;"
        elif rule.find("url(") != -1:
            return None

        hsla = self.__get_color_from_rule(rule)
        if hsla[1] > 0.2:
            hsla = (hsla[0], hsla[1], 0.3, hsla[3])
        else:
            hsla = self.__get_background_color_for_lightness(hsla[2])
        hsla_str = self.__get_hsla_to_css_string(hsla)
        return "background-color: %s !important;" % hsla_str

    def __handle_background(self, match, background_color_set):
        """
            Handle background rule
            @param match as re.Match
            @param background_color_set as bool
            @return new color string as str
        """
        if match is None:
            return None
        rule = match.group(1)

        if self.__should_ignore(rule):
            return None

        if self.__should_override(rule) or background_color_set:
            return "background: none !important;"
        elif rule.find("url(") != -1:
            return None

        hsla = self.__get_color_from_rule(rule)
        hsla = self.__get_background_color_for_lightness(hsla[2])
        hsla_str = self.__get_hsla_to_css_string(hsla)
        return "background-color: %s !important;" % hsla_str

    def __handle_background_image(self, match, background_color_set):
        """
            Handle background image rule
            @param match as re.Match
            @param background_color_set as bool
            @return new color string as str
        """
        if match is None:
            return None
        rule = match.group(1)

        if self.__should_ignore(rule):
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
        rule = match.group(1)

        if self.__should_ignore(rule):
            return None

        if self.__should_override(rule):
            return "color: #EAEAEA !important;"

        hsla = self.__get_color_from_rule(rule)
        if hsla is None:
            return None
        hsla = self.__get_hsla_to_css_string(
                (hsla[0], hsla[1], 0.8, hsla[3]))
        return "color: %s !important;" % hsla

    def __handle_border(self, match):
        """
            Handle color rule
            @param match as re.Match
            @return new color string as str
        """
        if match is None:
            return None

        rule = match.group(1)
        (prop, values) = rule.split(":")
        hsla = self.__get_color_from_rule(values)
        if hsla is not None:
            hsla = self.__get_hsla_to_css_string(
                    (hsla[0], hsla[1], 0.3, hsla[3]))
            return "border-color: %s !important;" % hsla
        return None

    def __handle_import_rule(self, selector, uri):
        """
            Search for import rules and download them
            @param selector as str
            @param current css uri as str
            @return str
        """
        parsed = urlparse(uri)
        for css in re.findall('@import url\(["\']([^"\']*)', selector):
            if css.startswith("//"):
                css_uri = "%s:%s" % (parsed.scheme, css)
            elif not css.startswith("http"):
                parent = dirname(parsed.path)
                css_uri = "%s://%s%s/%s" % (
                    parsed.scheme, parsed.netloc, parent, css)
            self.load_css_uri("@EOLIE_CSS_URI@" + css_uri)
        return re.sub('[^*]@import[^;]*;', "", selector)

    def __apply_night_mode(self, css, encoded, uri):
        """
            Apply night mode on CSS
            @param css as str
            @param encoded as str
            @param uri as str
        """
        # Remove cariage return
        css = css.replace("\n", "")
        split = css.split("}")
        new_rules = []
        for index, rules in enumerate(split):
            try:
                # This is rule end } or any @ rule
                if rules == "" or\
                        rules.startswith("@media"):
                    new_rules.append(rules)
                    continue
                # We don't know what to do with @import for inline CSS
                if uri is not None:
                    rules = self.__handle_import_rule(rules, uri)
                search = re.search('.*{', rules)
                # This is a comment
                if search is None:
                    continue
                selector = search[0]
                color = re.search(
                    '[; {](color[ ]*:[^;]*)', rules)
                border = re.search(
                    '[; {](border[^;]*:[^;]*)', rules)
                background = re.search(
                    '[; {](background[^-: ]*:[ ]*[^;]*)', rules)
                background_color = re.search(
                    '[; {](background-color[ ]*:[^;]*)', rules)
                background_image = re.search(
                    '[; {](background-image[ ]*:[^;]*)', rules)
                if background_color is None and background is None and\
                        background_image is None and color is None:
                    continue
                selector_rules = ""
                background_color_str = self.__handle_background_color(
                    background_color)
                if background_color_str is not None:
                    selector_rules += background_color_str
                background_str = self.__handle_background(
                    background, background_color_str is not None)
                if background_str is not None:
                    selector_rules += background_str
                background_image_str = self.__handle_background_image(
                    background_image, background_color_str is not None or
                    background_str is not None)
                if background_image_str is not None:
                    selector_rules += background_image_str
                color_str = self.__handle_color(color)
                if color_str is not None:
                    selector_rules += color_str
                border_str = self.__handle_border(border)
                if border_str is not None:
                    selector_rules += border_str
                if selector_rules:
                    new_rules.append(selector + selector_rules)
            except Exception as e:
                Logger.warning(
                    "WebViewNightMode::__apply_night_mode(): %s: %s -> %s",
                    e, uri, rules)
        css = "}".join(new_rules)
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
            self.__loading_css -= 1
            if status:
                self.__apply_night_mode(contents.decode("utf-8"), encoded, uri)
        except Exception as e:
            Logger.error("WebViewNightMode::__on_load_uri_content(): %s", e)
        if self.__loading_css == 0:
            self.emit("load-changed", EolieLoadEvent.LOADED_CSS)
            GLib.timeout_add(250, self.set_opacity, 1)
