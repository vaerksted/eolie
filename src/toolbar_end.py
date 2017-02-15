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
        self.__reader_action = Gio.SimpleAction.new_stateful(
                                               "reader",
                                               None,
                                               GLib.Variant.new_boolean(False))
        self.__reader_action.connect("change-state",
                                     self.__on_reader_change_state)
        El().add_action(self.__reader_action)

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
        El().active_window.container.current.load_uri(El().start_page)

    def _on_menu_button_clicked(self, button):
        """
            Update reader action
            @param button as Gtk.Button
        """
        self.__reader_action.set_state(
                GLib.Variant("b",
                             El().active_window.container.current.readable))

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

    def __on_current_changed(self, container):
        """
            Update toggle button
            @param container as Container
        """
        self.__read_button.set_active(container.current.is_readable)

    def __on_event_release_event(self, widget, event):
        """
            Forward event to button
            @param widget as Gtk.Widget
            @param event as Gdk.Event
        """
        self.__download_button.clicked()

    def __on_adblock_change_state(self, action, param):
        """
            Set adblock state
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        action.set_state(param)
        El().settings.set_value('adblock', param)
        if param.get_boolean():
            self.__menu_button.get_style_context().add_class("red")
        else:
            self.__menu_button.get_style_context().remove_class("red")

    def __on_reader_change_state(self, action, param):
        """
            Set reader view
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        action.set_state(param)
        current_view = El().active_window.container.current
        active = param.get_boolean()
        if active == current_view.readable:
            return
        current_view.show_readable_version(active)

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
