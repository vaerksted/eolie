# Copyright (c) 2014-2016 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from gi.repository import WebKit2, Gio, Gtk, Gdk

import ctypes
from urllib.parse import urlparse

from eolie.widget_find import FindWidget
from eolie.define import El, LOGINS, PASSWORDS
from eolie.utils import get_current_monitor_model


class WebView(Gtk.Grid):
    """
        WebKit view
        All WebKit2.WebView members available
        Forward all connect to internal WebKit2.WebView webview, you get
        self as first argument
    """
    def __init__(self, parent=None, webview=None):
        """
            Init view
            @param parent as WebView
            @param webview as WebKit2.WebView
        """
        Gtk.Grid.__init__(self)
        self.__parent = parent
        if parent is not None:
            parent.connect("destroy", self.__on_parent_destroy)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.__input_source = Gdk.InputSource.MOUSE
        self.__loaded_uri = ""
        if webview is None:
            self.__webview = WebKit2.WebView()
        else:
            self.__webview = webview
        self.__webview.set_hexpand(True)
        self.__webview.set_vexpand(True)
        self.__webview.connect("scroll-event", self.__on_scroll_event)
        self.__webview.show()
        self.__find_widget = FindWidget(self.__webview)
        self.__find_widget.show()
        settings = self.__webview.get_settings()
        settings.set_property('enable-java',
                              El().settings.get_value('enable-plugins'))
        settings.set_property('enable-plugins',
                              El().settings.get_value('enable-plugins'))
        settings.set_property('minimum-font-size',
                              El().settings.get_value(
                                'min-font-size').get_int32())
        if El().settings.get_value('use-system-fonts'):
            self.__set_system_fonts(settings)
        else:
            settings.set_property('monospace-font-family',
                                  El().settings.get_value(
                                    'font-monospace').get_string())
            settings.set_property('sans-serif-font-family',
                                  El().settings.get_value(
                                    'font-sans-serif').get_string())
            settings.set_property('serif-font-family',
                                  El().settings.get_value(
                                    'font-serif').get_string())
        settings.set_property("allow-file-access-from-file-urls",
                              False)
        settings.set_property("auto-load-images", True)
        settings.set_property("enable-javascript", True)
        settings.set_property("enable-media-stream", True)
        settings.set_property("enable-mediasource", True)
        settings.set_property("enable-offline-web-application-cache", True)
        settings.set_property("enable-page-cache", True)
        settings.set_property("enable-resizable-text-areas", True)
        settings.set_property("enable-smooth-scrolling", True)
        settings.set_property("enable-webaudio", True)
        settings.set_property("enable-webgl", True)
        settings.set_property("javascript-can-access-clipboard", True)
        settings.set_property("javascript-can-open-windows-automatically",
                              True)
        settings.set_property("media-playback-allows-inline", True)
        self.__webview.set_settings(settings)
        self.__webview.connect("decide-policy", self.__on_decide_policy)
        self.__webview.connect("submit-form", self.__on_submit_form)
        self.__webview.connect("create", self.__on_create)
        self.__webview.connect("run-as-modal", self.__on_run_as_modal)
        self.__webview.connect("close", self.__on_close)
        self.__webview.get_context().connect("download-started",
                                             self.__on_download_started)
        self.add(self.__find_widget)
        self.add(self.__webview)
        self.update_zoom_level()

    def load_uri(self, uri):
        """
            Load uri
            @param uri as str
        """
        if not uri.startswith("http://") and not uri.startswith("https://"):
            uri = "http://" + uri
        self.__loaded_uri = uri
        self.__webview.load_uri(uri)

    def update_zoom_level(self):
        """
            Update zoom level
        """
        monitor_model = get_current_monitor_model()
        zoom_levels = El().settings.get_value(
                                         "default-zoom-level")
        wanted_zoom_level = 1.0
        try:
            for zoom_level in zoom_levels:
                zoom_splited = zoom_level.split('@')
                if zoom_splited[0] == monitor_model:
                    wanted_zoom_level = float(zoom_splited[1])
        except Exception as e:
            print("Window::__save_size_position()", e)
        self.__webview.set_zoom_level(wanted_zoom_level)

    def set_setting(self, key, value):
        """
            Set setting to value
            @param key as str
            @param value as GLib.Variant
        """
        settings = self.__webview.get_settings()
        if key == 'use-system-fonts':
            self.__set_system_fonts(settings)
        else:
            settings.set_property(key, value)
        self.__webview.set_settings(settings)

    def __getattr__(self, name):
        """
            Get all attributes from webview
            @param name as str
        """
        return getattr(self.__webview, name)

    def connect(self, *args, **kwargs):
        """
            Forward connect to webview, prepend self as arg as
            internal webview may not be useful for callers
            @param args as (str, callback)
            @param kwargs as data
        """
        self.__webview.connect(*args, self, **kwargs)

    def find(self):
        """
            Show find widget
        """
        search_mode = self.__find_widget.get_search_mode()
        self.__find_widget.set_search_mode(not search_mode)
        if not search_mode:
            self.__find_widget.grab_focus()

    @property
    def parent(self):
        """
            Get parent web view
            @return WebView/None
        """
        return self.__parent

    @property
    def loaded_uri(self):
        """
            Return loaded uri (This is not current uri!)
            @return str
        """
        return self.__loaded_uri

