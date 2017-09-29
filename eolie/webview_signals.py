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

from gi.repository import Gtk, Gdk, Gio, GLib, WebKit2, GObject

from gettext import gettext as _
from urllib.parse import urlparse
from ctypes import string_at
from time import time
import cairo

from eolie.menu_form import FormMenu
from eolie.helper_passwords import PasswordsHelper
from eolie.define import El, Indicator, ArtSize
from eolie.search import Search


class WebViewSignals:
    """
        Handle webview signals
    """

    gsignals = {
        "readable": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "title-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "uri-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "new-page":  (GObject.SignalFlags.RUN_FIRST, None, (str, int, int)),
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

    def __init__(self):
        """
            Init handler
            @param webview as WebView
        """
        self.__js_timeout_id = None
        self.__cancellable = Gio.Cancellable()
        self.__reset_js_blocker()
        self.connect("map", self.__on_map)
        self.connect("unmap", self.__on_unmap)
        self.connect("new-page", self.__on_new_page)
        self.connect("create", self.__on_create)
        self.connect("close", self.__on_close)
        # Always connected as we need on_title_changed() update history
        self.connect("title-changed", self.__on_title_changed)
        self.connect("button-press-event", self.__on_button_press_event)
        self.connect("scroll-event", self.__on_scroll_event)
        self.connect("context-menu", self.__on_context_menu)
        self.connect("run-file-chooser", self.__on_run_file_chooser)
        self.connect("submit-form", self.__on_submit_form)

#######################
# PRIVATE             #
#######################
    def __set_snapshot(self, uri):
        """
            Set webpage preview
            @param uri as str
        """
        if uri == self.get_uri() and not self.ephemeral:
            self.get_snapshot(WebKit2.SnapshotRegion.FULL_DOCUMENT,
                              WebKit2.SnapshotOptions.NONE,
                              self.__cancellable,
                              self.__on_snapshot,
                              uri)

    def __reset_js_blocker(self):
        """
            Reset js blocker
        """
        self.__js_dialog_type = None
        self.__js_dialog_message = None

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
            print("WebView::__on_get_forms():", e)

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

    def __on_context_menu(self, view, context_menu, event, hit):
        """
            Add custom items to menu
            @param view as WebView
            @param context_menu as WebKit2.ContextMenu
            @param event as Gdk.Event
            @param hit as WebKit2.HitTestResult
        """
        parsed = urlparse(view.get_uri())
        if hit.context_is_link():
            # Add an item for open in a new page
            # FIXME https://bugs.webkit.org/show_bug.cgi?id=159631
            # Introspection missing, Gtk.Action deprecated
            action = Gtk.Action.new("open_new_page",
                                    _("Open link in a new page"),
                                    None,
                                    None)
            action.connect("activate",
                           self.__on_open_new_page_activate,
                           hit.get_link_uri())
            item = WebKit2.ContextMenuItem.new(action)
            context_menu.insert(item, 1)

        user_data = context_menu.get_user_data()
        if user_data is not None and user_data.get_string():
            selection = user_data.get_string()
            if hit.context_is_selection():
                # Add an item for open words in search
                # FIXME https://bugs.webkit.org/show_bug.cgi?id=159631
                # Introspection missing, Gtk.Action deprecated
                action = Gtk.Action.new("search_words",
                                        _("Search on the Web"),
                                        None,
                                        None)
                action.connect("activate",
                               self.__on_search_words_activate,
                               selection)
                item = WebKit2.ContextMenuItem.new(action)
                context_menu.insert(item, 1)
            if hit.context_is_link():
                # Add an item for open words in search
                # FIXME https://bugs.webkit.org/show_bug.cgi?id=159631
                # Introspection missing, Gtk.Action deprecated
                action = Gtk.Action.new("copy_text",
                                        _("Copy"),
                                        None,
                                        None)
                action.connect("activate",
                               self.__on_copy_text_activate,
                               selection)
                item = WebKit2.ContextMenuItem.new(action)
                context_menu.insert(item, 2)
        else:
            # Add an item for open all images
            if view.is_loading() or parsed.scheme not in ["http", "https"]:
                return
            # FIXME https://bugs.webkit.org/show_bug.cgi?id=159631
            # Introspection missing, Gtk.Action deprecated
            action = Gtk.Action.new("save_imgs",
                                    _("Save images"),
                                    None,
                                    None)
            action.connect("activate", self.__on_save_images_activate,)
            item = WebKit2.ContextMenuItem.new(action)
            n_items = context_menu.get_n_items()
            if El().settings.get_value("developer-extras"):
                context_menu.insert(item, n_items - 2)
            else:
                context_menu.insert(item, n_items)
            # Add an item for page capture
            # FIXME https://bugs.webkit.org/show_bug.cgi?id=159631
            # Introspection missing, Gtk.Action deprecated
            action = Gtk.Action.new("save_as_image",
                                    _("Save page as image"),
                                    None,
                                    None)
            action.connect("activate", self.__on_save_as_image_activate,)
            item = WebKit2.ContextMenuItem.new(action)
            n_items = context_menu.get_n_items()
            if El().settings.get_value("developer-extras"):
                context_menu.insert(item, n_items - 2)
            else:
                context_menu.insert(item, n_items)

    def __on_open_new_page_activate(self, action, uri):
        """
            Open link in a new page
            @param action as Gtk.Action
            @param uri as str
        """
        self._window.container.add_webview(uri,
                                           Gdk.WindowType.CHILD,
                                           self.ephemeral)

    def __on_search_words_activate(self, action, selection):
        """
            Open link in a new page
            @param action as Gtk.Action
            @param selection as str
        """
        search = Search()
        uri = search.get_search_uri(selection)
        self._window.container.add_webview(uri, Gdk.WindowType.CHILD)

    def __on_copy_text_activate(self, action, selection):
        """
            Open link in a new page
            @param action as Gtk.Action
            @param selection as str
        """
        Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(selection, -1)

    def __on_save_images_activate(self, action):
        """
            Show images filtering popover
            @param action as Gtk.Action
        """
        self._window.toolbar.end.save_images(self.get_uri(),
                                             self.get_page_id())

    def __on_save_as_image_activate(self, action):
        """
            Save image in /tmp and show it to user
            @param action as Gtk.Action
        """
        self.get_snapshot(WebKit2.SnapshotRegion.FULL_DOCUMENT,
                          WebKit2.SnapshotOptions.NONE,
                          None,
                          self.__on_image_snapshot)

    def __on_image_snapshot(self, webview, result):
        """
            Set snapshot on main image
            @param webview as WebView
            @param result as Gio.AsyncResult
        """
        try:
            snapshot = webview.get_snapshot_finish(result)
            pixbuf = Gdk.pixbuf_get_from_surface(snapshot, 0, 0,
                                                 snapshot.get_width(),
                                                 snapshot.get_height())
            pixbuf.savev("/tmp/eolie_snapshot.png", "png", [None], [None])
            Gtk.show_uri_on_window(self._window,
                                   "file:///tmp/eolie_snapshot.png",
                                   Gtk.get_current_event_time())
        except Exception as e:
            print("WebView::__on_snapshot():", e)

    def __on_run_file_chooser(self, webview, request):
        """
            Run own file chooser
            @param webview as WebView
            @param request as WebKit2.FileChooserRequest
        """
        uri = webview.get_uri()
        dialog = Gtk.FileChooserNative.new(_("Select files to upload"),
                                           self._window,
                                           Gtk.FileChooserAction.OPEN,
                                           _("Open"),
                                           _("Cancel"))
        dialog.set_select_multiple(request.get_select_multiple())
        chooser_uri = El().websettings.get_chooser_uri(uri)
        if chooser_uri is not None:
            dialog.set_current_folder_uri(chooser_uri)
        response = dialog.run()
        if response in [Gtk.ResponseType.DELETE_EVENT,
                        Gtk.ResponseType.CANCEL]:
            request.cancel()
        else:
            request.select_files(dialog.get_filenames())
            El().websettings.set_chooser_uri(dialog.get_current_folder_uri(),
                                             uri)
        return True

    def __on_button_press_event(self, widget, event):
        """
            Store last press event
            @param widget as WebView
            @param event as Gdk.EventButton
        """
        self._last_click_event = {"x": event.x,
                                  "y": event.y,
                                  "time": time()}

    def __on_scroll_event(self, webview, event):
        """
            Adapt scroll speed to device
            @param webview as WebView
            @param event as Gdk.EventScroll
        """
        source = event.get_source_device().get_source()
        if event.state & Gdk.ModifierType.CONTROL_MASK:
            if source == Gdk.InputSource.MOUSE:
                if event.delta_y < 0.5:
                    webview.zoom_in()
                elif event.delta_y > 0.5:
                    webview.zoom_out()
            else:
                if event.delta_y > 0.5:
                    webview.zoom_in()
                elif event.delta_y < - 0.5:
                    webview.zoom_out()
            return True
        elif source == Gdk.InputSource.MOUSE:
            event.delta_x *= 2
            event.delta_y *= 2

    def __on_script_dialog(self, webview, dialog):
        """
            Show message to user
            @param webview as WebView
            @param dialog as WebKit2.ScriptDialog
        """
        message = dialog.get_message()
        # Reader js message
        if message.startswith("@EOLIE_READER@"):
            self._readable_content = message.replace("@EOLIE_READER@", "")
            self.emit("readable")
        # Populars view message
        elif message.startswith("@EOLIE_HIDE_BOOKMARK_POPULARS@"):
            uri = message.replace("@EOLIE_HIDE_BOOKMARK_POPULARS@", "")
            El().bookmarks.reset_popularity(uri)
        # Populars view message
        elif message.startswith("@EOLIE_HIDE_HISTORY_POPULARS@"):
            uri = message.replace("@EOLIE_HIDE_HISTORY_POPULARS@", "")
            El().history.reset_popularity(uri)
        # Here we handle JS flood
        elif message() == self.__js_dialog_message and\
                dialog.get_dialog_type() == self.__js_dialog_type:
            self._window.toolbar.title.show_message(
                   _("Eolie is going to close this page because it is broken"))
            self._window.container.pages_manager.close_view(self, False)
        # Webpage message
        else:
            self.__js_dialog_type = dialog.get_dialog_type()
            self.__js_dialog_message = dialog.get_message()
            self._window.toolbar.title.show_javascript(dialog)
            GLib.timeout_add(1000, self.__reset_js_blocker)
        return True

    def __on_new_page(self, webview, uri, window_type, rtime):
        """
            Open a new page, switch to view if show is True
            @param webview as WebView
            @param uri as str
            @param window_type as Gdk.WindowType
            @param rtime as int
        """
        if uri:
            if window_type == Gdk.WindowType.SUBSURFACE:
                if self.ephemeral:
                    webview = self.new_ephemeral(self._window)
                else:
                    webview = self.new(self._window)
                self._window.container.popup_webview(webview, True)
                GLib.idle_add(self.load_uri, uri)
            else:
                new = self._window.container.add_webview(uri,
                                                         window_type,
                                                         self.ephemeral)
                # parent.rtime = child.rtime + 1
                # Used to search for best matching webview
                new.set_rtime(self.rtime - 1)

    def __on_create(self, related, navigation_action):
        """
            Create a new view for action
            @param related as WebView
            @param navigation_action as WebKit2.NavigationAction
            @param force as bool
        """
        webview = self.new_with_related_view(related, self._window)
        self.set_rtime(related.rtime - 1)
        self.connect("ready-to-show",
                     self.__on_ready_to_show,
                     related,
                     navigation_action)
        return webview

    def __on_close(self, webview):
        """
            Close my self
            @param webview as WebView
        """
        if self.get_ancestor(Gtk.Popover) is None:
            self._window.container.pages_manager.try_close_view(self)

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

    def __on_ready_to_show(self, webview, related, navigation_action):
        """
            Add a new webview with related
            @param webview as WebView
            @param related as WebView
            @param navigation_action as WebKit2.NavigationAction
        """
        # Do not block if we get a click on view
        elapsed = time() - related.last_click_time
        popup_block = El().settings.get_value("popupblock")
        parsed_related = urlparse(related.get_uri())
        exception = \
            related.js_load or\
            El().popup_exceptions.find(parsed_related.netloc) or\
            El().popup_exceptions.find(parsed_related.netloc +
                                       parsed_related.path) or\
            (not related.is_loading() and elapsed < 0.5)
        if not exception and popup_block and\
                navigation_action.get_navigation_type() in [
                               WebKit2.NavigationType.OTHER,
                               WebKit2.NavigationType.RELOAD,
                               WebKit2.NavigationType.BACK_FORWARD]:
            related.add_popup(webview)
            self.connect("close", self.__on_popup_close, related)
            if related == self._window.container.current.webview:
                self._window.toolbar.title.show_indicator(
                                                        Indicator.POPUPS)
            return
        properties = self.get_window_properties()
        if properties.get_locationbar_visible() and\
                properties.get_toolbar_visible() and\
                not navigation_action.get_modifiers() &\
                Gdk.ModifierType.SHIFT_MASK:
            self._window.container.add_view(webview,
                                            Gdk.WindowType.CHILD)
        else:
            self._window.container.popup_webview(webview, True)

    def __on_save_password(self, webview, user_form_name, user_form_value,
                           pass_form_name, pass_form_value, uri, form_uri):
        """
            Ask user to save password
            @param webview as WebView
            @param user_form_name as str
            @param user_form_value as str
            @param pass_form_name as str
            @param pass_form_value as str
            @param uri as str
        """
        self._window.toolbar.title.show_password(user_form_name,
                                                 user_form_value,
                                                 pass_form_name,
                                                 pass_form_value,
                                                 uri,
                                                 form_uri)

    def __on_button_press(self, webview, event):
        """
            Hide Titlebar popover
            @param webview as WebView
            @param event as Gdk.Event
        """
        if self.get_ancestor(Gtk.Popover) is None:
            return self._window.close_popovers()

    def __on_estimated_load_progress(self, webview, value):
        """
            Update progress bar
            @param webview as WebView
            @param value GparamFloat
        """
        if webview.get_mapped():
            value = self.get_estimated_load_progress()
            self._window.toolbar.title.progress.set_fraction(value)

    def __on_uri_changed(self, webview, uri):
        """
            Update UI and cancel current snapshot
            @param webview as WebView
            @param uri as GParamString (Do not use)
        """
        self.__cancellable.cancel()
        self.__cancellable.reset()
        if webview.get_mapped():
            self._window.toolbar.title.set_uri(uri)

    def __on_title_changed(self, webview, title):
        """
            Update title
            @param webview as WebView
            @param title as str
        """
        if webview.get_mapped():
            self._window.toolbar.title.set_title(title)
            self._window.container.sites_manager.update_label(
                                                self._window.container.current)
        # We only update history on title changed, should be enough
        if self.error is None:
            uri = self.get_uri()
            parsed = urlparse(uri)
            if parsed.scheme in ["http", "https"] and\
                    not self.ephemeral:
                mtime = round(time(), 2)
                El().history.thread_lock.acquire()
                history_id = El().history.add(title, uri, mtime)
                El().history.set_page_state(uri, mtime)
                El().history.thread_lock.release()
                if El().sync_worker is not None:
                    El().sync_worker.push_history([history_id])

    def __on_enter_fullscreen(self, webview):
        """
            Hide sidebar (conflict with fs)
            @param webview as WebView
        """
        self._window.container.sites_manager.hide()

    def __on_leave_fullscreen(self, webview):
        """
            Show sidebar (conflict with fs)
            @param webview as WebView
        """
        self._window.container.sites_manager.show()

    def __on_insecure_content_detected(self, webview, event):
        """
            @param webview as WebView
            @param event as WebKit2.InsecureContentEvent
        """
        self._window.toolbar.title.set_insecure_content()

    def __on_load_changed(self, webview, event):
        """
            Update sidebar/urlbar
            @param webview as WebView
            @param event as WebKit2.LoadEvent
        """
        # Check needed by WebViewPopover!
        if not webview.get_mapped():
            return
        self._window.toolbar.title.update_load_indicator(webview)
        uri = self.get_uri()
        parsed = urlparse(uri)
        wanted_scheme = parsed.scheme in ["http", "https", "file"]
        if event == WebKit2.LoadEvent.STARTED:
            self._window.container.current.find_widget.set_search_mode(False)
            self._window.toolbar.title.set_title(uri)
            if wanted_scheme:
                self._window.toolbar.title.show_spinner(True)
            else:
                # Give focus to url bar
                self._window.toolbar.title.start_search()
            self._window.toolbar.title.show_indicator(Indicator.NONE)
            # Turn off reading mode if needed
            if self._window.container.current.reading:
                self._window.container.current.switch_read_mode()
            self._window.toolbar.title.progress.show()
        elif event == WebKit2.LoadEvent.COMMITTED:
            self._window.toolbar.title.set_title(uri)
        elif event == WebKit2.LoadEvent.FINISHED:
            self._window.toolbar.title.show_spinner(False)
            # Give focus to webview
            if wanted_scheme:
                GLib.idle_add(self.grab_focus)
            # Hide progress delayed to show result to user
            GLib.timeout_add(500, self._window.toolbar.title.progress.hide)
            GLib.timeout_add(3000, self.__set_snapshot, uri)

    def __on_back_forward_list_changed(self, bf_list, added, removed, webview):
        """
            Update actions
            @param bf_list as WebKit2.BackForwardList
            @param added as WebKit2.BackForwardListItem
            @param removed as WebKit2.BackForwardListItem
            @param webview as WebView
        """
        self._window.toolbar.actions.set_actions(webview)

    def __on_resource_load_started(self, webview, resource, request):
        """
            Listen to off loading events
            @param webview as WebView
            @param resource WebKit2.WebResource
            @param request as WebKit2.URIRequest
        """
        # Javascript execution happened
        if not self.is_loading():
            if self.__js_timeout_id is not None:
                GLib.source_remove(self.__js_timeout_id)
            self.__js_timeout_id = GLib.timeout_add(500,
                                                    self.__on_js_timeout,
                                                    webview)

    def __on_js_timeout(self, webview):
        """
            Tell webpage to update credentials
            @param webview as WebView
        """
        self.__js_timeout_id = None
        page_id = self.get_page_id()
        El().helper.call("SetCredentials",
                         GLib.Variant("(i)", (page_id,)),
                         None,
                         page_id)

    def __on_snapshot(self, webview, result, uri):
        """
            Set snapshot on main image
            @param webview as WebView
            @param result as Gio.AsyncResult
            @param uri as str
        """
        ART_RATIO = 1.5  # ArtSize.START_WIDTH / ArtSize.START_HEIGHT
        # Do not cache snapshot on error
        if self.error is not None or uri != self.get_uri():
            return
        try:
            snapshot = self.get_snapshot_finish(result)
            # Set start image scale factor
            ratio = snapshot.get_width() / snapshot.get_height()
            if ratio > ART_RATIO:
                factor = ArtSize.START_HEIGHT / snapshot.get_height()
            else:
                factor = ArtSize.START_WIDTH / snapshot.get_width()
            surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                         ArtSize.START_WIDTH,
                                         ArtSize.START_HEIGHT)
            context = cairo.Context(surface)
            context.scale(factor, factor)
            context.set_source_surface(snapshot, factor, 0)
            context.paint()
            # Cache result
            # We also cache initial URI
            uris = [self.get_uri()]
            parsed = urlparse(uri)
            # Caching this will break populars navigation
            # as we are looking for subpage snapshots
            if parsed.scheme == "populars":
                return
            initial_parsed = urlparse(self.initial_uri)
            if parsed.netloc == initial_parsed.netloc and\
                    self.initial_uri not in uris:
                uris.append(self.initial_uri)
            for uri in uris:
                if not El().art.exists(uri, "start"):
                    El().art.save_artwork(uri, surface, "start")
        except Exception as e:
            print("WebViewSignalsHandler::__on_snapshot():", e)

    def __on_signal(self, connection, sender, path,
                    interface, signal, params):
        """
            Add video to download manager
            @param connection as Gio.DBusConnection
            @param sender as str
            @param path as str
            @param interface as str
            @param signal as str
            @param parameters as GLib.Variant
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

    def __on_map(self, webview):
        """
            Connect all signals
            @param webview as WebView
        """
        # We are offscreen
        if self._window != self.get_toplevel():
            return
        self._window.update(webview)
        self.connect("notify::estimated-load-progress",
                     self.__on_estimated_load_progress)
        self.connect("resource-load-started",
                     self.__on_resource_load_started)
        self.connect("load-changed", self.__on_load_changed)
        self.connect("button-press-event", self.__on_button_press)
        self.connect("uri-changed", self.__on_uri_changed)
        self.connect("enter-fullscreen", self.__on_enter_fullscreen)
        self.connect("leave-fullscreen", self.__on_leave_fullscreen)
        self.connect("save-password", self.__on_save_password)
        self.connect("script-dialog", self.__on_script_dialog)
        self.connect("insecure-content-detected",
                     self.__on_insecure_content_detected)
        self.get_back_forward_list().connect(
                             "changed",
                             self.__on_back_forward_list_changed,
                             webview)
        page_id = webview.get_page_id()
        El().helper.connect(None, self.__on_signal, page_id)

    def __on_unmap(self, webview):
        """
            Disconnect all signals
            @param webview as WebView
        """
        # We are offscreen
        if self._window != self.get_toplevel():
            return
        self.disconnect_by_func(self.__on_estimated_load_progress)
        self.disconnect_by_func(self.__on_resource_load_started)
        self.disconnect_by_func(self.__on_load_changed)
        self.disconnect_by_func(self.__on_button_press)
        self.disconnect_by_func(self.__on_uri_changed)
        self.disconnect_by_func(self.__on_enter_fullscreen)
        self.disconnect_by_func(self.__on_leave_fullscreen)
        self.disconnect_by_func(self.__on_save_password)
        self.disconnect_by_func(self.__on_script_dialog)
        self.disconnect_by_func(self.__on_insecure_content_detected)
        self.get_back_forward_list().disconnect_by_func(
                                         self.__on_back_forward_list_changed)
        page_id = webview.get_page_id()
        El().helper.disconnect(page_id)
