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
from eolie.pages_manager import PagesManager
from eolie.define import App, LoadingType
from eolie.webview_state import WebViewState, WebViewStateStruct
from eolie.container_sidebar import SidebarContainer


class Container(Gtk.Overlay, SidebarContainer):
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
        self.__popover = WebViewPopover(window)
        self.__current = None
        self.__next_timeout_id = None
        self.__previous_timeout_id = None

        self.__stack = Gtk.Stack()
        self.__stack.set_hexpand(True)
        self.__stack.set_vexpand(True)
        self.__stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.__stack.set_transition_duration(150)
        self.__stack.show()

        self.__expose_stack = Gtk.Stack()
        self.__expose_stack.set_hexpand(True)
        self.__expose_stack.set_vexpand(True)
        self.__expose_stack.set_transition_type(
            Gtk.StackTransitionType.CROSSFADE)
        self.__expose_stack.set_transition_duration(150)
        self.__expose_stack.show()
        self.__pages_manager = PagesManager(self._window)
        self.__pages_manager.show()
        self._paned.add2(self.__expose_stack)
        self.__expose_stack.add_named(self.__stack, "stack")
        self.__expose_stack.add_named(self.__pages_manager, "expose")
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
        self.__pages_manager.add_view(view)
        self.sites_manager.add_view(view)
        self.__stack.add(view)
        # Check for expose because we will be unable to get snapshot as
        # window is not visible
        if loading_type == LoadingType.FOREGROUND and not self.in_expose:
            self.__current = view
            self.__pages_manager.update_visible_child()
            self.sites_manager.update_visible_child()
            self.__stack.set_visible_child(view)
        # Do not count container views as destroy may be pending on somes
        # Reason: we do not remove/destroy view to let stack animation run
        count = len(self.__pages_manager.children)
        self._window.toolbar.actions.count_label.set_text(str(count))
        App().update_unity_badge()

    def add_view(self, view):
        """
            Add view to container
            @param view as View
        """
        self.__current = view
        self.__stack.add(view)
        self.__pages_manager.add_view(view)
        self.sites_manager.add_view(view)
        self.__stack.set_visible_child(view)
        count = len(self.__stack.get_children())
        self._window.toolbar.actions.count_label.set_text(str(count))
        App().update_unity_badge()
        self.__pages_manager.update_visible_child()
        self.sites_manager.update_visible_child()

    def remove_view(self, view):
        """
            Remove view from container
            @param view as View
        """
        self.__stack.remove(view)
        self.__pages_manager.remove_view(view)
        self.sites_manager.remove_view(view)
        children = self.__stack.get_children()
        if children:
            self.__current = self.__stack.get_visible_child()
            count = len(children)
            self._window.toolbar.actions.count_label.set_text(str(count))
            App().update_unity_badge()
            self.__pages_manager.update_visible_child()
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

    def set_current(self, view, switch=False):
        """
            Set visible view
            @param view as View
            @param switch as bool
        """
        self.__current = view
        self.__pages_manager.update_visible_child()
        self.sites_manager.update_visible_child()
        if switch:
            self.__stack.set_visible_child(view)

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

    def set_expose(self, expose):
        """
            Show current views
            @param expose as bool
        """
        if expose:
            self.__pages_manager.update_sort(self.sites_manager.sort)
            self.__pages_manager.set_filtered(True)
        else:
            self._window.toolbar.actions.view_button.set_active(False)
            self._window.container.pages_manager.set_filter("")
            self.__pages_manager.set_filtered(False)
        self.__set_expose(expose)

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

    def next(self):
        """
            Show next view
        """
        if self.__next_timeout_id is None and\
                self.__next_timeout_id != -1:
            self.__next_timeout_id = GLib.timeout_add(
                100,
                self.__on_prev_next_timeout,
                self.__pages_manager.next)
        else:
            self.__pages_manager.next()

    def previous(self):
        """
            Show next view
        """
        if self.__previous_timeout_id is None and\
                self.__previous_timeout_id != -1:
            self.__previous_timeout_id = GLib.timeout_add(
                100,
                self.__on_prev_next_timeout,
                self.__pages_manager.previous)
        else:
            self.__pages_manager.previous()

    def ctrl_released(self):
        """
            Disable any pending expose
        """
        if self.__next_timeout_id is not None:
            if self.__next_timeout_id != -1:
                self.pages_manager.next()
                GLib.source_remove(self.__next_timeout_id)
        if self.__previous_timeout_id is not None:
            if self.__previous_timeout_id != -1:
                self.pages_manager.previous()
                GLib.source_remove(self.__previous_timeout_id)

        self.__next_timeout_id = None
        self.__previous_timeout_id = None
        self.set_expose(False)

    @property
    def in_expose(self):
        """
            True if in expose mode
            @return bool
        """
        return self.__expose_stack.get_visible_child_name() == "expose"

    @property
    def pages_manager(self):
        """
            Get pages manager
            @return PagesManager
        """
        return self.__pages_manager

    @property
    def views(self):
        """
            Get views
            @return views as [View]
        """
        return self.__stack.get_children()

    @property
    def current(self):
        """
            Current view
            @return WebView
        """
        return self.__current

#######################
# PRIVATE             #
#######################
    def __on_prev_next_timeout(self, callback):
        """
            Set expose on and call callback
            @param callback as __next()/__previous()
        """
        self.__next_timeout_id = -1
        self.__previous_timeout_id = -1
        if not self.in_expose:
            self.__set_expose(True)
        callback()

    def __set_expose(self, expose):
        """
            Show current views
            @param expose as bool
            @param search as bool
        """
        # Show expose mode
        if expose:
            self.__expose_stack.set_visible_child_name("expose")
        else:
            if self.__stack.get_visible_child() != self.__current:
                self.__stack.set_visible_child(self.__current)
            self.__expose_stack.set_visible_child_name("stack")
            self.__pages_manager.update_visible_child()

    def __get_children(self):
        """
            Get children
            @return [View]
        """
        return [child for child in self.__stack.get_children()
                if not child.destroyed]

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
