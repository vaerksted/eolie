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

from gi.repository import WebKit2, GObject, Gio, GLib, Gdk

import ctypes
from gettext import gettext as _
from urllib.parse import urlparse

from eolie.define import El, LOGINS, PASSWORDS
from eolie.utils import get_ftp_cmd, debug


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
        "title-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "new-page":  (GObject.SignalFlags.RUN_FIRST, None, (str, bool)),
        "save-password": (GObject.SignalFlags.RUN_FIRST, None, (str,
                                                                str,
                                                                str)),
    }

    def __init__(self, private):
        """
            Init view
            @param private as bool
        """
        WebKit2.WebView.__init__(self)
        self.__init(private)

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
            "title-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
            "save-password": (GObject.SignalFlags.RUN_FIRST, None, (str,
                                                                    str,
                                                                    str))
        }
        if "readable" not in GObject.signal_list_names(WebKit2.WebView):
            for signal in gsignals:
                args = gsignals[signal]
                GObject.signal_new(signal, WebKit2.WebView,
                                   args[0], args[1], args[2])
        view.__class__ = WebView
        view.__init(related.private)
        return view

    def load_uri(self, uri):
        """
            Load uri
            @param uri as str
        """
        self.__cancellable.cancel()
        self.__cancellable.reset()
        parsed = urlparse(uri)
        # We are not a ftp browser, fall back to env
        if parsed.scheme == "ftp":
            argv = [get_ftp_cmd(), uri, None]
            GLib.spawn_sync(None, argv, None,
                            GLib.SpawnFlags.SEARCH_PATH, None)
            return
        elif parsed.scheme not in ["http", "https", "file",
                                   "populars", "accept"]:
            uri = "http://" + uri
        # Reset bad tls certificate
        elif parsed.scheme != "accept":
            self.__bad_tls = None
            self.__insecure_content_detected = False
        self.__loaded_uri = uri
        WebKit2.WebView.load_uri(self, uri)

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

    def update_zoom_level(self):
        """
            Update zoom level
        """
        try:
            parsed = urlparse(self.get_uri())
            if parsed.netloc in El().zoom_levels.keys():
                zoom_level = El().zoom_levels[parsed.netloc]
            else:
                zoom_level = 100
            zoom_level *= self.get_toplevel().zoom_level
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

    @property
    def readable(self):
        """
            Readable status
            @return (in_read_mode, content) as (bool, str)
        """
        return (self.__in_read_mode, self.__readable_content)

    @property
    def private(self):
        """
            True if view is private
            @return bool
        """
        return self.__private

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
    def __init(self, private):
        """
            Init WebView
            @param private as bool
        """
        self.__private = private
        self.__in_read_mode = False
        self.__readable_content = ""
        self.__js_timeout = None
        self.__cancellable = Gio.Cancellable()
        self.__input_source = Gdk.InputSource.MOUSE
        self.__loaded_uri = ""
        self.__title = ""
        self.__document_font_size = "14pt"
        self.__bad_tls = None  # Keep bad TLS certificate
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
        settings.set_property("auto-load-images", True)
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
        settings.set_property("enable-private-browsing", private)
        settings.set_property("javascript-can-access-clipboard", True)
        settings.set_property("javascript-can-open-windows-automatically",
                              True)
        settings.set_property("media-playback-allows-inline", True)
        self.set_settings(settings)
        self.connect("decide-policy", self.__on_decide_policy)
        self.connect("insecure-content-detected",
                     self.__on_insecure_content_detected)
        self.connect("submit-form", self.__on_submit_form)
        self.connect("run-as-modal", self.__on_run_as_modal)
        self.connect("web-process-crashed", self.__on_web_process_crashed)
        self.connect("permission_request", self.__on_permission_request)
        self.connect("load-changed", self.__on_load_changed)
        self.connect("load-failed", self.__on_load_failed)
        self.connect("load-failed-with-tls-errors", self.__on_load_failed_tls)
        # We launch Readability.js at page loading finished
        # As Webkit2GTK doesn't allow us to get content from python
        # It sets title with content for one shot, so try to get it here
        self.connect("notify::title", self.__on_title_changed)
        self.connect("notify::uri", self.__on_uri_changed)

        context = self.get_context()
        if private:
            context.set_cache_model(WebKit2.CacheModel.DOCUMENT_VIEWER)
            cookie_manager = context.get_cookie_manager()
            cookie_manager.set_accept_policy(
                                     El().settings.get_enum("cookie-storage"))
            cookie_manager.set_persistent_storage(
                                        "",
                                        WebKit2.CookiePersistentStorage.SQLITE)
        context.register_uri_scheme("populars", self.__on_populars_scheme)
        context.register_uri_scheme("internal", self.__on_internal_scheme)
        context.register_uri_scheme("accept", self.__on_accept_scheme)
        context.get_security_manager().register_uri_scheme_as_local("populars")
        context.connect("download-started", self.__on_download_started)

    def __check_for_network(self, uri):
        """
            Load uri when network is available
        """
        if Gio.NetworkMonitor.get_default().get_network_available():
            self.load_uri(uri)
        else:
            return True

    def __set_system_fonts(self, settings):
        """
            Set system font
            @param settings as WebKit2.Settings
        """
        system = Gio.Settings.new("org.gnome.desktop.interface")
        document_font_name = system.get_value("document-font-name").get_string(
                                                                              )
        self.__document_font_size = str(
                                    int(document_font_name[-2:]) * 1.3) + "pt"
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
            found = False
            if not password:
                for search in PASSWORDS:
                    if name.lower().find(search) != -1:
                        password = ctypes.string_at(v).decode("utf-8")
                        found = True
                        break
                if found:
                    continue
            if not username:
                for search in LOGINS:
                    if name.lower().find(search) != -1:
                        username = ctypes.string_at(v).decode("utf-8")
                        break
            if username and password:
                break
        if username and password:
            auth = True
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

    def __on_insecure_content_detected(self, webview, event):
        """
            @param webview as WebView
            @param event as WebKit2.InsecureContentEvent
        """
        self.__insecure_content_detected = True

    def __on_permission_request(self, webview, request):
        """
            Handle Webkit permissions
            @param webview as WebKit2.WebView
            @param request as WebKit2.PermissionRequest
        """
        if isinstance(request, WebKit2.GeolocationPermissionRequest):
            if self.__insecure_content_detected or self.__private:
                request.deny()
            else:
                request.allow()

    def __on_populars_scheme(self, request):
        """
            Show populars web pages
            @param request as WebKit2.URISchemeRequest
        """
        items = []
        # First from bookmarks
        for (bookmark_id, title, uri) in El().bookmarks.get_populars(20):
            items.append((title, uri))
        # Then from history
        more = 20 - len(items)
        if more > 0:
            items += El().history.search("", more)
        start = Gio.File.new_for_uri("resource:///org/gnome/Eolie/start.html")
        end = Gio.File.new_for_uri("resource:///org/gnome/Eolie/end.html")
        (status, start_content, tag) = start.load_contents(None)
        (status, end_content, tag) = end.load_contents(None)
        # Update start
        html_start = start_content.decode("utf-8")
        html_start = html_start.replace("@TITLE@", _("Popular pages"))
        for (title, uri) in items:
            f = Gio.File.new_for_path(El().art.get_path(uri, "preview"))
            if not f.query_exists():
                continue
            path = El().art.get_path(uri, "start")
            html_start += '<a class="child" title="%s" href="%s">' % (title,
                                                                      uri)
            html_start += '<img src="file://%s"></img>' % path
            html_start += '<div class="caption">%s</div></a>' % title
        html = html_start.encode("utf-8") + end_content
        stream = Gio.MemoryInputStream.new_from_data(html)
        request.finish(stream, -1, "text/html")

    def __on_internal_scheme(self, request):
        """
            Load an internal resource
            @param request as WebKit2.URISchemeRequest
        """
        # We use internal:/ because resource:/ is already used by WebKit2
        uri = request.get_uri().replace("internal:/", "resource:/")
        f = Gio.File.new_for_uri(uri)
        request.finish(f.read(), -1, "image/svg+xml")

    def __on_accept_scheme(self, request):
        """
            Accept certificate for uri
            @param request as WebKit2.URISchemeRequest
        """
        if self.__bad_tls is None:
            return
        parsed = urlparse(request.get_uri())
        self.get_context().allow_tls_certificate_for_host(self.__bad_tls,
                                                          parsed.netloc)
        self.load_uri("https://" + parsed.netloc + parsed.path)

    def __on_uri_changed(self, view, uri):
        """
            Clear readable context and title
            @param view as WebKit2.WebView
            @param uri as GParamSpec
        """
        self.__title = ""
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
            @param event as GParamSpec
        """
        if event.name != "title":
            return
        title = webview.get_title()
        if not title or title == self.__title:
            return
        if title.startswith("@&$%ù²"):
            self.__readable_content = title.replace("@&$%ù²", "")
            self.emit("readable")
            return
        else:
            self.__title = title
            self.emit("title-changed", title)
            if self.__js_timeout is None and not self.__in_read_mode:
                self.__js_timeout = GLib.timeout_add(
                                 2000,
                                 self.run_javascript_from_gresource,
                                 '/org/gnome/Eolie/Readability.js', None, None)

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
        if self.__private:
            return
        (auth, username, password) = self.__read_auth_request(request)
        if not auth:
            return
        parsed = urlparse(view.get_uri())
        self.emit("save-password", username, password, parsed.netloc)
        request.submit()

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
            self.__title = ""
        if event == WebKit2.LoadEvent.COMMITTED:
            self.update_zoom_level()
        elif event == WebKit2.LoadEvent.FINISHED:
            if El().settings.get_value("adblock"):
                uri = view.get_uri()
                # We need to send a title if non exists
                if not self.__title:
                    self.__title = view.get_title()
                    if not self.__title:
                        self.__title = view.get_uri()
                    self.emit("title-changed", self.__title)
                for site in ["facebook.com"]:
                    if uri.find(site) != -1:
                        parsed = urlparse(uri)
                        exception = El().adblock.is_an_exception(
                                        parsed.netloc) or\
                            El().adblock.is_an_exception(
                                        parsed.netloc + parsed.path)
                        if not exception:
                            self.run_javascript_from_gresource(
                                '/org/gnome/Eolie/%s_adblock.js' % site,
                                None, None)

    def __on_load_failed(self, view, event, uri, error):
        """
            Show error page
            @param view as WebKit2.WebView
            @param event as WebKit2.LoadEvent
            @param uri as str
            @param error as GLib.Error
        """
        network_available = Gio.NetworkMonitor.get_default(
                                                      ).get_network_available()
        # Ignore all others errors
        if error.code not in [2, 4]:
            return False
        f = Gio.File.new_for_uri("resource:///org/gnome/Eolie/error.css")
        (status, css_content, tag) = f.load_contents(None)
        css = css_content.decode("utf-8")
        # Hide reload button if network is down
        if network_available:
            css = css.replace("@button@", "")
        else:
            css = css.replace("@button@", "display: none")
        f = Gio.File.new_for_uri("resource:///org/gnome/Eolie/error.html")
        (status, content, tag) = f.load_contents(None)
        html = content.decode("utf-8")
        if network_available:
            title = _("Failed to load this web page")
            detail = _("It may be temporarily inaccessible or moved"
                       " to a new address.<br/>"
                       "You may wish to verify that your internet"
                       " connection is working correctly.")
            icon = "dialog-information-symbolic.svg"
        else:
            title = _("Network not available")
            detail = _("Check your network connection")
            icon = "network-offline-symbolic.svg"
        html = html % (title,
                       css,
                       "load_uri('%s')" % uri,
                       "internal:///org/gnome/Eolie/" + icon,
                       title,
                       _("%s is not available") % uri,
                       detail,
                       "suggested-action",
                       _("Retry"))
        self.load_html(html, None)
        if network_available:
            # Remove preview and start as should be wrong
            for suffix in ["preview", "start"]:
                path = El().art.get_path(uri, suffix)
                f = Gio.File.new_for_path(path)
                try:
                    f.delete()
                except:
                    pass
        else:
            GLib.timeout_add(1000, self.__check_for_network, uri)
        return True

    def __on_load_failed_tls(self, view, uri, certificate, errors):
        """
            Show TLS error page
            @param view as WebKit2.WebView
            @param certificate as Gio.TlsCertificate
            @parma errors as Gio.TlsCertificateFlags
        """
        self.__bad_tls = certificate
        f = Gio.File.new_for_uri("resource:///org/gnome/Eolie/error.css")
        (status, css_content, tag) = f.load_contents(None)
        css = css_content.decode("utf-8")
        f = Gio.File.new_for_uri("resource:///org/gnome/Eolie/error.html")
        (status, content, tag) = f.load_contents(None)
        html = content.decode("utf-8")
        if errors == Gio.TlsCertificateFlags.BAD_IDENTITY:
            error = _("The certificate does not match this website")
        elif errors == Gio.TlsCertificateFlags.EXPIRED:
            error = _("The certificate has expired")
        elif errors == Gio.TlsCertificateFlags.UNKNOWN_CA:
            error = _("The signing certificate authority is not known")
        elif errors == Gio.TlsCertificateFlags.GENERIC_ERROR:
            error = _("The certificate contains errors")
        elif errors == Gio.TlsCertificateFlags.REVOKED:
            error = _("The certificate has been revoked")
        elif errors == Gio.TlsCertificateFlags.INSECURE:
            error = _("The certificate is signed using"
                      " a weak signature algorithm")
        elif errors == Gio.TlsCertificateFlags.NOT_ACTIVATED:
            error = _("The certificate activation time is still in the future")
        else:
            error = _("The identity of this website has not been verified")
        html = html % (_("Connection is not secure"),
                       css,
                       "load_uri('%s')" % uri.replace("https://",
                                                      "accept://"),
                       "internal:///org/gnome/Eolie/"
                       "dialog-warning-symbolic.svg",
                       _("Connection is not secure"),
                       error,
                       _("This does not look like the real %s.<br/>"
                         "Attackers might be trying to steal or alter"
                         " information going to or from this site"
                         " (for example, private messages, credit card"
                         " information, or passwords).") % uri,
                       "destructive-action",
                       _("Accept Risk and Proceed"))
        self.load_html(html, None)
        return True

    def __on_web_process_crashed(self, view):
        """
            We just crashed :-(
            @param view as WebKit2.WebView
        """
        print("WebView::__on_web_process_crashed():", view)

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
