# Copyright (c) 2017-2020 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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


class WebViewSignals(WebViewMenuSignals, WebViewJsSignals):
    """
        Handle webview signals
    """

    gsignals = {
        "readability-content": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "readability-status": (GObject.SignalFlags.RUN_FIRST, None, (bool,)),
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
        self.reset_last_click_event()
        self.__cancellable = Gio.Cancellable()
        self.__uri = ""
        self.__title = ""
        self.connect("notify::title", self.__on_title_changed)
        self.connect("notify::uri", self.__on_uri_changed)
        self.connect("scroll-event", self.__on_scroll_event)
        self.connect("run-file-chooser", self.__on_run_file_chooser)
        self.connect("button-press-event", self.__on_button_press_event)

    def reset_last_click_event(self):
        """
            Reset last click event
        """
        self._last_click_event_x = 0
        self._last_click_event_y = 0
        self._last_click_time = 0

    def set_title(self, title):
        """
            Set title
            @param title as str
        """
        self.__title = title
        self.emit("title-changed", title)

    def set_uri(self, uri):
        """
            Set delayed uri
            @param uri as str
        """
        self.__uri = uri.rstrip("/")
        self.emit("uri-changed", uri)

    @property
    def uri(self):
        """
            Get webview uri
            @return str
        """
        return self.__uri

    @property
    def title(self):
        """
            Get webview title
            @return str
        """
        return self.__title

#######################
# PRIVATE             #
#######################
    def __on_button_press_event(self, webview, event):
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
        chooser_uri = App().websettings.get("chooser_uri", webview.uri)
        if chooser_uri is not None:
            dialog.set_current_folder_uri(chooser_uri)
        response = dialog.run()
        if response in [Gtk.ResponseType.DELETE_EVENT,
                        Gtk.ResponseType.CANCEL]:
            request.cancel()
        else:
            request.select_files(dialog.get_filenames())
            App().websettings.set("chooser_uri",
                                  webview.uri,
                                  dialog.get_current_folder_uri())
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

    def __on_uri_changed(self, webview, param):
        """
            Handle JS updates
            @param webview as WebKit2.WebView
            @param param as GObject.ParamSpec
        """
        uri = webview.get_property(param.name).rstrip("/")
        if not uri.startswith("javascript:") and not self.error:
            self.__uri = uri
            self.emit("uri-changed", uri)
            self._set_user_agent(uri)

    def __on_title_changed(self, webview, param):
        """
            We launch Readability.js at page loading finished.
            @param webview as WebKit2.WebView
            @param param as GObject.ParamSpec
        """
        self.__title = webview.get_property(param.name)
        self.emit("title-changed", self.__title)
        if self.__title:
            parsed = urlparse(self.uri)
            if self.error or\
                    webview.is_ephemeral or\
                    parsed.scheme not in ["http", "https"]:
                return
            mtime = round(time(), 2)
            history_id = App().history.add(self.__title, self.__uri, mtime)
            App().history.set_page_state(self.__uri, mtime)
            if App().sync_worker is not None:
                App().sync_worker.push_history(history_id)
