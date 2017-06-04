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
import itertools
from threading import Lock

from eolie.utils import noaccents, get_random_string
from eolie.define import El, EOLIE_LOCAL_PATH
from eolie.localized import LocalizedCollation
from eolie.sqlcursor import SqlCursor


class DatabaseHistory:
    """
        Eolie history db
    """
    DB_PATH = "%s/history.db" % EOLIE_LOCAL_PATH

    __UPGRADES = {
        1: "ALTER TABLE history ADD opened INT NOT NULL DEFAULT 0"
    }

    # SQLite documentation:
    # In SQLite, a column with type INTEGER PRIMARY KEY
    # is an alias for the ROWID.
    # Here, we define an id INT PRIMARY KEY but never feed it,
    # this make VACUUM not destroy rowids...
    __create_history = '''CREATE TABLE history (
                                               id INTEGER PRIMARY KEY,
                                               title TEXT NOT NULL,
                                               uri TEXT NOT NULL,
                                               guid TEXT NOT NULL,
                                               mtime REAL NOT NULL,
                                               opened INT NOT NULL DEFAULT 0,
                                               popularity INT NOT NULL
                                               )'''
    __create_history_atime = '''CREATE TABLE history_atime (
                                                history_id INT NOT NULL,
                                                atime REAL NOT NULL
                                               )'''

    def __init__(self):
        """
            Create database tables or manage update if needed
        """
        new_version = len(self.__UPGRADES)
        self.thread_lock = Lock()
        f = Gio.File.new_for_path(self.DB_PATH)
        if not f.query_exists():
            try:
                d = Gio.File.new_for_path(EOLIE_LOCAL_PATH)
                if not d.query_exists():
                    d.make_directory_with_parents()
                # Create db schema
                with SqlCursor(self) as sql:
                    sql.execute(self.__create_history)
                    sql.execute(self.__create_history_atime)
                    sql.execute("PRAGMA user_version=%s" % new_version)
                    sql.commit()
            except Exception as e:
                print("DatabaseHistory::__init__(): %s" % e)
        # DB upgrade
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
                        print("History DB upgrade %s failed" % i)
                sql.execute("PRAGMA user_version=%s" % new_version)
                sql.commit()

    def add(self, title, uri, mtime, guid=None, atimes=[], commit=True):
        """
            Add a new entry to history, if exists, update it
            @param title as str
            @param uri as str
            @param mtime as int
            @parma guid as str
            @param atime as [int]
            @param commit as bool
            @return history id as int
        """
        if not uri:
            return
        uri = uri.rstrip('/')
        if title is None:
            title = ""
        # No guid provided, first search in bookmarks
        # Then in history. Db may be broken and contains multiple guid
        # for same uri
        if guid is None:
            bookmark_id = El().bookmarks.get_id(uri)
            if bookmark_id is not None:
                guid = El().bookmarks.get_guid(bookmark_id)
            else:
                history_id = El().history.get_id(uri)
                guid = El().history.get_guid(history_id)
        # Find an uniq guid if none exists in db
        while guid is None:
            guid = get_random_string(12)
            if self.exists_guid(guid):
                guid = None
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT rowid, popularity FROM history\
                                  WHERE guid=?", (guid,))
            v = result.fetchone()
            if v is not None:
                history_id = v[0]
                sql.execute("UPDATE history\
                             SET uri=?, mtime=?, title=?, popularity=?\
                             WHERE rowid=?", (uri, mtime, title,
                                              v[1]+1, history_id))
            else:
                result = sql.execute("INSERT INTO history\
                                      (title, uri, mtime, popularity, guid)\
                                      VALUES (?, ?, ?, ?, ?)",
                                     (title, uri, mtime, 0, guid))
                history_id = result.lastrowid
            # Only add new atimes to db
            if not atimes:
                atimes = [mtime]
            current_atimes = self.get_atimes(history_id)
            for atime in atimes:
                if atime not in current_atimes:
                    sql.execute("INSERT INTO history_atime\
                                 (history_id, atime)\
                                 VALUES (?, ?)", (history_id, atime))
            if commit:
                sql.commit()
            return history_id

    def remove(self, history_id):
        """
            Remove item from history
            @param history id as int
        """
        with SqlCursor(self) as sql:
            sql.execute("DELETE from history\
                         WHERE rowid=?", (history_id,))
            sql.commit()

    def clear(self, atime):
        """
            Clear history from atime
            @param atime as int
            @return modified history ids as [int]
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT DISTINCT history.rowid\
                                  FROM history, history_atime\
                                  WHERE history_atime.history_id=history.rowid\
                                  AND atime >= ?", (atime,))
            items = list(itertools.chain(*result))
            sql.execute("DELETE FROM history_atime\
                         WHERE atime >= ?", (atime,))
            sql.commit()
            return items

    def get_empties(self):
        """
            Get empties history entries (without atime)
            @return history ids as [int]
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT history.rowid FROM history\
                                  WHERE NOT EXISTS (\
                                    SELECT rowid FROM history_atime AS ha\
                                    WHERE ha.history_id=history.rowid)")
            return list(itertools.chain(*result))

    def get(self, atime):
        """
            Get history for atime (current day)
            @param atime as int
            @return (str, str, int)
        """
        one_day = 86400
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT history.rowid, title, uri, atime\
                                  FROM history, history_atime\
                                  WHERE history.rowid=history_atime.history_id\
                                  AND atime >= ? AND atime <= ?\
                                  ORDER BY atime DESC",
                                 (atime, atime + one_day))
            return list(result)

    def get_id(self, uri):
        """
            Get history id
            @param uri as str
            @return history_id as int
        """
        with SqlCursor(self) as sql:
            uri = uri.rstrip('/')
            result = sql.execute("SELECT rowid\
                                  FROM history\
                                  WHERE uri=?",
                                 (uri,))
            v = result.fetchone()
            if v is not None:
                return v[0]
            return None

    def get_title(self, history_id):
        """
            Get history title
            @param history_id as int
            @return title as str
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT title\
                                  FROM history\
                                  WHERE rowid=?", (history_id,))
            v = result.fetchone()
            if v is not None:
                return v[0]
            return ""

    def get_uri(self, history_id):
        """
            Get history uri
            @param history_id as int
            @return uri as str
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT uri\
                                  FROM history\
                                  WHERE rowid=?", (history_id,))
            v = result.fetchone()
            if v is not None:
                return v[0]
            return ""

    def get_guid(self, history_id):
        """
            Get history item guid
            @param history_id as int
            @return guid as str
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT guid\
                                  FROM history\
                                  WHERE rowid=?", (history_id,))
            v = result.fetchone()
            if v is not None:
                return v[0]
            return None

    def get_mtime(self, history_id):
        """
            Get history mtime
            @param history_id as int
            @return mtime as int
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT mtime\
                                  FROM history\
                                  WHERE rowid=?", (history_id,))
            v = result.fetchone()
            if v is not None:
                return v[0]
            return 0

    def get_atimes(self, history_id):
        """
            Get history access times
            @param history_id as int
            @return [int]
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT atime\
                                  FROM history_atime\
                                  WHERE history_id=?", (history_id,))
            return list(itertools.chain(*result))

    def get_id_by_guid(self, guid):
        """
            Get id for guid
            @param guid as str
            @return id as int
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT rowid\
                                  FROM history\
                                  WHERE guid=?", (guid,))
            v = result.fetchone()
            if v is not None:
                return v[0]
            return None

    def get_ids_for_mtime(self, mtime):
        """
            Get ids that need to be synced related to mtime
            @param mtime as int
            @return [int]
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT rowid\
                                  FROM history\
                                  WHERE mtime > ?", (mtime,))
            return list(itertools.chain(*result))

    def set_title(self, history_id, title, commit=True):
        """
            Set history title
            @param history_id as int
            @param title as str
            @param commit as bool
        """
        with SqlCursor(self) as sql:
            sql.execute("UPDATE history\
                         SET title=?\
                         WHERE rowid=?", (title, history_id,))
            if commit:
                sql.commit()

    def get_opened_pages(self):
        """
            Get page with opened state
            @return [(uri, title)]
        """
        with SqlCursor(self) as sql:
            try:
                result = sql.execute("SELECT uri, title\
                                      FROM history\
                                      WHERE opened=1")
                return list(result)
            finally:
                sql.execute("UPDATE history\
                             SET opened=0\
                             WHERE opened=1")
                sql.commit()

    def set_page_state(self, uri, mtime=None):
        """
            Mark page with uri as opened if mtime is not None
            @param uri as str
            @param mtime as double
        """
        if uri is None:
            return
        uri = uri.rstrip('/')
        with SqlCursor(self) as sql:
            if mtime is None:
                sql.execute("UPDATE history\
                             SET opened=0\
                             WHERE uri=?\
                             AND opened=1", (uri,))
            else:
                sql.execute("UPDATE history\
                             SET opened=1 WHERE uri=?\
                             AND mtime=?", (uri, mtime))
            sql.commit()

    def set_atimes(self, history_id, atimes, commit=True):
        """
            Set history atime
            @param history_id as int
            @param atimes as [int]
            @param commit as bool
        """
        with SqlCursor(self) as sql:
            current_atimes = self.get_atimes(history_id)
            for atime in atimes:
                if atime not in current_atimes:
                    sql.execute("INSERT INTO history_atime (history_id, atime)\
                                 VALUES (?, ?)", (history_id, atime))
            if commit:
                sql.commit()

    def set_mtime(self, history_id, mtime, commit=True):
        """
            Set history mtime
            @param history_id as int
            @param mtime as int
            @param commit as bool
        """
        with SqlCursor(self) as sql:
            sql.execute("UPDATE history\
                         SET mtime=? where rowid=?", (mtime, history_id))
            if commit:
                sql.commit()

    def search(self, search, limit):
        """
            Search string in db (uri and title)
            @param search as str
            @param limit as int
            @return [(id, title, uri)] as [(int, str, str)]
        """
        with SqlCursor(self) as sql:
            filter = '%' + search + '%'
            result = sql.execute("SELECT rowid, title, uri\
                                  FROM history\
                                  WHERE title LIKE ?\
                                   OR uri LIKE ?\
                                  ORDER BY popularity DESC,\
                                  mtime DESC LIMIT ?",
                                 (filter, filter, limit))
            return list(result)

    def exists_guid(self, guid):
        """
            Check if guid exists in db
            @return bool
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT guid FROM history\
                                  WHERE guid=?", (guid,))
            v = result.fetchone()
            return v is not None

    def get_cursor(self):
        """
            Return a new sqlite cursor
        """
        try:
            c = sqlite3.connect(self.DB_PATH, 600.0)
            c.create_collation('LOCALIZED', LocalizedCollation())
            c.create_function("noaccents", 1, noaccents)
            return c
        except:
            exit(-1)

    def drop_db(self):
        """
            Drop database
        """
        try:
            f = Gio.File.new_for_path(self.DB_PATH)
            f.trash()
        except Exception as e:
            print("DatabaseHistory::drop_db():", e)

#######################
# PRIVATE             #
#######################
