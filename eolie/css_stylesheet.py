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

from gi.repository import Gio, GObject, GLib, Soup

from eolie.css_rule_list import CSSRuleList
from eolie.logger import Logger


class StyleSheet(GObject.Object):
    """
        Represent a stylesheet
    """

    __gsignals__ = {
        "populated": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, uri=None, contents=None, cancellable=None):
        """
            Init StyleSheet
            @param uri as str
            @param contents as str
            @param cancellable as Gio.Cancellable
        """
        GObject.Object.__init__(self)
        if cancellable is None:
            self.__cancellable = Gio.Cancellable.new()
        else:
            self.__cancellable = cancellable
        self.__uri = uri
        self.__contents = contents
        self.__css_rules = None
        self.__css_text = None
        self.__started_time = 0

    def populate(self):
        """
            Populate styleheet
        """
        if self.__uri is not None and self.__contents is None:
            self.__contents = self.__get_uri_contents(self.__uri)
        if self.__contents is not None:
            self.__css_rules = CSSRuleList(self.__contents,
                                           self.__uri,
                                           self.__cancellable)
        GLib.idle_add(self.emit, "populated")

    def set_css_text(self, css_text):
        """
            Set css text
            @param css_text as str
        """
        self.__css_text = css_text

    def set_started_time(self, started_time):
        """
            Set started time
            @param started time as int
        """
        self.__started_time = started_time

    @property
    def started_time(self):
        """
            Get started time
            @return int
        """
        return self.__started_time

    @property
    def css_text(self):
        """
            Get css text
            @return str
        """
        if self.__css_text is not None:
            return self.__css_text
        elif self.__css_rules is not None:
            self.__css_text = self.__css_rules.css_text
            return self.__css_text
        return ""

    @property
    def uri(self):
        """
            Get stylesheet URI
            @return str
        """
        return self.__uri

    @property
    def contents(self):
        """
            Get contents
            @return str
        """
        return self.__contents

    @property
    def populated(self):
        """
            True if stylesheet is populated
            @return bool
        """
        return self.__css_text is not None or (
            self.__css_rules is not None and self.__css_rules.populated)

#######################
# PRIVATE             #
#######################
    def __get_uri_contents(self, uri):
        """
            Get URI content
            @param uri as str
            @return str
        """
        try:
            session = Soup.Session.new()
            request = session.request(uri)
            stream = request.send(self.__cancellable)
            bytes = bytearray(0)
            buf = stream.read_bytes(1024, self.__cancellable).get_data()
            while buf:
                bytes += buf
                buf = stream.read_bytes(1024, self.__cancellable).get_data()
            stream.close()
            try:
                return bytes.decode("utf-8")
            except:
                return bytes.decode("iso8859-1")
        except Exception as e:
            Logger.error("StyleSheet::__get_uri_contents(): %s -> %s" %
                         (e, uri))
        return None
