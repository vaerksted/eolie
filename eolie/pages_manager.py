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

from gi.repository import Gtk, Gdk, GLib

from eolie.pages_manager_child import PagesManagerChild
from eolie.define import El, WindowType


class PagesManager(Gtk.EventBox):
    """
        Box linked to a Gtk.Stack
    """

    def __init__(self, window):
        """
            Init stack
            @param window as Window
        """
        Gtk.EventBox.__init__(self)
        self.__window = window
        self.__next_timeout_id = None
        self.__previous_timeout_id = None
        self.get_style_context().add_class("sidebar")
        self.connect("button-press-event", self.__on_button_press)
        grid = Gtk.Grid()
        grid.set_orientation(Gtk.Orientation.VERTICAL)
        grid.show()
        self.__search_entry = Gtk.SearchEntry.new()
        self.__search_entry.connect("search-changed", self.__on_search_changed)
        self.__search_entry.show()
        self.__search_bar = Gtk.SearchBar.new()
        self.__search_bar.add(self.__search_entry)
        self.__scrolled = Gtk.ScrolledWindow()
        self.__scrolled.set_vexpand(True)
        self.__scrolled.set_hexpand(True)
        self.__scrolled.show()
        viewport = Gtk.Viewport()
        viewport.show()
        self.__scrolled.add(viewport)
        self.set_hexpand(False)

        self.__box = Gtk.FlowBox.new()
        self.__box.set_activate_on_single_click(True)
        self.__box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.__box.set_max_children_per_line(1000)
        self.__box.set_filter_func(self.__filter_func)
        self.__box.set_sort_func(self.__sort_func)
        self.__box.show()
        self.__box.connect("child-activated", self._on_child_activated)
        viewport.set_property("valign", Gtk.Align.START)
        viewport.add(self.__box)
        grid.add(self.__scrolled)
        grid.add(self.__search_bar)

        self.add(grid)

    def add_view(self, view):
        """
            Add child to sidebar
            @param view as View
            @return child
        """
        child = PagesManagerChild(view, self.__window)
        child.show()
        self.__box.add(child)
        return child

    def update_visible_child(self):
        """
            Mark current child as visible
            Unmark all others
        """
        visible = self.__window.container.current
        for child in self.__box.get_children():
            style_context = child.get_style_context()
            if child.view == visible:
                style_context.add_class("sidebar-item-selected")
            else:
                style_context.remove_class("sidebar-item-selected")

    def search_grab_focus(self):
        """
            Grab focus on search entry
        """
        self.__search_entry.grab_focus()

    def update_sort(self):
        """
            Reset sort
        """
        self.__box.invalidate_sort()

    def set_filter(self, search):
        """
            Filter view
            @param search as str
        """
        self.__search_entry.set_text(search)
        self.__box.invalidate_filter()

    def set_filtered(self, b):
        """
            Show filtering widget
            @param b as bool
        """
        if b and not self.__search_bar.is_visible():
            self.__search_bar.show()
            self.__search_entry.grab_focus()
            self.__search_entry.connect("key-press-event",
                                        self.__on_key_press)
        elif self.__search_bar.is_visible():
            self.__search_bar.hide()
            self.__search_entry.disconnect_by_func(self.__on_key_press)
        self.__search_bar.set_search_mode(b)

    def next(self):
        """
            Show next view
        """
        if self.__next_timeout_id is None and\
                self.__next_timeout_id != -1:
            self.__next_timeout_id = GLib.timeout_add(100,
                                                      self.__set_expose,
                                                      self.__next)
        else:
            self.__next()

    def previous(self):
        """
            Show next view
        """
        if self.__previous_timeout_id is None and\
                self.__previous_timeout_id != -1:
            self.__previous_timeout_id = GLib.timeout_add(100,
                                                          self.__set_expose,
                                                          self.__previous)
        else:
            self.__previous()

    def ctrl_released(self):
        """
            Disable any pending expose
        """
        if self.__next_timeout_id is not None:
            if self.__next_timeout_id != -1:
                self.__next()
                GLib.source_remove(self.__next_timeout_id)
        if self.__previous_timeout_id is not None:
            if self.__previous_timeout_id != -1:
                self.__previous()
                GLib.source_remove(self.__previous_timeout_id)

        self.__next_timeout_id = None
        self.__previous_timeout_id = None

    @property
    def filter(self):
        """
            Get filter
            @return str
        """
        return self.__search_entry.get_text()

    @property
    def filtered(self):
        """
            True if filtered
            @return bool
        """
        return self.__search_bar.get_search_mode()

    @property
    def children(self):
        """
            Get views ordered
            @return [PagesManagerChild]
        """
        return self.__box.get_children()

