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

from gi.repository import Gtk

from eolie.define import El, ArtSize
from eolie.stacksidebar_child import StackSidebarChild
from eolie.stack import Stack


class StackSidebar(Stack):
    """
        Listbox linked to a Gtk.Stack
    """

    def __init__(self, window):
        """
            Init sidebar
            @param window as Window
        """
        Stack.__init__(self, window)
        self._box = Gtk.ListBox.new()
        self._box.set_activate_on_single_click(True)
        self._box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._box.show()
        self._box.connect("row_activated", self.__on_row_activated)
        self._viewport.add(self._box)
        self._CHILD_CLASS = StackSidebarChild
        self.set_panel_mode()

    def add_child(self, view):
        """
            Add child to sidebar
            @param view as WebView
            @return child
        """
        child = Stack.add_child(self, view)
        self.__set_child_height(child)
        return child

    def set_panel_mode(self, panel_mode=None):
        """
            Set panel mode
            @param panel_mode as int
        """
        if panel_mode is None:
            self.__panel_mode = El().settings.get_enum("panel-mode")
        else:
            self.__panel_mode = panel_mode
        if self.__panel_mode == 2:
            self.set_property("width-request", -1)
        else:
            self.set_property("width-request", ArtSize.PREVIEW_WIDTH)
        for child in self._box.get_children():
            child.show_title(self.__panel_mode != 2)
            self.__set_child_height(child)

    @property
    def panel_mode(self):
        """
            Get current panel mode
            @return int
        """
        return self.__panel_mode

#######################
# PROTECTED           #
#######################
    def _get_child_at_index(self, index):
        """
            Update filter
            @param index as int
        """
        return self._box.get_row_at_index(index)

#######################
# PRIVATE             #
#######################
    def __set_child_height(self, child):
        """
            Set child height
            @param child as SidebarChild
        """
        if self.__panel_mode == 0:
            child.set_preview_height(ArtSize.PREVIEW_HEIGHT)
            child.set_snapshot(child.view.webview.get_uri(), True)
        else:
            child.set_preview_height(None)
            child.clear_snapshot()

    def __on_row_activated(self, listbox, row):
        """
            Show wanted web view
            @param listbox as Gtk.ListBox
            @param row as StackSidebarChild
        """
        self._window.container.set_visible_view(row.view)
        self.update_visible_child()
