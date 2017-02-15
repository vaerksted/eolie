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

from gi.repository import Gtk, GLib, Pango

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
        builder.add_from_resource('/org/gnome/Eolie/RowDownload.ui')
        builder.connect_signals(self)
        self.__progress = builder.get_object('progress')
        filename = GLib.filename_from_uri(download.get_destination())
        if filename is not None:
            builder.get_object('label').set_label(
                                         GLib.path_get_basename(filename[0]))
            builder.get_object('path').set_label(filename[0])
        else:
            builder.get_object('label').set_label(download.get_destination())
            builder.get_object('label').set_ellipsize(
                                                   Pango.EllipsizeMode.START)
        self.__button = builder.get_object('button')
        self.__button_image = builder.get_object('button_image')
        if finished:
            self.__on_finished(download)
        else:
            self.__progress.set_fraction(download.get_estimated_progress())
            download.connect('finished', self.__on_finished)
            download.connect('received-data', self.__on_received_data)
            download.connect('failed', self.__on_failed)
        self.add(builder.get_object('row'))

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
        if self.__button_image.get_icon_name()[0] == 'close-symbolic':
            self.__download.cancel()
        elif self.__button_image.get_icon_name()[0] == 'view-refresh-symbolic':
            self.__download.get_web_view().download_uri(self.__uri)
            El().download_manager.remove(self.__download)
            self.destroy()

#######################
# PRIVATE             #
#######################
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
        if self.__button_image.get_icon_name()[0] == 'view-refresh-symbolic':
            return True
        else:
            self.__button.hide()

    def __on_failed(self, download, error):
        """
            @param download as WebKit2.Download
            @param error as GLib.Error
        """
        self.__button_image.set_from_icon_name('view-refresh-symbolic',
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
        builder.add_from_resource('/org/gnome/Eolie/PopoverDownloads.ui')
        builder.connect_signals(self)
        self.__listbox = builder.get_object('downloads_box')
        self.__listbox.connect('row-activated', self.__on_row_activated)
        self.__listbox.set_placeholder(builder.get_object('placeholder'))
        self.__listbox.set_sort_func(self.__sort)
        self.__scrolled = builder.get_object('scrolled')
        self.add(builder.get_object('widget'))
        self.connect('map', self.__on_map)
        self.connect('unmap', self.__on_unmap)
        self.__populate()

#######################
# PROTECTED           #
#######################

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
            child.connect('size-allocate', self.__on_child_size_allocate)
            child.show()
            self.__listbox.add(child)
        for download in El().download_manager.get_finished():
            child = Row(download, True)
            child.connect('size-allocate', self.__on_child_size_allocate)
            child.show()
            self.__listbox.add(child)

    def __on_row_activated(self, listbox, row):
        """
            Launch row if download finished
            @param listbox as Gtk.ListBox
            @param row as Row
        """
        if row.finished:
            Gtk.show_uri(None, row.download.get_destination(), int(time()))
            self.hide()

    def __on_map(self, widget):
        """
            Resize
            @param widget as Gtk.Widget
        """
        El().download_manager.connect('download-start',
                                      self.__on_download_start)
        self.set_size_request(400, -1)

    def __on_unmap(self, widget):
        """
            Resize
            @param widget as Gtk.Widget
        """
        for child in self.__listbox.get_children():
            child.destroy()
        El().download_manager.disconnect_by_func(self.__on_download_start)

    def __on_download_start(self, download_manager, download_name):
        """
            Add download
            @param download manager as Download Manager
            @param download_name as str
        """
        for download in El().download_manager.get():
            if str(download) == download_name:
                child = Row(download, False)
                child.connect('size-allocate', self.__on_child_size_allocate)
                child.show()
                self.__listbox.add(child)
                break

    def __on_child_size_allocate(self, widget, allocation=None):
        """
            Update popover height request
            @param widget as Gtk.Widget
            @param allocation as Gdk.Rectangle
        """
        height = 0
        for child in self.__listbox.get_children():
            height += allocation.height
        size = El().active_window.get_size()
        if height > size[1] * 0.6:
            height = size[1] * 0.6
        self.__scrolled.set_size_request(400, height)
