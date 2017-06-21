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

from gi.repository import Gtk, Gdk, GLib, Gio

from gettext import gettext as _

from eolie.define import El, ArtSize
from eolie.stacksidebar_child import SidebarChild


class StackSidebar(Gtk.EventBox):
    """
        Sidebar linked to a Window Gtk.Stack
    """

    def __init__(self, window):
        """
            Init sidebar
            @param window as Window
        """
        Gtk.EventBox.__init__(self)
        try:
            system = Gio.Settings.new("org.gnome.desktop.interface")
            self.__animate = system.get_value("enable-animations")
        except:
            self.__animate = False
        self.__animation_cancel = Gio.Cancellable()
        self.__leave_timeout_id = None
        self.__window = window
        self.get_style_context().add_class("sidebar")
        self.connect("button-press-event", self.__on_button_press)
        grid = Gtk.Grid()
        grid.set_orientation(Gtk.Orientation.VERTICAL)
        grid.show()
        self.__search_entry = Gtk.SearchEntry.new()
        self.__search_entry.connect("search-changed", self._on_search_changed)

        self.__search_entry.show()
        self.__search_bar = Gtk.SearchBar.new()
        self.__search_bar.add(self.__search_entry)
        grid.add(self.__search_bar)
        self.__scrolled = Gtk.ScrolledWindow()
        self.__scrolled.set_vexpand(True)
        self.__scrolled.show()
        self.__listbox = Gtk.ListBox.new()
        self.__listbox.set_activate_on_single_click(True)
        self.__listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.__listbox.show()
        self.__listbox.connect("row_activated", self.__on_row_activated)
        self.__scrolled.add(self.__listbox)
        self.set_hexpand(False)
        grid.add(self.__scrolled)
        self.add(grid)
        self.set_panel_mode()

    def add_child(self, view, window_type):
        """
            Add child to sidebar
            @param view as WebView
            @param window_type as Gdk.WindowType
        """
        child = SidebarChild(view, self.__window)
        self.__set_child_height(child)
        child.connect("moved", self.__on_moved)
        if self.__panel_mode == 2:
            child.show_title(False)
        child.show()

        if window_type == Gdk.WindowType.CHILD:
            # We want to insert child next to its parent and brothers
            wanted_index = 1
            i = 1
            for row in self.__listbox.get_children():
                if row.view == view.parent or (view.parent is not None and
                                               row.view.parent == view.parent):
                    wanted_index = i
                i += 1
            self.__listbox.insert(child, wanted_index)
        else:
            self.__listbox.insert(child, -1)

    def update_visible_child(self):
        """
            Mark current child as visible
            Unmark all others
        """
        visible = self.__window.container.current
        for child in self.__listbox.get_children():
            if child.view.webview.ephemeral:
                class_name = "sidebar-item-selected-private"
            else:
                class_name = "sidebar-item-selected"
            if child.view == visible:
                child.get_style_context().add_class(class_name)
                # Wait loop empty: will fails otherwise if child just created
                GLib.idle_add(self.__scroll_to_row, child)
            else:
                child.get_style_context().remove_class(class_name)

    def set_filtered(self, b):
        """
            Show filtering widget
            @param b as bool
        """
        if b:
            if self.__window.toolbar.lock_focus and\
                    self.__window.is_fullscreen:
                height = self.__window.toolbar.get_allocated_height()
                self.__search_bar.set_margin_top(height)
            else:
                self.__search_bar.set_margin_top(0)
            self.__search_bar.show()
            self.__search_entry.grab_focus()
            self.__search_entry.connect("key-press-event",
                                        self.__on_key_press)
            self.__listbox.set_filter_func(self.__filter_func)
            for child in self.__listbox.get_children():
                child.show_title(True)
        else:
            self.__search_bar.hide()
            self.__search_entry.disconnect_by_func(self.__on_key_press)
            self.__listbox.set_filter_func(None)
            for child in self.__listbox.get_children():
                child.show_title(self.__panel_mode)
        self.__search_bar.set_search_mode(b)

    def next(self):
        """
            Show next view
        """
        children = self.__listbox.get_children()
        index = self.__get_index(self.__window.container.current)
        if index + 1 < len(children):
            next_row = self.__listbox.get_row_at_index(index + 1)
        else:
            next_row = self.__listbox.get_row_at_index(0)
        if next_row is not None:
            self.__window.container.set_visible_view(next_row.view)
        self.update_visible_child()

    def previous(self):
        """
            Show next view
        """
        children = self.__listbox.get_children()
        index = self.__get_index(self.__window.container.current)
        if index == 0:
            next_row = self.__listbox.get_row_at_index(len(children) - 1)
        else:
            next_row = self.__listbox.get_row_at_index(index - 1)
        if next_row is not None:
            self.__window.container.set_visible_view(next_row.view)
        self.update_visible_child()

    def close_view(self, view):
        """
            Ask user before closing view if forms filled
            @param view as View
        """
        page_id = view.webview.get_page_id()
        El().helper.call("FormsFilled",
                         GLib.Variant("(i)", (page_id,)),
                         self.__on_forms_filled, view, page_id)

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
        for child in self.__listbox.get_children():
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
    def _on_search_changed(self, entry):
        """
            Update filter
            @param entry as Gtk.Entry
        """
        self.__listbox.invalidate_filter()

