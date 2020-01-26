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

from gi.repository import GLib

from urllib.parse import urlparse

from eolie.define import Type, App, Score
from eolie.popover_uri_item import Item
from eolie.popover_uri_row import Row


class UriPopoverSuggestions:
    """
        Suggestions handler for UriPopover
    """

    def __init__(self):
        """
            Init handler
        """
        self.__suggestion_id = None

    def add_suggestions(self, value, cancellable):
        """
            Add suggestions for value
            @param value as str
            @param cancellable as Gio.Cancellable
        """
        parsed = urlparse(value)
        is_uri = parsed.scheme in ["about, http", "file", "https", "populars"]
        # Remove any pending suggestion search
        if self.__suggestion_id is not None:
            GLib.source_remove(self.__suggestion_id)
            self.__suggestion_id = None
        # Search for suggestions if needed
        if App().settings.get_value("enable-suggestions") and not is_uri:
            self.__suggestion_id = GLib.timeout_add(
                100,
                self.__on_suggestion_timeout,
                value,
                cancellable)

#######################
# PRIVATE             #
#######################
    def __add_suggestions(self, suggestions):
        """
            Add suggestions to popover
            @param suggestions as [str]
        """
        for suggestion in suggestions[:2]:
            if suggestion:
                item = Item()
                item.set_property("type", Type.SUGGESTION)
                item.set_property("title", suggestion)
                item.set_property("uri",
                                  App().search.get_search_uri(suggestion))
                item.set_property("score", Score.SUGGESTION)
                child = Row(item, self._window)
                child.show()
                self._search_box.insert(child, 0)

    def __on_search_suggestion(self, uri, status, content, encoding, value):
        """
            Add suggestions
            @param uri as str
            @param status as bool
            @param content as bytes
            @param encoding as str
            @param value as str
        """
        if status:
            string = content.decode(encoding)
            # format: '["{"words"}",["result1","result2"]]'
            sgs = string.replace('[', '')\
                        .replace(']', '')\
                        .replace('"', '')\
                        .split(',')[1:]
            self.__add_suggestions(sgs)

    def __on_suggestion_timeout(self, value, cancellable):
        """
            Search suggestions
            @param value as str
            @param cancellable as Gio.Cancellable
        """
        self.__suggestion_id = None
        App().search.search_suggestions(value,
                                        cancellable,
                                        self.__on_search_suggestion)
