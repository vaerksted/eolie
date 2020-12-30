# Copyright (c) 2017-2020 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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
from urllib.parse import urlparse

from eolie.menu_languages import LanguagesMenu
from eolie.menu_scripts import ScriptsMenu
from eolie.define import App
from eolie.utils import get_safe_netloc


class ToolbarMenu(Gtk.PopoverMenu):
    """
        Gtk.PopoverMenu showing main menu
    """

    def __init__(self, uri, window, toolbar):
        """
            Init self
            @param uri as str
            @param window as Window
            THIS IS FUCKING IDIOT, MOVE CODE FROM TOOLBAR HERE NOW BUTTONS
            ARE NOT IN TOOLBAR ANYMORE
            @param toolbar as ToolbarEnd
        """
        Gtk.PopoverMenu.__init__(self)
        self.__uri = uri
        self.__window = window
        self.__toolbar = toolbar
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/ToolbarMenu.ui")
        fullscreen_button = builder.get_object("fullscreen_button")
        if self.__window.is_fullscreen:
            fullscreen_button.set_active(True)
            fullscreen_button.set_tooltip_text(_("Leave fullscreen"))
        else:
            fullscreen_button.set_tooltip_text(_("Enter fullscreen"))
        builder.connect_signals(self)
        widget = builder.get_object("widget")
        self.add(widget)
        webview = self.__window.container.webview
        builder.get_object("default_zoom_button").set_label(
            "{} %".format(int(webview.get_zoom_level() * 100)))
        netloc = get_safe_netloc(uri)
        parsed = urlparse(uri)
        builder.get_object("domain_label").set_text(netloc)
        if parsed.scheme in ["http", "https"]:
            # Add blocker actions
            for blocker in ["block-ads", "block-popups",
                            "block-images", "block-medias"]:
                if not App().settings.get_value(blocker):
                    continue
                builder.get_object(blocker).show()
                content_blocker = App().get_content_blocker(blocker)
                exception = content_blocker.exceptions.is_domain_exception(
                    netloc)
                action = Gio.SimpleAction.new_stateful(
                    "%s-exception" % blocker,
                    None,
                    GLib.Variant.new_boolean(exception))
                action.connect("change-state",
                               self.__on_exception_change_state,
                               netloc,
                               blocker)
                window.add_action(action)
            # Audio policy
            netloc_audio = App().websettings.get("audio", uri)
            builder.get_object("audio_policy").show()
            action = Gio.SimpleAction.new_stateful(
                    "audio-policy",
                    None,
                    GLib.Variant.new_boolean(netloc_audio))
            action.connect("change-state",
                           self.__on_audio_policy_change_state,
                           uri)
            window.add_action(action)
            # Night mode
            night_mode = App().settings.get_value("night-mode")
            netloc_night_mode = App().websettings.get("night_mode", uri)
            builder.get_object("night_mode").show()
            enabled = night_mode and netloc_night_mode in [1, None]
            action = Gio.SimpleAction.new_stateful(
                    "night-mode",
                    None,
                    GLib.Variant.new_boolean(enabled))
            action.connect("change-state",
                           self.__on_night_mode_change_state,
                           uri)
            window.add_action(action)
            # Scripts
            if App().settings.get_value("block-scripts"):
                builder.get_object("scripts").show()
                scripts_menu = ScriptsMenu(uri, self.__window)
                scripts_menu.show()
                self.add(scripts_menu)
                self.child_set_property(scripts_menu, "submenu", "scripts")
            # Languages
            builder.get_object("spell-checking").show()
            languages_menu = LanguagesMenu(uri)
            languages_menu.show()
            self.add(languages_menu)
            self.child_set_property(languages_menu, "submenu", "languages")

#######################
# PROTECTED           #
#######################
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

    def _on_zoom_button_clicked(self, button):
        """
            Zoom current page
            @param button as Gtk.Button
        """
        webview = self.__window.container.webview
        current = webview.zoom_in()
        button.set_label("{} %".format(current))

    def _on_unzoom_button_clicked(self, button):
        """
            Unzoom current page
            @param button as Gtk.Button
        """
        webview = self.__window.container.webview
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
        webview = self.__window.container.webview
        current = webview.zoom_default()
        button.set_label("{} %".format(current))

#######################
# PRIVATE             #
#######################
    def __on_exception_change_state(self, action, param, domain, blocker):
        """
            Set option value
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
            @param domain as str
            @param blocker as str
        """
        action.set_state(param)
        content_blocker = App().get_content_blocker(blocker)
        if content_blocker.exceptions.is_domain_exception(domain):
            content_blocker.exceptions.remove_domain_exception(domain)
        else:
            content_blocker.exceptions.add_domain_exception(domain)
        content_blocker.exceptions.save()
        content_blocker.update()
        self.__window.container.webview.reload()

    def __on_night_mode_change_state(self, action, param, uri):
        """
            Set night mode value
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
            @param uri as str
        """
        action.set_state(param)
        App().websettings.set("night_mode", uri, param.get_boolean())
        self.__window.container.webview.night_mode()

    def __on_audio_policy_change_state(self, action, param, uri):
        """
            Set audio policy for URI
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
            @param uri as str
        """
        action.set_state(param)
        value = param.get_boolean()
        App().websettings.set("audio", uri, value)
        self.__window.container.webview.update_sound_policy()
