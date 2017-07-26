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
from eolie.define import El, PanelMode


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

        self.__grid_stack = Gtk.Stack()
        self.__grid_stack.set_hexpand(True)
        self.__grid_stack.set_vexpand(True)
        self.__grid_stack.set_transition_type(
                                         Gtk.StackTransitionType.CROSSFADE)
        self.__grid_stack.set_transition_duration(150)
        self.__grid_stack.show()
        self.__grid = Gtk.Grid()
        # Attach at position 1 to let place to pages_manager
        self.__grid.attach(self.__stack, 1, 0, 1, 1)
        self.__grid.show()
        self.__pages_manager = None
        self.__grid_stack.add_named(self.__grid, "grid")
        self.add(self.__grid_stack)

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
        view = self.add_view(webview, parent, window_type)
        if uri is not None:
            if load:
                panel_mode = El().settings.get_enum("panel-mode")
                # Do not load uri until we are on screen
                GLib.idle_add(webview.load_uri, uri)
                # Notify user about new window
                if window_type == Gdk.WindowType.OFFSCREEN and\
                        panel_mode == PanelMode.NONE:
                    GLib.idle_add(self.__add_overlay_view, view)
            else:
                webview.set_delayed_uri(uri)
                webview.emit("title-changed", uri)

    def add_view(self, webview, parent, window_type):
        """
            Add view t.container
            @param webview as WebView
            @param parent as WebView
            @param window_type as Gdk.WindowType
            @return view
        """
        view = self.__get_new_view(webview, parent)
        view.show()
        self.__pages_manager.add_child(view)
        # Force window type as current window is not visible
        if self.__grid_stack.get_visible_child_name() == "expose":
            window_type = Gdk.WindowType.OFFSCREEN
        if window_type == Gdk.WindowType.CHILD:
            self.__stack.add(view)
            self.__stack.set_visible_child(view)
        elif window_type == Gdk.WindowType.OFFSCREEN:
            panel_mode = El().settings.get_enum("panel-mode")
            # Little hack, we force webview to be shown (offscreen)
            # This allow getting snapshots from webkit
            window = Gtk.OffscreenWindow.new()
            if panel_mode == PanelMode.NONE:
                width = self.get_allocated_width()
            else:
                width = self.get_allocated_width() -\
                    self.__pages_manager.get_allocated_width()
            view.set_size_request(width, self.get_allocated_height())
            window.add(view)
            window.show()
            window.remove(view)
            view.set_size_request(-1, -1)
            self.__stack.add(view)
        self.__pages_manager.update_visible_child()
        # Do not count container views as destroy may be pending on somes
        count = str(len(self.__pages_manager.children))
        self.__window.toolbar.actions.count_label.set_text(count)
        return view

    def load_uri(self, uri):
        """
            Load uri in current view
            @param uri as str
        """
        if self.current is not None:
            self.current.webview.load_uri(uri)

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
        view.webview.connect("create", self.__on_create)
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
        child = self.__grid_stack.get_child_by_name("expose")
        if child is not None:
            GLib.timeout_add(500, child.set_filtered, search and expose)
        # Show expose mode
        if expose:
            self.__grid_stack.set_visible_child_name("expose")
            if self.__pages_overlay is not None:
                self.__pages_overlay.destroy()
                self.__pages_overlay = None
        else:
            self.__grid_stack.set_visible_child_name("grid")
            self.__window.toolbar.actions.view_button.set_active(False)
            GLib.idle_add(self.__pages_manager.move_first, self.current)

    def update_pages_manager(self, panel_mode):
        """
            Switch pages manager
            @param panel mode as int
        """
        views = []
        if self.__pages_manager is not None:
            for child in self.__pages_manager.children:
                views.append(child.view)
            self.__pages_manager.destroy()
        if self.__pages_overlay is not None:
            self.__pages_overlay.destroy()
            self.__pages_overlay = None
        if panel_mode == PanelMode.NONE:
            from eolie.pages_manager_flowbox import PagesManagerFlowBox
            self.__pages_manager = PagesManagerFlowBox(self.__window)
            self.__grid_stack.add_named(self.__pages_manager, "expose")
        else:
            from eolie.pages_manager_listbox import PagesManagerListBox
            self.__pages_manager = PagesManagerListBox(self.__window)
            self.__grid.attach(self.__pages_manager, 0, 0, 1, 1)
        self.__pages_manager.show()
        for view in views:
            self.__pages_manager.add_child(view)
        self.__pages_manager.update_visible_child()

    def set_panel_mode(self, panel_mode):
        """
            Set panel mode
            @param panel_mode as int
        """
        self.update_pages_manager(panel_mode)
        self.pages_manager.set_panel_mode()

    @property
    def pages_manager(self):
        """
            Get page manager
            @return PagesManager
        """
        return self.__pages_manager

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

    def __add_overlay_view(self, view):
        """
            Add an overlay view
            @param view as View
        """
        from eolie.pages_overlay import PagesOverlay
        if self.__pages_overlay is None:
            self.__pages_overlay = PagesOverlay(self.__window)
            self.add_overlay(self.__pages_overlay)
        self.__pages_overlay.show()
        self.__pages_overlay.add_child(view)
