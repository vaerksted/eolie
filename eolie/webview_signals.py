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

from gi.repository import Gtk, Gdk, Gio, GLib, WebKit2, GObject

from gettext import gettext as _
from urllib.parse import urlparse
from time import time

from eolie.define import El
from eolie.webview_signals_menu import WebViewMenuSignals
from eolie.webview_signals_js import WebViewJsSignals
from eolie.webview_signals_dbus import WebViewDBusSignals
from eolie.webview_signals_load import WebViewLoadSignals


class WebViewSignals(WebViewMenuSignals, WebViewJsSignals,
                     WebViewDBusSignals, WebViewLoadSignals):
    """
        Handle webview signals
    """

    gsignals = {
        "readable": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "title-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "uri-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "new-page":  (GObject.SignalFlags.RUN_FIRST, None, (str, int, int)),
        "save-password": (GObject.SignalFlags.RUN_FIRST, None, (str,
                                                                str,
                                                                str,
                                                                str,
                                                                str,
                                                                str)),
    }

    for signal in gsignals:
        args = gsignals[signal]
        GObject.signal_new(signal, WebKit2.WebView,
                           args[0], args[1], args[2])

    def __init__(self):
        """
            Init handler
            @param webview as WebView
        """
        WebViewMenuSignals.__init__(self)
        WebViewJsSignals.__init__(self)
        WebViewDBusSignals.__init__(self)
        WebViewLoadSignals.__init__(self)
        self._cancellable = Gio.Cancellable()
        self.connect("map", self._on_map)
        self.connect("unmap", self._on_unmap)
        self.connect("new-page", self.__on_new_page)
        self.connect("uri-changed", self.__on_uri_changed)
        self.connect("title-changed", self.__on_title_changed)
        self.connect("scroll-event", self.__on_scroll_event)
        self.connect("run-file-chooser", self.__on_run_file_chooser)

#######################
# PROTECTED           #
#######################
    def _on_button_press_event(self, webview, event):
        """
            Hide Titlebar popover
            @param webview as WebView
            @param event as Gdk.Event
        """
        WebViewDBusSignals._on_button_press_event(self, webview, event)
        if self.get_ancestor(Gtk.Popover) is None:
            return self._window.close_popovers()

    def _on_map(self, webview):
        """
            Connect all signals
            @param webview as WebView
        """
        # We are offscreen
        if self._window != self.get_toplevel():
            return
        self._window.update(webview)
        self.connect("button-press-event", self._on_button_press_event)
        self.connect("enter-fullscreen", self.__on_enter_fullscreen)
        self.connect("leave-fullscreen", self.__on_leave_fullscreen)
        self.connect("save-password", self.__on_save_password)
        self.connect("insecure-content-detected",
                     self.__on_insecure_content_detected)
        WebViewJsSignals._on_map(self, webview)
        WebViewDBusSignals._on_map(self, webview)
        WebViewLoadSignals._on_map(self, webview)

    def _on_unmap(self, webview):
        """
            Disconnect all signals
            @param webview as WebView
        """
        # We are offscreen
        if self._window != self.get_toplevel():
            return
        self.disconnect_by_func(self._on_button_press_event)
        self.disconnect_by_func(self.__on_enter_fullscreen)
        self.disconnect_by_func(self.__on_leave_fullscreen)
        self.disconnect_by_func(self.__on_save_password)
        self.disconnect_by_func(self.__on_insecure_content_detected)
        WebViewJsSignals._on_unmap(self, webview)
        WebViewDBusSignals._on_unmap(self, webview)
        WebViewLoadSignals._on_map(self, webview)

#######################
# PRIVATE             #
#######################
    def __on_run_file_chooser(self, webview, request):
        """
            Run own file chooser
            @param webview as WebView
            @param request as WebKit2.FileChooserRequest
        """
        uri = webview.get_uri()
        dialog = Gtk.FileChooserNative.new(_("Select files to upload"),
                                           self._window,
                                           Gtk.FileChooserAction.OPEN,
                                           _("Open"),
                                           _("Cancel"))
        dialog.set_select_multiple(request.get_select_multiple())
        chooser_uri = El().websettings.get_chooser_uri(uri)
        if chooser_uri is not None:
            dialog.set_current_folder_uri(chooser_uri)
        response = dialog.run()
        if response in [Gtk.ResponseType.DELETE_EVENT,
                        Gtk.ResponseType.CANCEL]:
            request.cancel()
        else:
            request.select_files(dialog.get_filenames())
            El().websettings.set_chooser_uri(dialog.get_current_folder_uri(),
                                             uri)
        return True

    def __on_scroll_event(self, webview, event):
        """
            Adapt scroll speed to device
            @param webview as WebView
            @param event as Gdk.EventScroll
        """
        source = event.get_source_device().get_source()
        if event.state & Gdk.ModifierType.CONTROL_MASK:
            if source == Gdk.InputSource.MOUSE:
                if event.delta_y < 0.5:
                    webview.zoom_in()
                elif event.delta_y > 0.5:
                    webview.zoom_out()
            else:
                if event.delta_y > 0.5:
                    webview.zoom_in()
                elif event.delta_y < - 0.5:
                    webview.zoom_out()
            return True
        elif source == Gdk.InputSource.MOUSE:
            event.delta_x *= 2
            event.delta_y *= 2

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

    def __on_uri_changed(self, webview, uri):
        """
            Update UI and cancel current snapshot
            @param webview as WebView
            @param uri as GParamString (Do not use)
        """
        self._cancellable.cancel()
        self._cancellable.reset()
        if webview.get_mapped():
            self._window.toolbar.title.set_uri(uri)

    def __on_title_changed(self, webview, title):
        """
            Update title
            @param webview as WebView
            @param title as str
        """
        if webview.get_mapped():
            self._window.toolbar.title.set_title(title)
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
