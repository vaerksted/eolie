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

from gi.repository import Gtk, Gdk, Gio, GLib, WebKit2

from gettext import gettext as _
from urllib.parse import urlparse
from time import time
import cairo

from eolie.define import El, Indicator, ArtSize


class WebViewSignals:
    """
        Handle webview signals
    """

    def __init__(self):
        """
            Init handler
            @param webview as WebView
        """
        self.__js_timeout_id = None
        self.__signals_connected = False
        self.__cancellable = Gio.Cancellable()
        self.__reset_js_blocker()
        self.connect("map", self.__on_map)
        self.connect("unmap", self.__on_unmap)
        self.connect("new-page", self.__on_new_page)
        self.connect("create", self.__on_create)
        self.connect("close", self.__on_close)
        # Always connected as we need on_title_changed() update history
        self.connect("title-changed", self.__on_title_changed)

#######################
# PRIVATE             #
#######################
    def __set_snapshot(self, uri):
        """
            Set webpage preview
            @param uri as str
        """
        if uri == self.get_uri() and not self.ephemeral:
            self.get_snapshot(WebKit2.SnapshotRegion.FULL_DOCUMENT,
                              WebKit2.SnapshotOptions.NONE,
                              self.__cancellable,
                              self.__on_snapshot,
                              uri)

    def __reset_js_blocker(self):
        """
            Reset js blocker
        """
        self.__js_dialog_type = None
        self.__js_dialog_message = None

    def __on_new_page(self, webview, uri, window_type, rtime):
        """
            Open a new page, switch to view if show is True
            @param webview as WebView
            @param uri as str
            @param window_type as Gdk.WindowType
            @param rtime as int
        """
        if uri:
            if window_type == Gdk.WindowType.SUBSURFACE:
                if self.ephemeral:
                    webview = self.new_ephemeral(self._window)
                else:
                    webview = self.new(self._window)
                self._window.container.popup_webview(webview, True)
                GLib.idle_add(self.load_uri, uri)
            else:
                new = self._window.container.add_webview(uri,
                                                         window_type,
                                                         self.ephemeral)
                # parent.rtime = child.rtime + 1
                # Used to search for best matching webview
                new.set_rtime(self.rtime - 1)

    def __on_create(self, related, navigation_action):
        """
            Create a new view for action
            @param related as WebView
            @param navigation_action as WebKit2.NavigationAction
            @param force as bool
        """
        webview = self.new_with_related_view(related, self._window)
        self.set_rtime(related.rtime - 1)
        self.connect("ready-to-show",
                     self.__on_ready_to_show,
                     related,
                     navigation_action)
        return webview

    def __on_close(self, webview):
        """
            Close my self
            @param webview as WebView
        """
        if self.get_ancestor(Gtk.Popover) is None:
            self._window.container.pages_manager.try_close_view(self)

    def __on_popup_close(self, webview, related):
        """
            Remove webview from popups
            @param webview as WebView
            @param related as WebView
        """
        related.remove_popup(webview)
        if self._window.container.current.webview == related and\
                not related.popups:
            self._window.toolbar.title.show_indicator(Indicator.NONE)

    def __on_ready_to_show(self, webview, related, navigation_action):
        """
            Add a new webview with related
            @param webview as WebView
            @param related as WebView
            @param navigation_action as WebKit2.NavigationAction
        """
        # Do not block if we get a click on view
        elapsed = time() - related.last_click_time
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
            self.connect("close", self.__on_popup_close, related)
            if related == self._window.container.current.webview:
                self._window.toolbar.title.show_indicator(
                                                        Indicator.POPUPS)
            return
        properties = self.get_window_properties()
        if properties.get_locationbar_visible() and\
                properties.get_toolbar_visible() and\
                not navigation_action.get_modifiers() &\
                Gdk.ModifierType.SHIFT_MASK:
            self._window.container.add_view(webview,
                                            Gdk.WindowType.CHILD)
        else:
            self._window.container.popup_webview(webview, True)

    def __on_save_password(self, webview, user_form_name, user_form_value,
                           pass_form_name, pass_form_value, uri, form_uri):
        """
            Ask user to save password
            @param webview as WebView
            @param user_form_name as str
            @param user_form_value as str
            @param pass_form_name as str
            @param pass_form_value as str
            @param uri as str
        """
        self._window.toolbar.title.show_password(user_form_name,
                                                 user_form_value,
                                                 pass_form_name,
                                                 pass_form_value,
                                                 uri,
                                                 form_uri)

    def __on_script_dialog(self, webview, dialog):
        """
            Show message to user
            @param webview as WebView
            @param dialog as WebKit2.ScriptDialog
        """
        # Here we handle JS flood
        if dialog.get_message() == self.__js_dialog_message and\
                dialog.get_dialog_type() == self.__js_dialog_type:
            self._window.toolbar.title.show_message(
                   _("Eolie is going to close this page because it is broken"))
            self._window.container.pages_manager.close_view(self, False)
            return True

        if not dialog.get_message().startswith("@EOLIE_"):
            self.__js_dialog_type = dialog.get_dialog_type()
            self.__js_dialog_message = dialog.get_message()
            self._window.toolbar.title.show_javascript(dialog)
            GLib.timeout_add(1000, self.__reset_js_blocker)
            return True

    def __on_button_press(self, webview, event):
        """
            Hide Titlebar popover
            @param webview as WebView
            @param event as Gdk.Event
        """
        if self.get_ancestor(Gtk.Popover) is None:
            return self._window.close_popovers()

    def __on_estimated_load_progress(self, webview, value):
        """
            Update progress bar
            @param webview as WebView
            @param value GparamFloat
        """
        if webview == self._window.container.current.webview:
            value = self.get_estimated_load_progress()
            self._window.toolbar.title.progress.set_fraction(value)

    def __on_uri_changed(self, webview, uri):
        """
            Update UI and cancel current snapshot
            @param webview as WebView
            @param uri as GParamString (Do not use)
        """
        self.__cancellable.cancel()
        self.__cancellable.reset()
        # Check needed by WebViewPopover!
        if webview == self._window.container.current.webview and uri:
            self._window.toolbar.title.set_uri(uri)

    def __on_title_changed(self, webview, title):
        """
            Update title
            @param webview as WebView
            @param title as str
        """
        # Check needed by WebViewPopover!
        if webview == self._window.container.current.webview:
            self._window.toolbar.title.set_title(title)
            self._window.container.sites_manager.update_label(
                                                self._window.container.current)
        # We only update history on title changed, should be enough
        if self.error is None:
            uri = self.get_uri()
            parsed = urlparse(uri)
            if parsed.scheme in ["http", "https"] and\
                    not self.ephemeral:
                mtime = round(time(), 2)
                El().history.thread_lock.acquire()
                history_id = El().history.add(title, uri, mtime)
                El().history.set_page_state(uri, mtime)
                El().history.thread_lock.release()
                if El().sync_worker is not None:
                    El().sync_worker.push_history([history_id])

    def __on_enter_fullscreen(self, webview):
        """
            Hide sidebar (conflict with fs)
            @param webview as WebView
        """
        self._window.container.sites_manager.hide()

    def __on_leave_fullscreen(self, webview):
        """
            Show sidebar (conflict with fs)
            @param webview as WebView
        """
        self._window.container.sites_manager.show()

    def __on_insecure_content_detected(self, webview, event):
        """
            @param webview as WebView
            @param event as WebKit2.InsecureContentEvent
        """
        self._window.toolbar.title.set_insecure_content()

    def __on_load_changed(self, webview, event):
        """
            Update sidebar/urlbar
            @param webview as WebView
            @param event as WebKit2.LoadEvent
        """
        # Check needed by WebViewPopover!
        if webview != self._window.container.current.webview:
            return
        self._window.toolbar.title.update_load_indicator(webview)
        uri = self.get_uri()
        parsed = urlparse(uri)
        wanted_scheme = parsed.scheme in ["http", "https", "file"]
        if event == WebKit2.LoadEvent.STARTED:
            self._window.container.current.find_widget.set_search_mode(False)
            self._window.toolbar.title.set_title(uri)
            if wanted_scheme:
                self._window.toolbar.title.show_spinner(True)
            else:
                # Give focus to url bar
                self._window.toolbar.title.start_search()
            self._window.toolbar.title.show_indicator(Indicator.NONE)
            # Turn off reading mode if needed
            if self._window.container.current.reading:
                self._window.container.current.switch_read_mode()
            self._window.toolbar.title.progress.show()
        elif event == WebKit2.LoadEvent.COMMITTED:
            self._window.toolbar.title.set_title(uri)
        elif event == WebKit2.LoadEvent.FINISHED:
            self._window.toolbar.title.show_spinner(False)
            # Give focus to webview
            if wanted_scheme:
                GLib.idle_add(self.grab_focus)
            # Hide progress delayed to show result to user
            GLib.timeout_add(500, self._window.toolbar.title.progress.hide)
            GLib.timeout_add(3000, self.__set_snapshot, uri)

    def __on_back_forward_list_changed(self, bf_list, added, removed, webview):
        """
            Update actions
            @param bf_list as WebKit2.BackForwardList
            @param added as WebKit2.BackForwardListItem
            @param removed as WebKit2.BackForwardListItem
            @param webview as WebView
        """
        self._window.toolbar.actions.set_actions(webview)

    def __on_resource_load_started(self, webview, resource, request):
        """
            Listen to off loading events
            @param webview as WebView
            @param resource WebKit2.WebResource
            @param request as WebKit2.URIRequest
        """
        # Javascript execution happened
        if not self.is_loading():
            if self.__js_timeout_id is not None:
                GLib.source_remove(self.__js_timeout_id)
            self.__js_timeout_id = GLib.timeout_add(500,
                                                    self.__on_js_timeout,
                                                    webview)

    def __on_js_timeout(self, webview):
        """
            Tell webpage to update credentials
            @param webview as WebView
        """
        self.__js_timeout_id = None
        page_id = self.get_page_id()
        El().helper.call("SetCredentials",
                         GLib.Variant("(i)", (page_id,)),
                         None,
                         page_id)

    def __on_snapshot(self, webview, result, uri):
        """
            Set snapshot on main image
            @param webview as WebView
            @param result as Gio.AsyncResult
            @param uri as str
        """
        ART_RATIO = 1.5  # ArtSize.START_WIDTH / ArtSize.START_HEIGHT
        # Do not cache snapshot on error
        if self.error is not None or uri != self.get_uri():
            return
        try:
            snapshot = self.get_snapshot_finish(result)
            # Set start image scale factor
            ratio = snapshot.get_width() / snapshot.get_height()
            if ratio > ART_RATIO:
                factor = ArtSize.START_HEIGHT / snapshot.get_height()
            else:
                factor = ArtSize.START_WIDTH / snapshot.get_width()
            surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                         ArtSize.START_WIDTH,
                                         ArtSize.START_HEIGHT)
            context = cairo.Context(surface)
            context.scale(factor, factor)
            context.set_source_surface(snapshot, factor, 0)
            context.paint()
            # Cache result
            # We also cache initial URI
            uris = [self.get_uri()]
            parsed = urlparse(uri)
            # Caching this will break populars navigation
            # as we are looking for subpage snapshots
            if parsed.scheme == "populars":
                return
            initial_parsed = urlparse(self.initial_uri)
            if parsed.netloc == initial_parsed.netloc and\
                    self.initial_uri not in uris:
                uris.append(self.initial_uri)
            for uri in uris:
                if not El().art.exists(uri, "start"):
                    El().art.save_artwork(uri, surface, "start")
        except Exception as e:
            print("WebViewSignalsHandler::__on_snapshot():", e)

    def __on_map(self, webview):
        """
            Connect all signals
            @param webview as WebView
        """
        if self.__signals_connected:
            return
        self.__signals_connected = True
        self._window.update(webview)
        self.connect("notify::estimated-load-progress",
                     self.__on_estimated_load_progress)
        self.connect("resource-load-started",
                     self.__on_resource_load_started)
        self.connect("load-changed", self.__on_load_changed)
        self.connect("button-press-event", self.__on_button_press)
        self.connect("uri-changed", self.__on_uri_changed)
        self.connect("enter-fullscreen", self.__on_enter_fullscreen)
        self.connect("leave-fullscreen", self.__on_leave_fullscreen)
        self.connect("save-password", self.__on_save_password)
        self.connect("script-dialog", self.__on_script_dialog)
        self.connect("insecure-content-detected",
                     self.__on_insecure_content_detected)
        self.get_back_forward_list().connect(
                             "changed",
                             self.__on_back_forward_list_changed,
                             webview)

    def __on_unmap(self, webview):
        """
            Disconnect all signals
            @param webview as WebView
        """
        if not self.__signals_connected:
            return
        self.__signals_connected = False
        self.disconnect_by_func(self.__on_estimated_load_progress)
        self.disconnect_by_func(self.__on_resource_load_started)
        self.disconnect_by_func(self.__on_load_changed)
        self.disconnect_by_func(self.__on_button_press)
        self.disconnect_by_func(self.__on_uri_changed)
        self.disconnect_by_func(self.__on_enter_fullscreen)
        self.disconnect_by_func(self.__on_leave_fullscreen)
        self.disconnect_by_func(self.__on_save_password)
        self.disconnect_by_func(self.__on_script_dialog)
        self.disconnect_by_func(self.__on_insecure_content_detected)
        self.get_back_forward_list().disconnect_by_func(
                                         self.__on_back_forward_list_changed)
