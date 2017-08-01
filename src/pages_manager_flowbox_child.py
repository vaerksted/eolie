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

from gi.repository import Gtk, WebKit2

import cairo

from eolie.define import El, ArtSize
from eolie.pages_manager_child import PagesManagerChild


class PagesManagerFlowBoxChild(Gtk.FlowBoxChild, PagesManagerChild):
    """
        A stack box child
    """

    def __init__(self, view, window):
        """
            Init child
            @param view as View
            @param window as Window
        """
        Gtk.FlowBoxChild.__init__(self)
        PagesManagerChild.__init__(self, view, window)
        self.set_property("halign", Gtk.Align.START)
        self.set_margin_start(20)
        self.set_margin_end(20)
        self.set_margin_top(20)
        self.set_margin_bottom(20)
        self.set_property("width-request", ArtSize.START_WIDTH +
                          ArtSize.PREVIEW_WIDTH_MARGIN)
        # TODO: 12?
        self.set_property("height-request", ArtSize.START_HEIGHT + 12)

    def set_snapshot(self, uri, save):
        """
            Set webpage preview
            @param uri as str
            @param save as bool
        """
        if self._view.webview.ephemeral:
            self._image.set_from_icon_name(
                                         "user-not-tracked-symbolic",
                                         Gtk.IconSize.DIALOG)
        else:
            self._view.webview.get_snapshot(
                                         WebKit2.SnapshotRegion.VISIBLE,
                                         WebKit2.SnapshotOptions.NONE,
                                         None,
                                         self._on_snapshot,
                                         uri,
                                         save)

#######################
# PROTECTED           #
#######################
    def _on_button_press_event(self, eventbox, event):
        """
            Hide popover or close view
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        return PagesManagerChild._on_button_press_event(self, eventbox, event)

    def _on_button_release_event(self, eventbox, event):
        """
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        PagesManagerChild._on_button_release_event(self, eventbox, event)

    def _on_close_button_press_event(self, eventbox, event):
        """
            Destroy self
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        return PagesManagerChild._on_close_button_press_event(self,
                                                              eventbox,
                                                              event)

    def _on_load_changed(self, webview, event):
        """
            Update widget content
            @param webview as WebView
            @param event as WebKit2.LoadEvent
        """
        PagesManagerChild._on_load_changed(self, webview, event)

    def _on_snapshot(self, webview, result, uri, save):
        """
            Set snapshot on main image
            @param webview as WebView
            @param result as Gio.AsyncResult
            @param uri as str
            @param save as bool
        """
        current_uri = webview.get_uri()
        if current_uri is None or\
                current_uri != uri or\
                webview != self._view.webview:
            return
        # Do not cache snapshot on error
        if webview.error is not None:
            save = False
        try:
            snapshot = webview.get_snapshot_finish(result)
            # Save start image to cache
            # We also cache original URI
            uris = [current_uri]
            if save:
                if webview.related_uri is not None and\
                        webview.related_uri not in uris:
                    uris.append(webview.related_uri)
            # Set start image scale factor
            margin = 0
            if snapshot.get_width() > snapshot.get_height():
                margin = (snapshot.get_width() - ArtSize.START_WIDTH) / 2
                factor = ArtSize.START_HEIGHT / snapshot.get_height()
            else:
                factor = ArtSize.START_WIDTH / snapshot.get_width()
            surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                         ArtSize.START_WIDTH,
                                         ArtSize.START_HEIGHT)
            context = cairo.Context(surface)
            context.scale(factor, factor)
            context.set_source_surface(snapshot, -margin * factor, 0)
            context.paint()
            self._image.set_from_surface(surface)
            for uri in uris:
                if not El().art.exists(uri, "start") and save:
                    El().art.save_artwork(uri, surface, "start")
            del surface
            del snapshot
        except Exception as e:
            print("StackboxChild::__on_snapshot():", e)

#######################
# PRIVATE             #
#######################
