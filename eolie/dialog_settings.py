# Copyright (c) 2014-2020 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from gi.repository import Gtk, GLib, Gdk

from gettext import gettext as _

from eolie.utils import get_current_monitor_model
from eolie.helper_passwords import PasswordsHelper
from eolie.logger import Logger
from eolie.define import App


class SettingsDialog:
    """
        Dialog showing Eolie settings
    """

    __BOOLEAN = ["night-mode", "use-system-fonts", "remember-session",
                 "open-downloads", "enable-plugins", "developer-extras",
                 "do-not-track", "autoplay-videos", "remember-passwords",
                 "enable-firefox-sync", "enable-suggestions"]

    __RANGE = ["min-font-size", "max-popular-items"]
    __COMBO = ["start-page", "cookie-storage", "history-storage"]
    __ENTRY = ["start-page-custom"]
    __LOCKED_ON = {"use-system-fonts": ["sans-serif_row",
                                        "serif_row",
                                        "monospace_row"]}
    __LOCKED_OFF = {"enable-firefox-sync": ["status_row",
                                            "sync_row",
                                            "configure_row"]}

    def __init__(self, window):
        """
            Init dialog
            @param window as Window
        """
        self.__window = window
        self.__locked = []
        self.__passwords_helper = PasswordsHelper()
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/SettingsDialog.ui")
        self.__settings_dialog = builder.get_object("settings_dialog")
        self.__start_page_custom_entry = builder.get_object(
            "start-page-custom_entry")
        # Firefox sync
        self.__status_row = builder.get_object("status_row")
        self.__sync_button = builder.get_object("sync_button")
        self.__username_entry = builder.get_object("username_entry")
        self.__password_entry = builder.get_object("password_entry")
        self.__code_entry = builder.get_object("code_entry")
        for dic in [self.__LOCKED_ON, self.__LOCKED_OFF]:
            for key in dic.keys():
                for locked in dic[key]:
                    widget = builder.get_object(locked)
                    widget.set_name(key)
                    self.__locked.append(widget)
        self.__set_default_zoom_level(builder.get_object("default_zoom_level"))
        download_chooser = builder.get_object("download_chooser")
        dir_uri = App().settings.get_value("download-uri").get_string()
        if not dir_uri:
            directory = GLib.get_user_special_dir(
                GLib.UserDirectory.DIRECTORY_DOWNLOAD)
            if directory is not None:
                dir_uri = GLib.filename_to_uri(directory, None)
        if dir_uri:
            download_chooser.set_uri(dir_uri)
        else:
            download_chooser.set_uri("file://" + GLib.getenv("HOME"))
        builder.connect_signals(self)
        for setting in self.__BOOLEAN:
            button = builder.get_object("%s_boolean" % setting)
            value = App().settings.get_value(setting)
            # Only setting switch on fires a signal
            if value:
                button.set_state(value)
            else:
                self._on_boolean_state_set(button, False)
        for setting in self.__ENTRY:
            entry = builder.get_object("%s_entry" % setting)
            value = App().settings.get_value(setting).get_string()
            entry.set_text(value)
        for setting in self.__RANGE:
            widget = builder.get_object("%s_range" % setting)
            value = App().settings.get_value(setting).get_int32()
            widget.set_value(value)
        for setting in self.__COMBO:
            widget = builder.get_object("%s_combo" % setting)
            value = App().settings.get_enum(setting)
            widget.set_active(value)
        self.__multi_press = Gtk.EventControllerKey.new(self.__settings_dialog)
        self.__multi_press.connect("key-released", self.__on_key_released)
        self.__passwords_helper.get_sync(self.__on_get_sync)
        self.__check_sync_status()
        App().sync_worker.connect("syncing", self.__on_syncing)

    def show(self):
        """
            Show dialog
        """
        self.__settings_dialog.show()

    @property
    def stack(self):
        """
            Get main stack
            @return Gtk.Stack
        """
        return self.__settings_dialog.get_child()

