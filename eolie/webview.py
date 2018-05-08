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

from gi.repository import WebKit2, Gtk, Gio, Gdk, GLib

from urllib.parse import urlparse
from time import time

from eolie.define import App, Indicator, LoadingType
from eolie.webview_errors import WebViewErrors
from eolie.webview_navigation import WebViewNavigation
from eolie.webview_signals import WebViewSignals
from eolie.webview_artwork import WebViewArtwork
from eolie.context import Context
from eolie.list import LinkedList
from eolie.logger import Logger


class WebView(WebKit2.WebView):
    """
        WebKit view
    """

    def new(window, view):
        """
            New webview
            @param window as Window
            @param view as View
        """
        context = WebKit2.WebContext.new()
        Context(context)
        webview = WebKit2.WebView.new_with_context(context)
        content_manager = webview.get_property("user-content-manager")
        webview.__class__ = WebViewMeta
        webview.__init(None, context, content_manager, window, view)
        return webview

    def new_ephemeral(window, view):
        """
            New ephemeral webview
            @param window as Window
            @param view as View
        """
        context = WebKit2.WebContext.new_ephemeral()
        Context(context)
        webview = WebKit2.WebView.new_with_context(context)
        webview.__class__ = WebViewMeta
        content_manager = webview.get_property("user-content-manager")
        webview.__init(None, context, content_manager, window, view)
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
        # Related view are linked to related context, can't do anything about
        # this
        webview.__init(related, related.context,
                       related.content_manager, window, None)
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
            zoom_level = App().websettings.get_zoom(self.uri)
            if zoom_level is None:
                zoom_level = 100
            if self.__related_view is None:
                zoom_level *= self._window.zoom_level
            else:
                window = self.__related_view.get_ancestor(Gtk.Window)
                if window is not None and hasattr(window, "zoom_level"):
                    zoom_level *= window.zoom_level
        except Exception as e:
            Logger.error("WebView::update_zoom_level(): %s", e)
        Logger.debug("Update zoom level: %s", zoom_level)
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
        current = App().websettings.get_zoom(self.uri)
        if current is None:
            current = 100
        current += 10
        App().websettings.set_zoom(current, self.uri)
        self.update_zoom_level()
        return current

    def zoom_out(self):
        """
            Zoom out view
            @return current zoom after zoom out
        """
        current = App().websettings.get_zoom(self.uri)
        if current is None:
            current = 100
        current -= 10
        if current == 0:
            return 10
        App().websettings.set_zoom(current, self.uri)
        self.update_zoom_level()
        return current

    def zoom_default(self):
        """
            Reset zoom level
            @return current zoom after zoom out
        """
        App().websettings.set_zoom(100, self.uri)
        self.update_zoom_level()

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
        self.__uri = uri
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
        parsed = urlparse(uri)
        if App().settings.get_value("adblock") and\
                parsed.scheme in ["http", "https"] and\
                not App().adblock_exceptions.find_parsed(parsed):
            if App().adblock.is_netloc_blocked(parsed.netloc) or\
                    App().adblock.is_uri_blocked(uri,
                                                 parsed.netloc):
                Logger.debug("WebView::new_page(): blocking %s ->%s",
                             uri, self.uri)
                return True
        if loading_type == LoadingType.POPOVER:
            if self.ephemeral:
                webview = WebView.new_ephemeral(self._window, None)
            else:
                webview = WebView.new(self._window, None)
            self._window.container.popup_webview(webview, True)
            GLib.idle_add(webview.load_uri, uri)
        else:
            self.__new_pages_opened += 1
            webview = self._window.container.add_webview(
                uri,
                loading_type,
                self.ephemeral,
                None,
                self.atime -
                self.__new_pages_opened)
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

    def set_view(self, view):
        """
            Set webview view
            @param view as View
        """
        self.__view = view

    def set_window(self, window):
        """
            Set webview window
            @param window as Window
        """
        self._window = window

    def add_child(self, child):
        """
            Add a child to webview
            @param child as WebView
        """
        if child not in self.__children:
            self.__children.insert(0, child)

    def remove_child(self, child):
        """
            Remove child from webview
            @param child as WebView
        """
        if child in self.__children:
            self.__children.remove(child)

    @property
    def content_manager(self):
        """
            Get content manager
            @return WebKit2.UserContentManager
        """
        return self.__content_manager

    @property
    def context(self):
        """
            Get context
            @return WebKit2.WebContext
        """
        return self.__context

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
    def view(self):
        """
            Get view
            @return View
        """
        return self.__view

    @property
    def shown(self):
        """
            True if page already shown on screen (one time)
        """
        return self._shown

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
        uri = self.get_uri()
        if uri is None:
            uri = self.__uri
        return uri

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
    def __init(self, related_view, context, content_manager, window, view):
        """
            Init WebView
            @param related_view as WebView
            @param context as WebKit2.WebContext
            @param content_manager as WebKit2.UserContentManager
            @param window as Window
            @param view as View
        """
        WebViewErrors.__init__(self)
        WebViewNavigation.__init__(self, related_view)
        WebViewSignals.__init__(self)
        WebViewArtwork.__init__(self)
        self._window = window
        self.__view = view
        self.__context = context
        self.__content_manager = content_manager
        self.__atime = 0
        self.__children = []
        self.__parent = None
        self.__new_pages_opened = 0
        # WebKitGTK doesn't provide an API to get selection, so try to guess
        # it from clipboard FIXME Get it from extensions
        self.__selection = ""
        self._readable_content = ""
        self.__uri = None
        self._title = None
        self.__related_view = related_view
        self._shown = False
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.clear_text_entry()
        # Set settings
        settings = self.get_settings()
        system = Gio.Settings.new("org.gnome.desktop.interface")
        animations = system.get_value("enable-animations")
        settings.set_property("enable-java",
                              App().settings.get_value('enable-plugins'))
        settings.set_property("enable-plugins",
                              App().settings.get_value('enable-plugins'))
        settings.set_property("minimum-font-size",
                              App().settings.get_value(
                                  "min-font-size").get_int32())
        if App().settings.get_value("use-system-fonts"):
            self.__set_system_fonts(settings, system)
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
        settings.set_property("enable-site-specific-quirks", True)
        settings.set_property("allow-universal-access-from-file-urls", False)
        settings.set_property("allow-file-access-from-file-urls", False)
        settings.set_property("enable-javascript", True)
        settings.set_property("enable-media-stream", True)
        settings.set_property("enable-mediasource", False)
        settings.set_property("enable-developer-extras",
                              App().settings.get_value("developer-extras"))
        settings.set_property("enable-offline-web-application-cache", True)
        settings.set_property("enable-page-cache", True)
        settings.set_property("enable-resizable-text-areas", True)
        settings.set_property("enable-smooth-scrolling", animations)
        settings.set_property("enable-webaudio", True)
        settings.set_property("enable-webgl", True)
        settings.set_property("javascript-can-access-clipboard", True)
        settings.set_property("javascript-can-open-windows-automatically",
                              True)
        settings.set_property("media-playback-allows-inline", True)
        self.connect("create", self.__on_create)
        self.connect("load-changed", self._on_load_changed)

    def __set_system_fonts(self, settings, system=None):
        """
            Set system font
            @param settings as WebKit2.Settings
            @param system as Gio.Settings("org.gnome.desktop.interface")
        """
        if system is None:
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
        webview = WebView.new_with_related_view(related, self._window)
        webview.set_atime(related.atime - 1)
        webview.connect("ready-to-show",
                        self.__on_ready_to_show,
                        related,
                        navigation_action)
        webview.set_parent(self)
        self.add_child(webview)
        return webview

    def __on_ready_to_show(self, webview, related, navigation_action):
        """
            Add a new webview with related
            @param webview as WebView
            @param related as WebView
            @param navigation_action as WebKit2.NavigationAction
        """
        def on_load_changed(webview, event):
            parsed = urlparse(webview.uri)
            # First, adblocking
            if not parsed.netloc:
                return
            if App().settings.get_value("adblock") and\
                    parsed.scheme in ["http", "https"] and\
                    not App().adblock_exceptions.find_parsed(parsed):
                if App().adblock.is_netloc_blocked(parsed.netloc) or\
                        App().adblock.is_uri_blocked(webview.uri,
                                                     parsed.netloc):
                    webview.destroy()
                    return
            if event != WebKit2.LoadEvent.FINISHED:
                return
            else:
                webview.disconnect_by_func(on_load_changed)

            # Then popup blocking
            popup_block = App().settings.get_value("popupblock")
            if related.uri is not None:
                parsed_related = urlparse(related.uri)
                elapsed = time() - related._last_click_time
                exception = elapsed < 1.0 or\
                    App().popup_exceptions.find_parsed(parsed_related)
            else:
                exception = False

            properties = webview.get_window_properties()
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
            elif (properties.get_toolbar_visible() or
                    properties.get_scrollbars_visible()) and\
                    not self._window.modifiers & Gdk.ModifierType.SHIFT_MASK:
                self._window.container.add_webview_with_new_view(
                    webview,
                    LoadingType.FOREGROUND)
            else:
                self._window.container.popup_webview(webview, True)

        webview.connect("load-changed", on_load_changed)

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


class WebViewMeta(WebViewNavigation, WebView, WebViewErrors,
                  WebViewSignals, WebViewArtwork):

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
        self.__uri = webview.get_uri()
        if event == WebKit2.LoadEvent.STARTED:
            self.__new_pages_opened = 0
        WebViewNavigation._on_load_changed(self, webview, event)
        WebViewSignals._on_load_changed(self, webview, event)
        WebViewArtwork._on_load_changed(self, webview, event)
