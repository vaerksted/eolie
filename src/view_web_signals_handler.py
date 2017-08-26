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

from gi.repository import Gtk, Gdk, GLib, Pango, WebKit2

from urllib.parse import urlparse
from time import time
import cairo

from eolie.view_web import WebView
from eolie.define import El, Indicator, ArtSize


class UriLabel(Gtk.EventBox):
    """
        Small label trying to not be under mouse pointer
    """

    def __init__(self):
        """
            Init label
        """
        Gtk.EventBox.__init__(self)
        self.__label = Gtk.Label()
        self.__label.set_ellipsize(Pango.EllipsizeMode.END)
        self.__label.get_style_context().add_class("urilabel")
        self.__label.show()
        self.add(self.__label)
        self.connect("enter-notify-event", self.__on_enter_notify)

    def set_text(self, text):
        """
            Set label text
            @param text as str
        """
        if text == self.__label.get_text():
            return
        self.set_property("halign", Gtk.Align.END)
        self.set_property("valign", Gtk.Align.END)
        self.__label.get_style_context().add_class("bottom-right")
        self.__label.get_style_context().remove_class("bottom-left")
        self.__label.get_style_context().remove_class("top-left")
        self.__label.set_text(text)

#######################
# PRIVATE             #
#######################
    def __on_enter_notify(self, widget, event):
        """
            Try to go away from mouse cursor
            @param widget as Gtk.Widget
            @param event as Gdk.Event
        """
        GLib.idle_add(self.hide)
        # Move label at the right
        if self.get_property("halign") == Gtk.Align.END:
            self.set_property("halign", Gtk.Align.START)
            self.__label.get_style_context().add_class("bottom-left")
            self.__label.get_style_context().remove_class("bottom-right")
            self.__label.get_style_context().remove_class("top-left")
        # Move label at top
        else:
            self.set_property("halign", Gtk.Align.END)
            self.set_property("valign", Gtk.Align.END)
            self.__label.get_style_context().add_class("top-left")
            self.__label.get_style_context().remove_class("bottom-left")
            self.__label.get_style_context().remove_class("bottom-right")
        GLib.idle_add(self.show)


class WebViewSignalsHandler:
    """
        Webview signals handler, should be herited by a View
    """

    def __init__(self, webview):
        """
            Init handler
            @param webview as WebView
        """
        self.__uri_label = UriLabel()
        self.add_overlay(self.__uri_label)
        self.__js_timeout_id = None
        self.__signals_connected = False
        webview.connect("map", self.__on_webview_map)
        webview.connect("unmap", self.__on_webview_unmap)
        webview.connect("new-page", self.__on_new_page)
        webview.connect("create", self.__on_create)
        webview.connect("close", self.__on_close)
        webview.connect("title-changed", self.__on_title_changed)

