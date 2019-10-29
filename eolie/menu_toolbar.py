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

from gi.repository import Gtk

from gettext import gettext as _

from eolie.menu_languages import LanguagesMenu
from eolie.menu_block import BlockMenu


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
        block_menu = BlockMenu(uri, self.__window)
        block_menu.show()
        languages_menu = LanguagesMenu(uri)
        languages_menu.show()

        # Add items
        self.add(widget)
        self.add(block_menu)
        self.add(languages_menu)
        self.child_set_property(block_menu, "submenu", "block_menu")
        self.child_set_property(languages_menu, "submenu", "languages")

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
