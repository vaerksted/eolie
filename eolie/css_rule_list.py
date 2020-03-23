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

from eolie.css_rule_style import CSSStyleRule
from eolie.css_rule_media import CSSMediaRule
from eolie.css_rule_import import CSSImportRule
from eolie.css_rule_supports import CSSSupportsRule


class CSSRuleList:
    """
        Represent a list of rules
    """

    def __init__(self, css, uri, cancellable):
        """
            Init rule
            @param css as str
            @param uri as str
            @param cancellable as Gio.Cancellable
        """
        self.__uri = uri
        self.__rules = []
        for child in self.__get_children(css):
            child = child.strip()
            # Remove any comment
            child = re.sub("\/\*[^*]*[^/]*\*\/", "", child)
            if child.startswith("@media"):
                rule = CSSMediaRule(child, uri, cancellable)
            elif child.startswith("@supports"):
                rule = CSSSupportsRule(child, uri, cancellable)
            elif child.startswith("@import"):
                rule = CSSImportRule(child, uri, cancellable)
            elif child.startswith("@"):
                # Ignore others at-rules
                continue
            else:
                rule = CSSStyleRule(child)
            self.__rules.append(rule)

    @property
    def css_text(self):
        """
            Get css text for rules
        """
        css = [rule.css_text for rule in self.__rules]
        return "".join(css)

    @property
    def populated(self):
        """
            True if rule is populated
            @return bool
        """
        for rule in self.__rules:
            if not rule.populated:
                return False
        return True

#######################
# PRIVATE             #
#######################
    def __get_children(self, css):
        """
            Get children for css
            @param css as str
            @return [str]
        """
        children = []
        css = css.replace("\n", "").strip()
        css_split = css.split("}")
        bracket_count = 0
        children = []
        subcss = []
        while css_split:
            item = css_split.pop(0)
            for import_css in re.findall("@import[^;]*;", item):
                children.append(import_css)
                item.replace(import_css, "")
            bracket_count += item.count("{") - 1
            subcss.append(item)
            if bracket_count == 0:
                children.append("%s}" % "}".join(subcss))
                subcss = []
        return children
