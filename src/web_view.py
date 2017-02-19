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

from gi.repository import WebKit2, GObject, Gio, GLib, Gdk

import ctypes
from urllib.parse import urlparse

from eolie.define import El, LOGINS, PASSWORDS
from eolie.utils import get_current_monitor_model


class WebView(WebKit2.WebView):
    """
        WebKit view
        All WebKit2.WebView members available
        Forward all connect to internal WebKit2.WebView webview, you get
        self as first argument
    """

    # If you add a signal here, you need to update new_with_related_view()
    __gsignals__ = {
        "readable": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "new-page":  (GObject.SignalFlags.RUN_FIRST, None, (str, bool)),
    }

    def __init__(self):
        """
            Init view
        """
        WebKit2.WebView.__init__(self)
        self.__init()

    def new_with_related_view(related):
        """
            Create a new WebView related to view
            @param related as WebView
            @return WebView
        """
        view = WebKit2.WebView.new_with_related_view(related)
        # Manually install signals
        gsignals = {
            "readable": (GObject.SignalFlags.RUN_FIRST, None, ()),
            "new-page":  (GObject.SignalFlags.RUN_FIRST, None, (str, bool)),
        }
        if "readable" not in GObject.signal_list_names(WebKit2.WebView):
            for signal in gsignals:
                args = gsignals[signal]
                GObject.signal_new(signal, WebKit2.WebView,
                                   args[0], args[1], args[2])
        view.__class__ = WebView
        view.__init()
        return view

    def load_uri(self, uri):
        """
            Load uri
            @param uri as str
        """
        self.__cancellable.cancel()
        self.__cancellable.reset()
        if not uri.startswith("http://") and not uri.startswith("https://"):
            uri = "http://" + uri
        self.__loaded_uri = uri
        WebKit2.WebView.load_uri(self, uri)

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
        self.set_zoom_level(wanted_zoom_level)

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
        self.set_settings(settings)

    def switch_read_mode(self, force=False):
        """
            Show a readable version of page if available.
            If in read mode, switch back to page
            If force, always go in read mode
            @param force as bool
        """
        show = not self.__in_read_mode or force
        if show and self.__readable_content:
            self.__in_read_mode = True
            html = "<html><head>\
                    <style type='text/css'>\
                    *:not(img) {font-size: %s;\
                        background-color: #333333;\
                        color: #e6e6e6;\
                        margin-left: auto;\
                        margin-right: auto;\
                        width: %s}\
                    </style></head>" % (self.__document_font_size,
                                        self.get_allocated_width() / 1.5)
            html += "<title>%s</title>" % self.get_title()
            html += self.__readable_content
            html += "</html>"
            GLib.idle_add(self.load_html, html, None)
        else:
            self.__in_read_mode = False
            self.load_uri(self.__loaded_uri)

    @property
    def readable(self):
        """
            Readable status
            @return (in_read_mode, content) as (bool, str)
        """
        return (self.__in_read_mode, self.__readable_content)

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
    def __init(self):
        """
            Init WebView
        """
        self.__in_read_mode = False
        self.__readable_content = ""
        self.__js_timeout = None
        self.__cancellable = Gio.Cancellable()
        self.__input_source = Gdk.InputSource.MOUSE
        self.__loaded_uri = ""
        self.__document_font_size = "14pt"
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.connect("scroll-event", self.__on_scroll_event)
        settings = self.get_settings()
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
        self.set_settings(settings)
        self.connect("decide-policy", self.__on_decide_policy)
        self.connect("submit-form", self.__on_submit_form)
        self.connect("run-as-modal", self.__on_run_as_modal)
        self.connect("load-changed", self.__on_load_changed)
        # We launch Readability.js at page loading finished
        # As Webkit2GTK doesn't allow us to get content from python
        # It sets title with content for one shot, so try to get it here
        self.connect("notify::title", self.__on_title_changed)
        self.connect("notify::uri", self.__on_uri_changed)
        self.get_context().connect("download-started",
                                   self.__on_download_started)
        self.update_zoom_level()

    def __set_system_fonts(self, settings):
        """
            Set system font
            @param settings as WebKit2.Settings
        """
        system = Gio.Settings.new("org.gnome.desktop.interface")
        document_font_name = system.get_value("document-font-name").get_string(
                                                                              )
        self.__document_font_size = document_font_name[-2:] + "pt"
        settings.set_property(
                        "monospace-font-family",
                        system.get_value("monospace-font-name").get_string())
        settings.set_property(
                        "sans-serif-font-family",
                        system.get_value("document-font-name").get_string())
        settings.set_property(
                        "serif-font-family",
                        system.get_value("font-name").get_string())

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
        settings = self.get_settings()
        settings.set_property("enable-smooth-scrolling",
                              source != Gdk.InputSource.MOUSE)
        self.set_settings(settings)

    def __on_uri_changed(self, view, uri):
        """
            Clear readable version
            @param view as WebKit2.WebView
            @param uri as GParamSpec
        """
        if view.get_uri() != "about:blank":
            self.__readable_content = ""
            self.__in_read_mode = False
            self.__js_timeout = None

    def __on_title_changed(self, webview, event):
        """
            We launch Readability.js at page loading finished.
            As Webkit2GTK doesn't allow us to get content from python,
            it sets title with content for one shot, so try to get it here
            @param webview as WebKit2.WebView
            @param event as  GParamSpec
        """
        if event.name != "title":
            return True
        title = webview.get_title()
        if title.startswith("@&$%ù²"):
            self.__readable_content = title.replace("@&$%ù²", "")
            self.emit("readable")
            return True
        else:
            if self.__js_timeout is None and not self.__in_read_mode:
                self.__js_timeout = GLib.timeout_add(
                                 2000,
                                 self.run_javascript_from_gresource,
                                 '/org/gnome/Eolie/Readability.js', None, None)
        return False

    def __on_run_as_modal(self, view):
        """
        """
        print("WebView::__on_run_as_modal(): TODO")

    def __on_scroll_event(self, widget, event):
        """
            Adapt scroll speed to device
            @param widget as WebKit2.WebView
            @param event as Gdk.EventScroll
        """
        source = event.get_source_device().get_source()
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

    def __on_load_changed(self, view, event):
        """
            Update sidebar/urlbar
            @param view as WebView
            @param event as WebKit2.LoadEvent
        """
        if event == WebKit2.LoadEvent.STARTED:
            self.set_setting("auto-load-images",
                             not El().settings.get_value("imgblock"))

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
                self.emit("new-page", uri, True)
                decision.ignore()
                return True
            else:
                decision.use()
                return False
        elif mouse_button == 1:
            self.__loaded_uri = uri
            if decision_type == WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION:
                self.emit("new-page", uri, True)
                decision.ignore()
                return True
            else:
                decision.use()
                return False
        else:
            self.emit("new-page", uri, False)
            decision.ignore()
            return True
