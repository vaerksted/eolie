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

from gi.repository import Gtk, GLib, Pango, Gio

from time import time

from eolie.define import El


class Row(Gtk.ListBoxRow):
    """
        A row
    """
    def __init__(self, download, finished):
        """
            Init row
            @param download as WebKit2.Download
            @param finished as bool
        """
        Gtk.ListBoxRow.__init__(self)
        self.__download = download
        self.__finished = finished
        self.__uri = self.__download.get_request().get_uri()
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/RowDownload.ui")
        builder.connect_signals(self)
        self.__preview = builder.get_object("preview")
        self.__progress = builder.get_object("progress")
        filename = GLib.filename_from_uri(download.get_destination())
        if filename is not None:
            builder.get_object("label").set_label(
                                         GLib.path_get_basename(filename[0]))
            builder.get_object("path").set_label(filename[0])
        else:
            builder.get_object("label").set_label(download.get_destination())
            builder.get_object("label").set_ellipsize(
                                                   Pango.EllipsizeMode.START)
        self.__button = builder.get_object("button")
        self.__button_image = builder.get_object("button_image")
        if finished:
            self.__on_finished(download)
        else:
            progress = download.get_estimated_progress()
            if progress is not None:
                self.__progress.set_fraction(progress)
        self.add(builder.get_object("row"))
        self.connect("map", self.__on_map)
        self.connect("unmap", self.__on_unmap)

    @property
    def finished(self):
        """
            True if download is finished
        """
        return self.__finished

    @property
    def download(self):
        """
            Get row download
            @return WebKit2.Download
        """
        return self.__download

#######################
# PROTECTED           #
#######################
    def _on_cancel_button_clicked(self, button):
        """
            Cancel download
            @param button as Gtk.Button
        """
        if self.__button_image.get_icon_name()[0] == "window-close-symbolic":
            self.__download.cancel()
        elif self.__button_image.get_icon_name()[0] == "view-refresh-symbolic":
            self.__download.get_web_view().download_uri(self.__uri)
            El().download_manager.remove(self.__download)
            self.destroy()

#######################
# PRIVATE             #
######################
    def __on_map(self, widget):
        """
            Connect signals
            @param widget as Gtk.Widget
        """
        self.__download.connect("finished", self.__on_finished)
        self.__download.connect("received-data", self.__on_received_data)
        self.__download.connect("failed", self.__on_failed)
        response = self.__download.get_response()
        if response is None:
            return
        destination = self.__download.get_destination()
        if destination is None:
            return
        f = GLib.filename_from_uri(destination)[0]
        (mime, uncertain) = Gio.content_type_guess(f, None)
        if uncertain:
            self.__preview.set_from_icon_name("text-x-generic",
                                              Gtk.IconSize.DIALOG)
        else:
            icon = Gio.content_type_get_icon(mime)
            self.__preview.set_from_gicon(icon, Gtk.IconSize.DIALOG)

    def __on_unmap(self, widget):
        """
            Disconnect signals
            @param widget as Gtk.Widget
        """
        self.__download.disconnect_by_func(self.__on_finished)
        self.__download.disconnect_by_func(self.__on_received_data)
        self.__download.disconnect_by_func(self.__on_failed)

    def __on_received_data(self, download, length):
        """
            @param download as WebKit2.Download
            @param length as int
        """
        self.__progress.set_fraction(download.get_estimated_progress())

    def __on_finished(self, download):
        """
            @param download as WebKit2.Download
        """
        self.__finished = True
        self.__progress.set_opacity(0)
        parent = self.get_parent()
        if parent is not None:
            parent.invalidate_sort()
        if self.__button_image.get_icon_name()[0] == "view-refresh-symbolic":
            return True
        else:
            self.__button.hide()

    def __on_failed(self, download, error):
        """
            @param download as WebKit2.Download
            @param error as GLib.Error
        """
        self.__button_image.set_from_icon_name("view-refresh-symbolic",
                                               Gtk.IconSize.MENU)


