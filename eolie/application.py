# Copyright (c) 2017-2018 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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
from getpass import getuser
from time import time
import json

from eolie.settings import Settings, SettingsDialog
from eolie.window import Window
from eolie.art import Art
from eolie.database_history import DatabaseHistory
from eolie.database_bookmarks import DatabaseBookmarks
from eolie.database_adblock import DatabaseAdblock
from eolie.database_exceptions import DatabaseExceptions
from eolie.database_settings import DatabaseSettings
from eolie.database_phishing import DatabasePhishing
from eolie.sqlcursor import SqlCursor
from eolie.search import Search
from eolie.download_manager import DownloadManager
from eolie.menu_pages import PagesMenu
from eolie.helper_dbus import DBusHelper
from eolie.helper_task import TaskHelper
from eolie.define import EOLIE_DATA_PATH, TimeSpan, TimeSpanValues, LoadingType
from eolie.utils import is_unity, wanted_loading_type, set_proxy_from_gnome
from eolie.logger import Logger


class Application(Gtk.Application):
    """
        Eolie application
    """

    __FAVICONS_PATH = "/tmp/eolie_%s" % getuser()

    def __init__(self, version, extension_dir):
        """
            Create application
            @param version as str
            @param extension_dir as str
        """
        self.__version = version
        self.__state_cache = []
        # Set main thread name
        # We force it to current python 3.6 name, to be sure in case of
        # change in python
        current_thread().setName("MainThread")
        set_proxy_from_gnome()
        # First check WebKit2 version
        if WebKit2.MINOR_VERSION < 18:
            exit("You need WebKit2GTK >= 2.18")
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
        self.__extension_dir = extension_dir
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
        self.connect("shutdown", lambda a: self.__save_state())
        self.connect("handle-local-options", self.__on_handle_local_options)
        self.connect("command-line", self.__on_command_line)
        self.register(None)
        if self.get_is_remote():
            Gdk.notify_startup_complete()

    def get_app_menu(self):
        """
            Setup application menu
            @return menu as Gio.Menu
        """
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/Appmenu.ui")
        menu = builder.get_object("app-menu")

        settings_action = Gio.SimpleAction.new("settings", None)
        settings_action.connect("activate", self.__on_settings_activate)
        self.add_action(settings_action)

        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self.__on_about_activate)
        self.add_action(about_action)

        show_sidebar = self.settings.get_value("show-sidebar")
        sidebar_action = Gio.SimpleAction.new_stateful(
                                       "sidebar",
                                       None,
                                       GLib.Variant.new_boolean(show_sidebar))
        sidebar_action.connect("change-state", self.__on_sidebar_change_state)
        self.add_action(sidebar_action)

        shortcuts_action = Gio.SimpleAction.new("shortcuts", None)
        shortcuts_action.connect("activate", self.__on_shortcuts_activate)
        self.add_action(shortcuts_action)

        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda x, y: self.quit())
        self.add_action(quit_action)
        return menu

    def update_default_style_sheet(self):
        """
            Should be called on startup
        """
        rules = self.adblock.get_default_css_rules()
        self.__default_style_sheet = WebKit2.UserStyleSheet(
                                 rules,
                                 WebKit2.UserContentInjectedFrames.ALL_FRAMES,
                                 WebKit2.UserStyleLevel.USER,
                                 None,
                                 None)

    def do_startup(self):
        """
            Init application
        """
        Gtk.Application.do_startup(self)
        if not self.get_windows():
            self.__init()

    def get_new_window(self, size=None, maximized=False):
        """
            Return a new window
            @return Window
        """
        windows = self.get_windows()
        if windows and size is None:
            active_window = self.active_window
            size = active_window.get_size()
            maximized = active_window.is_maximized()
        window = Window(self, size, maximized)
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
            for view in window.container.views:
                view.webview.set_setting(key, value)

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

    def set_profiles(self):
        """
            Set profiles
        """
        try:
            f = Gio.File.new_for_path(EOLIE_DATA_PATH + "/profiles.json")
            if f.query_exists():
                (status, contents, tag) = f.load_contents(None)
                self.__profiles = json.loads(contents.decode("utf-8"))
            else:
                PROFILES = {"default": _("Default"),
                            "social": _("Social networks"),
                            "work": _("Work"),
                            "shopping": _("Shopping"),
                            "personal": _("Personal"),
                            "finance": _("Finance"),
                            "sport": _("Sport")}
                content = json.dumps(PROFILES)
                f.replace_contents(content.encode("utf-8"),
                                   None,
                                   False,
                                   Gio.FileCreateFlags.REPLACE_DESTINATION,
                                   None)
                self.__profiles = PROFILES
        except Exception as e:
            Logger.error("Application::set_profiles(): %s", e)

    def quit(self, vacuum=False):
        """
            Quit application
            @param vacuum as bool
        """
        # Stop pending tasks
        self.download_manager.cancel()
        self.adblock.stop()
        # Clear history
        active_id = str(self.settings.get_enum("history-storage"))
        if active_id != TimeSpan.FOREVER:
            atime = time()
            if active_id != TimeSpan.NEVER:
                atime -= TimeSpanValues[active_id]/1000000
            self.history.clear_to(int(atime))
        # If sync is running, to avoid DB lock, we do not vacuum
        if self.sync_worker is not None and self.sync_worker.syncing:
            self.sync_worker.stop()
            Gio.Application.quit(self)
        elif vacuum:
            task_helper = TaskHelper()
            task_helper.run(self.__vacuum,
                            callback=(lambda x: Gio.Application.quit(self),))
        else:
            Gio.Application.quit(self)

    @property
    def profiles(self):
        """
            Get profiles
            @return {}
        """
        return self.__profiles

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
    def default_style_sheet(self):
        """
            Get default style sheet
            @return WebKit2.UserStyleSheet
        """
        return self.__default_style_sheet

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
    def favicons_path(self):
        """
            Cookies sqlite DB path
        """
        return self.__FAVICONS_PATH

    @property
    def extension_dir(self):
        """
            Extension dir path
            @return str
        """
        return self.__extension_dir

