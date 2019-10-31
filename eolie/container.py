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

from gi.repository import Gtk, GLib, Gdk

from gettext import gettext as _
from random import randint

from eolie.view import View
from eolie.popover_webview import WebViewPopover
from eolie.define import App, LoadingType
from eolie.webview_state import WebViewState, WebViewStateStruct
from eolie.container_sidebar import SidebarContainer
from eolie.container_expose import ExposeContainer


class Container(Gtk.Overlay, SidebarContainer, ExposeContainer):
    """
        Main Eolie view
    """

    __DONATION = 1

    def __init__(self, window):
        """
            Ini.container
            @param window as Window
        """
        Gtk.Overlay.__init__(self)
        self._window = window
        SidebarContainer.__init__(self)
        ExposeContainer.__init__(self)
        self.__popover = WebViewPopover(window)
        self.add(self._paned)
        # Show donation notification after one hour
        if App().settings.get_value("donation").get_int32() != self.__DONATION:
            GLib.timeout_add_seconds(randint(3600, 7200),
                                     self.__show_donation)

    def add_webview_for_uri(self, uri, loading_type):
        """
            Add a webview to container with uri
            @param uri as str
            @param loading_type as Gdk.LoadingType
        """
        state = WebViewStateStruct()
        state.uri = uri
        webview = WebViewState.new_from_state(state)
        webview.show()
        self.add_webview(webview, loading_type)

    def add_webview(self, webview, loading_type):
        """
            Add a webview to container
            @param webview as WebView
            @param loading_type as Gdk.LoadingType
        """
        if loading_type == LoadingType.BACKGROUND or self.in_expose:
            webview.load_uri(webview.uri)
        view = View(webview)
        view.show()
        self.pages_manager.add_view(view)
        self.sites_manager.add_view(view)
        self._stack.add(view)
        # Check for expose because we will be unable to get snapshot as
        # window is not visible
        if loading_type == LoadingType.FOREGROUND and not self.in_expose:
            self._current = view
            self.pages_manager.update_visible_child()
            self.sites_manager.update_visible_child()
            self._stack.set_visible_child(view)
        # Do not count container views as destroy may be pending on somes
        # Reason: we do not remove/destroy view to let stack animation run
        count = len(self.pages_manager.children)
        self._window.toolbar.actions.count_label.set_text(str(count))
        App().update_unity_badge()

    def add_view(self, view):
        """
            Add view to container
            @param view as View
        """
        self._current = view
        self._stack.add(view)
        self.pages_manager.add_view(view)
        self.sites_manager.add_view(view)
        self._stack.set_visible_child(view)
        count = len(self._stack.get_children())
        self._window.toolbar.actions.count_label.set_text(str(count))
        App().update_unity_badge()
        self.pages_manager.update_visible_child()
        self.sites_manager.update_visible_child()

    def remove_view(self, view):
        """
            Remove view from container
            @param view as View
        """
        self._stack.remove(view)
        self.pages_manager.remove_view(view)
        self.sites_manager.remove_view(view)
        children = self._stack.get_children()
        if children:
            self._current = self._stack.get_visible_child()
            count = len(children)
            self._window.toolbar.actions.count_label.set_text(str(count))
            App().update_unity_badge()
            self.pages_manager.update_visible_child()
            self.sites_manager.update_visible_child()
        else:
            for window in App().windows:
                window.mark(False)
            self._window.close()

    def load_uri(self, uri):
        """
            Load uri in current view
            @param uri as str
        """
        if self.current is not None:
            self.current.webview.load_uri(uri)

    def popup_webview(self, webview, destroy):
        """
            Show webview in popopver
            @param webview as WebView
            @param destroy webview when popover hidden
        """
        view = View(webview, self._window, True)
        view.show()
        self.__popover.add_view(view, destroy)
        if not self.__popover.is_visible():
            self.__popover.set_relative_to(self._window.toolbar)
            self.__popover.set_position(Gtk.PositionType.BOTTOM)
            self.__popover.popup()

    def try_close_view(self, view):
        """
            Ask user before closing view if forms filled
            @param view as View
        """
        page_id = view.webview.get_page_id()
        App().helper.call("FormsFilled", page_id, None,
                          self.__on_forms_filled, view)

    def close_view(self, view):
        """
            close current view
            @param view as View
            @param animate as bool
        """
        # Get children less view
        views = self.__get_children()
        if view.destroyed or view not in views:
            return
        views.remove(view)
        views_count = len(views)
        App().history.set_page_state(view.webview.uri)
        self._window.close_popovers()
        # Needed to unfocus titlebar
        self._window.set_focus(None)
        was_current = view == self._window.container.current
        if not view.webview.is_ephemeral:
            App().pages_menu.add_action(view.webview.title,
                                        view.webview.uri,
                                        view.webview.get_session_state())

        view.destroy()
        # Don't show 0 as we are going to open a new one
        if views_count:
            App().update_unity_badge()
            self._window.toolbar.actions.count_label.set_text(
                str(views_count))
        # Nothing to do if was not current page
        if not was_current:
            return False

        next_view = None

        # First we search for a child for current view
        if view.webview.children:
            next_view = view.webview.children[0].view

        # Current webview children not needed, clear parent
        for child in view.webview.children:
            child.set_parent(None)

        # Next we search for a brother for current view
        # If no brother, use parent
        parent = view.webview.parent
        if next_view is None and parent is not None:
            for parent_child in parent.children:
                if view.webview != parent_child:
                    next_view = parent_child.view
                    break
            if next_view is None and parent.view in views:
                next_view = parent.view

        # Next we search for view with higher atime
        if next_view is None:
            atime = 0
            for view in reversed(views):
                if view.webview.atime >= atime:
                    next_view = view
                    atime = view.webview.atime
        if next_view is not None:
            self._window.container.set_current(next_view, True)
        else:
            # We are last row, add a new one
            self.add_webview_for_uri(App().start_page, LoadingType.FOREGROUND)

