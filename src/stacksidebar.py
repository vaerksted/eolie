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

from gi.repository import Gtk, Gdk, GLib, GObject, GdkPixbuf, WebKit2
import cairo

from eolie.define import El, ArtSize
from eolie.utils import strip_uri


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
        self.__view = view
        self.__window = window
        self.__uri = ""
        self.__load_status = WebKit2.LoadEvent.FINISHED
        builder = Gtk.Builder()
        builder.add_from_resource('/org/gnome/Eolie/SidebarChild.ui')
        builder.connect_signals(self)
        self.__title = builder.get_object('title')
        self.__uri = builder.get_object('uri')
        self.__image = builder.get_object('image')
        self.__image_close = builder.get_object('image_close')
        self.__image_close.set_from_icon_name('applications-internet',
                                              Gtk.IconSize.MENU)
        self.__title.set_label("Empty page")
        self.add(builder.get_object('widget'))
        view.webview.connect('notify::favicon', self.__on_notify_favicon)
        view.webview.connect('scroll-event', self.__on_scroll_event)
        view.webview.connect('notify::uri', self.__on_uri_changed)
        view.webview.connect('notify::title', self.__on_title_changed)
        view.webview.connect('load-changed', self.__on_load_changed)
        self.get_style_context().add_class('sidebar-item')

        self.drag_source_set(Gdk.ModifierType.BUTTON1_MASK, [],
                             Gdk.DragAction.MOVE)
        self.drag_source_add_text_targets()
        self.connect('drag-begin', self.__on_drag_begin)
        self.connect('drag-data-get', self.__on_drag_data_get)
        self.drag_dest_set(Gtk.DestDefaults.DROP | Gtk.DestDefaults.MOTION,
                           [], Gdk.DragAction.MOVE)
        self.drag_dest_add_text_targets()
        self.connect('drag-data-received', self.__on_drag_data_received)
        self.connect('drag-motion', self.__on_drag_motion)
        self.connect('drag-leave', self.__on_drag_leave)

    @property
    def view(self):
        """
            Get linked view
            @return View
        """
        return self.__view

    def set_snapshot(self, save):
        """
            Set webpage preview
            @param save as bool
        """
        if self.__view != self.__window.container.current:
            parent = self.__view.get_parent()
            if not isinstance(parent, Gtk.OffscreenWindow):
                self.__window.container.remove_view(self.__view)
                window = Gtk.OffscreenWindow.new()
                width = self.__window.container.get_allocated_width() -\
                    self.get_allocated_width()
                self.__view.set_size_request(
                              width,
                              self.__window.container.get_allocated_height())
                window.add(self.__view)
                window.show()
        self.__view.webview.get_snapshot(WebKit2.SnapshotRegion.VISIBLE,
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
    def _on_button_press(self, button, event):
        """
            Destroy self
        """
        if event.button == 2:
            self.__window.container.sidebar.close_view(self.__view)
        self.__window.toolbar.title.hide_popover()

    def _on_close_button_press(self, button, event):
        """
            Destroy self
        """
        self.__window.container.sidebar.close_view(self.__view)

    def _on_enter_notify(self, eventbox, event):
        """
            Show close button
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        self.__image_close.set_from_icon_name('close-symbolic',
                                              Gtk.IconSize.DIALOG)
        self.__image_close.get_style_context().add_class('sidebar-close')

    def _on_leave_notify(self, eventbox, event):
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
                                                               'sidebar-close')
            self.__on_notify_favicon(self.__view.webview, None)

#######################
# PRIVATE             #
#######################
    def __get_favicon(self, surface):
        """
            Resize surface to match favicon size
            @param surface as cairo.surface
        """
        if surface is None:
            return None
        pixbuf = Gdk.pixbuf_get_from_surface(surface, 0, 0,
                                             surface.get_width(),
                                             surface.get_height())
        scaled = pixbuf.scale_simple(ArtSize.FAVICON,
                                     ArtSize.FAVICON,
                                     GdkPixbuf.InterpType.BILINEAR)
        del pixbuf
        s = Gdk.cairo_surface_create_from_pixbuf(scaled,
                                                 self.get_scale_factor(), None)
        del scaled
        return s

    def __set_favicon(self):
        """
            Set favicon
        """
        surface = self.__get_favicon(self.__view.webview.get_favicon())
        if surface is None:
            self.__image_close.set_from_icon_name('applications-internet',
                                                  Gtk.IconSize.MENU)
            return
        # We save favicon twice. If user have https://www.google.com as
        # bookmark, it will be directed and wont save bookmark's favicon
        El().art.save_artwork(self.__view.webview.get_uri(),
                              surface, "favicon")
        if self.__view.webview.get_uri() != self.__view.webview.loaded_uri:
            if strip_uri(self.__view.webview.get_uri(), False, False) ==\
               strip_uri(self.__view.webview.loaded_uri, False, False):
                El().art.save_artwork(self.__view.webview.loaded_uri,
                                      surface, "favicon")
        self.__image_close.set_from_surface(surface)
        del surface
        self.__image_close.get_style_context().remove_class('sidebar-close')
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
        # Some uri update may not change title
        uri = view.get_uri()
        if strip_uri(uri) != strip_uri(self.__uri):
            self.__title.set_text(uri)
        self.__uri = uri

        # Just set icon if special schemes
        if uri == "populars://":
            self.__image_close.set_from_icon_name("emote-love-symbolic",
                                                  Gtk.IconSize.MENU)
            return

        # We are not filtered
        if self.get_allocated_width() != 1:
            preview = El().art.get_artwork(view.get_uri(),
                                           "preview",
                                           view.get_scale_factor(),
                                           self.get_allocated_width() -
                                           ArtSize.PREVIEW_WIDTH_MARGIN,
                                           ArtSize.PREVIEW_HEIGHT)
            if preview is not None:
                self.__image.set_from_surface(preview)
                del preview
            else:
                self.__image.clear()
        favicon = El().art.get_artwork(view.get_uri(),
                                       "favicon",
                                       view.get_scale_factor(),
                                       ArtSize.FAVICON,
                                       ArtSize.FAVICON)
        if favicon is not None:
            self.__image_close.set_from_surface(favicon)
            del favicon
        else:
            self.__image_close.set_from_icon_name('applications-internet',
                                                  Gtk.IconSize.MENU)

    def __on_title_changed(self, view, event):
        """
            Update title
            @param view as WebView
            @param event as GParamSpec
        """
        if self.__load_status != WebKit2.LoadEvent.FINISHED:
            return True
        title = view.get_title()
        if not title:
            title = view.get_uri()
        if title.startswith("@&$%ù²"):
            return True
        self.__title.set_text(title)
        if view.get_favicon() is not None:
            GLib.timeout_add(1000, self.__set_favicon)
        GLib.timeout_add(500, self.set_snapshot, True)

    def __on_load_changed(self, view, event):
        """
            Update snapshot
            @param view as WebView
            @param event as WebKit2.LoadEvent
        """
        self.__load_status = event
        if event == WebKit2.LoadEvent.STARTED:
            self.__snapshot_valid = False
        elif event == WebKit2.LoadEvent.FINISHED:
            self.__on_title_changed(view, event)

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
            if save:
                El().art.save_artwork(view.get_uri(),
                                      surface, "preview")
            # Manage start page cache
            if not El().art.exists(view.get_uri(), "start"):
                width = snapshot.get_width()
                factor = ArtSize.START_WIDTH / width
                surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                             ArtSize.START_WIDTH,
                                             ArtSize.START_HEIGHT)
                context = cairo.Context(surface)
                context.scale(factor, factor)
                context.set_source_surface(snapshot, 0, 0)
                context.paint()
                El().art.save_artwork(view.get_uri(),
                                      surface, "start")
            del surface
            del snapshot
        except Exception as e:
            print("StackSidebar::__on_snapshot:", e)
            return
        parent = self.__view.get_parent()
        if parent is not None and isinstance(parent, Gtk.OffscreenWindow):
            parent.remove(self.__view)
            self.__view.set_size_request(-1, -1)
            self.__window.container.add_view(self.__view)

    def __on_notify_favicon(self, view, pointer):
        """
            Set favicon
            @param view as WebView
            @param pointer as GParamPointer
        """
        # Just set icon if special schemes
        if view.get_uri() == "populars://":
            self.__image_close.set_from_icon_name("emote-love-symbolic",
                                                  Gtk.IconSize.MENU)
        elif view.get_favicon() is None:
            self.__image_close.set_from_icon_name('applications-internet',
                                                  Gtk.IconSize.MENU)
        else:
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
            self.emit('moved', src_widget, up)
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
            self.get_style_context().add_class('drag-up')
            self.get_style_context().remove_class('drag-down')
        else:
            self.get_style_context().remove_class('drag-up')
            self.get_style_context().add_class('drag-down')

    def __on_drag_leave(self, widget, context, time):
        """
            Remove style
            @param widget as Gtk.Widget
            @param context as Gdk.DragContext
            @param time as int
        """
        self.get_style_context().remove_class('drag-up')
        self.get_style_context().remove_class('drag-down')


class StackSidebar(Gtk.Grid):
    """
        Sidebar linked to a Window Gtk.Stack
    """
    def __init__(self, window):
        """
            Init sidebar
            @param window as Window
        """
        Gtk.Grid.__init__(self)
        self.__window = window
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.__search_entry = Gtk.SearchEntry.new()
        self.__search_entry.connect('search-changed', self._on_search_changed)

        self.__search_entry.show()
        self.__search_bar = Gtk.SearchBar.new()
        self.__search_bar.add(self.__search_entry)
        self.__search_bar.show()
        self.add(self.__search_bar)
        self.__scrolled = Gtk.ScrolledWindow()
        self.__scrolled.set_vexpand(True)
        self.__scrolled.show()
        self.__listbox = Gtk.ListBox.new()
        self.__listbox.set_activate_on_single_click(True)
        self.__listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.__listbox.show()
        self.__listbox.connect('row_activated', self.__on_row_activated)
        self.__scrolled.add(self.__listbox)
        self.add(self.__scrolled)

    def add_child(self, view):
        """
            Add child to sidebar
            @param view as WebView
        """
        child = SidebarChild(view, self.__window)
        child.connect("moved", self.__on_moved)
        child.show()
        self.__listbox.add(child)

    def update_children_snapshot(self):
        """
            Update child snapshot
        """
        for row in self.__listbox.get_children():
            row.clear_snapshot()
            row.set_snapshot(True)

    def update_visible_child(self):
        """
            Mark current child as visible
            Unmark all others
        """
        visible = self.__window.container.current
        for child in self.__listbox.get_children():
            if child.view == visible:
                child.get_style_context().add_class('sidebar-item-selected')
                # Wait loop empty: will fails otherwise if child just created
                GLib.idle_add(self.__scroll_to_row, child)
            else:
                child.get_style_context().remove_class('sidebar-item-selected')

    def set_filtered(self, b):
        """
            Show filtering widget
            @param b as bool
        """
        if b:
            self.__search_entry.grab_focus()
            self.__search_entry.connect('key-press-event',
                                        self.__on_key_press)
            self.__listbox.set_filter_func(self.__filter_func)
        else:
            self.__search_entry.disconnect_by_func(self.__on_key_press)
            self.__listbox.set_filter_func(None)
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
        # Needed to unfocus titlebar
        self.__window.set_focus(None)
        was_current = view == self.__window.container.current
        child_index = self.__get_index(str(view))
        # Delay view destroy to allow stack animation
        child = self.__listbox.get_row_at_index(child_index)
        if child is None:
            return
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
    def __scroll_to_row(self, row):
        """
            Scroll to row
            @param row as Row
        """
        scrolled = self.__listbox.get_ancestor(Gtk.ScrolledWindow)
        if scrolled is None:
            return
        y = row.translate_coordinates(self.__listbox, 0, 0)[1]
        if y + row.get_allocated_height() >\
                scrolled.get_allocated_height() or\
                y - row.get_allocated_height() < 0:
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
        self.__listbox.remove(row)
        child_index = self.__get_index(str(child.view))
        if not up:
            child_index += 1
        self.__listbox.insert(row, child_index)

    def __on_key_press(self, widget, event):
        """
            If Esc, hide widget, why GTK doesn't do that?
            Otherwise, we get an ugly frame
            @param widget as Gtk.SearchEntry
            @param event as Gdk.Event
        """
        if event.keyval == Gdk.KEY_Escape:
            self.__search_entry.set_text('')
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
