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

from gi.repository import Gtk

from gettext import gettext as _

from eolie.define import App, LoadingType
from eolie.widget_stack import Stack
from eolie.webview_state import WebViewState, WebViewStateStruct


class StackContainer:
    """
        Stack management for container
    """

    def __init__(self):
        """
            Init container
        """
        self._stack = Stack()
        self._stack.set_hexpand(True)
        self._stack.set_vexpand(True)
        self._stack.show()

    def add_webview_for_uri(self, uri, loading_type):
        """
            Add a webview to container with uri
            @param uri as str
            @param loading_type as Gdk.LoadingType
        """
        state = WebViewStateStruct()
        state.uri = uri
        webview = WebViewState.new_from_state(state, self._window)
        webview.show()
        self.add_webview(webview, loading_type)

    def add_webview(self, webview, loading_type):
        """
            Add a webview to container
            @param webview as WebView
            @param loading_type as Gdk.LoadingType
        """
        webview.connect("destroy", self.__on_destroy)
        self.pages_manager.add_webview(webview)
        self.sites_manager.add_webview(webview)
        self._stack.add(webview)
        # Check for expose because we will be unable to get snapshot as
        # window is not visible
        if loading_type == LoadingType.FOREGROUND and not self.in_expose:
            self.set_visible_webview(webview)
        # Do not count container.webviews as destroy may be pending on somes
        # Reason: we do not remove/destroy view to let stack animation run
        count = len(self.pages_manager.children)
        self._window.toolbar.actions.count_label.set_text(str(count))
        App().update_unity_badge()
        if loading_type == LoadingType.BACKGROUND or self.in_expose:
            webview.load_uri(webview.uri)

    def remove_webview(self, webview):
        """
            Remove view from container
            @param webview as WebView
        """
        self._stack.remove(webview)
        self.pages_manager.remove_webview(webview)
        self.sites_manager.remove_webview(webview)
        children = self._stack.get_children()
        if children:
            count = len(children)
            self._window.toolbar.actions.count_label.set_text(str(count))
            App().update_unity_badge()
            self.pages_manager.update_visible_child()
            self.sites_manager.update_visible_child()
        else:
            for window in App().windows:
                window.mark(False)
            self._window.close()

    def try_close_webview(self, webview):
        """
            Ask user before closing view if forms filled
            @param webview as WebView
        """
        page_id = webview.get_page_id()
        App().helper.call("FormsFilled", page_id, None,
                          self.__on_forms_filled, webview)

    def close_view(self, webview):
        """
            close current webview
            @param view as View
            @param animate as bool
        """
        # Get children less view
        webviews = [child for child in self._stack.get_children()]
        if webview not in webviews:
            return
        webviews.remove(webview)
        webviews_count = len(webviews)
        App().history.set_page_state(webview.uri)
        self._window.close_popovers()
        # Needed to unfocus titlebar
        self._window.set_focus(None)
        was_current = webview == self._window.container.webview
        if not webview.is_ephemeral:
            App().pages_menu.add_action(webview.title,
                                        webview.uri,
                                        webview.get_session_state())

        webview.destroy()
        # Don't show 0 as we are going to open a new one
        if webviews_count:
            App().update_unity_badge()
            self._window.toolbar.actions.count_label.set_text(
                str(webviews_count))
        # Nothing to do if was not current page
        if not was_current:
            return False

        next_webview = None

        # First we search for a child for current view
        if webview.children:
            next_webview = webview.children[0].webview

        # Current webview children not needed, clear parent
        for child in webview.children:
            child.set_parent(None)

        # Next we search for a brother for current view
        # If no brother, use parent
        parent = webview.parent
        if next_webview is None and parent is not None:
            for parent_child in parent.children:
                if webview != parent_child:
                    next_webview = parent_child.webview
                    break
            if next_webview is None and parent.webview in webviews:
                next_webview = parent.webview

        # Next we search for view with higher atime
        if next_webview is None:
            atime = 0
            for webview in reversed(webviews):
                if webview.atime >= atime:
                    next_webview = webview
                    atime = webview.atime
        if next_webview is not None:
            self._window.container.set_webview(next_webview, True)
        else:
            # We are last row, add a new one
            self.add_webview_for_uri(App().start_page, LoadingType.FOREGROUND)

    def set_visible_webview(self, webview):
        """
            Set visible webview
            @param webview as WebView
        """
        self._stack.set_visible_child(webview)
        self.pages_manager.update_visible_child()
        self.sites_manager.update_visible_child()

    @property
    def webview(self):
        """
            Get current webview
            @return webview
        """
        return self._stack.get_visible_child()

#######################
# PRIVATE             #
#######################
    def __on_destroy(self, webview):
        """
            Remove webview from monitored webviews
            @param webview as WebView
        """
        self.dismiss_webview(webview)
        self.pages_manager.remove_webview(webview)
        self.sites_manager.remove_webview(webview)

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
