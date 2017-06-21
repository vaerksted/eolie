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

from gi.repository import Gtk, WebKit2, GLib, Gdk

from urllib.parse import urlparse
from time import time

from eolie.view_web import WebView
from eolie.stacksidebar import StackSidebar
from eolie.view import View
from eolie.popover_webview import WebViewPopover
from eolie.define import El


class Container(Gtk.Overlay):
    """
        Main Eolie view
    """

    def __init__(self, window):
        """
            Init container
            @param window as Window
        """
        Gtk.Overlay.__init__(self)
        self.__window = window
        self.__history_queue = []
        self.__popover = WebViewPopover(window)
        if El().sync_worker is not None:
            El().sync_worker.connect("sync-finished",
                                     self.__on_sync_finished)
        self.__stack = Gtk.Stack()
        self.__stack.set_hexpand(True)
        self.__stack.set_vexpand(True)
        self.__stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.__stack.set_transition_duration(150)
        self.__stack.show()
        self.__stack_sidebar = StackSidebar(window)
        self.__stack_sidebar.show()
        grid = Gtk.Grid()
        grid.add(self.__stack_sidebar)
        grid.add(self.__stack)
        grid.show()
        self.add(grid)
        self.connect("unmap", self.__on_unmap)
        self.__stack_sidebar.set_property("halign", Gtk.Align.START)

    def add_webview(self, uri, window_type, ephemeral=False,
                    parent=None, state=None, load=True):
        """
            Add a web view to container
            @param uri as str
            @param window_type as Gdk.WindowType
            @param parent as View
            @param ephemeral as bool
            @param state as WebViewSessionState
        """
        # Use current page if possible
        if parent is None and state is None and\
                self.current is not None and\
                self.current.webview.get_uri() == "about:blank":
            self.current.webview.load_uri(uri)
        else:
            webview = View.get_new_webview(ephemeral, self.__window)
            view = self.__get_new_view(webview, parent)
            if state is not None:
                webview.restore_session_state(state)
            view.show()
            self.add_view(view, window_type)
            if uri is not None:
                if load:
                    # Do not load uri until we are on screen
                    GLib.idle_add(webview.load_uri, uri)
                else:
                    webview.set_delayed_uri(uri)
                    webview.emit("title-changed", uri)

    def add_view(self, view, window_type):
        """
            Add view to container
            @param view as View
            @param window_type as Gdk.WindowType
        """
        self.__stack_sidebar.add_child(view, window_type)
        if window_type == Gdk.WindowType.CHILD:
            self.__stack.add(view)
            self.__stack.set_visible_child(view)
        elif window_type == Gdk.WindowType.OFFSCREEN:
            # Little hack, we force webview to be shown (offscreen)
            # This allow getting snapshots from webkit
            window = Gtk.OffscreenWindow.new()
            width = self.get_allocated_width() -\
                self.__stack_sidebar.get_allocated_width()
            view.set_size_request(width, self.get_allocated_height())
            window.add(view)
            window.show()
            window.remove(view)
            view.set_size_request(-1, -1)
            self.__stack.add(view)
        self.__stack_sidebar.update_visible_child()

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

    def stop(self):
        """
            Stop pending tasks
        """
        if El().sync_worker is not None:
            self.__on_sync_finished(El().sync_worker)

    def popup_webview(self, webview, destroy):
        """
            Show webview in popopver
            @param webview as WebView
            @param destroy webview when popover hidden
        """
        view = View(webview, None)
        view.webview.connect("create", self.__on_create)
        view.show()
        self.__popover.add_view(view, destroy)
        if not self.__popover.is_visible():
            self.__popover.set_size_request(
                                 self.__window.get_allocated_width() / 3,
                                 self.__window.get_allocated_height() / 1.5)
            self.__popover.set_relative_to(self.__window.toolbar)
            self.__popover.set_position(Gtk.PositionType.BOTTOM)
            self.__popover.show()

    def on_view_map(self, webview):
        """
            Update window
            @param webview as WebView
        """
        uri = webview.delayed_uri
        if uri is None:
            uri = webview.get_uri()
        else:
            webview.load_uri(uri)
        title = webview.get_title()
        self.__window.toolbar.title.update_load_indicator(webview)
        self.__window.toolbar.title.show_popup_indicator(webview.popups)
        self.__window.toolbar.actions.set_actions(webview)
        self.__window.toolbar.title.show_readable_button(
                                            webview.readable_content != "")
        if uri is not None:
            self.__window.toolbar.title.set_uri(uri)
        if webview.is_loading():
            self.__window.toolbar.title.progress.show()
        else:
            self.__window.toolbar.title.progress.hide()
        if title:
            self.__window.toolbar.title.set_title(title)
        elif uri:
            self.__window.toolbar.title.set_title(uri)

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
    def __get_new_view(self, webview, parent):
        """
            Get a new view
            @param parent as webview
            @param webview as WebView
            @return View
        """
        view = View(webview, parent, self.__window)
        view.webview.connect("map", self.on_view_map)
        view.webview.connect("notify::estimated-load-progress",
                             self.__on_estimated_load_progress)
        view.webview.connect("load-changed", self.__on_load_changed)
        view.webview.connect("button-press-event", self.__on_button_press)
        view.webview.connect("uri-changed", self.__on_uri_changed)
        view.webview.connect("title-changed", self.__on_title_changed)
        view.webview.connect("enter-fullscreen", self.__on_enter_fullscreen)
        view.webview.connect("leave-fullscreen", self.__on_leave_fullscreen)
        view.webview.connect("readable", self.__on_readable)
        view.webview.connect("new-page", self.__on_new_page)
        view.webview.connect("create", self.__on_create)
        view.webview.connect("close", self.__on_close)
        view.webview.connect("save-password", self.__on_save_password)
        view.webview.connect("script-dialog", self.__on_script_dialog)
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

    def __grab_focus_on_current(self):
        """
            Grab focus on current view
        """
        if not self.__window.toolbar.title.lock_focus:
            self.current.webview.grab_focus()

    def __on_new_page(self, webview, uri, window_type):
        """
            Open a new page, switch to view if show is True
            @param webview as WebView
            @param uri as str
            @param window_type as Gdk.WindowType
        """
        if uri:
            if window_type == Gdk.WindowType.SUBSURFACE:
                if webview.ephemeral:
                    webview = WebView.new_ephemeral()
                else:
                    webview = WebView.new()
                self.popup_webview(webview, True)
                GLib.idle_add(webview.load_uri, uri)
            else:
                parent = self.__get_view_for_webview(webview)
                self.add_webview(uri, window_type, webview.ephemeral, parent)

    def __on_create(self, related, navigation_action):
        """
            Create a new view for action
            @param related as WebView
            @param navigation_action as WebKit2.NavigationAction
            @param force as bool
        """
        webview = WebView.new_with_related_view(related, self.__window)
        webview.connect("ready-to-show",
                        self.__on_ready_to_show,
                        related,
                        navigation_action)
        return webview

    def __on_close(self, webview):
        """
            Close my self
            @param webview as WebView
        """
        self.__window.toolbar.title.remove_from_text_entry_history(webview)
        view = self.__get_view_for_webview(webview)
        if view is not None:
            self.sidebar.close_view(view)

    def __on_ready_to_show(self, webview, related, navigation_action):
        """
            Add a new webview with related
            @param webview as WebView
            @param related as WebView
            @param navigation_action as WebKit2.NavigationAction
        """
        properties = webview.get_window_properties()
        if properties.get_locationbar_visible() and\
                properties.get_toolbar_visible():
            view = self.__get_view_for_webview(related)
            view = self.__get_new_view(webview, None)
            view.show()
            active_window = El().get_new_window()
            active_window.container.add_view(view, Gdk.WindowType.CHILD)
        else:
            elapsed = time() - related.last_click_time
            # Block popups, see WebView::set_popup_exception() for details
            popup_block = El().settings.get_value("popupblock")
            parsed_related = urlparse(related.get_uri())
            exception = \
                related.js_load or\
                El().popup_exceptions.find(parsed_related.netloc) or\
                El().popup_exceptions.find(parsed_related.netloc +
                                           parsed_related.path) or\
                (not related.is_loading() and elapsed < 0.5)
            if not exception and popup_block and\
                    navigation_action.get_navigation_type() in [
                                   WebKit2.NavigationType.OTHER,
                                   WebKit2.NavigationType.RELOAD,
                                   WebKit2.NavigationType.BACK_FORWARD]:
                related.add_popup(webview)
                if related == self.current.webview:
                    self.__window.toolbar.title.show_popup_indicator(True)
                return
            self.popup_webview(webview, True)

    def __on_readable(self, webview):
        """
            Show readable button in titlebar
            @param webview as WebView
        """
        if webview == self.current.webview:
            self.__window.toolbar.title.show_readable_button(True)

    def __on_save_password(self, webview, username, userform,
                           password, passform, uri):
        """
            Ask user to save password
            @param webview as WebView
            @param username as str
            @param userform as str
            @param password as str
            @param passform as str
            @param uri as str
        """
        self.__window.toolbar.title.show_password(username, userform,
                                                  password, passform,
                                                  uri)

    def __on_script_dialog(self, webview, dialog):
        """
            Show message to user
            @param webview as WebView
            @param dialog as WebKit2.ScriptDialog
        """
        if not dialog.get_message().startswith("@&$%ù²"):
            self.__window.toolbar.title.show_javascript(dialog)
            return True

    def __on_button_press(self, webview, event):
        """
            Hide Titlebar popover
            @param webview as WebView
            @param event as Gdk.Event
        """
        self.__window.toolbar.title.close_popover()

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
            @param uri as GParamString (Do not use)
        """
        if webview == self.current.webview:
            if uri:
                self.__window.toolbar.title.show_readable_button(
                                                webview.readable_content != "")
                self.__window.toolbar.title.set_uri(uri)
            else:
                # Close web page if uri is null
                self.sidebar.close_view(webview.get_ancestor(View))

    def __on_title_changed(self, webview, title):
        """
            Update title
            @param webview as WebView
            @param title as str
        """
        if webview == self.current.webview:
            self.__window.toolbar.title.set_title(title)
        # Update history
        uri = webview.get_uri()
        parsed = urlparse(uri)
        if parsed.scheme in ["http", "https"] and\
                not webview.ephemeral:
            mtime = round(time(), 2)
            El().history.thread_lock.acquire()
            history_id = El().history.add(title, uri, mtime)
            El().history.set_page_state(uri, mtime)
            El().history.thread_lock.release()
            if El().sync_worker is not None:
                if El().sync_worker.syncing:
                    self.__history_queue.append(history_id)
                else:
                    El().sync_worker.push_history([history_id])

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
        if webview != self.current.webview:
            return
        self.__window.toolbar.title.update_load_indicator(webview)
        uri = webview.get_uri()
        parsed = urlparse(uri)
        focus_in_view = parsed.scheme in ["http", "https", "file"]
        if event == WebKit2.LoadEvent.STARTED:
            self.__window.toolbar.title.set_title(uri)
            # Give focus to url bar
            if not focus_in_view:
                self.__window.toolbar.title.start_search()
            self.__window.toolbar.title.show_popup_indicator(False)
            # Turn off reading mode if needed
            if self.current.reading:
                self.current.switch_read_mode()
            self.__window.toolbar.title.progress.show()
        elif event == WebKit2.LoadEvent.COMMITTED:
            self.__window.toolbar.actions.set_actions(webview)
            self.__window.toolbar.title.set_title(uri)
            self.__window.toolbar.title.remove_from_text_entry_history(webview)
        elif event == WebKit2.LoadEvent.FINISHED:
            title = webview.get_title()
            if title is not None:
                self.__window.toolbar.title.set_title(title)
            # Give focus to webview
            if focus_in_view:
                GLib.idle_add(self.__grab_focus_on_current)
            # Hide progress
            GLib.timeout_add(500, self.__window.toolbar.title.progress.hide)

    def __on_unmap(self, widget):
        """
            Disconnect sync signal
            @param widget as Gtk.Widget
        """
        if El().sync_worker is not None:
            El().sync_worker.disconnect_by_func(self.__on_sync_finished)

    def __on_sync_finished(self, worker):
        """
            Commit queue to sync
            @param worker as SyncWorker
        """
        if self.__history_queue:
            history_id = self.__history_queue.pop(0)
            worker.push_history([history_id])
            GLib.idle_add(self.__on_sync_finished, worker)
