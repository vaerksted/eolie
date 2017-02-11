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
from eolie.utils import strip_uri


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
        self.__progress = Gtk.ProgressBar()
        self.__progress.get_style_context().add_class("progressbar")
        self.__progress.set_property("valign", Gtk.Align.START)
        overlay = Gtk.Overlay.new()
        overlay.add(self.__stack)
        overlay.add_overlay(self.__progress)
        overlay.show()
        self.add1(self.__stack_sidebar)
        self.child_set_property(self.__stack_sidebar, "shrink", False)
        self.add2(overlay)

    def add_web_view(self, uri, show, state=None):
        """
            Add a web view to container
            @param uri as str
            @param show as bool
            @param state as WebKit2.WebViewSessionState
        """
        view = self.__get_new_webview()
        if state is not None:
            view.restore_session_state(state)
        view.show()
        self.__stack_sidebar.add_child(view)
        if uri is not None:
            view.load_uri(uri)
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
            self.current.load_uri(uri)

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
    def __get_new_webview(self):
        """
            Get a new webview
            @return WebView
        """
        from eolie.web_view import WebView
        view = WebView()
        view.connect("map", self.__on_view_map)
        view.connect("notify::estimated-load-progress",
                     self.__on_estimated_load_progress)
        view.connect("load-changed", self.__on_load_changed)
        view.connect("button-press-event", self.__on_button_press)
        view.connect("notify::uri", self.__on_uri_changed)
        view.connect("notify::title", self.__on_title_changed)
        view.connect("enter-fullscreen", self.__on_enter_fullscreen)
        view.connect("leave-fullscreen", self.__on_leave_fullscreen)
        view.connect("insecure-content-detected",
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

    def __on_view_map(self, internal, view):
        """
            Update window
            @param internal as WebKit2.WebView
            @param view as WebView
        """
        if view == self.current:
            self.window.toolbar.title.set_uri(view.get_uri())
            if view.is_loading():
                self.__progress.show()
            else:
                self.__progress.hide()
                self.window.toolbar.title.set_title(view.get_title())

    def __on_button_press(self, internal, event, view):
        """
            Hide Titlebar popover
            @param internal as WebKit2.WebView
            @param event as Gdk.Event
            @param view as WebView
        """
        self.window.toolbar.title.hide_popover()

    def __on_estimated_load_progress(self, internal, value, view):
        """
            Update progress bar
            @param internal as WebKit2.WebView
            @param value GparamFloat
            @param view as WebView
        """
        if view == self.current:
            value = view.get_estimated_load_progress()
            self.__progress.set_fraction(value)

    def __on_uri_changed(self, internal, uri, view):
        """
            Update uri
            @param internal as WebKit2.WebView
            @param uri as str
            @param view as WebView
        """
        if view == self.current:
            self.window.toolbar.title.set_uri(view.get_uri())

    def __on_title_changed(self, internal, event, view):
        """
            Update title
            @param internal as WebKit2.WebView
            @param title as str
            @param view as WebView
        """
        if event.name != "title":
            return
        uri = view.get_uri()
        title = view.get_title()
        if view == self.current:
            if title:
                self.window.toolbar.title.set_title(title)
            else:
                self.window.toolbar.title.set_title(uri)
            self.window.toolbar.actions.set_actions(view)
        # Update history
        if title:
            El().history.add(title, strip_uri(uri))
            # Update loaded uri too allowing user's bookmarks popularity
            if strip_uri(uri, False) != strip_uri(view.loaded_uri, False):
                El().history.add(title, strip_uri(view.loaded_uri))

    def __on_enter_fullscreen(self, internal, view):
        """
            Hide sidebar (conflict with fs)
            @param internal as WebKit2.WebView
            @param view as WebView
        """
        self.__stack_sidebar.hide()

    def __on_leave_fullscreen(self, internal, view):
        """
            Show sidebar (conflict with fs)
            @param internal as WebKit2.WebView
            @param view as WebView
        """
        self.__stack_sidebar.show()

    def __on_insecure_content_detected(self, internal, event, view):
        """
            @param internal as WebKit2.WebView
            @param event as WebKit2.InsecureContentEvent
            @param view as WebView
        """
        self.window.toolbar.title.set_insecure_content()

    def __on_load_changed(self, internal, event, view):
        """
            Update sidebar/urlbar
            @param internal as WebKit2.WebView
            @param event as WebKit2.LoadEvent
            @param view as WebView
        """
        self.window.toolbar.title.on_load_changed(view, event)
        if event == WebKit2.LoadEvent.STARTED:
            if view == self.current:
                self.__progress.show()
        elif event == WebKit2.LoadEvent.FINISHED:
            if view == self.current:
                self.__progress.hide()
