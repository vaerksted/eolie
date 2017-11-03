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

from gi.repository import Gtk, GLib

from gettext import gettext as _

from eolie.view import View
from eolie.popover_webview import WebViewPopover
from eolie.pages_manager import PagesManager
from eolie.sites_manager import SitesManager
from eolie.define import El, LoadingType


class DelayedStack(Gtk.Stack):
    """
        Gtk.Stack not mapping widgets on add()
    """

    def __init__(self):
        """
            Init widget
        """
        Gtk.Stack.__init__(self)
        self.__pending_widget = []

    def add(self, widget):
        """
            Add widget to stack
            @param widget as Gtk.Widget
        """
        self.__pending_widget.append(widget)

    def set_visible_child(self, widget):
        """
            Set widget visible
        """
        if widget in self.__pending_widget:
            self.__pending_widget.remove(widget)
            Gtk.Stack.add(self, widget)
        Gtk.Stack.set_visible_child(self, widget)

    def get_children(self):
        """
            Return stack children
            @return [Gtk.Widget]
        """
        return Gtk.Stack.get_children(self) + self.__pending_widget


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
        self.__popover = WebViewPopover(window)
        self.__current = None
        self.__pending_items = []

        self.__stack = DelayedStack()
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
        self.__pages_manager = PagesManager(self.__window)
        self.__pages_manager.show()
        self.__sites_manager = SitesManager(self.__window)
        if El().settings.get_value("show-sidebar"):
            self.__sites_manager.show()
        El().settings.connect("changed::show-sidebar",
                              self.__on_show_sidebar_changed)
        paned = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        paned.pack1(self.__sites_manager, False, False)
        paned.add2(self.__stack)
        position = El().settings.get_value("sidebar-position").get_int32()
        paned.set_position(position)
        paned.connect("notify::position", self.__on_paned_notify_position)
        paned.show()
        self.__expose_stack.add_named(paned, "stack")
        self.__expose_stack.add_named(self.__pages_manager, "expose")
        self.add(self.__expose_stack)

    def add_webview(self, uri, loading_type, ephemeral=False,
                    state=None, gtime=None):
        """
            Add a webview to container
            @param uri as str
            @param loading_type as Gdk.LoadingType
            @param ephemeral as bool
            @param state as WebViewSessionState
            @param gtime as int
            @return WebView
        """
        webview = View.get_new_webview(ephemeral, self.__window)
        if gtime is not None:
            # We force atime to be sure child is initially sorted after parent
            webview.set_atime(gtime)
            webview.set_gtime(gtime)
        if state is not None:
            webview.restore_session_state(state)
        if uri is not None:
            webview.set_uri(uri)
            if loading_type != LoadingType.OFFLOAD:
                # Do not load uri until we are on screen
                GLib.idle_add(webview.load_uri, uri)
        self.add_view(webview, loading_type)
        return webview

    def add_webviews(self, items):
        """
            Add webviews to container
            @param items as [(uri, title, atime, gtime,
                              ephemeral, state, loading_type)]
        """
        running = self.__pending_items != []
        self.__pending_items += items
        if not running:
            self.__add_pending_items()

    def add_view(self, webview, loading_type):
        """
            Add view to container
            @param webview as WebView
            @param loading_type as Gdk.LoadingType
        """
        view = self.__get_new_view(webview)
        view.show()
        self.__pages_manager.add_view(view)
        self.__sites_manager.add_view(view)
        # Check for expose because we will be unable to get snapshot as
        # window is not visible
        if loading_type == LoadingType.FOREGROUND and not self.in_expose:
            self.__current = view
            self.__stack.add(view)
            self.__pages_manager.update_visible_child()
            self.__sites_manager.update_visible_child()
            self.__stack.set_visible_child(view)
        elif loading_type in [LoadingType.BACKGROUND, LoadingType.OFFLOAD] or\
                self.in_expose:
            # Little hack, we force webview to be shown (offscreen)
            # This allow getting snapshots from webkit
            window = Gtk.OffscreenWindow.new()
            view.set_size_request(self.get_allocated_width(),
                                  self.get_allocated_height())
            window.add(view)
            window.show()
            window.remove(view)
            view.set_size_request(-1, -1)
            # Needed to force view to resize
            view.queue_draw()
            self.__stack.add(view)
            window.destroy()
            if self.in_expose and loading_type == LoadingType.FOREGROUND:
                self.set_current(view, True)
        # Do not count container views as destroy may be pending on somes
        # Reason: we do not remove/destroy view to let stack animation run
        count = len(self.__pages_manager.children)
        self.__window.toolbar.actions.count_label.set_text(str(count))
        El().update_unity_badge()

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
        self.__sites_manager.update_visible_child()
        if switch:
            self.__stack.set_visible_child(view)

    def popup_webview(self, webview, destroy):
        """
            Show webview in popopver
            @param webview as WebView
            @param destroy webview when popover hidden
        """
        view = View(webview, self.__window, True)
        view.show()
        self.__popover.add_view(view, destroy)
        if not self.__popover.is_visible():
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
        if not child.filtered:
            GLib.timeout_add(500, child.set_filtered, search and expose)
        # Show expose mode
        if expose:
            self.__pages_manager.update_sort()
            self.__expose_stack.set_visible_child_name("expose")
        else:
            if self.__stack.get_visible_child() != self.__current:
                self.__stack.set_visible_child(self.__current)
            self.__expose_stack.set_visible_child_name("stack")
            self.__window.toolbar.actions.view_button.set_active(False)
            self.__window.container.pages_manager.set_filter("")
            self.__pages_manager.update_visible_child()
            child.set_filtered(False)

    def try_close_view(self, view):
        """
            Ask user before closing view if forms filled
            @param view as View
        """
        page_id = view.webview.get_page_id()
        El().helper.call("FormsFilled",
                         GLib.Variant("(i)", (page_id,)),
                         self.__on_forms_filled, page_id, view)

    def close_view(self, view):
        """
            close current view
            @param view as View
            @param animate as bool
        """
        # Get children less view
        children = self.__get_children()
        if view.destroying:
            return
        children.remove(view)
        reversed_children = list(reversed(children))
        children_count = len(children)
        El().history.set_page_state(view.webview.uri)
        self.__window.close_popovers()
        # Needed to unfocus titlebar
        self.__window.set_focus(None)
        was_current = view == self.__window.container.current
        gtime = view.webview.gtime
        El().pages_menu.add_action(view.webview.title,
                                   view.webview.uri,
                                   view.webview.ephemeral,
                                   view.webview.get_session_state())
        view.destroy()
        # Don't show 0 as we are going to open a new one
        if children_count:
            El().update_unity_badge()
            self.__window.toolbar.actions.count_label.set_text(
                                                       str(children_count))
        # Nothing to do if was not current page
        if not was_current:
            return False
        next_view = None
        # First we search a brother ie a paged opened from the same parent page
        for view in reversed_children:
            if view.webview.gtime == gtime:
                next_view = view
                break
        # Get view with gtime -+ 1
        # If closing a parent, go to child
        # If closing a child, go to parent
        if next_view is None:
            for view in reversed_children:
                if view.webview.gtime == gtime + 1 or\
                        view.webview.gtime == gtime - 1:
                    next_view = view
                    break
        # Get view with higher access time
        if next_view is None:
            atime = 0
            for view in reversed_children:
                if view.webview.atime >= atime:
                    next_view = view
                    atime = view.webview.atime
        if next_view is not None:
            self.__window.container.set_current(next_view, True)
        else:
            # We are last row, add a new one
            self.__window.container.add_webview(El().start_page,
                                                LoadingType.FOREGROUND)

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
        return self.__current

