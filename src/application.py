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

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.0')
gi.require_version('Soup', '2.4')
gi.require_version('Secret', '1')
from gi.repository import Gtk, Gio, GLib, Gdk, WebKit2

from gettext import gettext as _
from pickle import dump, load
from threading import Thread

from eolie.settings import Settings, SettingsDialog
from eolie.window import Window
from eolie.art import Art
from eolie.database_history import DatabaseHistory
from eolie.database_bookmarks import DatabaseBookmarks
from eolie.database_adblock import DatabaseAdblock
from eolie.database_exceptions import DatabaseExceptions
from eolie.database_pishing import DatabasePishing
from eolie.sqlcursor import SqlCursor
from eolie.search import Search
from eolie.download_manager import DownloadManager
from eolie.menu_pages import PagesMenu
from eolie.dbus_helper import DBusHelper
from eolie.context import Context
from eolie.define import LOCAL_PATH


class Application(Gtk.Application):
    """
        Eolie application:
    """

    __COOKIES_PATH = "%s/cookies.db" % LOCAL_PATH
    __FAVICONS_PATH = "%s/favicons" % LOCAL_PATH

    def __init__(self, extension_dir):
        """
            Create application
            @param extension_dir as str
        """
        # First check WebKit2 version
        if WebKit2.MINOR_VERSION < 16:
            exit("You need WebKit2GTK >= 2.16")
        Gtk.Application.__init__(
                            self,
                            application_id='org.gnome.Eolie',
                            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.set_property('register-session', True)
        # Ideally, we will be able to delete this once Flatpak has a solution
        # for SSL certificate management inside of applications.
        if GLib.file_test("/app", GLib.FileTest.EXISTS):
            paths = ["/etc/ssl/certs/ca-certificates.crt",
                     "/etc/pki/tls/cert.pem",
                     "/etc/ssl/cert.pem"]
            for path in paths:
                if GLib.file_test(path, GLib.FileTest.EXISTS):
                    GLib.setenv('SSL_CERT_FILE', path, True)
                    break
        self.__sync_worker = -1  # Not initialised
        self.__extension_dir = extension_dir
        self.__windows = []
        self.__pages_menu = PagesMenu(self)
        self.debug = False
        try:
            self.zoom_levels = load(open(self.LOCAL_PATH + "/zoom_levels.bin",
                                         "rb"))
        except:
            self.zoom_levels = {}
        self.cursors = {}
        GLib.set_application_name('Eolie')
        GLib.set_prgname('eolie')
        self.add_main_option("debug", b'd', GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE, "Debug Eolie", None)
        self.add_main_option("private", b'p', GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE, "Add a private page",
                             None)
        self.connect('activate', self.__on_activate)
        self.connect('command-line', self.__on_command_line)
        self.register(None)
        if self.get_is_remote():
            Gdk.notify_startup_complete()
        self.__listen_to_gnome_sm()

    def get_app_menu(self):
        """
            Setup application menu
            @return menu as Gio.Menu
        """
        builder = Gtk.Builder()
        builder.add_from_resource('/org/gnome/Eolie/Appmenu.ui')
        menu = builder.get_object('app-menu')

        settings_action = Gio.SimpleAction.new('settings', None)
        settings_action.connect('activate', self.__on_settings_activate)
        self.add_action(settings_action)

        about_action = Gio.SimpleAction.new('about', None)
        about_action.connect('activate', self.__on_about_activate)
        self.add_action(about_action)

        shortcuts_action = Gio.SimpleAction.new('shortcuts', None)
        shortcuts_action.connect('activate', self.__on_shortcuts_activate)
        self.add_action(shortcuts_action)

        # help_action = Gio.SimpleAction.new('help', None)
        # help_action.connect('activate', self.__on_help_activate)
        # self.add_action(help_action)

        quit_action = Gio.SimpleAction.new('quit', None)
        quit_action.connect('activate', lambda x, y: self.quit())
        self.add_action(quit_action)
        return menu

    def do_startup(self):
        """
            Init application
        """
        Gtk.Application.do_startup(self)

        if not self.__windows:
            self.__init()
            self.__get_new_window()

    def set_setting(self, key, value):
        """
            Set setting for all view
            @param key as str
            @param value as GLib.Variant
        """
        for window in self.__windows:
            for view in window.container.views:
                view.webview.set_setting(key, value)

    def quit(self, vacuum=False):
        """
            Quit application
            @param vacuum as bool
        """
        self.download_manager.cancel()
        self.adblock.stop()
        if self.sync_worker is not None:
            self.sync_worker.stop()
        # Save webpage state
        self.__save_state()
        # Then vacuum db and artwork
        if vacuum:
            thread = Thread(target=self.__vacuum)
            thread.daemon = True
            thread.start()
        else:
            Gio.Application.quit(self)

    @property
    def pages_menu(self):
        """
            Get pages menu
            @return PagesMenu
        """
        return self.__pages_menu

    @property
    def start_page(self):
        """
            Get start page
            @return uri as str
        """
        value = self.settings.get_value("start-page").get_string()
        if value == "search":
            value = self.search.uri
        elif value == "popular":
            value = "populars://"
        elif value == "blank":
            value = "about:blank"
        return value

    @property
    def active_window(self):
        """
            Get active window
            @return Window
        """
        for window in self.__windows:
            if window.is_active():
                return window
        # Fallback
        if self.__windows:
            return self.__windows[0]
        return None

    @property
    def windows(self):
        """
            Get windows
            @return [Window]
        """
        return self.__windows

    @property
    def cookies_path(self):
        """
            Cookies sqlite db path
        """
        return self.__COOKIES_PATH

    @property
    def favicons_path(self):
        """
            Cookies sqlite db path
        """
        return self.__FAVICONS_PATH + "/WebpageIcons.db"

#######################
# PRIVATE             #
#######################
    def __init(self):
        """
            Init main application
        """
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
        self.settings = Settings.new()
        self.history = DatabaseHistory()
        self.bookmarks = DatabaseBookmarks()
        # We store cursors for main thread
        SqlCursor.add(self.history)
        SqlCursor.add(self.bookmarks)
        self.sync_worker = None
        self.adblock = DatabaseAdblock()
        self.adblock.update()
        self.pishing = DatabasePishing()
        self.adblock_exceptions = DatabaseExceptions("adblock")
        self.popup_exceptions = DatabaseExceptions("popup")
        self.image_exceptions = DatabaseExceptions("image")
        self.pishing.update()
        self.art = Art()
        self.search = Search()
        self.download_manager = DownloadManager()

        shortcut_action = Gio.SimpleAction.new('shortcut',
                                               GLib.VariantType.new('s'))
        shortcut_action.connect('activate', self.__on_shortcut_action)
        self.add_action(shortcut_action)
        self.set_accels_for_action("win.exceptions::site", ["<Control>e"])
        self.set_accels_for_action("win.shortcut::uri", ["<Control>l"])
        self.set_accels_for_action("win.shortcut::new_page", ["<Control>t"])
        self.set_accels_for_action("win.shortcut::last_page",
                                   ["<Control><Shift>t"])
        self.set_accels_for_action("app.shortcut::new_window", ["<Control>n"])
        self.set_accels_for_action("win.shortcut::private",
                                   ["<Control><Shift>p"])
        self.set_accels_for_action("win.shortcut::close_page", ["<Control>w"])
        self.set_accels_for_action("win.shortcut::save", ["<Control>s"])
        self.set_accels_for_action("win.shortcut::filter", ["<Control>i"])
        self.set_accels_for_action("win.shortcut::reload", ["<Control>r"])
        self.set_accels_for_action("win.shortcut::find", ["<Control>f"])
        self.set_accels_for_action("win.shortcut::print", ["<Control>p"])
        self.set_accels_for_action("app.settings",
                                   ["<Control><Shift>s"])
        self.set_accels_for_action("win.shortcut::backward",
                                   ["<Alt>Left", "XF86Back"])
        self.set_accels_for_action("win.shortcut::forward",
                                   ["<Alt>Right", "XF86Forward"])
        self.set_accels_for_action("win.shortcut::next", ["<Control>Tab"])
        self.set_accels_for_action("win.shortcut::previous",
                                   ["<Control><Shift>Tab"])
        self.set_accels_for_action("win.shortcut::zoom_in",
                                   ["<Control>KP_Add", "<Control>plus"])
        self.set_accels_for_action("win.shortcut::zoom_out",
                                   ["<Control>KP_Subtract", "<Control>minus"])
        self.set_accels_for_action("win.panel_mode(0)",
                                   ["<Control><Alt>0", "<Control><Alt>KP_0"])
        self.set_accels_for_action("win.panel_mode(1)",
                                   ["<Control><Alt>1", "<Control><Alt>KP_1"])
        self.set_accels_for_action("win.panel_mode(2)",
                                   ["<Control><Alt>2", "<Control><Alt>KP_2"])

        # Set some WebKit defaults
        context = WebKit2.WebContext.get_default()
        Context(context)
        GLib.setenv('PYTHONPATH', self.__extension_dir, True)
        context.set_web_extensions_directory(self.__extension_dir)

        data_manager = WebKit2.WebsiteDataManager()
        context.new_with_website_data_manager(data_manager)
        context.set_process_model(
                            WebKit2.ProcessModel.MULTIPLE_SECONDARY_PROCESSES)
        context.set_cache_model(WebKit2.CacheModel.WEB_BROWSER)
        d = Gio.File.new_for_path(self.__FAVICONS_PATH)
        if not d.query_exists():
            d.make_directory_with_parents()
        context.set_favicon_database_directory(self.__FAVICONS_PATH)
        cookie_manager = context.get_cookie_manager()
        cookie_manager.set_accept_policy(
                                     self.settings.get_enum("cookie-storage"))
        cookie_manager.set_persistent_storage(
                                        self.__COOKIES_PATH,
                                        WebKit2.CookiePersistentStorage.SQLITE)
        helper = DBusHelper()
        helper.connect(self.__on_extension_signal, "UnsecureFormFocused")

    def __init_delayed(self):
        """
            Init delayed for startup speed reasons
        """
        thread = Thread(target=self.__start_sync_worker)
        thread.daemon = True
        thread.start()
        thread = Thread(target=self.__show_plugins)
        thread.daemon = True
        thread.start()

    def __start_sync_worker(self):
        """
            Start sync worker
            @thread safe
        """
        try:
            from eolie.mozilla_sync import SyncWorker
            self.sync_worker = SyncWorker()
            self.sync_worker.sync()
            GLib.timeout_add_seconds(3600,
                                     self.sync_worker.sync)
        except Exception as e:
            print("Application::init():", e)
            self.__sync_worker = None

    def __listen_to_gnome_sm(self):
        """
            Save state on EndSession signal
        """
        try:
            bus = self.get_dbus_connection()
            bus.signal_subscribe(None,
                                 "org.gnome.SessionManager.EndSessionDialog",
                                 "ConfirmedLogout",
                                 "/org/gnome/SessionManager/EndSessionDialog",
                                 None,
                                 Gio.DBusSignalFlags.NONE,
                                 lambda a, b, c, d, e, f: self.__save_state())
        except Exception as e:
            print("Application::__listen_to_gnome_sm():", e)

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
            with SqlCursor(self.pishing) as sql:
                sql.isolation_level = None
                sql.execute("VACUUM")
                sql.isolation_level = ""
        except Exception as e:
            print("Application::__vacuum(): ", e)
        self.art.vacuum()
        GLib.idle_add(Gio.Application.quit, self)

    def __save_state(self):
        """
            Save window position and view
        """
        try:
            remember_session = self.settings.get_value("remember-session")
            session_states = []
            for window in self.__windows:
                window.container.stop()
                if not remember_session:
                    continue
                for view in window.container.views:
                    uri = view.webview.get_uri()
                    private = view.webview.private
                    state = view.webview.get_session_state().serialize()
                    session_states.append((uri, private, state.get_data()))
            if remember_session:
                dump(session_states,
                     open(self.LOCAL_PATH + "/session_states.bin", "wb"))
                dump(self.zoom_levels,
                     open(self.LOCAL_PATH + "/zoom_levels.bin", "wb"))
        except Exception as e:
            print("Application::save_state()", e)

    def __get_new_window(self):
        """
            Return a new window
            @return Window
        """
        window = Window(self)
        window.connect('delete-event', self.__on_delete_event)
        window.show()
        self.__windows.append(window)
        return window

    def __show_plugins(self):
        """
            Show available plugins on stdout
        """
        if self.debug:
            self.active_window.container.current.webview.get_context(
                                                                ).get_plugins(
                                   None, self.__on_get_plugins, None)

    def __restore_state(self):
        """
            Restore saved state
            @return restored pages count as int
        """
        count = 0
        try:
            session_states = load(open(
                                     self.LOCAL_PATH + "/session_states.bin",
                                     "rb"))
            for (uri, private, state) in session_states:
                webkit_state = WebKit2.WebViewSessionState(
                                                         GLib.Bytes.new(state))
                GLib.idle_add(self.active_window.container.add_web_view,
                              uri, count == 0, private,
                              None, None, webkit_state)
                count += 1
        except Exception as e:
            print("Application::restore_state()", e)
        return count

    def __on_command_line(self, app, app_cmd_line):
        """
            Handle command line
            @param app as Gio.Application
            @param options as Gio.ApplicationCommandLine
        """
        self.__externals_count = 0
        args = app_cmd_line.get_arguments()
        options = app_cmd_line.get_options_dict()
        if options.contains("debug"):
            GLib.setenv("LIBGL_DEBUG", "verbose", True)
            GLib.setenv("WEBKIT_DEBUG", "network", True)
            GLib.setenv("GST_DEBUG", "webkit*:5", True)
            self.debug = True
        private_browsing = options.contains("private")
        if self.settings.get_value("remember-session"):
            count = self.__restore_state()
        else:
            count = 0
        active_window = self.active_window
        if len(args) > 1:
            for uri in args[1:]:
                active_window.container.add_web_view(uri, True,
                                                     private_browsing)
            active_window.present()
        elif count == 0:
            # We already have a window, open a new one
            if active_window.container.current:
                window = self.__get_new_window()
                window.container.add_web_view(self.start_page, True,
                                              private_browsing)
            else:
                active_window.container.add_web_view(self.start_page, True,
                                                     private_browsing)
        GLib.timeout_add(1000, self.__init_delayed)
        return 0

    def __on_get_plugins(self, source, result, data):
        """
            Print plugins on command line
            @param source as GObject.Object
            @param result as Gio.AsyncResult
            @param data as None
        """
        plugins = source.get_plugins_finish(result)
        for plugin in plugins:
            print(plugin.get_name(),
                  plugin.get_description(),
                  plugin.get_path())

    def __on_delete_event(self, window, event):
        """
            Exit application
            @param window as Window
            @param event as Gdk.Event
        """
        self.__windows.remove(window)
        if self.__windows:
            window.destroy()
        else:
            window.hide()
            self.quit(True)
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
        try:
            builder = Gtk.Builder()
            builder.add_from_resource('/org/gnome/Eolie/Shortcuts.ui')
            shortcuts = builder.get_object('shortcuts')
            window = self.active_window
            if window is not None:
                shortcuts.set_transient_for(window)
            shortcuts.show()
        except:  # GTK < 3.20
            self.__on_help_activate(action, param)

    def __on_help_activate(self, action, param):
        """
            Show help in yelp
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        try:
            Gtk.show_uri(None, "help:eolie", Gtk.get_current_event_time())
        except:
            print(_("Eolie: You need to install yelp."))

    def __on_about_activate_response(self, dialog, response_id):
        """
            Destroy about dialog when closed
            @param dialog as Gtk.Dialog
            @param response id as int
        """
        dialog.destroy()

    def __on_activate(self, application):
        """
            Call default handler, raise last window
            @param application as Gio.Application
        """
        if self.__windows:
            self.__windows[-1].present()

    def __on_shortcut_action(self, action, param):
        """
            Global shortcuts handler
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        string = param.get_string()
        if string == "new_window":
            window = self.__get_new_window()
            window.container.add_web_view(self.start_page, True)

    def __on_extension_signal(self, connection, sender, path,
                              interface, signal, params, data):
        """
            Show message on wanted window
            @param connection as Gio.DBusConnection
            @param sender as str
            @param path as str
            @param interface as str
            @param signal as str
            @param parameters as GLib.Variant
            @param data
        """
        webview = self.active_window.container.current.webview
        self.active_window.toolbar.title.show_input_warning(webview)
