# Copyright (c) 2014-2016 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from gi.repository import Gtk, Gdk, GLib, GdkPixbuf, WebKit2
import cairo

from eolie.define import El, ArtSize
from eolie.utils import strip_uri


class SidebarChild(Gtk.ListBoxRow):
    """
        A Sidebar Child
    """

    def __init__(self, view, container):
        """
            Init child
            @param view as WebView
            @param container as Container
        """
        Gtk.ListBoxRow.__init__(self)
        self.__scroll_timeout_id = None
        self.__view = view
        self.__container = container
        self.__uri = ""
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
        view.connect('notify::favicon', self.__on_notify_favicon)
        view.connect('scroll-event', self.__on_scroll_event)
        view.connect('notify::uri', self.__on_uri_changed)
        view.connect('notify::title', self.__on_title_changed)
        view.connect('load-changed', self.__on_load_changed)
        self.get_style_context().add_class('sidebar-item')

    @property
    def view(self):
        """
            Get linked view
            @return WebView
        """
        return self.__view

    def set_snapshot(self, save):
        """
            Set webpage preview
            @param save as bool
        """
        if self.__view != self.__container.current:
            parent = self.__view.get_parent()
            if not isinstance(parent, Gtk.OffscreenWindow):
                self.__container.remove_view(self.__view)
                window = Gtk.OffscreenWindow.new()
                width = self.__container.get_allocated_width() -\
                    self.get_allocated_width()
                self.__view.set_size_request(
                                      width,
                                      self.__container.get_allocated_height())
                window.add(self.__view)
                window.show()
        self.__view.get_snapshot(WebKit2.SnapshotRegion.VISIBLE,
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
            self.__container.sidebar.close_view(self.__view)

    def _on_close_button_press(self, button, event):
        """
            Destroy self
        """
        self.__container.sidebar.close_view(self.__view)

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
            self.__on_notify_favicon(None, None, self.__view)

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
        surface = self.__get_favicon(self.__view.get_favicon())
        if surface is None:
            self.__image_close.set_from_icon_name('applications-internet',
                                                  Gtk.IconSize.MENU)
            return
        # We save favicon twice. If user have https://www.google.com as
        # bookmark, it will be directed and wont save bookmark's favicon
        El().art.save_artwork(self.__view.get_uri(), surface, "favicon")
        El().art.save_artwork(self.__view.loaded_uri, surface, "favicon")
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

    def __on_uri_changed(self, internal, uri, view):
        """
            Update uri
            @param internal as WebKit2.WebView
            @param uri as str
            @param view as WebView
        """
        # Some uri update may not change title
        uri = view.get_uri()
        if strip_uri(uri) != strip_uri(self.__uri):
            self.__title.set_text(uri)
        self.__uri = uri
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

    def __on_title_changed(self, internal, event, view):
        """
            Update title
            @param internal as WebKit2.WebView
            @param title as str
            @param view as WebView
        """
        if event.name != "title":
            return
        title = view.get_title()
        if not title:
            title = view.get_uri()
        self.__title.set_text(title)
        if not view.is_loading():
            GLib.timeout_add(1000, self.set_snapshot, True)
        if view.get_favicon() is not None:
            GLib.timeout_add(500, self.__set_favicon)

    def __on_scroll_event(self, internal, event, view):
        """
            Update snapshot
            @param internal as WebKit2.WebView
            @param event as WebKit2.Event
            @param view as WebView
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
            snapshot = self.__view.get_snapshot_finish(result)
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
                El().art.save_artwork(self.__view.get_uri(),
                                      surface, "preview")
            del surface
        except Exception as e:
            print("StackSidebar::__on_snapshot:", e)
            return
        parent = self.__view.get_parent()
        if parent is not None and isinstance(parent, Gtk.OffscreenWindow):
            parent.remove(self.__view)
            self.__view.set_size_request(-1, -1)
            self.__container.add_view(self.__view)

    def __on_load_changed(self, internal, event, view):
        """
            Update sidebar/urlbar
            @param internal as WebKit2.WebView
            @param event as WebKit2.LoadEvent
            @param view as WebView
        """
        if event == WebKit2.LoadEvent.STARTED:
            pass
        elif event == WebKit2.LoadEvent.FINISHED:
            GLib.timeout_add(500, self.set_snapshot, True)

    def __on_notify_favicon(self, internal, pointer, view):
        """
            Set favicon
            @param internal as WebKit2.WebView
            @param pointer as GParamPointer
            @param view as WebView
        """
        if view.get_favicon() is None:
            self.__image_close.set_from_icon_name('applications-internet',
                                                  Gtk.IconSize.MENU)
        else:
            self.__set_favicon()


class StackSidebar(Gtk.Grid):
    """
        Sidebar linked to a Gtk.Stack
    """
    def __init__(self, container):
        """
            Init sidebar
            @param container as Container
        """
        Gtk.Grid.__init__(self)
        self.__container = container
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
        child = SidebarChild(view, self.__container)
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
        visible = self.__container.current
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
        index = self.__get_index(self.__container.current)
        if index + 1 < len(children):
            next_row = self.__listbox.get_row_at_index(index + 1)
        else:
            next_row = self.__listbox.get_row_at_index(0)
        if next_row is not None:
            self.__container.set_visible_view(next_row.view)
        self.update_visible_child()

    def previous(self):
        """
            Show next view
        """
        children = self.__listbox.get_children()
        index = self.__get_index(self.__container.current)
        if index == 0:
            next_row = self.__listbox.get_row_at_index(len(children) - 1)
        else:
            next_row = self.__listbox.get_row_at_index(index - 1)
        if next_row is not None:
            self.__container.set_visible_view(next_row.view)
        self.update_visible_child()

    def close_view(self, view):
        """
            close current view
            @param view as WebView
            @return child SidebarChild
        """
        index = self.__get_index(view)
        next_row = None
        # Delay view destroy to allow stack animation
        child = self.__listbox.get_row_at_index(index)
        if child is None:
            return
        GLib.timeout_add(1000, child.view.destroy)
        child.destroy()
        children = self.__listbox.get_children()
        if len(children) == 0:
            self.__container.add_web_view(El().start_page, True)
        elif index + 1 < len(children):
            next_row = self.__listbox.get_row_at_index(index + 1)
        else:
            next_row = self.__listbox.get_row_at_index(index - 1)
        if next_row is not None:
            self.__container.set_visible_view(next_row.view)
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

    def __filter_func(self, row):
        """
            Filter list based on current filter
            @param row as Row
        """
        filter = self.__search_entry.get_text()
        if not filter:
            row.set_snapshot(False)
            return True
        uri = row.view.get_uri()
        title = row.view.get_title()
        if (uri is not None and uri.find(filter) != -1) or\
                (title is not None and title.find(filter) != -1):
            row.set_snapshot(False)
            return True
        return False

    def __on_key_press(self, widget, event):
        """
            If Esc, hide widget, why GTK doesn't do that?
            Otherwise, we get an ugly frame
            @param widget as Gtk.SearchEntry
            @param event as Gdk.Event
        """
        if event.keyval == Gdk.KEY_Escape:
            self.__search_entry.set_text('')
            El().active_window.toolbar.actions.filter_button.set_active(False)
            return True

    def __on_row_activated(self, listbox, row):
        """
            Show wanted web view
            @param listbox as Gtk.ListBox
            @param row as SidebarChild
        """
        self.__container.set_visible_view(row.view)
        self.update_visible_child()
