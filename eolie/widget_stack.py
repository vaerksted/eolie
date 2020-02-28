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

from gi.repository import Gtk


class Stack(Gtk.Overlay):
    """
        Compatible with Gtk.Stack API
        Used to get snapshot from WebKit by unmapping webview only when needed
    """

    def __init__(self):
        """
            Init overlay
        """
        Gtk.Overlay.__init__(self)
        self.__visible_child = None
        # https://gitlab.gnome.org/GNOME/pygobject/issues/387
        self.__webviews = []

    def add(self, webview):
        """
            Add widget to stack
            @param webview as WebView
        """
        self.__webviews.append(webview)
        webview.connect("snapshot-changed", self.__on_webview_snapshot_changed)
        webview.connect("destroy", self.__on_webview_destroy)
        self.add_overlay(webview)
        self.reorder_overlay(webview, 0)
        if self.__visible_child is None:
            self.__visible_child = webview

    def set_visible_child(self, webview):
        """
            Set visible child
            @param webview as WebView
        """
        if self.__visible_child is not None and\
                self.__visible_child.is_snapshot_valid:
            self.__visible_child.hide()
        webview.show()
        self.__visible_child = webview
        self.reorder_overlay(webview, -1)

    def get_visible_child(self):
        """
            Get visible child
            @return Gtk.Widget
        """
        return self.__visible_child

#######################
# PRIVATE             #
#######################
    def __on_webview_destroy(self, webview):
        """
            Reset visible child
            @param webview as WebView
        """
        if self.__visible_child == webview:
            self.__visible_child = None
        if webview in self.__webviews:
            self.__webviews.remove(webview)

    def __on_webview_snapshot_changed(self, webview, surface):
        """
            We can now hide this view if not visible one
            @param webview as WebView
            @param surface as cairo.Surface
        """
        if webview != self.__visible_child:
            webview.hide()
