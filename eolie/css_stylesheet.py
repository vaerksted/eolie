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

    def __init__(self, uri=None, content=None, cancellable=None):
        """
            Init StyleSheet
            @param uri as str
            @param content as str
            @param cancellable as Gio.Cancellable
        """
        GObject.Object.__init__(self)
        if cancellable is None:
            self.__cancellable = Gio.Cancellable.new()
        else:
            self.__cancellable = cancellable
        self.__uri = uri
        self.__contents = content
        self.__css_rules = None

    def populate(self):
        """
            Populate styleheet
        """
        if self.__uri is not None:
            self.__contents = self.__get_uri_contents(self.__uri)
        if self.__contents is not None:
            self.__css_rules = CSSRuleList(self.__contents,
                                           self.__uri,
                                           self.__cancellable)
        GLib.idle_add(self.emit, "populated")

    @property
    def css_rules(self):
        """
            Get css rules
            @return CSSRuleList
        """
        return self.__css_rules

    @property
    def uri(self):
        """
            Get stylesheet URI
            @return str
        """
        return self.__uri

    @property
    def populated(self):
        """
            True if stylesheet is populated
            @return bool
        """
        return self.__css_rules is not None and self.__css_rules.populated

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
            return bytes.decode("utf-8")
        except Exception as e:
            Logger.error("StyleSheet::__get_uri_contents(): %s" % e)
        return None
