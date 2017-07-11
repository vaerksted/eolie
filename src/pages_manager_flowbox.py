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

from eolie.pages_manager_flowbox_child import PagesManagerFlowBoxChild
from eolie.pages_manager import PagesManager


class PagesManagerFlowBox(PagesManager):
    """
        Flow box linked to a Gtk.Stack
    """

    def __init__(self, window):
        """
            Init stack
            @param window as Window
        """
        PagesManager.__init__(self, window)
        self._box = Gtk.FlowBox.new()
        self._box.set_activate_on_single_click(True)
        self._box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._box.set_homogeneous(True)
        self._box.set_max_children_per_line(1000)
        self._box.show()
        self._box.connect("child-activated", self.__on_child_activated)
        self._viewport.set_property("valign", Gtk.Align.START)
        self._viewport.add(self._box)
        self._CHILD_CLASS = PagesManagerFlowBoxChild
        self._grid.add(self._scrolled)
        self._grid.add(self._search_bar)

    def add_child(self, view):
        """
            Add child to sidebar
            @param view as View
            @return child
        """
        uri = view.webview.get_uri()
        child = PagesManager.add_child(self, view)
        if uri:
            child.set_snapshot(uri, False)
        return child

    def move_first(self, view):
        """
            Move view at first position
            @param view as View
        """
        for child in self._box.get_children():
            if child.view == view:
                self._box.remove(child)
                self._box.insert(child, 0)
                break

#######################
# PROTECTED           #
#######################
    def _get_child_at_index(self, index):
        """
            Update filter
            @param index as int
        """
        return self._box.get_child_at_index(index)

#######################
# PRIVATE             #
#######################
    def __on_child_activated(self, listbox, row):
        """
            Show wanted web view
            @param listbox as Gtk.ListBox
            @param row as PagesManagerFlowBoxChild
        """
        self._window.container.set_visible_view(row.view)
        self._window.container.set_expose(False)
        self.update_visible_child()
