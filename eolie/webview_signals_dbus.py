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

from gi.repository import GLib, Gtk, Gdk

from urllib.parse import urlparse
from time import time
from ctypes import string_at

from eolie.menu_form import FormMenu
from eolie.helper_passwords import PasswordsHelper
from eolie.define import El


class WebViewDBusSignals:
    """
        Handle webview DBus signals
    """

    def __init__(self):
        """
            Init class
        """
        self.__last_click_event = {}
        self.connect("submit-form", self.__on_submit_form)

    @property
    def last_click_event(self):
        """
            Get last click time
            @return {}
        """
        if self.__last_click_event:
            return self.__last_click_event["time"]
        else:
            return 0

#######################
# PROTECTED           #
#######################
    def _on_button_press_event(self, widget, event):
        """
            Store last press event
            @param widget as WebView
            @param event as Gdk.EventButton
        """
        self.__last_click_event = {"x": event.x,
                                   "y": event.y,
                                   "time": time()}

    def _on_map(self, webview):
        """
            Connect all signals
            @param webview as WebView
        """
        page_id = webview.get_page_id()
        El().helper.connect(None,
                            lambda a, b, c, d, e, f:
                            WebViewDBusSignals.__on_signal(self, e, f),
                            page_id)

    def _on_unmap(self, webview):
        """
            Disconnect all signals
            @param webview as WebView
        """
        page_id = webview.get_page_id()
        El().helper.disconnect(page_id)

#######################
# PRIVATE             #
#######################
    def __on_submit_form(self, webview, request):
        """
            Check for auth forms
            @param webview as WebKit2.WebView
            @param request as WebKit2.FormSubmissionRequest
        """
        uri = self._navigation_uri
        if self.ephemeral or not El().settings.get_value("remember-passwords"):
            return
        fields = request.get_text_fields()
        if fields is None:
            return
        forms = []
        for k, v in fields.items():
            name = string_at(k).decode("utf-8")
            value = string_at(v).decode("utf-8")
            forms.append((name, value))
        page_id = webview.get_page_id()
        El().helper.call("GetAuthForms",
                         GLib.Variant("(aasi)", (forms, page_id)),
                         self.__on_get_forms, page_id, request, uri)

    def __on_get_forms(self, source, result, request, uri):
        """
            Set forms value
            @param source as GObject.Object
            @param result as Gio.AsyncResult
            @param request as WebKit2.FormSubmissionRequest
            @param uri as str
        """
        try:
            (user_form_name,
             user_form_value,
             pass_form_name,
             pass_form_value) = source.call_finish(result)[0]
            if user_form_name and pass_form_name:
                self._window.close_popovers()
                self.emit("save-password",
                          user_form_name, user_form_value,
                          pass_form_name, pass_form_value,
                          self.get_uri(),
                          uri)
            request.submit()
        except Exception as e:
            print("WebViewDBusSignals::__on_get_forms():", e)

    def __on_signal(self, signal, params):
        """
            Add video to download manager
            @param signal as str
            @params as []
        """
        if signal == "VideoInPage":
            uri = params[0]
            title = params[1]
            page_id = params[2]
            El().download_manager.add_video(uri, title, page_id)
        elif signal == "UnsecureFormFocused":
            self._window.toolbar.title.show_input_warning(self)
        elif signal == "InputMouseDown":
            if self.__last_click_event:
                model = FormMenu(params[0], self.get_page_id())
                popover = Gtk.Popover.new_from_model(self, model)
                popover.set_modal(False)
                self._window.register(popover)
                rect = Gdk.Rectangle()
                rect.x = self.__last_click_event["x"]
                rect.y = self.__last_click_event["y"] - 10
                rect.width = rect.height = 1
                popover.set_pointing_to(rect)
                helper = PasswordsHelper()
                helper.get(self.get_uri(), self.__on_password, popover, model)

    def __on_password(self, attributes, password, uri,
                      index, count, popover, model):
        """
            Show form popover
            @param attributes as {}
            @param password as str
            @param uri as str
            @param index as int
            @param count as int
            @param popover as Gtk.Popover
            @param model as Gio.MenuModel
        """
        parsed = urlparse(uri)
        self.__last_click_event = {}
        if attributes is not None and (count > 1 or
                                       parsed.scheme == "http"):
            parsed = urlparse(uri)
            submit_uri = "%s://%s" % (parsed.scheme, parsed.netloc)
            if submit_uri == attributes["formSubmitURL"]:
                model.add_attributes(attributes, uri)
                if index == 0:
                    popover.popup()
