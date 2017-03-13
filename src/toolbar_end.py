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

from gi.repository import Gtk, GLib, Gio, WebKit2, Soup

from urllib.parse import urlparse
from gettext import gettext as _

from threading import Thread

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

    def __init__(self, window):
        """
            Init toolbar
            @param window as Window
        """
        Gtk.Bin.__init__(self)
        self.__window = window
        self.__timeout_id = None
        self.set_hexpand(True)
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/ToolbarEnd.ui")
        builder.connect_signals(self)
        self.__download_button = builder.get_object("download_button")
        self.__adblock_button = builder.get_object("adblock_button")
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
        self.add(builder.get_object("end"))

        adblock_action = Gio.SimpleAction.new_stateful(
               "adblock",
               None,
               GLib.Variant.new_boolean(El().settings.get_value("adblock")))
        adblock_action.connect("change-state", self.__on_adblock_change_state)
        self.__window.add_action(adblock_action)
        image_action = Gio.SimpleAction.new_stateful(
               "imgblock",
               None,
               GLib.Variant.new_boolean(El().settings.get_value("imgblock")))
        image_action.connect("change-state",
                             self.__on_image_change_state)
        self.__window.add_action(image_action)
        self.__exceptions_action = Gio.SimpleAction.new_stateful(
                                                   "exceptions",
                                                   GLib.VariantType.new("s"),
                                                   GLib.Variant("s", "none"))
        self.__exceptions_action.connect("activate",
                                         self.__on_exceptions_active)
        self.__window.add_action(self.__exceptions_action)

#######################
# PROTECTED           #
#######################
    def _on_download_button_clicked(self, button):
        """
            Show download popover
            @param button as Gtk.Button
        """
        self.__window.toolbar.title.hide_popover()
        button.get_style_context().remove_class("selected")
        popover = DownloadsPopover()
        popover.set_relative_to(button)
        popover.show()

    def _on_home_button_clicked(self, button):
        """
            Go to home page
            @param button as Gtk.Button
        """
        self.__window.toolbar.title.hide_popover()
        self.__window.container.current.webview.load_uri(El().start_page)

    def _on_menu_button_clicked(self, button):
        """
            Show settings menu
            @param button as Gtk.Button
        """
        self.__window.toolbar.title.hide_popover()
        uri = self.__window.container.current.webview.get_uri()
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
        popover = Gtk.PopoverMenu.new()
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/ActionsMenu.ui")
        builder.connect_signals(self)
        webview = El().active_window.container.current.webview
        parsed = urlparse(webview.get_uri())
        if parsed.scheme not in ["http", "https"]:
            builder.get_object("source_button").set_sensitive(False)
        if parsed.netloc in El().zoom_levels.keys():
            current = El().zoom_levels[parsed.netloc]
        else:
            current = 100
        builder.get_object("default_zoom_button").set_label(
                                                        "{} %".format(current))
        popover.add(builder.get_object("widget"))
        exceptions = builder.get_object("exceptions")
        popover.add(exceptions)
        popover.child_set_property(exceptions, "submenu", "exceptions")
        popover.set_relative_to(button)
        popover.connect("closed", self.__on_popover_closed)
        self.__window.set_lock_focus(True)
        popover.show()

    def _on_save_button_clicked(self, button):
        """
            Save current page
            @param button as Gtk.Button
        """
        button.get_ancestor(Gtk.Popover).hide()
        filechooser = Gtk.FileChooserNative.new(_("Save page"),
                                                El().active_window,
                                                Gtk.FileChooserAction.SAVE,
                                                _("Save"),
                                                _("Cancel"))
        filechooser.connect("response", self.__on_save_response)
        filechooser.run()

    def _on_print_button_clicked(self, button):
        """
            Print current page
            @param button as Gtk.button
        """
        button.get_ancestor(Gtk.Popover).hide()
        action = El().lookup_action("shortcut")
        action.activate(GLib.Variant("s", "print"))

    def _on_source_button_clicked(self, button):
        """
            Show current page source
            @param button as Gtk.button
        """
        button.get_ancestor(Gtk.Popover).hide()
        uri = El().active_window.container.current.webview.get_uri()
        thread = Thread(target=self.__show_source_code,
                        args=(uri,))
        thread.daemon = True
        thread.start()

    def _on_zoom_button_clicked(self, button):
        """
            Zoom current page
            @param button as Gtk.Button
        """
        webview = El().active_window.container.current.webview
        parsed = urlparse(webview.get_uri())
        if parsed.netloc in El().zoom_levels.keys():
            current = El().zoom_levels[parsed.netloc]
        else:
            current = 100
        current += 5
        El().zoom_levels[parsed.netloc] = current
        webview.update_zoom_level()
        button.set_label("{} %".format(current))

    def _on_unzoom_button_clicked(self, button):
        """
            Unzoom current page
            @param button as Gtk.Button
        """
        webview = El().active_window.container.current.webview
        parsed = urlparse(webview.get_uri())
        if parsed.netloc in El().zoom_levels.keys():
            current = El().zoom_levels[parsed.netloc]
        else:
            current = 100
        current -= 5
        El().zoom_levels[parsed.netloc] = current
        webview.update_zoom_level()
        button.set_label("{} %".format(current))

    def _on_default_zoom_button_clicked(self, button):
        """
            Restore default zoom level
            @param button as Gtk.Button
        """
        try:
            webview = El().active_window.container.current.webview
            parsed = urlparse(webview.get_uri())
            del El().zoom_levels[parsed.netloc]
            webview.update_zoom_level()
            button.set_label("100 %")
        except:
            pass

#######################
# PRIVATE             #
#######################
    def __show_source_code(self, uri):
        """
            Show source code for uri
            @param uri as str
            @thread safe
        """
        try:
            (tmp, tmp_stream) = Gio.File.new_tmp("XXXXXX.html")
            session = Soup.Session.new()
            request = session.request(uri)
            stream = request.send(None)
            bytes = bytearray(0)
            buf = stream.read_bytes(1024, None).get_data()
            while buf:
                bytes += buf
                buf = stream.read_bytes(1024, None).get_data()
            tmp_stream.get_output_stream().write_all(bytes)
            GLib.idle_add(self.__launch_editor, tmp)
        except Exception as e:
            print("ToolbarEnd::__show_source_code():", e)

    def __launch_editor(self, f):
        """
            Launch text editor
            @param f as Gio.File
        """
        appinfo = Gio.app_info_get_default_for_type("text/plain", False)
        appinfo.launch([f], None)

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

    def __on_save_response(self, dialog, response_id):
        """
            Tell WebKit to save current page
            @param dialog as Gtk.NativeDialog
            @param response_id as int
        """
        if response_id == Gtk.ResponseType.ACCEPT:
            El().active_window.container.current.webview.save_to_file(
                                    dialog.get_file(),
                                    WebKit2.SaveMode.MHTML,
                                    None,
                                    None)

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
        uri = self.__window.container.current.webview.get_uri()
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
        self.__window.container.current.webview.reload()

    def __on_adblock_change_state(self, action, param):
        """
            Set adblock state
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        action.set_state(param)
        El().settings.set_value('adblock', param)
        self.__window.container.current.webview.reload()

    def __on_image_change_state(self, action, param):
        """
            Set reader view
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        action.set_state(param)
        El().settings.set_value('imgblock', param)
        self.__window.container.current.webview.reload()

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
            self.__download_button.get_style_context().add_class("selected")

    def __on_popover_closed(self, popover):
        """
            Unlock focus
        """
        self.__window.set_lock_focus(False)
