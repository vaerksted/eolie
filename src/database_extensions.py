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

from gi.repository import Gio, GLib

import sqlite3

from eolie.sqlcursor import SqlCursor
from eolie.utils import strip_uri


class DatabaseExtensions:
    """
        Allow python webkit extension to store data for Eolie
    """
    if GLib.getenv("XDG_DATA_HOME") is None:
        __LOCAL_PATH = GLib.get_home_dir() + "/.local/share/eolie"
    else:
        __LOCAL_PATH = GLib.getenv("XDG_DATA_HOME") + "/eolie"
    DB_PATH = "%s/extensions.db" % __LOCAL_PATH

    # SQLite documentation:
    # In SQLite, a column with type INTEGER PRIMARY KEY
    # is an alias for the ROWID.
    # Here, we define an id INT PRIMARY KEY but never feed it,
    # this make VACUUM not destroy rowids...
    __create_passwords = '''CREATE TABLE passwords (
                                               id INTEGER PRIMARY KEY,
                                               uri TEXT NOT NULL,
                                               name TEXT NOT NULL
                                               )'''

    def __init__(self):
        """
            Create database tables or manage update if needed
        """
        self.__cancellable = Gio.Cancellable.new()
        f = Gio.File.new_for_path(self.DB_PATH)
        # Lazy loading if not empty
        if not f.query_exists():
            try:
                d = Gio.File.new_for_path(self.__LOCAL_PATH)
                if not d.query_exists():
                    d.make_directory_with_parents()
                # Create db schema
                with SqlCursor(self) as sql:
                    sql.execute(self.__create_passwords)
                    sql.commit()
            except Exception as e:
                print("DatabaseExtensions::__init__(): %s" % e)

    def add_password(self, uri, name):
        """
            Add an exception
            @param uri as str
            @param name as str
        """
        uri = strip_uri(uri)
        try:
            with SqlCursor(self) as sql:
                result = sql.execute("SELECT rowid FROM passwords\
                                      WHERE uri=?", (uri,))
                v = result.fetchone()
                if v is not None:
                    sql.execute("UPDATE passwords SET\
                                 name=? WHERE uri=?", (name, uri))
                else:
                    sql.execute("INSERT INTO passwords (uri, name)\
                                 VALUES (?, ?)", (uri, name))
                sql.commit()
        except:
            pass

    def remove_password(self, uri):
        """
            Remove password
            @param uri as str
        """
        uri = strip_uri(uri)
        try:
            with SqlCursor(self) as sql:
                sql.execute("DELETE FROM passwords\
                             WHERE uri=?", (uri,))
                sql.commit()
        except:
            pass

    def clear_passwords(self):
        """
            Clear all passwords
        """
        try:
            with SqlCursor(self) as sql:
                sql.execute("DELETE FROM passwords")
                sql.commit()
        except:
            pass

    def get_password_input_name(self, uri):
        """
            Return password input name for uri
            @param uri as str
            @return str/None
        """
        uri = strip_uri(uri)
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT name FROM passwords\
                                  WHERE uri=?", (uri,))
            v = result.fetchone()
            if v is not None:
                return v[0]
            return None

    def get_cursor(self):
        """
            Return a new sqlite cursor
        """
        try:
            c = sqlite3.connect(self.DB_PATH, 600.0)
            return c
        except Exception as e:
            print(e)
            exit(-1)
