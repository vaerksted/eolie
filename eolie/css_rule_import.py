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

from urllib.parse import urlparse
import re
from os.path import dirname

from eolie.logger import Logger


class CSSImportRule:
    """
        Represent an import rule
    """

    def __init__(self, css, uri, cancellable):
        """
            Init rule
            @param css as str
            @param uri as str
            @param cancellable as Gio.Cancellable
        """
        self.__stylesheet = None
        try:
            parsed = urlparse(uri)
            search = re.search('@import url\(["\']([^"\']*)', css)
            css = search.group(1)
            if css.startswith(".."):
                path_split = parsed.path.split("/")
                css_uri = "%s://%s%s/%s" % (parsed.scheme, parsed.netloc,
                                            "/".join(path_split[:-1]), css)
            elif css.startswith("//"):
                css_uri = "%s:%s" % (parsed.scheme, css)
            elif not css.startswith("http"):
                parent = dirname(parsed.path)
                css_uri = "%s://%s%s/%s" % (
                    parsed.scheme, parsed.netloc, parent, css)
            from eolie.css_stylesheet import StyleSheet
            self.__stylesheet = StyleSheet(uri=css_uri,
                                           cancellable=cancellable)
            self.__stylesheet.populate()
        except Exception as e:
            Logger.error("CSSImportRule::__init__: %s -> %s", e, css)

    @property
    def css_text(self):
        """
            Get css text for rules
        """
        return self.__stylesheet.css_text

    @property
    def populated(self):
        """
            True if rule is populated
            @return bool
        """
        return self.__stylesheet is not None and self.__stylesheet.populated

#######################
# PRIVATE             #
#######################
