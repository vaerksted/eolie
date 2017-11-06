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
gi.require_version('WebKit2', '4.0')

from gi.repository import Gio, Gdk, Gtk, GLib

from gettext import gettext as _

from eolie.define import El
from eolie.utils import get_current_monitor_model
from eolie.helper_task import TaskHelper
from eolie.helper_passwords import PasswordsHelper


class Settings(Gio.Settings):
    """
        Eolie settings
    """

    def __init__(self):
        """
            Init settings
        """
        Gio.Settings.__init__(self)

    def new():
        """
            Return a new Settings object
        """
        settings = Gio.Settings.new("org.gnome.Eolie")
        settings.__class__ = Settings
        return settings


class SettingsDialog:
    """
        Dialog showing eolie options
    """

    def __init__(self, window):
        """
            Init dialog
            @param window as Window
        """
        self.__window = window
        self.__helper = PasswordsHelper()
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/SettingsDialog.ui")

        self.__settings_dialog = builder.get_object("settings_dialog")
        self.__settings_dialog.set_transient_for(window)
        # self.__settings_dialog.connect("destroy", self.__on_destroy)

        if False:
            self.__settings_dialog.set_title(_("Preferences"))
        else:
            headerbar = builder.get_object("header_bar")
            headerbar.set_title(_("Preferences"))
            self.__settings_dialog.set_titlebar(headerbar)

        download_chooser = builder.get_object("download_chooser")
        dir_uri = El().settings.get_value("download-uri").get_string()
        if not dir_uri:
            directory = GLib.get_user_special_dir(
                                         GLib.UserDirectory.DIRECTORY_DOWNLOAD)
            if directory is not None:
                dir_uri = GLib.filename_to_uri(directory, None)
        if dir_uri:
            download_chooser.set_uri(dir_uri)
        else:
            download_chooser.set_uri("file://" + GLib.getenv("HOME"))

        open_downloads = builder.get_object("open_downloads_check")
        open_downloads.set_active(
                                El().settings.get_value("open-downloads"))

        self.__start_page_uri = builder.get_object("start_page_uri")
        combo_start = builder.get_object("combo_start")
        start_page = El().settings.get_value("start-page").get_string()
        if start_page.startswith("http"):
            combo_start.set_active_id("address")
            self.__start_page_uri.set_text(start_page)
            self.__start_page_uri.show()
        else:
            combo_start.set_active_id(start_page)

        remember_session = builder.get_object("remember_sessions_check")
        remember_session.set_active(
                                El().settings.get_value("remember-session"))

        suggestions = builder.get_object("suggestions_check")
        suggestions.set_active(El().settings.get_value("enable-suggestions"))

        enable_dev_tools = builder.get_object("dev_tools_check")
        enable_dev_tools.set_active(
                                El().settings.get_value("developer-extras"))

        enable_plugins = builder.get_object("plugins_check")
        enable_plugins.set_active(
                                El().settings.get_value("enable-plugins"))

        self.__fonts_grid = builder.get_object("fonts_grid")
        use_system_fonts = builder.get_object("system_fonts_check")
        use_system_fonts.set_active(
                                El().settings.get_value("use-system-fonts"))
        self.__fonts_grid.set_sensitive(
                            not El().settings.get_value("use-system-fonts"))

        sans_serif_button = builder.get_object("sans_serif_button")
        sans_serif_button.set_font_name(
                       El().settings.get_value("font-sans-serif").get_string())
        serif_button = builder.get_object("serif_button")
        serif_button.set_font_name(
                       El().settings.get_value("font-serif").get_string())
        monospace_button = builder.get_object("monospace_button")
        monospace_button.set_font_name(
                       El().settings.get_value("font-monospace").get_string())

        min_font_size_spin = builder.get_object("min_font_size_spin")
        min_font_size_spin.set_value(
                       El().settings.get_value("min-font-size").get_int32())

        monitor_model = get_current_monitor_model(window)
        zoom_levels = El().settings.get_value("default-zoom-level")
        wanted_zoom_level = 1.0
        try:
            for zoom_level in zoom_levels:
                zoom_splited = zoom_level.split('@')
                if zoom_splited[0] == monitor_model:
                    wanted_zoom_level = float(zoom_splited[1])
        except:
            pass
        default_zoom_level = builder.get_object("default_zoom_level")
        default_zoom_level.set_value(float(wanted_zoom_level))

        cookies_combo = builder.get_object("cookies_combo")
        storage = El().settings.get_enum("cookie-storage")
        cookies_combo.set_active_id(str(storage))

        history_combo = builder.get_object("history_combo")
        storage = El().settings.get_enum("history-storage")
        history_combo.set_active_id(str(storage))

        self.__populars_count = builder.get_object("populars_count")
        if start_page in ["popular_book", "popular_hist"]:
            self.__populars_count.show()
        max_popular_items = El().settings.get_value(
                                              "max-popular-items").get_int32()
        builder.get_object("popular_spin_button").set_value(max_popular_items)
        remember_passwords = builder.get_object("remember_passwords_check")
        remember_passwords.set_active(
                                El().settings.get_value("remember-passwords"))

        dns_prediction_check = builder.get_object("dns_prediction_check")
        dns_prediction_check.set_active(
                                El().settings.get_value("dns-prediction"))
        tracking_check = builder.get_object("tracking_check")
        tracking_check.set_active(
                                El().settings.get_value("do-not-track"))
        self.__result_label = builder.get_object("result_label")
        self.__sync_button = builder.get_object("sync_button")
        self.__login_entry = builder.get_object("login_entry")
        self.__password_entry = builder.get_object("password_entry")
        self.__result_image = builder.get_object("result_image")
        builder.connect_signals(self)
        self.__helper.get_sync(self.__on_get_sync)

        task_helper = TaskHelper()
        task_helper.run(self.__get_sync_status)

    def show(self):
        """
            Show dialog
        """
        self.__settings_dialog.show()

