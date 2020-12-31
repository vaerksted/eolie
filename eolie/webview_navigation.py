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

from gi.repository import GLib, Gtk, Gio, WebKit2, Gdk

from gettext import gettext as _
from urllib.parse import urlparse
from time import time

from eolie.define import App, LoadingType, LoadingState
from eolie.utils import get_ftp_cmd, emit_signal
from eolie.logger import Logger


class WebViewNavigation:
    """
        Implement WebView navigation (uri, title, readable, ...)
        Should be inherited by a WebView
    """

    __MIMES = ["text/html", "text/xml", "application/xhtml+xml",
               "x-scheme-handler/http", "x-scheme-handler/https",
               "multipart/related", "application/x-mimearchive",
               "application/x-extension-html"]

    def __init__(self):
        """
            Init navigation
        """
        self.__loaded_uri = None
        self.__insecure_content_detected = False
        self.connect("decide-policy", self.__on_decide_policy)
        self.connect("insecure-content-detected",
                     self.__on_insecure_content_detected)
        self.connect("run-as-modal", self.__on_run_as_modal)
        self.connect("permission_request", self.__on_permission_request)

    def load_uri(self, uri):
        """
            Load uri
            @param uri as str
        """
        parsed = urlparse(uri)
        # If not an URI, start a search
        is_uri = parsed.scheme in ["about", "http",
                                   "https", "file", "populars"]
        if not is_uri and\
                not uri.startswith("/") and\
                App().search.is_search(uri):
            uri = App().search.get_search_uri(uri)
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
                # To bypass popup blocker
                self._last_click_time = time()
                uri = GLib.uri_unescape_string(uri, None)
                self.run_javascript(uri.replace("javascript:", ""), None, None)
            elif parsed.scheme not in ["http", "https", "file",
                                       "populars", "accept"]:
                uri = "http://" + uri
            # Reset bad tls certificate
            if parsed.scheme != "accept":
                self.reset_bad_tls()
                self.__insecure_content_detected = False
            self.stop_loading()
            self.set_uri(uri)
            self.__loaded_uri = self.uri
            GLib.idle_add(WebKit2.WebView.load_uri, self, uri)

    @property
    def loaded_uri(self):
        """
            Get loaded uri
            @return str/None
        """
        return self.__loaded_uri

#######################
# PROTECTED           #
#######################
    def _set_user_agent(self, uri):
        """
            Set user agent for uri
            @param uri as str
        """
        user_agent = App().websettings.get("user_agent", uri)
        settings = self.get_settings()
        if user_agent:
            settings.set_user_agent(user_agent)
        else:
            settings.set_user_agent_with_application_details("Eolie",
                                                             None)

    def _on_load_changed(self, webview, event):
        """
            Update internals
            @param webview as WebView
            @param event as WebKit2.LoadEvent
        """
        parsed = urlparse(webview.uri)
        if event == WebKit2.LoadEvent.STARTED:
            self._loading_state = LoadingState.LOADING
        elif event == WebKit2.LoadEvent.COMMITTED:
            if parsed.scheme in ["http", "https"]:
                emit_signal(self, "title-changed", webview.uri)
                self.update_zoom_level()
                self.update_sound_policy()
        elif event == WebKit2.LoadEvent.FINISHED:
            if self._loading_state != LoadingState.STOPPED:
                self._loading_state = LoadingState.NONE
            App().history.set_page_state(self.uri)
            self.__update_bookmark_metadata(self.uri)
            self.update_spell_checking(self.uri)
            self.run_javascript_from_gresource(
                "/org/gnome/Eolie/Extensions.js", None, None)
            self.run_javascript_from_gresource(
                "/org/gnome/Eolie/javascript/HandleInput.js", None, None)
            if App().show_tls:
                try:
                    from OpenSSL import crypto
                    from datetime import datetime
                    (valid, tls, errors) = webview.get_tls_info()
                    if tls is not None:
                        Logger.info("***************************************"
                                    "***************************************")
                        cert_pem = tls.get_property("certificate-pem")
                        cert = crypto.load_certificate(crypto.FILETYPE_PEM,
                                                       cert_pem)
                        subject = cert.get_subject()
                        Logger.info("CN: %s", subject.CN)
                        start_bytes = cert.get_notBefore()
                        end_bytes = cert.get_notAfter()
                        start = datetime.strptime(start_bytes.decode("utf-8"),
                                                  "%Y%m%d%H%M%SZ")
                        end = datetime.strptime(end_bytes.decode("utf-8"),
                                                "%Y%m%d%H%M%SZ")
                        Logger.info("Valid from %s to %s", (start, end))
                        Logger.info("Serial number: %s",
                                    cert.get_serial_number())
                        Logger.info(cert_pem)
                        Logger.info("***************************************"
                                    "***************************************")
                except Exception as e:
                    Logger.info("Please install OpenSSL python support: %s", e)

