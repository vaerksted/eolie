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

from gi.repository import Gtk, GLib, WebKit2

import cairo
from urllib.parse import urlparse

from eolie.define import El, ArtSize
from eolie.utils import resize_favicon


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
        self.__title = builder.get_object("title")
        self.__image = builder.get_object("image")
        self.__image_close = builder.get_object("image_close")
        self.__audio_indicator = builder.get_object("audio_indicator")
        if view.webview.is_playing_audio():
            self.__audio_indicator.show()
        if view.webview.ephemeral:
            self.__image_close.set_from_icon_name("window-close-symbolic",
                                                  Gtk.IconSize.INVALID)
        else:
            self.__image_close.set_from_icon_name("applications-internet",
                                                  Gtk.IconSize.INVALID)
        self.__image_close.set_property("pixel-size", ArtSize.FAVICON)
        self.__spinner = builder.get_object("spinner")
        self.add(builder.get_object("widget"))

        self.get_style_context().add_class("sidebar-item")

        self.set_property("has-tooltip", True)
        self.set_property("halign", Gtk.Align.START)
        self.set_margin_start(20)
        self.set_margin_end(20)
        self.set_margin_top(20)
        self.set_margin_bottom(20)
        self.set_property("width-request", ArtSize.START_WIDTH +
                          ArtSize.PREVIEW_WIDTH_MARGIN)
        if view.webview.access_time == 0:
            self.get_style_context().add_class("sidebar-item-unread")
        self.connect("query-tooltip", self.__on_query_tooltip)
        self.connect("destroy", self.__on_destroy)
        self.__view_destroy_id = view.connect("destroy",
                                              self.__on_view_destroy)
        self.__connected_ids.append(
                             self.__view.webview.connect(
                                 "notify::favicon",
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

    def set_snapshot(self, uri):
        """
            Set webpage preview
            @param uri as str
        """
        if uri == self.__view.webview.get_uri():
            if self.__view.webview.ephemeral:
                self.__image.set_from_icon_name(
                                             "user-not-tracked-symbolic",
                                             Gtk.IconSize.DIALOG)
            else:
                self.__view.webview.get_snapshot(
                                             WebKit2.SnapshotRegion.VISIBLE,
                                             WebKit2.SnapshotOptions.NONE,
                                             None,
                                             self.__on_snapshot,
                                             uri)

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
            self.__window.container.pages_manager.close_view(self.__view)
            return True

    def _on_button_release_event(self, eventbox, event):
        """
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        pass

    def _on_close_button_press_event(self, eventbox, event):
        """
            Destroy self
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        self.__window.container.pages_manager.close_view(self.__view)
        return True

    def _on_enter_notify_event(self, eventbox, event):
        """
            Show close button
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        self.__image_close.set_from_icon_name("window-close-symbolic",
                                              Gtk.IconSize.INVALID)
        self.__image_close.get_style_context().add_class("sidebar-item-close")

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
        resized = None
        uri = self.__view.webview.get_uri()
        surface = self.__view.webview.get_favicon()
        artwork = El().art.get_icon_theme_artwork(
                                                 uri,
                                                 self.__view.webview.ephemeral)
        if artwork is not None:
            self.__image_close.set_from_icon_name(artwork,
                                                  Gtk.IconSize.INVALID)
        elif surface is not None:
            resized = resize_favicon(surface)
            El().art.save_artwork(uri, resized, "favicon")
            self.__set_favicon_related(resized,
                                       uri,
                                       self.__view.webview.initial_uri)
            self.__image_close.set_from_surface(resized)
            del surface
        else:
            self.__image_close.set_from_icon_name("applications-internet",
                                                  Gtk.IconSize.INVALID)
        if resized is not None:
            self.__window.container.sites_manager.set_favicon(
                                                          self.__view.webview,
                                                          resized)
            del resized

    def __set_favicon_related(self, surface, uri, initial_uri):
        """
            Set favicon for initial uri
            @param surface as cairo.surface
            @param uri as str
            @param initial_uri as str
        """
        parsed = urlparse(uri)
        initial_parsed = urlparse(initial_uri)
        if parsed.netloc == initial_parsed.netloc and\
                initial_uri != uri and\
                not El().art.exists(initial_uri, "favicon"):
            El().art.save_artwork(initial_uri, surface, "favicon")

    def __on_scroll_timeout(self):
        """
            Update snapshot
        """
        uri = self.__view.webview.get_uri()
        self.__scroll_timeout_id = None
        self.set_snapshot(uri)

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
        GLib.idle_add(self.destroy)

    def __on_notify_favicon(self, webview, favicon):
        """
            Set favicon
            @param webview as WebView
            @param favicon as Gparam
        """
        if self.__view.webview == webview:
            self.__set_favicon()

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

    def __on_snapshot(self, webview, result, uri):
        """
            Set snapshot on main image
            @param webview as WebView
            @param result as Gio.AsyncResult
            @param uri as str
        """
        try:
            snapshot = webview.get_snapshot_finish(result)
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
            self.__image.set_from_surface(surface)
            del surface
            del snapshot
        except Exception as e:
            print("PagesManagerChild::__on_snapshot():", e)

    def __on_uri_changed(self, webview, uri):
        """
            Update uri
            @param webview as WebView
            @param uri as str
        """
        # We are not filtered and not in private mode
        # Update snapshot and favicon to be sure
        if not webview.is_loading() and\
                not webview.ephemeral:
            GLib.timeout_add(2000, self.set_snapshot, uri)
        else:
            self.__window.container.sites_manager.add_webview_for_uri(
                                                          self.__view.webview,
                                                          uri)

    def __on_title_changed(self, webview, title):
        """
            Update title
            @param webview as WebView
            @param title as str
        """
        self.__title.set_text(title)

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
            GLib.timeout_add(500, self.set_snapshot, uri)