#######################
# PROTECTED           #
#######################
    def _on_child_activated(self, flowbox, child):
        """
            Show wanted web view
            @param flowbox as Gtk.FlowBox
            @param child as PagesManagerChild
        """
        self.__window.close_popovers()
        self.__window.container.set_current(child.view)
        self.__window.container.set_expose(False)

#######################
# PRIVATE             #
#######################
    def __set_expose(self, callback):
        """
            Set expose on and call callback
            @param callback as function
        """
        self.__next_timeout_id = -1
        self.__previous_timeout_id = -1
        self.__window.container.set_expose(True)
        callback()

    def __next(self):
        """
            Show next view
        """
        children = self.__box.get_children()
        if not children:
            return
        current_row = None
        next_row = None
        for child in children:
            # First search for current
            if child.view == self.__window.container.current:
                current_row = child
            # Init next to first valid child
            elif next_row is None and\
                    current_row is None and\
                    self.__filter_func(child):
                next_row = child
            # Second search for next
            elif current_row is not None and self.__filter_func(child):
                next_row = child
                break
        if next_row is not None:
            self.__window.container.set_current(next_row.view)

    def __previous(self):
        """
            Show previous view
        """
        children = self.__box.get_children()
        if not children:
            return
        current_row = None
        prev_row = None
        for child in reversed(children):
            # First search for current
            if child.view == self.__window.container.current:
                current_row = child
            # Init prev to first valid child
            elif prev_row is None and\
                    current_row is None and\
                    self.__filter_func(child):
                prev_row = child
            # Second search for next
            elif current_row is not None and self.__filter_func(child):
                prev_row = child
                break
        if prev_row is not None:
            self.__window.container.set_current(prev_row.view)

    def __get_index(self, view):
        """
            Get view index
            @param view as View
            @return int
        """
        # Search current index
        children = self.__box.get_children()
        index = 0
        for child in children:
            if child.view == view:
                break
            index += 1
        return index

    def __sort_func(self, row1, row2):
        """
            Sort listbox
            @param row1 as Row
            @param row2 as Row
        """
        return row2.view.webview.atime > row1.view.webview.atime

    def __filter_func(self, row):
        """
            Filter list based on current filter
            @param row as Row
        """
        filter = self.__search_entry.get_text()
        if not filter:
            return True
        uri = row.view.webview.uri
        title = row.view.webview.title
        if (uri is not None and uri.find(filter) != -1) or\
                (title is not None and title.find(filter) != -1) or\
                (filter == "private://" and row.view.webview.ephemeral):
            return True
        return False

    def __on_search_changed(self, entry):
        """
            Update filter
            @param entry as Gtk.Entry
        """
        self.__box.invalidate_filter()

    def __on_button_press(self, widget, event):
        """
            Hide popover if visible
            @param widget as Gtk.Widget
            @param event as Gdk.EventButton
        """
        if event.type == Gdk.EventType._2BUTTON_PRESS:
            self.__window.container.add_webview(El().start_page,
                                                WindowType.FOREGROUND)
        return self.__window.close_popovers()

    def __on_key_press(self, widget, event):
        """
            If Esc, reset search
            Otherwise, we get an ugly frame
            @param widget as Gtk.SearchEntry
            @param event as Gdk.Event
        """
        if event.keyval == Gdk.KEY_Escape:
            self.__search_entry.set_text("")
            return True
