# Copyright (c) 2017-2021 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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
from eolie.utils import emit_signal
from eolie.define import EOLIE_DATA_PATH, App
from eolie.content_blocker_exceptions import ContentBlockerExceptions
from eolie.logger import Logger


class ContentBlocker(GObject.Object):
    """
        A WebKit Content Blocker
    """
    _DB_PATH = "%s/content_blocker" % EOLIE_DATA_PATH
    _JSON_PATH = "%s/content_blocker_json" % EOLIE_DATA_PATH
    __gsignals__ = {
        "set-filter": (GObject.SignalFlags.RUN_FIRST, None,
                       (GObject.TYPE_PYOBJECT,)),
        "unset-filter": (GObject.SignalFlags.RUN_FIRST, None,
                         (GObject.TYPE_PYOBJECT,))
    }

    def __init__(self, name):
        """
            Init helper
            @param blocker name as str
        """
        try:
            GObject.Object.__init__(self)
            self.__filter = None
            self.__name = name
            self.__exceptions = ContentBlockerExceptions(name)
            self._cancellable = Gio.Cancellable.new()
            self._task_helper = TaskHelper()
            self.__store = WebKit2.UserContentFilterStore.new(self._DB_PATH)
            if not GLib.file_test(self._JSON_PATH, GLib.FileTest.IS_DIR):
                GLib.mkdir_with_parents(self._JSON_PATH, 0o0750)
            if self.enabled:
                self.load()
            App().settings.connect("changed::%s" % name,
                                   self.__on_setting_changed)
        except Exception as e:
            Logger.error("ContentBlocker::__init__(): %s", e)

    def load(self):
        """
            Load from store
        """
        self.__store.load(self.__name, self._cancellable,
                          self.__on_store_load)

    def save(self, bytes):
        """
            Save to store
        """
        self.__store.save(self.__name, GLib.Bytes(bytes), self._cancellable,
                          self.__on_store_save)

    def update(self):
        """
            Update current filters with new exceptions
        """
        try:
            f = Gio.File.new_for_path(
                "%s/%s.json" % (self._JSON_PATH, self.__name))
            if f.query_exists():
                (status, content, tag) = f.load_contents(None)
                if status:
                    rules = json.loads(content.decode("utf-8"))
                    self._task_helper.run(self._save_rules, rules)
            else:
                self._task_helper.run(self._save_rules, self.DEFAULT)
        except Exception as e:
            Logger.error("ContentBlocker::update(): %s", e)

    def stop(self):
        """
            Stop update
        """
        self._cancellable.cancel()
        self._cancellable = Gio.Cancellable.new()

    @property
    def exceptions(self):
        """
            Get exceptions
            @return ContentBlockerExceptions
        """
        return self.__exceptions

    @property
    def filter(self):
        """
            Get filters
            return WebKit2.UserContentFilter
        """
        return self.__filter

    @property
    def name(self):
        """
            Get name
            return str
        """
        return self.__name

    @property
    def enabled(self):
        """
            True if enabled
            @return bool
        """
        return App().settings.get_value(self.__name)

#######################
# PROTECTED           #
#######################
    def _save_rules(self, rules):
        """
            Save rules to file
            @param uri as str
            @param rules []
        """
        try:
            new_rules = list(rules)
            if self.__exceptions is not None:
                new_rules += self.__exceptions.rules
            bytes = json.dumps(new_rules).encode("utf-8")
            self.save(bytes)
        except Exception as e:
            Logger.error("ContentBlocker::_save_rules(): %s", e)

#######################
# PRIVATE             #
#######################
    def __on_store_load(self, store, result):
        """
            Notify for new filter
            @param store as WebKit2.UserContentFilterStore
            @param result as Gio.AsyncResult
            @param encoded as str
        """
        try:
            self.__filter = store.save_finish(result)
            if self.enabled:
                emit_signal(self, "set-filter", self.__filter)
        except Exception as e:
            Logger.error("ContentBlocker::__on_store_load(): %s", e)

    def __on_store_save(self, store, result):
        """
            Notify for new filter
            @param store as WebKit2.UserContentFilterStore
            @param result as Gio.AsyncResult
        """
        try:
            self.__filter = store.load_finish(result)
            if self.enabled:
                emit_signal(self, "set-filter", self.__filter)
        except Exception as e:
            Logger.error("ContentBlocker::__on_store_save(): %s", e)

    def __on_setting_changed(self, settings, value):
        """
            Enable disable filtering
            @param settings as Gio.Settings
            @param value as GLib.Variant
        """
        if self.enabled:
            self.load()
        else:
            emit_signal(self, "unset-filter", self.__filter)
