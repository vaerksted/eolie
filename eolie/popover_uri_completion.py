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

from gi.repository import GLib

from gettext import gettext as _
from urllib.parse import urlparse

from eolie.define import Type, App, Score
from eolie.helper_task import TaskHelper
from eolie.popover_uri_item import Item
from eolie.popover_uri_row import Row


class UriPopoverCompletion:
    """
        Completion handler for UriPopover
    """

    def __init__(self):
        """
            Init handler
        """
        self.__task_helper = TaskHelper()
        self.__dns_suffixes = ["com", "org"]
        for string in reversed(GLib.get_language_names()):
            if len(string) == 2:
                self.__dns_suffixes.insert(0, string)
                break

    def add_completion(self, value, cancellable):
        """
            Add completion for value
            @param value as str
            @param cancellable as Gio.Cancellable
        """
        self.__task_helper.run(self.__do_completion, value, cancellable)

#######################
# PRIVATE             #
#######################
    def __add_completion_row(self, value, cancellable):
        """
            Add a completion row for value
            @param value as str
            @param cancellable as Gio.Cancellable
        """
        if not cancellable.is_cancelled():
            item = Item()
            item.set_property("type", Type.COMPLETION)
            item.set_property("title", _("Go to"))
            item.set_property("uri", value)
            item.set_property("score", Score.COMPLETION)
            child = Row(item, self._window)
            child.show()
            self._search_box.insert(child, 0)

    def __do_completion(self, value, cancellable):
        """
            Do completion for value
            @param value as str
            @param cancellable as Gio.Cancellable
            @thread safe
        """
        # Look for a match in history
        match = App().history.get_match(value)
        if match is not None and not cancellable.is_cancelled():
            match_str = match.split("://")[-1].split("www.")[-1]
            GLib.idle_add(self.__add_completion_row, match, cancellable)
        elif App().settings.get_value("dns-prediction") and\
                not cancellable.is_cancelled():
            # Try some DNS request, FIXME Better list?
            from socket import gethostbyname
            parsed = urlparse(value)
            if parsed.netloc:
                value = parsed.netloc
            for suffix in self.__dns_suffixes:
                if cancellable.is_cancelled():
                    break
                for prefix in ["www.", ""]:
                    if cancellable.is_cancelled():
                        break
                    try:
                        lookup = "%s%s.%s" % (prefix, value, suffix)
                        gethostbyname(lookup)
                        GLib.idle_add(self.__add_completion_row, match_str,
                                      cancellable)
                        return
                    except:
                        pass
