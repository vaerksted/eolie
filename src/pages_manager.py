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

from eolie.define import El, PanelMode


class PagesManager(Gtk.EventBox):
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
        self.__next_timeout_id = None
        self.__previous_timeout_id = None
        self.get_style_context().add_class("sidebar")
        self.connect("button-press-event", self.__on_button_press)
        self._grid = Gtk.Grid()
        self._grid.set_orientation(Gtk.Orientation.VERTICAL)
        self._grid.show()
        self.__search_entry = Gtk.SearchEntry.new()
        self.__search_entry.connect("search-changed", self.__on_search_changed)

        self.__search_entry.show()
        self._search_bar = Gtk.SearchBar.new()
        self._search_bar.add(self.__search_entry)
        self._scrolled = Gtk.ScrolledWindow()
        self._scrolled.set_vexpand(True)
        self._scrolled.set_hexpand(True)
        self._scrolled.show()
        self._viewport = Gtk.Viewport()
        self._viewport.show()
        self._scrolled.add(self._viewport)
        self.set_hexpand(False)
        self.add(self._grid)

    def add_child(self, view):
        """
            Add child to sidebar
            @param view as View
            @return child
        """
        child = self._CHILD_CLASS(view, self._window, False)
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
        uri = view.webview.get_uri()
        if uri:
            child.update()
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
            child.destroy()
        Gtk.EventBox.destroy(self)

    def search_grab_focus(self):
        """
            Grab focus on search entry
        """
        self.__search_entry.grab_focus()

    def set_filtered(self, b):
        """
            Show filtering widget
            @param b as bool
        """
        panel_mode = El().settings.get_enum("panel-mode")
        if b and not self._search_bar.is_visible():
            if self._window.is_fullscreen and panel_mode != PanelMode.NONE:
                height = self._window.toolbar.get_allocated_height()
                self._search_bar.set_margin_top(height)
            else:
                self._search_bar.set_margin_top(0)
            self._search_bar.show()
            self.__search_entry.grab_focus()
            self.__search_entry.connect("key-press-event",
                                        self.__on_key_press)
            self._box.set_filter_func(self.__filter_func)
            for child in self._box.get_children():
                child.show_title(True)
        elif self._search_bar.is_visible():
            self._search_bar.hide()
            self.__search_entry.disconnect_by_func(self.__on_key_press)
            self._box.set_filter_func(None)
            for child in self._box.get_children():
                child.show_title(panel_mode != PanelMode.MINIMAL)
        self._search_bar.set_search_mode(b)

    def next(self):
        """
            Show next view
        """
        panel_mode = El().settings.get_enum("panel-mode")
        if panel_mode == PanelMode.NONE and\
                self.__next_timeout_id is None and\
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
        panel_mode = El().settings.get_enum("panel-mode")
        if panel_mode == PanelMode.NONE and\
                self.__previous_timeout_id is None and\
                self.__previous_timeout_id != -1:
            self.__previous_timeout_id = GLib.timeout_add(100,
                                                          self.__set_expose,
                                                          self.__previous)
        else:
            self.__previous()

    def close_view(self, view):
        """
            Ask user before closing view if forms filled
            @param view as View
        """
        page_id = view.webview.get_page_id()
        El().helper.call("FormsFilled",
                         GLib.Variant("(i)", (page_id,)),
                         self.__on_forms_filled, page_id, view)

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

    def move_first(self, view):
        """
            Move view at first position
            @param view as View
        """
        pass

    def set_panel_mode(self):
        """
            Set panel mode
        """
        pass

    @property
    def children(self):
        """
            Get views ordered
            @return [PagesManagerChild]
        """
        return self._box.get_children()

#######################
# PROTECTED           #
#######################
    def _on_moved(self, child, view_str, up):
        """
            Move child row
            @param child as PagesManagerChild
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
        self._window.container.set_expose(True)
        callback()

    def __next(self):
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

    def __previous(self):
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

    def __close_view(self, view):
        """
            close current view
            @param view as View
        """
        children_count = len(self._box.get_children()) - 1
        # Don't show 0 as we are going to open a new one
        if children_count:
            self._window.toolbar.actions.count_label.set_text(
                                                       str(children_count))
        El().history.set_page_state(view.webview.get_uri())
        self._window.close_popovers()
        # Needed to unfocus titlebar
        self._window.set_focus(None)
        was_current = view == self._window.container.current
        child_index = self.__get_index(view)
        child = self._get_child_at_index(child_index)
        if child is None:
            return
        El().pages_menu.add_action(view.webview.get_title(),
                                   view.webview.get_uri(),
                                   view.webview.ephemeral,
                                   view.webview.get_session_state())
        child.destroy()
        # Delay view destroy to allow stack animation
        GLib.timeout_add(1000, view.destroy)
        # Nothing to do if was not current page
        if not was_current:
            return False

        # First we search a child with same parent as closed
        brother = None
        if view.parent is not None:
            for child in reversed(self._box.get_children()):
                if child.view != view and child.view.parent == view.parent:
                    brother = child
                    break
        next_view = None
        # Load brother
        if brother is not None:
            brother_index = self.__get_index(brother.view)
            next_view = self._get_child_at_index(brother_index).view
        # Go back to parent page
        elif view.parent is not None:
            parent_index = self.__get_index(view.parent)
            next_view = self._get_child_at_index(parent_index).view
        else:
            # We are last row, add a new one
            if children_count == 0:
                self._window.container.add_webview(El().start_page,
                                                   Gdk.WindowType.CHILD)
            # Find last activated page
            else:
                atime = 0
                for child in self._box.get_children():
                    if child.view != view and\
                            child.view.webview.access_time >= atime:
                        next_view = child.view
                        atime = next_view.webview.access_time
        if next_view is not None:
            self._window.container.set_visible_view(next_view)
        self.update_visible_child()

    def __scroll_to_child(self, row):
        """
            Scroll to row
            @param row as Row
        """
        adj = self._scrolled.get_vadjustment()
        if adj is None:
            return
        value = adj.get_value()
        coordinates = row.translate_coordinates(self._box, 0, 0)
        if coordinates is None:
            return
        y = coordinates[1]
        if y + row.get_allocated_height() >\
                self._scrolled.get_allocated_height() + value or\
                y - row.get_allocated_height() < 0 + value:
            self._scrolled.get_vadjustment().set_value(y)

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
            print("PagesManager::__on_forms_filled():", e)

    def __on_button_press(self, widget, event):
        """
            Hide popover if visible
            @param widget as Gtk.Widget
            @param event as Gdk.EventButton
        """
        if event.type == Gdk.EventType._2BUTTON_PRESS:
            self._window.container.add_webview(El().start_page,
                                               Gdk.WindowType.CHILD)
        return self._window.close_popovers()

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
