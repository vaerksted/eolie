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

from gi.repository import WebKit2, Gtk, Gio, Gdk, GLib

from urllib.parse import urlparse
from time import time

from eolie.define import El, Indicator
from eolie.utils import debug
from eolie.webview_errors import WebViewErrors
from eolie.webview_navigation import WebViewNavigation
from eolie.webview_signals import WebViewSignals
from eolie.list import LinkedList


class WebView(WebKit2.WebView):
    """
        WebKit view
    """

    def new(window):
        """
            New webview
            @param window as Window
        """
        content_manager = WebKit2.UserContentManager.new()
        view = WebKit2.WebView.new_with_user_content_manager(content_manager)
        view.__class__ = WebViewMeta
        view.__init(None, content_manager, window)
        return view

    def new_ephemeral(window):
        """
            New ephemeral webview
            @param window as Window
        """
        view = WebKit2.WebView.new_with_context(El().ephemeral_context)
        view.__class__ = WebViewMeta
        view.__init(None, None, window)
        return view

    def new_with_related_view(related, window):
        """
            Create a new WebView related to view
            @param related as WebView
            @param window as Window
            @return WebView
        """
        view = WebKit2.WebView.new_with_related_view(related)
        view.__class__ = WebViewMeta
        view.__init(related, None, window)
        return view

    def set_setting(self, key, value):
        """
            Set setting to value
            @param key as str
            @param value as GLib.Variant
        """
        settings = self.get_settings()
        if key == 'use-system-fonts':
            self.__set_system_fonts(settings)
        else:
            settings.set_property(key, value)

    def update_zoom_level(self):
        """
            Update zoom level
        """
        try:
            zoom_level = El().websettings.get_zoom(self.get_uri())
            if zoom_level is None:
                zoom_level = 100
            if self.__related_view is None:
                zoom_level *= self._window.zoom_level
            else:
                zoom_level *= self.__related_view.get_ancestor(
                                                Gtk.Window).zoom_level
        except Exception as e:
            print("WebView::update_zoom_level()", e)
        debug("Update zoom level: %s" % zoom_level)
        self.set_zoom_level(zoom_level / 100)

    def print(self):
        """
            Show print dialog for current page
        """
        p = WebKit2.PrintOperation.new(self)
        p.run_dialog()

    def zoom_in(self):
        """
            Zoom in view
            @return current zoom after zoom in
        """
        current = El().websettings.get_zoom(self.get_uri())
        if current is None:
            current = 100
        current += 10
        El().websettings.set_zoom(current, self.get_uri())
        self.update_zoom_level()
        return current

    def zoom_out(self):
        """
            Zoom out view
            @return current zoom after zoom out
        """
        current = El().websettings.get_zoom(self.get_uri())
        if current is None:
            current = 100
        current -= 10
        if current == 0:
            return 10
        El().websettings.set_zoom(current, self.get_uri())
        self.update_zoom_level()
        return current

    def zoom_default(self):
        """
            Reset zoom level
            @return current zoom after zoom out
        """
        El().websettings.set_zoom(100, self.get_uri())
        self.update_zoom_level()

    def set_delayed_uri(self, uri):
        """
            Set delayed uri
            @param uri as str
        """
        self.__delayed_uri = uri

    def update_spell_checking(self):
        """
            Update spell checking
        """
        codes = El().websettings.get_languages(self.get_uri())
        # If None, default user language
        if codes is not None:
            self.get_context().set_spell_checking_languages(codes)

    def add_text_entry(self, text):
        """
            Add an uri to text entry list
            @param text as str
        """
        if text and text != self.__text_entry.value:
            item = LinkedList(text, None, self.__text_entry)
            self.__text_entry = item

    def clear_text_entry(self):
        """
            Clear text entry history
        """
        self.__text_entry = LinkedList("", None, None)

    def get_current_text_entry(self):
        """
            Get currnet text entry value
            @return text as str
        """
        current = None
        if self.__text_entry is not None:
            current = self.__text_entry.value
        return current

    def get_prev_text_entry(self, current_value=None):
        """
            Get previous text entry value
            @param current_value as str
            @return text as str
        """
        previous = None
        if self.__text_entry.prev is not None:
            # Append current to list as it is missing
            if current_value != self.__text_entry.value:
                item = LinkedList(current_value, None, self.__text_entry)
                self.__text_entry.set_next(item)
                previous = self.__text_entry.value
            else:
                current = self.__text_entry
                previous = self.__text_entry.prev.value
                if previous is not None:
                    self.__text_entry = self.__text_entry.prev
                    self.__text_entry.set_next(current)
        return previous

    def get_next_text_entry(self):
        """
            Get next text entry value
            @return text as str
        """
        next = None
        if self.__text_entry.next is not None:
            next = self.__text_entry.next.value
            if next is not None:
                self.__text_entry = self.__text_entry.next
        return next

    def stop_loading(self):
        """
            Keep stop loading state
        """
        self._cancelled = True
        WebKit2.WebView.stop_loading(self)

    def new_page(self, window_type):
        """
            Open a new page
            @param window_type as Gdk.WindowType
        """
        if window_type == Gdk.WindowType.SUBSURFACE:
            if self.ephemeral:
                webview = WebView.new_ephemeral(self._window)
            else:
                webview = WebView.new(self._window)
            self._window.container.popup_webview(webview, True)
            GLib.idle_add(webview.load_uri, self._navigation_uri)
        else:
            new = self._window.container.add_webview(self._navigation_uri,
                                                     window_type,
                                                     self.ephemeral)
            # parent.rtime = child.rtime + 1
            # Used to search for best matching webview
            new.set_rtime(self.rtime - 1)

    def set_rtime(self, time):
        """
            Update related time
            @param time as int
        """
        self.__rtime = time

    def set_atime(self):
        """
            Update access time
        """
        self._atime = int(time())

    def mark_shown(self):
        """
            Mark view as shown
        """
        self.__shown = True

    @property
    def rtime(self):
        """
            Get creation time
            @return int
        """
        return self.__rtime

    @property
    def atime(self):
        """
            Get access time
            @return int
        """
        return self._atime

    @property
    def shown(self):
        """
            True if page already shown on screen (one time)
        """
        return self.__shown

    @property
    def cancelled(self):
        """
            True if last loading was cancelled
            @return bool
        """
        return self._cancelled

    @property
    def delayed_uri(self):
        """
            Get delayed uri (one time)
            @return str
        """
        try:
            return self.__delayed_uri
        finally:
            self.__delayed_uri = None

    @property
    def ephemeral(self):
        """
            True if view is private/ephemeral
            @return bool
        """
        return self.get_property("is-ephemeral")

    @property
    def selection(self):
        """
            Get current selection
            @return str
        """
        return self.__selection

    @property
    def readable_content(self):
        """
            Readable content
            @return content as str
        """
        return self._readable_content

