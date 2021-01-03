# Copyright (c) 2017-2021 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

import re
from colorsys import rgb_to_hls

from eolie.logger import Logger
from eolie.define import COLORS


class CSSStyleRule:
    """
        Represent a style rule
    """

    def __init__(self, css):
        """
            Init rule
            @param css as str
        """
        self.__selector = ""
        self.__variables = []
        self.__color_str = None
        self.__background_color_str = None
        self.__background_image_str = None
        self.__background_str = None
        self.__border_str = None
        self.__has_background_url = False
        # Get selectors
        search = re.search('^([^{]*){(.*)}', css)
        if search is not None:
            self.__selector = search.group(1).strip()
            declarations = search.group(2)
            self.__has_background_url = declarations.find("url(") != -1
            for declaration in declarations.split(";"):
                if declaration.find(":") == -1:
                    continue
                (prop, value) = declaration.split(":", 1)
                if not self.__contains_color(value):
                    continue
                prop = prop.strip()
                # This is a variable
                if prop.startswith("--") and value.find("var(") == -1:
                    self.__variables.append((prop, value))
                elif prop == "color":
                    self.__color_str = self.__get_clean_value(value)
                elif prop == "background-color":
                    self.__background_color_str = self.__get_clean_value(value)
                elif prop == "background-image":
                    self.__background_image_str = self.__get_clean_value(value)
                elif prop == "background":
                    self.__background_str = self.__get_clean_value(value)
                elif prop.startswith("border"):
                    self.__border_str = self.__get_clean_value(value)
            if self.__color_str is not None:
                self.__update_color()
            if self.__background_color_str is not None:
                self.__update_background_color()
            if self.__background_image_str is not None:
                self.__update_background_image()
            if self.__background_str is not None:
                self.__update_background()
            if self.__border_str is not None:
                self.__update_border_color()
            if self.__variables:
                self.__update_variables_color()

    @property
    def css_text(self):
        """
            Get css text for rules
            @return str
        """
        rules = []
        if self.__color_str is not None:
            rules.append("color: %s" % self.__color_str)
        if self.__background_color_str is not None:
            rules.append("background-color: %s" % self.__background_color_str)
        if self.__background_image_str is not None:
            rules.append("background-image: %s" % self.__background_image_str)
        if self.__background_str is not None:
            rules.append("background: %s" % self.__background_str)
        if self.__border_str is not None:
            rules.append("border-color: %s" % self.__border_str)
        for (prop, value) in self.__variables:
            rules.append("%s : %s" % (prop, value))
        if rules:
            css_text = "%s{ %s } " % (self.__selector, ";".join(rules))
            if self.__has_background_url:
                css_text += """%s > *
                    {text-shadow: 0px 0px 5px black
                    !important}""" % self.__selector
            return css_text
        else:
            return ""

    @property
    def populated(self):
        """
            True if rule is populated
            @return bool
        """
        return True

