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

from eolie.define import ArtSize
from eolie.pages_manager_child import PagesManagerChild
from eolie.utils import debug


class PagesManagerFlowBoxChild(Gtk.FlowBoxChild, PagesManagerChild):
    """
        A stack box child
    """

    def __init__(self, view, window, static):
        """
            Init child
            @param view as View
            @param window as Window
            @param static as bool
        """
        Gtk.FlowBoxChild.__init__(self)
        PagesManagerChild.__init__(self, view, window, static)
        self.set_property("halign", Gtk.Align.START)
        self.set_margin_start(20)
        self.set_margin_end(20)
        self.set_margin_top(20)
        self.set_margin_bottom(20)
        self.set_property("width-request", ArtSize.START_WIDTH +
                          ArtSize.PREVIEW_WIDTH_MARGIN)
        # TODO: 12?
        self.set_property("height-request", ArtSize.START_HEIGHT + 12)

    def update(self):
        """
            Update child title, favicon and snapshot
        """
        PagesManagerChild.update(self)
        self.set_snapshot(self._view.webview.get_uri(), False)

    def set_snapshot(self, uri, save):
        """
            Set webpage preview
            @param uri as str
            @param save as bool
        """
        try:
            if self._view.webview.ephemeral:
                self._image.set_from_icon_name(
                                             "user-not-tracked-symbolic",
                                             Gtk.IconSize.DIALOG)
            else:
                PagesManagerChild.set_snapshot(self, uri, save)
                if save:
                    region = WebKit2.SnapshotRegion.FULL_DOCUMENT
                else:
                    region = WebKit2.SnapshotRegion.VISIBLE
                self._view.webview.get_snapshot(
                                             region,
                                             WebKit2.SnapshotOptions.NONE,
                                             None,
                                             self._on_snapshot,
                                             uri,
                                             save)
        except Exception as e:
            debug("PagesManagerFlowBoxChild::set_snapshot(): %s" % e)

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

#######################
# PRIVATE             #
#######################
