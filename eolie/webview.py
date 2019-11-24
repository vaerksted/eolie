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

from gi.repository import WebKit2, Gtk, Gio, GLib

from urllib.parse import urlparse
from time import time

from eolie.define import App, LoadingType
from eolie.context import Context
from eolie.webview_errors import WebViewErrors
from eolie.webview_navigation import WebViewNavigation
from eolie.webview_signals import WebViewSignals
from eolie.webview_artwork import WebViewArtwork
from eolie.webview_state import WebViewState
from eolie.webview_credentials import WebViewCredentials
from eolie.webview_helpers import WebViewHelpers
from eolie.webview_night_mode import WebViewNightMode
from eolie.list import LinkedList
from eolie.logger import Logger


class WebView(WebKit2.WebView):
    """
        WebKit view
    """

    def new(window):
        """
            New webview
            @param window as Window
        """
        webview = WebKit2.WebView.new_with_user_content_manager(
            App().content_manager)
        webview.__class__ = WebViewMeta
        webview.__init(None, window)
        return webview

    def new_ephemeral(window):
        """
            New ephemeral webview
            @param window as Window
        """
        context = WebKit2.WebContext.new_ephemeral()
        Context(context)
        webview = WebKit2.WebView.new_with_context(context)
        webview.__class__ = WebViewMeta
        webview.__init(None, window)
        return webview

    def new_with_related_view(related, window):
        """
            Create a new WebView related to view
            @param related as WebView
            @param window as Window
            @return WebView
        """
        webview = WebKit2.WebView.new_with_related_view(related)
        webview.__class__ = WebViewMeta
        webview.__init(related, window)
        return webview

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
            zoom_level = self.window.zoom_level
            if self.__related is not None:
                window = self.__related.get_ancestor(Gtk.Window)
                if window is not None and hasattr(window, "zoom_level"):
                    zoom_level = window.zoom_level
            else:
                _zoom_level = App().websettings.get("zoom", self.uri)
                if _zoom_level is not None:
                    zoom_level = _zoom_level / 100
        except Exception as e:
            Logger.error("WebView::update_zoom_level(): %s", e)
        Logger.debug("Update zoom level: %s", zoom_level)
        self.set_zoom_level(zoom_level)

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
        current = App().websettings.get("zoom", self.uri)
        if current is None:
            current = int(self.window.zoom_level * 100)
        current += 10
        App().websettings.set("zoom", self.uri, current)
        self.update_zoom_level()
        return current

    def zoom_out(self):
        """
            Zoom out view
            @return current zoom after zoom out
        """
        current = App().websettings.get("zoom", self.uri)
        if current is None:
            current = int(self.window.zoom_level * 100)
        current -= 10
        if current == 0:
            return 10
        App().websettings.set("zoom", self.uri, current)
        self.update_zoom_level()
        return current

    def zoom_default(self):
        """
            Reset zoom level
            @return current zoom after zoom out
        """
        current = int(self.window.zoom_level * 100)
        App().websettings.set("zoom", self.uri, None)
        self.update_zoom_level()
        return current

    def set_title(self, title):
        """
            Set title, will be returned by title property until title is set
            by WebView
            @param title as str
        """
        self._title = title
        self.emit("title-changed", title)

    def set_uri(self, uri):
        """
            Set delayed uri
            @param uri as str
        """
        self._uri = uri
        self.emit("uri-changed", uri)

    def update_spell_checking(self, uri):
        """
            Update spell checking
        """
        context = self.get_context()
        codes = App().websettings.get_languages(uri)
        # If None, default user language
        if codes is None:
            locales = GLib.get_language_names()
            try:
                codes = [locales[0].split(".")[0]]
            except:
                codes = None
        if context.get_spell_checking_languages() != codes:
            context.set_spell_checking_languages(codes)

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

    def new_page(self, uri, loading_type):
        """
            Open a new page
            @param uri as uri
            @param loading_type as Gdk.LoadingType
        """
        if self.is_ephemeral:
            webview = WebView.new_ephemeral(self.window)
        else:
            webview = WebView.new(self.window)
        webview.show()
        webview.load_uri(uri)
        if loading_type == LoadingType.POPOVER:
            self.window.container.popup_webview(webview)
        else:
            self.window.container.add_webview(webview, loading_type)
            webview.set_parent(self)
            self.add_child(webview)

    def set_parent(self, parent):
        """
            Set webview parent
            @param parent as WebView
        """
        self.__parent = parent

    def set_atime(self, atime):
        """
            Update access time
            @param atime as int
        """
        self.__atime = atime

    def set_pinned(self, pinned):
        """
            Set window pinned
            @param pinned as bool
        """
        self.__pinned = pinned

    def add_child(self, child):
        """
            Add a child to webview
            @param child as WebView
        """
        if child not in self.__children:
            self.__children.insert(0, child)
            child.connect("destroy", lambda x: self.__children.remove(x))

    def set_shown(self, shown):
        """
            Set webview as shown
            @param shown as bool
        """
        self.__shown = shown

    def set_window(self, window):
        """
            Update GTK window
            @param window as Window
        """
        self.__window = window

    @property
    def is_pinned(self):
        """
            True if window is pinned
            @return bool
        """
        return self.__pinned

    @property
    def readability(self):
        """
            True if webview readable
            @return bool
        """
        return self._readability

    @property
    def atime(self):
        """
            Get access time
            @return int
        """
        return self.__atime

    @property
    def children(self):
        """
            Get page children
            @return [WebView]
        """
        return self.__children

    @property
    def parent(self):
        """
            Get page parent
            @return WebView/None
        """
        return self.__parent

    @property
    def shown(self):
        """
            True if page already shown on screen (one time)
            @return bool
        """
        return self.__shown

    @property
    def title(self):
        """
            Get title (loaded or unloaded)
            @return str
        """
        title = self.get_title()
        if title is None:
            title = self._title
        if title is None:
            title = self.uri
        return title

    @property
    def uri(self):
        """
            Get uri (loaded or unloaded)
            @return str
        """
        return self._uri

    @property
    def netloc(self):
        """
            Get netloc
            @return str
        """
        uri = self.uri
        parsed = urlparse(uri)
        return parsed.netloc or ""

    @property
    def is_ephemeral(self):
        """
            True if view is private/ephemeral
            @return bool
        """
        return self.get_property("is-ephemeral")

    @property
    def related(self):
        """
            Get related webview
            @return WebView
        """
        return self.__related

    @property
    def window(self):
        """
            Get window
            @return Gtk.Window
        """
        return self.__window

    @property
    def selection(self):
        """
            Get current selection
            @return str
        """
        return self.__selection

