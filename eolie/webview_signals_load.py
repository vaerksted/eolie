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

from gi.repository import GLib, Gio, WebKit2

from urllib.parse import urlparse

from eolie.define import Indicator, App


class WebViewLoadSignals:
    """
        Handle webview load signal
    """

    def __init__(self):
        """
            Init class
        """
        self.__current_event = WebKit2.LoadEvent.FINISHED
        self.__popups = []

    def add_popup(self, webview):
        """
            Add webview to popups
            @webview as WebView
        """
        self.__popups.append(webview)

    def remove_popup(self, webview):
        """
            Remove webview to popups
            @webview as WebView
        """
        if webview in self.__popups:
            self.__popups.remove(webview)

    @property
    def popups(self):
        """
            Get popups
            @return [WebView]
        """
        return self.__popups

    @property
    def current_event(self):
        """
            Get current event
            @return WebKit2.LoadEvent
        """
        return self.__current_event

#######################
# PROTECTED           #
#######################
    def _on_map(self, webview):
        """
            Connect all signals
            @param webview as WebView
        """
        if not self.view.popover:
            self.connect("title-changed", self.__on_title_changed)
            self.connect("uri-changed", self.__on_uri_changed)
            self.connect("notify::estimated-load-progress",
                         self.__on_estimated_load_progress)
            self.get_back_forward_list().connect(
                "changed",
                self.__on_back_forward_list_changed,
                webview)

    def _on_unmap(self, webview):
        """
            Disconnect all signals
            @param webview as WebView
        """
        if not self.view.popover:
            self.disconnect_by_func(self.__on_title_changed)
            self.disconnect_by_func(self.__on_uri_changed)
            self.disconnect_by_func(self.__on_estimated_load_progress)
            self._window.toolbar.title.progress.set_fraction(0)
            self.get_back_forward_list().disconnect_by_func(
                self.__on_back_forward_list_changed)

    def _on_load_changed(self, webview, event):
        """
            Update sidebar/urlbar
            @param webview as WebView
            @param event as WebKit2.LoadEvent
        """
        self.__current_event = event
        # Load event may happen before a related webview is ready-to-show and
        # so before a view is associated
        if self.view is not None and not self.view.popover:
            if event == WebKit2.LoadEvent.STARTED:
                # Destroy current popups
                for popup in self.__popups:
                    popup.destroy()
                self.__popups = []
            elif event == WebKit2.LoadEvent.FINISHED:
                js1 = Gio.File.new_for_uri(
                    "resource:///org/gnome/Eolie/Readability.js")
                js2 = Gio.File.new_for_uri(
                    "resource:///org/gnome/Eolie/Readability_check.js")
                (status, content1, tags) = js1.load_contents()
                (status, content2, tags) = js2.load_contents()
                script = content1.decode("utf-8") + content2.decode("utf-8")
                self.run_javascript(script, None, None)
            if webview.get_mapped() and not webview.view.popover:
                self.__update_toolbars(event)

#######################
# PRIVATE             #
#######################
    def __update_toolbars(self, event):
        """
            Update toolbar content with on self
            @param event as WebKit2.LoadEvent
        """
        parsed = urlparse(self.uri)
        wanted_scheme = parsed.scheme in ["http", "https", "file"]
        if event == WebKit2.LoadEvent.STARTED:
            self._window.container.current.find_widget.set_search_mode(False)
            self._window.toolbar.title.set_title(self.uri)
            self._window.toolbar.title.show_readable_button(False)
            if wanted_scheme:
                self._window.toolbar.title.set_loading(True)
            else:
                # Give focus to url bar
                self._window.toolbar.title.start_search()
            self._window.toolbar.title.show_indicator(Indicator.NONE)
            # Turn off reading mode
            self._window.container.current.stop_reading()
            self._window.toolbar.title.progress.show()
        elif event == WebKit2.LoadEvent.COMMITTED:
            self._window.toolbar.title.set_title(self.uri)
        elif event == WebKit2.LoadEvent.FINISHED:
            self._window.toolbar.title.set_loading(False)
            self._window.toolbar.title.progress.set_fraction(1.0)
            # Give focus to webview
            if wanted_scheme:
                GLib.idle_add(self.grab_focus)

    def __on_title_changed(self, webview, title):
        """
            Update title
            @param webview as WebView
            @param title as str
        """
        if webview.get_mapped():
            self._window.toolbar.title.set_title(title)
        self._window.container.sites_manager.update_label(self.view)

    def __on_uri_changed(self, webview, uri):
        """
            Update title bar
            @param webview as WebView
            @param uri as str
        """
        if webview.get_mapped():
            accept_tls = App().websettings.get_accept_tls(uri)
            self._window.toolbar.end.show_tls_button(accept_tls)
            self._window.toolbar.title.set_uri(uri)

    def __on_estimated_load_progress(self, webview, value):
        """
            Update progress bar
            @param webview as WebView
            @param value GparamFloat
        """
        if webview.get_mapped():
            value = self.get_estimated_load_progress()
            self._window.toolbar.title.progress.set_fraction(value)

    def __on_back_forward_list_changed(self, bf_list, added, removed, webview):
        """
            Update actions
            @param bf_list as WebKit2.BackForwardList
            @param added as WebKit2.BackForwardListItem
            @param removed as WebKit2.BackForwardListItem
            @param webview as WebView
        """
        self._window.toolbar.actions.set_actions(webview)
