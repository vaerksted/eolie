# Copyright (c) 2017-2019 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from eolie.label_indicator import LabelIndicator
from eolie.utils import resize_favicon, update_popover_internals
from eolie.utils import get_round_surface, get_char_surface, get_safe_netloc
from eolie.define import App
from eolie.logger import Logger


class SitesManagerChild(Gtk.ListBoxRow):
    """
        Child showing snapshot, title and favicon
    """

    def __init__(self, netloc, window, is_ephemeral):
        """
            Init child
            @param netloc as str
            @param window as Window
            @param is_ephemeral as bool
        """
        Gtk.ListBoxRow.__init__(self)
        self.__window = window
        self.__netloc = netloc
        self.__minimal = None
        self.__current_child = None
        self.__is_ephemeral = is_ephemeral
        self.__webviews = []
        self.__connected_ids = []
        self.__scroll_timeout_id = None
        self.set_margin_top(1)
        self.get_style_context().add_class("sidebar-item")
        self.set_property("has-tooltip", True)
        self.connect("query-tooltip", self.__on_query_tooltip)
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/SitesManagerChild.ui")
        builder.connect_signals(self)
        widget = builder.get_object("widget")
        self.__netloc_label = builder.get_object("netloc_label")
        self.__indicator_label = LabelIndicator(True)
        self.__indicator_label.set_hexpand(True)
        self.__indicator_label.show()
        builder.get_object("grid").attach(self.__indicator_label, 1, 0, 1, 1)
        self.__separator = builder.get_object("separator")
        self.__image = builder.get_object("image")
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
        self.set_property("margin", 2)

    def add_webview(self, webview):
        """
            Add webview
            @param webview as WebView
            @param uri as str
        """
        if webview not in self.__webviews:
            self.__webviews.append(webview)
            webview.connect("load-changed", self.on_webview_load_changed)
            webview.connect("notify::is-playing-audio",
                            self.__on_webview_notify_is_playing_audio)
            webview.connect("notify::favicon",
                            self.__on_webview_favicon_changed)
            self.__indicator_label.add()
            self.__indicator_label.mark(webview)
            self.__netloc_label.set_text(get_safe_netloc(webview.uri))
            # URI is None, webview not loaded, get favicon from cache
            if webview.get_uri() is None:
                uri = webview.uri
                favicon_path = App().art.get_favicon_path(uri)
                if favicon_path is not None:
                    self.__image.set_from_file(favicon_path)

    def remove_webview(self, webview):
        """
            Remove webview and destroy self if no more webview
            @param webview as WebView
        """
        if webview in self.__webviews:
            self.__webviews.remove(webview)
            webview.disconnect_by_func(self.__on_webview_favicon_changed)
            webview.disconnect_by_func(self.on_webview_load_changed)
            webview.disconnect_by_func(
                self.__on_webview_notify_is_playing_audio)
            self.__indicator_label.remove()
            self.__indicator_label.mark(webview)
            if self.__webviews:
                self.__set_favicon(self.__webviews[0])

    def show_label(self, show):
        """
            Show netloc label
            @param show as bool
        """
        if show:
            self.__netloc_label.show()
        else:
            self.__netloc_label.hide()

    def update_favicon(self):
        """
            Update favicon for current webview
        """
        if self.__window.container.webview in self.__webviews:
            self.__set_favicon(self.__window.container.webview)

    def reset(self, netloc):
        """
            Reset widget to new netloc
            @param netloc as str
        """
        if netloc != self.__netloc:
            self.__netloc = netloc

    def on_webview_load_changed(self, webview, event):
        """
            Update widget content
            @param webview as WebView
            @param event as WebKit2.LoadEvent
        """
        if event in [WebKit2.LoadEvent.STARTED,
                     WebKit2.LoadEvent.COMMITTED]:
            self.__image.set_from_icon_name(
                "emblem-synchronizing-symbolic", Gtk.IconSize.MENU)
            self.__image.get_style_context().add_class("image-rotate")
        elif event == WebKit2.LoadEvent.FINISHED:
            self.__set_favicon(webview)

    @property
    def indicator_label(self):
        """
            Get indicator
            @return IndicatorLabel
        """
        return self.__indicator_label

    @property
    def empty(self):
        """
            True if no webview associated
            @return bool
        """
        return len(self.__webviews) == 0

    @property
    def webviews(self):
        """
            Get webviews
            @return [webview]
        """
        return self.__webviews

    @property
    def is_ephemeral(self):
        """
            True if ephemeral
            @return bool
        """
        return self.__is_ephemeral

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
    def _on_button_press_event(self, eventbox, event):
        """
            Hide popover or close webview
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        try:
            if event.button == 2:
                for webview in self.__webviews:
                    self.__window.container.try_close_webview(webview)
                return True
            elif event.button == 3:
                from eolie.menu_sites import SitesMenu
                from eolie.menu_move_to import MoveToMenu
                sites_menu = SitesMenu(self.__webviews, self.__window)
                sites_menu.show()
                moveto_menu = MoveToMenu(self.__webviews, self.__window)
                moveto_menu.show()
                popover = Gtk.PopoverMenu.new()
                popover.add(sites_menu)
                popover.add(moveto_menu)
                popover.child_set_property(moveto_menu,
                                           "submenu", "moveto")
                popover.set_relative_to(eventbox)
                popover.set_position(Gtk.PositionType.RIGHT)
                popover.forall(update_popover_internals)
                popover.show()
                return True
        except Exception as e:
            Logger.error("SitesManagerChild::_on_button_press_event: %s", e)

#######################
# PRIVATE             #
#######################
    def __set_favicon(self, webview):
        """
            Set webview favicon
            @param webview as WebView
        """
        self.__image.get_style_context().remove_class("image-rotate")
        artwork = App().art.get_icon_theme_artwork(webview.uri,
                                                   webview.is_ephemeral)
        if artwork is not None:
            self.__image.set_from_icon_name(
                artwork, Gtk.IconSize.LARGE_TOOLBAR)
        else:
            surface = webview.get_favicon()
            if surface is not None:
                surface = get_round_surface(surface,
                                            webview.get_scale_factor(),
                                            surface.get_width() / 4)
                self.__image.set_from_surface(resize_favicon(surface))
            else:
                surface = get_char_surface(get_safe_netloc(webview.uri)[0])
                self.__image.set_from_surface(surface)

    def __on_webview_notify_is_playing_audio(self, webview, playing):
        """
            Update favicon
            @param webview as WebView
            @param playing as bool
        """
        if playing:
            self.__image.set_from_icon_name("audio-speakers-symbolic",
                                            Gtk.IconSize.BUTTON)
        else:
            self.__set_favicon(webview)

    def __on_webview_favicon_changed(self, webview, *ignore):
        """
            Set favicon
            @param webview as WebView
        """
        if self.__image.get_icon_name()[0] == "emblem-synchronizing-symbolic":
            return
        if webview.get_favicon() is not None:
            self.__set_favicon(webview)

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
        for webview in self.__webviews:
            title = webview.get_title()
            if title is not None:
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
        if y > height / 2:
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
        if y > height / 2:
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
