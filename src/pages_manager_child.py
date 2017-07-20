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

from eolie.define import El, ArtSize, PanelMode
from eolie.utils import resize_favicon


class PagesManagerChild:
    """
        Generic parent for Stack children
        Need to be inherited by a Gtk.*BoxRow
    """

    def __init__(self, view, window):
        """
            Init child
        """
        self._view = view
        self._window = window
        self.__connected_ids = []
        self.__scroll_timeout_id = None
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/StackChild.ui")
        builder.connect_signals(self)
        self._widget = builder.get_object("widget")
        self._overlay = builder.get_object("overlay")
        self._grid = builder.get_object("grid")
        self._title = builder.get_object("title")
        self._image = builder.get_object("image")
        self._image_close = builder.get_object("image_close")
        self.__audio_indicator = builder.get_object("audio_indicator")
        if view.webview.is_playing_audio():
            self.__audio_indicator.show()
        if view.webview.ephemeral:
            self._image_close.set_from_icon_name("window-close-symbolic",
                                                 Gtk.IconSize.INVALID)
        else:
            self._image_close.set_from_icon_name("applications-internet",
                                                 Gtk.IconSize.INVALID)
        self._image_close.set_property("pixel-size", ArtSize.FAVICON)
        self.__spinner = builder.get_object("spinner")
        self._title.set_label("Empty page")
        self.add(self._widget)

        self.get_style_context().add_class("sidebar-item")

        self.set_property("has-tooltip", True)
        self.connect("query-tooltip", self.__on_query_tooltip)
        self.connect("destroy", self.__on_destroy)
        self.__view_destroy_id = view.connect("destroy",
                                              self.__on_view_destroy)
        self.__connected_ids.append(
                             self._view.webview.connect(
                                 "notify::favicon",
                                 self._on_notify_favicon))
        self.__connected_ids.append(
                             self._view.webview.connect(
                                 "notify::is-playing-audio",
                                 self._on_notify_is_playing_audio))
        self.__connected_ids.append(
                             self._view.webview.connect(
                                 "uri-changed",
                                 self._on_uri_changed))
        self.__connected_ids.append(
                             self._view.webview.connect(
                                 "title-changed",
                                 self._on_title_changed))
        self.__connected_ids.append(
                             self._view.webview.connect(
                                 "scroll-event",
                                 self._on_scroll_event))
        self.__connected_ids.append(
                             self._view.webview.connect(
                                 "load-changed",
                                 self._on_load_changed))

    def update(self):
        """
            Update child title and favicon
        """
        title = self._view.webview.get_title()
        if title is None:
            title = self._view.webview.get_uri()
        self._title.set_text(title)
        self.__set_favicon()

    def set_snapshot(self, uri, save):
        """
            Set webpage preview
            @param uri as str
            @param save as bool
        """
        pass

    def clear_snapshot(self):
        """
            Get snapshot
            @return Gtk.Image
        """
        if self._image is not None:
            self._image.clear()

    def show_title(self, b):
        pass

    @property
    def view(self):
        """
            Get linked view
            @return View
        """
        return self._view

