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

from gi.repository import Gtk, GObject

import cairo

from eolie.define import El, ArtSize
from eolie.stack_child import StackChild


class StackboxChild(Gtk.FlowBoxChild, StackChild):
    """
        A stack box child
    """

    __gsignals__ = {
        'moved': (GObject.SignalFlags.RUN_FIRST, None, (str, bool))
    }

    def __init__(self, view, window):
        """
            Init child
            @param view as View
            @param window as Window
        """
        Gtk.FlowBoxChild.__init__(self)
        StackChild.__init__(self, view, window)
        self.set_property("halign", Gtk.Align.START)
        self.set_margin_start(20)
        self.set_margin_end(20)
        self.set_margin_top(20)
        self.set_margin_bottom(20)
        self.set_property("width-request", ArtSize.START_WIDTH +
                          ArtSize.PREVIEW_WIDTH_MARGIN)
        self.set_property("height-request", ArtSize.START_HEIGHT)

#######################
# PROTECTED           #
#######################
    def _on_snapshot(self, view, result, uri, save):
        """
            Set snapshot on main image
            @param view as WebView
            @param result as Gio.AsyncResult
            @param uri as str
            @param save as bool
            @warning view here is WebKit2.WebView, not WebView
        """
        current_uri = view.get_uri()
        if current_uri is None or current_uri != uri:
            return
        # Do not cache snapshot on error
        if self._view.webview.error is not None:
            save = False
        try:
            snapshot = view.get_snapshot_finish(result)

            # Save start image to cache
            # We also cache original URI
            uris = [current_uri]
            if view.related_uri is not None and\
                    view.related_uri not in uris:
                uris.append(view.related_uri)
            view.reset_related_uri()
            # Set start image scale factor
            factor = ArtSize.START_WIDTH / snapshot.get_width()
            surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                         ArtSize.START_WIDTH,
                                         ArtSize.START_HEIGHT)
            context = cairo.Context(surface)
            context.scale(factor, factor)
            context.set_source_surface(snapshot, 0, 0)
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
