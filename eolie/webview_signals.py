# Copyright (c) 2017-2019 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from gi.repository import Gtk, Gdk, Gio, WebKit2, GObject, GLib

from gettext import gettext as _
from urllib.parse import urlparse
from time import time

from eolie.define import App
from eolie.webview_signals_menu import WebViewMenuSignals
from eolie.webview_signals_js import WebViewJsSignals
from eolie.webview_signals_dbus import WebViewDBusSignals


class WebViewSignals(WebViewMenuSignals, WebViewJsSignals,
                     WebViewDBusSignals):
    """
        Handle webview signals
    """

    gsignals = {
        "readability-content": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "shown": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "title-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "uri-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "snapshot-changed": (GObject.SignalFlags.RUN_FIRST, None,
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
        self.__title_changed_timeout_id = None
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
            return self.window.close_popovers()

    def _on_map(self, webview):
        """
            Connect all signals
            @param webview as WebView
        """
        # We are offscreen
        if self.window != self.get_toplevel():
            return
        # URI set but not loaded
        # Webviews with a related webview have a None URI
        if self.get_uri() is None and\
                self.uri is not None and\
                self._related_view is None:
            self.load_uri(self.uri)
        self._shown = True
        self.emit("shown")
        self.set_atime(int(time()))
        self.connect("button-press-event", self._on_button_press_event)
        self.connect("enter-fullscreen", self.__on_enter_fullscreen)
        self.connect("leave-fullscreen", self.__on_leave_fullscreen)
        self.connect("insecure-content-detected",
                     self.__on_insecure_content_detected)
        WebViewDBusSignals._on_map(self, webview)

    def _on_unmap(self, webview):
        """
            Disconnect all signals
            @param webview as WebView
        """
        # We are offscreen
        if self.window != self.get_toplevel():
            return
        self.disconnect_by_func(self._on_button_press_event)
        self.disconnect_by_func(self.__on_enter_fullscreen)
        self.disconnect_by_func(self.__on_leave_fullscreen)
        self.disconnect_by_func(self.__on_insecure_content_detected)
        WebViewDBusSignals._on_unmap(self, webview)

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
                                           self.window,
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
        def title_changed_timeout():
            """
                We need this to update history as soon title is available
            """
            self.__title_changed_timeout_id = None
            self.__on_title_changed(webview, webview.title)
        if self.__title_changed_timeout_id is not None:
            GLib.source_remove(self.__title_changed_timeout_id)
        self.__title_changed_timeout_id = GLib.timeout_add(
            2000, title_changed_timeout)
        self.__cancellable.cancel()
        self.__cancellable = Gio.Cancellable()
        self._readable = False

    def __on_title_changed(self, webview, title):
        """
            Append title to history
            @param webview as WebView
            @param title as str
        """
        if self.__title_changed_timeout_id is not None:
            GLib.source_remove(self.__title_changed_timeout_id)
        self.__title_changed_timeout_id = None
        parsed = urlparse(webview.uri)
        if self.error or\
                webview.is_ephemeral or\
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
        self.window.container.sites_manager.hide()

    def __on_leave_fullscreen(self, webview):
        """
            Show sidebar (conflict with fs)
            @param webview as WebView
        """
        if App().settings.get_value("show-sidebar"):
            self.window.container.sites_manager.show()

    def __on_insecure_content_detected(self, webview, event):
        """
            @param webview as WebView
            @param event as WebKit2.InsecureContentEvent
        """
        self.window.toolbar.title.set_insecure_content()