#######################
# PROTECTED           #
#######################
    def _on_popular_spin_value_changed(self, button):
        """
            Save value
            @param button as Gtk.SpinButton
        """
        value = GLib.Variant("i", button.get_value())
        El().settings.set_value("max-popular-items", value)

    def _on_configure_engines_clicked(self, button):
        """
            Show Web engines configurator
            @param button as Gtk.Button
        """
        from eolie.dialog_search_engine import SearchEngineDialog
        dialog = SearchEngineDialog(self.__settings_dialog)
        dialog.run()

    def _on_clear_personnal_data_clicked(self, button):
        """
            Show clear personnal data dialog
            @param button as Gtk.button
        """
        from eolie.dialog_clear_data import ClearDataDialog
        dialog = ClearDataDialog(self.__settings_dialog)
        dialog.run()

    def _on_manage_cookies_clicked(self, button):
        """
            Show cookies popover
            @param button as Gtk.button
        """
        from eolie.popover_cookies import CookiesPopover
        popover = CookiesPopover()
        popover.populate()
        popover.set_relative_to(button)
        popover.popup()

    def _on_manage_passwords_clicked(self, button):
        """
            Launch searhorse
            @param button as Gtk.Button
        """
        from eolie.popover_passwords import PasswordsPopover
        popover = PasswordsPopover()
        popover.populate()
        popover.set_relative_to(button)
        popover.popup()

    def _on_dns_prediction_toggled(self, button):
        """
            Save state
            @param button as Gtk.ToggleButton
        """
        El().settings.set_value("dns-prediction",
                                GLib.Variant("b", button.get_active()))

    def _on_tracking_toggled(self, button):
        """
            Save state
            @param button as Gtk.ToggleButton
        """
        El().settings.set_value("do-not-track",
                                GLib.Variant("b", button.get_active()))

    def _on_cookies_changed(self, combo):
        """
            Save cookies setting
            @param combo as Gtk.ComboBoxText
        """
        El().settings.set_enum("cookie-storage", int(combo.get_active_id()))
        for window in El().windows:
            for view in window.container.views:
                context = view.webview.get_context()
                cookie_manager = context.get_cookie_manager()
                cookie_manager.set_accept_policy(
                                     El().settings.get_enum("cookie-storage"))

    def _on_history_changed(self, combo):
        """
            Save history keep setting
            @param combo as Gtk.ComboBoxText
        """
        El().settings.set_enum("history-storage", int(combo.get_active_id()))

    def _on_default_zoom_changed(self, button):
        """
            Save size
            @param button as Gtk.SpinButton
        """
        monitor_model = get_current_monitor_model(
                                    self.__settings_dialog.get_transient_for())
        try:
            # Add current value less monitor model
            zoom_levels = []
            for zoom_level in El().settings.get_value("default-zoom-level"):
                zoom_splited = zoom_level.split('@')
                if zoom_splited[0] == monitor_model:
                    continue
                else:
                    zoom_levels.append("%s@%s" % (zoom_splited[0],
                                                  zoom_splited[1]))
            # Add new zoom value for monitor model
            zoom_levels.append("%s@%s" % (monitor_model, button.get_value()))
            El().settings.set_value("default-zoom-level",
                                    GLib.Variant("as", zoom_levels))
            for window in El().windows:
                window.update_zoom_level(True)
        except Exception as e:
            print("SettingsDialog::_on_default_zoom_changed():", e)

    def _on_min_font_size_changed(self, button):
        """
            Save size
            @param button as Gtk.SpinButton
        """
        value = GLib.Variant("i", button.get_value())
        El().settings.set_value("min-font-size", value)
        El().set_setting("minimum-font-size", button.get_value())

    def _on_system_fonts_toggled(self, button):
        """
            Save state
            @param button as Gtk.ToggleButton
        """
        self.__fonts_grid.set_sensitive(not button.get_active())
        El().settings.set_value("use-system-fonts",
                                GLib.Variant("b", button.get_active()))

    def _on_font_sans_serif_set(self, fontbutton):
        """
            Save font setting
            @param fontchooser as Gtk.FontButton
        """
        value = GLib.Variant("s", fontbutton.get_font_name())
        El().settings.set_value("font-sans-serif", value)
        El().set_setting("sans-serif-font-family", fontbutton.get_font_name())

    def _on_font_serif_set(self, fontbutton):
        """
            Save font setting
            @param fontchooser as Gtk.FontButton
        """
        value = GLib.Variant("s", fontbutton.get_font_name())
        El().settings.set_value("font-serif", value)
        El().set_setting("serif-font-family", fontbutton.get_font_name())

    def _on_font_monospace_set(self, fontbutton):
        """
            Save font setting
            @param fontchooser as Gtk.FontButton
        """
        value = GLib.Variant("s", fontbutton.get_font_name())
        El().settings.set_value("font-monospace", value)
        El().set_setting("monospace-font-family", fontbutton.get_font_name())

    def _on_plugins_toggled(self, button):
        """
            Save state
            @param button as Gtk.ToggleButton
        """
        value = GLib.Variant("b", button.get_active())
        El().settings.set_value("enable-plugins", value)
        El().set_setting("enable-plugins", button.get_active())

    def _on_dev_tools_toggled(self, button):
        """
            Save state
            @param button as Gtk.ToggleButton
        """
        value = GLib.Variant("b", button.get_active())
        El().settings.set_value("developer-extras", value)

    def _on_remember_passwords_toggled(self, button):
        """
            Save state
            @param button as Gtk.ToggleButton
        """
        El().settings.set_value("remember-passwords",
                                GLib.Variant("b", button.get_active()))

    def _on_remember_sessions_toggled(self, button):
        """
            Save state
            @param button as Gtk.ToggleButton
        """
        El().settings.set_value("remember-session",
                                GLib.Variant("b", button.get_active()))

    def _on_suggestions_toggled(self, button):
        """
            Save state
            @param button as Gtk.ToggleButton
        """
        El().settings.set_value("enable-suggestions",
                                GLib.Variant("b", button.get_active()))

    def _on_start_page_uri_changed(self, entry):
        """
            Save startup page
            @param entry as Gtk.Entry
        """
        El().settings.set_value("start-page",
                                GLib.Variant("s", entry.get_text()))

    def _on_start_changed(self, combo):
        """
            Save startup page
            @param combo as Gtk.ComboBoxText
        """
        self.__start_page_uri.hide()
        self.__populars_count.hide()
        if combo.get_active_id() == "address":
            self.__start_page_uri.show()
        elif combo.get_active_id() in ["popular_hist", "popular_book"]:
            self.__populars_count.show()
        El().settings.set_value("start-page",
                                GLib.Variant("s", combo.get_active_id()))

    def _on_engine_changed(self, combo):
        """
            Save engine
            @param combo as Gtk.ComboBoxText
        """
        El().settings.set_value("search-engine",
                                GLib.Variant("s", combo.get_active_id()))
        El().search.update_default_engine()

    def _on_open_downloads_toggled(self, button):
        """
            Save state
            @param button as Gtk.ToggleButton
        """
        El().settings.set_value("open-downloads",
                                GLib.Variant("b", button.get_active()))

    def _on_selection_changed(self, chooser):
        """
            Save uri
            @chooser as Gtk.FileChooserButton
        """
        uri = chooser.get_uri()
        if uri is None:
            uri = ""
        El().settings.set_value("download-uri", GLib.Variant("s", uri))

    def _on_key_release_event(self, widget, event):
        """
            Destroy window if Esc
            @param widget as Gtk.Widget
            @param event as Gdk.event
        """
        if event.keyval == Gdk.KEY_Escape:
            self.__settings_dialog.destroy()

    def _on_sync_button_clicked(self, button):
        """
            Connect to Mozilla Sync to get tokens
            @param button as Gtk.Button
        """
        icon_name = self.__result_image.get_icon_name()[0]
        login = self.__login_entry.get_text()
        password = self.__password_entry.get_text()
        if icon_name == "network-transmit-receive-symbolic":
            El().sync_worker.stop(True)
            El().sync_worker.delete_secret()
            self.__setup_sync_button(False)
        elif login and password:
            self.__result_label.set_text(_("Connecting…"))
            button.set_sensitive(False)
            self.__result_image.set_from_icon_name("content-loading-symbolic",
                                                   Gtk.IconSize.MENU)
            task_helper = TaskHelper()
            task_helper.run(self.__connect_mozilla_sync,
                            self.__login_entry.get_text(),
                            self.__password_entry.get_text())