#######################
# PROTECTED           #
#######################
    def _on_dialog_destroy(self, widget):
        """
            Clean up
            @param widget as Gtk.Widget
        """
        App().sync_worker.disconnect_by_func(self.__on_syncing)

    def _on_boolean_state_set(self, widget, state):
        """
            Save setting
            @param widget as Gtk.Switch
            @param state as bool
        """
        setting = widget.get_name()
        App().settings.set_value(setting,
                                 GLib.Variant("b", state))
        if setting in self.__LOCKED_ON.keys():
            self.__lock_for_setting(setting, not state)
        elif setting in self.__LOCKED_OFF.keys():
            self.__lock_for_setting(setting, state)
        if setting == "enable-firefox-sync":
            if state:
                App().sync_worker.set_credentials()
                App().sync_worker.pull_loop()
                self.__status_row.set_subtitle(_("Connecting…"))
                GLib.timeout_add(5000, self.__check_sync_status)
            else:
                App().sync_worker.stop(True)
                self.__status_row.set_subtitle(_("Not running"))

    def _on_range_changed(self, widget):
        """
            Save value
            @param widget as Gtk.Range
        """
        setting = widget.get_name()
        value = widget.get_value()
        App().settings.set_value(setting, GLib.Variant("i", value))

    def _on_entry_changed(self, widget):
        """
            Save value
            @param widget as Gtk.Entry
        """
        setting = widget.get_name()
        value = widget.get_text()
        App().settings.set_value(setting, GLib.Variant("s", value))

    def _on_combo_changed(self, widget):
        """
            Save value
            @param widget as Gtk.ComboBoxText
        """
        setting = widget.get_name()
        value = widget.get_active()
        App().settings.set_enum(setting, value)
        if setting == "start-page":
            if value == 4:
                self.__start_page_custom_entry.show()
            else:
                self.__start_page_custom_entry.hide()

    def _on_selection_changed(self, chooser):
        """
            Save uri
            @chooser as Gtk.FileChooserButton
        """
        uri = chooser.get_uri()
        if uri is None:
            uri = ""
        App().settings.set_value("download-uri", GLib.Variant("s", uri))

    def _on_font_sans_serif_set(self, fontbutton):
        """
            Save font setting
            @param fontchooser as Gtk.FontButton
        """
        value = GLib.Variant("s", fontbutton.get_font_name())
        App().settings.set_value("font-sans-serif", value)
        App().set_setting("sans-serif-font-family", fontbutton.get_font_name())

    def _on_font_serif_set(self, fontbutton):
        """
            Save font setting
            @param fontchooser as Gtk.FontButton
        """
        value = GLib.Variant("s", fontbutton.get_font_name())
        App().settings.set_value("font-serif", value)
        App().set_setting("serif-font-family", fontbutton.get_font_name())

    def _on_font_monospace_set(self, fontbutton):
        """
            Save font setting
            @param fontchooser as Gtk.FontButton
        """
        value = GLib.Variant("s", fontbutton.get_font_name())
        App().settings.set_value("font-monospace", value)
        App().set_setting("monospace-font-family", fontbutton.get_font_name())

    def _on_configure_engines_clicked(self, button):
        """
            Show Web engines configurator
            @param button as Gtk.Button
        """
        from eolie.dialog_search_engine import SearchEngineDialog
        dialog = SearchEngineDialog()
        dialog.show()
        dialog.connect("destroy-me", self.__on_sub_dialog_destroyed)
        self.stack.add(dialog)
        self.stack.set_visible_child(dialog)

    def _on_clear_personnal_data_clicked(self, button):
        """
            Show clear personnal data dialog
            @param button as Gtk.button
        """
        from eolie.dialog_clear_data import ClearDataDialog
        dialog = ClearDataDialog()
        dialog.show()
        dialog.connect("destroy-me", self.__on_sub_dialog_destroyed)
        self.stack.add(dialog)
        self.stack.set_visible_child(dialog)

    def _on_manage_cookies_clicked(self, button):
        """
            Show cookies popover
            @param button as Gtk.button
        """
        from eolie.dialog_cookies import CookiesDialog
        dialog = CookiesDialog()
        dialog.show()
        dialog.connect("destroy-me", self.__on_sub_dialog_destroyed)
        self.stack.add(dialog)
        self.stack.set_visible_child(dialog)

    def _on_manage_passwords_clicked(self, button):
        """
            Launch searhorse
            @param button as Gtk.Button
        """
        from eolie.dialog_credentials import CredentialsDialog
        dialog = CredentialsDialog()
        dialog.show()
        dialog.connect("destroy-me", self.__on_sub_dialog_destroyed)
        self.stack.add(dialog)
        self.stack.set_visible_child(dialog)

    def _on_sync_now_clicked(self, button):
        """
            Sync now with Firefox Sync
            @param button as Gtk.Button
        """
        App().sync_worker.pull(True)
        App().sync_worker.push()

    def _on_sync_button_clicked(self, button):
        """
            Connect to Firefox Sync to get tokens
            @param button as Gtk.Button
        """
        if button.get_style_context().has_class("suggested-action"):
            button.get_style_context().remove_class("destructive-action")
            self.__status_row.set_subtitle(_("Connecting…"))
            self.__result_image.set_from_icon_name("content-loading-symbolic",
                                                   Gtk.IconSize.MENU)
            App().task_helper.run(self.__connect_firefox_sync,
                                  self.__username_entry.get_text(),
                                  self.__password_entry.get_text(),
                                  self.__code_entry.get_text(),
                                  callback=(self.__on_sync_result,))
        else:
            App().sync_worker.stop(True)
            App().sync_worker.delete_secret()
            button.get_style_context().remove_class("suggested-action")
            button.get_style_context().add_class("destructive-action")
            self.__status_row.set_subtitle(_("Stopped…"))

    def _on_credentials_changed(self, entry):
        """
            Update widgets state
            @param entry as Gtk.Entry
        """
        credentials_ok = self.__username_entry.get_text() != "" and (
            self.__password_entry.get_text() != "" or
            self.__code_entry.get_text() != "")
        self.__sync_button.set_sensitive(credentials_ok)
        if self.__password_entry.get_text() != "":
            self.__password_entry.set_sensitive(True)
            self.__code_entry.set_sensitive(False)
        elif self.__code_entry.get_text() != "":
            self.__password_entry.set_sensitive(False)
            self.__code_entry.set_sensitive(True)
        else:
            self.__password_entry.set_sensitive(True)
            self.__code_entry.set_sensitive(True)