class DownloadsPopover(Gtk.Popover):
    """
        Show current downloads
    """

    def __init__(self):
        """
            Init popover
        """
        Gtk.Popover.__init__(self)
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/PopoverDownloads.ui")
        builder.connect_signals(self)
        self.__listbox = builder.get_object("downloads_box")
        self.__listbox.connect("row-activated", self.__on_row_activated)
        self.__listbox.set_placeholder(builder.get_object("placeholder"))
        self.__listbox.set_sort_func(self.__sort)
        self.__scrolled = builder.get_object("scrolled")
        self.__clear_button = builder.get_object("clear_button")
        self.add(builder.get_object("widget"))
        self.connect("map", self.__on_map)
        self.connect("unmap", self.__on_unmap)
        self.__populate()

#######################
# PROTECTED           #
#######################
    def _on_open_clicked(self, button):
        """
            Open download folder
            @param button as Gtk.button
        """
        directory_uri = El().settings.get_value("download-uri").get_string()
        if not directory_uri:
            directory = GLib.get_user_special_dir(
                                         GLib.UserDirectory.DIRECTORY_DOWNLOAD)
            directory_uri = GLib.filename_to_uri(directory, None)
        Gtk.show_uri(None, directory_uri, int(time()))
        self.hide()

    def _on_clear_clicked(self, button):
        """
            Clear finished downloads
            @param button as Gtk.button
        """
        self.__clear_button.set_sensitive(False)
        for child in self.__listbox.get_children():
            El().download_manager.remove(child.download)
            if child.finished:
                child.destroy()

#######################
# PRIVATE             #
#######################
    def __sort(self, row1, row2):
        """
            Sort listbox
            @param row1 as Row
            @param row2 as Row
        """
        if row1.finished:
            return True
        elif row1.download.get_estimated_progress() >\
                row2.download.get_estimated_progress():
            return False

    def __populate(self):
        """
            Populate view
        """
        for download in El().download_manager.get():
            child = Row(download, False)
            child.connect("size-allocate", self.__on_child_size_allocate)
            child.show()
            self.__listbox.add(child)
        for download in El().download_manager.get_finished():
            child = Row(download, True)
            child.connect("size-allocate", self.__on_child_size_allocate)
            child.show()
            self.__listbox.add(child)
        self.__clear_button.set_sensitive(El().download_manager.get_finished())

    def __on_row_activated(self, listbox, row):
        """
            Launch row if download finished
            @param listbox as Gtk.ListBox
            @param row as Row
        """
        if row.finished:
            try:
                Gtk.show_uri(None, row.download.get_destination(), int(time()))
            except:  # Destination not found
                pass
            self.hide()

    def __on_map(self, widget):
        """
            Resize
            @param widget as Gtk.Widget
        """
        El().download_manager.connect("download-start",
                                      self.__on_download_start)
        El().download_manager.connect("download-finish",
                                      self.__on_download_finish)
        self.set_size_request(400, -1)

    def __on_unmap(self, widget):
        """
            Resize
            @param widget as Gtk.Widget
        """
        for child in self.__listbox.get_children():
            child.destroy()
        El().download_manager.disconnect_by_func(self.__on_download_start)
        El().download_manager.disconnect_by_func(self.__on_download_finish)

    def __on_download_start(self, download_manager, download_name):
        """
            Add download
            @param download manager as Download Manager
            @param download_name as str
        """
        for download in El().download_manager.get():
            if str(download) == download_name:
                child = Row(download, False)
                child.connect("size-allocate", self.__on_child_size_allocate)
                child.show()
                self.__listbox.add(child)
                break

    def __on_download_finish(self, download_manager):
        """
            Update clear button
            @param download manager as Download Manager
        """
        self.__clear_button.set_sensitive(True)

    def __on_child_size_allocate(self, widget, allocation=None):
        """
            Update popover height request
            @param widget as Gtk.Widget
            @param allocation as Gdk.Rectangle
        """
        height = 0
        for child in self.__listbox.get_children():
            height += allocation.height
        size = self.get_ancestor(Gtk.Window).get_size()
        if height > size[1] * 0.6:
            height = size[1] * 0.6
        self.__scrolled.set_size_request(400, height)