#######################
# PRIVATE             #
#######################
    def __get_sync_status(self):
        """
            Get sync status
            @thread safe
        """
        if El().sync_worker is not None:
            status = El().sync_worker.status
            GLib.idle_add(self.__setup_sync_button, status)
        else:
            GLib.idle_add(self.__missing_fxa)

    def __setup_sync_button(self, status):
        """
            Setup sync button based on current sync status
            @param status as bool
        """
        self.__sync_button.set_sensitive(True)
        self.__sync_button.get_style_context().remove_class(
                                                          "destructive-action")
        self.__sync_button.get_style_context().remove_class(
                                                          "suggested-action")
        if status:
            self.__result_label.set_text(_("Synchronization is working"))
            self.__result_image.set_from_icon_name(
                                     "network-transmit-receive-symbolic",
                                     Gtk.IconSize.MENU)
            self.__sync_button.get_style_context().add_class(
                                                      "destructive-action")
            self.__sync_button.set_label(_("Cancel synchronization"))
        else:
            self.__sync_button.get_style_context().add_class(
                                                      "suggested-action")
            self.__sync_button.set_label(_("Allow synchronization"))
            self.__result_image.set_from_icon_name(
                                 "computer-fail-symbolic",
                                 Gtk.IconSize.MENU)
            self.__result_label.set_text(
                                   _("Synchronization is not working"))

    def __missing_fxa(self):
        """
            Show a message about missing fxa module
        """
        from eolie.mozilla_sync import SyncWorker
        if not SyncWorker.check_modules():
            cmd = "<b>$ pip3 install requests-hawk\n"\
                  "PyFxA pycrypto cryptography</b>"
            self.__result_label.set_markup(
                  _("Synchronization is not available"
                    " on your computer:\n %s") % cmd)
            self.__sync_button.set_sensitive(False)

    def __connect_mozilla_sync(self, username, password):
        """
            Connect to mozilla sync
            @param username as str
            @param password as str
            @thread safe
        """
        try:
            El().sync_worker.new_session()
            El().sync_worker.login({"login": username}, password)
            GLib.idle_add(self.__setup_sync_button, True)
        except Exception as e:
            print("SettingsDialog::__connect_mozilla_sync():", e)
            GLib.idle_add(self.__sync_button.set_sensitive, True)
            if str(e) == "Unverified account":
                GLib.timeout_add(500, self.__settings_dialog.destroy)
                self.__window.toolbar.end.show_sync_button()
                GLib.idle_add(
                    El().active_window.toolbar.title.show_message,
                    _("You've received an email"
                      " to validate synchronization"))
            else:
                GLib.idle_add(self.__result_label.set_text, str(e))
                GLib.idle_add(self.__result_image.set_from_icon_name,
                              "computer-fail-symbolic",
                              Gtk.IconSize.MENU)

    def __on_get_sync(self, attributes, password, uri, index, count):
        """
            Set username and password
            @param attributes as {}
            @param password as str
            @param uri as None
            @param index as int
            @param count as int
        """
        if attributes is None:
            return
        try:
            self.__login_entry.set_text(attributes["login"])
            self.__password_entry.set_text(password)
        except Exception as e:
            print("SettingsDialog::__on_get_sync()", e)
