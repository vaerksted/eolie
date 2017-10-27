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

from gi.repository import Gtk, Gdk, Gio, WebKit2, GLib

from gettext import gettext as _
from urllib.parse import urlparse
from time import time

from eolie.define import El, WindowType
from eolie.utils import get_snapshot
from eolie.search import Search


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
        parsed = urlparse(webview.get_uri())
        if parsed.scheme == "populars":
            context_menu.remove_all()
            if hit.context_is_link():
                action = Gio.SimpleAction(name="reload_preview")
                El().add_action(action)
                action.connect("activate",
                               self.__on_reload_preview_activate,
                               hit.get_link_uri())
                item = WebKit2.ContextMenuItem.new_from_gaction(
                                                         action,
                                                         _("Reload preview"),
                                                         None)
                context_menu.insert(item, 0)
                return
        if hit.context_is_link():
            action = Gio.SimpleAction(name="open_new_page")
            El().add_action(action)
            action.connect("activate",
                           self.__on_open_new_page_activate,
                           hit.get_link_uri(), False)
            item = WebKit2.ContextMenuItem.new_from_gaction(
                                             action,
                                             _("Open link in a new page"),
                                             None)
            context_menu.insert(item, 1)
            action = Gio.SimpleAction(name="open_new_private_page")
            El().add_action(action)
            action.connect("activate",
                           self.__on_open_new_page_activate,
                           hit.get_link_uri(), True)
            item = WebKit2.ContextMenuItem.new_from_gaction(
                                         action,
                                         _("Open link in a new private page"),
                                         None)
            context_menu.insert(item, 2)
        user_data = context_menu.get_user_data()
        if user_data is not None and user_data.get_string():
            selection = user_data.get_string()
            if hit.context_is_selection():
                action = Gio.SimpleAction(name="search_words")
                El().add_action(action)
                action.connect("activate",
                               self.__on_search_words_activate,
                               selection)
                item = WebKit2.ContextMenuItem.new_from_gaction(
                                                 action,
                                                 _("Search on the Web"),
                                                 None)
                context_menu.insert(item, 1)
            if hit.context_is_link():
                action = Gio.SimpleAction(name="copy_text")
                El().add_action(action)
                action.connect("activate",
                               self.__on_copy_text_activate,
                               selection)
                item = WebKit2.ContextMenuItem.new_from_gaction(
                                                 action,
                                                 _("Copy"),
                                                 None)
                context_menu.insert(item, 2)
        else:
            if not webview.is_loading() and parsed.scheme in ["http", "https"]:
                # Save all images
                action = Gio.SimpleAction(name="save_imgs")
                El().add_action(action)
                action.connect("activate",
                               self.__on_save_images_activate)
                item = WebKit2.ContextMenuItem.new_from_gaction(
                                                 action,
                                                 _("Save images"),
                                                 None)
                n_items = context_menu.get_n_items()
                if El().settings.get_value("developer-extras"):
                    context_menu.insert(item, n_items - 2)
                else:
                    context_menu.insert(item, n_items)
                # Save all videos
                action = Gio.SimpleAction(name="save_videos")
                El().add_action(action)
                action.connect("activate",
                               self.__on_save_videos_activate)
                item = WebKit2.ContextMenuItem.new_from_gaction(
                                                 action,
                                                 _("Save videos"),
                                                 None)
                n_items = context_menu.get_n_items()
                if El().settings.get_value("developer-extras"):
                    context_menu.insert(item, n_items - 2)
                else:
                    context_menu.insert(item, n_items)
                # Save page as image
                action = Gio.SimpleAction(name="save_as_image")
                El().add_action(action)
                action.connect("activate",
                               self.__on_save_as_image_activate)
                item = WebKit2.ContextMenuItem.new_from_gaction(
                                                 action,
                                                 _("Save page as image"),
                                                 None)
                n_items = context_menu.get_n_items()
                if El().settings.get_value("developer-extras"):
                    context_menu.insert(item, n_items - 2)
                else:
                    context_menu.insert(item, n_items)

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
        self._window.container.add_webview(uri,
                                           WindowType.FOREGROUND,
                                           self.ephemeral or ephemeral)

    def __on_search_words_activate(self, action, variant, selection):
        """
            Open link in a new page
            @param action as Gio.SimpleAction
            @param variant as GLib.Variant
            @param selection as str
        """
        search = Search()
        uri = search.get_search_uri(selection)
        self._window.container.add_webview(uri, WindowType.FOREGROUND)

    def __on_copy_text_activate(self, action, variant, selection):
        """
            Open link in a new page
            @param action as Gio.SimpleAction
            @param variant as GLib.Variant
            @param selection as str
        """
        Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(selection, -1)

    def __on_save_images_activate(self, action, variant):
        """
            Show images filtering popover
            @param action as Gio.SimpleAction
            @param variant as GLib.Variant
        """
        self._window.toolbar.end.save_images(self.get_uri(),
                                             self.get_page_id())

    def __on_save_videos_activate(self, action, variant):
        """
            Show videos download popover
            @param action as Gio.SimpleAction
            @param variant as GLib.Variant
        """
        self._window.toolbar.end.save_videos(self.get_page_id())

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
            print("WebViewMenuSignals::__on_reload_preview_activate():", e)

    def __on_load_changed(self, webview, event, uri):
        """
            Get a snapshot
            @param webview as WebView
            @param event as WebKit2.LoadEvent
            @param uri as str
        """
        if event == WebKit2.LoadEvent.FINISHED:
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
                El().art.save_artwork(uri, surface, "start")
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
            Gtk.show_uri_on_window(self._window,
                                   "file:///tmp/eolie_snapshot.png",
                                   Gtk.get_current_event_time())
        except Exception as e:
            print("WebView::__on_snapshot():", e)
            # The 32767 limit on the width/height dimensions
            # of an image surface is new in cairo 1.10,
            # try with WebKit2.SnapshotRegion.VISIBLE
            if first_pass:
                self.get_snapshot(WebKit2.SnapshotRegion.VISIBLE,
                                  WebKit2.SnapshotOptions.NONE,
                                  None,
                                  self.__on_snapshot,
                                  False)
