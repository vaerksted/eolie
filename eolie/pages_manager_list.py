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

from eolie.pages_manager_row import PagesManagerRow
from eolie.define import ArtSize, MARGIN


class PagesManagerList(Gtk.ScrolledWindow):
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
        self.__selected_row = None
        self.__hovered_row = None
        self.__listbox = Gtk.ListBox.new()
        self.__listbox.show()
        self.__listbox.set_sort_func(self.__sort_func)
        self.__listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.__listbox.set_activate_on_single_click(True)
        self.__listbox.connect("row-activated", self.__on_row_activated)
        self.__listbox.get_style_context().add_class("transparent")
        self.__viewport = Gtk.Viewport.new()
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
            row = PagesManagerRow(webview, self.__window)
            row.show()
            row.connect("destroy", self.__on_row_destroy)
            self.__listbox.add(row)
            self.__calculate_height()
            if webview == current_webview:
                self.__selected_row = row
                row.set_state_flags(Gtk.StateFlags.VISITED, False)

#######################
# PRIVATE             #
#######################
    def __calculate_height(self):
        """
            Update popover height request
        """
        height = 0
        for row in self.__listbox.get_children():
            height += ArtSize.START_HEIGHT + 8 + MARGIN * 2
        size = self.__window.get_size()
        # 8 for child padding/border, 10 for scrolled padding + MARGIN
        # TODO: Use style context to get this
        self.set_size_request(ArtSize.START_WIDTH + 8 + 10 + MARGIN * 2,
                              min(size[1] - 100, height + 10))

    def __sort_func(self, row1, row2):
        """
            Sort pages
            @param row1 as PageChildRow
            @param row2 as PageChildRow
        """
        # Always show current first
        if self.__selected_row in [row1, row2]:
            return self.__selected_row == row2
        else:
            return row2.webview.atime > row1.webview.atime

    def __on_row_destroy(self, row):
        """
            Destroy list if empty
            @parma row as PageRow
        """
        if self.__listbox.get_children():
            self.__calculate_height()
        else:
            popover = self.get_ancestor(Gtk.Popover)
            if popover is not None:
                popover.destroy()

    def __on_row_activated(self, listbox, row):
        """
            Switch to webview
            @param listbox as Gtk.ListBox
            @param row as PageRow
        """
        self.__window.container.set_visible_webview(row.webview)
        self.get_ancestor(Gtk.Popover).hide()