#######################
# PRIVATE             #
#######################
    def __get_clean_value(self, value):
        """
            Remove unwanted parts from value
            @param value as str
            @return str
        """
        value = re.sub('[ ]*!.*important', '', value)
        value = re.sub('url.*\([^\)]*\)', 'url()', value)
        return value.strip()

    def __contains_color(self, value):
        """
            True if value contains a color
            @param value as str
            @return bool
        """
        ignores = ["inherit", "transparent", "data:",
                   "unset", "currentcolor"]
        for ignore in ignores:
            if value.find(ignore) != -1:
                return False
        # Check hsl/rgb/# colors
        if value.find("hsl") != -1 or\
                value.find("rgb") != -1 or\
                value.find("#") != -1:
            return True
        # Check named colors
        else:
            for color in COLORS.keys():
                if value.find(color) != -1:
                    return True
        return False

    def __get_hsla_as_float(self, value):
        """
            Convert percent str to float, keep value if no percent
            @param value as str
            @return float
        """
        if value.find("%") != -1:
            return float(value[:-1]) / 100
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

    def __get_hex_colors_from_rule(self, rule):
        """
            Get RGBA colors as hexa from rule
            @param rule as str
            @return {"hex_color": (int, int, int, int)}
        """
        results = {}
        # Extract values from hexadecimal notation
        colors = re.findall(
            '(#[0-9A-Fa-f]{8}|#[0-9A-Fa-f]{6}|#[0-9A-Fa-f]{3})', rule)
        for color in colors:
            hexa = color[1:]
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
            results[color] = (rgb + (a,))
        return results

    def __get_rgba_colors_from_rule(self, rule):
        """
            Get RGBA colors from rule
            @param rule str
            @return {"rgba_color": (int, int, int, int)}
        """
        results = {}
        # Extract values from rgb() and rgba()
        colors = re.findall('(rgb.?\([^\)]*\))', rule)
        for color in colors:
            color_tuple = re.search('rgb.?\(([^\)]*)', color)
            if color_tuple is None:
                continue
            split = self.__get_split(color_tuple[1])
            r = self.__get_rgba_as_int(split[0])
            g = self.__get_rgba_as_int(split[1])
            b = self.__get_rgba_as_int(split[2])
            # Indentical to hsla float calculation
            a = 1
            if len(split) == 4:
                a = self.__get_hsla_as_float(split[3])
            results[color] = (r, g, b, a)
        return results

    def __get_hsla_colors_from_rule(self, rule):
        """
            Get HSLA colors from rule
            @return {"hsla_color": (int, float, float, float)}
        """
        results = {}
        # Extract values from hsl() and hsla()
        colors = re.findall('(hsl.?\([^\)]*\))', rule)
        for color in colors:
            color_tuple = re.search('hsl.?\(([^\)]*)', color)
            if color_tuple is None:
                continue
            split = self.__get_split(color_tuple[1])
            h = self.__get_deg(split[0])
            s = self.__get_hsla_as_float(split[1])
            l = self.__get_hsla_as_float(split[2])
            a = 1
            if len(split) == 4:
                a = self.__get_hsla_as_float(split[3])
            results[color] = (h, s, l, a)
        return results

    def __get_colors_from_rule(self, rule):
        """
            Get RGBA colors from rule
            @param rule as str
            @return [(h, s, l, a)] as [(int, float, float, float)]
        """
        hex_colors = self.__get_hex_colors_from_rule(rule)
        rgba_colors = self.__get_rgba_colors_from_rule(rule)
        named_colors = {}
        for color in COLORS.keys():
            if rule.find(color) != -1:
                named_colors[color] = COLORS[color] + (1,)
        colors = {**hex_colors, **rgba_colors, **named_colors}
        for key in colors.keys():
            rgba = colors[key]
            (h, l, s) = rgb_to_hls(rgba[0] / 255,
                                   rgba[1] / 255,
                                   rgba[2] / 255)
            colors[key] = (h, s, l, rgba[3])
        hsla_colors = self.__get_hsla_colors_from_rule(rule)
        return {**colors, **hsla_colors}

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

    def __update_background_color(self):
        """
            Update background color for night mode
        """
        try:
            colors = self.__get_colors_from_rule(self.__background_color_str)
            if not colors:
                return None
            for key in colors.keys():
                hsla = colors[key]
                if hsla[3] < 0.4:
                    continue
                elif hsla[1] > 0.2:
                    if hsla[2] > 0.7:
                        hsla = (hsla[0], hsla[1], 0.1, hsla[3])
                    else:
                        hsla = (hsla[0], hsla[1], 0.3, hsla[3])
                else:
                    hsla = (0, 0, 0.21, 1)
                hsla_str = self.__get_hsla_to_css_string(hsla)
                self.__background_color_str =\
                    self.__background_color_str.replace(
                        key, hsla_str)
            self.__background_color_str += " !important;"
        except Exception as e:
            Logger.warning("CSSStyleRule::__update_background_color(): %s", e)
            self.__background_color_str = "#353535 !important;"

    def __update_background_image(self):
        """
            Update background image for night mode
        """
        try:
            colors = self.__get_colors_from_rule(self.__background_image_str)
            if not colors:
                return None
            for key in colors.keys():
                hsla = colors[key]
                if hsla[3] < 0.4:
                    continue
                elif hsla[1] > 0.2:
                    if hsla[2] > 0.7:
                        hsla = (hsla[0], hsla[1], 0.1, hsla[3])
                    else:
                        hsla = (hsla[0], hsla[1], 0.3, hsla[3])
                else:
                    hsla = (0, 0, 0.21, 1)
                hsla_str = self.__get_hsla_to_css_string(hsla)
                self.__background_image_str =\
                    self.__background_image_str.replace(
                        key, hsla_str)
            self.__background_image_str += " !important;"
        except Exception as e:
            Logger.warning("CSSStyleRule::__update_background_image(): %s", e)
            self.__background_image_str = "#353535 !important;"

    def __update_background(self):
        """
            Update background for night mode
        """
        try:
            colors = self.__get_colors_from_rule(self.__background_str)
            if not colors:
                return None
            for key in colors.keys():
                hsla = colors[key]
                if hsla[3] < 0.4:
                    continue
                hsla = (0, 0, 0.21, 1)
                hsla_str = self.__get_hsla_to_css_string(hsla)
                self.__background_str =\
                    self.__background_str.replace(
                        key, hsla_str)
            self.__background_str += " !important;"
        except Exception as e:
            Logger.warning("CSSStyleRule::__update_background(): %s", e)
            self.__background_str = "#353535 !important;"

    def __update_color(self):
        """
            Update color for night mode
        """
        try:
            colors = self.__get_colors_from_rule(self.__color_str)
            if not colors:
                return None
            for key in colors.keys():
                hsla = colors[key]
                hsla_str = self.__get_hsla_to_css_string(
                    (hsla[0], hsla[1], 0.8, hsla[3]))
                self.__color_str =\
                    self.__color_str.replace(
                        key, hsla_str)
            self.__color_str += " !important;"
        except Exception as e:
            Logger.warning("CSSStyleRule::__update_color(): %s", e)
            self.__color_str = "#EAEAEA !important;"

    def __update_border_color(self):
        """
            Update border color for night mode
        """
        try:
            colors = self.__get_colors_from_rule(self.__border_str)
            if not colors:
                return None
            for key in colors.keys():
                hsla = colors[key]
                hsla_str = self.__get_hsla_to_css_string(
                        (hsla[0], hsla[1], 0.3, hsla[3]))
                self.__border_str =\
                    self.__border_str.replace(
                        key, hsla_str)
            self.__border_str += " !important;"
        except Exception as e:
            Logger.warning("CSSStyleRule::__update_border_color(): %s", e)
            self.__border_str = "#EAEAEA !important;"

    def __update_variables_color(self):
        """
            Update variables color for night mode
        """
        variables = []
        for (prop, value) in self.__variables:
            try:
                colors = self.__get_colors_from_rule(value)
                if not colors:
                    continue
                for key in colors.keys():
                    hsla = colors[key]
                    if hsla[2] > 0.75:
                        hsla_str = self.__get_hsla_to_css_string(
                                (0, 0, 0.21, hsla[3]))
                    elif hsla[2] > 0.5:
                        hsla_str = self.__get_hsla_to_css_string(
                            (0, 0, 1 - hsla[2], hsla[3]))
                    else:
                        hsla_str = self.__get_hsla_to_css_string(
                            (hsla[0], hsla[1], 0.5 + hsla[2], hsla[3]))
                    value = value.replace(key, hsla_str)
            except Exception as e:
                Logger.warning(
                    "CSSStyleRule::__update_variables_color(): %s", e)
            variables.append((prop, "%s !important;" % value))
        self.__variables = variables
