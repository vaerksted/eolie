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

from gi.repository import Gtk, Gdk, Gio, WebKit2, GLib

from gettext import gettext as _
from urllib.parse import urlparse
from time import time

from eolie.define import App, LoadingType, EolieLoadEvent
from eolie.utils import get_snapshot
from eolie.search import Search
from eolie.logger import Logger


class WebViewMenuSignals:
    """
        Handle webview menu signals
    """

    def __init__(self):
        """
            Init class
        """
        self.connect("context-menu", self.__on_context_menu)
        self.connect("context-menu-dismissed",
                     self.__on_context_menu_dismissed)

#######################
# PRIVATE             #
#######################
    def __on_context_menu(self, webview, context_menu, event, hit):
        """
            Add custom items to menu
            @param webview as WebView
            @param context_menu as WebKit2.ContextMenu
            @param event as Gdk.Event
            @param hit as WebKit2.HitTestResult
        """
        parsed = urlparse(webview.uri)
        if parsed.scheme == "populars":
            context_menu.remove_all()
            if hit.context_is_link():
                action = Gio.SimpleAction(name="reload_preview")
                App().add_action(action)
                action.connect("activate",
                               self.__on_reload_preview_activate,
                               hit.get_link_uri())
                item = WebKit2.ContextMenuItem.new_from_gaction(
                    action,
                    _("Reload preview"),
                    None)
                context_menu.append(item)
                return
        position = 0
        for item in context_menu.get_items():
            action = item.get_stock_action()
            if action in [WebKit2.ContextMenuAction.OPEN_LINK,
                          WebKit2.ContextMenuAction.OPEN_VIDEO_IN_NEW_WINDOW,
                          WebKit2.ContextMenuAction.OPEN_AUDIO_IN_NEW_WINDOW,
                          WebKit2.ContextMenuAction.OPEN_FRAME_IN_NEW_WINDOW]:
                context_menu.remove(item)
            elif action == WebKit2.ContextMenuAction.OPEN_LINK_IN_NEW_WINDOW:
                context_menu.remove(item)
                action = Gio.SimpleAction(name="open_new_page")
                App().add_action(action)
                action.connect("activate",
                               self.__on_open_new_page_activate,
                               hit.get_link_uri(), False)
                item = WebKit2.ContextMenuItem.new_from_gaction(
                    action,
                    _("Open link in a new page"),
                    None)
                context_menu.insert(item, position)
                action = Gio.SimpleAction(name="open_new_private_page")
                App().add_action(action)
                action.connect("activate",
                               self.__on_open_new_page_activate,
                               hit.get_link_uri(), True)
                item = WebKit2.ContextMenuItem.new_from_gaction(
                    action,
                    _("Open link in a new private page"),
                    None)
                context_menu.insert(item, position + 1)
                action = Gio.SimpleAction(name="open_new_window")
                App().add_action(action)
                action.connect("activate",
                               self.__on_open_new_window_activate,
                               hit.get_link_uri())
                item = WebKit2.ContextMenuItem.new_from_gaction(
                    action,
                    _("Open link in a new window"),
                    None)
                context_menu.append(item)
                item = WebKit2.ContextMenuItem.new_separator()
                context_menu.insert(item, position + 2)

        # Get current selection
        selection = ""
        user_data = context_menu.get_user_data()
        if user_data is not None and user_data.get_string():
            selection = user_data.get_string()
        if selection and hit.context_is_selection():
            action = Gio.SimpleAction(name="search_words")
            App().add_action(action)
            action.connect("activate",
                           self.__on_search_words_activate,
                           selection)
            item = WebKit2.ContextMenuItem.new_from_gaction(
                action,
                _("Search on the Web"),
                None)
            context_menu.append(item)
        if not hit.context_is_link() and parsed.scheme in ["http", "https"]:
            item = WebKit2.ContextMenuItem.new_separator()
            context_menu.append(item)
            # Save page as image
            action = Gio.SimpleAction(name="save_as_image")
            App().add_action(action)
            action.connect("activate",
                           self.__on_save_as_image_activate)
            item = WebKit2.ContextMenuItem.new_from_gaction(
                action,
                _("Save page as image"),
                None)
            context_menu.append(item)

    def __on_context_menu_dismissed(self, webview):
        """
            Add custom items to menu
            @param webview as WebView
        """
        self._last_click_time = time()

    def __on_open_new_page_activate(self, action, variant, uri, ephemeral):
        """
            Open link in a new page
            @param action as Gio.SimpleAction
            @param variant as GLib.Variant
            @param uri as str
            @param ephemeral as bool
        """
        self.window.container.add_webview_for_uri(
                                          uri,
                                          LoadingType.FOREGROUND,
                                          self.is_ephemeral or ephemeral)

    def __on_open_new_window_activate(self, action, variant, uri):
        """
            Open link in a new page
            @param action as Gio.SimpleAction
            @param variant as GLib.Variant
            @param uri as str
            @param ephemeral as bool
        """
        window = App().get_new_window()
        window.container.add_webview(uri,
                                     LoadingType.FOREGROUND,
                                     self.ephemeral)

    def __on_search_words_activate(self, action, variant, selection):
        """
            Open link in a new page
            @param action as Gio.SimpleAction
            @param variant as GLib.Variant
            @param selection as str
        """
        search = Search()
        uri = search.get_search_uri(selection)
        self.window.container.add_webview(uri, LoadingType.FOREGROUND)

    def __on_save_as_image_activate(self, action, variant):
        """
            Save image in /tmp and show it to user
            @param action as Gio.SimpleAction
            @param variant as GLib.Variant
        """
        self.get_snapshot(WebKit2.SnapshotRegion.FULL_DOCUMENT,
                          WebKit2.SnapshotOptions.NONE,
                          None,
                          self.__on_snapshot,
                          True)

    def __on_reload_preview_activate(self, action, variant, uri):
        """
            Reload preview for uri
            @param action as Gio.SimpleAction
            @param variant as GLib.Variant
            @param uri as str
        """
        try:
            webview = WebKit2.WebView.new()
            webview.show()
            window = Gtk.OffscreenWindow.new()
            window.set_size_request(self.get_allocated_width(),
                                    self.get_allocated_height())
            window.add(webview)
            window.show()
            webview.load_uri(uri)
            webview.connect("load-changed", self.__on_load_changed, uri)
        except Exception as e:
            Logger.error("""WebViewMenuSignals::
                            __on_reload_preview_activate(): %s""", e)

    def __on_load_changed(self, webview, event, uri):
        """
            Get a snapshot
            @param webview as WebView
            @param event as EolieLoadEvent
            @param uri as str
        """
        if event == EolieLoadEvent.FINISHED:
            GLib.timeout_add(3000,
                             webview.get_snapshot,
                             WebKit2.SnapshotRegion.FULL_DOCUMENT,
                             WebKit2.SnapshotOptions.NONE,
                             None,
                             get_snapshot,
                             self.__on_preview_snapshot,
                             webview,
                             uri, True)

    def __on_preview_snapshot(self, surface, webview, uri, first_pass):
        """
            Cache snapshot
            @param surface as cairo.Surface
            @param webview as WebKit2.WebView
            @param uri as str
            @param first_pass as bool
        """
        # The 32767 limit on the width/height dimensions
        # of an image surface is new in cairo 1.10,
        # try with WebKit2.SnapshotRegion.VISIBLE
        if surface is None and first_pass:
            webview.get_snapshot(WebKit2.SnapshotRegion.VISIBLE,
                                 WebKit2.SnapshotOptions.NONE,
                                 None,
                                 get_snapshot,
                                 self.__on_preview_snapshot,
                                 webview,
                                 uri, False)
        else:
            if surface is not None:
                App().art.save_artwork(uri, surface, "start")
                self.reload()
            window = webview.get_toplevel()
            webview.destroy()
            window.destroy()

    def __on_snapshot(self, webview, result, first_pass):
        """
            Set snapshot on main image
            @param webview as WebView
            @param result as Gio.AsyncResult
            @param first_pass as bool
        """
        try:
            snapshot = webview.get_snapshot_finish(result)
            pixbuf = Gdk.pixbuf_get_from_surface(snapshot, 0, 0,
                                                 snapshot.get_width(),
                                                 snapshot.get_height())
            pixbuf.savev("/tmp/eolie_snapshot.png", "png", [None], [None])
            Gtk.show_uri_on_window(self.window,
                                   "file:///tmp/eolie_snapshot.png",
                                   Gtk.get_current_event_time())
        except Exception as e:
            Logger.error("WebView::__on_snapshot(): %s", e)
            # The 32767 limit on the width/height dimensions
            # of an image surface is new in cairo 1.10,
            # try with WebKit2.SnapshotRegion.VISIBLE
            if first_pass:
                self.get_snapshot(WebKit2.SnapshotRegion.VISIBLE,
                                  WebKit2.SnapshotOptions.NONE,
                                  None,
                                  self.__on_snapshot,
                                  False)