#######################
# PRIVATE             #
#######################
    def __init(self):
        """
            Init main application
        """
        self.settings = Settings.new()

        # Init extensions
        current_path = GLib.getenv("PYTHONPATH")
        new_path = self.__extension_dir
        if current_path:
            new_path = new_path + ':' + current_path
        GLib.setenv("PYTHONPATH", new_path, True)

        # Create favicon path
        if not GLib.file_test(self.__FAVICONS_PATH, GLib.FileTest.IS_DIR):
            GLib.mkdir_with_parents(self.__FAVICONS_PATH, 0o0750)

        # Add a global DBus helper
        self.helper = DBusHelper()
        # First init sync worker
        from eolie.mozilla_sync import SyncWorker
        if SyncWorker.check_modules():
            self.sync_worker = SyncWorker()
            # Run a first sync in 10 seconds, speed up app start
            GLib.timeout_add_seconds(10,
                                     self.sync_worker.sync,
                                     False)
            # Then run a sync every hour
            GLib.timeout_add_seconds(3600,
                                     self.sync_worker.sync,
                                     True)
        else:
            self.sync_worker = None
        if self.prefers_app_menu():
            menu = self.get_app_menu()
            self.set_app_menu(menu)
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
        self.adblock = DatabaseAdblock()
        self.adblock.create_db()
        self.adblock.update()
        self.phishing = DatabasePhishing()
        self.adblock_exceptions = DatabaseExceptions("adblock")
        # Do not remove this!
        self.update_default_style_sheet()
        self.popup_exceptions = DatabaseExceptions("popups")
        self.image_exceptions = DatabaseExceptions("images")
        if self.settings.get_user_value("jsblock") is not None:
            self.js_exceptions = DatabaseExceptions("js")
        else:
            self.js_exceptions = None
        self.phishing.update()
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

        # Init profiles
        self.set_profiles()

        shortcut_action = Gio.SimpleAction.new('shortcut',
                                               GLib.VariantType.new('s'))
        shortcut_action.connect('activate', self.__on_shortcut_action)
        self.add_action(shortcut_action)
        self.set_accels_for_action("win.shortcut::expose", ["<Alt>e"])
        self.set_accels_for_action("win.exceptions::site", ["<Control>e"])
        self.set_accels_for_action("win.shortcut::jsblock", ["<Control>j"])
        self.set_accels_for_action("win.shortcut::show_left_panel", ["F9"])
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
        self.set_accels_for_action("app.settings",
                                   ["<Control>s"])
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
            with SqlCursor(self.adblock) as sql:
                sql.isolation_level = None
                sql.execute("VACUUM")
                sql.isolation_level = ""
            with SqlCursor(self.phishing) as sql:
                sql.isolation_level = None
                sql.execute("VACUUM")
                sql.isolation_level = ""
        except Exception as e:
            Logger.error("Application::__vacuum(): %s ", e)
        self.art.vacuum()

    def __get_state(self, window):
        """
            Return state for window
            @param window as Window
            @return {}
        """
        def get_state_for_webview(webview):
            uri = webview.uri
            parsed = urlparse(uri)
            if parsed.scheme in ["http", "https"]:
                ephemeral = webview.ephemeral
                state = webview.get_session_state().serialize()
                return (uri, webview.title, webview.atime,
                        ephemeral, state.get_data())
            else:
                return None

        window_state = {}
        window_state["id"] = str(window)
        window_state["size"] = window.get_size()
        window_state["maximized"] = window.is_maximized()
        session_states = []
        if self.settings.get_value("remember-session"):
            # Save current first, will be loaded first on restore
            current = window.container.current.webview
            state = get_state_for_webview(current)
            if state is not None:
                session_states.append(state)
            # Do not get view from container to save order
            for view in window.container.views:
                if view.webview == current or view.destroying:
                    continue
                state = get_state_for_webview(view.webview)
                if state is not None:
                    session_states.append(state)
        window_state["states"] = session_states
        return window_state

    def __save_state(self):
        """
            Save windows state
        """
        try:
            window_states = []
            for window in self.get_windows():
                window_state = self.__get_state(window)
                window_states.append(window_state)
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
            if state["id"] == window_id:
                self.__state_cache.remove(state)
                break

    def __create_initial_windows(self, foreground):
        """
            Create initial windows based on saved session
            @param foreground  as bool if foreground loading allowed
        """
        size = (800, 600)
        maximized = False
        try:
            windows = load(open(EOLIE_DATA_PATH + "/session_states.bin", "rb"))
            if self.settings.get_value("remember-session"):
                for window in windows:
                    if not window["states"]:
                        continue
                    new_window = self.get_new_window(window["size"],
                                                     window["maximized"])
                    items = []
                    i = 0 if foreground else 1
                    for (uri, title, atime,
                         ephemeral, state) in window["states"]:
                        loading_type = wanted_loading_type(i)
                        webkit_state = WebKit2.WebViewSessionState(
                                                         GLib.Bytes.new(state))
                        items.append((uri, title, atime, ephemeral,
                                      webkit_state, loading_type))
                        i += 1
                    new_window.container.add_webviews(items)
            elif windows:
                    size = windows[0]["size"]
                    maximized = windows[0]["maximized"]
        except Exception as e:
            Logger.error("Application::__create_initial_windows(): %s", e)
        if not self.get_windows():
            self.get_new_window(size, maximized)

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
        ephemeral = options.contains("private")
        if not self.get_windows():
            self.__create_initial_windows(len(args) < 2)
        if options.contains("new"):
            active_window = self.get_new_window()
        else:
            active_window = self.active_window
        # Open command line args
        if len(args) > 1:
            items = []
            i = 0
            for uri in args[1:]:
                # Transform path to uri
                parsed = urlparse(uri)
                if not parsed.scheme:
                    if uri.startswith('/'):
                        uri = "file://%s" % uri
                    else:
                        uri = "http://%s" % uri
                loading_type = wanted_loading_type(i)
                items.append((uri, uri, 0, ephemeral, None, loading_type))
                i += 1
            active_window.container.add_webviews(items)
            active_window.present()
        # Add default start page
        if not active_window.container.views:
            active_window.container.add_webview(self.start_page,
                                                LoadingType.FOREGROUND,
                                                ephemeral)
        if self.settings.get_value("debug"):
            WebKit2.WebContext.get_default().get_plugins(None,
                                                         self.__on_get_plugins,
                                                         None)
        return 0

    def __close_window(self, window):
        """
            Close window
        """
        if len(self.get_windows()) > 1:
            state = self.__get_state(window)
            self.__state_cache.append(state)
            GLib.timeout_add(25000, self.__clean_state_cache, state["id"])
            window.destroy()
        else:
            self.quit(True)

    def __try_closing(self, window, views):
        """
            Try closing all views
        """
        if views:
            view = views.pop(0)
            page_id = view.webview.get_page_id()
            self.helper.call("FormsFilled", page_id, None,
                             self.__on_forms_filled, window, views)
        else:
            self.__close_window(window)

    def __on_forms_filled(self, source, result, window, views):
        """
            Ask user to close view, if ok, close view
            @param source as GObject.Object
            @param result as Gio.AsyncResult
            @param window as Window
            @param views as [View]
        """
        def on_response_id(dialog, response_id, window, views, self):
            if response_id == Gtk.ResponseType.CLOSE:
                if views:
                    self.__try_closing(window, views)
                else:
                    self.__close_window(window)
            dialog.destroy()

        def on_close(widget, dialog):
            dialog.response(Gtk.ResponseType.CLOSE)

        def on_cancel(widget, dialog):
            dialog.response(Gtk.ResponseType.CANCEL)

        try:
            result = source.call_finish(result)[0]
            if result:
                builder = Gtk.Builder()
                builder.add_from_resource("/org/gnome/Eolie/QuitDialog.ui")
                dialog = builder.get_object("dialog")
                label = builder.get_object("label")
                close = builder.get_object("close")
                cancel = builder.get_object("cancel")
                label.set_text(_("Do you really want to quit Eolie?"))
                dialog.set_transient_for(window)
                dialog.connect("response", on_response_id, window, views, self)
                close.connect("clicked", on_close, dialog)
                cancel.connect("clicked", on_cancel, dialog)
                dialog.run()
            else:
                if views:
                    self.__try_closing(window, views)
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
                self.__try_closing(window, window.container.views)
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
                             " are you sure you want quit ?"))
            dialog.set_transient_for(window)
            dialog.connect("response", on_response_id, window)
            close.connect("clicked", on_close, dialog)
            cancel.connect("clicked", on_cancel, dialog)
            dialog.run()
        else:
            self.__try_closing(window, window.container.views)
        return True

    def __on_settings_activate(self, action, param):
        """
            Show settings dialog
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        dialog = SettingsDialog(self.active_window)
        dialog.show()

    def __on_about_activate(self, action, param):
        """
            Setup about dialog
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        builder = Gtk.Builder()
        builder.add_from_resource('/org/gnome/Eolie/AboutDialog.ui')
        about = builder.get_object('about_dialog')
        window = self.active_window
        if window is not None:
            about.set_transient_for(window)
        about.connect("response", self.__on_about_activate_response)
        about.show()

    def __on_shortcuts_activate(self, action, param):
        """
            Show help in yelp
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/Shortcuts.ui")
        shortcuts = builder.get_object("shortcuts")
        window = self.active_window
        if window is not None:
            shortcuts.set_transient_for(window)
        shortcuts.show()

    def __on_about_activate_response(self, dialog, response_id):
        """
            Destroy about dialog when closed
            @param dialog as Gtk.Dialog
            @param response ID as int
        """
        dialog.destroy()

    def __on_sidebar_change_state(self, action, value):
        """
            Show/hide sidebar
            @param action as Gio.SimpleAction
            @param value as bool
        """
        action.set_state(value)
        self.settings.set_value("show-sidebar", GLib.Variant("b", value))

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
            window.container.add_webview(self.start_page,
                                         LoadingType.FOREGROUND)
