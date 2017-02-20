# Copyright (c) 2014-2016 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from gi.repository import Gtk, WebKit2, GLib

from gettext import gettext as _
from urllib.parse import urlparse

from eolie.stacksidebar import StackSidebar
from eolie.view import View
from eolie.define import El


class Container(Gtk.Paned):
    """
        Main Eolie view
    """

    def __init__(self, window):
        """
            Init container
            @param window as Window
        """
        Gtk.Paned.__init__(self)
        self.__window = window
        self.__load_status = WebKit2.LoadEvent.FINISHED
        self.set_position(
            El().settings.get_value("paned-width").get_int32())
        self.connect("notify::position", self.__on_notify_position)
        self.__stack = Gtk.Stack()
        self.__stack.set_hexpand(True)
        self.__stack.set_vexpand(True)
        self.__stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.__stack.set_transition_duration(150)
        self.__stack.show()
        self.__stack_sidebar = StackSidebar(window)
        self.__stack_sidebar.show()
        self.add1(self.__stack_sidebar)
        self.child_set_property(self.__stack_sidebar, "shrink", False)
        self.add2(self.__stack)

    def add_web_view(self, uri, show, parent=None, webview=None, state=None):
        """
            Add a web view to container
            @param uri as str
            @param show as bool
            @param parent as View
            @param webview as WebView
            @param state as WebKit2.WebViewSessionState
        """
        view = self.__get_new_view(parent, webview)
        if state is not None:
            view.webview.restore_session_state(state)
        view.show()
        self.__stack_sidebar.add_child(view)
        if uri is not None:
            # Do not load uri until we are on screen
            GLib.idle_add(view.webview.load_uri, uri)
        self.__stack.add(view)
        if show:
            self.__stack.set_visible_child(view)
        self.__stack_sidebar.update_visible_child()

    def load_uri(self, uri):
        """
            Load uri in current view
            @param uri as str
        """
        if self.current is not None:
            self.current.webview.load_uri(uri)

    def add_view(self, view):
        """
            Add view to container
        """
        if view not in self.__stack.get_children():
            self.__stack.add(view)

    def remove_view(self, view):
        """
            Remove view from container
        """
        if view in self.__stack.get_children():
            self.__stack.remove(view)

    def set_visible_view(self, view):
        """
            Set visible view
            @param view as WebView
        """
        # Remove from offscreen window if needed
        # Will kill running get_snapshot :-/
        parent = view.get_parent()
        if parent is not None and isinstance(parent, Gtk.OffscreenWindow):
            parent.remove(view)
            view.set_size_request(-1, -1)
            self.__stack.add(view)
        self.__stack.set_visible_child(view)

    def save_position(self):
        """
            Save current position
        """
        El().settings.set_value('paned-width',
                                GLib.Variant('i', self.get_position()))

    @property
    def sidebar(self):
        """
            Get sidebar
            @return StackSidebar
        """
        return self.__stack_sidebar

    @property
    def views(self):
        """
            Get views
            @return views as [WebView]
        """
        return self.__stack.get_children()

    @property
    def current(self):
        """
            Current view
            @return WebView
        """
        return self.__stack.get_visible_child()

