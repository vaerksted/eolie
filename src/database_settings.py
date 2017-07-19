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
    __UPGRADES = {
        1: "ALTER TABLE settings ADD geolocation INT"
    }

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
                                               zoom INT,
                                               geolocation INT
                                               )'''

    def __init__(self):
        """
            Create database tables or manage update if needed
            @param suffix as str
        """
        new_version = len(self.__UPGRADES)
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
                    sql.execute("PRAGMA user_version=%s" % new_version)
                    sql.commit()
            except Exception as e:
                print("DatabaseSettings::__init__(): %s" % e)
        # DB upgrade, TODO Make it generic between class
        version = 0
        with SqlCursor(self) as sql:
            result = sql.execute("PRAGMA user_version")
            v = result.fetchone()
            if v is not None:
                version = v[0]
            if version < new_version:
                for i in range(version+1, new_version + 1):
                    try:
                        sql.execute(self.__UPGRADES[i])
                    except:
                        print("Settings DB upgrade %s failed" % i)
                sql.execute("PRAGMA user_version=%s" % new_version)
                sql.commit()

    def set_chooser_uri(self, chooseruri, url):
        """
            Add an uri related to url
            @param chooseruri as str
            @param url as str
        """
        parsed = urlparse(url)
        if parsed.scheme not in ["http", "https"]:
            return
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
                    sql.execute("INSERT INTO settings\
                                          (url, chooseruri)\
                                          VALUES (?, ?)", (parsed.netloc,
                                                           chooseruri))
                sql.commit()
        except Exception as e:
            print("DatabaseSettings::set_chooser_uri():", e)

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

    def allow_geolocation(self, url, b):
        """
            Allow geolocation for url
            @param url as str
            @param b as bool
        """
        parsed = urlparse(url)
        if parsed.scheme not in ["http", "https"]:
            return
        try:
            with SqlCursor(self) as sql:
                result = sql.execute("SELECT rowid FROM settings\
                                      WHERE url=?", (parsed.netloc,))
                v = result.fetchone()
                if v is not None:
                    sql.execute("UPDATE settings\
                                 SET geolocation=?\
                                 WHERE url=?", (b, parsed.netloc))
                else:
                    sql.execute("INSERT INTO settings\
                                          (url, geolocation)\
                                          VALUES (?, ?)", (b, parsed.netloc))
                sql.commit()
        except Exception as e:
            print("DatabaseSettings::allow_geolocation():", e)

    def allowed_geolocation(self, url):
        """
            Check if geolocation is allowed
            @param url as str
            @return allowed as bool
        """
        parsed = urlparse(url)
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT geolocation FROM settings\
                                  WHERE url=?", (parsed.netloc,))
            v = result.fetchone()
            if v is not None:
                return v[0] == 1
            return False

    def set_zoom(self, zoom, url):
        """
            Set zoom for url
            @param zoom as int
            @param url as str
        """
        parsed = urlparse(url)
        if parsed.scheme not in ["http", "https"]:
            return
        try:
            with SqlCursor(self) as sql:
                result = sql.execute("SELECT rowid FROM settings\
                                      WHERE url=?", (parsed.netloc,))
                v = result.fetchone()
                if v is not None:
                    sql.execute("UPDATE settings\
                                 SET zoom=?\
                                 WHERE url=?", (zoom, parsed.netloc))
                else:
                    sql.execute("INSERT INTO settings\
                                          (url, zoom)\
                                          VALUES (?, ?)", (parsed.netloc,
                                                           zoom))
                sql.commit()
        except Exception as e:
            print("DatabaseSettings::set_zoom():", e)

    def get_zoom(self, url):
        """
            Get zoom for url
            @param url as str
            @return zoom as int/None
        """
        parsed = urlparse(url)
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT zoom FROM settings\
                                  WHERE url=?", (parsed.netloc,))
            v = result.fetchone()
            if v is not None:
                return v[0]
            return None

    def get_languages(self, url):
        """
            Get languages for url
            @param url as str
            @return codes as [str]
            @raise if not found
        """
        parsed = urlparse(url)
        with SqlCursor(self) as sql:
                result = sql.execute("SELECT languages FROM settings\
                                      WHERE url=?", (parsed.netloc,))
                v = result.fetchone()
                if v is not None:
                    languages = v[0]
                    if languages:
                        return languages.split(";")
                    else:
                        return []
                else:
                    return None

    def add_language(self, code, url):
        """
            Add language for url
            @param code as str
            @param url as str
        """
        parsed = urlparse(url)
        if parsed.scheme not in ["http", "https"]:
            return
        try:
            with SqlCursor(self) as sql:
                codes = self.get_languages(url)
                if codes is not None:
                    if code not in codes:
                        codes.append(code)
                    sql.execute("UPDATE settings\
                                 SET languages=?\
                                 WHERE url=?", (";".join(codes),
                                                parsed.netloc))
                else:
                    sql.execute("INSERT INTO settings\
                                          (url, languages)\
                                          VALUES (?, ?)", (parsed.netloc,
                                                           code))
                sql.commit()
        except Exception as e:
            print("DatabaseSettings::add_language():", e)

    def remove_language(self, code, url):
        """
            Remove language for url
            @param code as str
            @param url as str
        """
        parsed = urlparse(url)
        codes = self.get_languages(url)
        if codes is not None and code in codes:
            codes.remove(code)
            with SqlCursor(self) as sql:
                sql.execute("UPDATE settings\
                                 SET languages=?\
                                 WHERE url=?", (";".join(codes),
                                                parsed.netloc))
                sql.commit()

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
