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

from gi.repository import Gio, GObject, GLib
from gi.repository.Gio import FILE_ATTRIBUTE_TIME_MODIFIED

from hashlib import md5
from time import time

from eolie.helper_task import TaskHelper
from eolie.define import EOLIE_CACHE_PATH
from eolie.css_stylesheet import StyleSheet


class StyleSheets(GObject.Object):
    """
        Represent a stylesheets collection
    """

    __gsignals__ = {
        "populated": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "invalidated": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self):
        """
            Init StyleSheet
        """
        GObject.Object.__init__(self)
        self.__task_helper = TaskHelper()
        self.__cancellable = None
        self.__populated = False
        self.__stylesheets = {}

    def set_cancellable(self, cancellable):
        """
            Set current cancellable
            @param cancellable as Gio.Cancellable
        """
        self.__cancellable = cancellable

    def load_css_uri(self, message, started_time):
        """
            Load CSS URI as user style
            @param started_time as int
            @param message as str
        """
        self.__populated = False
        count = len(self.__stylesheets)
        uri = message.replace("@EOLIE_CSS_URI@", "")
        if uri in self.__stylesheets.keys():
            self.__stylesheets[uri].set_started_time(started_time)
        else:
            stylesheet = self.__load_from_cache(uri)
            if stylesheet is None:
                stylesheet = StyleSheet(uri=uri)
                stylesheet.connect("populated", self.__on_stylesheet_populated)
                self.__stylesheets[uri] = stylesheet
                stylesheet.set_started_time(started_time)
                self.__task_helper.run(stylesheet.populate)
            else:
                self.__stylesheets[uri] = stylesheet
                stylesheet.set_started_time(started_time)
                self.__check_populated()
        if count != len(self.__stylesheets):
            self.emit("invalidated")

    def load_css_text(self, message, started_time):
        """
            Load CSS text as user style
            @param started_time as int
            @param message as str
        """
        self.__populated = False
        count = len(self.__stylesheets)
        contents = message.replace("@EOLIE_CSS_TEXT@", "")
        if contents:
            uri = md5(contents.encode("utf-8")).hexdigest()
            if uri in self.__stylesheets.keys():
                self.__stylesheets[uri].set_started_time(started_time)
                return
            stylesheet = StyleSheet(contents=contents)
            self.__stylesheets[uri] = stylesheet
            stylesheet.set_started_time(started_time)
            stylesheet.connect("populated", self.__on_stylesheet_populated)
            self.__task_helper.run(stylesheet.populate)
        if count != len(self.__stylesheets):
            self.emit("invalidated")

    def get_css_text(self, started_time):
        """
            Get css text for all stylsheets
            @param started_time as str
            @return str
        """
        css = []
        for key in list(self.__stylesheets.keys()):
            stylesheet = self.__stylesheets[key]
            if stylesheet.started_time == started_time:
                css.append(stylesheet.css_text)
            else:
                del self.__stylesheets[key]
        return "".join(css)

    @property
    def populated(self):
        """
            True if populated
            @return bool
        """
        return self.__populated

#######################
# PRIVATE             #
#######################
    def __check_populated(self):
        """
            Check all stylsheets are populated and emit signal if so
        """
        if not self.__populated:
            for uri in self.__stylesheets.keys():
                if not self.__stylesheets[uri].populated:
                    return
            self.__populated = True
            GLib.idle_add(self.emit, "populated")

    def __load_from_cache(self, uri):
        """
            Load CSS from cache
            @param uri as str
            @return StyleSheet
        """
        encoded = md5(uri.encode("utf-8")).hexdigest()
        filepath = "%s/css/%s.css" % (EOLIE_CACHE_PATH, encoded)
        f = Gio.File.new_for_path(filepath)
        if f.query_exists():
            info = f.query_info(FILE_ATTRIBUTE_TIME_MODIFIED,
                                Gio.FileQueryInfoFlags.NONE,
                                None)
            mtime = int(info.get_attribute_as_string("time::modified"))
            if time() - mtime < 86400:
                (status, contents, tags) = f.load_contents(None)
                if status:
                    stylesheet = StyleSheet(uri=uri)
                    stylesheet.set_css_text(contents.decode("utf-8"))
                    return stylesheet
        return None

    def __on_stylesheet_populated(self, stylesheet):
        """
            Load stylesheet
            @param stylesheet as StyleSheet
        """
        if stylesheet.uri is not None:
            encoded = md5(stylesheet.uri.encode("utf-8")).hexdigest()
            filepath = "%s/css/%s.css" % (EOLIE_CACHE_PATH, encoded)
            f = Gio.File.new_for_path(filepath)
            fstream = f.replace(None, False,
                                Gio.FileCreateFlags.REPLACE_DESTINATION,
                                None)
            if fstream is not None:
                fstream.write(stylesheet.css_text.encode("utf-8"), None)
                fstream.close()
        self.__check_populated()
