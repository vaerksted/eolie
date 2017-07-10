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

from gi.repository import Gtk, Gdk, GLib, WebKit2

from eolie.define import El, ArtSize
from eolie.utils import resize_favicon


class StackChild:
    """
        Generic parent for Stack children
        Need to be inherited by a Gtk.*BoxRow
    """

    def __init__(self, view, window):
        """
            Init child
        """
        self._view = view
        self._window = window
        self.__connected_ids = []
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/StackChild.ui")
        builder.connect_signals(self)
        self._overlay = builder.get_object("overlay")
        self._grid = builder.get_object("grid")
        self._title = builder.get_object("title")
        self._image = builder.get_object("image")
        self._image_close = builder.get_object("image_close")
        if view.webview.ephemeral:
            self._image_close.set_from_icon_name("window-close-symbolic",
                                                 Gtk.IconSize.INVALID)
        else:
            self._image_close.set_from_icon_name("applications-internet",
                                                 Gtk.IconSize.INVALID)
        self._image_close.set_property("pixel-size", ArtSize.FAVICON)
        self.__spinner = builder.get_object("spinner")
        self._title.set_label("Empty page")
        self.add(builder.get_object("widget"))

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

        self.set_property("has-tooltip", True)
        self.connect("query-tooltip", self.__on_query_tooltip)

        self.__connected_ids.append(
                             self._view.webview.connect(
                                 "notify::favicon",
                                 lambda x, y: self.__set_favicon()))
        self.__connected_ids.append(
                             self._view.webview.connect(
                                 "uri-changed",
                                 self._on_uri_changed))
        self.__connected_ids.append(
                             self._view.webview.connect(
                                 "title-changed",
                                 self.__on_title_changed))
        self.__connected_ids.append(
                             self._view.webview.connect(
                                 "load-changed",
                                 self.__on_load_changed))

    def update(self):
        """
            Update child title and favicon
        """
        title = self._view.webview.get_title()
        if title is None:
            title = self._view.webview.get_uri()
        self._title.set_text(title)
        self.__set_favicon()

    def disconnect_signals(self):
        """
            Disconnect signals
        """
        while self.__connected_ids:
            connected_id = self.__connected_ids.pop(0)
            self._view.webview.disconnect(connected_id)

    def set_snapshot(self, uri, save):
        """
            Set webpage preview
            @param uri as str
            @param save as bool
        """
        if self._view.webview.ephemeral:
            self._image.set_from_icon_name(
                                         "user-not-tracked-symbolic",
                                         Gtk.IconSize.DIALOG)
        else:
            self._view.webview.get_snapshot(
                                         WebKit2.SnapshotRegion.FULL_DOCUMENT,
                                         WebKit2.SnapshotOptions.NONE,
                                         None,
                                         self._on_snapshot,
                                         uri,
                                         save)

    def clear_snapshot(self):
        """
            Get snapshot
            @return Gtk.Image
        """
        if self._image is not None:
            self._image.clear()

    def show_title(self, b):
        pass

    @property
    def view(self):
        """
            Get linked view
            @return View
        """
        return self._view

#######################
# PROTECTED           #
#######################
    def _on_snapshot(self, view, result, uri, save):
        """
            Set snapshot on main image
            @param view as WebView
            @param result as Gio.AsyncResult
            @param uri as str
            @param save as bool
            @warning view here is WebKit2.WebView, not WebView
        """
        pass

    def _on_button_press_event(self, button, event):
        """
            Hide popover or close view
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        if event.button == 2:
            self._window.container.pages_manager.close_view(self._view)

    def _on_close_button_press_event(self, eventbox, event):
        """
            Destroy self
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        if El().settings.get_enum("panel-mode") != 2:
            self._window.container.pages_manager.close_view(self._view)

    def _on_enter_notify_event(self, eventbox, event):
        """
            Show close button
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        if El().settings.get_enum("panel-mode") == 2:
            return
        self._image_close.set_from_icon_name("window-close-symbolic",
                                             Gtk.IconSize.INVALID)
        self._image_close.get_style_context().add_class("sidebar-item-close")

    def _on_leave_notify_event(self, eventbox, event):
        """
            Show close button
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        if El().settings.get_enum("panel-mode") == 2:
            return
        allocation = eventbox.get_allocation()
        if event.x <= 0 or\
           event.x >= allocation.width or\
           event.y <= 0 or\
           event.y >= allocation.height:
            self._image_close.get_style_context().remove_class(
                                                          "sidebar-item-close")
            self.__set_favicon()

    def _on_uri_changed(self, view, uri):
        """
            Update uri
            @param view as WebView
            @param uri as str
        """
        # We are not filtered and not in private mode
        if not self._view.webview.is_loading() and\
                not self._view.webview.ephemeral and\
                El().settings.get_enum("panel-mode") == 0:
            GLib.timeout_add(2000, self.set_snapshot,
                             self._view.webview.get_uri(), False)

