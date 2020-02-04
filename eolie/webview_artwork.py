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

from gi.repository import GLib, WebKit2, Gio

from urllib.parse import urlparse

from eolie.define import App
from eolie.helper_task import TaskHelper
from eolie.utils import get_snapshot, resize_favicon
from eolie.utils import get_round_surface, get_char_surface, get_safe_netloc


class WebViewArtwork:
    """
        Handle webview artwork: snapshot and favicon
    """

    def __init__(self):
        """
            Init class
        """
        self.__helper = TaskHelper()
        self.__cancellable = Gio.Cancellable()
        self.__surface = None
        self.__snapshot_id = None
        self.__scroll_event_id = None
        self.__is_snapshot_valid = False
        self.connect("uri-changed", self.__on_uri_changed)
        self.connect("scroll-event", self.__on_scroll_event)
        self.connect("notify::favicon", self.__on_webview_favicon_changed)

    @property
    def surface(self):
        """
            Get webview snapshot surface
            @return cairo.Surface
        """
        return self.__surface

    @property
    def is_snapshot_valid(self):
        """
            True if snapshot is valid for current URI
            @return bool
        """
        return self.__is_snapshot_valid

#######################
# PROTECTED           #
#######################
    def _on_load_changed(self, webview, event):
        """
            Update sidebar/urlbar
            @param webview as WebView
            @param event as WebKit2.LoadEvent
        """
        if event == WebKit2.LoadEvent.STARTED:
            self.__is_snapshot_valid = False
            self.__cancellable.cancel()
            self.__cancellable = Gio.Cancellable()
            if self.__snapshot_id is not None:
                GLib.source_remove(self.__snapshot_id)
                self.__snapshot_id = None
        elif event == WebKit2.LoadEvent.FINISHED:
            if self.__snapshot_id is not None:
                GLib.source_remove(self.__snapshot_id)
            self.__snapshot_id = GLib.timeout_add(2500,
                                                  self.__set_snapshot)

#######################
# PRIVATE             #
#######################
    def __on_webview_favicon_changed(self, webview, *ignore):
        """
            Set favicon based on current webview favicon
            @param webview as WebView
        """
        parsed = urlparse(self.uri)
        if self.is_ephemeral or parsed.scheme not in ["http", "https"]:
            return
        surface = self.get_favicon()
        if surface is not None:
            surface = get_round_surface(surface,
                                        self.get_scale_factor(),
                                        surface.get_width() / 4)
            self.__set_favicon_from_surface(surface, self.uri)
        else:
            self.__set_favicon_from_surface(None, self.uri)

    def __set_snapshot(self):
        """
            Set webpage preview
        """
        self.__snapshot_id = None
        # Only save page if bookmarked
        save = False
        for uri in [self.uri, self.loaded_uri]:
            if uri is not None and App().bookmarks.get_id(uri) is not None:
                save = True
                break
        self.get_snapshot(WebKit2.SnapshotRegion.VISIBLE,
                          WebKit2.SnapshotOptions.NONE,
                          self.__cancellable,
                          get_snapshot,
                          self.__on_snapshot,
                          save)

    def __set_favicon_from_surface(self, surface, uri):
        """
            Set favicon for surface
            @param favicon_db as WebKit2.FaviconDatabase
            @param result as Gio.AsyncResult
            @param uri as str
        """
        # Get a default favicon
        if surface is None:
            surface = get_char_surface(get_safe_netloc(uri)[0])
        # Save webview favicon
        if surface is not None:
            resized = resize_favicon(surface)
            self.__save_favicon_to_cache(resized,
                                         uri)
            if self.loaded_uri is not None and uri != self.loaded_uri:
                self.__save_favicon_to_cache(resized,
                                             self.loaded_uri)

    def __save_favicon_to_cache(self, surface, uri):
        """
            Save favicon to cache
            @param surface as cairo.Surface
            @param uri as str
        """
        # Save favicon for URI
        self.__helper.run(App().art.save_artwork,
                          uri,
                          surface,
                          "favicon")

    def __on_uri_changed(self, webview, param):
        """
            Handle JS updates
            @param webview as WebKit2.WebView
            @param param as GObject.ParamSpec
        """
        if webview.get_uri() is not None and\
                not webview.is_loading() and\
                not webview.is_ephemeral:
            if self.__snapshot_id is not None:
                GLib.source_remove(self.__snapshot_id)
            self.__snapshot_id = GLib.timeout_add(2500,
                                                  self.__set_snapshot)

    def __on_snapshot(self, surface, save):
        """
            Cache snapshot
            @param surface as cairo.Surface
            @param uri as str
            @param save as bool
        """
        self.__surface = surface
        self.__is_snapshot_valid = True
        self.emit("snapshot-changed", surface)
        if not save or self.error:
            return
        App().art.save_artwork(self.uri, surface, "start")
        if self.loaded_uri is not None and self.uri != self.loaded_uri:
            App().art.save_artwork(self.loaded_uri, surface, "start")

    def __on_scroll_event(self, widget, event):
        """
            Update snapshot
            @param widget as WebView
            @param event as Gdk.EventScroll
        """
        def update_snapshot():
            self.__scroll_event_id = None
            self.get_snapshot(WebKit2.SnapshotRegion.VISIBLE,
                              WebKit2.SnapshotOptions.NONE,
                              self.__cancellable,
                              get_snapshot,
                              self.__on_snapshot,
                              False)
        if self.__snapshot_id is not None:
            GLib.source_remove(self.__snapshot_id)
            self.__snapshot_id = None
        if self.__scroll_event_id is not None:
            GLib.source_remove(self.__scroll_event_id)
        self.__scroll_event_id = GLib.timeout_add(1000, update_snapshot)
