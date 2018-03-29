# Copyright (c) 2017-2018 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from gi.repository import Gtk, Gdk, Gio, WebKit2, GObject

from gettext import gettext as _
from urllib.parse import urlparse
from time import time

from eolie.define import App
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
        "shown": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "title-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "uri-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "favicon-changed": (GObject.SignalFlags.RUN_FIRST, None,
                            (GObject.TYPE_PYOBJECT,)),
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
        self.reset_last_click_event()
        self.__cancellable = Gio.Cancellable()
        self.connect("map", self._on_map)
        self.connect("unmap", self._on_unmap)
        self.connect("uri-changed", self.__on_uri_changed)
        self.connect("title-changed", self.__on_title_changed)
        self.connect("scroll-event", self.__on_scroll_event)
        self.connect("run-file-chooser", self.__on_run_file_chooser)

    def reset_last_click_event(self):
        """
            Reset last click event
        """
        self._last_click_event_x = 0
        self._last_click_event_y = 0
        self._last_click_time = 0

#######################
# PROTECTED           #
#######################
    def _on_button_press_event(self, webview, event):
        """
            Hide Titlebar popover
            @param webview as WebView
            @param event as Gdk.Event
        """
        self._last_click_event_x = event.x
        self._last_click_event_y = event.y
        self._last_click_time = time()
        if event.button == 8:
            self.go_back()
            return True
        elif event.button == 9:
            self.go_forward()
            return True
        elif self.get_ancestor(Gtk.Popover) is None:
            return self._window.close_popovers()

    def _on_map(self, webview):
        """
            Connect all signals
            @param webview as WebView
        """
        # We are offscreen
        if self._window != self.get_toplevel():
            return
        # URI set but not loaded
        if webview.get_uri() != webview.uri:
            webview.load_uri(webview.uri)
        self._shown = True
        self.emit("shown")
        self.set_atime(int(time()))
        if not webview.view.popover:
            self._window.update(webview)
        self.connect("button-press-event", self._on_button_press_event)
        self.connect("enter-fullscreen", self.__on_enter_fullscreen)
        self.connect("leave-fullscreen", self.__on_leave_fullscreen)
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
        # We are offscreen or already unmapped (happens with Gtk.Stack)
        if self._window != self.get_toplevel() or not self.get_mapped():
            return
        self.disconnect_by_func(self._on_button_press_event)
        self.disconnect_by_func(self.__on_enter_fullscreen)
        self.disconnect_by_func(self.__on_leave_fullscreen)
        self.disconnect_by_func(self.__on_insecure_content_detected)
        WebViewJsSignals._on_unmap(self, webview)
        WebViewDBusSignals._on_unmap(self, webview)
        WebViewLoadSignals._on_unmap(self, webview)

#######################
# PRIVATE             #
#######################
    def __on_run_file_chooser(self, webview, request):
        """
            Run own file chooser
            @param webview as WebView
            @param request as WebKit2.FileChooserRequest
        """
        dialog = Gtk.FileChooserNative.new(_("Select files to upload"),
                                           self._window,
                                           Gtk.FileChooserAction.OPEN,
                                           _("Open"),
                                           _("Cancel"))
        dialog.set_select_multiple(request.get_select_multiple())
        chooser_uri = App().websettings.get_chooser_uri(webview.uri)
        if chooser_uri is not None:
            dialog.set_current_folder_uri(chooser_uri)
        response = dialog.run()
        if response in [Gtk.ResponseType.DELETE_EVENT,
                        Gtk.ResponseType.CANCEL]:
            request.cancel()
        else:
            request.select_files(dialog.get_filenames())
            App().websettings.set_chooser_uri(dialog.get_current_folder_uri(),
                                              webview.uri)
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

    def __on_uri_changed(self, webview, uri):
        """
            Update UI and cancel current snapshot
            @param webview as WebView
            @param uri as str
        """
        self.__cancellable.cancel()
        self.__cancellable.reset()

    def __on_title_changed(self, webview, title):
        """
            Append title to history
            @param webview as WebView
            @param title as str
        """
        parsed = urlparse(webview.uri)
        if self._error or\
                webview.ephemeral or\
                parsed.scheme not in ["http", "https"]:
            return
        mtime = round(time(), 2)
        history_id = App().history.add(title, webview.uri, mtime)
        App().history.set_page_state(webview.uri, mtime)
        if App().sync_worker is not None:
            App().sync_worker.push_history(history_id)

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
        if App().settings.get_value("show-sidebar"):
            self._window.container.sites_manager.show()

    def __on_insecure_content_detected(self, webview, event):
        """
            @param webview as WebView
            @param event as WebKit2.InsecureContentEvent
        """
        self._window.toolbar.title.set_insecure_content()
