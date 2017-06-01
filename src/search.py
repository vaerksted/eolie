# Copyright (c) 2017 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from gi.repository import Soup

from gettext import gettext as _

from eolie.define import El


class Search:
    """
        Eolie search engines
    """

    def __init__(self):
        """
            Init search
        """
        # Gettext does not work outside init
        self.__ENGINES = {
            'Google': [
                # Translators: Google url for your country
                _("https://www.google.com"),
                'https://www.google.com/search?q=%s&ie=utf-8&oe=utf-8',
                'https://www.google.com/complete/search?client=firefox&q=%s',
                'unicode_escape',
                'g'
                ],
            'DuckDuckGo': [
                'https://duckduckgo.com',
                'https://duckduckgo.com/?q=%s',
                'https://ac.duckduckgo.com/ac/?q=%s&type=list',
                'utf-8',
                'd'
                ],
            'Yahoo': [
                # Translators: Yahoo url for your country
                _("https://www.yahoo.com"),
                # Translators: Google url for your country
                _("https://us.search.yahoo.com") + "/search?p=%s&ei=UTF-8",
                'https://ca.search.yahoo.com/sugg/ff?'
                'command=%s&output=fxjson&appid=fd',
                'utf-8',
                'y'
                ],
            'Bing': [
                'https://www.bing.com',
                'https://www.bing.com/search?q=%s',
                'https://www.bing.com/osjson.aspx?query=%s&form=OSDJAS',
                'utf-8',
                'b'
                ]
            }

        self.__uri = ""
        self.__search = ""
        self.__keywords = ""
        self.__encoding = ""
        self.update_default_engine()

    def update_default_engine(self):
        """
            Update default engine based on user settings
        """
        wanted = El().settings.get_value('search-engine').get_string()
        for engine in self.__ENGINES:
            if engine == wanted:
                self.__uri = self.__ENGINES[engine][0]
                self.__search = self.__ENGINES[engine][1]
                self.__keywords = self.__ENGINES[engine][2]
                self.__encoding = self.__ENGINES[engine][3]
                break

    def get_search_uri(self, words):
        """
            Return search uri for words
            @param words as str
            @return str
        """
        return self.__search % words

    def get_keywords(self, words, cancellable):
        """
            Get keywords for words
            @param words as str
            @param cancellable as Gio.Cancellable
            @return [str]
        """
        try:
            uri = self.__keywords % words
            session = Soup.Session.new()
            session.set_property('accept-language-auto', True)
            request = session.request(uri)
            stream = request.send(cancellable)
            bytes = bytearray(0)
            buf = stream.read_bytes(1024, cancellable).get_data()
            while buf:
                bytes += buf
                buf = stream.read_bytes(1024, cancellable).get_data()
            stream.close()
            string = bytes.decode(self.__encoding)
            # format: '["{"words"}",["result1","result2"]]'
            keywords = string.replace('[', '').replace(']', '').split(',')[1:]
            return keywords
        except Exception as e:
            print("Search::get_keywords():", e)
            return []

    def is_search(self, string):
        """
            Return True is string is a search string
            @param string as str
            @return bool
        """
        # String contains space, not an uri
        search = string.find(" ") != -1
        if not search:
            # String contains dot, is an uri
            search = string.find(".") == -1
        return search

    @property
    def uri(self):
        """
            Search engine uri
            @return str
        """
        return self.__uri

#######################
# PRIVATE             #
#######################
