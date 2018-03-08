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

from gi.repository import GLib, WebKit2

from urllib.parse import urlparse

from eolie.define import App, ArtSize
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
        self.__snapshot_id = None
        self.__favicon_timeout_id = None
        self.__favicon_width = 0
        self.__favicon_cached = False
        self.__initial_uri = None

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

    def stop_favicon(self):
        """
            Stop pending favicon loading
        """
        if self.__favicon_timeout_id is not None:
            GLib.source_remove(self.__favicon_timeout_id)
            self.__favicon_timeout_id = None

    def set_favicon(self):
        """
            Set favicon
        """
        if self.ephemeral or self._error or self.uri is None:
            return
        # Get symbolic favicon for icon theme
        icon_theme_artwork = App().art.get_icon_theme_artwork(self.uri,
                                                              self.ephemeral)
        if icon_theme_artwork is not None:
            self.emit("favicon-changed", None, icon_theme_artwork)
        else:
            parsed = urlparse(self.uri)
            netloc = remove_www(parsed.netloc)
            if not netloc:
                return
            surface = self.get_favicon()
            if surface is None:
                width = -1
            else:
                width = surface.get_width()
            # Better favicon, stop any running __set_favicon()
            if width > self.__favicon_width:
                self.stop_favicon()
                # Uncache any previously cached favicon (with wrong width)
                if self.__favicon_cached:
                    self.__favicon_cached = False
                    App().art.uncache(self.uri, "favicon")
                    App().art.uncache(self.uri, "favicon_alt")
            # Uglier favicon, return
            elif surface is not None and width < self.__favicon_width:
                return
            # Save current width
            if width > 0:
                self.__favicon_width = width
            # Check any favicon in cache
            if surface is None:
                for favicon in ["favicon", "favicon_alt"]:
                    surface = App().art.get_artwork(netloc,
                                                    favicon,
                                                    self.get_scale_factor(),
                                                    ArtSize.FAVICON,
                                                    ArtSize.FAVICON)
                    if surface is not None:
                        self.emit("favicon-changed", surface, None)
                        break
            # Get builtin favicon
            if surface is None:
                self.__favicon_timeout_id = GLib.timeout_add(
                                                 1000,
                                                 self.__set_builtin_favicon,
                                                 netloc)
            # Get webview favicon
            else:
                self.__favicon_timeout_id = GLib.timeout_add(
                                                 1000,
                                                 self.__set_favicon,
                                                 surface,
                                                 netloc)

#######################
# PROTECTED           #
#######################
    def _on_load_changed(self, webview, event):
        """
            Update sidebar/urlbar
            @param webview as WebView
            @param event as WebKit2.LoadEvent
        """
        uri = webview.uri
        if event == WebKit2.LoadEvent.STARTED:
            self.__initial_uri = uri.rstrip('/')
            self.__favicon_width = 0
            self.__favicon_cached = False

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
                          self._cancellable,
                          get_snapshot,
                          self.__on_snapshot,
                          True)

    def __set_builtin_favicon(self, netloc):
        """
            Build favicon and cache it
            @param netloc as str
        """
        self.__favicon_timeout_id = None
        surface = get_char_surface(netloc[0])
        self.emit("favicon-changed", surface, None)
        self.__save_favicon_to_cache(surface, netloc, "favicon_alt")

    def __set_favicon(self, surface, netloc):
        """
            Cache favicon and emit signal
            @param surface as cairo.Surface
            @param netloc as str
            @param safe as bool
        """
        self.__favicon_timeout_id = None
        resized = resize_favicon(surface)
        self.emit("favicon-changed", resized, None)
        self.__save_favicon_to_cache(resized, netloc, "favicon")

    def __save_favicon_to_cache(self, surface, netloc, favicon_type):
        """
            Save favicon to cache
            @param surface as cairo.Surface
            @parma netloc as str
            @param favicon_type as str
        """
        exists = App().art.exists(self.uri, favicon_type)
        if not exists:
            self.__favicon_cached = True
            App().art.save_artwork(self.uri, surface, favicon_type)
            # Save favicon for initial URI
            striped_uri = self.uri.rstrip("/")
            if self.__initial_uri != striped_uri:
                App().art.save_artwork(self.__initial_uri,
                                       surface,
                                       favicon_type)
        # Save favicon for netloc
        exists = App().art.exists(netloc, favicon_type)
        if not exists:
            self.__favicon_cached = True
            App().art.save_artwork(netloc, surface, favicon_type)

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
                                  self._cancellable,
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
