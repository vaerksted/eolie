# Copyright (c) 2017-2018 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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
from eolie.utils import get_snapshot, resize_favicon, get_char_surface
from eolie.utils import remove_www


class WebViewArtwork:
    """
        Handle webview artwork: snapshot and favicon
    """

    def __init__(self):
        """
            Init class
        """
        self.__helper = TaskHelper()
        self.__snapshot_id = None
        self.__cancellable = Gio.Cancellable()
        self.__initial_uri = None
        self.__favicon_width = {}
        self.__save_favicon_timeout_id = None
        self.__current_netloc = None

    def set_snapshot(self):
        """
            Set webpage preview
        """
        self.stop_snapshot()
        if not self.ephemeral and not self._error:
            self.__snapshot_id = GLib.timeout_add(3000, self.__set_snapshot)

    def stop_snapshot(self):
        """
            Stop pending snapshot loading
        """
        if self.__snapshot_id is not None:
            GLib.source_remove(self.__snapshot_id)
            self.__snapshot_id = None

    def set_favicon(self):
        """
            Set favicon
        """
        if self.ephemeral or self._error:
            return
        parsed = urlparse(self.uri)
        if parsed.scheme in ["http", "https"]:
            self.context.get_favicon_database().get_favicon(
                                                        self.uri,
                                                        None,
                                                        self.__on_get_favicon,
                                                        self.uri,
                                                        self.__initial_uri,
                                                        False)

#######################
# PROTECTED           #
#######################
    def _on_load_changed(self, webview, event):
        """
            Update sidebar/urlbar
            @param webview as WebView
            @param event as WebKit2.LoadEvent
        """
        parsed = urlparse(webview.uri)
        if event == WebKit2.LoadEvent.STARTED:
            self.__cancellable.cancel()
            self.__cancellable.reset()
            if parsed.scheme in ["http", "https"]:
                self.__initial_uri = webview.uri.rstrip('/')
            else:
                self.__initial_uri = None
            surface = App().art.get_favicon(webview.uri,
                                            self.get_scale_factor())
            if surface is not None:
                self.emit("favicon-changed", surface, None)
            elif self.__current_netloc is None or\
                    self.__current_netloc not in webview.uri:
                # Get symbolic favicon for icon theme
                icon_theme_artwork = App().art.get_icon_theme_artwork(
                                                              webview.uri,
                                                              self.ephemeral)
                if icon_theme_artwork is not None:
                    self.emit("favicon-changed", None, icon_theme_artwork)
                else:
                    self.emit("favicon-changed", None, "applications-internet")
        elif event == WebKit2.LoadEvent.FINISHED:
            if parsed.scheme in ["http", "https"]:
                favicon_database = self.context.get_favicon_database()
                favicon_database.get_favicon(webview.uri,
                                             None,
                                             self.__on_get_favicon,
                                             webview.uri,
                                             self.__initial_uri,
                                             True)
            self.__current_netloc = parsed.netloc or None

#######################
# PRIVATE             #
#######################
    def __set_snapshot(self):
        """
            Set webpage preview
        """
        self.__snapshot_id = None
        self.get_snapshot(WebKit2.SnapshotRegion.FULL_DOCUMENT,
                          WebKit2.SnapshotOptions.NONE,
                          self.__cancellable,
                          get_snapshot,
                          self.__on_snapshot,
                          True)

    def __save_favicon_to_cache(self, surface, uri, initial_uri, favicon_type):
        """
            Save favicon to cache
            @param surface as cairo.Surface
            @param uri as str
            @param initial_uri as str
            @param favicon_type as str
        """
        self.__save_favicon_timeout_id = None
        # Save favicon for URI
        if not App().art.exists(uri, "favicon"):
            self.__helper.run(App().art.save_artwork,
                              uri,
                              surface,
                              favicon_type)
        # Save favicon for initial URI
        if initial_uri is not None and\
                not App().art.exists(initial_uri, "favicon"):
            striped_uri = uri.rstrip("/")
            if initial_uri != striped_uri:
                self.__helper.run(App().art.save_artwork,
                                  initial_uri,
                                  surface,
                                  favicon_type)

    def __on_get_favicon(self, favicon_db, result, uri, initial_uri, builtin):
        """
            Read favicon
            @param favicon_db as WebKit2.FaviconDatabase
            @param result as Gio.AsyncResult
            @param uri as str
            @param initial_uri as str
            @param builtin as bool
        """
        resized = None
        try:
            surface = favicon_db.get_favicon_finish(result)
        except:
            surface = None
        # Save webview favicon
        if surface is not None:
            favicon_width = surface.get_width()
            if uri not in self.__favicon_width.keys() or\
                    favicon_width >= self.__favicon_width[uri]:
                if self.__save_favicon_timeout_id is not None:
                    GLib.source_remove(self.__save_favicon_timeout_id)
                    self.__save_favicon_timeout_id = None
                self.__favicon_width[uri] = favicon_width
                resized = resize_favicon(surface)
                # We wait for a better favicon
                self.__save_favicon_timeout_id = GLib.timeout_add(
                                  2000,
                                  self.__save_favicon_to_cache,
                                  resized,
                                  uri,
                                  initial_uri,
                                  "favicon")
        elif builtin:
            netloc = remove_www(urlparse(uri).netloc)
            if netloc:
                resized = App().art.get_favicon(uri,
                                                self.get_scale_factor())
                if resized is None:
                    resized = get_char_surface(netloc[0])
                    self.__save_favicon_to_cache(resized,
                                                 uri,
                                                 initial_uri,
                                                 "favicon_alt")
        if resized is not None and uri == self.uri:
            self.emit("favicon-changed", resized, None)

    def __on_snapshot(self, surface, first_pass):
        """
            Cache snapshot
            @param surface as cairo.Surface
            @param uri as str
            @param first_pass as bool
        """
        # The 32767 limit on the width/height dimensions
        # of an image surface is new in cairo 1.10,
        # try with WebKit2.SnapshotRegion.VISIBLE
        if surface is None:
            if first_pass:
                self.get_snapshot(WebKit2.SnapshotRegion.VISIBLE,
                                  WebKit2.SnapshotOptions.NONE,
                                  self.__cancellable,
                                  get_snapshot,
                                  self.__on_snapshot,
                                  False)
            return
        uri = self.uri
        # We also cache initial URI
        uris = [uri.rstrip("/")]
        if self.__initial_uri is not None and\
                self.__initial_uri not in uris:
            uris.append(self.__initial_uri)
        for uri in uris:
            exists = App().art.exists(uri, "start")
            if not exists:
                App().art.save_artwork(uri, surface, "start")
