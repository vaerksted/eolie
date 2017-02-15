# Copyright (c) 2014-2016 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from gi.repository import Gtk, GLib, Gio

from urllib.parse import urlparse

from eolie.define import El
from eolie.popover_downloads import DownloadsPopover


class ProgressBar(Gtk.ProgressBar):
    """
        Simple progress bar with width contraint and event pass through
    """
    def __init__(self, parent):
        Gtk.ProgressBar.__init__(self)
        self.__parent = parent
        self.set_property("valign", Gtk.Align.END)

    def do_get_preferred_width(self):
        return (24, 24)


class ToolbarEnd(Gtk.Bin):
    """
        Toolbar end
    """

    def __init__(self):
        """
            Init toolbar
        """
        Gtk.Bin.__init__(self)
        self.__timeout_id = None
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/ToolbarEnd.ui")
        builder.connect_signals(self)
        self.__download_button = builder.get_object("download_button")
        self.__menu_button = builder.get_object("menu_button")
        eventbox = Gtk.EventBox()
        eventbox.connect("button-release-event", self.__on_event_release_event)
        eventbox.show()
        self.__settings_button = builder.get_object("settings_button")
        self.__progress = ProgressBar(builder.get_object("download_button"))
        if El().download_manager.get():
            self._progress.show()
        El().download_manager.connect("download-start",
                                      self.__on_download)
        El().download_manager.connect("download-finish",
                                      self.__on_download)
        eventbox.add(self.__progress)
        builder.get_object("overlay").add_overlay(eventbox)
        if El().settings.get_value("adblock"):
            builder.get_object(
                         "menu_button").get_style_context().add_class("red")
        self.add(builder.get_object("end"))

        adblock_action = Gio.SimpleAction.new_stateful(
               "adblock",
               None,
               GLib.Variant.new_boolean(El().settings.get_value("adblock")))
        adblock_action.connect("change-state", self.__on_adblock_change_state)
        El().add_action(adblock_action)
        image_action = Gio.SimpleAction.new_stateful(
               "imgblock",
               None,
               GLib.Variant.new_boolean(El().settings.get_value("imgblock")))
        image_action.connect("change-state",
                             self.__on_image_change_state)
        El().add_action(image_action)
        self.__exceptions_action = Gio.SimpleAction.new_stateful(
                                                   "exceptions",
                                                   GLib.VariantType.new("s"),
                                                   GLib.Variant("s", "none"))
        self.__exceptions_action.connect("activate",
                                         self.__on_exceptions_active)
        El().add_action(self.__exceptions_action)

    def setup_menu(self, menu):
        """
            Add an application menu to menu button
            @parma: menu as Gio.Menu
        """
        self.__settings_button.show()
        self.__settings_button.set_menu_model(menu)

    def on_uri_changed(self):
        """
            Update menu button color
        """
        self.__update_filtering_button_color()

#######################
# PROTECTED           #
#######################
    def _on_download_button_clicked(self, button):
        """
            Show download popover
            @param button as Gtk.Button
        """
        popover = DownloadsPopover()
        popover.set_relative_to(button)
        popover.show()

    def _on_home_button_clicked(self, button):
        """
            Go to home page
            @param button as Gtk.Button
        """
        El().active_window.container.current.webview.load_uri(El().start_page)

    def _on_menu_button_clicked(self, button):
        """
            Update reader action
            @param button as Gtk.Button
        """
        uri = El().active_window.container.current.webview.get_uri()
        if not uri:
            return
        parsed = urlparse(uri)
        page_ex = El().adblock.is_an_exception(parsed.netloc +
                                               parsed.path)
        site_ex = El().adblock.is_an_exception(parsed.netloc)
        if not page_ex and not site_ex:
            self.__exceptions_action.change_state(GLib.Variant("s", "none"))
        elif site_ex:
            self.__exceptions_action.change_state(GLib.Variant("s", "site"))
        else:
            self.__exceptions_action.change_state(GLib.Variant("s", "page"))

