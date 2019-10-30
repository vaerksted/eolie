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

from gi.repository import Gtk, GLib, WebKit2, Pango

from gettext import gettext as _

from eolie.label_indicator import LabelIndicator
from eolie.define import App, ArtSize
from eolie.utils import update_popover_internals


class PagesManagerChild(Gtk.FlowBoxChild):
    """
        Child showing snapshot, title and favicon
    """

    def __init__(self, view, window):
        """
            Init child
            @param view as View
            @param window as Window
        """
        Gtk.FlowBoxChild.__init__(self)
        self.__view = view
        self.__window = window
        self.__connected_ids = []
        self.__scroll_timeout_id = None
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/PagesManagerChild.ui")
        builder.connect_signals(self)
        self.__indicator_label = LabelIndicator(False)
        self.__indicator_label.mark_unshown(view.webview)
        self.__indicator_label.set_hexpand(True)
        self.__indicator_label.set_margin_right(4)
        self.__indicator_label.set_property("halign", Gtk.Align.CENTER)
        self.__indicator_label.set_property("valign", Gtk.Align.CENTER)
        self.__indicator_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.__indicator_label.show()
        self.__indicator_image = builder.get_object("indicator_image")
        if view.webview.title:
            self.__indicator_label.set_text(view.webview.title)
        builder.get_object("grid").attach(self.__indicator_label, 1, 0, 1, 1)
        self.__image = builder.get_object("image")
        self.__pin_button = builder.get_object("pin_button")
        self.__pin_image = builder.get_object("pin_image")
        self.__close_button = builder.get_object("close_button")
        self.__close_button_image = self.__close_button.get_image()
        self.__close_button_image.set_from_icon_name(
            "window-close-symbolic",
            Gtk.IconSize.INVALID)
        self.__close_button_image.set_property("pixel-size",
                                               ArtSize.FAVICON)
        self.add(builder.get_object("widget"))

        self.get_style_context().add_class("sidebar-item")

        self.set_property("has-tooltip", True)
        self.set_property("halign", Gtk.Align.START)
        self.set_margin_start(20)
        self.set_margin_end(20)
        self.set_margin_top(20)
        self.set_margin_bottom(20)
        self.set_size_request(ArtSize.START_WIDTH +
                              ArtSize.PREVIEW_WIDTH_MARGIN,
                              ArtSize.START_HEIGHT +
                              ArtSize.PREVIEW_WIDTH_MARGIN)
        self.connect("query-tooltip", self.__on_query_tooltip)
        view.connect("destroying", self.__on_view_destroying)
        self.__view.webview.connect("snapshot-changed",
                                    self.__on_webview_snapshot_changed)
        self.__view.webview.connect("notify::is-playing-audio",
                                    self.__on_webview_notify_is_playing_audio)
        self.__view.webview.connect("title-changed",
                                    self.__on_webview_title_changed)
        self.__view.webview.connect("load-changed",
                                    self.__on_webview_load_changed)
        self.__view.webview.connect("shown",
                                    self.__on_webview_shown)

    @property
    def view(self):
        """
            Get linked view
            @return View
        """
        return self.__view

