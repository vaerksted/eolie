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

from gi.repository import Gio, GLib
from gi.repository.Gio import FILE_ATTRIBUTE_STANDARD_NAME, \
                              FILE_ATTRIBUTE_TIME_MODIFIED


from time import time
from hashlib import sha256

from eolie.helper_task import TaskHelper
from eolie.define import EOLIE_DATA_PATH
from eolie.logger import Logger

SCAN_QUERY_INFO = "{},{}".format(FILE_ATTRIBUTE_STANDARD_NAME,
                                 FILE_ATTRIBUTE_TIME_MODIFIED)


class DatabaseAdblock:
    """
        Eolie adblock db
    """
    __DB_PATH = "%s/adblock" % EOLIE_DATA_PATH

    __URIS = ["https://easylist-downloads.adblockplus.org/" +
              "easylist_content_blocker.json"]

    __UPDATE = 172800

    def __init__(self):
        """
            Create database tables or manage update if needed
        """
        self.__cancellable = Gio.Cancellable.new()
        self.__task_helper = TaskHelper()
        if not GLib.file_test(self.__DB_PATH, GLib.FileTest.IS_DIR):
            try:
                GLib.mkdir_with_parents(self.__DB_PATH, 0o0750)
            except Exception as e:
                Logger.error("DatabaseAdblock::__init__(): %s", e)
        self.update(list(self.__URIS))

    def update(self, uris=[]):
        """
            Update database
        """
        if not Gio.NetworkMonitor.get_default().get_network_available():
            return

        while uris:
            uri = uris.pop(0)
            encoded = sha256(uri.encode("utf-8")).hexdigest()
            f = Gio.File.new_for_path("%s/%s.json" % (self.__DB_PATH, encoded))
            try:
                info = f.query_info(SCAN_QUERY_INFO,
                                    Gio.FileQueryInfoFlags.NONE,
                                    None)
                mtime = int(info.get_attribute_as_string("time::modified"))
            except Exception as e:
                Logger.warning("DatabaseAdblock::update(): %s", e)
                mtime = self.__UPDATE
            if time() - mtime >= self.__UPDATE:
                self.__task_helper.load_uri_content(uri,
                                                    self.__cancellable,
                                                    self.__on_load_uri_content,
                                                    uris)
                return

    def stop(self):
        """
            Stop update
        """
        self.__cancellable.cancel()
        self.__cancellable = Gio.Cancellable.new()

#######################
# PRIVATE             #
#######################
    def __save_rules(self, uri, rules):
        """
            Save rules to file
            @param uri as str
            @param rules as bytes
        """
        encoded = sha256(uri.encode("utf-8")).hexdigest()
        f = Gio.File.new_for_path("%s/%s.json" % (self.__DB_PATH, encoded))
        try:
            f.replace_contents(rules,
                               None,
                               False,
                               Gio.FileCreateFlags.REPLACE_DESTINATION,
                               None)
        except Exception as e:
            Logger.warning("DatabaseAdblock::__save_rules(): %s", e)

    def __on_save_rules(self, result, uris):
        """
            Load next uri
            @ignore result
            @param uris as [str]
        """
        if self.__cancellable.is_cancelled():
            return
        self.update(uris)

    def __on_load_uri_content(self, uri, status, content, uris):
        """
            Save loaded values
            @param uri as str
            @param status as bool
            @param content as bytes
            @param uris as [str]
        """
        Logger.debug("DatabaseAdblock::__on_load_uri_content(): %s", uri)
        if status:
            self.__task_helper.run(self.__save_rules, uri, content,
                                   callback=(self.__on_save_rules, uris))
        else:
            self.__on_save_rules(None, uris)
            Logger.error("DatabaseAdblock::__on_load_uri_content(): %s", uri)
