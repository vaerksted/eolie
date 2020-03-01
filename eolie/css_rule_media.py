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

import re

from eolie.logger import Logger


class CSSMediaRule:
    """
        Represent a media rule
    """

    def __init__(self, css, uri, cancellable):
        """
            Init rule
            @param css as str
            @param uri as str
            @param cancellable as Gio.Cancellable
        """
        self.__rules = None
        self.__condition = None
        try:
            # Get condition @media ... {
            search = re.search('@media ([^{]*){(.*)', css)
            if search is not None:
                from eolie.css_rule_list import CSSRuleList
                self.__condition = search.group(1)
                self.__rules = CSSRuleList(search.group(2), uri, cancellable)
        except Exception as e:
            Logger.error("CSSMediaRule::__init__(): %s -> %s", e, css)

    @property
    def css_text(self):
        """
            Get css text for rules
            @return str
        """
        if self.__rules is not None:
            css_text = self.__rules.css_text
            if css_text != "":
                return "@media %s { %s } " % (self.__condition, css_text)
        return ""

    @property
    def populated(self):
        """
            True if rule is populated
            @return bool
        """
        if self.__rules is None:
            return True
        else:
            return self.__rules.populated

#######################
# PRIVATE             #
#######################
