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

from gi.repository import Gtk, GLib, WebKit2, Pango

from eolie.label_indicator import LabelIndicator
from eolie.define import App, ArtSize
from eolie.utils import get_snapshot


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
        self.__favicon = None
        self.__connected_ids = []
        self.__scroll_timeout_id = None
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/PagesManagerChild.ui")
        builder.connect_signals(self)
        self.__indicator_label = LabelIndicator()
        self.__indicator_label.mark_unshown(view.webview)
        self.__indicator_label.set_hexpand(True)
        self.__indicator_label.set_margin_right(4)
        self.__indicator_label.set_property("halign", Gtk.Align.CENTER)
        self.__indicator_label.set_property("valign", Gtk.Align.CENTER)
        self.__indicator_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.__indicator_label.show()
        if view.webview.title:
            self.__indicator_label.set_text(view.webview.title)
        builder.get_object("grid").attach(self.__indicator_label, 0, 0, 1, 1)
        self.__image = builder.get_object("image")
        self.__close_button = builder.get_object("close_button")
        self.__audio_indicator = builder.get_object("audio_indicator")
        if view.webview.is_playing_audio():
            self.__audio_indicator.show()
        self.__close_button.get_image().set_from_icon_name(
            "window-close-symbolic",
            Gtk.IconSize.INVALID)
        self.__close_button.get_image().set_property("pixel-size",
                                                     ArtSize.FAVICON)
        self.__spinner = builder.get_object("spinner")
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
        self.__connected_signals = []
        self.__connected_signals.append(
            self.__view.webview.connect("favicon-changed",
                                        self.__on_webview_favicon_changed))
        self.__connected_signals.append(
            self.__view.webview.connect(
                "notify::is-playing-audio",
                self.__on_webview_notify_is_playing_audio))
        self.__connected_signals.append(
            self.__view.webview.connect("uri-changed",
                                        self.__on_webview_uri_changed))
        self.__connected_signals.append(
            self.__view.webview.connect("title-changed",
                                        self.__on_webview_title_changed))
        self.__connected_signals.append(
            self.__view.webview.connect("scroll-event",
                                        self.__on_webview_scroll_event))
        self.__connected_signals.append(
            self.__view.webview.connect("load-changed",
                                        self.__on_webview_load_changed))
        self.__connected_signals.append(
            self.__view.webview.connect("shown",
                                        self.__on_webview_shown))
        self.__set_favicon_artwork()
        if self.__view.webview.uri is not None:
            artwork_path = App().art.get_path(self.__view.webview.uri, "start")
            if artwork_path is not None and\
                    GLib.file_test(artwork_path, GLib.FileTest.IS_REGULAR):
                self.__image.set_from_file(artwork_path)

    def destroy(self):
        """
            Disconnect signals and destroy self
        """
        for signal_id in self.__connected_signals:
            self.__view.webview.disconnect(signal_id)
        Gtk.FlowBoxChild.destroy(self)

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
            popover.forall(self.__update_popover_internals)
            popover.show()
            return True

    def _on_button_release_event(self, eventbox, event):
        """
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        pass

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
        self.__close_button.get_image().set_from_icon_name(
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
            self.__set_favicon_artwork()

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

    def __set_favicon_artwork(self):
        """
            Set favicon artwork
        """
        if self.__view.webview.ephemeral:
            return
        image = self.__close_button.get_image()
        if self.__favicon is not None:
            image.set_from_surface(self.__favicon)
        else:
            uri = self.__view.webview.uri
            artwork = App().art.get_icon_theme_artwork(
                uri,
                self.view.webview.ephemeral)
            if artwork is not None:
                image.set_from_icon_name(artwork,
                                         Gtk.IconSize.INVALID)
            else:
                favicon_path = App().art.get_favicon_path(uri)
                if favicon_path is not None:
                    image.set_from_file(favicon_path)
                else:
                    image.set_from_icon_name("applications-internet",
                                             Gtk.IconSize.INVALID)

    def __set_snapshot(self):
        """
            Set webpage preview
        """
        if self.__view.webview.ephemeral:
            self.__image.set_from_icon_name(
                "user-not-tracked-symbolic",
                Gtk.IconSize.DIALOG)
        else:
            self.__view.webview.get_snapshot(
                WebKit2.SnapshotRegion.VISIBLE,
                WebKit2.SnapshotOptions.NONE,
                None,
                get_snapshot,
                self.__on_snapshot)

    def __on_scroll_timeout(self):
        """
            Update snapshot
        """
        self.__scroll_timeout_id = None
        self.__set_snapshot()

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
        self.destroy()

    def __on_webview_favicon_changed(self, webview, favicon,
                                     icon_theme_artwork):
        """
            Set favicon
            @param webview as WebView
            @param favicon as cairo.Surface
            @param icon_theme_artwork as str
        """
        if favicon is not None:
            self.__favicon = favicon
            self.__close_button.get_image().set_from_surface(favicon)
        elif icon_theme_artwork is not None:
            self.__close_button.get_image().set_from_icon_name(
                icon_theme_artwork,
                Gtk.IconSize.INVALID)

    def __on_webview_notify_is_playing_audio(self, webview, playing):
        """
            Update status
            @param webview as WebView
            @param playing as bool
        """
        if not webview.is_loading() and webview.is_playing_audio():
            self.__audio_indicator.show()
        else:
            self.__audio_indicator.hide()

    def __on_webview_scroll_event(self, webview, event):
        """
            Update snapshot
            @param webview as WebView
            @param event as Gdk.EventScroll
        """
        if self.__scroll_timeout_id is not None:
            GLib.source_remove(self.__scroll_timeout_id)
        self.__scroll_timeout_id = GLib.timeout_add(250,
                                                    self.__on_scroll_timeout)

    def __on_snapshot(self, surface):
        """
            Set snapshot
            @param surface as cairo.Surface
        """
        self.__image.set_from_surface(surface)

    def __on_webview_uri_changed(self, webview, uri):
        """
            Update uri
            @param webview as WebView
            @param uri as str
        """
        # Js change, update snapshot
        if not webview.is_loading() and not webview.ephemeral:
            GLib.timeout_add(500, self.__set_snapshot)

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
        uri = webview.uri
        if event == WebKit2.LoadEvent.STARTED:
            self.__favicon = None
            self.__image.clear()
            self.__audio_indicator.hide()
            self.__spinner.start()
            self.__indicator_label.set_text(uri)
        elif event == WebKit2.LoadEvent.COMMITTED:
            self.__indicator_label.set_text(uri)
        elif event == WebKit2.LoadEvent.FINISHED:
            self.__spinner.stop()
            if webview.is_playing_audio():
                self.__audio_indicator.show()
            GLib.timeout_add(500, self.__set_snapshot)

    def __on_webview_shown(self, webview):
        """
            Remove indicator
        """
        self.__indicator_label.mark_shown(webview)
