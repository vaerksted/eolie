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

from eolie.define import El, ArtSize, PanelMode
from eolie.pages_manager_listbox_child import PagesManagerListBoxChild
from eolie.pages_manager import PagesManager


class PagesManagerListBox(PagesManager):
    """
        Listbox linked to a Gtk.Stack
    """

    def __init__(self, window):
        """
            Init sidebar
            @param window as Window
        """
        PagesManager.__init__(self, window)
        self.__panel_mode = PanelMode.PREVIEW
        self._box = Gtk.ListBox.new()
        self._box.set_activate_on_single_click(True)
        self._box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._box.show()
        self._box.connect("row_activated", self.__on_row_activated)
        self._viewport.add(self._box)
        self._CHILD_CLASS = PagesManagerListBoxChild
        self._grid.add(self._search_bar)
        self._grid.add(self._scrolled)

    def add_child(self, view):
        """
            Add child to sidebar
            @param view as View
            @return child
        """
        child = PagesManager.add_child(self, view)
        self.__set_child_height(child)
        child.connect("moved", self._on_moved)
        return child

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
        panel_mode = El().settings.get_enum("panel-mode")
        if panel_mode == PanelMode.PREVIEW:
            uri = child.view.webview.get_uri()
            child.set_preview_height(ArtSize.PREVIEW_HEIGHT)
            if uri:
                child.set_snapshot(uri, False)
        else:
            child.set_preview_height(None)
            child.clear_snapshot()
        child.show_title(panel_mode != PanelMode.MINIMAL)

    def __on_row_activated(self, listbox, row):
        """
            Show wanted web view
            @param listbox as Gtk.ListBox
            @param row as PagesManagerChild
        """
        self._window.container.set_visible_view(row.view)
        self.update_visible_child()
