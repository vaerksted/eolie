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

from gi.repository import Gtk, Gdk, GLib, Pango, GObject

from eolie.label_indicator import LabelIndicator
from eolie.define import El, ArtSize


class SitesManagerChild(Gtk.ListBoxRow):
    """
        Child showing snapshot, title and favicon
    """

    __gsignals__ = {
        'moved': (GObject.SignalFlags.RUN_FIRST, None, (str, bool))
    }

    def __init__(self, netloc, window, ephemeral):
        """
            Init child
            @param netloc as str
            @param window as Window
            @param ephemeral as bool
        """
        Gtk.ListBoxRow.__init__(self)
        self.__window = window
        self.__netloc = netloc
        self.__ephemeral = ephemeral
        self.__views = []
        self.__connected_ids = []
        self.__scroll_timeout_id = None
        self.set_property("has-tooltip", True)
        self.connect("query-tooltip", self.__on_query_tooltip)
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/SitesManagerChild.ui")
        builder.connect_signals(self)
        widget = builder.get_object("widget")
        self.__close_button = builder.get_object("close_button")
        self.__indicator_label = LabelIndicator()
        self.__indicator_label.set_property("halign", Gtk.Align.CENTER)
        self.__indicator_label.show()
        builder.get_object("grid").attach(self.__indicator_label, 1, 0, 1, 1)
        self.__netloc_label = builder.get_object("netloc")
        self.__netloc_label.set_text(self.__netloc)
        self.__image = builder.get_object("image")
        self.__image.set_property("pixel-size", ArtSize.FAVICON)
        favicon_path = El().art.get_favicon_path(netloc)
        if favicon_path is not None:
            self.__image.set_from_file(favicon_path)
        else:
            self.__set_initial_artwork(self.__netloc)
        self.add(widget)
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

    def add_view(self, view):
        """
            Add view
            @param view as View
            @param uri as str
        """
        if view not in self.__views:
            self.__views.append(view)
            view.webview.connect("shown", self.__on_webview_shown)
            view.webview.connect("favicon-changed",
                                 self.__on_webview_favicon_changed)
            self.update_label()
            self.__indicator_label.update_count(True)
            if not view.webview.shown:
                self.__indicator_label.mark_unshown(view.webview)

    def remove_view(self, view):
        """
            Remove view and destroy self if no more view
            @param view as View
        """
        if view in self.__views:
            self.__views.remove(view)
            view.webview.disconnect_by_func(self.__on_webview_shown)
            view.webview.disconnect_by_func(self.__on_webview_favicon_changed)
            self.update_label()
            self.__indicator_label.update_count(False)
            if not view.webview.shown:
                self.__indicator_label.mark_shown(view.webview)

    def set_minimal(self, minimal):
        """
            Make widget minimal
            @param minimal as bool
        """
        if minimal:
            self.__netloc_label.hide()
            self.__close_button.hide()
            self.__image.set_property("halign", Gtk.Align.CENTER)
            self.__image.set_hexpand(True)
        else:
            self.__netloc_label.show()
            self.__close_button.show()
            self.__image.set_hexpand(False)
            self.__image.set_property("halign", Gtk.Align.START)

    def reset(self, netloc):
        """
            Reset widget to new netloc
            @param netloc as str
        """
        if netloc != self.__netloc:
            self.__netloc = netloc
            favicon_path = El().art.get_favicon_path(netloc)
            if favicon_path is not None:
                self.__image.set_from_file(favicon_path)
            else:
                self.__set_initial_artwork(self.__netloc)
            self.__netloc_label.set_text(self.__netloc)

    def update_label(self):
        """
            Update label: if one view, use title else use netloc
            @param view as View
        """
        if len(self.__views) == 1:
            title = self.__views[0].webview.get_title()
            if title is None:
                self.__netloc_label.set_text(self.__netloc)
            else:
                self.__netloc_label.set_text(title)
        else:
            self.__netloc_label.set_text(self.__netloc)

    @property
    def empty(self):
        """
            True if no view associated
            @return bool
        """
        return len(self.__views) == 0

    @property
    def views(self):
        """
            Get views
            @return [view]
        """
        return self.__views

    @property
    def ephemeral(self):
        """
            Get ephemeral
            @return bool
        """
        return self.__ephemeral

    @property
    def netloc(self):
        """
            Get netloc
            @return str
        """
        return self.__netloc

