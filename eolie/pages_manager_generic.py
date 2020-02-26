# Copyright (c) 2017-2020 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from gi.repository import Gtk, Pango, WebKit2

from eolie.widget_label_indicator import LabelIndicator
from eolie.define import ArtSize, MARGIN_SMALL, MARGIN
from eolie.utils import on_query_tooltip, update_popover_internals
from eolie.helper_signals import SignalsHelper, signals
from eolie.helper_gestures import GesturesHelper


class PagesManagerGenericChild(SignalsHelper, GesturesHelper):
    """
        Widget showing a webpage snapshot and title
    """

    @signals
    def __init__(self, webview, window):
        """
            Init child
            @param webview as WebView
            @param window as Window
        """
        GesturesHelper.__init__(self, self)

        self.__webview = webview
        self.__window = window

        self.get_style_context().add_class("sidebar-item")

        close_button = Gtk.Button.new_from_icon_name(
            "window-close-symbolic", Gtk.IconSize.LARGE_TOOLBAR)
        close_button.show()
        close_button.set_relief(Gtk.ReliefStyle.NONE)
        close_button.get_style_context().add_class("no-border-button")
        close_button.set_property("valign", Gtk.Align.CENTER)
        close_button.set_property("halign", Gtk.Align.END)
        close_button.connect("clicked", self.__on_close_button_clicked)

        self.__indicator_label = LabelIndicator(False)
        self.__indicator_label.show()
        self.__indicator_label.mark(webview)
        self.__indicator_label.set_hexpand(True)
        self.__indicator_label.set_margin_right(4)
        self.__indicator_label.set_property("halign", Gtk.Align.CENTER)
        self.__indicator_label.set_property("valign", Gtk.Align.CENTER)
        self.__indicator_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.__indicator_label.set_property("has-tooltip", True)
        self.__indicator_label.connect("query-tooltip", on_query_tooltip)
        if webview.title:
            self.__indicator_label.set_text(webview.title)

        self.__indicator_image = Gtk.Image.new()
        self.__indicator_image.show()
        self.__indicator_image.set_property("halign", Gtk.Align.CENTER)
        self.__indicator_image.set_property("valign", Gtk.Align.CENTER)

        self.__background_image = Gtk.Image.new_from_surface(webview.surface)
        self.__background_image.show()
        self.__background_image.get_style_context().add_class(
            "sidebar-item-image")

        grid = Gtk.Grid()
        grid.show()
        grid.get_style_context().add_class("sidebar-item-title")
        grid.set_column_spacing(MARGIN_SMALL)
        grid.set_vexpand(True)
        grid.set_property("valign", Gtk.Align.END)
        grid.set_property("margin", MARGIN_SMALL)
        grid.add(self.__indicator_label)
        grid.add(close_button)

        overlay = Gtk.Overlay.new()
        overlay.show()
        overlay.add(self.__background_image)
        overlay.add_overlay(grid)
        overlay.add_overlay(self.__indicator_image)

        self.set_property("halign", Gtk.Align.START)
        self.set_property("margin", MARGIN)
        # padding + border
        self.set_size_request(ArtSize.START_WIDTH + 8,
                              ArtSize.START_HEIGHT + 8)
        self.add(overlay)

        return [
            (webview, "snapshot-changed", "_on_webview_snapshot_changed"),
            (webview, "notify::is-playing-audio",
                      "_on_webview_notify_is_playing_audio"),
            (webview, "title-changed", "_on_webview_title_changed"),
            (webview, "load-changed", "_on_webview_load_changed"),
            (webview, "destroy", "_on_webview_destroyed")
        ]

    @property
    def indicator_label(self):
        """
            Get indicator
            @return IndicatorLabel
        """
        return self.__indicator_label

    @property
    def webview(self):
        """
            Get linked webview
            @return WebView
        """
        return self.__webview

#######################
# PROTECTED           #
#######################
    def _on_secondary_press_gesture(self, x, y):
        """
            Show row menu
            @param x as int
            @param y as int
        """
        self.__window.container.try_close_webview(self.__webview)

    def _on_tertiary_press_gesture(self, eventbox, event):
        """
            Hide popover or close view
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        from eolie.menu_move_to import MoveToMenu
        moveto_menu = MoveToMenu([self.__webview], self.__window, False)
        moveto_menu.show()
        popover = Gtk.PopoverMenu.new()
        popover.set_relative_to(eventbox)
        popover.set_position(Gtk.PositionType.BOTTOM)
        popover.add(moveto_menu)
        popover.forall(update_popover_internals)
        popover.show()

    def _on_webview_notify_is_playing_audio(self, webview, playing):
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

    def _on_webview_title_changed(self, webview, title):
        """
            Update title
            @param webview as WebView
            @param title as str
        """
        if title:
            self.__indicator_label.set_text(title)

    def _on_webview_load_changed(self, webview, event):
        """
            Update widget content
            @param webview as WebView
            @param event as WebKit2.LoadEvent
        """
        if event != WebKit2.LoadEvent.FINISHED:
            self.__background_image.set_from_surface(None)
            self.__indicator_image.set_from_surface(None)
            self.__indicator_image.set_from_icon_name(
                "emblem-synchronizing-symbolic", Gtk.IconSize.MENU)
            self.__indicator_image.get_style_context().add_class(
                "image-rotate")
        else:
            self.__indicator_image.set_from_surface(None)
            self.__indicator_image.get_style_context().remove_class(
                "image-rotate")

    def _on_webview_snapshot_changed(self, webview, surface):
        """
            Update preview with surface
            @param webview as WebView
            @param surface as cairo.surface
        """
        if webview.is_ephemeral:
            self.__background_image.set_from_icon_name(
                "user-not-tracked-symbolic",
                Gtk.IconSize.DIALOG)
        else:
            self.__background_image.set_from_surface(surface)

    def _on_webview_destroyed(self, webview):
        """
            Destroy self
            @param webview as WebView
        """
        self.destroy()

#######################
# PRIVATE             #
#######################
    def __on_close_button_clicked(self, button):
        """
            Destroy self
            @param button as Gtk.Button
        """
        self.__window.container.try_close_webview(self.__webview)
