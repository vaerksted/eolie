# Copyright (c) 2017-2019 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.0')
gi.require_version('Soup', '2.4')
gi.require_version('Secret', '1')
gi.require_version('GtkSpell', '3.0')
from gi.repository import Gtk, Gio, GLib, Gdk, WebKit2

from threading import current_thread
from gettext import gettext as _
from pickle import dump, load
from urllib.parse import urlparse
from time import time
from getpass import getuser
from signal import signal, SIGINT, SIGTERM

from eolie.application_night import NightApplication
from eolie.settings import Settings
from eolie.window import Window
from eolie.art import Art
from eolie.content_blocker_ad import AdContentBlocker
from eolie.content_blocker_popups import PopupsContentBlocker
from eolie.content_blocker_images import ImagesContentBlocker
from eolie.content_blocker_medias import MediasContentBlocker
from eolie.content_blocker_scripts import ScriptsContentBlocker
from eolie.content_blocker_phishing import PhishingContentBlocker
from eolie.database_history import DatabaseHistory
from eolie.database_bookmarks import DatabaseBookmarks
from eolie.database_settings import DatabaseSettings
from eolie.sqlcursor import SqlCursor
from eolie.context import Context
from eolie.search import Search
from eolie.download_manager import DownloadManager
from eolie.menu_pages import PagesMenu
from eolie.helper_task import TaskHelper
from eolie.define import EOLIE_DATA_PATH, TimeSpan, TimeSpanValues, LoadingType
from eolie.utils import is_unity, wanted_loading_type
from eolie.logger import Logger
from eolie.webview_state import WebViewState


