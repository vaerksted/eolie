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

from gi.repository import Gtk, GLib, Gdk, Gio, GdkPixbuf, Pango

from hashlib import sha256
from urllib.parse import urlparse

from eolie.helper_task import TaskHelper
from eolie.define import EOLIE_CACHE_PATH, ArtSize, El


class Image(Gtk.FlowBoxChild):
    """
        An image
    """
    def __init__(self, uri):
        """
            Create image
        """
        Gtk.FlowBoxChild.__init__(self)
        self.__uri = uri
        try:
            encoded = sha256(uri.encode("utf-8")).hexdigest()
            filepath = "%s/%s" % (EOLIE_CACHE_PATH, encoded)
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                                                       filepath,
                                                       ArtSize.START_HEIGHT,
                                                       ArtSize.START_HEIGHT,
                                                       True)
            surface = Gdk.cairo_surface_create_from_pixbuf(
                                                       pixbuf,
                                                       self.get_scale_factor(),
                                                       None)
            image = Gtk.Image.new_from_surface(surface)
            image.set_size_request(ArtSize.START_HEIGHT, ArtSize.START_HEIGHT)
            image.show()
            grid = Gtk.Grid()
            grid.set_orientation(Gtk.Orientation.VERTICAL)
            label = Gtk.Label.new(uri.split("/")[-1])
            label.set_ellipsize(Pango.EllipsizeMode.START)
            label.show()
            self.set_tooltip_text(uri)
            grid.add(image)
            grid.add(label)
            grid.show()
            self.add(grid)
        except:
            pass

    @property
    def uri(self):
        """
            Get uri
            @return str
        """
        return self.__uri

    def do_get_preferred_width(self):
        """
            Return preferred width
            @return (int, int)
        """
        return (ArtSize.START_HEIGHT, ArtSize.START_HEIGHT)


class ImagesPopover(Gtk.Popover):
    """
        Show images for page id
    """

    def __init__(self, uri, page_id, window):
        """
            Init popover
            @param uri as str
            @param page_id as int
            @param window as Window
        """
        Gtk.Popover.__init__(self)
        self.set_modal(False)
        window.register(self)
        self.__uri = uri
        self.__page_id = page_id
        self.__cancellable = Gio.Cancellable()
        self.__filter = ""
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/PopoverImages.ui")
        builder.connect_signals(self)
        widget = builder.get_object("widget")
        self.__spinner = builder.get_object("spinner")
        self.__flowbox = builder.get_object("flowbox")
        self.__flowbox.set_filter_func(self.__filter_func)
        self.__entry = builder.get_object("entry")
        self.__button = builder.get_object("button")
        self.add(widget)
        if Gio.NetworkMonitor.get_default().get_network_available():
            El().helper.call("GetImages",
                             GLib.Variant("(i)", (page_id,)),
                             self.__on_get_images, page_id)
        (width, height) = El().active_window.get_size()
        self.set_size_request(width / 2, height / 1.5)
        self.connect("closed", self.__on_closed)
        self.__task_helper = TaskHelper()

#######################
# PROTECTED           #
#######################
    def _on_search_changed(self, entry):
        """
            Filter flowbox
            @param entry as Gtk.Entry
        """
        self.__filter = entry.get_text()
        self.__flowbox.invalidate_filter()

    def _on_button_clicked(self, button):
        """
            Save visible images
            @param button as Gtk.Button
        """
        task_helper = TaskHelper()
        task_helper.run(self.__move_images)
        self.__spinner.start()

    def _on_button_toggled(self, button):
        """
            Cancel previous download
        """
        self.__cancellable.cancel()
        self.__cancellable.reset()
        self.__spinner.start()
        self.__button.set_sensitive(False)
        for child in self.__flowbox.get_children():
            child.destroy()
        self.__links = button.get_active()
        if Gio.NetworkMonitor.get_default().get_network_available():
            if button.get_active():
                El().helper.call("GetImageLinks",
                                 GLib.Variant("(i)", (self.__page_id,)),
                                 self.__on_get_images, self.__page_id)
            else:
                El().helper.call("GetImages",
                                 GLib.Variant("(i)", (self.__page_id,)),
                                 self.__on_get_images, self.__page_id)

