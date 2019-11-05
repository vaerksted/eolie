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

from eolie.pages_manager_row import PageRow


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
        self.__hovered_row = None
        self.__listbox = Gtk.ListBox.new()
        self.__listbox.show()
        self.__listbox.set_sort_func(self.__sort_func)
        self.__listbox.set_activate_on_single_click(True)
        self.__listbox.connect("row-activated", self.__on_row_activated)
        self.__listbox.get_style_context().add_class("dark")
        self.add(self.__listbox)
        self.get_style_context().add_class("big-padding")
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.connect("destroy", self.__on_destroy)
        self.__event_controller = Gtk.EventControllerMotion.new(self)
        self.__event_controller.connect("motion", self.__on_box_motion)
        self.__current_webview = self.__window.container.webview

    def populate(self, webviews):
        """
            Populate list with webviews
            @param webviews as [WebView]
        """
        for webview in webviews:
            child = PageRow(webview, self.__window)
            child.show()
            self.__listbox.add(child)
            if webview == self.__current_webview:
                self.__listbox.select_row(child)

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
        # Unshown first
        elif not row2.webview.shown and row1.webview.shown:
            return True
        else:
            return row2.webview.atime > row1.webview.atime

    def __on_destroy(self, widget):
        """
            Restore current if not None
            @param widget as Gtk.Widget
        """
        if self.__current_webview is not None:
            self.__window.container.set_visible_webview(self.__current_webview)

    def __on_row_activated(self, listbox, row):
        """
            Switch to webview
            @param listbox as Gtk.ListBox
            @param row as PageRow
        """
        self.__current_webview = None
        self.__window.container.set_visible_webview(row.webview)
        self.get_ancestor(Gtk.Popover).hide()

    def __on_box_motion(self, event_controller, x, y):
        """
            Update current selected child
            @param event_controller as Gtk.EventControllerMotion
            @param x as int
            @param y as int
        """
        row = self.__listbox.get_row_at_y(y)
        if row == self.__hovered_row or row is None:
            return
        self.__hovered_row = row
        self.__window.container.set_visible_webview(row.webview)
