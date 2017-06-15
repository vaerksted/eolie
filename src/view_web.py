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

from gi.repository import WebKit2, Gtk, Gio, Gdk, GLib

from gettext import gettext as _
from urllib.parse import urlparse
from time import time
from ctypes import string_at

from eolie.define import El
from eolie.utils import debug
from eolie.view_web_errors import WebViewErrors
from eolie.view_web_navigation import WebViewNavigation


class WebView(WebKit2.WebView):
    """
        WebKit view
    """
    def new():
        """
            New webview
        """
        view = WebKit2.WebView.new()
        view.__class__ = WebViewMeta
        view.__init()
        return view

    def new_ephemeral():
        """
            New ephemeral webview
        """
        from eolie.context import Context
        context = WebKit2.WebContext.new_ephemeral()
        context.set_process_model(
                            WebKit2.ProcessModel.MULTIPLE_SECONDARY_PROCESSES)
        context.set_web_extensions_directory(El().extension_dir)
        Context(context)
        view = WebKit2.WebView.new_with_context(context)
        view.__class__ = WebViewMeta
        view.__init()
        return view

    def new_with_related_view(related):
        """
            Create a new WebView related to view
            @param related as WebView
            @return WebView
        """
        view = WebKit2.WebView.new_with_related_view(related)
        view.__class__ = WebViewMeta
        view.__init(related)
        return view

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
        from eolie.database_settings import DatabaseSettings
        try:
            settings_db = DatabaseSettings()
            zoom_level = settings_db.get_zoom(self.get_uri())
            if zoom_level is None:
                zoom_level = 100
            if self.__related_view is None:
                zoom_level *= self.get_ancestor(Gtk.Window).zoom_level
            else:
                zoom_level *= self.__related_view.get_ancestor(
                                                Gtk.Window).zoom_level
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

    def zoom_in(self):
        """
            Zoom in view
            @return current zoom after zoom in
        """
        from eolie.database_settings import DatabaseSettings
        settings_db = DatabaseSettings()
        current = settings_db.get_zoom(self.get_uri())
        if current is None:
            current = 100
        current += 10
        settings_db.set_zoom(current, self.get_uri())
        self.update_zoom_level()
        return current

    def zoom_out(self):
        """
            Zoom in view
            @return current zoom after zoom out
        """
        from eolie.database_settings import DatabaseSettings
        settings_db = DatabaseSettings()
        current = settings_db.get_zoom(self.get_uri())
        if current is None:
            current = 100
        current -= 10
        if current == 0:
            return 10
        settings_db.set_zoom(current, self.get_uri())
        self.update_zoom_level()
        return current

    def set_delayed_uri(self, uri):
        """
            Set delayed uri
            @param uri as str
        """
        self.__delayed_uri = uri

    @property
    def delayed_uri(self):
        """
            Get delayed uri (one time)
            @return str
        """
        try:
            return self.__delayed_uri
        finally:
            self.__delayed_uri = None

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
    def last_click_time(self):
        """
            Get last click time
            @return float
        """
        return self.__last_click_time

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
    def __init(self, related_view=None):
        """
            Init WebView
            @param related_view as WebView
        """
        WebViewErrors.__init__(self)
        WebViewNavigation.__init__(self)
        # WebKitGTK doesn't provide an API to get selection, so try to guess
        # it from clipboard
        self.__selection = ""
        self._readable_content = ""
        self.__last_click_time = 0
        self.__delayed_uri = None
        self.__related_view = related_view
        self.__initial_selection = ""
        self.__input_source = Gdk.InputSource.MOUSE
        self.set_hexpand(True)
        self.set_vexpand(True)
        settings = self.get_settings()
        settings.set_property("enable-java",
                              El().settings.get_value('enable-plugins'))
        settings.set_property("enable-plugins",
                              El().settings.get_value('enable-plugins'))
        settings.set_property("minimum-font-size",
                              El().settings.get_value(
                                "min-font-size").get_int32())
        if El().settings.get_value("use-system-fonts"):
            self.__set_system_fonts(settings)
        else:
            settings.set_property("monospace-font-family",
                                  El().settings.get_value(
                                    "font-monospace").get_string())
            settings.set_property("sans-serif-font-family",
                                  El().settings.get_value(
                                    "font-sans-serif").get_string())
            settings.set_property("serif-font-family",
                                  El().settings.get_value(
                                    "font-serif").get_string())
        settings.set_property("auto-load-images", True)
        settings.set_property("enable-site-specific-quirks", False)
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
        settings.set_property("javascript-can-access-clipboard", True)
        settings.set_property("javascript-can-open-windows-automatically",
                              True)
        settings.set_property("media-playback-allows-inline", True)
        self.connect("scroll-event", self.__on_scroll_event)
        self.connect("button-press-event", self.__on_button_press_event)
        self.connect("button-release-event", self.__on_button_release_event)
        self.connect("context-menu", self.__on_context_menu)
        self.connect("run-file-chooser", self.__on_run_file_chooser)
        self.connect("script-dialog", self.__on_script_dialog)
        self.connect("submit-form", self.__on_submit_form)
        self.connect("map", self.__on_map)
        self.connect("unmap", self.__on_unmap)

    def __set_system_fonts(self, settings):
        """
            Set system font
            @param settings as WebKit2.Settings
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

    def __set_smooth_scrolling(self, source):
        """
            Set smooth scrolling based on source
            @param source as Gdk.InputSource
        """
        settings = self.get_settings()
        settings.set_property("enable-smooth-scrolling",
                              source != Gdk.InputSource.MOUSE)

    def __get_forms(self, forms, page_id, request):
        """
            Read request for authentification
            @param forms as [str]
            @param page_id as int
            @param request as WebKit2.FormSubmissionRequest
        """
        El().helper.call("GetAuthForms",
                         GLib.Variant("(asi)", (forms, page_id)),
                         self.__on_get_forms, request, page_id)

    def __on_get_forms(self, source, result, request):
        """
            Set forms value
            @param source as GObject.Object
            @param result as Gio.AsyncResult
            @param request as WebKit2.FormSubmissionRequest
        """
        try:
            (username, userform,
             password, passform) = source.call_finish(result)[0]
            if username and password:
                self.emit("save-password",
                          username, userform,
                          password, passform,
                          self.get_uri())
            request.submit()
        except Exception as e:
            print("WebView::__on_get_forms():", e)

    def __on_submit_form(self, webview, request):
        """
            Check for auth forms
            @param webview as WebKit2.WebView
            @param request as WebKit2.FormSubmissionRequest
        """
        if self.ephemeral or not El().settings.get_value("remember-passwords"):
            return
        fields = request.get_text_fields()
        if fields is None:
            return
        forms = []
        for k, v in fields.items():
            name = string_at(k).decode("utf-8")
            forms.append(name)
            self.__get_forms(forms, webview.get_page_id(), request)

    def __on_context_menu(self, view, context_menu, event, hit):
        """
            Add custom items to menu
            @param view as WebView
            @param context_menu as WebKit2.ContextMenu
            @param event as Gdk.Event
            @param hit as WebKit2.HitTestResult
        """
        parsed = urlparse(view.get_uri())
        if view.is_loading() or parsed.scheme not in ["http", "https"]:
            return
        # FIXME https://bugs.webkit.org/show_bug.cgi?id=159631
        # Introspection missing, Gtk.Action deprecated
        action = Gtk.Action.new("save_imgs",
                                _("Save images"),
                                None,
                                None)
        action.connect("activate", self.__on_save_images_activate)
        item = WebKit2.ContextMenuItem.new(action)
        n_items = context_menu.get_n_items()
        if El().settings.get_value("developer-extras"):
            context_menu.insert(item, n_items - 2)
        else:
            context_menu.insert(item, n_items)

    def __on_save_images_activate(self, action):
        """
            Show images filtering popover
            @param action as Gtk.Action
        """
        El().active_window.toolbar.end.save_images(self.get_uri(),
                                                   self.get_page_id())

    def __on_button_press_event(self, widget, event):
        """
            Store initial selection
            @param widget as WebView
            @param event as Gdk.Event
        """
        self.__last_click_time = time()
        self.__selection = ""
        c = Gtk.Clipboard.get(Gdk.SELECTION_PRIMARY)
        self.__initial_selection = c.wait_for_text()

    def __on_button_release_event(self, widget, event):
        """
            Set current selection
            @param widget as WebView
            @param event as Gdk.EventScroll
        """
        c = Gtk.Clipboard.get(Gdk.SELECTION_PRIMARY)
        selection = c.wait_for_text()
        if selection != self.__initial_selection:
            self.__selection = selection if selection is not None else ""
        self.__initial_selection = ""

    def __on_scroll_event(self, widget, event):
        """
            Adapt scroll speed to device
            @param widget as WebView
            @param event as Gdk.EventScroll
        """
        source = event.get_source_device().get_source()
        if source == Gdk.InputSource.MOUSE:
            event.delta_x *= 2
            event.delta_y *= 2
        # if self.__input_source != source:
        #    self.__input_source = source
        #    self.__set_smooth_scrolling(source)

    def __on_run_file_chooser(self, webview, request):
        """
            Run own file chooser
            @param webview as WebView
            @param request as WebKit2.FileChooserRequest
        """
        from eolie.database_settings import DatabaseSettings
        uri = webview.get_uri()
        settings_db = DatabaseSettings()
        dialog = Gtk.FileChooserNative.new(_("Select files to upload"),
                                           El().active_window,
                                           Gtk.FileChooserAction.OPEN,
                                           _("Open"),
                                           _("Cancel"))
        chooser_uri = settings_db.get_chooser_uri(uri)
        if chooser_uri is not None:
            dialog.set_current_folder_uri(chooser_uri)
        response = dialog.run()
        if response in [Gtk.ResponseType.DELETE_EVENT,
                        Gtk.ResponseType.CANCEL]:
            request.cancel()
        else:
            request.select_files(dialog.get_filenames())
            settings_db.set_chooser_uri(dialog.get_current_folder_uri(), uri)
        return True

    def __on_script_dialog(self, webview, dialog):
        """
            Show message to user
            @param webview as WebView
            @param dialog as WebKit2.ScriptDialog
        """
        if dialog.get_message().startswith("@&$%ù²"):
            self._readable_content = dialog.get_message().replace("@&$%ù²", "")
            self.emit("readable")
            return True

    def __on_map(self, webview):
        """
            Connect signals
            @parma webview as WebView
        """
        page_id = webview.get_page_id()
        El().helper.connect("VideoInPage",
                            self.__on_video_in_page, page_id)
        El().helper.connect("UnsecureFormFocused",
                            self.__on_unsecure_form_focused, page_id)

    def __on_unmap(self, webview):
        """
            Disconnect signals
            @parma webview as WebView
        """
        page_id = webview.get_page_id()
        El().helper.disconnect("VideoInPage", page_id)
        El().helper.disconnect("UnsecureFormFocused", page_id)

    def __on_video_in_page(self, connection, sender, path,
                           interface, signal, params, data):
        """
            Add video to download manager
            @param connection as Gio.DBusConnection
            @param sender as str
            @param path as str
            @param interface as str
            @param signal as str
            @param parameters as GLib.Variant
            @param data
        """
        uri = params[0]
        title = params[1]
        page_id = params[2]
        El().download_manager.add_video(uri, title, page_id)

    def __on_unsecure_form_focused(self, connection, sender, path,
                                   interface, signal, params, data):
        """
            Show a warning to user
            @param connection as Gio.DBusConnection
            @param sender as str
            @param path as str
            @param interface as str
            @param signal as str
            @param parameters as GLib.Variant
            @param data
        """
        El().active_window.toolbar.title.show_input_warning(self)


class WebViewMeta(WebViewNavigation, WebView, WebViewErrors):
    def __init__(self):
        pass
