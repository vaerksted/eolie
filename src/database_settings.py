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
from urllib.parse import urlparse

from eolie.sqlcursor import SqlCursor
from eolie.define import EOLIE_LOCAL_PATH


class DatabaseSettings:
    """
        Store various settings for webpage
    """

    # SQLite documentation:
    # In SQLite, a column with type INTEGER PRIMARY KEY
    # is an alias for the ROWID.
    # Here, we define an id INT PRIMARY KEY but never feed it,
    # this make VACUUM not destroy rowids...
    __create_settings = '''CREATE TABLE settings (
                                               id INTEGER PRIMARY KEY,
                                               url TEXT NOT NULL,
                                               chooseruri TEXT,
                                               languages TEXT,
                                               zoom FLOAT
                                               )'''

    def __init__(self):
        """
            Create database tables or manage update if needed
            @param suffix as str
        """
        self.__DB_PATH = "%s/settings.db" % EOLIE_LOCAL_PATH
        f = Gio.File.new_for_path(self.__DB_PATH)
        if not f.query_exists():
            try:
                d = Gio.File.new_for_path(EOLIE_LOCAL_PATH)
                if not d.query_exists():
                    d.make_directory_with_parents()
                # Create db schema
                with SqlCursor(self) as sql:
                    sql.execute(self.__create_settings)
                    sql.commit()
            except Exception as e:
                print("DatabaseSettings::__init__(): %s" % e)

    def set_chooser_uri(self, chooseruri, url):
        """
            Add an uri related to url
            @param chooseruri as str
            @param url as str
        """
        parsed = urlparse(url)
        try:
            with SqlCursor(self) as sql:
                result = sql.execute("SELECT rowid FROM settings\
                                      WHERE url=?", (parsed.netloc,))
                v = result.fetchone()
                if v is not None:
                    sql.execute("UPDATE settings\
                                 SET chooseruri=?\
                                 WHERE url=?", (chooseruri, parsed.netloc))
                else:
                    print(parsed.netloc, chooseruri, "plop")
                    sql.execute("INSERT INTO settings\
                                          (url, chooseruri)\
                                          VALUES (?, ?)", (parsed.netloc,
                                                           chooseruri))
                sql.commit()
        except Exception as e:
            print("DatabaseFilechooser::set_chooser_uri():", e)

    def get_chooser_uri(self, url):
        """
            Get chooser uri for url
            @param url as str
            @return chooseruri as str/None
        """
        parsed = urlparse(url)
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT chooseruri FROM settings\
                                  WHERE url=?", (parsed.netloc,))
            v = result.fetchone()
            if v is not None:
                return v[0]
            return None

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