#######################
# PRIVATE             #
#######################
    def __hide_progress(self):
        """
            Hide progress if needed
        """
        if self.__timeout_id is None:
            self.__progress.hide()

    def __update_progress(self, download_manager):
        """
            Update progress
        """
        fraction = 0.0
        nb_downloads = 0
        for download in download_manager.get():
            nb_downloads += 1
            fraction += download.get_estimated_progress()
        if nb_downloads:
            self.__progress.set_fraction(fraction/nb_downloads)
        return True

    def __update_filtering_button_color(self):
        """
            Show different colors:
                * red for adblock all
                * orange for adblock site
                * yellow for adblock page
                * black for no adblock
        """
        # Remove any previous class
        self.__menu_button.get_style_context().remove_class("red")
        self.__menu_button.get_style_context().remove_class("orange")
        self.__menu_button.get_style_context().remove_class("yellow")
        # If adblock disabled, nothing more to do
        if not El().settings.get_value("adblock"):
            return
        uri = El().active_window.container.current.webview.get_uri()
        # If uri empty, we just set adblock color to red and leave
        if not uri:
            if El().settings.get_value("adblock"):
                self.__menu_button.get_style_context().add_class("red")
            return
        parsed = urlparse(uri)
        page_ex = El().adblock.is_an_exception(parsed.netloc + parsed.path)
        site_ex = El().adblock.is_an_exception(parsed.netloc)
        if page_ex:
            self.__menu_button.get_style_context().add_class("yellow")
        elif site_ex:
            self.__menu_button.get_style_context().add_class("orange")
        else:
            self.__menu_button.get_style_context().add_class("red")

    def __on_event_release_event(self, widget, event):
        """
            Forward event to button
            @param widget as Gtk.Widget
            @param event as Gdk.Event
        """
        self.__download_button.clicked()

    def __on_exceptions_active(self, action, param):
        """
            Update exception for current page/site
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        uri = El().active_window.container.current.webview.get_uri()
        if not uri:
            return
        action.set_state(param)
        parsed = urlparse(uri)
        page_ex = El().adblock.is_an_exception(parsed.netloc + parsed.path)
        site_ex = El().adblock.is_an_exception(parsed.netloc)
        # Clean previous exceptions
        if param.get_string() in ["site", "none"]:
            if page_ex:
                El().adblock.remove_exception(parsed.netloc + parsed.path)
        if param.get_string() in ["page", "none"]:
            if site_ex:
                El().adblock.remove_exception(parsed.netloc)
        # Add new exceptions
        if param.get_string() == "site":
            El().adblock.add_exception(parsed.netloc)
        elif param.get_string() == "page":
            El().adblock.add_exception(parsed.netloc + parsed.path)
        self.__update_filtering_button_color()
        El().active_window.container.current.webview.reload()

    def __on_adblock_change_state(self, action, param):
        """
            Set adblock state
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        action.set_state(param)
        El().settings.set_value('adblock', param)
        self.__update_filtering_button_color()
        El().active_window.container.current.webview.reload()

    def __on_image_change_state(self, action, param):
        """
            Set reader view
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        action.set_state(param)
        El().settings.set_value('imgblock', param)
        El().active_window.container.current.webview.reload()

    def __on_download(self, download_manager, name=""):
        """
            Update progress bar
            @param downloads manager as DownloadsManager
            @param name as str (do not use this)
        """
        if download_manager.is_active():
            if self.__timeout_id is None:
                self.__progress.show()
                self.__timeout_id = GLib.timeout_add(1000,
                                                     self.__update_progress,
                                                     download_manager)
        elif self.__timeout_id is not None:
            self.__progress.set_fraction(1.0)
            GLib.timeout_add(1000, self.__hide_progress)
            GLib.source_remove(self.__timeout_id)
            self.__timeout_id = None
