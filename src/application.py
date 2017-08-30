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
gi.require_version('GtkSpell', '3.0')
from gi.repository import Gtk, Gio, GLib, Gdk, WebKit2

from gettext import gettext as _
from pickle import dump, load
from urllib.parse import urlparse
from getpass import getuser
from time import time

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
from eolie.context import Context
from eolie.define import EOLIE_LOCAL_PATH, TimeSpan, TimeSpanValues


class Application(Gtk.Application):
    """
        Eolie application:
    """

    __COOKIES_PATH = "%s/cookies.db" % EOLIE_LOCAL_PATH
    __FAVICONS_PATH = "/tmp/eolie_%s" % getuser()

    def __init__(self, version, extension_dir):
        """
            Create application
            @param version as str
            @param extension_dir as str
        """
        self.__version = version
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
        self.sync_worker = None  # Not initialised
        self.__extension_dir = extension_dir
        self.debug = False
        self.show_tls = False
        self.cursors = {}
        GLib.set_application_name('Eolie')
        GLib.set_prgname('org.gnome.Eolie')
        self.add_main_option("debug", b'd', GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE, "Debug Eolie", None)
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
        self.add_main_option("show-tls", b's', GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE, "Show TLS info",
                             None)
        self.connect('activate', self.__on_activate)
        self.connect("handle-local-options", self.__on_handle_local_options)
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
        builder.add_from_resource("/org/gnome/Eolie/Appmenu.ui")
        menu = builder.get_object("app-menu")

        report_action = Gio.SimpleAction.new("report", None)
        report_action.connect("activate", self.__on_report_activate)
        self.add_action(report_action)

        settings_action = Gio.SimpleAction.new("settings", None)
        settings_action.connect("activate", self.__on_settings_activate)
        self.add_action(settings_action)

        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self.__on_about_activate)
        self.add_action(about_action)

        shortcuts_action = Gio.SimpleAction.new("shortcuts", None)
        shortcuts_action.connect("activate", self.__on_shortcuts_activate)
        self.add_action(shortcuts_action)

        # help_action = Gio.SimpleAction.new('help', None)
        # help_action.connect('activate', self.__on_help_activate)
        # self.add_action(help_action)

        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda x, y: self.quit())
        self.add_action(quit_action)
        return menu

    def do_startup(self):
        """
            Init application
        """
        Gtk.Application.do_startup(self)
        if not self.get_windows():
            self.__init()
            window = self.get_new_window()
            window.container.add_webview(None,
                                         Gdk.WindowType.CHILD,
                                         False)

    def get_new_window(self):
        """
            Return a new window
            @return Window
        """
        window = Window(self)
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

    def quit(self, vacuum=False):
        """
            Quit application
            @param vacuum as bool
        """
        # Save webpage state
        self.__save_state()
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
        # If sync is running, to avoid db lock, we do not vacuum
        if self.sync_worker is not None and self.sync_worker.syncing:
            self.sync_worker.stop()
            Gio.Application.quit(self)
        elif vacuum:
            task_helper = TaskHelper()
            task_helper.run(self.__vacuum,
                            (),
                            lambda x: Gio.Application.quit(self))
        else:
            Gio.Application.quit(self)

    @property
    def ephemeral_context(self):
        """
            Get default ephemral context
            @return WebKit2.WebContext
        """
        return self.__ephemeral_context

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
        return self.get_windows()[0]

    @property
    def windows(self):
        """
            Get windows
            @return [Window]
        """
        return self.get_windows()

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
        GLib.setenv('PYTHONPATH', self.__extension_dir, True)

        # Create favicon path
        d = Gio.File.new_for_path(self.__FAVICONS_PATH)
        if not d.query_exists():
            d.make_directory_with_parents()

        # Setup default context
        context = WebKit2.WebContext.get_default()
        Context(context)
        # Setup ephemeral context
        self.__ephemeral_context = WebKit2.WebContext.new_ephemeral()
        Context(self.__ephemeral_context)

        # Add a global DBus helper
        self.helper = DBusHelper()
        # First init sync worker
        try:
            from eolie.mozilla_sync import SyncWorker
            self.sync_worker = SyncWorker()
            # Run a first sync in 10 seconds, speed up app start
            GLib.timeout_add_seconds(10,
                                     self.sync_worker.sync,
                                     False)
            # Then run a sync every hour
            GLib.timeout_add_seconds(3600,
                                     self.sync_worker.sync,
                                     True)
        except Exception as e:
            print("Application::init():", e)
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
        # We store cursors for main thread
        SqlCursor.add(self.history)
        SqlCursor.add(self.bookmarks)
        self.websettings = DatabaseSettings()
        self.adblock = DatabaseAdblock()
        self.adblock.update()
        self.phishing = DatabasePhishing()
        self.adblock_exceptions = DatabaseExceptions("adblock")
        self.popup_exceptions = DatabaseExceptions("popup")
        self.image_exceptions = DatabaseExceptions("image")
        if self.settings.get_user_value("jsblock") is not None:
            self.js_exceptions = DatabaseExceptions("js")
        else:
            self.js_exceptions = None
        self.phishing.update()
        self.art = Art()
        self.search = Search()
        self.download_manager = DownloadManager()
        self.pages_menu = PagesMenu()

        shortcut_action = Gio.SimpleAction.new('shortcut',
                                               GLib.VariantType.new('s'))
        shortcut_action.connect('activate', self.__on_shortcut_action)
        self.add_action(shortcut_action)
        self.set_accels_for_action("win.shortcut::expose", ["<Alt>e"])
        self.set_accels_for_action("win.exceptions::site", ["<Control>e"])
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
        self.set_accels_for_action("win.shortcut::save", ["<Control>s"])
        self.set_accels_for_action("win.shortcut::filter", ["<Control>i"])
        self.set_accels_for_action("win.shortcut::reload",
                                   ["<Control>r", "F5"])
        self.set_accels_for_action("win.shortcut::find", ["<Control>f"])
        self.set_accels_for_action("win.shortcut::print", ["<Control>p"])
        self.set_accels_for_action("win.shortcut::source",
                                   ["<Control><Shift>c"])
        self.set_accels_for_action("win.shortcut::history", ["<Control>h"])
        self.set_accels_for_action("win.shortcut::search", ["<Control>k"])
        self.set_accels_for_action("win.shortcut::fullscreen", ["F11"])
        self.set_accels_for_action("app.settings",
                                   ["<Control><Shift>s"])
        self.set_accels_for_action("win.shortcut::backward",
                                   ["<Alt>Left", "XF86Back"])
        self.set_accels_for_action("win.shortcut::forward",
                                   ["<Alt>Right", "XF86Forward"])
        self.set_accels_for_action("win.shortcut::next",
                                   ["<Control>Tab",
                                    "<Control>Page_Down"])
        self.set_accels_for_action("win.shortcut::previous",
                                   ["<Control><Shift>Tab",
                                    "<Control>Page_Up"])
        self.set_accels_for_action("win.shortcut::zoom_in",
                                   ["<Control>KP_Add",
                                    "<Control>plus",
                                    "<Control>equal"])
        self.set_accels_for_action("win.shortcut::zoom_out",
                                   ["<Control>KP_Subtract", "<Control>minus"])
        self.set_accels_for_action("win.shortcut::zoom_default",
                                   ["<Control>KP_0", "<Control>0"])

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
            with SqlCursor(self.phishing) as sql:
                sql.isolation_level = None
                sql.execute("VACUUM")
                sql.isolation_level = ""
        except Exception as e:
            print("Application::__vacuum(): ", e)
        self.art.vacuum()

    def __save_state(self):
        """
            Save window position and view
        """
        try:
            remember_session = self.settings.get_value("remember-session")
            session_states = []
            for window in self.get_windows():
                if not remember_session:
                    continue
                for view in window.container.views:
                    uri = view.webview.get_uri()
                    parsed = urlparse(uri)
                    if parsed.scheme not in ["http", "https"]:
                        continue
                    ephemeral = view.webview.ephemeral
                    state = view.webview.get_session_state().serialize()
                    session_states.append((uri, ephemeral, state.get_data()))
            if remember_session:
                dump(session_states,
                     open(EOLIE_LOCAL_PATH + "/session_states.bin", "wb"))
        except Exception as e:
            print("Application::__save_state()", e)

    def __restore_state(self):
        """
            Restore saved state
            @return True as bool if restored
        """
        window_type = Gdk.WindowType.CHILD
        try:
            session_states = load(open(
                                     EOLIE_LOCAL_PATH + "/session_states.bin",
                                     "rb"))
            for (uri, ephemeral, state) in session_states:
                webkit_state = WebKit2.WebViewSessionState(
                                                         GLib.Bytes.new(state))
                GLib.idle_add(self.active_window.container.add_webview,
                              uri, window_type, ephemeral,
                              None, webkit_state,
                              window_type == Gdk.WindowType.CHILD)
                window_type = Gdk.WindowType.OFFSCREEN
            dump([],
                 open(EOLIE_LOCAL_PATH + "/session_states.bin", "wb"))
        except Exception as e:
            print("Application::restore_state()", e)
        return window_type != Gdk.WindowType.CHILD

    def __on_handle_local_options(self, app, options):
        """
            Handle local options
            @param app as Gio.Application
            @param options as GLib.VariantDict
        """
        if options.contains("version"):
            print("Eolie %s" % self.__version)
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
        if options.contains("debug"):
            GLib.setenv("WEBKIT_DEBUG", "network", True)
            self.debug = True
        if options.contains("show-tls"):
            self.show_tls = True
        if options.contains("disable-artwork-cache"):
            self.art.disable_cache()
        ephemeral = options.contains("private")
        restored = False
        if self.settings.get_value("remember-session"):
            restored = self.__restore_state()
        if options.contains("new"):
            active_window = self.get_new_window()
        else:
            active_window = self.active_window
        # Open command line args
        if len(args) > 1:
            for uri in args[1:]:
                # Transform path to uri
                f = Gio.File.new_for_path(uri)
                if f.query_exists():
                    uri = f.get_uri()
                self.__new_or_load(uri, Gdk.WindowType.CHILD, ephemeral)
            active_window.present_with_time(Gtk.get_current_event_time())
        # Add default start page
        elif not restored:
            self.active_window.present_with_time(Gtk.get_current_event_time())
            self.__new_or_load(self.start_page,
                               Gdk.WindowType.CHILD,
                               ephemeral)
        if self.debug:
            WebKit2.WebContext.get_default().get_plugins(None,
                                                         self.__on_get_plugins,
                                                         None)
        return 0

    def __new_or_load(self, uri, window_type, ephemeral):
        """
            Check current webview, if uri is None, use it, else create
            a new webview
        """
        if self.active_window.container.current.webview.get_uri() is None:
            if ephemeral:
                self.active_window.container.pages_manager.close_view(
                                          self.active_window.container.current)
                self.active_window.container.add_webview(uri,
                                                         window_type,
                                                         ephemeral)
            else:
                self.active_window.container.current.webview.load_uri(uri)
        else:
            self.active_window.container.add_webview(uri,
                                                     window_type,
                                                     ephemeral)

    def __close_window(self, window):
        """
            Close window
        """
        if len(self.get_windows()) > 1:
            window.destroy()
        else:
            window.hide()
            self.quit(True)

    def __try_closing(self, window, views):
        """
            Try closing all views
        """
        if views:
            view = views.pop(0)
            page_id = view.webview.get_page_id()
            self.helper.call("FormsFilled",
                             GLib.Variant("(i)", (page_id,)),
                             self.__on_forms_filled, page_id, window, views)
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
            print("Application::__on_forms_filled():", e)

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
        # Ask for user if needed
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

    def __on_report_activate(self, action, param):
        """
            Launch bug report page
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        argv = ["uname", "-a", None]
        (s, o, e, s) = GLib.spawn_sync(None,
                                       argv,
                                       None,
                                       GLib.SpawnFlags.SEARCH_PATH,
                                       None)
        if o:
            os = o.decode("utf-8")
        else:
            os = "Unknown"

        github = "https://github.com/gnumdk/eolie/issues/new?body="
        body = """
TRANSLATORS:
https://translate.zanata.org/project/view/eolie

### Environment
- Eolie version: %s
- GTK+ version: %s.%s
- Operating system: %s

### Bug/Feature
If your bug is a rendering bug or a WebKit crash, you should report it here:
https://bugs.webkit.org -> Section WebKit Gtk -> title starting with [GTK]

<Describe your bug here>""" % (
                                self.__version,
                                Gtk.get_major_version(),
                                Gtk.get_minor_version(),
                                os)
        url = github + GLib.uri_escape_string(body, "", False)
        self.active_window.container.add_webview(url,
                                                 Gdk.WindowType.CHILD,
                                                 False)

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
        if self.get_windows():
            self.active_window.present_with_time(Gtk.get_current_event_time())

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
                                         Gdk.WindowType.CHILD)
