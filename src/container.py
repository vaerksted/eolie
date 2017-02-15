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

from eolie.stacksidebar import StackSidebar
from eolie.define import El


class Container(Gtk.Paned):
    """
        Main Eolie view
    """

    def __init__(self):
        """
            Init container
        """
        Gtk.Paned.__init__(self)
        self.set_position(
            El().settings.get_value("paned-width").get_int32())
        self.connect("notify::position", self.__on_notify_position)
        self.__stack = Gtk.Stack()
        self.__stack.set_hexpand(True)
        self.__stack.set_vexpand(True)
        self.__stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.__stack.set_transition_duration(150)
        self.__stack.show()
        self.__stack_sidebar = StackSidebar(self)
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

    @property
    def window(self):
        """
            Get window for self
            @return Window
        """
        return self.get_toplevel()

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
        from eolie.view import View
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
        view.webview.connect("insecure-content-detected",
                             self.__on_insecure_content_detected)
        view.show()
        return view

    def __on_notify_position(self, paned, position):
        """
            Update sidebar
            @param paned as Gtk.Paned
            @param position as GParamInt
        """
        self.__stack_sidebar.update_children_snapshot()

    def __on_readable(self, view):
        """
            Show readable button in titlebar
            @param view as WebView
        """
        self.window.toolbar.title.show_readable_button(True)

    def __on_view_map(self, view):
        """
            Update window
            @param view as WebView
        """
        if view == self.current.webview:
            self.window.toolbar.title.set_uri(view.get_uri())
            if view.is_loading():
                self.window.toolbar.title.progress.show()
            else:
                self.window.toolbar.title.progress.hide()
                self.window.toolbar.title.set_title(view.get_title())

    def __on_button_press(self, view, event):
        """
            Hide Titlebar popover
            @param view as WebView
            @param event as Gdk.Event
        """
        self.window.toolbar.title.hide_popover()

    def __on_estimated_load_progress(self, view, value):
        """
            Update progress bar
            @param view as WebView
            @param value GparamFloat
        """
        if view == self.current.webview:
            value = view.get_estimated_load_progress()
            self.window.toolbar.title.progress.set_fraction(value)

    def __on_uri_changed(self, view, uri):
        """
            Update uri
            @param view as WebView
            @param uri as str
        """
        if view == self.current.webview:
            self.window.toolbar.end.on_uri_changed()
            self.window.toolbar.title.set_uri(view.get_uri())

    def __on_title_changed(self, view, event):
        """
            Update title
            @param view as WebView
            @param event as  GParamSpec
        """
        uri = view.get_uri()
        title = view.get_title()
        if view == self.current.webview:
            if title:
                self.window.toolbar.title.set_title(title)
            else:
                self.window.toolbar.title.set_title(uri)
            self.window.toolbar.actions.set_actions(view)
        # Update history
        if title:
            El().history.add(title, uri)

    def __on_enter_fullscreen(self, view):
        """
            Hide sidebar (conflict with fs)
            @param view as WebView
        """
        self.__stack_sidebar.hide()

    def __on_leave_fullscreen(self, view):
        """
            Show sidebar (conflict with fs)
            @param view as WebView
        """
        self.__stack_sidebar.show()

    def __on_insecure_content_detected(self, view, event):
        """
            @param view as WebView
            @param event as WebKit2.InsecureContentEvent
        """
        self.window.toolbar.title.set_insecure_content()

    def __on_load_changed(self, view, event):
        """
            Update sidebar/urlbar
            @param view as WebView
            @param event as WebKit2.LoadEvent
        """
        self.window.toolbar.title.on_load_changed(view, event)
        if event == WebKit2.LoadEvent.STARTED:
            if view == self.current.webview:
                self.window.toolbar.title.progress.show()
        elif event == WebKit2.LoadEvent.FINISHED:
            if view == self.current.webview:
                if not self.window.toolbar.title.focus_in:
                    GLib.idle_add(view.grab_focus)
                GLib.timeout_add(500, self.window.toolbar.title.progress.hide)