#######################
# PRIVATE             #
#######################
    def __filter_func(self, child):
        """
            Filter child
            @param child as image
        """
        if child.uri.find(self.__filter) != -1:
            return True

    def __add_image(self, uri):
        """
            Add a child to flowbox
            @param uri as str
        """
        image = Image(uri)
        image.show()
        self.__flowbox.add(image)

    def __move_images(self):
        """
            Move image to download directory
        """
        parsed = urlparse(self.__uri)
        directory_uri = El().settings.get_value('download-uri').get_string()
        if not directory_uri:
            directory = GLib.get_user_special_dir(
                                         GLib.UserDirectory.DIRECTORY_DOWNLOAD)
            directory_uri = GLib.filename_to_uri(directory, None)
        destination_uri = "%s/%s" % (directory_uri, parsed.netloc)
        directory = Gio.File.new_for_uri(destination_uri)
        if not directory.query_exists():
            directory.make_directory_with_parents()
        for child in self.__flowbox.get_children():
            if child.uri.find(self.__filter) != -1:
                encoded = sha256(child.uri.encode("utf-8")).hexdigest()
                child_basename = child.uri.split("/")[-1]
                filepath = "%s/%s" % (EOLIE_CACHE_PATH, encoded)
                s = Gio.File.new_for_path(filepath)
                if not s.query_exists():
                    continue
                d = Gio.File.new_for_uri("%s/%s" % (destination_uri,
                                                    child_basename))
                try:
                    s.move(d, Gio.FileCopyFlags.OVERWRITE, None, None, None)
                except Exception as e:
                    print("ImagesPopover::__move_images()", e)
        GLib.idle_add(self.hide)

    def __clean_cache(self):
        """
            Clean the cache
        """
        for child in self.__flowbox.get_children():
            encoded = sha256(child.uri.encode("utf-8")).hexdigest()
            filepath = "%s/%s" % (EOLIE_CACHE_PATH, encoded)
            f = Gio.File.new_for_path(filepath)
            try:
                if f.query_exists():
                    f.delete()
            except Exception as e:
                print("ImagesPopover::__clean_cache():", e)

    def __on_write_all_async(self, stream, result, uri):
        """
            Add image
            @param stream as Gio.OutputStream
            @param result as Gio.AsyncResult
            @param uri as str
        """
        try:
            stream.write_all_finish(result)
            self.__add_image(uri)
        except Exception as e:
            print("ImagesPopover::__on_write_all_async()", e)

    def __on_load_uri_content(self, uri, status, content, uris):
        """
            Load pending uris
            @param uri as str
            @param status as bool
            @param content as bytes
            @param uris as [str]
        """
        if status:
            encoded = sha256(uri.encode("utf-8")).hexdigest()
            filepath = "%s/%s" % (EOLIE_CACHE_PATH, encoded)
            f = Gio.File.new_for_path(filepath)
            stream = f.append_to(Gio.FileCreateFlags.REPLACE_DESTINATION,
                                 self.__cancellable)
            stream.write_all_async(content, GLib.PRIORITY_DEFAULT,
                                   self.__cancellable,
                                   self.__on_write_all_async, uri)
        if uris:
            uri = uris.pop(0)
            self.__task_helper.load_uri_content(uri,
                                                self.__cancellable,
                                                self.__on_load_uri_content,
                                                uris)
        else:
            self.__spinner.stop()
            self.__button.set_sensitive(True)

    def __on_get_images(self, source, result):
        """
            Get result and load pending uris
            @param source as GObject.Object
            @param result as Gio.AsyncResult
        """
        uris = []
        try:
            uris = source.call_finish(result)[0]
        except Exception as e:
            print("ImagesPopover::__on_get_images()", e)
        self.__on_load_uri_content(None, False, b"", uris)

    def __on_closed(self, popover):
        """
            Clean cache
        """
        self.__spinner.stop()
        self.__cancellable.cancel()
        self.__task_helper.run(self.__clean_cache)