#######################
# PRIVATE             #
#######################
    def __update_bookmark_metadata(self, uri):
        """
            Update bookmark access time/popularity
            @param uri as str
        """
        if App().bookmarks.get_id(uri) is not None:
            App().bookmarks.set_access_time(uri, round(time(), 2))
            App().bookmarks.set_more_popular(uri)

    def __on_run_as_modal(self, webview):
        Logger.info("WebView::__on_run_as_modal(): TODO")

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
        def on_allow_notifications(parsed):
            values = list(App().settings.get_value("notification-domains"))
            values.append("%s;%s" % (parsed.scheme, parsed.netloc))
            App().settings.set_value("notification-domains",
                                     GLib.Variant("as", values))
            request.allow()

        if isinstance(request, WebKit2.GeolocationPermissionRequest):
            if self.is_ephemeral:
                request.deny()
            else:
                uri = webview.uri
                self.window.toolbar.title.show_geolocation(uri, request)
        elif isinstance(request, WebKit2.NotificationPermissionRequest):
            parsed = urlparse(webview.uri)
            from eolie.container_notification import ContainerNotification
            notification = ContainerNotification(
                _("Allow notifications for %s") % parsed.netloc,
                [_("Allow")],
                [lambda: on_allow_notifications(parsed)])
            self.window.container.overlay.add_overlay(notification)
            notification.show()
            notification.set_reveal_child(True)
        return True

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
                return False
            elif parsed.scheme == "file":
                f = Gio.File.new_for_uri(uri)
                info = f.query_info("standard::type",
                                    Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS,
                                    None)
                if info.get_file_type() == Gio.FileType.REGULAR:
                    try:
                        Gtk.show_uri_on_window(self.window,
                                               uri,
                                               Gtk.get_current_event_time())
                    except Exception as e:
                        Logger.error("""WebViewNavigation::
                                        __on_decide_policy(): %s""", e)
                    decision.ignore()
                    return True
                else:
                    decision.use()
                    return False
            elif self.can_show_mime_type(mime_type):
                decision.use()
                return False
            else:
                decision.download()
                return True

        navigation_action = decision.get_navigation_action()
        navigation_uri = navigation_action.get_request().get_uri()
        mouse_button = navigation_action.get_mouse_button()
        parsed_navigation = urlparse(navigation_uri)
        self.clear_text_entry()
        if parsed_navigation.scheme not in ["http", "https", "file", "about",
                                            "populars", "accept"]:
            try:
                Gtk.show_uri_on_window(self.window,
                                       navigation_uri,
                                       Gtk.get_current_event_time())
            except Exception as e:
                Logger.error("WebViewNavigation::__on_decide_policy(): %s", e)
            decision.ignore()
        elif mouse_button == 0:
            # Prevent opening empty pages
            if navigation_uri == "about:blank":
                self.reset_last_click_event()
                decision.use()
                return False
            elif decision_type == WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION:
                decision.use()
                return False
            else:
                decision.use()
                return False
        elif mouse_button == 1:
            modifiers = navigation_action.get_modifiers()
            if decision_type == WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION:
                decision.use()
                return False
            elif modifiers == Gdk.ModifierType.CONTROL_MASK:
                self.new_page(navigation_uri, LoadingType.BACKGROUND)
                decision.ignore()
                return True
            elif modifiers == Gdk.ModifierType.SHIFT_MASK:
                self.new_page(navigation_uri, LoadingType.POPOVER)
                decision.ignore()
                return True
            else:
                self.__loaded_uri = navigation_uri.rstrip("/")
                emit_signal(self, "title-changed", navigation_uri)
                decision.use()
                return False
        else:
            self.new_page(navigation_uri, LoadingType.BACKGROUND)
            decision.ignore()
            return True