class Application(Gtk.Application, NightApplication):
    """
        Eolie application
    """

    __FAVICONS_PATH = "/tmp/eolie_%s" % getuser()

    def __init__(self, version, data_dir):
        """
            Create application
            @param version as str
            @param data_dir as str
        """
        self.__version = version
        self.__state_cache = []
        self.__data_dir = data_dir
        self.__content_blockers = []
        signal(SIGINT, lambda a, b: self.quit())
        signal(SIGTERM, lambda a, b: self.quit())
        # Set main thread name
        # We force it to current python 3.6 name, to be sure in case of
        # change in python
        current_thread().setName("MainThread")
        # First check WebKit2 version
        if WebKit2.MINOR_VERSION < 20:
            exit("You need WebKit2GTK >= 2.20")
        Gtk.Application.__init__(
            self,
            application_id="org.gnome.Eolie",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.set_property("register-session", True)
        # Fix proxy for python
        proxy = GLib.environ_getenv(GLib.get_environ(), "all_proxy")
        if proxy is not None and proxy.startswith("socks://"):
            proxy = proxy.replace("socks://", "socks4://")
            from os import environ
            environ["all_proxy"] = proxy
            environ["ALL_PROXY"] = proxy
        # Ideally, we will be able to delete this once Flatpak has a solution
        # for SSL certificate management inside of applications.
        if GLib.file_test("/app", GLib.FileTest.EXISTS):
            paths = ["/etc/ssl/certs/ca-certificates.crt",
                     "/etc/pki/tls/cert.pem",
                     "/etc/ssl/cert.pem"]
            for path in paths:
                if GLib.file_test(path, GLib.FileTest.EXISTS):
                    GLib.setenv("SSL_CERT_FILE", path, True)
                    break
        self.sync_worker = None  # Not initialised
        self.show_tls = False
        self.cursors = {}
        GLib.set_application_name('Eolie')
        GLib.set_prgname('org.gnome.Eolie')
        self.add_main_option("private", b'p', GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE, "Add a private page",
                             None)
        self.add_main_option("new", b'n', GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE, "Add a new window",
                             None)
        self.add_main_option("disable-artwork-cache", b'a',
                             GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE, "Do not use cache for art",
                             None)
        self.add_main_option("show-tls", b't', GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE, "Show TLS info",
                             None)
        self.connect("activate", self.__on_activate)
        self.connect("handle-local-options", self.__on_handle_local_options)
        self.connect("command-line", self.__on_command_line)
        self.register(None)
        if self.get_is_remote():
            Gdk.notify_startup_complete()

    def do_startup(self):
        """
            Init application
        """
        Gtk.Application.do_startup(self)
        if not self.get_windows():
            self.__init()

    def get_new_window(self):
        """
            Return a new window
            @return Window
        """
        size = (800, 600)
        is_maximized = False
        windows = self.get_windows()
        if windows:
            active_window = self.active_window
            size = active_window.size
            is_maximized = active_window.is_maximized()
        window = Window(size, is_maximized)
        window.connect('delete-event', self.__on_delete_event)
        window.show()
        return window

    def set_setting(self, key, value):
        """
            Set setting for all view
            @param key as str
            @param value as GLib.Variant
        """
        for window in self.get_windows():
            for webview in window.container.webviews:
                webview.set_setting(key, value)

    def update_unity_badge(self, fraction=None):
        """
            Update unity badge count/fraction
            @param fraction as double
        """
        if self.__unity is not None:
            if fraction is None:
                count = 0
                for window in self.get_windows():
                    count += len(window.container.pages_manager.children)
                self.__unity.set_property("count", count)
                self.__unity.set_property("count_visible", True)
            else:
                self.__unity.set_property("progress", fraction)
                self.__unity.set_property("progress_visible", fraction != 1.0)

    def quit(self, vacuum=False):
        """
            Quit application
            @param vacuum as bool
        """
        self.__save_state()
        for window in self.windows:
            window.hide()
        # Stop pending tasks
        self.download_manager.cancel()
        for content_blocker in self.__content_blockers:
            content_blocker.stop()
        # Clear history
        active_id = str(self.settings.get_enum("history-storage"))
        if active_id != TimeSpan.FOREVER:
            atime = time()
            if active_id != TimeSpan.NEVER:
                atime -= TimeSpanValues[active_id] / 1000000
            self.history.clear_to(int(atime))

        if self.sync_worker is not None:
            self.sync_worker.stop()
            self.sync_worker.save_pendings()
        if vacuum:
            task_helper = TaskHelper()
            task_helper.run(self.__vacuum,
                            callback=(lambda x: Gio.Application.quit(self),))
        else:
            Gio.Application.quit(self)

    def get_content_blocker(self, name):
        """
            Get content blocker by name
            @param name as str
            @return ContentBlocker
        """
        for content_blocker in self.__content_blockers:
            if content_blocker.name == name:
                return content_blocker

    @property
    def content_filters(self):
        """
            Get content filters
            @return [WebKit2.UserContentFilter]
        """
        filters = []
        for content_blocker in self.__content_blockers:
            if content_blocker.enabled:
                filters.append(content_blocker.filter)
        return filters

    @property
    def start_page(self):
        """
            Get start page
            @return uri as str
        """
        value = self.settings.get_value("start-page").get_string()
        if value in ["popular_hist", "popular_book"]:
            value = "populars://"
        elif value == "blank":
            value = "about:blank"
        else:
            value = self.search.uri
        return value

    @property
    def active_window(self):
        """
            Get active window
            @return Window
        """
        return self.get_active_window()

    @property
    def windows(self):
        """
            Get windows
            @return [Window]
        """
        return self.get_windows()

    @property
    def data_dir(self):
        """
            Get data dir
            @return str
        """
        return self.__data_dir

    @property
    def favicons_path(self):
        """
            Cookies sqlite DB path
            @return str
        """
        return self.__FAVICONS_PATH

#######################
# PRIVATE             #
#######################
    def __init(self):
        """
            Init main application
        """
        self.settings = Settings.new()
        NightApplication.__init__(self)

        # First init sync worker
        from eolie.firefox_sync import SyncWorker
        if SyncWorker.check_modules():
            self.sync_worker = SyncWorker()
            self.sync_worker.pull_loop()
        else:
            self.sync_worker = None
        cssProviderFile = Gio.File.new_for_uri(
            'resource:///org/gnome/Eolie/application.css')
        cssProvider = Gtk.CssProvider()
        cssProvider.load_from_file(cssProviderFile)
        screen = Gdk.Screen.get_default()
        styleContext = Gtk.StyleContext()
        styleContext.add_provider_for_screen(screen, cssProvider,
                                             Gtk.STYLE_PROVIDER_PRIORITY_USER)
        self.history = DatabaseHistory()
        self.bookmarks = DatabaseBookmarks()
        self.websettings = DatabaseSettings()
        for cls in [AdContentBlocker,
                    PopupsContentBlocker,
                    ImagesContentBlocker,
                    MediasContentBlocker,
                    ScriptsContentBlocker,
                    PhishingContentBlocker]:
            content_blocker = cls()
            content_blocker.connect("set-filter",
                                    self.__on_content_blocker_set_filter)
            content_blocker.connect("unset-filter",
                                    self.__on_content_blocker_unset_filter)
            self.__content_blockers.append(content_blocker)
        self.art = Art()

        # Get a default user agent for search
        settings = WebKit2.Settings.new()
        self.search = Search(settings.get_user_agent())

        self.download_manager = DownloadManager()
        self.pages_menu = PagesMenu()

        # Check MOZ_PLUGIN_PATH
        if self.settings.get_value('enable-plugins') and\
                not GLib.getenv("MOZ_PLUGIN_PATH"):
            Logger.info("You need to set MOZ_PLUGIN_PATH to use plugins")

        # https://wiki.ubuntu.com/Unity/LauncherAPI
        self.__unity = None
        if is_unity():
            try:
                gi.require_version('Unity', '7.0')
                from gi.repository import Unity
                self.__unity = Unity.LauncherEntry.get_for_desktop_id(
                    "org.gnome.Eolie.desktop")
            except:
                pass

        # Init default context
        Context(WebKit2.WebContext().get_default())

        shortcut_action = Gio.SimpleAction.new('shortcut',
                                               GLib.VariantType.new('s'))
        shortcut_action.connect('activate', self.__on_shortcut_action)
        self.add_action(shortcut_action)
        self.set_accels_for_action("win.shortcut::expose", ["<Alt>e"])
        self.set_accels_for_action("win.shortcut::show_sidebar", ["F9"])
        self.set_accels_for_action("win.shortcut::uri",
                                   ["<Control>l", "<Control>b"])
        self.set_accels_for_action("win.shortcut::new_page", ["<Control>t"])
        self.set_accels_for_action("win.shortcut::last_page",
                                   ["<Control><Shift>t"])
        self.set_accels_for_action("app.shortcut::new_window", ["<Control>n"])
        self.set_accels_for_action("win.shortcut::private",
                                   ["<Control><Shift>p"])
        self.set_accels_for_action("win.shortcut::close_page", ["<Control>w"])
        self.set_accels_for_action("win.shortcut::quit", ["<Control>q"])
        self.set_accels_for_action("win.shortcut::save", ["<Control><Shift>s"])
        self.set_accels_for_action("win.shortcut::filter", ["<Control>i"])
        self.set_accels_for_action("win.shortcut::reload",
                                   ["<Control>r", "F5"])
        self.set_accels_for_action("win.shortcut::home",
                                   ["<Control>Home"])
        self.set_accels_for_action("win.shortcut::find", ["<Control>f"])
        self.set_accels_for_action("win.shortcut::print", ["<Control>p"])
        self.set_accels_for_action("win.shortcut::source",
                                   ["<Control><Shift>c"])
        self.set_accels_for_action("win.shortcut::history", ["<Control>h"])
        self.set_accels_for_action("win.shortcut::search", ["<Control>k"])
        self.set_accels_for_action("win.shortcut::fullscreen", ["F11"])
        self.set_accels_for_action("win.shortcut::settings",
                                   ["<Control>comma"])
        self.set_accels_for_action("win.shortcut::backward",
                                   ["<Alt>Left", "Back"])
        self.set_accels_for_action("win.shortcut::forward",
                                   ["<Alt>Right", "Forward"])
        self.set_accels_for_action("win.shortcut::next",
                                   ["<Control>Tab",
                                    "<Control>Page_Down"])
        self.set_accels_for_action("win.shortcut::previous",
                                   ["<Control><Shift>Tab",
                                    "<Control>Page_Up"])
        self.set_accels_for_action("win.shortcut::next_site",
                                   ["<Control>twosuperior"])
        self.set_accels_for_action("win.shortcut::previous_site",
                                   ["<Control><Shift>twosuperior"])
        self.set_accels_for_action("win.shortcut::zoom_in",
                                   ["<Control>KP_Add",
                                    "<Control>plus",
                                    "<Control>equal"])
        self.set_accels_for_action("win.shortcut::zoom_out",
                                   ["<Control>KP_Subtract", "<Control>minus"])
        self.set_accels_for_action("win.shortcut::zoom_default",
                                   ["<Control>KP_0", "<Control>0"])
        self.set_accels_for_action("win.shortcut::mse_enabled",
                                   ["<Control>m"])

    def __vacuum(self):
        """
            VACUUM DB
            @thread safe
        """
        try:
            with SqlCursor(self.bookmarks) as sql:
                sql.isolation_level = None
                sql.execute("VACUUM")
                sql.isolation_level = ""
            with SqlCursor(self.history) as sql:
                sql.isolation_level = None
                sql.execute("VACUUM")
                sql.isolation_level = ""
        except Exception as e:
            Logger.error("Application::__vacuum(): %s ", e)
        self.art.vacuum()

    def __save_state(self):
        """
            Save windows state
        """
        try:
            window_states = []
            for window in self.windows:
                state = window.state
                window_states.append(state)
            for window_state in self.__state_cache:
                window_states.append(window_state)
            dump(window_states,
                 open(EOLIE_DATA_PATH + "/session_states.bin", "wb"))
        except Exception as e:
            Logger.error("Application::__save_state(): %s", e)

    def __clean_state_cache(self, window_id):
        """
            Remove window ID from cache
            @param window_id as str
        """
        for state in self.__state_cache:
            if state.wid == window_id:
                self.__state_cache.remove(state)
                break

    def __restore_state(self):
        """
            Restore state
            @return active window as Window
        """
        try:
            from eolie.window_state import WindowState, WindowStateStruct
            window_states = load(
                open(EOLIE_DATA_PATH + "/session_states.bin", "rb"))
            state = WindowStateStruct()
            for state in window_states:
                # If webview to restore
                if state.webview_states:
                    window = WindowState.new_from_state(state)
                    for webview_state in state.webview_states:
                        webview = WebViewState.new_from_state(webview_state,
                                                              window)
                        webview.show()
                        loading_type = wanted_loading_type(
                            len(window.container.webviews))
                        window.container.add_webview(webview, loading_type)
                        session = WebKit2.WebViewSessionState(
                            GLib.Bytes.new(webview_state.session))
                        webview.restore_session_state(session)
                    window.connect("delete-event", self.__on_delete_event)
                    window.show()
            # Add a default window
            if not self.windows:
                window = WindowState.new_from_state(state)
                window.connect("delete-event", self.__on_delete_event)
                window.show()
        except Exception as e:
            Logger.error("Application::__restore_state(): %s", e)

    def __on_handle_local_options(self, app, options):
        """
            Handle local options
            @param app as Gio.Application
            @param options as GLib.VariantDict
        """
        if options.contains("version"):
            Logger.info("Eolie %s", self.__version)
            return 0
        return -1

    def __on_command_line(self, app, app_cmd_line):
        """
            Handle command line
            @param app as Gio.Application
            @param options as Gio.ApplicationCommandLine
        """
        self.__externals_count = 0
        args = app_cmd_line.get_arguments()
        options = app_cmd_line.get_options_dict()
        if options.contains("show-tls"):
            self.show_tls = True
        if options.contains("disable-artwork-cache"):
            self.art.disable_cache()

        # FIXME
        # is_ephemeral = options.contains("private")

        # Only restore state on first run
        if not self.windows:
            self.__restore_state()

        # Setup at least one window
        if not self.windows or options.contains("new"):
            active_window = self.get_new_window()
        else:
            active_window = self.windows[0]

        # Open command line args
        for uri in args[1:]:
            # Transform path to uri
            parsed = urlparse(uri)
            if not parsed.scheme:
                if uri.startswith('/'):
                    uri = "file://%s" % uri
                else:
                    uri = "http://%s" % uri
            loading_type = wanted_loading_type(
                len(active_window.container.webviews))
            active_window.container.add_webview_for_uri(uri, loading_type)

        # Add default start page
        if not active_window.container.webviews:
            loading_type = wanted_loading_type(
                len(active_window.container.webviews))
            active_window.container.add_webview_for_uri(self.start_page,
                                                        loading_type)
        if self.settings.get_value("debug"):
            WebKit2.WebContext.get_default().get_plugins(None,
                                                         self.__on_get_plugins,
                                                         None)
        Gdk.notify_startup_complete()
        active_window.present()
        return 0

    def __close_window(self, window):
        """
            Close window
        """
        if len(self.get_windows()) > 1:
            state = window.state
            if state is not None:
                self.__state_cache.append(window.state)
                GLib.timeout_add(10000, self.__clean_state_cache, state.wid)
            window.destroy()
        else:
            self.quit(True)

    def __try_closing(self, window, webviews):
        """
            Try closing all webviews
            @param window as Window
            @param webviews as [WebView]
        """
        if webviews:
            webview = webviews.pop(0)
            webview.run_javascript("document.activeElement.tagName;", None,
                                   self.__on_get_active_element,
                                   webviews, window)
        else:
            self.__close_window(window)

    def __on_get_active_element(self, source, result, webviews, window):
        """
            Ask user to close view, if ok, close view
            @param source as GObject.Object
            @param result as Gio.AsyncResult
            @param webviews as [WebView]
            @param window as Window
        """
        def on_response_id(dialog, response_id, window, webviews, self):
            if response_id == Gtk.ResponseType.CLOSE:
                if webviews:
                    self.__try_closing(window, webviews)
                else:
                    self.__close_window(window)
            dialog.destroy()

        def on_close(widget, dialog):
            dialog.response(Gtk.ResponseType.CLOSE)

        def on_cancel(widget, dialog):
            dialog.response(Gtk.ResponseType.CANCEL)

        try:
            data = source.run_javascript_finish(result)
            name = data.get_js_value().to_string()
            if name == "TEXTAREA":
                builder = Gtk.Builder()
                builder.add_from_resource("/org/gnome/Eolie/QuitDialog.ui")
                dialog = builder.get_object("dialog")
                label = builder.get_object("label")
                close = builder.get_object("close")
                cancel = builder.get_object("cancel")
                label.set_text(_("Do you really want to quit Eolie?"))
                dialog.set_transient_for(window)
                dialog.connect("response", on_response_id,
                               window, webviews, self)
                close.connect("clicked", on_close, dialog)
                cancel.connect("clicked", on_cancel, dialog)
                dialog.run()
            else:
                if webviews:
                    self.__try_closing(window, webviews)
                else:
                    self.__close_window(window)
        except Exception as e:
            self.__close_window(window)
            Logger.error("Application::__on_forms_filled(): %s", e)

    def __on_get_plugins(self, source, result, data):
        """
            Print plugins on command line
            @param source as GObject.Object
            @param result as Gio.AsyncResult
            @param data as None
        """
        plugins = source.get_plugins_finish(result)
        for plugin in plugins:
            Logger.info("%s, %s, %s",
                        plugin.get_name(),
                        plugin.get_description(),
                        plugin.get_path())

    def __on_delete_event(self, window, event):
        """
            Exit application
            @param window as Window
            @param event as Gdk.Event
        """
        def on_response_id(dialog, response_id, window):
            if response_id == Gtk.ResponseType.CLOSE:
                self.__try_closing(window, window.container.webviews)
            dialog.destroy()

        def on_close(widget, dialog):
            dialog.response(Gtk.ResponseType.CLOSE)

        def on_cancel(widget, dialog):
            dialog.response(Gtk.ResponseType.CANCEL)
        # Ask for user if needed
        if len(self.get_windows()) == 1 and self.download_manager.active:
            builder = Gtk.Builder()
            builder.add_from_resource("/org/gnome/Eolie/QuitDialog.ui")
            dialog = builder.get_object("dialog")
            label = builder.get_object("label")
            close = builder.get_object("close")
            cancel = builder.get_object("cancel")
            label.set_text(_("Downloads running,"
                             " are you sure you want quit?"))
            dialog.set_transient_for(window)
            dialog.connect("response", on_response_id, window)
            close.connect("clicked", on_close, dialog)
            cancel.connect("clicked", on_cancel, dialog)
            dialog.run()
        else:
            self.__try_closing(window, window.container.webviews)
        return True

    def __on_activate(self, application):
        """
            Call default handler, raise last window
            @param application as Gio.Application
        """
        if self.get_windows():
            self.active_window.present()

    def __on_shortcut_action(self, action, param):
        """
            Global shortcuts handler
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        string = param.get_string()
        if string == "new_window":
            window = self.get_new_window()
            window.container.add_webview_for_uri(
                self.start_page, LoadingType.FOREGROUND)

    def __on_content_blocker_set_filter(self, content_blocker, content_filter):
        """
            Add filter to content manager
            @param content_blocker as ContentBlocker
            @param content_filter as WebKit2.UserContentFilter
        """
        for window in self.windows:
            for webview in window.container.webviews:
                content_manager = webview.get_user_content_manager()
                content_manager.add_filter(content_filter)

    def __on_content_blocker_unset_filter(self, content_blocker,
                                          content_filter):
        """
            Remove filter from content manager
            @param content_blocker as ContentBlocker
            @param content_filter as WebKit2.UserContentFilter
        """
        for window in self.windows:
            for webview in window.container.webviews:
                content_manager = webview.get_user_content_manager()
                content_manager.remove_filter(content_filter)