#######################
# PRIVATE             #
#######################
    def __set_snapshot(self, uri):
        """
            Set webpage preview
            @param uri as str
        """
        if uri == self.webview.get_uri() and not self.webview.ephemeral:
            self.webview.get_snapshot(WebKit2.SnapshotRegion.FULL_DOCUMENT,
                                      WebKit2.SnapshotOptions.NONE,
                                      None,
                                      self.__on_snapshot,
                                      uri)

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
                    webview = WebView.new_ephemeral(self._window)
                else:
                    webview = WebView.new(self._window)
                self._window.container.popup_webview(webview, True)
                GLib.idle_add(webview.load_uri, uri)
            else:
                self._window.container.add_webview(uri,
                                                   window_type,
                                                   webview.ephemeral,
                                                   self)

    def __on_create(self, related, navigation_action):
        """
            Create a new view for action
            @param related as WebView
            @param navigation_action as WebKit2.NavigationAction
            @param force as bool
        """
        webview = WebView.new_with_related_view(related, self._window)
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
        if webview.get_ancestor(Gtk.Popover) is None:
            self._window.container.pages_manager.close_view(self)

    def __on_ready_to_show(self, webview, related, navigation_action):
        """
            Add a new webview with related
            @param webview as WebView
            @param related as WebView
            @param navigation_action as WebKit2.NavigationAction
        """
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
            if related == self._window.container.current.webview:
                self._window.toolbar.title.show_indicator(
                                                        Indicator.POPUPS)
            return
        # Should not be an issue to not show page with None URI
        if webview.get_uri() is None:
            return
        properties = webview.get_window_properties()
        if properties.get_locationbar_visible() and\
                properties.get_toolbar_visible():
            self._window.container.add_view(webview,
                                            None,
                                            Gdk.WindowType.CHILD)
        else:
            self._window.container.popup_webview(webview, True)

    def __on_readable(self, webview):
        """
            Show readable button in titlebar
            @param webview as WebView
        """
        self._window.toolbar.title.show_readable_button(True)

    def __on_save_password(self, webview, username, userform,
                           password, passform, uri, form_uri):
        """
            Ask user to save password
            @param webview as WebView
            @param username as str
            @param userform as str
            @param password as str
            @param passform as str
            @param uri as str
        """
        self._window.toolbar.title.show_password(username, userform,
                                                 password, passform,
                                                 uri,
                                                 form_uri)

    def __on_script_dialog(self, webview, dialog):
        """
            Show message to user
            @param webview as WebView
            @param dialog as WebKit2.ScriptDialog
        """
        if not dialog.get_message().startswith("@&$%ù²"):
            self._window.toolbar.title.show_javascript(dialog)
            return True

    def __on_button_press(self, webview, event):
        """
            Hide Titlebar popover
            @param webview as WebView
            @param event as Gdk.Event
        """
        if webview.get_ancestor(Gtk.Popover) is None:
            return self._window.close_popovers()

    def __on_estimated_load_progress(self, webview, value):
        """
            Update progress bar
            @param webview as WebView
            @param value GparamFloat
        """
        value = webview.get_estimated_load_progress()
        self._window.toolbar.title.progress.set_fraction(value)

    def __on_uri_changed(self, webview, uri):
        """
            Update uri
            @param webview as WebView
            @param uri as GParamString (Do not use)
        """
        if uri:
            self._window.toolbar.title.set_uri(uri)
            if not webview.is_loading():
                self._window.toolbar.title.show_readable_button(
                                            webview.readable_content != "")

    def __on_title_changed(self, webview, title):
        """
            Update title
            @param webview as WebView
            @param title as str
        """
        if webview == self._window.container.current.webview:
            self._window.toolbar.title.set_title(title)
        # We only update history on title changed, should be enough
        if webview.error is None:
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
                    El().sync_worker.push_history([history_id])

    def __on_enter_fullscreen(self, webview):
        """
            Hide sidebar (conflict with fs)
            @param webview as WebView
        """
        self._window.container.pages_manager.hide()

    def __on_leave_fullscreen(self, webview):
        """
            Show sidebar (conflict with fs)
            @param webview as WebView
        """
        self._window.container.pages_manager.show()

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
        self._window.toolbar.title.update_load_indicator(webview)
        uri = webview.get_uri()
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
            if self.reading:
                self.switch_read_mode()
            self._window.toolbar.title.progress.show()
        elif event == WebKit2.LoadEvent.COMMITTED:
            self._window.toolbar.title.set_title(uri)
        elif event == WebKit2.LoadEvent.FINISHED:
            self._window.toolbar.title.show_spinner(False)
            # Give focus to webview
            if wanted_scheme:
                GLib.idle_add(webview.grab_focus)
            # Hide progress
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

    def __on_mouse_target_changed(self, webview, hit, modifiers):
        """
            Show uri in title bar
            @param webview as WebView
            @param hit as WebKit2.HitTestResult
            @param modifier as Gdk.ModifierType
        """
        if hit.context_is_link():
            self.__uri_label.set_text(hit.get_link_uri())
            self.__uri_label.show()
        else:
            self.__uri_label.hide()

    def __on_resource_load_started(self, webview, resource, request):
        """
            Listen to off loading events
            @param webview as WebView
            @param resource WebKit2.WebResource
            @param request as WebKit2.URIRequest
        """
        # Javascript execution happened
        if not webview.is_loading():
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
        page_id = webview.get_page_id()
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
        # Do not cache snapshot on error
        if webview.error is not None or uri != self.webview.get_uri():
            return
        try:
            snapshot = webview.get_snapshot_finish(result)
            # We also cache original URI
            uris = [webview.get_uri()]
            parsed = urlparse(uri)
            initial_parsed = urlparse(webview.initial_uri)
            if parsed.netloc == initial_parsed.netloc and\
                    webview.initial_uri not in uris:
                uris.append(webview.initial_uri)
            # Set start image scale factor
            factor = ArtSize.START_WIDTH / snapshot.get_width()
            surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                         ArtSize.START_WIDTH,
                                         ArtSize.START_HEIGHT)
            context = cairo.Context(surface)
            context.scale(factor, factor)
            context.set_source_surface(snapshot, factor, 0)
            context.paint()
            for uri in uris:
                if not El().art.exists(uri, "start"):
                    El().art.save_artwork(uri, surface, "start")
            del surface
            del snapshot
        except Exception as e:
            print("WebViewSignalsHandler::__on_snapshot():", e)

    def __on_webview_map(self, webview):
        """
            Connect all signals
            @param webview as WebView
        """
        if self.__signals_connected:
            return
        self.__signals_connected = True
        self._window.update(webview)
        webview.connect("mouse-target-changed",
                        self.__on_mouse_target_changed)
        webview.connect("notify::estimated-load-progress",
                        self.__on_estimated_load_progress)
        webview.connect("resource-load-started",
                        self.__on_resource_load_started)
        webview.connect("load-changed", self.__on_load_changed)
        webview.connect("button-press-event", self.__on_button_press)
        webview.connect("uri-changed", self.__on_uri_changed)
        webview.connect("enter-fullscreen", self.__on_enter_fullscreen)
        webview.connect("leave-fullscreen", self.__on_leave_fullscreen)
        webview.connect("readable", self.__on_readable)
        webview.connect("save-password", self.__on_save_password)
        webview.connect("script-dialog", self.__on_script_dialog)
        webview.connect("insecure-content-detected",
                        self.__on_insecure_content_detected)
        webview.get_back_forward_list().connect(
                             "changed",
                             self.__on_back_forward_list_changed,
                             webview)

    def __on_webview_unmap(self, webview):
        """
            Disconnect all signals
            @param webview as WebView
        """
        if not self.__signals_connected:
            return
        self.__signals_connected = False
        webview.disconnect_by_func(self.__on_mouse_target_changed)
        webview.disconnect_by_func(self.__on_estimated_load_progress)
        webview.disconnect_by_func(self.__on_resource_load_started)
        webview.disconnect_by_func(self.__on_load_changed)
        webview.disconnect_by_func(self.__on_button_press)
        webview.disconnect_by_func(self.__on_uri_changed)
        webview.disconnect_by_func(self.__on_enter_fullscreen)
        webview.disconnect_by_func(self.__on_leave_fullscreen)
        webview.disconnect_by_func(self.__on_readable)
        webview.disconnect_by_func(self.__on_save_password)
        webview.disconnect_by_func(self.__on_script_dialog)
        webview.disconnect_by_func(self.__on_insecure_content_detected)
        webview.get_back_forward_list().disconnect_by_func(
                                         self.__on_back_forward_list_changed)
