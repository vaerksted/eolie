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

from gi.repository import GLib

import sqlite3
from urllib.parse import urlparse
from threading import Lock

from eolie.sqlcursor import SqlCursor
from eolie.define import EOLIE_DATA_PATH
from eolie.logger import Logger


class DatabaseSettings:
    """
        Store various settings for webpage
    """
    __UPGRADES = {
        1: "ALTER TABLE settings ADD accept_tls INT NOT NULL DEFAULT 0",
    }

    # SQLite documentation:
    # In SQLite, a column with type INTEGER PRIMARY KEY
    # is an alias for the ROWID.
    # Here, we define an id INT PRIMARY KEY but never feed it,
    # this make VACUUM not destroy rowids...
    __create_settings = '''CREATE TABLE settings (
                                           id INTEGER PRIMARY KEY,
                                           uri TEXT NOT NULL,
                                           chooseruri TEXT,
                                           languages TEXT,
                                           profile TEXT,
                                           zoom INT,
                                           accept_tls INT NOT NULL DEFAULT 0,
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
        self.__DB_PATH = "%s/settings2.db" % EOLIE_DATA_PATH
        if not GLib.file_test(self.__DB_PATH, GLib.FileTest.IS_REGULAR):
            try:
                if not GLib.file_test(EOLIE_DATA_PATH, GLib.FileTest.IS_DIR):
                    GLib.mkdir_with_parents(EOLIE_DATA_PATH, 0o0750)
                # Create db schema
                with SqlCursor(self) as sql:
                    sql.execute(self.__create_settings)
                    sql.execute("PRAGMA user_version=%s" % new_version)
            except Exception as e:
                Logger.error("DatabaseSettings::__init__(): %s", e)
        # DB upgrade, TODO Make it generic between class
        version = 0
        with SqlCursor(self) as sql:
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

    def set_chooser_uri(self, chooseruri, uri):
        """
            Add an uri related to uri
            @param chooseruri as str
            @param uri as str
        """
        parsed = urlparse(uri)
        if parsed.scheme not in ["http", "https"]:
            return
        try:
            with SqlCursor(self) as sql:
                result = sql.execute("SELECT rowid FROM settings\
                                      WHERE uri=?", (parsed.netloc,))
                v = result.fetchone()
                if v is not None:
                    sql.execute("UPDATE settings\
                                 SET chooseruri=?\
                                 WHERE uri=?", (chooseruri, parsed.netloc))
                else:
                    sql.execute("INSERT INTO settings\
                                          (uri, chooseruri)\
                                          VALUES (?, ?)", (parsed.netloc,
                                                           chooseruri))
        except Exception as e:
            Logger.error("DatabaseSettings::set_chooser_uri(): %s", e)

    def get_chooser_uri(self, uri):
        """
            Get chooser uri for uri
            @param uri as str
            @return chooseruri as str/None
        """
        parsed = urlparse(uri)
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT chooseruri FROM settings\
                                  WHERE uri=?", (parsed.netloc,))
            v = result.fetchone()
            if v is not None:
                return v[0]
            return None

    def allow_geolocation(self, uri, b):
        """
            Allow geolocation for uri
            @param uri as str
            @param b as bool
        """
        parsed = urlparse(uri)
        if parsed.scheme not in ["http", "https"]:
            return
        try:
            with SqlCursor(self) as sql:
                result = sql.execute("SELECT rowid FROM settings\
                                      WHERE uri=?", (parsed.netloc,))
                v = result.fetchone()
                if v is not None:
                    sql.execute("UPDATE settings\
                                 SET geolocation=?\
                                 WHERE uri=?", (b, parsed.netloc))
                else:
                    sql.execute("INSERT INTO settings\
                                          (uri, geolocation)\
                                          VALUES (?, ?)", (b, parsed.netloc))
        except Exception as e:
            Logger.error("DatabaseSettings::allow_geolocation(): %s", e)

    def allowed_geolocation(self, uri):
        """
            Check if geolocation is allowed
            @param uri as str
            @return allowed as bool
        """
        parsed = urlparse(uri)
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT geolocation FROM settings\
                                  WHERE uri=?", (parsed.netloc,))
            v = result.fetchone()
            if v is not None:
                return v[0] == 1
            return False

    def set_accept_tls(self, uri, accept):
        """
            Accept TLS for uri
            @param uri as str
            @param accept as bool
        """
        parsed = urlparse(uri)
        if parsed.scheme != "https":
            return
        try:
            with SqlCursor(self) as sql:
                result = sql.execute("SELECT rowid FROM settings\
                                      WHERE uri=?", (parsed.netloc,))
                v = result.fetchone()
                if v is not None:
                    sql.execute("UPDATE settings\
                                 SET accept_tls=?\
                                 WHERE uri=?", (accept, parsed.netloc))
                else:
                    sql.execute("INSERT INTO settings\
                                          (uri, accept_tls)\
                                          VALUES (?, ?)", (parsed.netloc,
                                                           accept))
        except Exception as e:
            Logger.error("DatabaseSettings::set_accept_tls(): %s", e)

    def get_accept_tls(self, uri):
        """
            True if should accept tls for uri
            @param uri as str
            @return bool
        """
        parsed = urlparse(uri)
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT accept_tls FROM settings\
                                  WHERE uri=?", (parsed.netloc,))
            v = result.fetchone()
            if v is not None:
                return bool(v[0])
            return False

    def set_zoom(self, zoom, uri):
        """
            Set zoom for uri
            @param zoom as int
            @param uri as str
        """
        parsed = urlparse(uri)
        if parsed.scheme not in ["http", "https"]:
            return
        try:
            with SqlCursor(self) as sql:
                result = sql.execute("SELECT rowid FROM settings\
                                      WHERE uri=?", (parsed.netloc,))
                v = result.fetchone()
                if v is not None:
                    sql.execute("UPDATE settings\
                                 SET zoom=?\
                                 WHERE uri=?", (zoom, parsed.netloc))
                else:
                    sql.execute("INSERT INTO settings\
                                          (uri, zoom)\
                                          VALUES (?, ?)", (parsed.netloc,
                                                           zoom))
        except Exception as e:
            Logger.error("DatabaseSettings::set_zoom(): %s", e)

    def get_zoom(self, uri):
        """
            Get zoom for uri
            @param uri as str
            @return zoom as int/None
        """
        parsed = urlparse(uri)
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT zoom FROM settings\
                                  WHERE uri=?", (parsed.netloc,))
            v = result.fetchone()
            if v is not None:
                return v[0]
            return None

    def set_user_agent(self, user_agent, uri):
        """
            Set user agent for uri
            @param user_agent as str
            @param uri as str
        """
        parsed = urlparse(uri)
        if parsed.scheme not in ["http", "https"]:
            return
        try:
            with SqlCursor(self) as sql:
                result = sql.execute("SELECT rowid FROM settings\
                                      WHERE uri=?", (parsed.netloc,))
                v = result.fetchone()
                if v is not None:
                    sql.execute("UPDATE settings\
                                 SET user_agent=?\
                                 WHERE uri=?", (user_agent, parsed.netloc))
                else:
                    sql.execute("INSERT INTO settings\
                                          (uri, user_agent)\
                                          VALUES (?, ?)", (parsed.netloc,
                                                           user_agent))
        except Exception as e:
            Logger.error("DatabaseSettings::set_user_agent(): %s", e)

    def get_user_agent(self, uri):
        """
            Get user agent for uri
            @param uri as str
            @return user_agent as str
        """
        parsed = urlparse(uri)
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT user_agent FROM settings\
                                  WHERE uri=?", (parsed.netloc,))
            v = result.fetchone()
            if v is not None:
                return v[0] or ""
            return ""

    def set_profile(self, profile, uri):
        """
            Set profile for uri
            @param user_agent as str
            @param uri as str
        """
        parsed = urlparse(uri)
        if parsed.scheme not in ["http", "https"]:
            return
        try:
            with SqlCursor(self) as sql:
                result = sql.execute("SELECT rowid FROM settings\
                                      WHERE uri=?", (parsed.netloc,))
                v = result.fetchone()
                if v is not None:
                    sql.execute("UPDATE settings\
                                 SET profile=?\
                                 WHERE uri=?", (profile, parsed.netloc))
                else:
                    sql.execute("INSERT INTO settings\
                                          (uri, profile)\
                                          VALUES (?, ?)", (parsed.netloc,
                                                           profile))
        except Exception as e:
            Logger.error("DatabaseSettings::set_profile(): %s", e)

    def get_profile(self, uri):
        """
            Get profile for uri
            @param uri as str
            @return user_agent as str
        """
        parsed = urlparse(uri)
        if parsed.netloc:
            domain = ".".join(parsed.netloc.split(".")[-2:])
        else:
            return "default"
        with SqlCursor(self) as sql:
            filter = ("%" + domain + "%",)
            result = sql.execute("SELECT profile FROM settings\
                                  WHERE uri LIKE ?", filter)
            v = result.fetchone()
            if v is not None:
                return v[0] or "default"
            return "default"

    def remove_profile(self, profile):
        """
            Remove profile from settings
            @param profile as str
        """
        with SqlCursor(self) as sql:
            sql.execute("UPDATE settings SET profile=''\
                        WHERE profile=?", (profile,))

    def get_languages(self, uri):
        """
            Get languages for uri
            @param uri as str
            @return codes as [str]
            @raise if not found
        """
        parsed = urlparse(uri)
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT languages FROM settings\
                                  WHERE uri=?", (parsed.netloc,))
            v = result.fetchone()
            if v is not None:
                languages = v[0]
                if languages:
                    return languages.split(";")
                else:
                    return None
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
            with SqlCursor(self) as sql:
                codes = self.get_languages(uri)
                if codes is not None:
                    if code not in codes:
                        codes.append(code)
                    sql.execute("UPDATE settings\
                                 SET languages=?\
                                 WHERE uri=?", (";".join(codes),
                                                parsed.netloc))
                else:
                    sql.execute("INSERT INTO settings\
                                          (uri, languages)\
                                          VALUES (?, ?)", (parsed.netloc,
                                                           code))
        except Exception as e:
            Logger.error("DatabaseSettings::add_language(): %s", e)

    def remove_language(self, code, uri):
        """
            Remove language for uri
            @param code as str
            @param uri as str
        """
        parsed = urlparse(uri)
        codes = self.get_languages(uri)
        if codes is not None and code in codes:
            codes.remove(code)
            with SqlCursor(self) as sql:
                sql.execute("UPDATE settings\
                                 SET languages=?\
                                 WHERE uri=?", (";".join(codes),
                                                parsed.netloc))

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
