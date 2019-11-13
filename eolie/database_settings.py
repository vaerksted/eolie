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

from gi.repository import GLib

import sqlite3
from urllib.parse import urlparse
from threading import Lock

from eolie.sqlcursor import SqlCursor
from eolie.define import EOLIE_DATA_PATH
from eolie.logger import Logger
from eolie.utils import get_safe_netloc


class DatabaseSettings:
    """
        Store various settings for webpage
    """
    __UPGRADES = {
        1: "ALTER TABLE settings ADD accept_tls INT NOT NULL DEFAULT 0",
        2: "ALTER TABLE settings ADD night_mode INT NOT NULL DEFAULT 0",
    }

    # SQLite documentation:
    # In SQLite, a column with type INTEGER PRIMARY KEY
    # is an alias for the ROWID.
    # Here, we define an id INT PRIMARY KEY but never feed it,
    # this make VACUUM not destroy rowids...
    __create_settings = '''CREATE TABLE settings (
                                           id INTEGER PRIMARY KEY,
                                           uri TEXT NOT NULL,
                                           chooser_uri TEXT,
                                           languages TEXT,
                                           zoom INT,
                                           accept_tls INT NOT NULL DEFAULT 0,
                                           night_mode INT NOT NULL DEFAULT 0,
                                           geolocation INT,
                                           user_agent TEXT
                                           )'''

    def __init__(self):
        """
            Create database tables or manage update if needed
            @param suffix as str
        """
        self.thread_lock = Lock()
        new_version = len(self.__UPGRADES)
        self.__DB_PATH = "%s/websettings.db" % EOLIE_DATA_PATH
        if not GLib.file_test(self.__DB_PATH, GLib.FileTest.IS_REGULAR):
            try:
                if not GLib.file_test(EOLIE_DATA_PATH, GLib.FileTest.IS_DIR):
                    GLib.mkdir_with_parents(EOLIE_DATA_PATH, 0o0750)
                # Create db schema
                with SqlCursor(self, True) as sql:
                    sql.execute(self.__create_settings)
                    sql.execute("PRAGMA user_version=%s" % new_version)
            except Exception as e:
                Logger.error("DatabaseSettings::__init__(): %s", e)
        # DB upgrade, TODO Make it generic between class
        version = 0
        with SqlCursor(self, True) as sql:
            result = sql.execute("PRAGMA user_version")
            v = result.fetchone()
            if v is not None:
                version = v[0]
            if version < new_version:
                for i in range(version + 1, new_version + 1):
                    try:
                        sql.execute(self.__UPGRADES[i])
                    except:
                        Logger.error("Settings DB upgrade %s failed", i)
                sql.execute("PRAGMA user_version=%s" % new_version)

    def set(self, option, uri, status):
        """
            Set option for URI to value
            @param option as str
            @param uri as str
            @param status as object
        """
        parsed = urlparse(uri)
        if parsed.scheme not in ["http", "https"]:
            return
        try:
            netloc = get_safe_netloc(uri)
            with SqlCursor(self, True) as sql:
                result = sql.execute("SELECT rowid FROM settings\
                                      WHERE uri=?", (netloc,))
                v = result.fetchone()
                if v is not None:
                    sql.execute("UPDATE settings\
                                 SET %s=?\
                                 WHERE uri=?" % option,
                                (status, netloc))
                else:
                    sql.execute("INSERT INTO settings\
                                          (uri, %s)\
                                          VALUES (?, ?)" % option,
                                (netloc, status))
        except Exception as e:
            Logger.error("DatabaseSettings::set(): %s", e)

    def get(self, option, uri):
        """
            Get option for URI
            @param option as str
            @param uri as str
            @return object
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT %s FROM settings\
                                  WHERE uri=?" % option,
                                 (get_safe_netloc(uri),))
            v = result.fetchone()
            if v is not None:
                return v[0]
            return None

    def get_languages(self, uri):
        """
            Get languages for uri
            @param uri as str
            @return codes as [str]
            @raise if not found
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT languages FROM settings\
                                  WHERE uri=?", (get_safe_netloc(uri),))
            v = result.fetchone()
            if v is not None:
                languages = v[0]
                if languages:
                    return languages.split(";")
                else:
                    return []
            else:
                return None

    def add_language(self, code, uri):
        """
            Add language for uri
            @param code as str
            @param uri as str
        """
        parsed = urlparse(uri)
        if parsed.scheme not in ["http", "https"]:
            return
        try:
            with SqlCursor(self, True) as sql:
                codes = self.get_languages(uri)
                if codes is not None:
                    if code not in codes:
                        codes.append(code)
                    sql.execute("UPDATE settings\
                                 SET languages=?\
                                 WHERE uri=?", (";".join(codes),
                                                get_safe_netloc(uri)))
                else:
                    sql.execute("INSERT INTO settings\
                                          (uri, languages)\
                                          VALUES (?, ?)",
                                (get_safe_netloc(uri), code))
        except Exception as e:
            Logger.error("DatabaseSettings::add_language(): %s", e)

    def remove_language(self, code, uri):
        """
            Remove language for uri
            @param code as str
            @param uri as str
        """
        codes = self.get_languages(uri)
        if codes is not None and code in codes:
            codes.remove(code)
            with SqlCursor(self, True) as sql:
                sql.execute("UPDATE settings\
                                 SET languages=?\
                                 WHERE uri=?", (";".join(codes),
                                                get_safe_netloc(uri)))

    def get_cursor(self):
        """
            Return a new sqlite cursor
        """
        try:
            c = sqlite3.connect(self.__DB_PATH, 600.0)
            return c
        except Exception as e:
            Logger.error("DatabaseSettings::get_cursor(): %s", e)
            exit(-1)
