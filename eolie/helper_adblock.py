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

from gi.repository import GObject, Gio, GLib, WebKit2
from gi.repository.Gio import FILE_ATTRIBUTE_STANDARD_NAME, \
                              FILE_ATTRIBUTE_TIME_MODIFIED


from hashlib import sha256

from eolie.helper_task import TaskHelper
from eolie.define import EOLIE_DATA_PATH
from eolie.logger import Logger

SCAN_QUERY_INFO = "{},{}".format(FILE_ATTRIBUTE_STANDARD_NAME,
                                 FILE_ATTRIBUTE_TIME_MODIFIED)


class AdblockHelper(GObject.Object):
    """
        Eolie adblock helper
    """
    __DB_PATH = "%s/adblock" % EOLIE_DATA_PATH
    __UPDATE = 172800
    __gsignals__ = {
        "new-filter": (GObject.SignalFlags.RUN_FIRST, None,
                       (GObject.TYPE_PYOBJECT,))
    }

    def __init__(self):
        """
            Create database tables or manage update if needed
        """
        try:
            GObject.Object.__init__(self)
            self.__filters = {}
            self.__cancellable = Gio.Cancellable.new()
            self.__task_helper = TaskHelper()
            self.__store = WebKit2.UserContentFilterStore.new(self.__DB_PATH)
        except Exception as e:
            Logger.error("DatabaseAdblock::__init__(): %s", e)

    def update(self, uris):
        """
            Update database
            @param uris as [str]
        """
        if not Gio.NetworkMonitor.get_default().get_network_available():
            return
        if uris:
            uri = uris.pop(0)
            encoded = sha256(uri.encode("utf-8")).hexdigest()
            self.__store.load(encoded, self.__cancellable,
                              self.__on_store_load, encoded)
            self.__task_helper.load_uri_content(uri,
                                                self.__cancellable,
                                                self.__on_load_uri_content,
                                                uris)

    def stop(self):
        """
            Stop update
        """
        self.__cancellable.cancel()
        self.__cancellable = Gio.Cancellable.new()

    @property
    def filters(self):
        """
            Get filters
            return [WebKit2.UserContentFilter]
        """
        return list(self.__filters.values())

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
        try:
            self.__store.save(encoded, GLib.Bytes(rules), self.__cancellable,
                              self.__on_store_save, encoded)
        except Exception as e:
            Logger.warning("DatabaseAdblock::__save_rules(): %s", e)

    def __on_store_load(self, store, result, encoded):
        """
            Notify for new filter
            @param store as WebKit2.UserContentFilterStore
            @param result as Gio.AsyncResult
            @param encoded as str
        """
        content_filter = store.save_finish(result)
        self.__filters[encoded] = content_filter
        self.emit("new-filter", content_filter)

    def __on_store_save(self, store, result, encoded):
        """
            Notify for new filter
            @param store as WebKit2.UserContentFilterStore
            @param result as Gio.AsyncResult
            @param encoded as str
        """
        content_filter = store.load_finish(result)
        self.__filters[encoded] = content_filter
        self.emit("new-filter", content_filter)

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
