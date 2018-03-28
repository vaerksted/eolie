# Copyright (c) 2017-2018 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

import sqlite3
from time import time, sleep
import json
from threading import Lock
from pickle import dump, load

from eolie.helper_task import TaskHelper
from eolie.sqlcursor import SqlCursor
from eolie.define import EOLIE_DATA_PATH
from eolie.logger import Logger


class DatabasePhishing:
    """
        Phishing database
    """
    __DB_PATH = "%s/phishing.db" % EOLIE_DATA_PATH
    __URI = "http://data.phishtank.com/data/online-valid.json"
    __SCHEMA_VERSION = 0
    __UPDATE = 172800
    # SQLite documentation:
    # In SQLite, a column with type INTEGER PRIMARY KEY
    # is an alias for the ROWID.
    # Here, we define an id INT PRIMARY KEY but never feed it,
    # this make VACUUM not destroy rowids...
    __create_phishing = '''CREATE TABLE phishing (
                                               id INTEGER PRIMARY KEY,
                                               uri TEXT NOT NULL,
                                               mtime INT NOT NULL
                                               )'''
    __create_phishing_idx = """CREATE UNIQUE INDEX idx_phishing ON phishing(
                                               uri)"""

    def __init__(self):
        """
            Create database tables or manage update if needed
        """
        self.thread_lock = Lock()
        self.__cancellable = Gio.Cancellable.new()
        self.__task_helper = TaskHelper()
        self.__phishing_mtime = int(time())
        self.__regex = None

    def create_db(self):
        """
            Create databse
        """
        if not GLib.file_test(EOLIE_DATA_PATH, GLib.FileTest.IS_DIR):
            GLib.mkdir_with_parents(EOLIE_DATA_PATH, 0o0750)
        # If DB schema changed, remove it
        if GLib.file_test(self.__DB_PATH, GLib.FileTest.IS_REGULAR):
            with SqlCursor(self) as sql:
                result = sql.execute("PRAGMA user_version")
                v = result.fetchone()
                if v is None or v[0] != self.__SCHEMA_VERSION:
                    f = Gio.File.new_for_path(self.__DB_PATH)
                    f.delete()
        if not GLib.file_test(self.__DB_PATH, GLib.FileTest.IS_REGULAR):
            try:
                # Create db schema
                with SqlCursor(self) as sql:
                    sql.execute(self.__create_phishing)
                    sql.execute(self.__create_phishing_idx)
                    sql.execute("PRAGMA user_version=%s" %
                                self.__SCHEMA_VERSION)
            except Exception as e:
                Logger.error("DatabasePhishing::__init__(): %s", e)

    def update(self):
        """
            Update database
        """
        if not Gio.NetworkMonitor.get_default().get_network_available():
            return
        # DB version is last successful sync mtime
        try:
            version = load(open(EOLIE_DATA_PATH + "/phishing.bin", "rb"))
        except:
            version = 0
        self.__cancellable.reset()
        if self.__phishing_mtime - version > self.__UPDATE:
            self.__on_load_uri_content(None, False, b"", [self.__URI])

    def is_phishing(self, uri):
        """
            True if uri is phishing
            @param uri as str
            @return bool
        """
        uri = uri.rstrip("/")
        try:
            with SqlCursor(self) as sql:
                result = sql.execute("SELECT uri FROM phishing\
                                      WHERE uri=?", (uri,))
                v = result.fetchone()
                return v is not None
        except Exception as e:
            Logger.error("DatabasePhishing::is_phishing(): %s", e)
            return False

    def stop(self):
        """
            Stop update
        """
        self.__cancellable.cancel()
        self.__stop = True

    def get_cursor(self):
        """
            Return a new sqlite cursor
        """
        try:
            c = sqlite3.connect(self.__DB_PATH, 600.0)
            return c
        except Exception as e:
            Logger.error("DatabasePhishing::get_cursor(): %s", e)
            exit(-1)

#######################
# PRIVATE             #
#######################
    def __save_rules(self, rules, uris):
        """
            Save rules to db
            @param rules as bytes
            @param uris as [str]
        """
        SqlCursor.add(self)
        try:
            result = rules.decode('utf-8')
            j = json.loads(result)
            with SqlCursor(self) as sql:
                count = 0
                for item in j:
                    if self.__cancellable.is_cancelled():
                        raise IOError("Cancelled")
                    uri = item["url"].rstrip("/")
                    try:
                        sql.execute("INSERT INTO phishing\
                                     (uri, mtime) VALUES (?, ?)",
                                    (uri, self.__phishing_mtime))
                    except:
                        sql.execute("UPDATE phishing set mtime=?\
                                     WHERE uri=?",
                                    (self.__phishing_mtime, uri))
                    count += 1
                    if count == 1000:
                        SqlCursor.commit(self)
                        # Do not flood sqlite
                        # this allow webkit extension to run
                        sleep(0.1)
                        count = 0
            # We are the last call to save_rules()?
            # Delete removed entries and commit
            if not uris:
                with SqlCursor(self) as sql:
                    sql.execute("DELETE FROM phishing\
                                 WHERE mtime!=?", (self.__phishing_mtime,))
                    try:
                        dump(self.__phishing_mtime,
                             open(EOLIE_DATA_PATH + "/phishing.bin", "wb"))
                    except Exception as e:
                        Logger.error("DatabasePhishing::__save_rules(): %s", e)
        except Exception as e:
            Logger.error("DatabasePhishing::__save_rules():%s -> %s", e, rules)
        SqlCursor.remove(self)

    def __on_load_uri_content(self, uri, status, content, uris):
        """
            Load pending uris
            @param uri as str
            @param status as bool
            @param content as bytes
            @param uris as [str]
        """
        if status:
            self.__task_helper.run(self.__save_rules, content, uris)
        if uris:
            uri = uris.pop(0)
            self.__task_helper.load_uri_content(uri,
                                                self.__cancellable,
                                                self.__on_load_uri_content,
                                                uris)