#######################
# PRIVATE             #
#######################
    def __get_new_view(self, parent, webview):
        """
            Get a new view
            @param parent as webview
            @param webview as WebKit2.WebView
            @return View
        """
        view = View(parent, webview)
        view.webview.connect("map", self.__on_view_map)
        view.webview.connect("notify::estimated-load-progress",
                             self.__on_estimated_load_progress)
        view.webview.connect("load-changed", self.__on_load_changed)
        view.webview.connect("button-press-event", self.__on_button_press)
        view.webview.connect("notify::uri", self.__on_uri_changed)
        view.webview.connect("notify::title", self.__on_title_changed)
        view.webview.connect("enter-fullscreen", self.__on_enter_fullscreen)
        view.webview.connect("leave-fullscreen", self.__on_leave_fullscreen)
        view.webview.connect("readable", self.__on_readable)
        view.webview.connect("new-page", self.__on_new_page)
        view.webview.connect("create", self.__on_create)
        view.webview.connect("close", self.__on_close)
        view.webview.connect("save-password", self.__on_save_password)
        view.webview.connect("insecure-content-detected",
                             self.__on_insecure_content_detected)
        view.show()
        return view

    def __get_view_for_webview(self, webview):
        """
            @param webview as WebView
            @return view as View
        """
        for child in self.__stack.get_children():
            if child.webview == webview:
                return child
        return None

    def __on_notify_position(self, paned, position):
        """
            Update sidebar
            @param paned as Gtk.Paned
            @param position as GParamInt
        """
        self.__stack_sidebar.update_children_snapshot()

    def __on_new_page(self, webview, uri, show):
        """
            Open a new page, switch to view if show is True
            @param webview as WebView
            @param uri as str
            @param show as bool
        """
        view = self.__get_view_for_webview(webview)
        self.add_web_view(uri, show, view)

    def __on_create(self, related, action):
        """
            Create a new view for action
            @param related as WebKit2.WebView
            @param action as WebKit2.NavigationAction
        """
        from eolie.view_web import WebView
        uri = action.get_request().get_uri()
        webview = WebView.new_with_related_view(related)
        webview.connect("ready-to-show", self.__on_ready_to_show, uri)
        return webview

    def __on_close(self, webview):
        """
            Close my self
            @param webview as WebKit2.WebView
        """
        view = self.__get_view_for_webview(webview)
        if view is not None:
            self.sidebar.close_view(view)

    def __on_ready_to_show(self, webview, uri):
        """
            Add view to window
            @param webview as WebKit2.WebView
            @param uri as str
        """
        self.add_web_view(uri, True, None, webview)

    def __on_readable(self, webview):
        """
            Show readable button in titlebar
            @param webview as WebView
        """
        self.__window.toolbar.title.show_readable_button(True)

    def __on_view_map(self, webview):
        """
            Update window
            @param webview as WebView
        """
        if webview == self.current.webview:
            self.__window.toolbar.title.show_readable_button(
                                                    webview.readable[1] != "")
            self.__window.toolbar.title.set_uri(webview.get_uri())
            if webview.is_loading():
                self.__window.toolbar.title.progress.show()
            else:
                self.__window.toolbar.title.progress.hide()
                self.__window.toolbar.title.set_title(webview.get_title())

    def __on_save_password(self, webview, username, password, netloc):
        """
            Ask user to save password
            @param webview as WebView
            @param username as str
            @param password as str
            @param netloc as str
        """
        self.__window.toolbar.title.save_password(username, password, netloc)

    def __on_button_press(self, webview, event):
        """
            Hide Titlebar popover
            @param webview as WebView
            @param event as Gdk.Event
        """
        self.__window.toolbar.title.hide_popover()

    def __on_estimated_load_progress(self, webview, value):
        """
            Update progress bar
            @param webview as WebView
            @param value GparamFloat
        """
        if webview == self.current.webview:
            value = webview.get_estimated_load_progress()
            self.__window.toolbar.title.progress.set_fraction(value)

    def __on_uri_changed(self, webview, uri):
        """
            Update uri
            @param webview as WebView
            @param uri as str
        """
        if webview == self.current.webview:
            self.__window.toolbar.title.show_readable_button(
                                                    webview.readable[1] != "")
            self.__window.toolbar.end.on_uri_changed()
            self.__window.toolbar.title.set_uri(webview.get_uri())
            # Update title if available
            title = webview.get_title()
            if title:
                self.__window.toolbar.title.set_title(title)

    def __on_title_changed(self, webview, event):
        """
            Update title
            @param webview as WebView
            @param event as  GParamSpec
        """
        if self.__load_status != WebKit2.LoadEvent.FINISHED:
            return True
        title = webview.get_title()
        if not title:
            title = _("No title")
        if title.startswith("@&$%ù²"):
            return True
        if webview == self.current.webview:
            self.__window.toolbar.title.set_title(title)
            self.__window.toolbar.actions.set_actions(webview)
        # Update history
        if title:
            uri = webview.get_uri()
            parsed = urlparse(uri)
            if parsed.scheme in ["http", "https", "file"]:
                El().history.add(title, uri)

    def __on_enter_fullscreen(self, webview):
        """
            Hide sidebar (conflict with fs)
            @param webview as WebView
        """
        self.__stack_sidebar.hide()

    def __on_leave_fullscreen(self, webview):
        """
            Show sidebar (conflict with fs)
            @param webview as WebView
        """
        self.__stack_sidebar.show()

    def __on_insecure_content_detected(self, webview, event):
        """
            @param webview as WebView
            @param event as WebKit2.InsecureContentEvent
        """
        self.__window.toolbar.title.set_insecure_content()

    def __on_load_changed(self, webview, event):
        """
            Update sidebar/urlbar
            @param webview as WebView
            @param event as WebKit2.LoadEvent
        """
        self.__load_status = event
        self.__window.toolbar.title.on_load_changed(webview, event)
        if event == WebKit2.LoadEvent.STARTED:
            if webview == self.current.webview:
                self.__window.toolbar.title.progress.show()
        elif event == WebKit2.LoadEvent.FINISHED:
            self.__on_title_changed(webview, event)
            if webview == self.current.webview:
                if not self.__window.toolbar.title.focus_in:
                    GLib.idle_add(webview.grab_focus)
                GLib.timeout_add(500,
                                 self.__window.toolbar.title.progress.hide)
