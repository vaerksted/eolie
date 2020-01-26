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

from eolie.define import Type, Score
from eolie.popover_uri_item import Item
from eolie.popover_uri_row import Row


class UriPopoverWebviews:
    """
        Webviews handler for UriPopover
    """

    def __init__(self):
        """
            Init handler
        """
        self.__suggestion_id = None

    def add_webviews(self, value, cancellable):
        """
            Add webviews for value
            @param value as str
            @param cancellable as Gio.Cancellable
        """
        if len(value) < 2:
            return
        webviews = []
        for webview in self._window.container.webviews:
            uri = webview.uri
            if uri is None:
                continue
            parsed = urlparse(uri)
            if parsed.netloc.lower().find(value) != -1:
                webviews.append(webview)
        if webviews:
            GLib.idle_add(self.__add_webviews, webviews, cancellable)

#######################
# PRIVATE             #
#######################
    def __add_webviews(self, webviews, cancellable):
        """
            Add a row representing webview
            @param webviews as [WebView]
            @param cancellable as Gio.Cancellable
        """
        if cancellable.is_cancelled():
            return
        for webview in webviews:
            item = Item()
            item.set_property("type", Type.WEBVIEW)
            item.set_property("title", webview.title)
            item.set_property("uri", webview.uri)
            item.set_property("score", Score.WEBVIEW)
            child = Row(item, self._window)
            child.show()
            self._search_box.insert(child, 0)