#######################
# PROTECTED           #
#######################
    def _on_close_button_clicked(self, button):
        """
            Close site
            @param button as Gtk.Button
        """
        for view in self.__views:
            self.__window.container.pages_manager.try_close_view(view)

    def _on_scroll_event(self, eventbox, event):
        """
            Switch between children
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        if event.direction == Gdk.ScrollDirection.UP:
            self.__window.container.pages_manager.previous()
            self.__window.container.pages_manager.ctrl_released()
        elif event.direction == Gdk.ScrollDirection.DOWN:
            self.__window.container.pages_manager.next()
            self.__window.container.pages_manager.ctrl_released()

    def _on_button_press_event(self, eventbox, event):
        """
            Hide popover or close view
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        if event.button == 2:
            for view in self.__views:
                self.__window.container.pages_manager.try_close_view(view)
            return True
        elif event.button == 3:
            from eolie.menu_sites import SitesMenu
            menu = SitesMenu(self.__views, self.__window)
            popover = Gtk.Popover.new_from_model(eventbox, menu)
            popover.set_position(Gtk.PositionType.RIGHT)
            popover.forall(self.__update_popover_internals)
            popover.show()
            return True

#######################
# PRIVATE             #
#######################
    def __update_popover_internals(self, widget):
        """
            Little hack to manage Gtk.ModelButton text
            @param widget as Gtk.Widget
        """
        if isinstance(widget, Gtk.Label):
            widget.set_ellipsize(Pango.EllipsizeMode.END)
            widget.set_max_width_chars(40)
            widget.set_tooltip_text(widget.get_text())
        elif hasattr(widget, "forall"):
            GLib.idle_add(widget.forall, self.__update_popover_internals)

    def __set_initial_artwork(self, uri):
        """
            Set initial artwork on widget
            @param uri as str
            @param ephemeral as bool
        """
        artwork = El().art.get_icon_theme_artwork(
                                                 uri,
                                                 self.__ephemeral)
        if artwork is not None:
            self.__image.set_from_icon_name(artwork,
                                            Gtk.IconSize.INVALID)
        else:
            self.__image.set_from_icon_name("applications-internet",
                                            Gtk.IconSize.INVALID)

    def __on_webview_favicon_changed(self, webview, favicon,
                                     icon_theme_artwork):
        """
            Set favicon
            @param webview as WebView
            @param favicon as cairo.Surface
            @param icon_theme_artwork as str
        """
        if favicon is not None:
            self.__image.set_from_surface(favicon)

    def __on_query_tooltip(self, widget, x, y, keyboard, tooltip):
        """
            Show tooltip if needed
            @param widget as Gtk.Widget
            @param x as int
            @param y as int
            @param keyboard as bool
            @param tooltip as Gtk.Tooltip
        """
        tooltip = "<b>%s</b>" % GLib.markup_escape_text(self.__netloc)
        for view in self.__views:
            title = view.webview.get_title()
            if not title:
                title = view.webview.get_uri()
            tooltip += "\n%s" % GLib.markup_escape_text(title)
        widget.set_tooltip_markup(tooltip)

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
            Send netloc
            @param widget as Gtk.Widget
            @param context as Gdk.DragContext
            @param data as Gtk.SelectionData
            @param info as int
            @param time as int
        """
        data.set_text(self.__netloc, len(self.__netloc))

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
            netloc = data.get_text()
            self.emit("moved", netloc, up)
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

    def __on_webview_shown(self, webview):
        """
            Update indicataor
        """
        self.__indicator_label.mark_shown(webview)
