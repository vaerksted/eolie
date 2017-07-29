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

from gi.repository import GLib, Gtk, Gio, GObject, WebKit2, Gdk

from urllib.parse import urlparse

from eolie.define import El, ADBLOCK_JS, USER_AGENT
from eolie.utils import get_ftp_cmd


class WebViewNavigation:
    """
        Implement WebView navigation (uri, title, readable, ...)
        Should be inherited by a WebView
    """

    gsignals = {
        "readable": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "title-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "uri-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "new-page":  (GObject.SignalFlags.RUN_FIRST, None, (str, int)),
        "save-password": (GObject.SignalFlags.RUN_FIRST, None, (str,
                                                                str,
                                                                str,
                                                                str,
                                                                str,
                                                                str)),
    }

    for signal in gsignals:
        args = gsignals[signal]
        GObject.signal_new(signal, WebKit2.WebView,
                           args[0], args[1], args[2])

    __MIMES = ["text/html", "text/xml", "application/xhtml+xml",
               "x-scheme-handler/http", "x-scheme-handler/https",
               "multipart/related", "application/x-mimearchive"]

    def __init__(self):
        """
            Init navigation
        """
        self.__js_timeout = None
        self.__title = ""
        self.__popups = []
        self.__js_load = False
        self.__related_uri = None
        self.__insecure_content_detected = False
        self.connect("decide-policy", self.__on_decide_policy)
        self.connect("insecure-content-detected",
                     self.__on_insecure_content_detected)
        self.connect("run-as-modal", self.__on_run_as_modal)
        self.connect("permission_request", self.__on_permission_request)
        self.connect("load-changed", self.__on_load_changed)
        # We launch Readability.js at page loading finished
        # As Webkit2GTK doesn't allow us to get content from python
        # It sets title with content for one shot, so try to get it here
        self.connect("notify::title", self.__on_title_changed)
        self.connect("notify::uri", self.__on_uri_changed)
        settings = self.get_settings()
        settings.set_property("user-agent", USER_AGENT)

    def load_uri(self, uri):
        """
            Load uri
            @param uri as str
        """
        self._error = None
        # If not an URI, start a search
        parsed = urlparse(uri)
        is_uri = parsed.scheme in ["about", "http",
                                   "https", "file", "populars"]
        if not is_uri and\
                not uri.startswith("/") and\
                El().search.is_search(uri):
            uri = El().search.get_search_uri(uri)

        self.__related_uri = uri
        parsed = urlparse(uri)
        if uri == "about:blank":
            WebKit2.WebView.load_plain_text(self, "")
        # We are not a ftp browser, fall back to env
        elif parsed.scheme == "ftp":
            argv = [get_ftp_cmd(), uri, None]
            GLib.spawn_sync(None, argv, None,
                            GLib.SpawnFlags.SEARCH_PATH, None)
        else:
            if uri.startswith("/"):
                uri = "file://" + uri
            elif parsed.scheme == "javascript":
                self.__js_load = True
                uri = GLib.uri_unescape_string(uri, None)
                self.run_javascript(uri.replace("javascript:", ""), None, None)
            elif parsed.scheme not in ["http", "https", "file",
                                       "populars", "accept"]:
                uri = "http://" + uri
            # Reset bad tls certificate
            if parsed.scheme != "accept":
                self.reset_bad_tls()
                self.__insecure_content_detected = False
            self.emit("uri-changed", uri)
            WebKit2.WebView.load_uri(self, uri)

    def add_popup(self, webview):
        """
            Add webview to popups
            @webview as WebView
        """
        self.__popups.append(webview)

    @property
    def related_uri(self):
        """
            Related uri
            @return str
        """
        return self.__related_uri

    @property
    def js_load(self):
        """
            True if current action was a js execution. Useful when opening
            a related view to check if popup is wanted
        """
        return self.__js_load

    @property
    def popups(self):
        """
            Get popups
            @return [WebView]
        """
        return self.__popups