#######################
# PRIVATE             #
#######################
    def __check_sync_status(self):
        """
            Check worker status
        """
        App().task_helper.run(self.__get_sync_status,
                              callback=(self.__on_get_sync_status,))

    def __lock_for_setting(self, setting, sensitive):
        """
            Lock widgets for setting
            @param setting as str
            @param sensitive as bool
        """
        for locked in self.__locked:
            if locked.get_name() == setting:
                locked.set_sensitive(sensitive)

    def __get_sync_status(self):
        """
            Get sync status
            return int
        """
        if App().sync_worker is not None:
            return App().sync_worker.status
        else:
            return -1

    def __connect_firefox_sync(self, username, password, code):
        """
            Connect to firefox sync
            @param username as str
            @param password as str
            @param code as str
        """
        try:
            App().sync_worker.new_session()
            App().sync_worker.login({"login": username}, password, code)
            return True
        except Exception as e:
            Logger.error("SettingsDialog::__connect_firefox_sync(): %s", e)
            return False

    def __set_default_zoom_level(self, widget):
        """
            Set default zoom level
            @param widget as Gtk.SpinButton
        """
        monitor_model = get_current_monitor_model(self.__window)
        zoom_levels = App().settings.get_value("default-zoom-level")
        wanted_zoom_level = 1.0
        try:
            for zoom_level in zoom_levels:
                zoom_splited = zoom_level.split('@')
                if zoom_splited[0] == monitor_model:
                    wanted_zoom_level = float(zoom_splited[1])
        except:
            pass
        percent_zoom = int(wanted_zoom_level * 100)
        widget.set_value(percent_zoom)
        widget.set_text("{} %".format(percent_zoom))
        widget.connect("value-changed", self.__on_default_zoom_changed)

    def __on_default_zoom_changed(self, button):
        """
            Save size
            @param button as Gtk.SpinButton
        """
        button.set_text("{} %".format(int(button.get_value())))
        monitor_model = get_current_monitor_model(self.__window)
        try:
            # Add current value less monitor model
            zoom_levels = []
            for zoom_level in App().settings.get_value("default-zoom-level"):
                zoom_splited = zoom_level.split('@')
                if zoom_splited[0] == monitor_model:
                    continue
                else:
                    zoom_levels.append("%s@%s" % (zoom_splited[0],
                                                  zoom_splited[1]))
            # Add new zoom value for monitor model
            zoom_levels.append("%s@%s" % (monitor_model,
                                          button.get_value() / 100))
            App().settings.set_value("default-zoom-level",
                                     GLib.Variant("as", zoom_levels))
            for window in App().windows:
                window.update_zoom_level(True)
        except Exception as e:
            Logger.error("SettingsDialog::__on_default_zoom_changed(): %s", e)

    def __on_key_released(self, event_controller, keyval, keycode, state):
        """
            Quit on escape
            @param event_controller as Gtk.EventController
            @param keyval as int
            @param keycode as int
            @param state as Gdk.ModifierType
        """
        if keyval == Gdk.KEY_Escape:
            self.__settings_dialog.destroy()

    def __on_sync_result(self, result):
        """
            Show result to user
            @param result as bool
        """
        if result:
            self.__status_row.set_subtitle(_("Connected"))
        else:
            self.__status_row.set_subtitle(_("Failed"))

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
            self.__username_entry.set_text(attributes["login"])
        except Exception as e:
            Logger.error("SettingsDialog::__on_get_sync(): %s", e)

    def __on_get_sync_status(self, status):
        """
            Show a message about missing fxa module
            @param status as bool
        """
        if status:
            self.__status_row.set_subtitle(_("Connected"))
            App().sync_worker.pull_loop()
        else:
            from eolie.firefox_sync import SyncWorker
            if not SyncWorker.check_modules():
                cmd = "<b>$ pip3 install requests-hawk\n"\
                      "PyFxA pycrypto cryptography</b>"
                self.__status_row.set_subtitle(
                    _("Syncing is not available"
                        " on your computer:\n%s") % cmd)
            else:
                self.__status_row.set_subtitle(_("Not running"))

    def __on_syncing(self, worker, message):
        """
            Show message as status
            @param worker as SyncWorker
            @param message as str
        """
        self.__status_row.set_subtitle(_("Syncing %s") % message)

    def __on_sub_dialog_destroyed(self, widget):
        """
            Restore previous dialog
            @param widget as Gtk.Widget
        """
        for child in self.stack.get_children():
            if child != widget:
                self.stack.set_visible_child(child)
                break
        GLib.timeout_add(1000, widget.destroy)
