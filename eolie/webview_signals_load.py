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

from eolie.define import El, Indicator, ArtSize
from eolie.utils import get_snapshot, resize_favicon, get_char_surface


class WebViewLoadSignals:
    """
        Handle webview load signal
    """

    def __init__(self):
        """
            Init class
        """
        self.__load_monitoring = True
        self.__favicon_width = 0

    def set_snapshot(self, uri):
        """
            Set webpage preview
            @param uri as str
        """
        if uri == self.get_uri() and not self.ephemeral:
            self.get_snapshot(WebKit2.SnapshotRegion.FULL_DOCUMENT,
                              WebKit2.SnapshotOptions.NONE,
                              self._cancellable,
                              get_snapshot,
                              self.__on_snapshot,
                              uri,
                              True)

    def disable_load_monitoring(self):
        """
            Disable load monitoring, related to UI updates
            Internal load monitoring (adblock, ...) is not affected
        """
        self.__load_monitoring = False

    def set_favicon(self):
        """
            Set current favicon
        """
        resized = None
        uri = self.get_uri()
        parsed = urlparse(uri)
        if parsed.netloc:
            netloc = parsed.netloc.lstrip("www.")
        else:
            netloc = None
        surface = self.get_favicon()
        icon_theme_artwork = El().art.get_icon_theme_artwork(uri,
                                                             self.ephemeral)
        if icon_theme_artwork is None:
            # Try to get a favicon
            if surface is None:
                favicon_type = "favicon_alt"
                # Build a favicon from uri
                # Never update such favicon as we want to keep same color
                # get_char_surface() => random color
                if netloc is not None:
                    resized = El().art.get_artwork(netloc,
                                                   favicon_type,
                                                   self.get_scale_factor(),
                                                   ArtSize.FAVICON,
                                                   ArtSize.FAVICON)
                    if resized is None:
                        resized = get_char_surface(netloc[0])
            # If webpage has a favicon and quality is superior, resize it
            elif surface.get_width() > self.__favicon_width:
                favicon_type = "favicon"
                resized = resize_favicon(surface)
                self.__favicon_width = surface.get_width()
            # Save favicon if needed:
            if resized is not None:
                if not El().art.exists(uri, favicon_type):
                    El().art.save_artwork(uri, resized, favicon_type)
                if netloc is not None and\
                        not El().art.exists(netloc, favicon_type):
                    El().art.save_artwork(netloc, resized, favicon_type)
                self.__set_initial_uri_favicon(resized,
                                               uri,
                                               self.initial_uri,
                                               favicon_type)
        self.emit("favicon-changed", resized, icon_theme_artwork)

#######################
# PROTECTED           #
#######################
    def _on_map(self, webview):
        """
            Connect all signals
            @param webview as WebView
        """
        if self.__load_monitoring:
            self.connect("load-changed", self.__on_load_changed)
            self.connect("title-changed", self.__on_title_changed)
            self.connect("notify::favicon", self.__on_notify_favicon)
        self.connect("notify::estimated-load-progress",
                     self.__on_estimated_load_progress)
        self.get_back_forward_list().connect(
                             "changed",
                             self.__on_back_forward_list_changed,
                             webview)

    def _on_unmap(self, webview):
        """
            Disconnect all signals
            @param webview as WebView
        """
        if self.__load_monitoring:
            self.disconnect_by_func(self.__on_load_changed)
            self.disconnect_by_func(self.__on_title_changed)
        self.disconnect_by_func(self.__on_estimated_load_progress)
        self.get_back_forward_list().disconnect_by_func(
                                         self.__on_back_forward_list_changed)

#######################
# PRIVATE             #
#######################
    def __set_initial_uri_favicon(self, surface, uri,
                                  initial_uri, favicon_type):
        """
            Set favicon for initial uri
            @param surface as cairo.surface
            @param uri as str
            @param initial_uri as str
            @param favicon_type as str
        """
        if initial_uri != uri and initial_uri is not None:
            parsed = urlparse(uri)
            initial_parsed = urlparse(initial_uri)
            if parsed.netloc.lstrip("www.") ==\
                    initial_parsed.netloc.lstrip("www.") and\
                    not El().art.exists(initial_uri, favicon_type):
                El().art.save_artwork(initial_uri, surface, favicon_type)

    def __on_notify_favicon(self, webview, favicon):
        """
            Set favicon
            @param webview as WebView
            @param favicon as Gparam
        """
        # Do not set favicon now, will be down on WebKit2.LoadEvent.FINISHED
        # Prevent loading/caching a builtin one if page never finishes to load
        if self.get_favicon() is not None:
            self.set_favicon()

    def __on_load_changed(self, webview, event):
        """
            Update sidebar/urlbar
            @param webview as WebView
            @param event as WebKit2.LoadEvent
        """
        if not webview.get_mapped():
            return
        self._window.toolbar.title.update_load_indicator(webview)
        uri = self.get_uri()
        parsed = urlparse(uri)
        wanted_scheme = parsed.scheme in ["http", "https", "file"]
        if event == WebKit2.LoadEvent.STARTED:
            self.__favicon_width = 0
            self._window.container.current.find_widget.set_search_mode(False)
            self._window.toolbar.title.set_title(uri)
            if wanted_scheme:
                self._window.toolbar.title.show_spinner(True)
            else:
                # Give focus to url bar
                self._window.toolbar.title.start_search()
            self._window.toolbar.title.show_indicator(Indicator.NONE)
            # Turn off reading mode if needed
            if self._window.container.current.reading:
                self._window.container.current.switch_read_mode()
            self._window.toolbar.title.progress.show()
        elif event == WebKit2.LoadEvent.COMMITTED:
            self._window.toolbar.title.set_title(uri)
        elif event == WebKit2.LoadEvent.FINISHED:
            self._window.toolbar.title.show_spinner(False)
            # Give focus to webview
            if wanted_scheme:
                GLib.idle_add(self.grab_focus)
            # Hide progress delayed to show result to user
            GLib.timeout_add(500, self._window.toolbar.title.progress.hide)
            if parsed.scheme != "populars":
                GLib.timeout_add(3000, self.set_snapshot, uri)

    def __on_title_changed(self, webview, title):
        """
            Update title
            @param webview as WebView
            @param title as str
        """
        if webview.get_mapped():
            self._window.toolbar.title.set_title(title)
        self._window.container.sites_manager.update_label(self.view)

    def __on_estimated_load_progress(self, webview, value):
        """
            Update progress bar
            @param webview as WebView
            @param value GparamFloat
        """
        if webview.get_mapped():
            value = self.get_estimated_load_progress()
            self._window.toolbar.title.progress.set_fraction(value)

    def __on_back_forward_list_changed(self, bf_list, added, removed, webview):
        """
            Update actions
            @param bf_list as WebKit2.BackForwardList
            @param added as WebKit2.BackForwardListItem
            @param removed as WebKit2.BackForwardListItem
            @param webview as WebView
        """
        self._window.toolbar.actions.set_actions(webview)

    def __on_snapshot(self, surface, uri, first_pass):
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
                              uri,
                              False)
            return
        # Do not cache snapshot on error
        if self.error is not None or uri != self.get_uri():
            return
        # We also cache initial URI
        uris = [uri]
        parsed = urlparse(uri)
        initial_parsed = urlparse(self.initial_uri)
        if parsed.netloc == initial_parsed.netloc and\
                self.initial_uri not in uris:
            uris.append(self.initial_uri)
        for uri in uris:
            if not El().art.exists(uri, "start"):
                El().art.save_artwork(uri, surface, "start")
