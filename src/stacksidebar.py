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

from gi.repository import Gtk, Gdk, Gio, GLib, GObject, WebKit2, Pango
import cairo

from eolie.define import El, ArtSize
from eolie.utils import resize_favicon, get_favicon_best_uri


class SidebarChild(Gtk.ListBoxRow):
    """
        A Sidebar Child
    """

    __gsignals__ = {
        'moved': (GObject.SignalFlags.RUN_FIRST, None, (str, bool))
    }

    def __init__(self, view, window):
        """
            Init child
            @param view as View
            @param window as Window
        """
        Gtk.ListBoxRow.__init__(self)
        self.__scroll_timeout_id = None
        self.__start_uri = None
        self.__view = view
        self.__window = window
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/SidebarChild.ui")
        builder.connect_signals(self)
        self.__overlay = builder.get_object("overlay")
        self.__grid = builder.get_object("grid")
        self.__title = builder.get_object("title")
        self.__image = builder.get_object("image")
        self.__image_close = builder.get_object("image_close")
        if view.webview.private:
            self.__image_close.set_from_icon_name("window-close-symbolic",
                                                  Gtk.IconSize.INVALID)
        else:
            self.__image_close.set_from_icon_name("applications-internet",
                                                  Gtk.IconSize.INVALID)
        self.__image_close.set_property("pixel-size", ArtSize.FAVICON)
        self.__spinner = builder.get_object("spinner")
        self.__title.set_label("Empty page")
        self.add(builder.get_object("widget"))
        view.webview.connect("notify::favicon", self.__on_notify_favicon)
        view.webview.connect("scroll-event", self.__on_scroll_event)
        view.webview.connect("uri-changed", self.__on_uri_changed)
        view.webview.connect("title-changed", self.__on_title_changed)
        view.webview.connect("load-changed", self.__on_load_changed)
        self.get_style_context().add_class("sidebar-item")

        self.drag_source_set(Gdk.ModifierType.BUTTON1_MASK, [],
                             Gdk.DragAction.MOVE)
        self.drag_source_add_text_targets()
        self.connect("drag-begin", self.__on_drag_begin)
        self.connect("drag-data-get", self.__on_drag_data_get)
        self.drag_dest_set(Gtk.DestDefaults.DROP | Gtk.DestDefaults.MOTION,
                           [], Gdk.DragAction.MOVE)
        self.drag_dest_add_text_targets()
        self.connect("drag-data-received", self.__on_drag_data_received)
        self.connect("drag-motion", self.__on_drag_motion)
        self.connect("drag-leave", self.__on_drag_leave)

    @property
    def view(self):
        """
            Get linked view
            @return View
        """
        return self.__view

    def show_title(self, b):
        """
            Show page title
            @param b as bool
        """
        if b:
            self.__title.show()
            self.__image_close.set_hexpand(False)
        else:
            self.__title.hide()
            self.__image_close.set_hexpand(True)

    def set_preview_height(self, height):
        """
            Set child preview height
            @param height as int
        """
        if height is None:
            ctx = self.__title.get_pango_context()
            layout = Pango.Layout.new(ctx)
            height = int(layout.get_pixel_size()[1]) + 10
            self.__grid.set_property("valign", Gtk.Align.CENTER)
            self.__spinner.hide()
        else:
            self.__grid.set_property("valign", Gtk.Align.END)
            self.__spinner.show()
        self.__overlay.set_size_request(-1, height)

    def set_snapshot(self, save):
        """
            Set webpage preview
            @param save as bool
        """
        if El().settings.get_value("panel-mode").get_string() != "preview":
            pass
        elif self.__view.webview.private:
            self.__image.set_from_icon_name(
                                         "user-not-tracked-symbolic",
                                         Gtk.IconSize.DIALOG)
        else:
            self.__view.webview.get_snapshot(
                                         WebKit2.SnapshotRegion.VISIBLE,
                                         WebKit2.SnapshotOptions.NONE,
                                         None,
                                         self.__on_snapshot,
                                         save)

    def clear_snapshot(self):
        """
            Get snapshot
            @return Gtk.Image
        """
        if self.__image is not None:
            self.__image.clear()

