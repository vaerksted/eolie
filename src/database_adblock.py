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

from gi.repository import Soup, Gio, GLib

from urllib.parse import urlparse
import sqlite3
from gettext import gettext as _
from time import time
from threading import Thread

from eolie.sqlcursor import SqlCursor
from eolie.define import EOLIE_LOCAL_PATH, ADBLOCK_JS


class DatabaseAdblock:
    """
        Eolie adblock db
    """
    DB_PATH = "%s/adblock.db" % EOLIE_LOCAL_PATH

    __URIS = ["https://adaway.org/hosts.txt",
              "http://winhelp2002.mvps.org/hosts.txt",
              "http://hosts-file.net/ad_servers.txt",
              "https://pgl.yoyo.org/adservers/serverlist.php?"
              "hostformat=hosts&showintro=0&mimetype=plaintext"]

    # SQLite documentation:
    # In SQLite, a column with type INTEGER PRIMARY KEY
    # is an alias for the ROWID.
    # Here, we define an id INT PRIMARY KEY but never feed it,
    # this make VACUUM not destroy rowids...
    __create_adblock = '''CREATE TABLE adblock (
                                               id INTEGER PRIMARY KEY,
                                               dns TEXT NOT NULL,
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
                    sql.execute(self.__create_adblock)
                    sql.commit()
            except Exception as e:
                print("DatabaseAdblock::__init__(): %s" % e)

    def update(self):
        """
            Update database
        """
        if not Gio.NetworkMonitor.get_default().get_network_available():
            return
        # Update adblock_js repo
        git = GLib.find_program_in_path("git")
        if git is None:
            print(_("For stronger ad blocking, install git command"))
        else:
            d = Gio.File.new_for_path(ADBLOCK_JS)
            if d.query_exists():
                argv = [git,
                        "-C",
                        ADBLOCK_JS,
                        "pull"]
            else:
                argv = [git,
                        "clone",
                        "https://github.com/gnumdk/eolie-adblock.git",
                        ADBLOCK_JS]
            (pid, a1, a2, a3) = GLib.spawn_async(
                                    argv,
                                    flags=GLib.SpawnFlags.STDOUT_TO_DEV_NULL)
            GLib.spawn_close_pid(pid)

        # Get in db mtime
        # Only update if filters older than one week
        mtime = 0
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT mtime FROM adblock LIMIT 1")
            v = result.fetchone()
            if v is not None:
                mtime = v[0]
        self.__mtime = int(time())
        if self.__mtime - mtime < 604800:
            return
        # Update adblock db
        thread = Thread(target=self.__update)
        thread.daemon = True
        thread.start()

    def stop(self):
        """
            Stop update
        """
        self.__cancellable.cancel()

    def is_blocked(self, uri):
        """
            Return True if uri is blocked
            @param uri as str
            @return bool
        """
        try:
            parse = urlparse(uri)
            with SqlCursor(self) as sql:
                result = sql.execute("SELECT mtime FROM adblock\
                                      WHERE dns=?", (parse.netloc,))
                v = result.fetchone()
                return v is not None
        except Exception as e:
            print("DatabaseAdblock::is_blocked():", e)
            return False

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
        SqlCursor.add(self)
        result = ""
        try:
            for uri in self.__URIS:
                session = Soup.Session.new()
                request = session.request(uri)
                stream = request.send(self.__cancellable)
                bytes = bytearray(0)
                buf = stream.read_bytes(1024, self.__cancellable).get_data()
                while buf:
                    bytes += buf
                    buf = stream.read_bytes(
                                           1024, self.__cancellable).get_data()
                stream.close()
                result = bytes.decode('utf-8')
                count = 0
                for line in result.split('\n'):
                    if self.__cancellable.is_cancelled():
                        raise IOError("Cancelled")
                    if line.startswith('#'):
                        continue
                    array = line.replace(
                                 ' ', '\t', 1).replace('\t', '@', 1).split('@')
                    if len(array) <= 1:
                        continue
                    dns = array[1].replace(
                                       ' ', '').replace('\r', '').split('#')[0]
                    # Update entry if exists, create else
                    with SqlCursor(self) as sql:
                        sql.execute("INSERT INTO adblock\
                                          (dns, mtime)\
                                          VALUES (?, ?)",
                                    (dns, self.__mtime))
                        count += 1
                        if count == 1000:
                            sql.commit()
                            count = 0
            # Delete removed entries
            with SqlCursor(self) as sql:
                sql.execute("DELETE FROM adblock\
                             WHERE mtime!=?", (self.__mtime,))
        except Exception as e:
            print("DatabaseAdlbock:__update():", e)
        with SqlCursor(self) as sql:
            sql.commit()
        SqlCursor.remove(self)
