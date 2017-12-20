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

from gi.repository import Gio, GLib

from gettext import gettext as _
from urllib.parse import urlparse
import json

from eolie.helper_task import TaskHelper
from eolie.define import El, EOLIE_DATA_PATH


class Search:
    """
        Eolie search engines
    """

    def __init__(self, user_agent):
        """
            Init search
            @param user_agent as str
        """
        self.__user_agent = user_agent
        # Gettext does not work outside init
        self.__ENGINES = {
            'Google': [
                # Translators: Google url for your country
                _("https://www.google.com"),
                _("https://www.google.com") + '/search?q=%s&ie=utf-8&oe=utf-8',
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
            'Qwant': [
                'https://www.qwant.com',
                'https://www.qwant.com/?q=%s',
                'https://api.qwant.com/api/suggest/?q=%s&client=opensearch',
                'utf-8',
                'q'
                ],
            'Yahoo': [
                # Translators: Yahoo url for your country
                _("https://www.yahoo.com"),
                # Translators: Yahoo url for your country
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

        self.__engines = {}
        self.__uri = ""
        self.__search = ""
        self.__suggest = ""
        self.__encoding = ""
        self.update_default_engine()

    def save_engines(self, engines):
        """
            Save engines
            @param engines as {}
        """
        self.__engines = engines
        try:
            content = json.dumps(engines)
            f = Gio.File.new_for_path(EOLIE_DATA_PATH + "/search_engines.json")
            f.replace_contents(content.encode("utf-8"),
                               None,
                               False,
                               Gio.FileCreateFlags.REPLACE_DESTINATION,
                               None)
        except Exception as e:
            print("Search::save_engines():", e)

    def update_default_engine(self):
        """
            Update default engine based on user settings
        """
        wanted = El().settings.get_value('search-engine').get_string()
        for engine in self.engines:
            if engine == wanted:
                self.__uri = self.engines[engine][0]
                self.__search = self.engines[engine][1]
                self.__suggest = self.engines[engine][2]
                self.__encoding = self.engines[engine][3]
                break

    def get_search_uri(self, words):
        """
            Return search uri for words
            @param words as str
            @return str
        """
        if len(words) > 2 and words[1] == ":":
            for engine in self.engines:
                if words.startswith("%s:" % self.engines[engine][4]):
                    return self.engines[engine][1] % words[2:]
        try:
            return self.__search % words
        except:
            return self.engines["Google"][1] % words

    def search_suggestions(self, value, cancellable, callback):
        """
            Search suggestions for value
            @param value as str
            @param cancellable as Gio.Cancellable
            @param callback as str
        """
        try:
            if not value.strip(" "):
                return
            uri = self.__suggest % GLib.uri_escape_string(value,
                                                          None,
                                                          True)
            task_helper = TaskHelper(self.__user_agent)
            task_helper.load_uri_content(uri, cancellable,
                                         callback, self.__encoding, value)
        except Exception as e:
            print("Search::search_suggestions():", e)

    def install_engine(self, uri, window):
        """
            Install new search engine
            @param uri as str
            @param window as Window
        """
        self.__install_engine(uri, window)

    def is_search(self, string):
        """
            Return True is string is a search string
            @param string as str
            @return bool
        """
        # String contains space, not an uri
        search = string.find(" ") != -1 or\
            (len(string) > 2 and string[1] == ":")
        if not search:
            # String contains dot, is an uri
            search = string.find(".") == -1 and\
                string.find(":") == -1
        return search

    @property
    def engines(self):
        """
            Get engines
            return {}
        """
        if not self.__engines:
            # Load user engines
            try:
                f = Gio.File.new_for_path(EOLIE_DATA_PATH +
                                          "/search_engines.json")
                if f.query_exists():
                    (status, contents, tag) = f.load_contents(None)
                    self.__engines.update(json.loads(contents.decode("utf-8")))
            except Exception as e:
                print("Search::engines():", e)
            if not self.__engines:
                self.__engines = self.__ENGINES
        return self.__engines

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
    def __install_engine(self, uri, window):
        """
            Install engine from uri
            @param uri as str
            @param window as Window
        """
        task_helper = TaskHelper(self.__user_agent)
        task_helper.load_uri_content(uri, None,
                                     self.__on_engine_loaded,
                                     window)

    def __on_engine_loaded(self, uri, status, content, window):
        """
            Ask user to add engine
            @param uri as str
            @param content as bytes
            @param window as Window
        """
        SHORTNAME = "{http://a9.com/-/spec/opensearch/1.1/}ShortName"
        URL = "{http://a9.com/-/spec/opensearch/1.1/}Url"
        ENCODING = "{http://a9.com/-/spec/opensearch/1.1/}InputEncoding"
        HTML = "text/html"
        JSON = "application/x-suggestions+json"
        try:
            from eolie.popover_message import MessagePopover
            import xml.etree.ElementTree as xml
            root = xml.fromstring(content)
            name = None
            search = None
            suggest = None
            encoding = "utf-8"
            for child in root.iter():
                if child.tag == SHORTNAME:
                    name = child.text
                elif child.tag == URL:
                    if child.attrib["type"] == HTML:
                        if child.attrib["method"] == "get":
                            search = child.attrib["template"]
                    elif child.attrib["type"] == JSON:
                        suggest = child.attrib["template"]
                elif child.tag == ENCODING:
                    encoding = child.text
            if name is not None and search is not None:
                message = _("Do you want to install\n"
                            "%s search engine ?") % name
                callback = self.__on_message_popover_ok
            else:
                message = _("Unsupported search engine")
                callback = None
            popover = MessagePopover(message, window,
                                     callback,
                                     name,
                                     search,
                                     suggest or "",
                                     encoding)
            popover.set_relative_to(window.toolbar.title)
            popover.popup()
        except Exception as e:
            print("Search::__on_engine_loaded()", e)

    def __on_message_popover_ok(self, name, search, suggest, encoding):
        """
            Save engine
            @param name as str
            @param uri as str
            @param suggest_uri as str
            @param encoding as str
        """
        # Save engines
        engines = El().search.engines
        parsed = urlparse(search)
        uri = "%s://%s" % (parsed.scheme, parsed.netloc)
        engines[name] = [uri,
                         search.replace("{searchTerms}", "%s"),
                         suggest.replace("{searchTerms}", "%s"),
                         encoding,
                         ""]
        El().search.save_engines(engines)