#######################
# PRIVATE             #
#######################
    def __get_new_view(self, webview):
        """
            Get a new view
            @param webview as WebView
            @return View
        """
        view = View(webview, self.__window)
        view.show()
        return view

    def __get_children(self):
        """
            Get children
            @return [View]
        """
        return [child for child in self.__stack.get_children()
                if not child.destroying]

    def __add_pending_items(self):
        """
            Add pending items to container
        """
        if self.__pending_items:
            (uri, title, atime, gtime,
             ephemeral, state, loading_type) = self.__pending_items.pop(0)
            webview = self.add_webview(uri, loading_type, ephemeral, state)
            webview.set_title(title)
            webview.set_atime(atime)
            webview.set_gtime(gtime)
            GLib.idle_add(self.__add_pending_items)

    def __on_paned_notify_position(self, paned, ignore):
        """
            Update SitesManager width based on current position
            @param paned as Gtk.Paned
            @param ignore as GParamInt
        """
        position = paned.get_position()
        El().settings.set_value("sidebar-position",
                                GLib.Variant("i", position))
        self.__sites_manager.set_minimal(position < 80)

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
                dialog.set_transient_for(self.__window)
                dialog.connect("response", on_response_id, view, self)
                close.connect("clicked", on_close, dialog)
                cancel.connect("clicked", on_cancel, dialog)
                dialog.run()
            else:
                self.close_view(view)
        except:
            self.close_view(view)