#######################
# PRIVATE             #
#######################
    def __init(self, related, window):
        """
            Init WebView
            @param related as WebView
            @param window as Window
        """
        WebViewHelpers.__init__(self)
        WebViewNightMode.__init__(self)
        WebViewState.__init__(self)
        WebViewErrors.__init__(self)
        WebViewNavigation.__init__(self)
        WebViewSignals.__init__(self)
        WebViewArtwork.__init__(self)
        WebViewCredentials.__init__(self)
        self.__window = window
        self.__atime = 0
        self.__children = []
        self.__parent = None
        self.__pinned = False
        # WebKitGTK doesn't provide an API to get selection, so try to guess
        # it from clipboard FIXME Get it from extensions
        self.__selection = ""
        self._readability = False
        self._uri = None
        self._initial_uri = None
        self._title = None
        self.__related = related
        self.__shown = False
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.clear_text_entry()
        if related is None:
            # Set settings
            settings = self.get_settings()
            settings.set_property("enable-java",
                                  App().settings.get_value('enable-plugins'))
            settings.set_property("enable-plugins",
                                  App().settings.get_value('enable-plugins'))
            settings.set_property("minimum-font-size",
                                  App().settings.get_value(
                                      "min-font-size").get_int32())
            if App().settings.get_value("use-system-fonts"):
                self.__set_system_fonts(settings)
            else:
                settings.set_property("monospace-font-family",
                                      App().settings.get_value(
                                          "font-monospace").get_string())
                settings.set_property("sans-serif-font-family",
                                      App().settings.get_value(
                                          "font-sans-serif").get_string())
                settings.set_property("serif-font-family",
                                      App().settings.get_value(
                                          "font-serif").get_string())
            settings.set_property("auto-load-images", True)
            # settings.set_hardware_acceleration_policy(
            #    WebKit2.HardwareAccelerationPolicy.NEVER)
            settings.set_property("enable-site-specific-quirks", True)
            settings.set_property("allow-universal-access-from-file-urls",
                                  False)
            settings.set_property("allow-file-access-from-file-urls", False)
            settings.set_property("enable-javascript", True)
            settings.set_property("enable-media-stream", True)
            settings.set_property("enable-mediasource", True)
            autoplay_videos = App().settings.get_value('autoplay-videos')
            # Setting option to False make video playback buggy
            if not autoplay_videos:
                settings.set_property("media-playback-requires-user-gesture",
                                      True)
            if App().settings.get_value("developer-extras"):
                settings.set_property("enable-developer-extras", True)
                settings.set_enable_write_console_messages_to_stdout(True)
            settings.set_property("enable-offline-web-application-cache", True)
            settings.set_property("enable-page-cache", True)
            settings.set_property("enable-resizable-text-areas", True)
            settings.set_property(
                "enable-smooth-scrolling",
                App().settings.get_value("enable-smooth-scrolling"))
            settings.set_property("enable-webaudio", True)
            settings.set_property("enable-webgl", True)
            settings.set_property("javascript-can-access-clipboard", True)
            settings.set_property("javascript-can-open-windows-automatically",
                                  True)
            settings.set_property("media-playback-allows-inline", True)
            if WebKit2.get_minor_version() > 22:
                settings.set_property(
                    "enable-back-forward-navigation-gestures", True)
        self.connect("create", self.__on_create)
        self.connect("load-changed", self._on_load_changed)

    def __set_system_fonts(self, settings):
        """
            Set system font
            @param settings as WebKit2.Settings
            @param system as Gio.Settings("org.gnome.desktop.interface")
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

    def __on_create(self, related, navigation_action):
        """
            Create a new view for action
            @param related as WebView
            @param navigation_action as WebKit2.NavigationAction
        """
        webview = WebView.new_with_related_view(related, self.window)
        webview.set_atime(related.atime - 1)
        elapsed = time() - related._last_click_time
        uri = navigation_action.get_request().get_uri()
        webview.connect("ready-to-show",
                        self.__on_ready_to_show,
                        related,
                        navigation_action,
                        elapsed)
        webview.set_uri(uri)
        webview.set_parent(self)
        webview.show()
        self.add_child(webview)
        return webview

    def __on_ready_to_show(self, webview, related, navigation_action, elapsed):
        """
            Add a new webview with related
            @param webview as WebView
            @param related as WebView
            @param navigation_action as WebKit2.NavigationAction
            @param elapsed as float
        """
        properties = webview.get_window_properties()
        if (properties.get_toolbar_visible() or
                properties.get_scrollbars_visible()):
            self.window.container.add_webview(
                webview,
                LoadingType.FOREGROUND)
        else:
            self.window.container.popup_webview(webview)


class WebViewMeta(WebViewNavigation, WebView, WebViewErrors,
                  WebViewSignals, WebViewArtwork, WebViewState,
                  WebViewCredentials, WebViewHelpers, WebViewNightMode):

    def __init__(self):
        pass

#######################
# PROTECTED           #
#######################
    def _on_load_changed(self, webview, event):
        """
            Update internals
            @param webview as WebView
            @param event as WebKit2.LoadEvent
        """
        WebViewCredentials._on_load_changed(self, webview, event)
        WebViewHelpers._on_load_changed(self, webview, event)
        WebViewNavigation._on_load_changed(self, webview, event)
        WebViewArtwork._on_load_changed(self, webview, event)
        WebViewNightMode._on_load_changed(self, webview, event)
        if event == WebKit2.LoadEvent.COMMITTED:
            self._uri = webview.get_uri()
