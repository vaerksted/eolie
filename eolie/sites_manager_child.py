# Copyright (c) 2017-2018 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from gi.repository import Gtk, Gdk, GLib, Pango, GObject, WebKit2

from eolie.label_indicator import LabelIndicator
from eolie.define import App, ArtSize
from eolie.logger import Logger


class PageChildRow(Gtk.ListBoxRow):
    """
        Label for a view
    """

    def __init__(self, view, window):
        """
            Init widget
            @param view as View
            @param window as Window
        """
        Gtk.ListBoxRow.__init__(self)
        eventbox = Gtk.EventBox()
        eventbox.show()
        self.get_style_context().add_class("page-child-row")
        self.__view = view
        self.__window = window
        self.__label = Gtk.Label.new(view.webview.title)
        self.__label.set_property("valign", Gtk.Align.CENTER)
        self.__label.set_ellipsize(Pango.EllipsizeMode.END)
        self.__label.set_hexpand(True)
        self.__label.show()
        button = Gtk.Button.new_from_icon_name("window-close-symbolic",
                                               Gtk.IconSize.MENU)
        button.set_relief(Gtk.ReliefStyle.NONE)
        button.get_style_context().add_class("no-padding")
        button.set_property("valign", Gtk.Align.CENTER)
        button.set_property("halign", Gtk.Align.END)
        button.connect("clicked", self.__on_button_clicked)
        button.show()
        grid = Gtk.Grid()
        grid.add(self.__label)
        grid.add(button)
        grid.show()
        eventbox.add(grid)
        self.add(eventbox)
        self.connect("destroy", self.__on_destroy)
        self.set_property("has-tooltip", True)
        self.connect("query-tooltip", self.__on_query_tooltip)
        view.webview.connect("load-changed", self.__on_webview_load_changed)
        view.webview.connect("title-changed", self.__on_webview_title_changed)
        eventbox.connect("button-press-event", self.__on_button_press_event)

    @property
    def view(self):
        """
            Get associated view
        """
        return self.__view