#######################
# PRIVATE             #
#######################
    def __on_run_as_modal(self, webview):
        """
        """
        print("WebView::__on_run_as_modal(): TODO")

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
            if self.ephemeral:
                request.deny()
            else:
                uri = webview.get_uri()
                self._window.toolbar.title.show_geolocation(uri, request)
        elif isinstance(request, WebKit2.NotificationPermissionRequest):
            # Can use Gnome Shell notification policy
            request.allow()
        return True

    def __on_uri_changed(self, webview, uri):
        """
            Clear readable context and title
            @param webview as WebKit2.WebView
            @param uri as GParamSpec
        """
        self._readable_content = ""
        self.__title = ""
        uri = webview.get_uri()
        self.emit("uri-changed", uri)

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
        self.__title = title
        self.emit("title-changed", title)
        if self.__js_timeout is not None:
            GLib.source_remove(self.__js_timeout)
        self.__js_timeout = GLib.timeout_add(
                             2000,
                             self.__on_js_timeout,
                             "/org/gnome/Eolie/Readability.js")

    def __on_js_timeout(self, path):
        """
            Run js
            @param path as str
        """
        self.__js_timeout = None
        self.run_javascript_from_gresource(path, None, None)

    def __on_decide_policy(self, webview, decision, decision_type):
        """
            Navigation policy
            @param webview as WebKit2.WebView
            @param decision as WebKit2.NavigationPolicyDecision
            @param decision_type as WebKit2.PolicyDecisionType
            @return bool
        """
        # Always accept response
        if decision_type == WebKit2.PolicyDecisionType.RESPONSE:
            response = decision.get_response()
            mime_type = response.props.mime_type
            uri = response.get_uri()
            parsed = urlparse(uri)
            if mime_type in self.__MIMES:
                decision.use()
            elif parsed.scheme == "file":
                f = Gio.File.new_for_uri(uri)
                info = f.query_info("standard::type",
                                    Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS,
                                    None)
                if info.get_file_type() == Gio.FileType.REGULAR:
                    try:
                        Gtk.show_uri_on_window(self._window,
                                               uri,
                                               Gtk.get_current_event_time())
                    except Exception as e:
                        print("WebViewNavigation::__on_decide_policy()", e)
                    decision.ignore()
                else:
                    decision.use()
            elif self.can_show_mime_type(mime_type):
                decision.use()
            else:
                decision.download()
            return False

        navigation_action = decision.get_navigation_action()
        self._navigation_uri = navigation_action.get_request().get_uri()
        mouse_button = navigation_action.get_mouse_button()
        parsed = urlparse(self._navigation_uri)
        self.clear_text_entry()
        if parsed.scheme not in ["http", "https", "file", "about",
                                 "populars", "accept"]:
            try:
                Gtk.show_uri_on_window(self._window,
                                       uri,
                                       Gtk.get_current_event_time())
            except Exception as e:
                print("WebViewNavigation::__on_decide_policy()", e)
            decision.ignore()
        elif mouse_button == 0:
            # Prevent opening empty pages
            if self._navigation_uri != "about:blank" and decision_type ==\
                                  WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION:
                self.emit("new-page",
                          self._navigation_uri,
                          Gdk.WindowType.CHILD)
                decision.ignore()
                return True
            else:
                decision.use()
                return False
        elif mouse_button == 1:
            if decision_type == WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION:
                self.emit("new-page",
                          self._navigation_uri,
                          Gdk.WindowType.CHILD)
                decision.ignore()
                return True
            elif navigation_action.get_modifiers() &\
                    Gdk.ModifierType.CONTROL_MASK:
                self.emit("new-page",
                          self._navigation_uri,
                          Gdk.WindowType.OFFSCREEN)
                decision.ignore()
                return True
            elif navigation_action.get_modifiers() &\
                    Gdk.ModifierType.SHIFT_MASK:
                self.emit("new-page",
                          self._navigation_uri,
                          Gdk.WindowType.SUBSURFACE)
                decision.ignore()
                return True
            else:
                # Special case to force populars view to update related_uri
                if webview.get_uri() == "populars://":
                    self.__related_uri = self._navigation_uri
                El().history.set_page_state(webview.get_uri())
                decision.use()
                self._error = None
                return False
        else:
            self.emit("new-page",
                      self._navigation_uri,
                      Gdk.WindowType.OFFSCREEN)
            decision.ignore()
            return True

    def __on_load_changed(self, webview, event):
        """
            Update sidebar/urlbar
            @param webview as WebView
            @param event as WebKit2.LoadEvent
        """
        self.__js_load = False
        uri = webview.get_uri()
        parsed = urlparse(uri)
        if event == WebKit2.LoadEvent.STARTED:
            self._cancelled = False
            # Destroy current popups
            for popup in self.__popups:
                popup.destroy()
            self.__popups = []
            El().download_manager.remove_videos_for_page(webview.get_page_id())
            self.__title = ""
            # Setup js blocker
            if El().settings.get_value("jsblock"):
                exception = El().js_exceptions.find(
                                        parsed.netloc) or\
                    El().js_exceptions.find(
                                        parsed.netloc + parsed.path)
                print(exception)
                self.set_setting("enable_javascript", exception)
            elif not self.get_settings().get_enable_javascript():
                self.set_setting("enable_javascript", True)
        if event == WebKit2.LoadEvent.COMMITTED:
            if El().phishing.is_phishing(uri):
                self._show_phishing_error(uri)
            else:
                self.update_spell_checking()
                self.update_zoom_level()

                # Setup image blocker
                if El().settings.get_value("imgblock"):
                    exception = El().image_exceptions.find(
                                            parsed.netloc) or\
                        El().image_exceptions.find(
                                            parsed.netloc + parsed.path)
                    self.set_setting("auto-load-images", exception)
                elif not self.get_settings().get_auto_load_images():
                    self.set_setting("auto-load-images", True)

                # Setup ads blocker
                if El().settings.get_value("adblock"):
                    exception = El().adblock_exceptions.find(
                                            parsed.netloc) or\
                                El().adblock_exceptions.find(
                                            parsed.netloc + parsed.path)
                    if exception:
                        return
                    unlocated_netloc = ".".join(parsed.netloc.split(".")[:-1])
                    javascripts = ["adblock_%s.js" % parsed.netloc,
                                   "adblock_%s.js" % unlocated_netloc]
                    for javascript in javascripts:
                        f = Gio.File.new_for_path("%s/%s" % (ADBLOCK_JS,
                                                             javascript))
                        if f.query_exists():
                            (status, content, tag) = f.load_contents(None)
                            js = content.decode("utf-8")
                            self.run_javascript(js, None, None)
                            break
        elif event == WebKit2.LoadEvent.FINISHED:
            if El().show_tls:
                try:
                    from OpenSSL import crypto
                    from datetime import datetime
                    (valid, tls, errors) = webview.get_tls_info()
                    if tls is not None:
                        print("***************************************"
                              "***************************************")
                        cert_pem = tls.get_property("certificate-pem")
                        cert = crypto.load_certificate(crypto.FILETYPE_PEM,
                                                       cert_pem)
                        subject = cert.get_subject()
                        print("CN: %s" % subject.CN)
                        start_bytes = cert.get_notBefore()
                        end_bytes = cert.get_notAfter()
                        start = datetime.strptime(start_bytes.decode("utf-8"),
                                                  "%Y%m%d%H%M%SZ")
                        end = datetime.strptime(end_bytes.decode("utf-8"),
                                                "%Y%m%d%H%M%SZ")
                        print("Valid from %s to %s" % (start, end))
                        print("Serial number: %s" % cert.get_serial_number())
                        print(cert_pem)
                        print("***************************************"
                              "***************************************")
                except Exception as e:
                    print("Please install OpenSSL python support:", e)
