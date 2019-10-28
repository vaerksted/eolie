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

from gi.repository import Gio, GObject, GLib, WebKit2

import json

from eolie.helper_task import TaskHelper
from eolie.content_blocker_ad_exceptions import AdContentBlockerExceptions
from eolie.define import EOLIE_DATA_PATH, ADBLOCK_URIS, App
from eolie.logger import Logger


class AdContentBlocker(GObject.Object):
    """
        A WebKit Content Blocker for ads
    """
    __DB_PATH = "%s/content_blocker" % EOLIE_DATA_PATH
    __JSON_PATH = "%s/content_blocker_json" % EOLIE_DATA_PATH
    __gsignals__ = {
        "new-filter": (GObject.SignalFlags.RUN_FIRST, None,
                       (GObject.TYPE_PYOBJECT,))
    }

    def __init__(self):
        """
            Init adblock helper
        """
        try:
            GObject.Object.__init__(self)
            self.__filter = None
            self.__cancellable = Gio.Cancellable.new()
            self.__task_helper = TaskHelper()
            self.__store = WebKit2.UserContentFilterStore.new(self.__DB_PATH)
            self.__exceptions = AdContentBlockerExceptions()
            if not GLib.file_test(self.__JSON_PATH, GLib.FileTest.IS_DIR):
                GLib.mkdir_with_parents(self.__JSON_PATH, 0o0750)
            App().settings.connect("changed::adblock",
                                   self.__on_adblock_changed)
            self.__store.load("adblock", self.__cancellable,
                              self.__on_store_load)
            self.__download_uris(list(ADBLOCK_URIS))
        except Exception as e:
            Logger.error("AdContentBlocker::__init__(): %s", e)

    def update(self):
        """
            Update current filters with new exceptions
        """
        f = Gio.File.new_for_path("%s/adblock.json" % self.__JSON_PATH)
        if f.query_exists():
            (status, content, tag) = f.load_contents(None)
            if status:
                self.__task_helper.run(self.__save_rules, content)

    def stop(self):
        """
            Stop update
        """
        self.__cancellable.cancel()
        self.__cancellable = Gio.Cancellable.new()

    @property
    def exceptions(self):
        """
            Get adblock exceptions
            @return AdblockExceptions
        """
        return self.__exceptions

    @property
    def filter(self):
        """
            Get filters
            return WebKit2.UserContentFilter
        """
        return self.__filter

#######################
# PRIVATE             #
#######################
    def __download_uris(self, uris):
        """
            Update database from the web
            @param uris as [str]
        """
        if not Gio.NetworkMonitor.get_default().get_network_available():
            return
        if uris:
            uri = uris.pop(0)
            self.__task_helper.load_uri_content(uri,
                                                self.__cancellable,
                                                self.__on_load_uri_content,
                                                uris)

    def __save_rules(self, rules):
        """
            Save rules to file
            @param uri as str
            @param rules as bytes
        """
        data = json.loads(rules.decode("utf-8"))
        data += self.__exceptions.rules
        rules = json.dumps(data).encode("utf-8")
        try:
            self.__store.save("adblock", GLib.Bytes(rules), self.__cancellable,
                              self.__on_store_save)
        except Exception as e:
            Logger.error("AdContentBlocker::__save_rules(): %s", e)

    def __on_store_load(self, store, result):
        """
            Notify for new filter
            @param store as WebKit2.UserContentFilterStore
            @param result as Gio.AsyncResult
            @param encoded as str
        """
        try:
            self.__filter = store.save_finish(result)
            self.emit("new-filter", self.__filter)
        except Exception as e:
            Logger.error("AdContentBlocker::__on_store_load(): %s", e)

    def __on_store_save(self, store, result):
        """
            Notify for new filter
            @param store as WebKit2.UserContentFilterStore
            @param result as Gio.AsyncResult
        """
        try:
            self.__filter = store.load_finish(result)
            self.emit("new-filter", self.__filter)
        except Exception as e:
            Logger.error("AdContentBlocker::__on_store_save(): %s", e)

    def __on_save_rules(self, result, uris):
        """
            Load next uri
            @ignore result
            @param uris as [str]
        """
        if self.__cancellable.is_cancelled():
            return
        self.__download_uris(uris)

    def __on_load_uri_content(self, uri, status, content, uris):
        """
            Save loaded values
            @param uri as str
            @param status as bool
            @param content as bytes
            @param uris as [str]
        """
        Logger.debug("AdContentBlocker::__on_load_uri_content(): %s", uri)
        if status:
            # Save to sources
            f = Gio.File.new_for_path("%s/adblock.json" % self.__JSON_PATH)
            f.replace_contents(content,
                               None,
                               False,
                               Gio.FileCreateFlags.REPLACE_DESTINATION,
                               None)
            self.__task_helper.run(self.__save_rules, content,
                                   callback=(self.__on_save_rules, uris))
        else:
            self.__on_save_rules(None, uris)
            Logger.error("AdContentBlocker::__on_load_uri_content(): %s", uri)

    def __on_adblock_changed(self, settings, value):
        """
            Enable disable filtering
            @param settings as Gio.Settings
            @param value as GLib.Variant
        """
        adblock = self.settings.get_value("adblock")
        if adblock:
            self.__store.load("adblock", self.__cancellable,
                              self.__on_store_load)
        else:
            self.__store.save("adblock", GLib.Bytes(b""), self.__cancellable,
                              self.__on_store_save)