#######################
# PRIVATE             #
#######################
    def __show_donation(self):
        """
            Show a notification telling user to donate a little
        """
        from eolie.app_notification import AppNotification
        notification = AppNotification(
            _("Please consider a donation to the project"),
            [_("PayPal"), _("Patreon")],
            [lambda: Gtk.show_uri_on_window(
                App().active_window,
                "https://www.paypal.me/lollypopgnome",
                Gdk.CURRENT_TIME),
             lambda: Gtk.show_uri_on_window(
                App().active_window,
                "https://www.patreon.com/gnumdk",
                Gdk.CURRENT_TIME)])
        self.add_overlay(notification)
        notification.show()
        notification.set_reveal_child(True)
        App().settings.set_value("donation",
                                 GLib.Variant("i", self.__DONATION))

    def __on_forms_filled(self, source, result, view):
        """
            Ask user to close view, if ok, close view
            @param source as GObject.Object
            @param result as Gio.AsyncResult
            @param view as View
        """
        def on_response_id(dialog, response_id, view, self):
            if response_id == Gtk.ResponseType.CLOSE:
                self.close_view(view)
            dialog.destroy()

        def on_close(widget, dialog):
            dialog.response(Gtk.ResponseType.CLOSE)

        def on_cancel(widget, dialog):
            dialog.response(Gtk.ResponseType.CANCEL)

        try:
            try:
                result = source.call_finish(result)
            except:
                result = None
            if result is not None and result[0]:
                builder = Gtk.Builder()
                builder.add_from_resource("/org/gnome/Eolie/QuitDialog.ui")
                dialog = builder.get_object("dialog")
                label = builder.get_object("label")
                close = builder.get_object("close")
                cancel = builder.get_object("cancel")
                label.set_text(_("Do you really want to close this page?"))
                dialog.set_transient_for(self._window)
                dialog.connect("response", on_response_id, view, self)
                close.connect("clicked", on_close, dialog)
                cancel.connect("clicked", on_cancel, dialog)
                dialog.run()
            else:
                self.close_view(view)
        except:
            self.close_view(view)
