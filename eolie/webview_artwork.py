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

from gi.repository import GLib, WebKit2

from urllib.parse import urlparse

from eolie.define import El, ArtSize
from eolie.utils import get_snapshot, resize_favicon, get_char_surface


class WebViewArtwork:
    """
        Handle webview artwork: snapshot and favicon
    """

    def __init__(self):
        """
            Init class
        """
        self.__snapshot_id = None
        self.__last_uri = None
        self.__favicon_db = self.get_context().get_favicon_database()

    def set_snapshot(self):
        """
            Set webpage preview
        """
        if not self.ephemeral:
            self.__snapshot_id = GLib.timeout_add(3000, self.__set_snapshot)

    def stop_snapshot(self):
        """
            Stop pending snapshot
        """
        if self.__snapshot_id is not None:
            GLib.source_remove(self.__snapshot_id)
            self.__snapshot_id = None

    def set_favicon(self, uri):
        """
            Set favicon for uri
            @param uri as str
        """
        if uri != self.__last_uri:
            self.__last_uri = uri
            self.__favicon_db.get_favicon(uri, None, self.__on_favicon, uri)

#######################
# PROTECTED           #
#######################

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

    def __set_initial_uri_favicon(self, surface, uri, favicon_type):
        """
            Set favicon for initial uri
            @param surface as cairo.surface
            @param uri as str
            @param initial_uri as str
            @param favicon_type as str
        """
        if self.initial_uri is not None:
            striped_uri = uri.rstrip("/")
            if self.initial_uri != striped_uri:
                if not El().art.exists(self.initial_uri, favicon_type):
                    El().art.save_artwork(self.initial_uri,
                                          surface,
                                          favicon_type)

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
        if surface is None and first_pass:
            self.get_snapshot(WebKit2.SnapshotRegion.VISIBLE,
                              WebKit2.SnapshotOptions.NONE,
                              self._cancellable,
                              get_snapshot,
                              self.__on_snapshot,
                              False)
            return
        # Do not cache snapshot on error
        if self.error is not None:
            return
        uri = self.get_uri()
        # We also cache initial URI
        uris = [uri.rstrip("/")]
        if self.initial_uri is not None and\
                self.initial_uri not in uris:
            uris.append(self.initial_uri)
        for uri in uris:
            if not El().art.exists(uri, "start"):
                El().art.save_artwork(uri, surface, "start")

    def __on_favicon(self, favicon_db, result, uri):
        """
            Set current favicon
            @param favicon_db as WebKit2.FaviconDatabase
            @param result as Gio.AsyncResult
            @param uri as str
        """
        resized = None
        icon_theme_artwork = El().art.get_icon_theme_artwork(uri,
                                                             self.ephemeral)
        if icon_theme_artwork is not None:
            self.emit("favicon-changed", None, icon_theme_artwork)
        else:
            favicon_type = "favicon"
            # Calculate netloc
            parsed = urlparse(uri)
            if parsed.netloc:
                netloc = parsed.netloc.lstrip("www.")
            else:
                netloc = None
            # Read result
            try:
                surface = favicon_db.get_favicon_finish(result)
            except:
                surface = None
            # Resize surface and set favicon
            if surface is not None:
                resized = resize_favicon(surface)
            elif netloc is not None:
                # Check for already cached favicon
                # We do not want to show a favicon_alt if a favicon is cached
                # so check for favicon too
                for favicon in ["favicon", "favicon_alt"]:
                    resized = El().art.get_artwork(netloc,
                                                   favicon,
                                                   self.get_scale_factor(),
                                                   ArtSize.FAVICON,
                                                   ArtSize.FAVICON)
                    if resized is not None:
                        favicon_type = favicon
                        break
                if resized is None:
                    resized = get_char_surface(netloc[0])
                    favicon_type = "favicon_alt"
            self.emit("favicon-changed", resized, None)
            # Save favicon if needed
            if not El().art.exists(uri, favicon_type):
                El().art.save_artwork(uri, resized, favicon_type)
            if netloc is not None and\
                    not El().art.exists(netloc, favicon_type):
                El().art.save_artwork(netloc, resized, favicon_type)
            self.__set_initial_uri_favicon(resized,
                                           uri,
                                           favicon_type)
