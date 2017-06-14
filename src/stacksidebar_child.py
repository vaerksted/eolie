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

from gi.repository import Gtk, Gdk, GLib, GObject, WebKit2, Pango

import cairo

from eolie.define import El, ArtSize
from eolie.utils import resize_favicon


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
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/SidebarChild.ui")
        builder.connect_signals(self)
        self.__overlay = builder.get_object("overlay")
        self.__grid = builder.get_object("grid")
        self.__title = builder.get_object("title")
        self.__image = builder.get_object("image")
        self.__image_close = builder.get_object("image_close")
        if view.webview.ephemeral:
            self.__image_close.set_from_icon_name("window-close-symbolic",
                                                  Gtk.IconSize.INVALID)
        else:
            self.__image_close.set_from_icon_name("applications-internet",
                                                  Gtk.IconSize.INVALID)
        self.__image_close.set_property("pixel-size", ArtSize.FAVICON)
        self.__spinner = builder.get_object("spinner")
        self.__title.set_label("Empty page")
        self.add(builder.get_object("widget"))
        view.webview.connect("notify::favicon",
                             lambda x, y: self.__set_favicon())
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

        self.set_property("has-tooltip", True)
        self.connect("query-tooltip", self.__on_query_tooltip)

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
        if self.__view.webview.ephemeral:
            self.__image.set_from_icon_name(
                                         "user-not-tracked-symbolic",
                                         Gtk.IconSize.DIALOG)
        elif not self.__view.webview.is_loading() and\
                self.get_allocated_width() != 1:
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
        if self.__window.container.sidebar.panel_mode != 2:
            self.__window.container.sidebar.close_view(self.__view)

    def _on_enter_notify_event(self, eventbox, event):
        """
            Show close button
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        if self.__window.container.sidebar.panel_mode == 2:
            return
        self.__image_close.set_from_icon_name("window-close-symbolic",
                                              Gtk.IconSize.INVALID)
        self.__image_close.get_style_context().add_class("sidebar-item-close")

    def _on_leave_notify_event(self, eventbox, event):
        """
            Show close button
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        if self.__window.container.sidebar.panel_mode == 2:
            return
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
        uri = self.__view.webview.get_uri()
        self.__image_close.get_style_context().remove_class(
                                                          "sidebar-item-close")
        if uri == "populars://":
            self.__image_close.set_from_icon_name("emote-love-symbolic",
                                                  Gtk.IconSize.INVALID)
        elif self.__view.webview.ephemeral:
            self.__image_close.set_from_icon_name("user-not-tracked-symbolic",
                                                  Gtk.IconSize.INVALID)
        else:
            # First use favicon cached by Eolie
            surface = El().art.get_artwork(uri, "favicon",
                                           self.get_scale_factor(),
                                           ArtSize.FAVICON, ArtSize.FAVICON)
            # Then favicon cached by WebKitGTK
            if surface is None:
                surface = self.__view.webview.get_favicon()
                if surface is not None and not El().art.exists(uri, "favicon"):
                    El().art.save_artwork(uri, surface, "favicon")
            if surface is not None and\
                    self.__view.webview.related_uri is not None and\
                    self.__view.webview.related_uri != uri and\
                    not El().art.exists(self.__view.webview.related_uri,
                                        "favicon"):
                El().art.save_artwork(self.__view.webview.related_uri,
                                      surface, "favicon")
            # Set favicon
            if surface is None:
                self.__image_close.set_from_icon_name("applications-internet",
                                                      Gtk.IconSize.INVALID)
            else:
                self.__image_close.set_from_surface(resize_favicon(surface))
                del surface

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
        if not self.__view.webview.ephemeral and\
                self.__window.container.sidebar.panel_mode == 0 and\
                self.get_allocated_width() != 1:
            preview = El().art.get_artwork(uri,
                                           "preview",
                                           view.get_scale_factor(),
                                           self.get_allocated_width() -
                                           ArtSize.PREVIEW_WIDTH_MARGIN,
                                           ArtSize.PREVIEW_HEIGHT)
            if preview is None:
                self.__image.clear()
            else:
                self.__image.set_from_surface(preview)
                del preview

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
            self.__spinner.start()
            self.__title.set_text(uri)
        elif event == WebKit2.LoadEvent.COMMITTED:
            self.__title.set_text(uri)
        elif event == WebKit2.LoadEvent.FINISHED:
            self.__set_favicon()
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
        if not view.is_loading():
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
        # Do not cache snapshot on error
        if self.__view.webview.error is not None:
            save = False
        try:
            current_uri = view.get_uri()
            if current_uri is None:
                return
            snapshot = view.get_snapshot_finish(result)

            if self.__window.container.sidebar.panel_mode == 0:
                # Set sidebar child image
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

                # Save image to cache
                if save:
                    El().art.save_artwork(current_uri,
                                          surface, "preview")
                    # We also cache related URI
                    if view.related_uri is not None and\
                            view.related_uri != current_uri:
                        El().art.save_artwork(view.related_uri,
                                              surface, "preview")
                del surface

            # Save start image to cache
            # We also cache original URI
            uris = [current_uri]
            if view.related_uri is not None and\
                    view.related_uri not in uris:
                uris.append(view.related_uri)
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
                El().art.save_artwork(uri, surface, "start")
            del surface
            del snapshot
        except Exception as e:
            print("SidebarChild::__on_snapshot():", e)

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
        label = self.__title.get_text()
        uri = self.__view.webview.get_uri()
        # GLib.markup_escape_text
        if uri is None:
            text = "<b>%s</b>" % GLib.markup_escape_text(label)
        else:
            text = "<b>%s</b>\n%s" % (GLib.markup_escape_text(label),
                                      GLib.markup_escape_text(uri))
        widget.set_tooltip_markup(text)
