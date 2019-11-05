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

from gi.repository import GLib, WebKit2, Gio

from urllib.parse import urlparse

from eolie.define import App
from eolie.logger import Logger
from eolie.helper_task import TaskHelper
from eolie.utils import get_snapshot, resize_favicon, get_favicon_best_uri
from eolie.utils import get_round_surface, get_char_surface


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
        self.__favicon_db = self.get_context().get_favicon_database()
        self.__favicon_db.connect("favicon-changed", self.__on_favicon_changed)
        self.connect("notify::uri", self.__on_uri_changed)
        self.connect("scroll-event", self.__on_scroll_event)

    def set_favicon(self):
        """
            Set favicon based on current webview favicon
        """
        parsed = urlparse(self.uri)
        if self.is_ephemeral or parsed.scheme not in ["http", "https"]:
            return
        self.__cancellable.cancel()
        self.__cancellable = Gio.Cancellable()
        self.__favicon_db.get_favicon(self.uri,
                                      self.__cancellable,
                                      self.__on_get_favicon,
                                      self.uri,
                                      self._initial_uri)

    def set_current_favicon(self):
        """
            Set favicon based on current webview favicon
            Use this for JS update (do not update initial uri)
        """
        parsed = urlparse(self.uri)
        if self.is_ephemeral or parsed.scheme not in ["http", "https"]:
            return
        self.__cancellable.cancel()
        self.__cancellable = Gio.Cancellable()
        self.__favicon_db.get_favicon(self.uri,
                                      self.__cancellable,
                                      self.__on_get_favicon,
                                      self.uri,
                                      None)

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
            self.set_favicon()

#######################
# PRIVATE             #
#######################
    def __set_snapshot(self):
        """
            Set webpage preview
        """
        self.__snapshot_id = None
        # Only save http page if bookmarked
        parsed = urlparse(self.uri)
        save = parsed.scheme in ["http", "https"]
        bookmark_id = App().bookmarks.get_id(self.uri)
        ibookmark_id = App().bookmarks.get_id(self._initial_uri)
        if bookmark_id is None and ibookmark_id is None:
            save = False
        self.get_snapshot(WebKit2.SnapshotRegion.VISIBLE,
                          WebKit2.SnapshotOptions.NONE,
                          self.__cancellable,
                          get_snapshot,
                          self.__on_snapshot,
                          save)

    def __set_favicon_from_surface(self, surface, uri, initial_uri):
        """
            Set favicon for surface
            @param favicon_db as WebKit2.FaviconDatabase
            @param result as Gio.AsyncResult
            @param uri as str
            @param initial_uri as str
        """
        # Get a default favicon
        if surface is None:
            parsed = urlparse(uri)
            if parsed.netloc:
                netloc = parsed.netloc.replace("www.", "")
                surface = get_char_surface(netloc[0])
        # Save webview favicon
        if surface is not None:
            resized = resize_favicon(surface)
            self.__save_favicon_to_cache(resized,
                                         uri,
                                         initial_uri)

    def __save_favicon_to_cache(self, surface, uri, initial_uri):
        """
            Save favicon to cache
            @param surface as cairo.Surface
            @param uri as str
            @param initial_uri as str
        """
        # Save favicon for URI
        self.__helper.run(App().art.save_artwork,
                          uri,
                          surface,
                          "favicon")
        # Only update initial URI if netloc did not changed
        if initial_uri is not None:
            initial_parsed = urlparse(initial_uri)
            parsed = urlparse(uri)
            if parsed.netloc == initial_parsed.netloc:
                self.__helper.run(App().art.save_artwork,
                                  initial_uri,
                                  surface,
                                  "favicon")

    def __on_uri_changed(self, webview, param):
        """
            Handle JS updates
            @param webview as WebKit2.WebView
            @param param as GObject.ParamSpec
        """
        if not webview.is_loading() and not webview.is_ephemeral:
            if self.__snapshot_id is not None:
                GLib.source_remove(self.__snapshot_id)
            self.__snapshot_id = GLib.timeout_add(2500,
                                                  self.__set_snapshot)
            self.__on_favicon_changed(self.__favicon_db, webview.uri)

    def __on_get_favicon(self, favicon_db, result, uri,
                         initial_uri, first=True):
        """
            Get result and set from it
            @param favicon_db as WebKit2.FaviconDatabase
            @param result as Gio.AsyncResult
            @param uri as str
            @param initial_uri as str
            @internal first as bool
        """
        try:
            surface = favicon_db.get_favicon_finish(result)
            if surface is not None:
                surface = get_round_surface(surface,
                                            self.get_scale_factor(),
                                            surface.get_width() / 4)
            self.__set_favicon_from_surface(surface,
                                            uri,
                                            initial_uri)
        except Exception as e:
            Logger.debug("WebViewArtwork::__on_get_favicon(): %s", e)
            if first:
                favicons_path = App().favicons_path + "/WebpageIcons.db"
                best_uri = get_favicon_best_uri(favicons_path, uri)
                if best_uri is not None:
                    self.__favicon_db.get_favicon(best_uri,
                                                  None,
                                                  self.__on_get_favicon,
                                                  uri,
                                                  self._initial_uri,
                                                  False)
                else:
                    self.__set_favicon_from_surface(None, uri, initial_uri)

    def __on_favicon_changed(self, favicon_db, uri, *ignore):
        """
            Reload favicon
            @param favicon_db as WebKit2.FaviconDatabase
            @param uri as str
        """
        if uri != self.uri or self.is_ephemeral:
            return
        self.__favicon_db.get_favicon(uri,
                                      None,
                                      self.__on_get_favicon,
                                      uri,
                                      self._initial_uri)

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
        uri = self.uri
        # We also cache initial URI
        uris = [uri.rstrip("/")]
        if self._initial_uri is not None and\
                self._initial_uri not in uris:
            uris.append(self._initial_uri)
        for uri in uris:
            App().art.save_artwork(uri, surface, "start")

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
