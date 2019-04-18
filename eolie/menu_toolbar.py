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

from gi.repository import Gtk, Gio, GLib

from gettext import gettext as _

from eolie.menu_languages import LanguagesMenu
from eolie.menu_block import JSBlockMenu, AdblockMenu
from eolie.menu_block import PopupBlockMenu, ImageBlockMenu
from eolie.define import App


class ToolbarMenu(Gtk.PopoverMenu):
    """
        Gtk.PopoverMenu showing main menu
    """

    def __init__(self, uri, window, toolbar):
        """
            Init self
            @param uri as str
            @param window as Window
            @param toolbar as ToolbarEnd
        """
        Gtk.PopoverMenu.__init__(self)
        self.__uri = uri
        self.__window = window
        self.__toolbar = toolbar
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/ToolbarMenu.ui")
        if not toolbar.home_button.is_visible():
            builder.get_object("toolbar_items").show()
        fullscreen_button = builder.get_object("fullscreen_button")
        if self.__window.is_fullscreen:
            fullscreen_button.set_active(True)
            fullscreen_button.set_tooltip_text(_("Leave fullscreen"))
        else:
            fullscreen_button.set_tooltip_text(_("Enter fullscreen"))
        builder.connect_signals(self)
        widget = builder.get_object("widget")
        webview = self.__window.container.current.webview
        builder.get_object("default_zoom_button").set_label(
            "{} %".format(int(webview.get_zoom_level() * 100)))
        adblock_menu = AdblockMenu(uri, self.__window)
        adblock_menu.show()
        js_block_menu = JSBlockMenu(uri, self.__window)
        js_block_menu.show()
        popup_block_menu = PopupBlockMenu(uri, self.__window)
        popup_block_menu.show()
        image_block_menu = ImageBlockMenu(uri, self.__window)
        image_block_menu.show()
        languages_menu = LanguagesMenu(uri)
        languages_menu.show()

        # Add items
        self.add(widget)
        self.add(adblock_menu)
        self.add(popup_block_menu)
        self.add(js_block_menu)
        self.add(image_block_menu)
        self.add(languages_menu)
        self.child_set_property(adblock_menu, "submenu", "adblock_menu")
        self.child_set_property(js_block_menu, "submenu", "js_block_menu")
        self.child_set_property(popup_block_menu,
                                "submenu", "popup_block_menu")
        self.child_set_property(image_block_menu,
                                "submenu", "image_block_menu")
        self.child_set_property(languages_menu, "submenu", "languages")

        # Add old «Application Menu»
        settings_action = Gio.SimpleAction.new("settings", None)
        settings_action.connect("activate", self.__on_settings_activate)
        App().add_action(settings_action)

        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self.__on_about_activate)
        App().add_action(about_action)

        show_sidebar = App().settings.get_value("show-sidebar")
        sidebar_action = Gio.SimpleAction.new_stateful(
            "sidebar",
            None,
            GLib.Variant.new_boolean(show_sidebar))
        sidebar_action.connect("change-state", self.__on_sidebar_change_state)
        App().add_action(sidebar_action)

        shortcuts_action = Gio.SimpleAction.new("shortcuts", None)
        shortcuts_action.connect("activate", self.__on_shortcuts_activate)
        App().add_action(shortcuts_action)

        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda x, y: App().quit())
        App().add_action(quit_action)

#######################
# PROTECTED           #
#######################
    def _on_home_button_clicked(self, button):
        """
            Go to home page
            @param button as Gtk.Button
        """
        self.__toolbar._on_home_button_clicked(button)

    def _on_print_button_clicked(self, button):
        """
            Print current page
            @param button as Gtk.button
        """
        self.__toolbar._on_print_button_clicked(button)

    def _on_save_button_clicked(self, button):
        """
            Save current page
            @param button as Gtk.Button
        """
        self.__toolbar._on_save_button_clicked(button)

    def _on_download_button_toggled(self, button):
        """
            Show download popover
            @param button as Gtk.Button
        """
        self.__toolbar._on_download_button_toggled(self.__toolbar.menu_button)

    def _on_zoom_button_clicked(self, button):
        """
            Zoom current page
            @param button as Gtk.Button
        """
        webview = self.__window.container.current.webview
        current = webview.zoom_in()
        button.set_label("{} %".format(current))

    def _on_unzoom_button_clicked(self, button):
        """
            Unzoom current page
            @param button as Gtk.Button
        """
        webview = self.__window.container.current.webview
        current = webview.zoom_out()
        button.set_label("{} %".format(current))

    def _on_fullscreen_button_toggled(self, button):
        """
            Restore default zoom level
            @param button as Gtk.ToggleButton
        """
        button.get_ancestor(Gtk.Popover).hide()
        if button.get_active():
            if not self.__window.is_fullscreen:
                self.__window.fullscreen()
        else:
            if self.__window.is_fullscreen:
                self.__window.unfullscreen()

    def _on_default_zoom_button_clicked(self, button):
        """
            Restore default zoom level
            @param button as Gtk.Button
        """
        webview = self.__window.container.current.webview
        current = webview.zoom_default()
        button.set_label("{} %".format(current))

#######################
# PRIVATE             #
#######################
    def __on_settings_activate(self, action, param):
        """
            Show settings dialog
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        from eolie.settings import SettingsDialog
        dialog = SettingsDialog(self.__window)
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
        about.set_transient_for(self.__window)
        about.connect("response", self.__on_about_activate_response)
        about.show()

    def __on_shortcuts_activate(self, action, param):
        """
            Show shortcuts
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/Shortcuts.ui")
        shortcuts = builder.get_object("shortcuts")
        shortcuts.set_transient_for(self.__window)
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
        App().settings.set_value("show-sidebar", GLib.Variant("b", value))