#######################
# PROTECTED           #
#######################
    def _on_button_press_event(self, button, event):
        """
            Hide popover or close view
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        if event.button == 2:
            self.__window.container.sidebar.close_view(self.__view)

    def _on_close_button_press_event(self, eventbox, event):
        """
            Destroy self
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        self.__window.container.sidebar.close_view(self.__view)

    def _on_enter_notify_event(self, eventbox, event):
        """
            Show close button
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        self.__image_close.set_from_icon_name("window-close-symbolic",
                                              Gtk.IconSize.INVALID)
        self.__image_close.get_style_context().add_class("sidebar-item-close")

    def _on_leave_notify_event(self, eventbox, event):
        """
            Show close button
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        allocation = eventbox.get_allocation()
        if event.x <= 0 or\
           event.x >= allocation.width or\
           event.y <= 0 or\
           event.y >= allocation.height:
            self.__image_close.get_style_context().remove_class(
                                                          "sidebar-item-close")
            self.__set_favicon()

#######################
# PRIVATE             #
#######################
    def __set_favicon(self):
        """
            Set favicon
        """
        if self.__view.webview.private:
            self.__image_close.set_from_icon_name("user-not-tracked-symbolic",
                                                  Gtk.IconSize.INVALID)
            return
        uri = self.__view.webview.get_uri()
        favicon_db = self.__view.webview.get_context().get_favicon_database()
        favicon_uri = get_favicon_best_uri(uri)
        if favicon_uri is None:
            if uri == "populars://":
                self.__image_close.set_from_icon_name("emote-love-symbolic",
                                                      Gtk.IconSize.INVALID)
            else:
                self.__image_close.set_from_icon_name("applications-internet",
                                                      Gtk.IconSize.INVALID)
        else:
            favicon_db.get_favicon(favicon_uri, None,
                                   self.__set_favicon_result)

    def __set_favicon_result(self, db, result):
        """
            Set favicon db result
            @param db as WebKit2.FaviconDatabase
            @param result as Gio.AsyncResult
        """
        try:
            surface = db.get_favicon_finish(result)
        except:
            surface = None
        if surface is None:
            self.__image_close.set_from_icon_name("applications-internet",
                                                  Gtk.IconSize.INVALID)
        else:
            self.__image_close.set_from_surface(resize_favicon(surface))
            del surface
            self.__image_close.get_style_context().remove_class(
                                                          "sidebar-item-close")
            self.__image_close.show()

    def __set_snapshot_timeout(self):
        """
            Get snapshot timeout
        """
        self.__scroll_timeout_id = None
        self.set_snapshot(False)

    def __on_uri_changed(self, view, uri):
        """
            Update uri
            @param view as WebView
            @param uri as str
        """
        # We are not filtered and not in private mode
        if not self.__view.webview.private and\
                El().settings.get_value("panel-mode").get_string() ==\
                "preview" and\
                self.get_allocated_width() != 1:
            preview = El().art.get_artwork(uri,
                                           "preview",
                                           view.get_scale_factor(),
                                           self.get_allocated_width() -
                                           ArtSize.PREVIEW_WIDTH_MARGIN,
                                           ArtSize.PREVIEW_HEIGHT)
            if preview is not None:
                self.__image.set_from_surface(preview)
                del preview
        self.__set_favicon()

    def __on_title_changed(self, view, title):
        """
            Update title
            @param view as WebView
            @param title as str
        """
        self.__title.set_text(title)
        if not view.is_loading():
            GLib.timeout_add(500, self.set_snapshot, False)

    def __on_load_changed(self, view, event):
        """
            Update snapshot
            @param view as WebView
            @param event as WebKit2.LoadEvent
        """
        uri = view.get_uri()
        if event == WebKit2.LoadEvent.STARTED:
            self.__start_uri = view.get_uri()
            self.__spinner.start()
            self.__title.set_text(uri)
        elif event == WebKit2.LoadEvent.COMMITTED:
            self.__title.set_text(uri)
        elif event == WebKit2.LoadEvent.FINISHED:
            self.__spinner.stop()
            GLib.timeout_add(500, self.set_snapshot, True)

    def __on_scroll_event(self, view, event):
        """
            Update snapshot
            @param view as WebView
            @param event as WebKit2.Event
        """
        if self.__scroll_timeout_id is not None:
            GLib.source_remove(self.__scroll_timeout_id)
        self.__scroll_timeout_id = GLib.timeout_add(
                                                1000,
                                                self.__set_snapshot_timeout)

    def __on_snapshot(self, view, result, save):
        """
            Set snapshot on main image
            @param view as WebView
            @param result as Gio.AsyncResult
            @param save as bool
            @warning view here is WebKit2.WebView, not WebView
        """
        # We are filtered
        if self.get_allocated_width() == 1:
            return
        try:
            snapshot = view.get_snapshot_finish(result)
            factor = self.get_allocated_width() /\
                snapshot.get_width()
            surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                         self.get_allocated_width() -
                                         ArtSize.PREVIEW_WIDTH_MARGIN,
                                         ArtSize.PREVIEW_HEIGHT)
            context = cairo.Context(surface)
            context.scale(factor, factor)
            context.set_source_surface(snapshot, 0, 0)
            context.paint()
            self.__image.set_from_surface(surface)
            current_uri = view.get_uri()
            if save:
                El().art.save_artwork(current_uri,
                                      surface, "preview")
                if self.__start_uri is not None and\
                        current_uri != self.__start_uri:
                    El().art.save_artwork(self.__start_uri,
                                          surface, "preview")
                # Manage start page cache
                # We also cache original URI (for populars view)
                uris = [current_uri]
                if self.__start_uri is not None and\
                        self.__start_uri not in uris:
                    uris.append(self.__start_uri)
                surface = None
                for uri in uris:
                    if El().art.exists(uri, "start"):
                        continue
                    if surface is None:
                        height = snapshot.get_height()
                        factor = ArtSize.START_HEIGHT / height
                        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                                     ArtSize.START_WIDTH,
                                                     ArtSize.START_HEIGHT)
                        context = cairo.Context(surface)
                        context.scale(factor, factor)
                        context.set_source_surface(snapshot, 0, 0)
                        context.paint()
                    El().art.save_artwork(uri,
                                          surface, "start")
            del surface
            del snapshot
        except:
            pass
        self.__start_uri = None

    def __on_notify_favicon(self, view, pointer):
        """
            Set favicon
            @param view as WebView
            @param pointer as GParamPointer
        """
        self.__set_favicon()

    def __on_drag_begin(self, widget, context):
        """
            Set icon
            @param widget as Gtk.Widget
            @param context as Gdk.DragContext
        """
        surface = self.__image.get_property("surface")
        if surface is None:
            return
        pixbuf = Gdk.pixbuf_get_from_surface(surface,
                                             0, 0,
                                             surface.get_width(),
                                             surface.get_height())

        widget.drag_source_set_icon_pixbuf(pixbuf)
        del pixbuf

    def __on_drag_data_get(self, widget, context, data, info, time):
        """
            Send track id
            @param widget as Gtk.Widget
            @param context as Gdk.DragContext
            @param data as Gtk.SelectionData
            @param info as int
            @param time as int
        """
        name = str(self.__view)
        data.set_text(name, len(name))

    def __on_drag_data_received(self, widget, context, x, y, data, info, time):
        """
            Move track
            @param widget as Gtk.Widget
            @param context as Gdk.DragContext
            @param x as int
            @param y as int
            @param data as Gtk.SelectionData
            @param info as int
            @param time as int
        """
        height = self.get_allocated_height()
        if y > height/2:
            up = False
        else:
            up = True
        try:
            src_widget = data.get_text()
            self.emit("moved", src_widget, up)
        except:
            pass

    def __on_drag_motion(self, widget, context, x, y, time):
        """
            Add style
            @param widget as Gtk.Widget
            @param context as Gdk.DragContext
            @param x as int
            @param y as int
            @param time as int
        """
        height = self.get_allocated_height()
        if y > height/2:
            self.get_style_context().add_class("drag-up")
            self.get_style_context().remove_class("drag-down")
        else:
            self.get_style_context().remove_class("drag-up")
            self.get_style_context().add_class("drag-down")

    def __on_drag_leave(self, widget, context, time):
        """
            Remove style
            @param widget as Gtk.Widget
            @param context as Gdk.DragContext
            @param time as int
        """
        self.get_style_context().remove_class("drag-up")
        self.get_style_context().remove_class("drag-down")


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
        grid.add(self.__scrolled)
        self.add(grid)
        # Strange, this is needed but should not
        self.set_hexpand(False)
        self.connect("enter-notify-event", self.__on_enter_notify_event)
        self.connect("leave-notify-event", self.__on_leave_notify_event)
        self.__set_panel_mode()
        panel_mode = El().settings.get_enum("panel-mode")
        self.__panel_action = Gio.SimpleAction.new_stateful(
                                                 "panel_mode",
                                                 GLib.VariantType.new("i"),
                                                 GLib.Variant("i", panel_mode))
        self.__panel_action.connect("activate",
                                    self.__on_panel_mode_active)
        self.__window.add_action(self.__panel_action)

    def add_child(self, view):
        """
            Add child to sidebar
            @param view as WebView
        """
        child = SidebarChild(view, self.__window)
        self.__set_child_height(child)
        child.connect("moved", self.__on_moved)
        if El().settings.get_value("panel-mode").get_string() == "minimal":
            child.show_title(False)
        child.show()
        # We want to insert child next to its parent and brothers
        wanted_index = 1
        i = 1
        for row in self.__listbox.get_children():
            if row.view == view.parent or (view.parent is not None and
                                           row.view.parent == view.parent):
                wanted_index = i
            i += 1
        self.__listbox.insert(child, wanted_index)

    def update_visible_child(self):
        """
            Mark current child as visible
            Unmark all others
        """
        visible = self.__window.container.current
        for child in self.__listbox.get_children():
            if child.view.webview.private:
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
            panel_mode = El().settings.get_enum("panel-mode")
            for child in self.__listbox.get_children():
                child.show_title(panel_mode != 2)
        self.__search_bar.set_search_mode(b)

    def next(self):
        """
            Show next view
        """
        children = self.__listbox.get_children()
        index = self.__get_index(str(self.__window.container.current))
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
        index = self.__get_index(str(self.__window.container.current))
        if index == 0:
            next_row = self.__listbox.get_row_at_index(len(children) - 1)
        else:
            next_row = self.__listbox.get_row_at_index(index - 1)
        if next_row is not None:
            self.__window.container.set_visible_view(next_row.view)
        self.update_visible_child()

    def close_view(self, view):
        """
            close current view
            @param view as View
            @return child SidebarChild
        """
        self.__window.toolbar.title.close_popover()
        # Needed to unfocus titlebar
        self.__window.set_focus(None)
        was_current = view == self.__window.container.current
        child_index = self.__get_index(str(view))
        # Delay view destroy to allow stack animation
        child = self.__listbox.get_row_at_index(child_index)
        if child is None:
            return
        El().pages_menu.add_action(view.webview.get_title(),
                                   view.webview.get_uri(),
                                   view.webview.private,
                                   view.webview.get_session_state())
        GLib.timeout_add(1000, view.destroy)
        child.destroy()
        # Nothing to do if was not current page
        if not was_current:
            return
        next_row = None

        # First we search a child with same parent as closed
        brother = None
        for child in self.__listbox.get_children():
            if view.parent is not None and\
                    child.view != view and\
                    child.view.parent == view.parent:
                brother = child
                break
        # Load brother
        if brother is not None:
            brother_index = self.__get_index(str(brother.view))
            next_row = self.__listbox.get_row_at_index(brother_index)
        # Go back to parent page
        elif view.parent is not None:
            parent_index = self.__get_index(str(view.parent))
            next_row = self.__listbox.get_row_at_index(parent_index)
        # Find best near page
        else:
            children = self.__listbox.get_children()
            # We are last row, add a new one
            if len(children) == 0:
                self.__window.container.add_web_view(El().start_page, True)
            # We have rows next to closed, so reload current index
            elif child_index < len(children):
                next_row = self.__listbox.get_row_at_index(child_index)
            # We have rows before closed
            elif child_index - 1 >= 0:
                next_row = self.__listbox.get_row_at_index(child_index - 1)
        if next_row is not None:
            self.__window.container.set_visible_view(next_row.view)
        self.update_visible_child()

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
    def __set_panel_mode(self):
        """
            Set panel mode
        """
        panel_mode = El().settings.get_enum("panel-mode")
        if panel_mode == 2:
            self.set_property("width-request", -1)
        else:
            self.set_property("width-request", ArtSize.PREVIEW_WIDTH)
        for child in self.__listbox.get_children():
            child.show_title(panel_mode != 2)
            self.__set_child_height(child)
        # We need to delay update to allow widget to resize
        if self.__window.container is not None:
            GLib.timeout_add(
                         250,
                         self.__window.container.update_children_allocation)

    def __set_child_height(self, child):
        """
            Set child height
            @param child as SidebarChild
        """
        if El().settings.get_value("panel-mode").get_string() == "preview":
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
        y = row.translate_coordinates(self.__listbox, 0, 0)[1]
        if y + row.get_allocated_height() >\
                scrolled.get_allocated_height() + adj or\
                y - row.get_allocated_height() < 0 + adj:
            scrolled.get_vadjustment().set_value(y)

    def __get_index(self, view):
        """
            Get view index
            @param view as str
            @return int
        """
        # Search current index
        children = self.__listbox.get_children()
        index = 0
        for child in children:
            if str(child.view) == view:
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

    def __on_moved(self, child, view, up):
        """
            Move child row
            @param child as SidebarChild
            @param view as str
            @param up as bool
        """
        view_index = self.__get_index(view)
        row = self.__listbox.get_row_at_index(view_index)
        if row is None:
            return
        self.__listbox.remove(row)
        child_index = self.__get_index(str(child.view))
        if not up:
            child_index += 1
        self.__listbox.insert(row, child_index)

    def __on_panel_mode_active(self, action, param):
        """
            Update panel mode
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        action.set_state(param)
        El().settings.set_enum('panel-mode', param.get_int32())
        self.__set_panel_mode()

    def __on_button_press(self, widget, event):
        """
            Hide popover if visible
            @param widget as Gtk.Widget
            @param event as Gdk.Event
        """
        self.__window.toolbar.title.close_popover()
        if event.button == 3:
            popover = Gtk.PopoverMenu.new()
            builder = Gtk.Builder()
            builder.add_from_resource("/org/gnome/Eolie/PanelMenu.ui")
            popover.add(builder.get_object("menu"))
            popover.set_relative_to(widget)
            rect = widget.get_allocation()
            rect.x = event.x
            rect.y = event.y
            rect.width = rect.height = 1
            popover.set_pointing_to(rect)
            popover.show()

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

    def __on_enter_notify_event(self, eventbox, event):
        """
            Leave minimal mode
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        if El().settings.get_value("panel-mode").get_string() == "minimal":
            if self.__leave_timeout_id is not None:
                    GLib.source_remove(self.__leave_timeout_id)
                    self.__leave_timeout_id = None
            self.set_property("width-request", ArtSize.PREVIEW_WIDTH)
            for child in self.__listbox.get_children():
                child.show_title(True)

    def __on_leave_notify_event(self, eventbox, event):
        """
            Enter minimal mode if needed
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        if El().settings.get_value("panel-mode").get_string() == "minimal":
            allocation = eventbox.get_allocation()
            if event.x <= 0 or\
               event.x >= allocation.width or\
               event.y <= 0 or\
               event.y >= allocation.height:
                if self.__leave_timeout_id is not None:
                    GLib.source_remove(self.__leave_timeout_id)
                self.__leave_timeout_id = GLib.timeout_add(
                                          750,
                                          self.__on_leave_notify_event_timeout)

    def __on_leave_notify_event_timeout(self):
        """
            Enter minimal mode if needed
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        self.__leave_timeout_id = None
        self.set_property("width-request", -1)
        for child in self.__listbox.get_children():
            child.show_title(self.__search_bar.is_visible())

    def __on_row_activated(self, listbox, row):
        """
            Show wanted web view
            @param listbox as Gtk.ListBox
            @param row as SidebarChild
        """
        self.__window.container.set_visible_view(row.view)
        self.update_visible_child()