#######################
# PRIVATE             #
#######################
    def __set_system_fonts(self, settings):
        """
            Set system font
            @param settings as WebKit2.Settings
        """
        system = Gio.Settings.new('org.gnome.desktop.interface')
        settings.set_property(
                        'monospace-font-family',
                        system.get_value('monospace-font-name').get_string())
        settings.set_property(
                        'sans-serif-font-family',
                        system.get_value('document-font-name').get_string())
        settings.set_property(
                        'serif-font-family',
                        system.get_value('font-name').get_string())

    def __read_auth_request(self, request):
        """
            Read request for authentification
            @param request as WebKit2.FormSubmissionRequest
        """
        auth = False
        username = ""
        password = ""
        fields = request.get_text_fields()
        if fields is None:
            return (username, password, auth)
        for k, v in fields.items():
            name = ctypes.string_at(k).decode("utf-8")
            for search in LOGINS:
                if search in name.lower():
                    username = ctypes.string_at(v).decode("utf-8")
                    break
            for search in PASSWORDS:
                if search in name.lower():
                    password = ctypes.string_at(v).decode("utf-8")
                    break
            if username and password:
                auth = True
                break
        return (auth, username, password)

    def __set_smooth_scrolling(self, source):
        """
            Set smooth scrolling based on source
            @param source as Gdk.InputSource
        """
        settings = self.__webview.get_settings()
        settings.set_property("enable-smooth-scrolling",
                              source != Gdk.InputSource.MOUSE)
        self.__webview.set_settings(settings)

    def __on_parent_destroy(self, internal, view):
        """
            Remove parent
            @param internal as WebKit2.WebView
            @param view as WebView
        """
        self.__parent = None

    def __on_create(self, view, action):
        """
            Create a new view for action
            @param view as WebKit2.WebView
            @param action as WebKit2.NavigationAction
        """
        uri = action.get_request().get_uri()
        view = WebKit2.WebView.new_with_related_view(self.__webview)
        view.connect("ready-to-show", self.__on_ready_to_show, uri)
        return view

    def __on_ready_to_show(self, view, uri):
        """
            Add view to window
            @param view as WebKit2.WebView
            @param uri as str
        """
        El().active_window.container.add_web_view(uri, True, self, view)

    def __on_run_as_modal(self, view):
        """
        """
        print("WebView::__on_run_as_modal(): TODO")

    def __on_close(self, view):
        """
            Close my self
            @param view as WebKit2.WebView
        """
        for window in El().windows:
            window.container.sidebar.close_view(self)

    def __on_scroll_event(self, widget, event):
        """
            Adapt scroll speed to device
            @param widget as WebKit2.WebView
            @param event as Gdk.EventScroll
        """
        source = event.device.get_source()
        self.__input_source
        if source == Gdk.InputSource.MOUSE:
            event.delta_x *= 2
            event.delta_y *= 2
        if self.__input_source != source:
            self.__input_source = source
            self.__set_smooth_scrolling(source)

    def __on_submit_form(self, view, request):
        """
            Check for auth forms
            @param view as WebKit2.WebView
            @param request as WebKit2.FormSubmissionRequest
        """
        (auth, username, password) = self.__read_auth_request(request)
        if not auth:
            return
        parsed = urlparse(view.get_uri())
        El().active_window.toolbar.title.save_password(
                                 username, password, parsed.netloc)

    def __on_download_started(self, context, download):
        """
            A new download started, handle signals
            @param context as WebKit2.WebContext
            @param download as WebKit2.Download
        """
        El().download_manager.add(download)

    def __on_decide_policy(self, view, decision, decision_type):
        """
            Navigation policy
            @param view as WebKit2.WebView
            @param decision as WebKit2.NavigationPolicyDecision
            @param decision_type as WebKit2.PolicyDecisionType
            @return bool
        """
        # Always accept response
        if decision_type == WebKit2.PolicyDecisionType.RESPONSE:
            mime_type = decision.get_response().props.mime_type
            if "application/" in mime_type:
                decision.download()
            else:
                decision.use()
            return False

        uri = decision.get_navigation_action().get_request().get_uri()
        mouse_button = decision.get_navigation_action().get_mouse_button()
        if mouse_button == 0:
            if decision_type == WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION:
                El().active_window.container.add_web_view(uri, True, self)
                decision.ignore()
                return True
            else:
                decision.use()
                return False
        elif mouse_button == 1:
            self.__loaded_uri = uri
            if decision_type == WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION:
                El().active_window.container.add_web_view(uri, True, self)
                decision.ignore()
                return True
            else:
                decision.use()
                return False
        else:
            El().active_window.container.add_web_view(uri, False, self)
            decision.ignore()
            return True
