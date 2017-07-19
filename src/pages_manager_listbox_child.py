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

from gi.repository import Gtk, GObject, Pango, Gdk, Gio, GLib, WebKit2

import cairo
from gettext import gettext as _

from eolie.define import El, ArtSize, PanelMode
from eolie.pages_manager_child import PagesManagerChild


class PagesManagerListBoxChild(Gtk.ListBoxRow, PagesManagerChild):
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
        PagesManagerChild.__init__(self, view, window)
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

    def show_title(self, b):
        """
            Show page title
            @param b as bool
        """
        if b:
            self._title.show()
            self._image_close.set_hexpand(False)
        else:
            self._title.hide()
            self._image_close.set_hexpand(True)

    def set_preview_height(self, height):
        """
            Set child preview height
            @param height as int
        """
        if height is None:
            ctx = self._title.get_pango_context()
            layout = Pango.Layout.new(ctx)
            height = int(layout.get_pixel_size()[1]) + 10
            self._grid.set_property("valign", Gtk.Align.CENTER)
        else:
            self._grid.set_property("valign", Gtk.Align.END)
        self._overlay.set_size_request(-1, height)

    def set_snapshot(self, uri, save):
        """
            Set webpage preview
            @param uri as str
            @param save as bool
        """
        if self._view.webview.ephemeral:
            panel_mode = El().settings.get_enum("panel-mode")
            if panel_mode != PanelMode.MINIMAL:
                self._image.set_from_icon_name(
                                             "user-not-tracked-symbolic",
                                             Gtk.IconSize.DIALOG)
        else:
            self._view.webview.get_snapshot(
                                         WebKit2.SnapshotRegion.VISIBLE,
                                         WebKit2.SnapshotOptions.NONE,
                                         None,
                                         self._on_snapshot,
                                         uri,
                                         save)

#######################
# PROTECTED           #
#######################
    def _on_button_press_event(self, eventbox, event):
        """
            Hide popover or close view
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        PagesManagerChild._on_button_press_event(self, eventbox, event)
        if event.button == 3:
            menu = Gio.Menu.new()
            action = Gio.SimpleAction.new("close_page",
                                          GLib.VariantType.new("i"))
            self._window.add_action(action)
            page_id = self._view.webview.get_page_id()
            item = Gio.MenuItem.new(_("Close page"),
                                    "win.close_page(%s)" % page_id)
            menu.append_item(item)
            action.connect("activate",
                           self.__on_close_activate)
            popover = Gtk.Popover.new_from_model(eventbox, menu)
            popover.show()

    def _on_snapshot(self, view, result, uri, save):
        """
            Set snapshot on main image
            @param view as WebView
            @param result as Gio.AsyncResult
            @param uri as str
            @param save as bool
            @warning view here is WebKit2.WebView, not WebView
        """
        current_uri = view.get_uri()
        if current_uri is None or current_uri != uri:
            return
        # Do not cache snapshot on error
        if self._view.webview.error is not None:
            save = False
        try:
            snapshot = view.get_snapshot_finish(result)
            panel_mode = El().settings.get_enum("panel-mode")
            if panel_mode == PanelMode.PREVIEW:
                # Set sidebar child image
                # Set start image scale factor
                factor = (ArtSize.PREVIEW_WIDTH -
                          ArtSize.PREVIEW_WIDTH_MARGIN) /\
                          snapshot.get_width()
                surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                             ArtSize.PREVIEW_WIDTH -
                                             ArtSize.PREVIEW_WIDTH_MARGIN,
                                             ArtSize.PREVIEW_HEIGHT)
                context = cairo.Context(surface)
                context.scale(factor, factor)
                context.set_source_surface(snapshot, 0, 0)
                context.paint()
                self._image.set_from_surface(surface)
                del surface

            # Save start image to cache
            # We also cache original URI
            uris = [current_uri]
            if view.related_uri is not None and\
                    view.related_uri not in uris:
                uris.append(view.related_uri)
            view.reset_related_uri()
            # Set start image scale factor
            margin = 0
            if snapshot.get_width() > snapshot.get_height():
                margin = (snapshot.get_width() - ArtSize.START_WIDTH) / 2
                factor = ArtSize.START_HEIGHT / snapshot.get_height()
            else:
                factor = ArtSize.START_WIDTH / snapshot.get_width()
            surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                         ArtSize.START_WIDTH,
                                         ArtSize.START_HEIGHT)
            context = cairo.Context(surface)
            context.scale(factor, factor)
            context.set_source_surface(snapshot, -margin * factor, 0)
            context.paint()
            for uri in uris:
                if not El().art.exists(uri, "start") and save:
                    El().art.save_artwork(uri, surface, "start")
            del surface
            del snapshot
        except Exception as e:
            print("PagesManagerListBoxChild::__on_snapshot():", e)

#######################
# PRIVATE             #
#######################
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

    def __on_close_activate(self, action, param):
        """
            Close wanted page
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        page_id = param.get_int32()
        for view in self._window.container.views:
            if view.webview.get_page_id() == page_id:
                self._window.container.pages_manager.close_view(view)
                return
