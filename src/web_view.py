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

from gi.repository import WebKit2, Gio, Gtk

import ctypes
from urllib.parse import urlparse

from eolie.define import El, LOGINS, PASSWORDS


class WebView(Gtk.Grid):
    """
        WebKit view
        All WebKit2.WebView members available
        Forward all connect to internal WebKit2.WebView webview, you get
        self as first argument
    """
    def __init__(self):
        """
            Init view
        """
        Gtk.Grid.__init__(self)
        self.__loaded_uri = ""
        self.__webview = WebKit2.WebView()
        self.__webview.set_hexpand(True)
        self.__webview.set_vexpand(True)
        self.__webview.show()
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
        self.__webview.get_context().connect("download-started",
                                             self.__on_download_started)
        self.add(self.__webview)

    def load_uri(self, uri):
        """
            Load uri
            @param uri as str
        """
        if not uri.startswith("http://") and not uri.startswith("https://"):
            uri = "http://" + uri
        self.__loaded_uri = uri
        self.__webview.load_uri(uri)

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

    @property
    def is_offscreen(self):
        """
            True if offscreen
        """
        parent = self.get_parent()
        return parent is not None and isinstance(parent, Gtk.OffscreenWindow)

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
        if decision.get_mouse_button() == 0:
            decision.use()
            return False
        elif decision.get_mouse_button() == 1:
            self.__loaded_uri = uri
            decision.use()
            return False
        else:
            El().active_window.container.add_web_view(uri, False)
            decision.ignore()
            return True