#######################
# PROTECTED           #
#######################
    def _on_button_press_event(self, eventbox, event):
        """
            Hide popover or close view
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        if event.button == 2:
            self.__window.container.try_close_view(self.__view)
            return True
        elif event.button == 3:
            from eolie.menu_move_to import MoveToMenu
            moveto_menu = MoveToMenu([self.__view], self.__window, False)
            moveto_menu.show()
            popover = Gtk.PopoverMenu.new()
            popover.set_relative_to(eventbox)
            popover.set_position(Gtk.PositionType.BOTTOM)
            popover.add(moveto_menu)
            popover.forall(update_popover_internals)
            popover.show()
            return True

    def _on_button_release_event(self, eventbox, event):
        """
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        pass

    def _on_pin_button_clicked(self, button):
        """
            Pin/Unpin page
            @param button as Gtk.Button
        """
        if self.view.webview.uri in App().pinned:
            self.__pin_image.set_opacity(0.5)
            App().remove_from_pinned(self.view.webview.uri)
        else:
            self.__pin_image.set_opacity(1)
            App().add_to_pinned(self.view.webview.uri)
        return True

    def _on_close_button_clicked(self, button):
        """
            Destroy self
            @param button as Gtk.Button
        """
        self.__window.container.try_close_view(self.__view)
        return True

    def _on_enter_notify_event(self, eventbox, event):
        """
            Show close button
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        if self.view.webview.uri in App().pinned:
            self.__pin_image.set_opacity(1)
            self.__pin_button.set_tooltip_text(_("Unpin this page"))
        else:
            self.__pin_image.set_opacity(0.5)
            self.__pin_button.set_tooltip_text(_("Pin this page"))
        self.__pin_button.set_opacity(1)
        self.__close_button_image.set_from_icon_name(
            "window-close-symbolic",
            Gtk.IconSize.INVALID)

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
            self.__pin_button.set_opacity(0)
            self.__on_webview_favicon_changed(self.__view.webview)

#######################
# PRIVATE             #
#######################
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
        label = self.__indicator_label.get_text()
        uri = self.__view.webview.uri
        # GLib.markup_escape_text
        if uri is None:
            text = "<b>%s</b>" % GLib.markup_escape_text(label)
        else:
            text = "<b>%s</b>\n%s" % (GLib.markup_escape_text(label),
                                      GLib.markup_escape_text(uri))
        widget.set_tooltip_markup(text)

    def __on_view_destroying(self, view):
        """
            Destroy self
            @param view as View
        """
        self.__view.webview.disconnect_by_func(
                                    self.__on_webview_snapshot_changed)
        self.__view.webview.disconnect_by_func(
                                    self.__on_webview_favicon_changed)
        self.__view.webview.disconnect_by_func(
                                    self.__on_webview_notify_is_playing_audio)
        self.__view.webview.disconnect_by_func(
                                    self.__on_webview_title_changed)
        self.__view.webview.disconnect_by_func(
                                    self.__on_webview_load_changed)
        self.__view.webview.disconnect_by_func(
                                    self.__on_webview_shown)
        self.destroy()

    def __on_webview_notify_is_playing_audio(self, webview, playing):
        """
            Update favicon
            @param webview as WebView
            @param playing as bool
        """
        if playing:
            self.__indicator_image.set_from_icon_name(
                "audio-speakers-symbolic", Gtk.IconSize.BUTTON)
        else:
            self.__indicator_image.set_from_surface(None)

    def __on_webview_title_changed(self, webview, title):
        """
            Update title
            @param webview as WebView
            @param title as str
        """
        self.__indicator_label.set_text(title)

    def __on_webview_load_changed(self, webview, event):
        """
            Update widget content
            @param webview as WebView
            @param event as WebKit2.LoadEvent
        """
        if event != WebKit2.LoadEvent.FINISHED:
            self.__indicator_image.set_from_icon_name(
                "emblem-synchronizing-symbolic", Gtk.IconSize.MENU)
            self.__indicator_image.get_style_context().add_class(
                "image-rotate")
        else:
            self.__indicator_image.set_from_surface(None)
            self.__indicator_image.get_style_context().remove_class(
                "image-rotate")

    def __on_webview_snapshot_changed(self, webview, surface):
        """
            Update preview with surface
            @param webview as WebView
            @param surface as cairo.surface
        """
        if self.__view.webview.ephemeral:
            self.__image.set_from_icon_name(
                "user-not-tracked-symbolic",
                Gtk.IconSize.DIALOG)
        else:
            self.__image.set_from_surface(surface)

    def __on_webview_shown(self, webview):
        """
            Remove indicator
        """
        self.__indicator_label.mark_shown(webview)
