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

from eolie.pages_manager_row import PagesManagerRow
from eolie.define import ArtSize
from eolie.helper_size_allocation import SizeAllocationHelper


class PagesManagerList(Gtk.ScrolledWindow, SizeAllocationHelper):
    """
        WebViews in a ListBox
    """

    def __init__(self, window):
        """
            Init Box
            @param window as Window
        """
        Gtk.ScrolledWindow.__init__(self)
        self.__window = window
        self.__hovered_row = None
        self.__listbox = Gtk.ListBox.new()
        self.__listbox.show()
        self.__listbox.set_sort_func(self.__sort_func)
        self.__listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.__listbox.set_activate_on_single_click(True)
        self.__listbox.connect("row-activated", self.__on_row_activated)
        self.__listbox.get_style_context().add_class("transparent")
        self.__viewport = Gtk.Viewport.new()
        SizeAllocationHelper.__init__(self, self.__listbox)
        self.add(self.__listbox)
        self.get_style_context().add_class("padding")
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

    def populate(self, webviews):
        """
            Populate list with webviews
            @param webviews as [WebView]
        """
        current_webview = self.__window.container.webview
        for webview in webviews:
            child = PagesManagerRow(webview, self.__window)
            child.show()
            self.__listbox.add(child)
            if webview == current_webview:
                child.set_state_flags(Gtk.StateFlags.VISITED, False)

    def _handle_height_allocate(self, allocation):
        """
            @param allocation as Gtk.Allocation
        """
        if SizeAllocationHelper._handle_height_allocate(self, allocation):
            height = min(allocation.height + 10,
                         self.__window.get_allocated_height() - 100)
            self.set_size_request(ArtSize.START_WIDTH, height)

#######################
# PRIVATE             #
#######################
    def __sort_func(self, row1, row2):
        """
            Sort pages
            @param row1 as PageChildRow
            @param row2 as PageChildRow
        """
        current_child = self.__listbox.get_selected_row()
        # Always show current first
        if current_child in [row1, row2]:
            return current_child == row2
        else:
            return row2.webview.atime > row1.webview.atime

    def __on_row_activated(self, listbox, row):
        """
            Switch to webview
            @param listbox as Gtk.ListBox
            @param row as PageRow
        """
        self.__window.container.set_visible_webview(row.webview)
        self.get_ancestor(Gtk.Popover).hide()