#######################
# PRIVATE             #
#######################
    def __init(self, related_view, content_manager, window):
        """
            Init WebView
            @param related_view as WebView
            @param content_manager as WebKit2.UserContentManager
            @param window as Window
        """
        WebViewErrors.__init__(self)
        WebViewNavigation.__init__(self)
        WebViewSignals.__init__(self)
        self._window = window
        self._content_manager = content_manager
        self._atime = 0
        self.__rtime = int(time())
        # WebKitGTK doesn't provide an API to get selection, so try to guess
        # it from clipboard FIXME Get it from extensions
        self.__selection = ""
        self._readable_content = ""
        self.__delayed_uri = None
        self._navigation_uri = None
        self.__related_view = related_view
        self.__input_source = Gdk.InputSource.MOUSE
        self._cancelled = False
        self.__shown = False
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.clear_text_entry()
        # Set settings
        settings = self.get_settings()
        settings.set_property("enable-java",
                              El().settings.get_value('enable-plugins'))
        settings.set_property("enable-plugins",
                              El().settings.get_value('enable-plugins'))
        settings.set_property("minimum-font-size",
                              El().settings.get_value(
                                "min-font-size").get_int32())
        if El().settings.get_value("use-system-fonts"):
            self.__set_system_fonts(settings)
        else:
            settings.set_property("monospace-font-family",
                                  El().settings.get_value(
                                    "font-monospace").get_string())
            settings.set_property("sans-serif-font-family",
                                  El().settings.get_value(
                                    "font-sans-serif").get_string())
            settings.set_property("serif-font-family",
                                  El().settings.get_value(
                                    "font-serif").get_string())
        settings.set_property("auto-load-images", True)
        settings.set_property("enable-site-specific-quirks", True)
        settings.set_property("allow-universal-access-from-file-urls", False)
        settings.set_property("allow-file-access-from-file-urls", False)
        settings.set_property("enable-javascript", True)
        settings.set_property("enable-media-stream", True)
        settings.set_property("enable-mediasource", True)
        settings.set_property("enable-developer-extras",
                              El().settings.get_value("developer-extras"))
        settings.set_property("enable-offline-web-application-cache", True)
        settings.set_property("enable-page-cache", True)
        settings.set_property("enable-resizable-text-areas", True)
        settings.set_property("enable-smooth-scrolling", False)
        settings.set_property("enable-webaudio", True)
        settings.set_property("enable-webgl", True)
        settings.set_property("javascript-can-access-clipboard", True)
        settings.set_property("javascript-can-open-windows-automatically",
                              True)
        settings.set_property("media-playback-allows-inline", True)
        self.connect("create", self.__on_create)

    def __set_system_fonts(self, settings):
        """
            Set system font
            @param settings as WebKit2.Settings
        """
        system = Gio.Settings.new("org.gnome.desktop.interface")
        settings.set_property(
                        "monospace-font-family",
                        system.get_value("monospace-font-name").get_string())
        settings.set_property(
                        "sans-serif-font-family",
                        system.get_value("document-font-name").get_string())
        settings.set_property(
                        "serif-font-family",
                        system.get_value("font-name").get_string())

    def __set_smooth_scrolling(self, source):
        """
            Set smooth scrolling based on source
            @param source as Gdk.InputSource
        """
        settings = self.get_settings()
        settings.set_property("enable-smooth-scrolling",
                              source != Gdk.InputSource.MOUSE)

    def __on_create(self, related, navigation_action):
        """
            Create a new view for action
            @param related as WebView
            @param navigation_action as WebKit2.NavigationAction
        """
        webview = WebView.new_with_related_view(related, self._window)
        self.set_rtime(related.rtime - 1)
        webview.connect("ready-to-show",
                        self.__on_ready_to_show,
                        related,
                        navigation_action)
        return webview

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
            webview.connect("close", self.__on_popup_close, related)
            if related == self._window.container.current.webview:
                self._window.toolbar.title.show_indicator(
                                                        Indicator.POPUPS)
            return
        properties = webview.get_window_properties()
        if properties.get_locationbar_visible() and\
                properties.get_toolbar_visible() and\
                not navigation_action.get_modifiers() &\
                Gdk.ModifierType.SHIFT_MASK:
            self._window.container.add_view(webview,
                                            Gdk.WindowType.CHILD)
        else:
            self._window.container.popup_webview(webview, True)

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


class WebViewMeta(WebViewNavigation, WebView, WebViewErrors, WebViewSignals):
    def __init__(self):
        pass