#######################
# PRIVATE             #
#######################
    def __set_favicon(self):
        """
            Set favicon
        """
        uri = self._view.webview.get_uri()
        if uri == "populars://":
            self._image_close.set_from_icon_name("emote-love-symbolic",
                                                 Gtk.IconSize.INVALID)
        elif self._view.webview.ephemeral:
            self._image_close.set_from_icon_name("user-not-tracked-symbolic",
                                                 Gtk.IconSize.INVALID)
        elif uri:
            context = self._view.webview.get_context()
            favicon_db = context.get_favicon_database()
            favicon_db.get_favicon(uri, None, self.__set_favicon_result, uri)
        else:
            self._image_close.set_from_icon_name("applications-internet",
                                                 Gtk.IconSize.INVALID)

    def __set_favicon_related(self, surface, uri, related_uri):
        """
            Set favicon for related uri
            @param surface as cairo.surface
            @param uri as str
            @param related_uri as str
        """
        if related_uri is not None and\
                related_uri != uri and\
                not El().art.exists(related_uri, "favicon"):
            El().art.save_artwork(related_uri, surface, "favicon")

    def __set_favicon_result(self, db, result, uri):
        """
            Set favicon db result
            @param db as WebKit2.FaviconDatabase
            @param result as Gio.AsyncResult
            @param uri as str
        """
        try:
            surface = db.get_favicon_finish(result)
            save = True
        except:
            surface = self._view.webview.get_favicon()
            # Getting favicon is not accurate
            # We don't know if it really is for current uri
            # So don't save
            save = False

        if surface is None:
            self._image_close.set_from_icon_name("applications-internet",
                                                 Gtk.IconSize.INVALID)
        else:
            resized = resize_favicon(surface)
            if save:
                El().art.save_artwork(uri, resized, "favicon")
                self.__set_favicon_related(resized,
                                           uri,
                                           self._view.webview.related_uri)
            self._image_close.set_from_surface(resized)
            del resized
            del surface

    def __on_title_changed(self, view, title):
        """
            Update title
            @param view as WebView
            @param title as str
        """
        self._title.set_text(title)

    def __on_load_changed(self, view, event):
        """
            Update snapshot
            @param view as WebView
            @param event as WebKit2.LoadEvent
        """
        uri = view.get_uri()
        if event == WebKit2.LoadEvent.STARTED:
            self.__spinner.start()
            self._title.set_text(uri)
        elif event == WebKit2.LoadEvent.COMMITTED:
            self._title.set_text(uri)
        elif event == WebKit2.LoadEvent.FINISHED:
            self.__spinner.stop()
            # is_loading() happen when loading a new uri while
            # previous loading is not finished
            if not view.cancelled and not view.is_loading():
                GLib.timeout_add(500, self.set_snapshot, uri, False)
                # FIXME Should be better to have way to snapshot when
                # page is rendered
                GLib.timeout_add(3000, self.set_snapshot, uri, True)
                self.__set_favicon()

    def __on_drag_begin(self, widget, context):
        """
            Set icon
            @param widget as Gtk.Widget
            @param context as Gdk.DragContext
        """
        surface = self._image.get_property("surface")
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
        name = str(self._view)
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

    def __on_query_tooltip(self, widget, x, y, keyboard, tooltip):
        """
            Show tooltip if needed
            @param widget as Gtk.Widget
            @param x as int
            @param y as int
            @param keyboard as bool
            @param tooltip as Gtk.Tooltip
        """
        text = ""
        label = self._title.get_text()
        uri = self._view.webview.get_uri()
        # GLib.markup_escape_text
        if uri is None:
            text = "<b>%s</b>" % GLib.markup_escape_text(label)
        else:
            text = "<b>%s</b>\n%s" % (GLib.markup_escape_text(label),
                                      GLib.markup_escape_text(uri))
        widget.set_tooltip_markup(text)
