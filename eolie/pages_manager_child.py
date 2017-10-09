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

from gi.repository import Gtk, GLib, WebKit2, Pango

from eolie.label_indicator import LabelIndicator
from eolie.define import El, ArtSize
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
        self.__title = LabelIndicator()
        self.__title.set_hexpand(True)
        self.__title.set_margin_right(4)
        self.__title.set_property("halign", Gtk.Align.CENTER)
        self.__title.set_property("valign", Gtk.Align.CENTER)
        self.__title.set_ellipsize(Pango.EllipsizeMode.END)
        self.__title.show()
        builder.get_object("grid").attach(self.__title, 0, 0, 1, 1)
        self.__image = builder.get_object("image")
        self.__close_button = builder.get_object("close_button")
        self.__audio_indicator = builder.get_object("audio_indicator")
        if view.webview.is_playing_audio():
            self.__audio_indicator.show()
        if view.webview.ephemeral:
            self.__close_button.get_image().set_from_icon_name(
                                                  "window-close-symbolic",
                                                  Gtk.IconSize.INVALID)
        else:
            self.__close_button.get_image().set_from_icon_name(
                                                  "applications-internet",
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
        self.connect("destroy", self.__on_destroy)
        self.__view_destroy_id = view.connect("destroy",
                                              self.__on_view_destroy)
        self.__connected_ids.append(
                             self.__view.webview.connect(
                                 "favicon-changed",
                                 self.__on_notify_favicon))
        self.__connected_ids.append(
                             self.__view.webview.connect(
                                 "notify::is-playing-audio",
                                 self.__on_notify_is_playing_audio))
        self.__connected_ids.append(
                             self.__view.webview.connect(
                                 "uri-changed",
                                 self.__on_uri_changed))
        self.__connected_ids.append(
                             self.__view.webview.connect(
                                 "title-changed",
                                 self.__on_title_changed))
        self.__connected_ids.append(
                             self.__view.webview.connect(
                                 "scroll-event",
                                 self.__on_scroll_event))
        self.__connected_ids.append(
                             self.__view.webview.connect(
                                 "load-changed",
                                 self.__on_load_changed))

    @property
    def label_indicator(self):
        """
            Get label indicator
            @return LabelIndicator
        """
        return self.__title

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
            self.__window.container.pages_manager.try_close_view(self.__view)
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
        self.__window.container.pages_manager.try_close_view(self.__view)
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
            if self.__view.webview.ephemeral:
                return
            image = self.__close_button.get_image()
            if self.__favicon is not None:
                image.set_from_surface(self.__favicon)
            else:
                uri = self.__view.webview.get_uri()
                favicon = El().art.get_icon_theme_artwork(uri, False)
                image.set_from_icon_name(favicon, Gtk.IconSize.INVALID)

#######################
# PRIVATE             #
#######################
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
        label = self.__title.get_text()
        uri = self.__view.webview.get_uri()
        # GLib.markup_escape_text
        if uri is None:
            text = "<b>%s</b>" % GLib.markup_escape_text(label)
        else:
            text = "<b>%s</b>\n%s" % (GLib.markup_escape_text(label),
                                      GLib.markup_escape_text(uri))
        widget.set_tooltip_markup(text)

    def __on_destroy(self, widget):
        """
            Disconnect signals
            @param widget as Gtk.Widget
        """
        self.__window.container.sites_manager.remove_view(self.__view)
        while self.__connected_ids:
            connected_id = self.__connected_ids.pop(0)
            self.__view.webview.disconnect(connected_id)
        if self.__view_destroy_id is not None:
            self.__view.disconnect(self.__view_destroy_id)

    def __on_view_destroy(self, view):
        """
            Destroy self
            @param view as View
        """
        self.__connected_ids = []
        self.__view_destroy_id = None
        self.__window.container.sites_manager.remove_view(self.__view)
        GLib.idle_add(self.destroy)

    def __on_notify_favicon(self, webview, favicon, favicon_str):
        """
            Set favicon
            @param webview as WebView
            @param favicon as cairo.Surface
            @param favicon_str as str
        """
        self.__favicon = favicon
        if favicon is not None:
            self.__close_button.get_image().set_from_surface(favicon)
            # Update site manager favicon (missing or obsolete)
            self.__window.container.sites_manager.set_favicon(
                                                          self.__view,
                                                          favicon)
        else:
            self.__close_button.get_image().set_from_icon_name(
                                                  favicon_str,
                                                  Gtk.IconSize.INVALID)

    def __on_notify_is_playing_audio(self, webview, playing):
        """
            Update status
            @param webview as WebView
            @param playing as bool
        """
        if not webview.is_loading() and webview.is_playing_audio():
            self.__audio_indicator.show()
        else:
            self.__audio_indicator.hide()

    def __on_scroll_event(self, webview, event):
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

    def __on_uri_changed(self, webview, uri):
        """
            Update uri
            @param webview as WebView
            @param uri as str
        """
        # Js change, update snapshot
        if not webview.is_loading() and not webview.ephemeral:
            GLib.timeout_add(500, self.__set_snapshot)
        else:
            self.__window.container.sites_manager.add_view_for_uri(
                                                          self.__view,
                                                          uri)

    def __on_title_changed(self, webview, title):
        """
            Update title
            @param webview as WebView
            @param title as str
        """
        self.__title.set_text(title)
        self.__window.container.sites_manager.update_label(
                                               self.__window.container.current)

    def __on_load_changed(self, webview, event):
        """
            Update widget content
            @param webview as WebView
            @param event as WebKit2.LoadEvent
        """
        uri = webview.get_uri()
        if event == WebKit2.LoadEvent.STARTED:
            self.__image.clear()
            self.__audio_indicator.hide()
            self.__spinner.start()
            self.__title.set_text(uri)
        elif event == WebKit2.LoadEvent.COMMITTED:
            self.__title.set_text(uri)
        elif event == WebKit2.LoadEvent.FINISHED:
            self.__spinner.stop()
            if webview.is_playing_audio():
                self.__audio_indicator.show()
            GLib.timeout_add(500, self.__set_snapshot)
