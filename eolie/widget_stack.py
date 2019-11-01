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

    def add(self, widget):
        """
            Add widget to stack
            @param widget as Gtk.Widget
        """
        self.add_overlay(widget)
        self.reorder_overlay(widget, 0)

    def set_visible_child(self, widget):
        """
            Set visible child
            @param widget as Gtk.Widget
        """
        self.reorder_overlay(widget, -1)

    def get_visible_child(self):
        """
            Get visible child
            @return Gtk.Widget
        """
        visible_child = None
        index = -1
        for child in self.get_children():
            child_index = self.child_get_property(child, "index")
            if child_index > index:
                index = child_index
                visible_child = child
        return visible_child
