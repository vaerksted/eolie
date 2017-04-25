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

from gi.repository import Gtk, WebKit2, GLib

from urllib.parse import urlparse
from time import time

from eolie.stacksidebar import StackSidebar
from eolie.view import View
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
        if El().sync_worker is not None:
            El().sync_worker.connect("sync-finish", self.__on_sync_finish)
        self.__stack = Gtk.Stack()
        self.__stack.set_hexpand(True)
        self.__stack.set_vexpand(True)
        self.__stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.__stack.set_transition_duration(150)
        self.__stack.show()
        self.__stack_sidebar = StackSidebar(window)
        self.__stack_sidebar.show()
        self.add(self.__stack)
        self.connect("map", self.__on_map)
        self.__stack_sidebar.set_property("halign", Gtk.Align.START)
        self.add_overlay(self.__stack_sidebar)

    def add_web_view(self, uri, show, private=False, parent=None,
                     webview=None, state=None):
        """
            Add a web view to container
            @param uri as str
            @param show as bool
            @param parent as View
            @param private as bool
            @param webview as WebView
            @param state as WebViewSessionState
        """
        view = self.__get_new_view(private, parent, webview)
        if state is not None:
            view.webview.restore_session_state(state)
        view.show()
        self.__stack_sidebar.add_child(view)
        if uri is not None:
            # Do not load uri until we are on screen
            GLib.idle_add(view.webview.load_uri, uri)
        if show:
            self.__stack.add(view)
            self.__stack.set_visible_child(view)
        else:
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
            self.__on_sync_finish(El().sync_worker)

    def update_children_allocation(self):
        """
            Update stack and stacksidebar allocation
        """
        width = self.__stack_sidebar.get_allocated_width()
        self.__stack.set_margin_start(width)

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
    def __get_new_view(self, private, parent, webview):
        """
            Get a new view
            @param private as bool
            @param parent as webview
            @param webview as WebView
            @return View
        """
        view = View(private, parent, webview)
        view.webview.connect("map", self.__on_view_map)
        view.webview.connect("notify::estimated-load-progress",
                             self.__on_estimated_load_progress)
        view.webview.connect("load-changed", self.__on_load_changed)
        view.webview.connect("button-press-event", self.__on_button_press)
        view.webview.connect("notify::uri", self.__on_uri_changed)
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

    def __on_new_page(self, webview, uri, show):
        """
            Open a new page, switch to view if show is True
            @param webview as WebView
            @param uri as str
            @param show as bool
        """
        if uri:
            view = self.__get_view_for_webview(webview)
            self.add_web_view(uri, show, webview.private, view)

    def __on_create(self, related, navigation_action):
        """
            Create a new view for action
            @param related as WebView
            @param navigation_action as WebKit2.NavigationAction
        """
        # Block popups, see WebView::set_popup_exception() for details
        popup_block = El().settings.get_value("popupblock")
        request_parsed = urlparse(navigation_action.get_request().get_uri())
        request_uri = request_parsed.netloc + request_parsed.path
        parsed = urlparse(related.get_uri())
        exception = El().adblock.is_an_exception(parsed.netloc) or\
            El().adblock.is_an_exception(parsed.netloc + parsed.path)
        if not exception and popup_block and\
                navigation_action.get_navigation_type() in [
                               WebKit2.NavigationType.OTHER,
                               WebKit2.NavigationType.RELOAD,
                               WebKit2.NavigationType.BACK_FORWARD] and\
                request_uri != related.popup_exception:
            related.set_popup_exception(request_uri)
            return
        from eolie.view_web import WebView
        webview = WebView.new_with_related_view(related)
        webview.connect("ready-to-show", self.__on_ready_to_show)
        return webview

    def __on_close(self, webview):
        """
            Close my self
            @param webview as WebView
        """
        view = self.__get_view_for_webview(webview)
        if view is not None:
            self.sidebar.close_view(view)

    def __on_ready_to_show(self, webview):
        """
            Add view to window
            @param webview as WebView
        """
        self.add_web_view(None, True, webview.private, None, webview)

    def __on_readable(self, webview):
        """
            Show readable button in titlebar
            @param webview as WebView
        """
        if webview == self.current.webview:
            self.__window.toolbar.title.show_readable_button(True)

    def __on_view_map(self, webview):
        """
            Update window
            @param webview as WebView
        """
        self.__window.toolbar.title.update_load_indicator(webview)
        if webview == self.current.webview:
            self.__window.toolbar.actions.set_actions(webview)
            self.__window.toolbar.title.show_readable_button(
                                                webview.readable_content != "")
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

    def __on_script_dialog(self, webview, dialog):
        """
            Show message to user
            @param webview as WebView
            @param dialog as WebKit2.ScriptDialog
        """
        self.__window.toolbar.title.show_javascript(dialog)
        return True

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
            uri = webview.get_uri()
            if uri:
                self.__window.toolbar.title.show_readable_button(
                                                webview.readable_content != "")
                self.__window.toolbar.title.set_uri(uri)
                title = webview.get_title()
                if title:
                    self.__window.toolbar.title.set_title(title)
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
            self.__window.toolbar.actions.set_actions(webview)
        # Update history
        uri = webview.get_uri()
        parsed = urlparse(uri)
        if parsed.scheme in ["http", "https"] and\
                not webview.private:
            mtime = round(time(), 2)
            # Do not try to add to db if worker is syncing
            # We may lock sqlite and current webview otherwise
            # We use a queue and will commit items when sync is finished
            if El().sync_worker is None:
                El().history.add(title, uri, mtime)
            elif El().sync_worker.syncing:
                self.__history_queue.append((title, uri, mtime))
            else:
                history_id = El().history.add(title, uri, mtime)
                El().sync_worker.push_history([history_id])

    def __on_enter_fullscreen(self, webview):
        """
            Hide sidebar (conflict with fs)
            @param webview as WebView
        """
        self.__stack.set_margin_start(0)
        self.__stack_sidebar.hide()

    def __on_leave_fullscreen(self, webview):
        """
            Show sidebar (conflict with fs)
            @param webview as WebView
        """
        width = self.__stack_sidebar.get_allocated_width()
        self.__stack.set_margin_start(width)
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
        parsed = urlparse(webview.get_uri())
        if event == WebKit2.LoadEvent.STARTED:
            # Turn off reading mode if needed
            if self.current.reading:
                self.current.switch_read_mode()
            if parsed.scheme == "populars":
                GLib.idle_add(self.__window.toolbar.title.start_search)
            self.__window.toolbar.title.progress.show()
        elif event == WebKit2.LoadEvent.COMMITTED:
            pass
        elif event == WebKit2.LoadEvent.FINISHED:
            # Give focus to webview if allowed
            if not self.__window.toolbar.title.lock_focus:
                if parsed.scheme in ["http", "https"]:
                    GLib.idle_add(webview.grab_focus)
            # Hide progress
            GLib.timeout_add(500, self.__window.toolbar.title.progress.hide)

    def __on_map(self, widget):
        """
            Calculate widget margin
            @param widget as Gtk.Widget
        """
        self.update_children_allocation()

    def __on_sync_finish(self, worker):
        """
            Commit queue
            @param worker as SyncWorker
        """
        if self.__history_queue:
            (title, uri, mtime) = self.__history_queue.pop(0)
            history_id = El().history.add(title, uri, mtime)
            worker.push_history([history_id])
            GLib.idle_add(self.__on_sync_finish, worker)
