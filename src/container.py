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

from gi.repository import Gtk, GLib, Gdk

from eolie.view import View
from eolie.popover_webview import WebViewPopover
from eolie.pages_manager import PagesManager
from eolie.sites_manager import SitesManager
from eolie.define import El


class Container(Gtk.Overlay):
    """
        Main Eolie view
    """

    def __init__(self, window):
        """
            Ini.container
            @param window as Window
        """
        Gtk.Overlay.__init__(self)
        self.__window = window
        self.__pages_overlay = None
        self.__popover = WebViewPopover(window)

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
                                       Gtk.StackTransitionType.OVER_RIGHT_LEFT)
        self.__expose_stack.set_transition_duration(150)
        self.__expose_stack.show()
        self.__pages_manager = PagesManager(self.__window)
        self.__pages_manager.show()
        self.__sites_manager = SitesManager(self.__window)
        if El().settings.get_value("show-sidebar"):
            self.__sites_manager.show()
        El().settings.connect("changed::show-sidebar",
                              self.__on_show_sidebar_changed)
        paned = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        paned.pack1(self.__sites_manager, False, False)
        paned.add2(self.__expose_stack)
        position = El().settings.get_value("sidebar-position").get_int32()
        paned.set_position(position)
        paned.show()
        self.__expose_stack.add_named(self.__stack, "stack")
        self.__expose_stack.add_named(self.__pages_manager, "expose")
        self.add(paned)

    def add_webview(self, uri, window_type, ephemeral=False,
                    parent=None, state=None, load=True):
        """
            Add a web view t.container
            @param uri as str
            @param window_type as Gdk.WindowType
            @param parent as View
            @param ephemeral as bool
            @param state as WebViewSessionState
        """
        webview = View.get_new_webview(ephemeral, self.__window)
        if state is not None:
            webview.restore_session_state(state)
        self.add_view(webview, parent, window_type)
        if uri is not None:
            if load:
                # Do not load uri until we are on screen
                GLib.idle_add(webview.load_uri, uri)
            else:
                webview.set_delayed_uri(uri)
                webview.emit("title-changed", uri)

    def add_view(self, webview, parent, window_type):
        """
            Add view t.container
            @param webview as WebView
            @param parent as WebView
            @param window_type as Gdk.WindowType
        """
        view = self.__get_new_view(webview, parent)
        view.show()
        self.__pages_manager.add_child(view)
        # Force window type as current window is not visible
        if self.__expose_stack.get_visible_child_name() == "expose":
            window_type = Gdk.WindowType.OFFSCREEN
        if window_type == Gdk.WindowType.CHILD:
            self.__stack.add(view)
            self.__stack.set_visible_child(view)
        elif window_type == Gdk.WindowType.OFFSCREEN:
            # Little hack, we force webview to be shown (offscreen)
            # This allow getting snapshots from webkit
            window = Gtk.OffscreenWindow.new()
            view.set_size_request(self.get_allocated_width(),
                                  self.get_allocated_height())
            window.add(view)
            window.show()
            window.remove(view)
            view.set_size_request(-1, -1)
            self.__stack.add(view)
        self.__pages_manager.update_visible_child()
        # Do not count container views as destroy may be pending on somes
        count = str(len(self.__pages_manager.children))
        self.__window.toolbar.actions.count_label.set_text(count)

    def load_uri(self, uri):
        """
            Load uri in current view
            @param uri as str
        """
        if self.current is not None:
            self.current.webview.load_uri(uri)

    def set_visible_webview(self, webview):
        """
            Set visible webview
            @param webview as WebView
        """
        wanted = False
        for view in self.__stack.get_children():
            if view.webview == webview:
                wanted = view
        if wanted is not None:
            self.set_visible_view(wanted)

    def set_visible_view(self, view):
        """
            Set visible view
            @param view as View
        """
        # Remove from offscreen window if needed
        # Will kill running get_snapshot :-/
        parent = view.get_parent()
        if parent is not None and isinstance(parent, Gtk.OffscreenWindow):
            parent.remove(view)
            view.set_size_request(-1, -1)
            self.__stack.add(view)
        self.__stack.set_visible_child(view)
        if self.__pages_overlay is not None:
            self.__pages_overlay.destroy_child(view)

    def popup_webview(self, webview, destroy):
        """
            Show webview in popopver
            @param webview as WebView
            @param destroy webview when popover hidden
        """
        view = View(webview, None, self.__window)
        view.show()
        self.__popover.add_view(view, destroy)
        if not self.__popover.is_visible():
            self.__popover.set_size_request(
                                 self.__window.get_allocated_width() / 3,
                                 self.__window.get_allocated_height() / 1.5)
            self.__popover.set_relative_to(self.__window.toolbar)
            self.__popover.set_position(Gtk.PositionType.BOTTOM)
            self.__popover.popup()

    def set_expose(self, expose, search=False):
        """
            Show current views
            @param expose as bool
            @param search as bool
        """
        # Show search bar
        child = self.__expose_stack.get_child_by_name("expose")
        GLib.timeout_add(500, child.set_filtered, search and expose)
        # Show expose mode
        if expose:
            self.__expose_stack.set_visible_child_name("expose")
        else:
            self.__expose_stack.set_visible_child_name("stack")
            self.__window.toolbar.actions.view_button.set_active(False)
            GLib.idle_add(self.__pages_manager.move_first, self.current)

    @property
    def pages_manager(self):
        """
            Get pages manager
            @return PagesManager
        """
        return self.__pages_manager

    @property
    def sites_manager(self):
        """
            Get sites manager
            @return SitesManager
        """
        return self.__sites_manager

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
        return self.__stack.get_visible_child()

#######################
# PRIVATE             #
#######################
    def __get_new_view(self, webview, parent):
        """
            Get a new view
            @param parent as webview
            @param webview as WebView
            @return View
        """
        view = View(webview, parent, self.__window)
        view.show()
        return view

    def __on_show_sidebar_changed(self, settings, value):
        """
            Show/hide panel
            @param settings as Gio.Settings
            @param value as bool
        """
        if El().settings.get_value("show-sidebar"):
            self.__sites_manager.show()
        else:
            self.__sites_manager.hide()