#######################
# PRIVATE             #
#######################
    def __on_button_clicked(self, button):
        """
            Close view
            @param button as Gtk.Button
        """
        self.__window.container.try_close_view(self.__view)

    def __on_query_tooltip(self, widget, x, y, keyboard, tooltip):
        """
            Show tooltip if needed
            @param widget as Gtk.Widget
            @param x as int
            @param y as int
            @param keyboard as bool
            @param tooltip as Gtk.Tooltip
        """
        title = self.__view.webview.get_title()
        if title is not None:
            tooltip = GLib.markup_escape_text(title)
            widget.set_tooltip_markup(tooltip)

    def __on_button_press_event(self, widget, event):
        """
            Switch to view
            @param widget as Gtk.Widget
            @param event as Gdk.Event
        """
        self.__window.container.set_current(self.__view, True)
        self.__window.container.set_expose(False)
        return True

    def __on_destroy(self, widget):
        """
            Disconnect signals
            @param widget as Gtk.Widget
        """
        self.__view.webview.disconnect_by_func(self.__on_webview_load_changed)
        self.__view.webview.disconnect_by_func(self.__on_webview_title_changed)

    def __on_webview_load_changed(self, webview, event):
        """
            Update widget content
            @param webview as WebView
            @param event as WebKit2.LoadEvent
        """
        if event in [WebKit2.LoadEvent.STARTED,
                     WebKit2.LoadEvent.COMMITTED]:
            self.__label.set_text(webview.get_uri())

    def __on_webview_title_changed(self, webview, title):
        """
            Update title
            @param webview as WebView
            @param title as str
        """
        self.__label.set_text(title)


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
        self.__minimal = None
        self.__ephemeral = ephemeral
        self.__views = []
        self.__connected_ids = []
        self.__scroll_timeout_id = None
        self.__pages_listbox = None
        self.set_margin_top(1)
        self.set_property("has-tooltip", True)
        self.connect("query-tooltip", self.__on_query_tooltip)
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/SitesManagerChild.ui")
        builder.connect_signals(self)
        widget = builder.get_object("widget")
        self.__indicator_label = LabelIndicator()
        self.__indicator_label.set_property("halign", Gtk.Align.CENTER)
        self.__indicator_label.show()
        self.__separator = builder.get_object("separator")
        self.__grid = builder.get_object("grid")
        self.__netloc_label = builder.get_object("netloc")
        self.__netloc_label.set_text(self.__netloc)
        self.__image = builder.get_object("image")
        self.__image.set_property("pixel-size", ArtSize.FAVICON)
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
            if view.webview.shown:
                self.__on_webview_favicon_changed(view.webview)
            else:
                self.__indicator_label.mark_unshown(view.webview)
            if self.__pages_listbox is not None:
                child = PageChildRow(view, self.__window)
                child.show()
                self.__pages_listbox.add(child)

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
            if self.__pages_listbox is not None:
                for child in self.__pages_listbox.get_children():
                    if child.view == view:
                        self.__pages_listbox.remove(child)
                        break
        if self.__views:
            self.__on_webview_favicon_changed(self.__views[0].webview)

    def set_minimal(self, minimal):
        """
            Make widget minimal
            @param minimal as bool
        """
        if self.__minimal == minimal:
            return
        if minimal:
            self.__grid.remove(self.__netloc_label)
            if self.__pages_listbox is not None:
                self.__grid.remove(self.__pages_listbox)
                self.__pages_listbox.destroy()
            self.__pages_listbox = None
            self.__grid.attach(self.__indicator_label, 1, 0, 1, 1)
            self.__image.set_property("halign", Gtk.Align.CENTER)
            self.__image.set_hexpand(True)
            self.__separator.hide()
        else:
            self.__grid.remove(self.__indicator_label)
            self.__grid.attach(self.__netloc_label, 1, 0, 1, 1)
            self.__pages_listbox = Gtk.ListBox.new()
            self.__pages_listbox.show()
            self.__separator.show()
            self.__grid.attach(self.__pages_listbox, 0, 2, 2, 1)
            self.__image.set_hexpand(False)
            self.__image.set_property("halign", Gtk.Align.START)
            # Setup listbox
            current = self.__window.container.current
            for view in self.__views:
                child = PageChildRow(view, self.__window)
                child.show()
                self.__pages_listbox.add(child)
                if view == current:
                    self.__pages_listbox.select_row(child)
        self.__minimal = minimal

    def reset(self, netloc):
        """
            Reset widget to new netloc
            @param netloc as str
        """
        if netloc != self.__netloc:
            self.__netloc = netloc
            if self.__views:
                self.__set_favicon(self.__views[0].webview)
            self.__netloc_label.set_text(self.__netloc)

    def update_label(self):
        """
            Update label: if one view, use title else use netloc
            @param view as View
        """
        self.__netloc_label.set_text(self.__netloc)

    def set_selected(self, selected):
        """
            Mark self as selected
            @param selected as bool
        """
        if selected:
            self.get_style_context().add_class("item-selected")
        else:
            self.get_style_context().remove_class("item-selected")
        if self.__pages_listbox is not None:
            if selected:
                current = self.__window.container.current
                for child in self.__pages_listbox.get_children():
                    if child.view == current:
                        self.__pages_listbox.select_row(child)
            else:
                self.__pages_listbox.unselect_all()

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
    def _on_button_press_event(self, eventbox, event):
        """
            Hide popover or close view
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        try:
            if event.button == 2:
                for view in self.__views:
                    self.__window.container.try_close_view(view)
                return True
            elif event.button == 3:
                from eolie.menu_sites import SitesMenu
                from eolie.menu_profiles import ProfilesMenu
                from eolie.menu_move_to import MoveToMenu
                sites_menu = SitesMenu(self.__views, self.__window)
                sites_menu.show()
                webview = self.__views[0].webview
                profiles_menu = ProfilesMenu(webview, self.__window)
                profiles_menu.show()
                moveto_menu = MoveToMenu(self.__views, self.__window)
                moveto_menu.show()
                popover = Gtk.PopoverMenu.new()
                popover.add(sites_menu)
                popover.add(profiles_menu)
                popover.add(moveto_menu)
                popover.child_set_property(profiles_menu,
                                           "submenu", "profiles")
                popover.child_set_property(moveto_menu,
                                           "submenu", "moveto")
                popover.set_relative_to(eventbox)
                popover.set_position(Gtk.PositionType.RIGHT)
                popover.forall(self.__update_popover_internals)
                popover.show()
                return True
        except Exception as e:
            Logger.error("SitesManagerChild::_on_button_press_event:", e)

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
            widget.set_max_width_chars(30)
            widget.set_tooltip_text(widget.get_text())
        elif hasattr(widget, "forall"):
            GLib.idle_add(widget.forall, self.__update_popover_internals)

    def __on_webview_favicon_changed(self, webview, surface=None):
        """
            Set favicon
            @param webview as WebView
            @param surface as cairo.Surface
        """
        if surface is not None:
            self.__image.set_from_surface(surface)
            return

        favicon_path = App().art.get_favicon_path(webview.uri)
        if favicon_path is not None:
            self.__image.set_from_file(favicon_path)
            return

        artwork = App().art.get_icon_theme_artwork(webview.uri,
                                                   webview.ephemeral)
        if artwork is not None:
            self.__image.set_from_icon_name(artwork,
                                            Gtk.IconSize.INVALID)
            return

        self.__image.set_from_icon_name("applications-internet",
                                        Gtk.IconSize.INVALID)

    def __on_query_tooltip(self, widget, x, y, keyboard, tooltip):
        """
            Show tooltip if needed
            @param widget as Gtk.Widget
            @param x as int
            @param y as int
            @param keyboard as bool
            @param tooltip as Gtk.Tooltip
        """
        if self.__pages_listbox is not None:
            return
        tooltip = "<b>%s</b>" % GLib.markup_escape_text(self.__netloc)
        for view in self.__views:
            title = view.webview.get_title()
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

    def __on_webview_shown(self, webview):
        """
            Update indicataor
        """
        self.__indicator_label.mark_shown(webview)
        self.__on_webview_favicon_changed(webview)
