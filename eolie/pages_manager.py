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

from gettext import gettext as _

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

    def add_child(self, view):
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

    def try_close_view(self, view):
        """
            Ask user before closing view if forms filled
            @param view as View
        """
        page_id = view.webview.get_page_id()
        El().helper.call("FormsFilled",
                         GLib.Variant("(i)", (page_id,)),
                         self.__on_forms_filled, page_id, view)

    def close_view(self, view):
        """
            close current view
            @param view as View
            @param animate as bool
        """
        children_count = len(self.__box.get_children()) - 1
        # Don't show 0 as we are going to open a new one
        if children_count:
            El().update_unity_badge()
            self.__window.toolbar.actions.count_label.set_text(
                                                       str(children_count))
        El().history.set_page_state(view.webview.get_uri())
        self.__window.close_popovers()
        # Needed to unfocus titlebar
        self.__window.set_focus(None)
        was_current = view == self.__window.container.current
        child_index = self.__get_index(view)
        child = self.__box.get_child_at_index(child_index)
        if child is None:
            return
        gtime = child.view.webview.gtime
        El().pages_menu.add_action(view.webview.get_title(),
                                   view.webview.get_uri(),
                                   view.webview.ephemeral,
                                   view.webview.get_session_state())
        child.destroy()
        # Nothing to do if was not current page
        if not was_current:
            return False

        next_view = None
        reversed_children = reversed(self.__box.get_children())
        # First we search a brother ie a paged opened from the same parent page
        for child in reversed_children:
            if child.view.webview.gtime == gtime:
                next_view = child.view
                break
        # Get view with gtime -+ 1
        # If closing a parent, go to child
        # If closing a child, go to parent
        if next_view is None:
            for child in reversed_children:
                if child.view.webview.gtime == gtime + 1 or\
                        child.view.webview.gtime == gtime - 1:
                    next_view = child.view
                    break
        # Get view with higher access time
        if next_view is None:
            atime = 0
            for child in self.__box.get_children():
                if child.view.webview.atime > atime:
                    next_view = child.view
                    atime = child.view.webview.atime
        if next_view is not None:
            self.__window.container.set_current(next_view, True)
        else:
            # We are last row, add a new one
            self.__window.container.add_webview(El().start_page,
                                                WindowType.FOREGROUND)

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

    def __get_index_for_string(self, view_str):
        """
            Get view index for str
            @param view_str as str
            @return int
        """
        # Search current index
        children = self.__box.get_children()
        index = 0
        for child in children:
            if str(child.view) == view_str:
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
        uri = row.view.webview.get_uri()
        title = row.view.webview.get_title()
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

    def __on_forms_filled(self, source, result, view):
        """
            Ask user to close view, if ok, close view
            @param source as GObject.Object
            @param result as Gio.AsyncResult
            @param view as View
        """
        def on_response_id(dialog, response_id, view, self):
            if response_id == Gtk.ResponseType.CLOSE:
                self.close_view(view)
            dialog.destroy()

        def on_close(widget, dialog):
            dialog.response(Gtk.ResponseType.CLOSE)

        def on_cancel(widget, dialog):
            dialog.response(Gtk.ResponseType.CANCEL)

        try:
            result = source.call_finish(result)[0]
            if result:
                builder = Gtk.Builder()
                builder.add_from_resource("/org/gnome/Eolie/QuitDialog.ui")
                dialog = builder.get_object("dialog")
                label = builder.get_object("label")
                close = builder.get_object("close")
                cancel = builder.get_object("cancel")
                label.set_text(_("Do you really want to close this page?"))
                dialog.set_transient_for(self.__window)
                dialog.connect("response", on_response_id, view, self)
                close.connect("clicked", on_close, dialog)
                cancel.connect("clicked", on_cancel, dialog)
                dialog.run()
            else:
                self.close_view(view)
        except:
            self.close_view(view)

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