#######################
# PROTECTED           #
#######################
    def _on_notify_favicon(self, webview, favicon):
        """
            Set favicon
            @param webview as WebView
            @param favicon as Gparam
        """
        if self._view.webview == webview:
            # FIXME use favicon
            self.__set_favicon()

    def _on_notify_is_playing_audio(self, webview, playing):
        """
            Update status
            @param webview as WebView
            @param playing as bool
        """
        if not webview.is_loading() and webview.is_playing_audio():
            self.__audio_indicator.show()
        else:
            self.__audio_indicator.hide()

    def _on_scroll_event(self, webview, event):
        """
            Update snapshot
            @param webview as WebView
            @param event as Gdk.EventScroll
        """
        if self.__scroll_timeout_id is not None:
            GLib.source_remove(self.__scroll_timeout_id)
        self.__scroll_timeout_id = GLib.timeout_add(250,
                                                    self.__on_scroll_timeout)

    def _on_snapshot(self, webview, result, uri, save):
        """
            Set snapshot on main image
            @param webview as WebView
            @param result as Gio.AsyncResult
            @param uri as str
            @param save as bool
            @warning view here is WebKit2.WebView, not WebView
        """
        pass

    def _on_button_press_event(self, eventbox, event):
        """
            Hide popover or close view
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        if event.button == 2:
            self._window.container.pages_manager.close_view(self._view)
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
        if El().settings.get_enum("panel-mode") != PanelMode.MINIMAL:
            self._window.container.pages_manager.close_view(self._view)
            return True

    def _on_enter_notify_event(self, eventbox, event):
        """
            Show close button
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        if El().settings.get_enum("panel-mode") == PanelMode.MINIMAL:
            return
        self._image_close.set_from_icon_name("window-close-symbolic",
                                             Gtk.IconSize.INVALID)
        self._image_close.get_style_context().add_class("sidebar-item-close")

    def _on_leave_notify_event(self, eventbox, event):
        """
            Show close button
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        if El().settings.get_enum("panel-mode") == PanelMode.MINIMAL:
            return
        allocation = eventbox.get_allocation()
        if event.x <= 0 or\
           event.x >= allocation.width or\
           event.y <= 0 or\
           event.y >= allocation.height:
            self._image_close.get_style_context().remove_class(
                                                          "sidebar-item-close")
            self.__set_favicon()

    def _on_uri_changed(self, webview, uri):
        """
            Update uri
            @param webview as WebView
            @param uri as str
        """
        if self._view.webview != webview:
            return
        # We are not filtered and not in private mode
        if not webview.is_loading() and\
                not webview.ephemeral and\
                El().settings.get_enum("panel-mode") not in [
                                                         PanelMode.MINIMAL,
                                                         PanelMode.NO_PREVIEW]:
            GLib.timeout_add(2000, self.set_snapshot,
                             webview.get_uri(), False)

    def _on_title_changed(self, webview, title):
        """
            Update title
            @param webview as WebView
            @param title as str
        """
        if self._view.webview != webview:
            return
        self._title.set_text(title)

    def _on_load_changed(self, webview, event):
        """
            Update widget content
            @param webview as WebView
            @param event as WebKit2.LoadEvent
        """
        if self._view.webview != webview:
            return
        uri = webview.get_uri()
        if event == WebKit2.LoadEvent.STARTED:
            self._image.clear()
            self.__audio_indicator.hide()
            self.__spinner.start()
            self._title.set_text(uri)
        elif event == WebKit2.LoadEvent.COMMITTED:
            self._title.set_text(uri)
        elif event == WebKit2.LoadEvent.FINISHED:
            self.__spinner.stop()
            if webview.is_playing_audio():
                self.__audio_indicator.show()
            # is_loading() happen when loading a new uri while
            # previous loading is not finished
            if not webview.cancelled and not webview.is_loading():
                GLib.timeout_add(500, self.set_snapshot, uri, False)
                # FIXME Should be better to have way to snapshot when
                # page is rendered
                GLib.timeout_add(3000, self.set_snapshot, uri, True)
                self.__set_favicon()

#######################
# PRIVATE             #
#######################
    def __set_favicon(self):
        """
            Set favicon
        """
        uri = self._view.webview.get_uri()
        if self._view.webview.ephemeral:
            self._image_close.set_from_icon_name("user-not-tracked-symbolic",
                                                 Gtk.IconSize.INVALID)
        elif uri == "populars://":
            self._image_close.set_from_icon_name("emote-love-symbolic",
                                                 Gtk.IconSize.INVALID)
        elif uri:
            context = self._view.webview.get_context()
            favicon_db = context.get_favicon_database()
            favicon_db.get_favicon(uri, None, self.__set_favicon_result, uri)
        else:
            self._image_close.set_from_icon_name("applications-internet",
                                                 Gtk.IconSize.INVALID)

    def __set_favicon_related(self, surface, uri, related_uri):
        """
            Set favicon for related uri
            @param surface as cairo.surface
            @param uri as str
            @param related_uri as str
        """
        if related_uri is not None and\
                related_uri != uri and\
                not El().art.exists(related_uri, "favicon"):
            El().art.save_artwork(related_uri, surface, "favicon")

    def __set_favicon_result(self, db, result, uri):
        """
            Set favicon db result
            @param db as WebKit2.FaviconDatabase
            @param result as Gio.AsyncResult
            @param uri as str
        """
        try:
            surface = db.get_favicon_finish(result)
            save = True
        except:
            surface = self._view.webview.get_favicon()
            # Getting favicon is not accurate
            # We don't know if it really is for current uri
            # So don't save
            save = False

        if surface is None:
            self._image_close.set_from_icon_name("applications-internet",
                                                 Gtk.IconSize.INVALID)
        else:
            resized = resize_favicon(surface)
            if save:
                El().art.save_artwork(uri, resized, "favicon")
                self.__set_favicon_related(resized,
                                           uri,
                                           self._view.webview.related_uri)
            self._image_close.set_from_surface(resized)
            del resized
            del surface

    def __on_scroll_timeout(self):
        """
            Update snapshot
        """
        uri = self._view.webview.get_uri()
        self.__scroll_timeout_id = None
        self.set_snapshot(uri, False)

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
        label = self._title.get_text()
        uri = self._view.webview.get_uri()
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
            self._view.webview.disconnect(connected_id)
        if self.__view_destroy_id is not None:
            self._view.disconnect(self.__view_destroy_id)

    def __on_view_destroy(self, view):
        """
            Destroy self
            @param view as View
        """
        self.__connected_ids = []
        self.__view_destroy_id = None
        GLib.idle_add(self.destroy)
