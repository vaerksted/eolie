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
        self.__color_str = None
        self.__background_color_str = None
        self.__background_image_str = None
        self.__background_str = None
        self.__border_str = None
        # Get selectors
        search = search = re.search('^([^{]*){(.*)}', css)
        if search is not None:
            self.__selector = search.group(1).strip()
            declarations = search.group(2)
            for declaration in declarations.split(";"):
                if declaration.find(":") == -1:
                    continue
                (prop, value) = declaration.split(":", 1)
                prop = prop.strip()
                if prop == "color":
                    self.__color_str = value.strip()
                elif prop == "background-color":
                    self.__background_color_str = value.strip()
                elif prop == "background":
                    self.__background_str = value.strip()
                elif prop == "background-image":
                    self.__background_image_str = value.strip()
                elif prop.startswith("border"):
                    self.__border_str = value.strip()
            background_set = False
            if self.__color_str is not None:
                self.__update_color()
            if self.__background_color_str is not None:
                background_set = self.__update_background_color()
            if self.__background_str is not None:
                background_set = self.__update_background(background_set)
            if self.__background_image_str is not None:
                self.__update_background_image(background_set)
            if self.__border_str is not None:
                self.__update_border_color()

    @property
    def css_text(self):
        """
            Get css text for rules
            @return str
        """
        text = ""
        if self.__color_str is not None:
            text += "color: %s;" % self.__color_str
        if self.__background_color_str is not None:
            text += "background-color: %s;" % self.__background_color_str
        if self.__background_image_str is not None:
            text += "background-image: %s;" % self.__background_image_str
        if self.__background_str is not None:
            text += "background: %s;" % self.__background_str
        if self.__border_str is not None:
            text += "border-color: %s;" % self.__border_str
        if text:
            return "%s{ %s } " % (self.__selector, text)
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
        values = ["inherit", "transparent", "data:", "url",
                  "none", "unset", "currentcolor"]
        for value in values:
            if rule.find(value) != -1:
                return True
        return False

    def __should_override(self, rule):
        """
            True if color should be overrided
        """
        values = ["initial", "var(", "gradient", "webkit"]
        for value in values:
            if rule.find(value) != -1:
                return True
        return False

    def __update_background_color(self):
        """
            Update background color for night mode
            @return background_set as bool
        """
        try:
            should_override = self.__should_override(
                self.__background_color_str)
            if not should_override and\
                    self.__should_ignore(self.__background_color_str):
                self.__background_color_str = None
                return False
            elif should_override:
                self.__background_color_str = "#353535 !important"
                return True
            else:
                hsla = self.__get_color_from_rule(self.__background_color_str)
                if hsla[1] > 0.4:
                    hsla = (hsla[0], hsla[1], 0.1, hsla[3])
                else:
                    hsla = self.__get_background_color_for_lightness(hsla[2])
                hsla_str = self.__get_hsla_to_css_string(hsla)
                self.__background_color_str = "%s !important" % hsla_str
                return True
        except Exception as e:
            Logger.warning("CSSStyleRule::__update_background_color(): %s", e)
            self.__background_color_str = "#353535 !important"
            return True

    def __update_background(self, background_set):
        """
            Update background for night mode
            @param background_set as bool
            @return background_set as bool
        """
        try:
            should_override = self.__should_override(self.__background_str)
            if not should_override and self.__should_ignore(
                    self.__background_str):
                self.__background_str = None
                return False
            elif should_override or background_set:
                self.__background_str = "none !important"
                return True
            else:
                hsla = self.__get_color_from_rule(self.__background_str)
                hsla = self.__get_background_color_for_lightness(hsla[2])
                hsla_str = self.__get_hsla_to_css_string(hsla)
                self.__background_str = "%s !important" % hsla_str
                return True
        except Exception as e:
            Logger.warning("CSSStyleRule::__update_background(): %s", e)
            self.__background_str = "#353535 !important"
            return True

    def __update_background_image(self, background_set):
        """
            Update background-image for night mode
            @param background_set as bool
        """
        try:
            should_override = self.__should_override(
                self.__background_image_str)
            if not should_override and\
                    self.__should_ignore(self.__background_image_str):
                self.__background_image_str = None
            elif should_override or background_set:
                self.__background_image_str = "none !important"
        except Exception as e:
            Logger.warning("CSSStyleRule::__update_background_image(): %s", e)
            self.__background_image_str = "#353535 !important"

    def __update_color(self):
        """
            Update color for night mode
        """
        try:
            if self.__should_ignore(self.__color_str):
                self.__color_str = None
            elif self.__should_override(self.__color_str):
                self.__color_str = "#EAEAEA !important"
            else:
                hsla = self.__get_color_from_rule(self.__color_str)
                if hsla is None:
                    self.__color_str = None
                else:
                    hsla = self.__get_hsla_to_css_string(
                            (hsla[0], hsla[1], 0.8, hsla[3]))
                    self.__color_str = "%s !important" % hsla
        except Exception as e:
            Logger.warning("CSSStyleRule::__update_color(): %s", e)
            self.__color_str = "#EAEAEA !important"

    def __update_border_color(self):
        """
            Update border color for night mode
        """
        try:
            hsla = self.__get_color_from_rule(self.__border_str)
            if hsla is not None:
                hsla = self.__get_hsla_to_css_string(
                        (hsla[0], hsla[1], 0.3, hsla[3]))
                self.__border_str = "%s !important" % hsla
            else:
                self.__border_str = None
        except Exception as e:
            Logger.warning("CSSStyleRule::__update_border_color(): %s", e)
            self.__border_str = None
