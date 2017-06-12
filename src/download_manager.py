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
        "download-finish": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "video-in-page": (GObject.SignalFlags.RUN_FIRST, None, ())
    }

    def __init__(self):
        """
            Init download manager
        """
        GObject.GObject.__init__(self)
        self.__downloads = []
        self.__finished = []
        self.__video_uris = {}

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

    def add_video(self, uri, title, page_id):
        """
            Emit video-in-page signal
            @param uri as str
            @param title as str
            @param page_id as int
        """
        if page_id in self.__video_uris.keys():
            if (uri, title) not in self.__video_uris[page_id]:
                self.__video_uris[page_id].append((uri, title))
        else:
            self.__video_uris[page_id] = [(uri, title)]
        self.emit("video-in-page")

    def remove(self, download):
        """
            Remove download
            @param download as WebKit2.Download
        """
        if download in self.__downloads:
            self.__downloads.remove(download)
        if download in self.__finished:
            self.__finished.remove(download)

    def remove_video(self, uri, title, page_id):
        """
            Remove video uris for page
            @param uri
            @param title
            @param page_id as int
        """
        if page_id in self.__video_uris.keys():
            if (uri, title) in self.__video_uris[page_id]:
                self.__video_uris[page_id].remove((uri, title))

    def remove_videos_for_page(self, page_id):
        """
            Remove video uris for page
            @param page_id as int
        """
        if page_id in self.__video_uris.keys():
            del self.__video_uris[page_id]

    def get(self):
        """
            Get running downloads
            @return [WebKit2.Download]
        """
        return self.__downloads

    def get_videos(self, page_id):
        """
            Get videos available to download
            @param page_id as int
            @return [(uri, title)] as [(str, str)]
        """
        if page_id in self.__video_uris.keys():
            return self.__video_uris[page_id]
        return []

    def get_finished(self):
        """
            Get finished download
            @return [WebKit2.Download]
        """
        return self.__finished

    def is_active(self):
        """
            Get active downloads
        """
        for download in self.__downloads:
            if download.get_estimated_progress() != 1.0:
                return True

    def cancel(self):
        """
            Cancel all downloads
        """
        for download in self.__downloads:
            download.cancel()

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

        # WebKit is a little stupid, it is unable to download escaped strings
        # It fails do download uri with suggested filename too if contains %
        webkit_uri = GLib.uri_unescape_string(destination_uri, None)
        download.set_destination(webkit_uri.replace("%", ""))
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
