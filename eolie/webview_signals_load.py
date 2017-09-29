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
import cairo

from eolie.define import El, Indicator, ArtSize


class WebViewLoadSignals:
    """
        Handle webview load signal
    """

    def __init__(self):
        """
            Init class
        """
        pass

#######################
# PROTECTED           #
#######################
    def _on_map(self, webview):
        """
            Connect all signals
            @param webview as WebView
        """
        self.connect("load-changed", self.__on_load_changed)
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
        self.disconnect_by_func(self.__on_load_changed)
        self.disconnect_by_func(self.__on_estimated_load_progress)
        self.get_back_forward_list().disconnect_by_func(
                                         self.__on_back_forward_list_changed)

#######################
# PRIVATE             #
#######################
    def __set_snapshot(self, uri):
        """
            Set webpage preview
            @param uri as str
        """
        if uri == self.get_uri() and not self.ephemeral:
            self.get_snapshot(WebKit2.SnapshotRegion.FULL_DOCUMENT,
                              WebKit2.SnapshotOptions.NONE,
                              self._cancellable,
                              self.__on_snapshot,
                              uri)

    def __on_load_changed(self, webview, event):
        """
            Update sidebar/urlbar
            @param webview as WebView
            @param event as WebKit2.LoadEvent
        """
        # Check needed by WebViewPopover!
        if not webview.get_mapped():
            return
        self._window.toolbar.title.update_load_indicator(webview)
        uri = self.get_uri()
        parsed = urlparse(uri)
        wanted_scheme = parsed.scheme in ["http", "https", "file"]
        if event == WebKit2.LoadEvent.STARTED:
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
            GLib.timeout_add(3000, self.__set_snapshot, uri)

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

    def __on_snapshot(self, webview, result, uri):
        """
            Set snapshot on main image
            @param webview as WebView
            @param result as Gio.AsyncResult
            @param uri as str
        """
        ART_RATIO = 1.5  # ArtSize.START_WIDTH / ArtSize.START_HEIGHT
        # Do not cache snapshot on error
        if self.error is not None or uri != self.get_uri():
            return
        try:
            snapshot = self.get_snapshot_finish(result)
            # Set start image scale factor
            ratio = snapshot.get_width() / snapshot.get_height()
            if ratio > ART_RATIO:
                factor = ArtSize.START_HEIGHT / snapshot.get_height()
            else:
                factor = ArtSize.START_WIDTH / snapshot.get_width()
            surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                         ArtSize.START_WIDTH,
                                         ArtSize.START_HEIGHT)
            context = cairo.Context(surface)
            context.scale(factor, factor)
            context.set_source_surface(snapshot, factor, 0)
            context.paint()
            # Cache result
            # We also cache initial URI
            uris = [self.get_uri()]
            parsed = urlparse(uri)
            # Caching this will break populars navigation
            # as we are looking for subpage snapshots
            if parsed.scheme == "populars":
                return
            initial_parsed = urlparse(self.initial_uri)
            if parsed.netloc == initial_parsed.netloc and\
                    self.initial_uri not in uris:
                uris.append(self.initial_uri)
            for uri in uris:
                if not El().art.exists(uri, "start"):
                    El().art.save_artwork(uri, surface, "start")
        except Exception as e:
            print("WebViewSignalsHandler::__on_snapshot():", e)
