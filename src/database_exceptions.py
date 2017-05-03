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

from gi.repository import Gio

import sqlite3

from eolie.sqlcursor import SqlCursor
from eolie.define import EOLIE_LOCAL_PATH


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
                                               uri TEXT NOT NULL
                                               )'''

    def __init__(self, suffix):
        """
            Create database tables or manage update if needed
            @param suffix as str
        """
        self.__DB_PATH = "%s/exceptions_%s.db" % (EOLIE_LOCAL_PATH,
                                                  suffix)
        self.__cancellable = Gio.Cancellable.new()
        f = Gio.File.new_for_path(self.__DB_PATH)
        # Lazy loading if not empty
        if not f.query_exists():
            try:
                d = Gio.File.new_for_path(EOLIE_LOCAL_PATH)
                if not d.query_exists():
                    d.make_directory_with_parents()
                # Create db schema
                with SqlCursor(self) as sql:
                    sql.execute(self.__create_exceptions)
                    sql.commit()
            except Exception as e:
                print("DatabaseExceptions::__init__(): %s" % e)

    def add_exception(self, uri):
        """
            Add an exception
            @param uri as str
        """
        try:
            with SqlCursor(self) as sql:
                sql.execute("INSERT INTO exceptions (uri) VALUES (?)", (uri,))
                sql.commit()
        except:
            pass

    def remove_exception(self, uri):
        """
            Remove an exception
            @param uri as str
        """
        try:
            with SqlCursor(self) as sql:
                sql.execute("DELETE FROM exceptions WHERE uri=?", (uri,))
                sql.commit()
        except:
            pass

    def find(self, uri):
        """
            True if uri is an exception
            @param uri as str
            @return bool
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT rowid FROM exceptions\
                                  WHERE uri=?", (uri,))
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
            print(e)
            exit(-1)
