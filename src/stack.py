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

from eolie.define import El


class Stack(Gtk.EventBox):
    """
        Box linked to a Gtk.Stack
        Should be inherited by a class providing self._CHILD_CLASS
    """

    def __init__(self, window):
        """
            Init stack
            @param window as Window
        """
        Gtk.EventBox.__init__(self)
        self._window = window
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
        grid.add(self.__search_bar)
        self.__scrolled = Gtk.ScrolledWindow()
        self.__scrolled.set_vexpand(True)
        self.__scrolled.set_hexpand(True)
        self.__scrolled.show()
        self._viewport = Gtk.Viewport()
        self._viewport.show()
        self.__scrolled.add(self._viewport)
        self.set_hexpand(False)
        grid.add(self.__scrolled)
        self.add(grid)

    def add_child(self, view):
        """
            Add child to sidebar
            @param view as WebView
            @return child
        """
        child = self._CHILD_CLASS(view, self._window)
        child.connect("moved", self.__on_moved)
        child.show()

        # We want to insert child next to its parent and brothers
        wanted_index = -1
        i = 1
        for row in self._box.get_children():
            if row.view == view.parent or (view.parent is not None and
                                           row.view.parent == view.parent):
                wanted_index = i
            i += 1
        self._box.insert(child, wanted_index)
        return child

    def update_visible_child(self):
        """
            Mark current child as visible
            Unmark all others
        """
        visible = self._window.container.current
        for child in self._box.get_children():
            if child.view.webview.ephemeral:
                class_name = "sidebar-item-selected-private"
            else:
                class_name = "sidebar-item-selected"
            if child.view == visible:
                child.get_style_context().add_class(class_name)
                # Wait loop empty: will fails otherwise if child just created
                GLib.idle_add(self.__scroll_to_child, child)
            else:
                child.get_style_context().remove_class(class_name)

    def destroy(self):
        """
            Destroy widget and child
        """
        # We force child to disconnect from view
        for child in self._box.get_children():
            child.disconnect_signals()
            child.destroy()
        Gtk.EventBox.destroy(self)

    def set_filtered(self, b):
        """
            Show filtering widget
            @param b as bool
        """
        if b:
            if self._window.is_fullscreen:
                height = self._window.toolbar.get_allocated_height()
                self.__search_bar.set_margin_top(height)
            else:
                self.__search_bar.set_margin_top(0)
            self.__search_bar.show()
            self.__search_entry.grab_focus()
            self.__search_entry.connect("key-press-event",
                                        self.__on_key_press)
            self._box.set_filter_func(self.__filter_func)
            for child in self._box.get_children():
                child.show_title(True)
        else:
            self.__search_bar.hide()
            self.__search_entry.disconnect_by_func(self.__on_key_press)
            self._box.set_filter_func(None)
            for child in self._box.get_children():
                child.show_title(self.__panel_mode != 2)
        self.__search_bar.set_search_mode(b)

    def next(self):
        """
            Show next view
        """
        children = self._box.get_children()
        index = self.__get_index(self._window.container.current)
        if index + 1 < len(children):
            next_row = self._get_child_at_index(index + 1)
        else:
            next_row = self._get_child_at_index(0)
        if next_row is not None:
            self._window.container.set_visible_view(next_row.view)
        self.update_visible_child()
        panel_mode = El().settings.get_enum("panel-mode")
        if panel_mode == 3:
            self._window.container.set_expose(True)

    def previous(self):
        """
            Show next view
        """
        children = self._box.get_children()
        index = self.__get_index(self._window.container.current)
        if index == 0:
            next_row = self._get_child_at_index(len(children) - 1)
        else:
            next_row = self._get_child_at_index(index - 1)
        if next_row is not None:
            self._window.container.set_visible_view(next_row.view)
        self.update_visible_child()
        panel_mode = El().settings.get_enum("panel-mode")
        if panel_mode == 3:
            self._window.container.set_expose(True)

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
        pass

    @property
    def panel_mode(self):
        """
            Get current panel mode
            @return int
        """
        return 0

    @property
    def views(self):
        """
            Get views ordered
            @return [View]
        """
        views = []
        for child in self._box.get_children():
            views.append(child.view)
        return views

#######################
# PROTECTED           #
#######################

#######################
# PRIVATE             #
#######################
    def __close_view(self, view):
        """
            close current view
            @param view as View
        """
        count = len(self._window.container.views)
        El().history.set_page_state(view.webview.get_uri())
        self._window.close_popovers()
        # Needed to unfocus titlebar
        self._window.set_focus(None)
        was_current = view == self._window.container.current
        child_index = self.__get_index(view)
        # Delay view destroy to allow stack animation
        child = self._get_child_at_index(child_index)
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
        for child in reversed(self._box.get_children()):
            if child.view != view and (
                    child.view.parent == view.parent or
                    child.view.parent == view):
                brother = child
                break
        # Load brother
        if brother is not None:
            brother_index = self.__get_index(brother.view)
            next_row = self._get_child_at_index(brother_index)
        # Go back to parent page
        elif view.parent is not None:
            parent_index = self.__get_index(view.parent)
            next_row = self._get_child_at_index(parent_index)
        # Find best near page
        else:
            children = self._box.get_children()
            # We are last row, add a new one
            if len(children) == 0:
                self._window.container.add_webview(El().start_page,
                                                   Gdk.WindowType.CHILD)
            # We have rows before closed
            elif child_index - 1 >= 0:
                next_row = self._get_child_at_index(child_index - 1)
            # We have rows next to closed, so reload current index
            elif child_index < len(children):
                next_row = self._get_child_at_index(child_index)
        if next_row is not None:
            self._window.container.set_visible_view(next_row.view)
        self.update_visible_child()
        self._window.toolbar.actions.count_label.set_text(str(count - 1))

    def __scroll_to_child(self, row):
        """
            Scroll to row
            @param row as Row
        """
        adj = self.__scrolled.get_vadjustment().get_value()
        coordinates = row.translate_coordinates(self._box, 0, 0)
        if coordinates is None:
            return
        y = coordinates[1]
        if y + row.get_allocated_height() >\
                self.__scrolled.get_allocated_height() + adj or\
                y - row.get_allocated_height() < 0 + adj:
            self.__scrolled.get_vadjustment().set_value(y)

    def __get_index(self, view):
        """
            Get view index
            @param view as View
            @return int
        """
        # Search current index
        children = self._box.get_children()
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
        children = self._box.get_children()
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

    def __on_search_changed(self, entry):
        """
            Update filter
            @param entry as Gtk.Entry
        """
        self._box.invalidate_filter()

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
                dialog.set_transient_for(self._window)
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
            @param child as StackSidebarChild
            @param view_str as str
            @param up as bool
        """
        view_index = self.__get_index_for_string(view_str)
        row = self._get_child_at_index(view_index)
        if row is None:
            return
        self._box.remove(row)
        child_index = self.__get_index(child.view)
        if not up:
            child_index += 1
        self._box.insert(row, child_index)

    def __on_button_press(self, widget, event):
        """
            Hide popover if visible
            @param widget as Gtk.Widget
            @param event as Gdk.EventButton
        """
        self._window.close_popovers()
        if event.type == Gdk.EventType._2BUTTON_PRESS:
            self._window.container.add_webview(El().start_page,
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
            self._window.toolbar.actions.filter_button.set_active(False)
            return True

    def __on_child_activated(self, listbox, row):
        """
            Show wanted web view
            @param listbox as Gtk.ListBox
            @param row as StackSidebarChild
        """
        self._window.container.set_visible_view(row.view)
        self.update_visible_child()
