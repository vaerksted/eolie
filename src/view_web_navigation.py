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
from time import time

from eolie.dbus_helper import DBusHelper
from eolie.define import El, ADBLOCK_JS, FUA
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
        "new-page":  (GObject.SignalFlags.RUN_FIRST, None, (str, bool)),
        "save-password": (GObject.SignalFlags.RUN_FIRST, None, (str,
                                                                str,
                                                                str)),
    }

    for signal in gsignals:
        args = gsignals[signal]
        GObject.signal_new(signal, WebKit2.WebView,
                           args[0], args[1], args[2])

    __FUA_FIX = "outlook.live.com"

    def __init__(self):
        """
            Init navigation
        """
        self.__js_timeout = None
        self.__title = ""
        self.__readable_content = ""
        self.__popups = []
        self.__loaded_uri = ""
        self.__insecure_content_detected = False
        self.connect("decide-policy", self.__on_decide_policy)
        self.connect("insecure-content-detected",
                     self.__on_insecure_content_detected)
        self.connect("submit-form", self.__on_submit_form)
        self.connect("run-as-modal", self.__on_run_as_modal)
        self.connect("permission_request", self.__on_permission_request)
        self.connect("load-changed", self.__on_load_changed)
        # We launch Readability.js at page loading finished
        # As Webkit2GTK doesn't allow us to get content from python
        # It sets title with content for one shot, so try to get it here
        self.connect("notify::title", self.__on_title_changed)
        self.connect("notify::uri", self.__on_uri_changed)

    def load_uri(self, uri):
        """
            Load uri
            @param uri as str
        """
        if uri == "about:blank":
            WebKit2.WebView.load_plain_text(self, "")
            self.__loaded_uri = uri
            return
        parsed = urlparse(uri)
        # We are not a ftp browser, fall back to env
        if parsed.scheme == "ftp":
            argv = [get_ftp_cmd(), uri, None]
            GLib.spawn_sync(None, argv, None,
                            GLib.SpawnFlags.SEARCH_PATH, None)
            return
        elif parsed.scheme == "javascript":
            uri = GLib.uri_unescape_string(uri, None)
            self.run_javascript(uri.replace("javascript:", ""), None, None)
            return
        elif parsed.scheme not in ["http", "https", "populars", "accept"]:
            uri = "http://" + uri
        # Reset bad tls certificate
        elif parsed.scheme != "accept":
            self.reset_bad_tls()
            self.__insecure_content_detected = False
        self.__loaded_uri = uri
        self.emit("uri-changed", uri)
        WebKit2.WebView.load_uri(self, uri)

    def add_popup(self, webview):
        """
            Add webview to popups
            @webview as WebView
        """
        self.__popups.append(webview)

    @property
    def popups(self):
        """
            Get popups
            @return [WebView]
        """
        return self.__popups

    @property
    def readable_content(self):
        """
            Readable content
            @return content as str
        """
        return self.__readable_content

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
    def __update_user_agent(self, netloc):
        """
            Update user agent for some sites
            @param netloc as str
        """
        if netloc in self.__FUA_FIX:
            settings = self.get_settings()
            settings.set_property("user-agent", FUA)

    def __get_forms(self, page_id, request):
        """
            Read request for authentification
            @param page_id as int
            @param request as WebKit2.FormSubmissionRequest
        """
        helper = DBusHelper()
        helper.call("GetForms",
                    GLib.Variant("(i)", (page_id,)),
                    self.__on_get_forms, request)

    def __on_get_forms(self, source, result, request):
        """
            Set forms value
            @param source as GObject.Object
            @param result as Gio.AsyncResult
            @param request as WebKit2.FormSubmissionRequest
        """
        try:
            (username, password) = source.call_finish(result)[0]
            if not username or not password:
                return
            parsed = urlparse(self.get_uri())
            self.emit("save-password", username, password, parsed.netloc)
            request.submit()
        except Exception as e:
            print("WebView::__on_get_forms():", e)

    def __on_submit_form(self, view, request):
        """
            Check for auth forms
            @param view as WebKit2.WebView
            @param request as WebKit2.FormSubmissionRequest
        """
        if self.private:
            return
        self.__get_forms(view.get_page_id(), request)

    def __on_run_as_modal(self, view):
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
            if self.__insecure_content_detected or self.private:
                request.deny()
            else:
                request.allow()
        elif isinstance(request, WebKit2.NotificationPermissionRequest):
            # Use can use Gnome Shell notification policy
            request.allow()

    def __on_uri_changed(self, view, uri):
        """
            Clear readable context and title
            @param view as WebKit2.WebView
            @param uri as GParamSpec
        """
        self.__readable_content = ""
        self.__title = ""
        if view.get_uri() != "about:blank":
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
            if self.__js_timeout is None:
                self.__js_timeout = GLib.timeout_add(
                                 2000,
                                 self.run_javascript_from_gresource,
                                 '/org/gnome/Eolie/Readability.js', None, None)

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
            if self.can_show_mime_type(mime_type):
                decision.use()
            else:
                decision.download()
            return False

        navigation_action = decision.get_navigation_action()
        uri = navigation_action.get_request().get_uri()
        mouse_button = navigation_action.get_mouse_button()
        parsed = urlparse(uri)
        if parsed.scheme not in ["http", "https", "about",
                                 "populars", "accept"]:
            try:
                Gtk.show_uri(None, uri, int(time()))
            except Exception as e:
                print("WebViewNavigation::__on_decide_policy()", e)
            decision.ignore()
        elif mouse_button == 0:
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
            elif navigation_action.get_modifiers() &\
                    Gdk.ModifierType.CONTROL_MASK:
                self.emit("new-page", uri, False)
                decision.ignore()
                return True
            else:
                decision.use()
                return False
        else:
            self.emit("new-page", uri, False)
            decision.ignore()
            return True

    def __on_load_changed(self, view, event):
        """
            Update sidebar/urlbar
            @param view as WebView
            @param event as WebKit2.LoadEvent
        """
        uri = view.get_uri()
        parsed = urlparse(uri)
        if event == WebKit2.LoadEvent.STARTED:
            # Destroy current popups
            for popup in self.__popups:
                popup.destroy()
            El().download_manager.remove_video_for_page(view.get_page_id())
            self.emit("uri-changed", uri)
            self.__title = ""
        if event == WebKit2.LoadEvent.COMMITTED:
            self.__update_user_agent(parsed.netloc)
            if El().pishing.is_pishing(uri):
                self._show_pishing_error(uri)
            else:
                self.emit("uri-changed", uri)
                exception = El().image_exceptions.find(
                                        parsed.netloc) or\
                    El().image_exceptions.find(
                                        parsed.netloc + parsed.path)
                imgblock = El().settings.get_value("imgblock")
                self.set_setting("auto-load-images",
                                 not imgblock or exception)
                self.update_zoom_level()
            # Js adblocker
            if El().settings.get_value("adblock"):
                exception = El().adblock_exceptions.find(
                                        parsed.netloc) or\
                            El().adblock_exceptions.find(
                                        parsed.netloc + parsed.path)
                if exception:
                    return
                # We need to send a title if non exists
                if not self.__title:
                    self.__title = view.get_title()
                    if not self.__title:
                        self.__title = view.get_uri()
                    self.emit("title-changed", self.__title)
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
                        print(js)
                        break
        elif event == WebKit2.LoadEvent.FINISHED:
            pass
