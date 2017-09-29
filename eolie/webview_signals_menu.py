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

from gi.repository import Gtk, Gdk, WebKit2

from gettext import gettext as _
from urllib.parse import urlparse

from eolie.define import El
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

#######################
# PRIVATE             #
#######################
    def __on_context_menu(self, view, context_menu, event, hit):
        """
            Add custom items to menu
            @param view as WebView
            @param context_menu as WebKit2.ContextMenu
            @param event as Gdk.Event
            @param hit as WebKit2.HitTestResult
        """
        parsed = urlparse(view.get_uri())
        if hit.context_is_link():
            # Add an item for open in a new page
            # FIXME https://bugs.webkit.org/show_bug.cgi?id=159631
            # Introspection missing, Gtk.Action deprecated
            action = Gtk.Action.new("open_new_page",
                                    _("Open link in a new page"),
                                    None,
                                    None)
            action.connect("activate",
                           self.__on_open_new_page_activate,
                           hit.get_link_uri())
            item = WebKit2.ContextMenuItem.new(action)
            context_menu.insert(item, 1)

        user_data = context_menu.get_user_data()
        if user_data is not None and user_data.get_string():
            selection = user_data.get_string()
            if hit.context_is_selection():
                # Add an item for open words in search
                # FIXME https://bugs.webkit.org/show_bug.cgi?id=159631
                # Introspection missing, Gtk.Action deprecated
                action = Gtk.Action.new("search_words",
                                        _("Search on the Web"),
                                        None,
                                        None)
                action.connect("activate",
                               self.__on_search_words_activate,
                               selection)
                item = WebKit2.ContextMenuItem.new(action)
                context_menu.insert(item, 1)
            if hit.context_is_link():
                # Add an item for open words in search
                # FIXME https://bugs.webkit.org/show_bug.cgi?id=159631
                # Introspection missing, Gtk.Action deprecated
                action = Gtk.Action.new("copy_text",
                                        _("Copy"),
                                        None,
                                        None)
                action.connect("activate",
                               self.__on_copy_text_activate,
                               selection)
                item = WebKit2.ContextMenuItem.new(action)
                context_menu.insert(item, 2)
        else:
            # Add an item for open all images
            if view.is_loading() or parsed.scheme not in ["http", "https"]:
                return
            # FIXME https://bugs.webkit.org/show_bug.cgi?id=159631
            # Introspection missing, Gtk.Action deprecated
            action = Gtk.Action.new("save_imgs",
                                    _("Save images"),
                                    None,
                                    None)
            action.connect("activate", self.__on_save_images_activate,)
            item = WebKit2.ContextMenuItem.new(action)
            n_items = context_menu.get_n_items()
            if El().settings.get_value("developer-extras"):
                context_menu.insert(item, n_items - 2)
            else:
                context_menu.insert(item, n_items)
            # Add an item for page capture
            # FIXME https://bugs.webkit.org/show_bug.cgi?id=159631
            # Introspection missing, Gtk.Action deprecated
            action = Gtk.Action.new("save_as_image",
                                    _("Save page as image"),
                                    None,
                                    None)
            action.connect("activate", self.__on_save_as_image_activate,)
            item = WebKit2.ContextMenuItem.new(action)
            n_items = context_menu.get_n_items()
            if El().settings.get_value("developer-extras"):
                context_menu.insert(item, n_items - 2)
            else:
                context_menu.insert(item, n_items)

    def __on_open_new_page_activate(self, action, uri):
        """
            Open link in a new page
            @param action as Gtk.Action
            @param uri as str
        """
        self._window.container.add_webview(uri,
                                           Gdk.WindowType.CHILD,
                                           self.ephemeral)

    def __on_search_words_activate(self, action, selection):
        """
            Open link in a new page
            @param action as Gtk.Action
            @param selection as str
        """
        search = Search()
        uri = search.get_search_uri(selection)
        self._window.container.add_webview(uri, Gdk.WindowType.CHILD)

    def __on_copy_text_activate(self, action, selection):
        """
            Open link in a new page
            @param action as Gtk.Action
            @param selection as str
        """
        Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(selection, -1)

    def __on_save_images_activate(self, action):
        """
            Show images filtering popover
            @param action as Gtk.Action
        """
        self._window.toolbar.end.save_images(self.get_uri(),
                                             self.get_page_id())

    def __on_save_as_image_activate(self, action):
        """
            Save image in /tmp and show it to user
            @param action as Gtk.Action
        """
        self.get_snapshot(WebKit2.SnapshotRegion.FULL_DOCUMENT,
                          WebKit2.SnapshotOptions.NONE,
                          None,
                          self.__on_snapshot)

    def __on_snapshot(self, webview, result):
        """
            Set snapshot on main image
            @param webview as WebView
            @param result as Gio.AsyncResult
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
