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

from gi.repository import Gtk, GLib, Gio, WebKit2, Soup, Pango

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
        self.__settings_button = builder.get_object("settings_button")
        self.__progress = ProgressBar(builder.get_object("download_button"))
        if El().download_manager.get():
            self._progress.show()
        El().download_manager.connect("download-start",
                                      self.__on_download)
        El().download_manager.connect("download-finish",
                                      self.__on_download)
        El().download_manager.connect("video-in-page",
                                      self.__on_video_in_page)
        overlay = builder.get_object("overlay")
        overlay.add_overlay(self.__progress)
        overlay.set_overlay_pass_through(self.__progress, True)
        self.add(builder.get_object("end"))

        adblock_action = Gio.SimpleAction.new_stateful(
               "adblock",
               None,
               GLib.Variant.new_boolean(El().settings.get_value("adblock")))
        adblock_action.connect("change-state", self.__on_adblock_change_state)
        self.__window.add_action(adblock_action)
        popup_action = Gio.SimpleAction.new_stateful(
               "popupblock",
               None,
               GLib.Variant.new_boolean(El().settings.get_value("popupblock")))
        popup_action.connect("change-state",
                             self.__on_popup_change_state)
        self.__window.add_action(popup_action)
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
                                         self.__on_exceptions_activate)
        self.__window.add_action(self.__exceptions_action)

    def show_download(self, download):
        """
            Notify user about download
            @param download as WebKit2.Download
        """
        if self.__window.toolbar.title.lock_focus:
            return
        header = Gtk.Label()
        header.set_markup("<b>" + _("Downloading:") + "</b>")
        header.set_ellipsize(Pango.EllipsizeMode.END)
        header.show()
        uri = Gtk.Label.new(download.get_request().get_uri().split('/')[-1])
        uri.set_max_width_chars(30)
        uri.set_ellipsize(Pango.EllipsizeMode.END)
        uri.show()
        grid = Gtk.Grid()
        grid.set_margin_start(5)
        grid.set_margin_end(5)
        grid.set_margin_top(5)
        grid.set_margin_bottom(5)
        grid.set_orientation(Gtk.Orientation.VERTICAL)
        grid.show()
        grid.add(header)
        grid.add(uri)
        popover = Gtk.Popover.new()
        popover.get_style_context().add_class("dark")
        popover.add(grid)
        popover.set_modal(False)
        popover.set_relative_to(self.__download_button)
        popover.show()
        GLib.timeout_add(2000, popover.destroy)

    def save_images(self, uri, page_id):
        """
            Show a popover with all images for page id
            @param uri as str
            @param page_id as int
        """
        from eolie.popover_images import ImagesPopover
        popover = ImagesPopover(uri, page_id)
        popover.set_relative_to(self.__download_button)
        popover.show()

#######################
# PROTECTED           #
#######################
    def _on_download_button_toggled(self, button):
        """
            Show download popover
            @param button as Gtk.Button
        """
        if not button.get_active():
            return
        self.__window.toolbar.title.close_popover()
        popover = DownloadsPopover()
        popover.set_relative_to(button)
        popover.connect("closed", self.__on_popover_closed, button)
        self.__window.toolbar.title.set_lock_focus(True)
        popover.show()

    def _on_home_button_clicked(self, button):
        """
            Go to home page
            @param button as Gtk.Button
        """
        self.__window.toolbar.title.close_popover()
        self.__window.container.current.webview.load_uri(El().start_page)

    def _on_menu_button_toggled(self, button):
        """
            Show settings menu
            @param button as Gtk.ToogleButton
        """
        if not button.get_active():
            return
        self.__window.toolbar.title.close_popover()
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
        widget = builder.get_object("widget")
        webview = self.__window.container.current.webview
        parsed = urlparse(webview.get_uri())
        if parsed.scheme not in ["http", "https"]:
            builder.get_object("source_button").set_sensitive(False)
        if parsed.netloc in El().zoom_levels.keys():
            current = El().zoom_levels[parsed.netloc]
        else:
            current = 100
        builder.get_object("default_zoom_button").set_label(
                                                        "{} %".format(current))
        popover.add(widget)
        exceptions = builder.get_object("exceptions")
        popover.add(exceptions)
        popover.child_set_property(exceptions, "submenu", "exceptions")
        # Merge appmenu, we assume we only have one level (section -> items)
        if not El().prefers_app_menu():
            separator = Gtk.Separator.new(Gtk.Orientation.HORIZONTAL)
            separator.show()
            widget.add(separator)
            menu = El().get_app_menu()
            for i in range(0, menu.get_n_items()):
                section = menu.get_item_link(i, "section")
                for y in range(0, section.get_n_items()):
                    label = section.get_item_attribute_value(y, "label")
                    action = section.get_item_attribute_value(y, "action")
                    item = Gtk.ModelButton.new()
                    item.set_property("text", label.get_string())
                    item.set_action_name(action.get_string())
                    item.show()
                    widget.add(item)
        popover.set_relative_to(button)
        popover.connect("closed", self.__on_popover_closed, button)
        self.__window.toolbar.title.set_lock_focus(True)
        popover.show()

    def _on_save_button_clicked(self, button):
        """
            Save current page
            @param button as Gtk.Button
        """
        button.get_ancestor(Gtk.Popover).hide()
        filechooser = Gtk.FileChooserNative.new(_("Save page"),
                                                self.__window,
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
        action = self.__window.lookup_action("shortcut")
        action.activate(GLib.Variant("s", "print"))

    def _on_source_button_clicked(self, button):
        """
            Show current page source
            @param button as Gtk.button
        """
        button.get_ancestor(Gtk.Popover).hide()
        uri = self.__window.container.current.webview.get_uri()
        thread = Thread(target=self.__show_source_code,
                        args=(uri,))
        thread.daemon = True
        thread.start()

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

    def _on_default_zoom_button_clicked(self, button):
        """
            Restore default zoom level
            @param button as Gtk.Button
        """
        try:
            webview = self.__window.container.current.webview
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
            stream.close()
            tmp_stream.close()
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
            self.__window.container.current.webview.save_to_file(
                                    dialog.get_file(),
                                    WebKit2.SaveMode.MHTML,
                                    None,
                                    None)

    def __on_exceptions_activate(self, action, param):
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
        El().settings.set_value("adblock", param)
        self.__window.container.current.webview.reload()

    def __on_popup_change_state(self, action, param):
        """
            Update popup block state
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        action.set_state(param)
        El().settings.set_value("popupblock", param)

    def __on_image_change_state(self, action, param):
        """
            Update image block state
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        action.set_state(param)
        El().settings.set_value("imgblock", param)
        self.__window.container.current.webview.reload()

    def __on_download(self, download_manager, name=""):
        """
            Update progress bar
            @param download_manager as DownloadManager
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
            self.__download_button.get_style_context().remove_class(
                                                            "video-in-page")

    def __on_video_in_page(self, download_manager):
        """
            Mark download button
            @param download_manager as DownloadManager
        """
        self.__download_button.get_style_context().add_class("video-in-page")

    def __on_popover_closed(self, popover, button):
        """
            Unlock focus
            @param popover as Gtk.Popover
            @param button as Gtk.Button
        """
        button.get_style_context().remove_class("selected")
        button.get_style_context().remove_class("video-in-page")
        button.set_active(False)
        self.__window.toolbar.title.set_lock_focus(False)