#######################
# PRIVATE             #
#######################
    def __close_view(self, view):
        """
            close current view
            @param view as View
        """
        El().history.set_page_state(view.webview.get_uri())
        self.__window.toolbar.title.close_popover()
        # Needed to unfocus titlebar
        self.__window.set_focus(None)
        was_current = view == self.__window.container.current
        child_index = self.__get_index(view)
        # Delay view destroy to allow stack animation
        child = self.__listbox.get_row_at_index(child_index)
        if child is None:
            return
        El().pages_menu.add_action(view.webview.get_title(),
                                   view.webview.get_uri(),
                                   view.webview.ephemeral,
                                   view.webview.get_session_state())
        GLib.timeout_add(1000, view.destroy)
        child.destroy()
        # Nothing to do if was not current page
        if not was_current:
            return False
        next_row = None

        # First we search a child with same parent as closed
        brother = None
        for child in reversed(self.__listbox.get_children()):
            if view.parent is not None and\
                    child.view != view and\
                    child.view.parent == view.parent:
                brother = child
                break
        # Load brother
        if brother is not None:
            brother_index = self.__get_index(brother.view)
            next_row = self.__listbox.get_row_at_index(brother_index)
        # Go back to parent page
        elif view.parent is not None:
            parent_index = self.__get_index(view.parent)
            next_row = self.__listbox.get_row_at_index(parent_index)
        # Find best near page
        else:
            children = self.__listbox.get_children()
            # We are last row, add a new one
            if len(children) == 0:
                self.__window.container.add_webview(El().start_page,
                                                    Gdk.WindowType.CHILD)
            # We have rows before closed
            elif child_index - 1 >= 0:
                next_row = self.__listbox.get_row_at_index(child_index - 1)
            # We have rows next to closed, so reload current index
            elif child_index < len(children):
                next_row = self.__listbox.get_row_at_index(child_index)
        if next_row is not None:
            self.__window.container.set_visible_view(next_row.view)
        self.update_visible_child()

    def __set_child_height(self, child):
        """
            Set child height
            @param child as SidebarChild
        """
        if self.__panel_mode == 0:
            child.set_preview_height(ArtSize.PREVIEW_HEIGHT)
            child.set_snapshot(True)
        else:
            child.set_preview_height(None)
            child.clear_snapshot()

    def __scroll_to_row(self, row):
        """
            Scroll to row
            @param row as Row
        """
        scrolled = self.__listbox.get_ancestor(Gtk.ScrolledWindow)
        if scrolled is None:
            return
        adj = scrolled.get_vadjustment().get_value()
        coordinates = row.translate_coordinates(self.__listbox, 0, 0)
        if coordinates is None:
            return
        y = coordinates[1]
        if y + row.get_allocated_height() >\
                scrolled.get_allocated_height() + adj or\
                y - row.get_allocated_height() < 0 + adj:
            scrolled.get_vadjustment().set_value(y)

    def __get_index(self, view):
        """
            Get view index
            @param view as View
            @return int
        """
        # Search current index
        children = self.__listbox.get_children()
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
        children = self.__listbox.get_children()
        index = 0
        for child in children:
            if str(child.view) == view_str:
                break
            index += 1
        return index

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
                (title is not None and title.find(filter) != -1):
            return True
        return False

    def __on_forms_filled(self, source, result, view):
        """
            Ask user to close view, if ok, close view
            @param source as GObject.Object
            @param result as Gio.AsyncResult
            @param view as View
        """
        def on_response_id(dialog, response_id, view, self):
            if response_id == Gtk.ResponseType.CLOSE:
                self.__close_view(view)
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
                self.__close_view(view)
        except Exception as e:
            self.__close_view(view)
            print("StackSidebar::__on_forms_filled():", e)

    def __on_moved(self, child, view_str, up):
        """
            Move child row
            @param child as SidebarChild
            @param view_str as str
            @param up as bool
        """
        view_index = self.__get_index_for_string(view_str)
        row = self.__listbox.get_row_at_index(view_index)
        if row is None:
            return
        self.__listbox.remove(row)
        child_index = self.__get_index(child.view)
        if not up:
            child_index += 1
        self.__listbox.insert(row, child_index)

    def __on_button_press(self, widget, event):
        """
            Hide popover if visible
            @param widget as Gtk.Widget
            @param event as Gdk.EventButton
        """
        self.__window.toolbar.title.close_popover()
        if event.type == Gdk.EventType._2BUTTON_PRESS:
            self.__window.container.add_webview(El().start_page,
                                                Gdk.WindowType.CHILD)

    def __on_key_press(self, widget, event):
        """
            If Esc, hide widget, why GTK doesn't do that?
            Otherwise, we get an ugly frame
            @param widget as Gtk.SearchEntry
            @param event as Gdk.Event
        """
        if event.keyval == Gdk.KEY_Escape:
            self.__search_entry.set_text("")
            self.__window.toolbar.actions.filter_button.set_active(False)
            return True

    def __on_row_activated(self, listbox, row):
        """
            Show wanted web view
            @param listbox as Gtk.ListBox
            @param row as SidebarChild
        """
        self.__window.container.set_visible_view(row.view)
        self.update_visible_child()
