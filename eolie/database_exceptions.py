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

import itertools
import sqlite3
from threading import Lock

from eolie.sqlcursor import SqlCursor
from eolie.define import EOLIE_DATA_PATH
from eolie.logger import Logger


class DatabaseExceptions:
    """
        Handle exceptions
    """
    # SQLite documentation:
    # In SQLite, a column with type INTEGER PRIMARY KEY
    # is an alias for the ROWID.
    # Here, we define an id INT PRIMARY KEY but never feed it,
    # this make VACUUM not destroy rowids...
    __create_exceptions = '''CREATE TABLE exceptions (
                                               id INTEGER PRIMARY KEY,
                                               value TEXT NOT NULL,
                                               domain TEXT NOT NULL
                                               )'''

    def __init__(self, suffix):
        """
            Create database tables or manage update if needed
            @param suffix as str
        """
        self.thread_lock = Lock()
        self.__DB_PATH = "%s/exceptions2_%s.db" % (EOLIE_DATA_PATH,
                                                   suffix)
        self.__cancellable = Gio.Cancellable.new()
        if not GLib.file_test(self.__DB_PATH, GLib.FileTest.IS_REGULAR):
            try:
                if not GLib.file_test(EOLIE_DATA_PATH, GLib.FileTest.IS_DIR):
                    GLib.mkdir_with_parents(EOLIE_DATA_PATH, 0o0750)
                # Create db schema
                with SqlCursor(self) as sql:
                    sql.execute(self.__create_exceptions)
            except Exception as e:
                Logger.error("DatabaseExceptions::__init__(): %s", e)

    def add_exception(self, value, domain=""):
        """
            Add an exception
            @param value as str
            @param domain as str
        """
        try:
            with SqlCursor(self) as sql:
                sql.execute("INSERT INTO exceptions (value, domain)\
                             VALUES (?, ?)", (value, domain))
        except:
            pass

    def remove_exception(self, value, domain=""):
        """
            Remove an exception
            @param value as str
            @param domain as str
        """
        try:
            with SqlCursor(self) as sql:
                sql.execute("DELETE FROM exceptions\
                             WHERE value=? AND domain=?",
                            (value, domain))
        except:
            pass

    def get_values_for_domain(self, domain):
        """
            Get values for domain
            @param domain as str
            @return [str]
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT value FROM exceptions\
                                  WHERE domain=?", (domain,))
            return list(itertools.chain(*result))

    def find(self, value, domain=""):
        """
            True if value is an exception
            @param value  as str
            @param domain as str
            @return bool
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT rowid FROM exceptions\
                                  WHERE value=? AND domain=?", (value, domain))
            v = result.fetchone()
            return v is not None

    def find_parsed(self, parsed):
        """
            True if value is an exception
            @param parsed as urlparse.parsed
            @return bool
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT rowid FROM exceptions\
                                  WHERE value=? or value=?",
                                 (parsed.netloc, parsed.netloc + parsed.path))
            v = result.fetchone()
            return v is not None

    def get_cursor(self):
        """
            Return a new sqlite cursor
        """
        try:
            c = sqlite3.connect(self.__DB_PATH, 600.0)
            return c
        except Exception as e:
            Logger.error("DatabaseExceptions::get_cursor(): %s", e)
            exit(-1)
