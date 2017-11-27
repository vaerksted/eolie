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

from gi.repository import GObject, GLib, Gio, Gtk

from time import time

from eolie.define import El


class DownloadManager(GObject.GObject):
    """
        Downloads Manager
    """
    __gsignals__ = {
        "download-start": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "download-finish": (GObject.SignalFlags.RUN_FIRST, None, ())
    }

    def __init__(self):
        """
            Init download manager
        """
        GObject.GObject.__init__(self)
        self.__downloads = []
        self.__finished = []

    def add(self, download, filename=None):
        """
            Add a download
            @param download as WebKit2.Download
            @param filename as str/None
        """
        if download not in self.__downloads:
            self.__downloads.append(download)
            download.connect('finished', self.__on_finished)
            download.connect('failed', self.__on_failed)
            download.connect('decide-destination',
                             self.__on_decide_destination, filename)

    def remove(self, download):
        """
            Remove download
            @param download as WebKit2.Download
        """
        if download in self.__downloads:
            self.__downloads.remove(download)
        if download in self.__finished:
            self.__finished.remove(download)

    def get(self):
        """
            Get running downloads
            @return [WebKit2.Download]
        """
        return self.__downloads

    def get_finished(self):
        """
            Get finished download
            @return [WebKit2.Download]
        """
        return self.__finished

    def cancel(self):
        """
            Cancel all downloads
        """
        for download in self.__downloads:
            download.cancel()

    @property
    def active(self):
        """
            Is download active
            @return bool
        """
        for download in self.__downloads:
            if download.get_estimated_progress() != 1.0:
                return True

#######################
# PRIVATE             #
#######################
    def __on_decide_destination(self, download, filename, wanted_filename):
        """
            Modify destination if needed
            @param download as WebKit2.Download
            @param filename as str
            @param wanted_filename as str
        """
        filename = filename.replace("/", "_")
        extension = filename.split(".")[-1]
        if wanted_filename:
            # FIXME We should find a way to pass good extension,
            # fallback to avi
            if extension == filename:
                extension = "avi"
            filename = wanted_filename + "." + extension
        directory_uri = El().settings.get_value('download-uri').get_string()
        if not directory_uri:
            directory = GLib.get_user_special_dir(
                                         GLib.UserDirectory.DIRECTORY_DOWNLOAD)
            directory_uri = GLib.filename_to_uri(directory, None)
        destination_uri = "%s/%s" % (directory_uri,
                                     GLib.uri_escape_string(filename,
                                                            None,
                                                            False))
        not_ok = True
        i = 1
        try:
            while not_ok:
                f = Gio.File.new_for_uri(destination_uri)
                if f.query_exists():
                    extension_less = filename.replace(".%s" % extension, "")
                    new_filename = "%s_%s.%s" % (extension_less, i, extension)
                    destination_uri = "%s/%s" % (directory_uri,
                                                 GLib.uri_escape_string(
                                                            new_filename,
                                                            None,
                                                            False))
                else:
                    not_ok = False
                i += 1
        except:
            # Fallback to be sure
            destination_uri = "%s/@@%s" % (directory_uri,
                                           GLib.uri_escape_string(
                                                            filename,
                                                            None,
                                                            False))

        webkit_uri = GLib.uri_unescape_string(destination_uri, None)
        download.set_destination(webkit_uri)
        self.emit('download-start', str(download))
        # Notify user about download
        window = El().active_window
        if window is not None:
            window.toolbar.end.show_download(download)

    def __on_finished(self, download):
        """
            @param download as WebKit2.Download
        """
        self.remove(download)
        self.__finished.append(download)
        self.emit('download-finish')
        if El().settings.get_value('open-downloads'):
            destination = download.get_destination()
            f = Gio.File.new_for_uri(destination)
            if f.query_exists():
                Gtk.show_uri(None, destination, int(time()))

    def __on_failed(self, download, error):
        """
            @param download as WebKit2.Download
            @param error as GLib.Error
        """
        print("DownloadManager::__on_failed:", error)
