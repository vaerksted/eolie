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

from gi.repository import Soup, Gio

import sqlite3
from time import time
from threading import Thread
import json

from eolie.sqlcursor import SqlCursor
from eolie.define import EOLIE_LOCAL_PATH


class DatabasePhishing:
    """
        Phishing database
    """
    DB_PATH = "%s/phishing.db" % EOLIE_LOCAL_PATH
    __URI = "http://data.phishtank.com/data/online-valid.json"
    # SQLite documentation:
    # In SQLite, a column with type INTEGER PRIMARY KEY
    # is an alias for the ROWID.
    # Here, we define an id INT PRIMARY KEY but never feed it,
    # this make VACUUM not destroy rowids...
    __create_pishinbg = '''CREATE TABLE phishing (
                                               id INTEGER PRIMARY KEY,
                                               uri TEXT NOT NULL,
                                               mtime INT NOT NULL
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
                d = Gio.File.new_for_path(EOLIE_LOCAL_PATH)
                if not d.query_exists():
                    d.make_directory_with_parents()
                # Create db schema
                with SqlCursor(self) as sql:
                    sql.execute(self.__create_pishinbg)
                    sql.commit()
            except Exception as e:
                print("DatabasePhishing::__init__(): %s" % e)

    def update(self):
        """
            Update database
        """
        # Get in db mtime
        # Only update if filters older than one day
        mtime = 0
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT mtime FROM phishing LIMIT 1")
            v = result.fetchone()
            if v is not None:
                mtime = v[0]
        self.__mtime = int(time())
        if self.__mtime - mtime < 86400:
            return
        if Gio.NetworkMonitor.get_default().get_network_available():
            thread = Thread(target=self.__update)
            thread.daemon = True
            thread.start()

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
            print("DatabasePhishing::is_phishing():", e)
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
            c = sqlite3.connect(self.DB_PATH, 600.0)
            return c
        except Exception as e:
            print(e)
            exit(-1)

#######################
# PRIVATE             #
#######################
    def __update(self):
        """
            Update database
        """
        self.__cancellable.reset()
        try:
            SqlCursor.add(self)
            session = Soup.Session.new()
            request = session.request(self.__URI)
            stream = request.send(self.__cancellable)
            bytes = bytearray(0)
            buf = stream.read_bytes(1024, self.__cancellable).get_data()
            while buf:
                bytes += buf
                buf = stream.read_bytes(
                                       1024, self.__cancellable).get_data()
            stream.close()
            data = bytes.decode('utf-8')
            j = json.loads(data)
            with SqlCursor(self) as sql:
                count = 0
                for item in j:
                    if self.__cancellable.is_cancelled():
                        raise IOError("Cancelled")
                    sql.execute("INSERT INTO phishing\
                                 (uri, mtime) VALUES (?, ?)",
                                (item["url"].rstrip("/"), self.__mtime))
                    count += 1
                    if count == 1000:
                        sql.commit()
                        count = 0
                sql.commit()
            # Delete removed entries
            with SqlCursor(self) as sql:
                sql.execute("DELETE FROM phishing\
                             WHERE mtime!=?", (self.__mtime,))
            sql.commit()
            SqlCursor.remove(self)
        except Exception as e:
            print("DatabasePhishing::__update()", e)
