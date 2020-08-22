# Copyright (c) 2017-2020 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from gi.repository import GLib, Gio

import sqlite3
import itertools
from urllib.parse import urlparse
from threading import Lock

from eolie.utils import noaccents, get_random_string
from eolie.define import EOLIE_DATA_PATH, Type
from eolie.localized import LocalizedCollation
from eolie.sqlcursor import SqlCursor
from eolie.logger import Logger
from eolie.database_upgrade import DatabaseUpgrade


class DatabaseBookmarks:
    """
        Eolie bookmarks db
    """

    DB_PATH = "%s/bookmarks.db" % EOLIE_DATA_PATH

    # SQLite documentation:
    # In SQLite, a column with type INTEGER PRIMARY KEY
    # is an alias for the ROWID.
    # Here, we define an id INT PRIMARY KEY but never feed it,
    # this make VACUUM not destroy rowids...
    __create_bookmarks = '''CREATE TABLE bookmarks (
                                               id INTEGER PRIMARY KEY,
                                               title TEXT NOT NULL,
                                               uri TEXT NOT NULL,
                                               popularity INT NOT NULL,
                                               atime REAL NOT NULL,
                                               guid TEXT NOT NULL,
                                               mtime REAL NOT NULL,
                                               position INT DEFAULT 0,
                                               startup INT DEFAULT 0
                                               )'''
    __create_tags = '''CREATE TABLE tags (id INTEGER PRIMARY KEY,
                                          title TEXT NOT NULL)'''
    __create_bookmarks_tags = '''CREATE TABLE bookmarks_tags (
                                                    id INTEGER PRIMARY KEY,
                                                    bookmark_id INT NOT NULL,
                                                    tag_id INT NOT NULL)'''
    # Only useful for Firefox compatibility
    __create_parents = '''CREATE TABLE parents (
                                        id INTEGER PRIMARY KEY,
                                        bookmark_id INT NOT NULL,
                                        parent_guid TEXT NOT NULL,
                                        parent_name TEXT NOT NULL)'''

    def __init__(self):
        """
            Create database tables or manage update if needed
        """
        upgrade = DatabaseUpgrade(Type.BOOKMARK)
        self.thread_lock = Lock()
        if not GLib.file_test(self.DB_PATH, GLib.FileTest.IS_REGULAR):
            try:
                if not GLib.file_test(EOLIE_DATA_PATH, GLib.FileTest.IS_DIR):
                    GLib.mkdir_with_parents(EOLIE_DATA_PATH, 0o0750)
                # Create db schema
                with SqlCursor(self, True) as sql:
                    sql.execute(self.__create_bookmarks)
                    sql.execute(self.__create_tags)
                    sql.execute(self.__create_bookmarks_tags)
                    sql.execute(self.__create_parents)
                    sql.execute("PRAGMA user_version=%s" % upgrade.version)
            except Exception as e:
                Logger.error("DatabaseBookmarks::__init__(): %s", e)
        else:
            upgrade.upgrade(self)

    def add(self, title, uri, guid, tags, atime=0):
        """
            Add a new bookmark
            @param title as str
            @param uri as str
            @param guid as str
            @param tags as [str]
            @param parent_guid as str
            @param ctime as int
            @return bookmark id as int
        """
        # Find an uniq guid
        while guid is None:
            guid = get_random_string(12)
            if self.exists_guid(guid):
                guid = None

        with SqlCursor(self, True) as sql:
            result = sql.execute("INSERT INTO bookmarks\
                                  (title, uri, popularity, guid, atime, mtime)\
                                  VALUES (?, ?, ?, ?, ?, ?)",
                                 (title, uri.rstrip('/'), 0, guid, atime, 0))
            bookmarks_id = result.lastrowid
            for tag in tags:
                if not tag:
                    continue
                tag_id = self.get_tag_id(tag)
                if tag_id is None:
                    tag_id = self.add_tag(tag)
                sql.execute("INSERT INTO bookmarks_tags\
                             (bookmark_id, tag_id) VALUES (?, ?)",
                            (bookmarks_id, tag_id))
            return bookmarks_id

    def remove(self, bookmark_id):
        """
            Remove bookmark from db
            @param bookmark id as int
        """
        with SqlCursor(self, True) as sql:
            sql.execute("DELETE FROM bookmarks\
                         WHERE rowid=?", (bookmark_id,))
            sql.execute("DELETE FROM bookmarks_tags\
                         WHERE bookmark_id=?", (bookmark_id,))
            sql.execute("DELETE FROM parents\
                         WHERE bookmark_id=?", (bookmark_id,))

    def add_tag(self, tag):
        """
            Add tag to db, return existing if exists
            @param tag as str
            @return tag id as int
        """
        with SqlCursor(self, True) as sql:
            result = sql.execute("INSERT INTO tags\
                                  (title) VALUES (?)",
                                 (tag,))
            return result.lastrowid

    def del_tag(self, tag):
        """
            Add tag to db, return existing if exists
            @param tag as str
        """
        with SqlCursor(self, True) as sql:
            tag_id = self.get_tag_id(tag)
            if tag_id is None:
                return
            sql.execute("DELETE FROM tags\
                         WHERE rowid=?", (tag_id,))
            sql.execute("DELETE FROM bookmarks_tags\
                         WHERE tag_id=?", (tag_id,))

    def rename_tag(self, old, new):
        """
            Rename tag
            @param old as str
            @param new as str
        """
        with SqlCursor(self, True) as sql:
            sql.execute("UPDATE tags set title=? WHERE title=?", (new, old))

    def get_tags(self, bookmark_id):
        """
            Get tags for bookmark id
            @param bookmark id as int
            @return [str]
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT tags.title\
                                  FROM tags, bookmarks_tags\
                                  WHERE bookmarks_tags.bookmark_id=?\
                                  AND bookmarks_tags.tag_id=tags.rowid\
                                  ORDER BY title COLLATE LOCALIZED",
                                 (bookmark_id,))
            return list(itertools.chain(*result))

    def has_tag(self, bookmark_id, tag):
        """
            Return True if bookmark id as tag
            @param bookmark id as int
            @param tag as str
            @return bool
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT tags.rowid\
                                  FROM tags, bookmarks_tags\
                                  WHERE tags.title=? COLLATE NOCASE\
                                  AND bookmarks_tags.bookmark_id=?\
                                  AND bookmarks_tags.tag_id=tags.rowid",
                                 (tag, bookmark_id))
            v = result.fetchone()
            if v is not None:
                return True
            return False

    def get_id(self, uri):
        """
            Get id for uri
            @param uri as str
            @return id as int
        """
        if uri is None:
            return None
        with SqlCursor(self) as sql:
            parsed = urlparse(uri.rstrip('/'))
            if not parsed.netloc:
                return None
            search = "%{}{}%".format(parsed.netloc, parsed.path)
            result = sql.execute("SELECT rowid\
                                  FROM bookmarks\
                                  WHERE uri like ?", (search,))
            v = result.fetchone()
            if v is not None:
                return v[0]
            return None

    def get_id_by_guid(self, guid):
        """
            Get id for guid
            @param guid as str
            @return id as int
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT rowid\
                                  FROM bookmarks\
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
                                  FROM bookmarks\
                                  WHERE mtime > ?\
                                  AND uri != guid", (mtime,))
            return list(itertools.chain(*result))

    def get_parent_guid(self, bookmark_id):
        """
            Get parent for bookmark
            @param bookmark id as int
            @return guid as str
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT parent_guid\
                                  FROM parents\
                                  WHERE bookmark_id=?", (bookmark_id,))
            v = result.fetchone()
            if v is not None and v[0] is not None:
                return v[0]
            return "unfiled"

    def get_parent_name(self, bookmark_id):
        """
            Get parent for bookmark
            @param bookmark id as int
            @return name as str
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT parent_name\
                                  FROM parents\
                                  WHERE bookmark_id=?", (bookmark_id,))
            v = result.fetchone()
            if v is not None and v[0] is not None:
                return v[0]
            return ""

    def get_title(self, bookmark_id):
        """
            Get bookmark title
            @param bookmark id as int
            @return title as str
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT title\
                                  FROM bookmarks\
                                  WHERE rowid=?", (bookmark_id,))
            v = result.fetchone()
            if v is not None:
                return v[0]
            return ""

    def get_uri(self, bookmark_id):
        """
            Get bookmark uri
            @param bookmark id as int
            @return uri as str
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT uri\
                                  FROM bookmarks\
                                  WHERE rowid=?", (bookmark_id,))
            v = result.fetchone()
            if v is not None:
                return v[0]
            return ""

    def get_guid(self, bookmark_id):
        """
            Get bookmark guid
            @param bookmark id as int
            @return guid as str
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT guid\
                                  FROM bookmarks\
                                  WHERE rowid=?", (bookmark_id,))
            v = result.fetchone()
            if v is not None:
                return v[0]
            return None

    def get_guids(self):
        """
            Get all guids
            @return guids as [str]
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT guid FROM bookmarks")
            return list(itertools.chain(*result))

    def get_children(self, guid):
        """
            Get guid children
            @param guid as str
            @return [str]
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT bookmarks.guid\
                                  FROM bookmarks, parents\
                                  WHERE parents.parent_guid=?\
                                  AND parents.bookmark_id=bookmarks.rowid\
                                  ORDER BY position ASC", (guid,))
            return list(itertools.chain(*result))

    def get_mtime(self, bookmark_id):
        """
            Get bookmark mtime
            @param bookmark id as int
            @return mtime as int
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT mtime\
                                  FROM bookmarks\
                                  WHERE rowid=?", (bookmark_id,))
            v = result.fetchone()
            if v is not None:
                return v[0]
            return 0

    def get_position(self, bookmark_id):
        """
            Get bookmark position
            @param bookmark id as int
            @return position as int
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT position\
                                  FROM bookmarks\
                                  WHERE rowid=?", (bookmark_id,))
            v = result.fetchone()
            if v is not None:
                return v[0]
            return 0

    def get_tag_id(self, title):
        """
            Get tag id
            @param title as str
            @return tag id as int
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT rowid\
                                  FROM tags\
                                  WHERE title=? COLLATE NOCASE", (title,))
            v = result.fetchone()
            if v is not None:
                return v[0]
            return None

    def get_tag_title(self, tag_id):
        """
            Get tag id title
            @param tag id as int
            @return title as str
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT tags.title\
                                  FROM tags\
                                  WHERE id=?", (tag_id,))
            v = result.fetchone()
            if v is not None:
                return v[0]
            return None

    def get_all_tags(self):
        """
            Get all tags
            @return [rowid, str]
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT rowid, title\
                                  FROM tags\
                                  ORDER BY title COLLATE LOCALIZED")
            return list(result)

    def get_bookmarks(self, tag_id=None):
        """
            Get all bookmarks
            @param tag id as int
            @return [(id, title, uri)]
        """
        with SqlCursor(self) as sql:
            if tag_id is None:
                result = sql.execute("\
                                SELECT bookmarks.rowid,\
                                       bookmarks.uri,\
                                       bookmarks.title\
                                FROM bookmarks\
                                ORDER BY bookmarks.popularity DESC")
            else:
                result = sql.execute("\
                                SELECT bookmarks.rowid,\
                                       bookmarks.uri,\
                                       bookmarks.title\
                                FROM bookmarks, bookmarks_tags\
                                WHERE bookmarks.rowid=\
                                      bookmarks_tags.bookmark_id\
                                      AND bookmarks_tags.tag_id=?\
                                      AND bookmarks.guid != bookmarks.uri\
                                ORDER BY bookmarks.popularity DESC", (tag_id,))
            return list(result)

    def get_populars(self, limit):
        """
            Get popular bookmarks
            @param limit as bool
            @return [(id, title, uri)]
        """
        with SqlCursor(self) as sql:
            result = sql.execute("\
                            SELECT bookmarks.rowid,\
                                   bookmarks.uri,\
                                   bookmarks.title\
                            FROM bookmarks\
                            WHERE popularity!=0\
                            AND bookmarks.guid != bookmarks.uri\
                            ORDER BY bookmarks.popularity DESC,\
                            bookmarks.atime DESC\
                            LIMIT ?", (limit,))
            return list(result)

    def get_unclassified(self):
        """
            Get bookmarks without tag
            @return [(id, title, uri)]
        """
        with SqlCursor(self) as sql:
            result = sql.execute("\
                            SELECT bookmarks.rowid,\
                                   bookmarks.uri,\
                                   bookmarks.title\
                            FROM bookmarks\
                            WHERE NOT EXISTS (\
                                SELECT bookmark_id FROM bookmarks_tags\
                                WHERE bookmark_id=bookmarks.rowid)\
                            AND bookmarks.guid != bookmarks.uri\
                            ORDER BY bookmarks.popularity DESC")
            return list(result)

    def get_recents(self):
        """
            Get recents bookmarks
            @return [(id, title, uri)]
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT bookmarks.rowid,\
                                  bookmarks.uri,\
                                  bookmarks.title\
                                  FROM bookmarks\
                                  WHERE bookmarks.guid != bookmarks.uri\
                                  ORDER BY bookmarks.mtime DESC")
            return list(result)

    def get_popularity(self, bookmark_id):
        """
            Get popularity for bookmark id
            @param bookmark_id as int
            @return popularity as int
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT popularity\
                                  FROM bookmarks\
                                  WHERE rowid=?", (bookmark_id,))
            v = result.fetchone()
            if v is not None:
                return v[0]
            return 0

    def get_higher_popularity(self):
        """
            Get higher available popularity
            @return int
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT popularity\
                                  FROM bookmarks\
                                  ORDER BY POPULARITY DESC LIMIT 1")
            v = result.fetchone()
            if v is not None:
                return v[0]
            return 0

    def get_avg_popularity(self):
        """
            Return avarage popularity
            @return avarage popularity as int
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT AVG(popularity)\
                                  FROM (SELECT popularity\
                                        FROM bookmarks\
                                        ORDER BY POPULARITY DESC LIMIT 100)")
            v = result.fetchone()
            if v and v[0] > 5:
                return v[0]
            return 5

    def get_startup(self, bookmark_id):
        """
            True if bookmark needs to be loaded at startup
            @param bookmark_id as int
            @return bool
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT startup\
                                  FROM bookmarks\
                                  WHERE rowid=?", (bookmark_id,))
            v = result.fetchone()
            if v is not None:
                return bool(v[0])
            return False

    def get_startup_uris(self):
        """
            Get URIS to load at startup
            @param bookmark_id as int
            @return [str]
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT uri FROM bookmarks\
                                  WHERE startup=1")
            return list(itertools.chain(*result))

    def set_guid(self, bookmark_id, guid):
        """
            Set bookmark guid
            @param bookmark_id as int
            @param guid as str
        """
        with SqlCursor(self, True) as sql:
            sql.execute("UPDATE bookmarks\
                         SET guid=?\
                         WHERE rowid=?", (bookmark_id, guid))

    def set_title(self, bookmark_id, title):
        """
            Set bookmark title
            @param bookmark id as int
            @param title as str
        """
        with SqlCursor(self, True) as sql:
            sql.execute("UPDATE bookmarks\
                         SET title=?\
                         WHERE rowid=?", (title, bookmark_id,))

    def set_uri(self, bookmark_id, uri):
        """
            Set bookmark uri
            @param bookmark id as int
            @param uri as str
        """
        with SqlCursor(self, True) as sql:
            sql.execute("UPDATE bookmarks\
                         SET uri=?\
                         WHERE rowid=?", (uri.rstrip('/'), bookmark_id,))

    def set_popularity(self, bookmark_id, popularity):
        """
            Set bookmark popularity
            @param bookmark id as int
            @param popularity as int
        """
        with SqlCursor(self, True) as sql:
            sql.execute("UPDATE bookmarks\
                         SET popularity=?\
                         WHERE rowid=?", (popularity, bookmark_id,))

    def set_startup(self, bookmark_id, startup):
        """
            Set bookmark startup value
            @param bookmark id as int
            @param startup as bool
        """
        with SqlCursor(self, True) as sql:
            sql.execute("UPDATE bookmarks\
                         SET startup=?\
                         WHERE rowid=?", (startup, bookmark_id,))

    def set_parent(self, bookmark_id, parent_guid, parent_name):
        """
            Set parent id for bookmark
            @param bookmark_id as int
            @param parent_guid as str
            @param parent_name as str
        """
        with SqlCursor(self, True) as sql:
            result = sql.execute("SELECT parent_guid\
                                  FROM parents\
                                  WHERE bookmark_id=?", (bookmark_id,))
            v = result.fetchone()
            if v is None or v[0] is None:
                sql.execute("INSERT INTO parents\
                             (bookmark_id, parent_guid, parent_name)\
                             VALUES (?, ?, ?)",
                            (bookmark_id, parent_guid, parent_name))
            else:
                sql.execute("UPDATE parents\
                             SET parent_guid=?, parent_name=?\
                             WHERE bookmark_id=?",
                            (parent_guid, parent_name, bookmark_id))

    def set_access_time(self, uri, atime):
        """
            Set bookmark access time
            @param uri as str
            @param atime as int
        """
        with SqlCursor(self, True) as sql:
            sql.execute("UPDATE bookmarks\
                         SET atime=? where uri=?", (atime, uri.rstrip('/')))

    def set_mtime(self, bookmark_id, mtime):
        """
            Set bookmark sync time
            @param bookmark id as int
            @param mtime as int
        """
        with SqlCursor(self, True) as sql:
            sql.execute("UPDATE bookmarks\
                         SET mtime=? where rowid=?", (mtime, bookmark_id))

    def set_position(self, bookmark_id, position):
        """
            Set bookmark position
            @param bookmark id as int
            @param mtime as int
        """
        with SqlCursor(self, True) as sql:
            sql.execute("UPDATE bookmarks\
                         SET position=? where rowid=?", (position,
                                                         bookmark_id))

    def get_match(self, uri, ssl_force=False):
        """
            Try to get best uri matching
            @parma uri as str
            @param ssl_force as bool
            @return str
        """
        with SqlCursor(self) as sql:
            if ssl_force:
                filter = ("https://%{}%".format(uri),)
            else:
                filter = ("http%://%{}%".format(uri),)
            result = sql.execute("SELECT uri\
                                  FROM bookmarks\
                                  WHERE uri like ?\
                                  ORDER BY length(uri) ASC\
                                  LIMIT 1", filter)
            v = result.fetchone()
            if v is not None:
                return v[0]
            return None

    def set_tag_title(self, tag_id, title):
        """
            Set tag id title
            @param tag id as int
            @parma title as str
        """
        with SqlCursor(self, True) as sql:
            sql.execute("UPDATE tags SET title=? WHERE id=?", (title, tag_id,))

    def set_more_popular(self, uri):
        """
            Increment bookmark popularity
            @param uri as str
        """
        with SqlCursor(self, True) as sql:
            uri = uri.rstrip('/')
            result = sql.execute("SELECT popularity FROM bookmarks\
                                  WHERE uri=?", (uri,))
            v = result.fetchone()
            if v is not None:
                sql.execute("UPDATE bookmarks set popularity=?\
                             WHERE uri=?", (v[0] + 1, uri))

    def add_tag_to(self, tag_id, bookmark_id):
        """
            Add tag to bookmark
            @param tag id as int
            @param bookmark id as int
        """
        with SqlCursor(self, True) as sql:
            sql.execute("INSERT INTO bookmarks_tags\
                         (bookmark_id, tag_id) VALUES (?, ?)",
                        (bookmark_id, tag_id))

    def del_tag_from(self, tag_id, bookmark_id):
        """
            Remove tag from bookmark
            @param tag id as int
            @param bookmark id as int
        """
        with SqlCursor(self, True) as sql:
            sql.execute("DELETE from bookmarks_tags\
                         WHERE bookmark_id=? and tag_id=?",
                        (bookmark_id, tag_id))

    def clean_tags(self):
        """
            Remove orphan tags
        """
        with SqlCursor(self, True) as sql:
            sql.execute("DELETE from tags\
                         WHERE NOT EXISTS (\
                            SELECT bookmarks_tags.rowid\
                            FROM bookmarks, bookmarks_tags\
                            WHERE tags.rowid = bookmarks_tags.tag_id\
                            AND bookmarks.rowid = bookmarks_tags.bookmark_id)")

    def reset_popularity(self, uri):
        """
            Reset popularity for uri
            @param uri as str
        """
        with SqlCursor(self, True) as sql:
            sql.execute("UPDATE bookmarks SET popularity=0 WHERE uri=?",
                        (uri,))

    def is_empty(self):
        """
            True if db is empty
            @return bool
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT rowid FROM bookmarks LIMIT 1")
            v = result.fetchone()
            if v is None:
                return True
            return False

    def import_html(self, path):
        """
            Import html bookmarks
            @param path as str
        """
        try:
            from bs4 import BeautifulSoup
            SqlCursor.add(self)
            f = Gio.File.new_for_path(path)
            if not f.query_exists():
                return
            (status, content, tag) = f.load_contents(None)
            if status:
                data = content.decode("utf-8")
                soup = BeautifulSoup(data, "html.parser")
                parent_name = ""
                position = 0
                for dt in soup.findAll("dt"):
                    h3 = dt.find("h3")
                    if h3 is not None:
                        parent_name = h3.contents[0]
                        continue
                    else:
                        a = dt.find("a")
                        uri = a.get("href")
                        if a.get("tags") is None:
                            tags = [parent_name]
                        else:
                            tags = [a.get("tags")]
                        title = a.contents[0]
                        if uri is None:
                            parent_name = title
                            continue
                        elif not uri.startswith('http') or not title:
                            continue
                        uri = uri.rstrip('/')
                        rowid = self.get_id(uri)
                        if rowid is None:
                            if not tags:
                                tags = [parent_name]
                            # Add bookmark
                            bookmark_id = self.add(title, uri, None,
                                                   tags, 0)
                            # Set position
                            self.set_position(bookmark_id, position)
                            position += 1
            SqlCursor.remove(self)
        except Exception as e:
            Logger.error("DatabaseBookmarks::import_html(): %s", e)

    def import_chromium(self, chrome):
        """
            Chromium/Chrome importer
            As Eolie doesn't sync with Chromium, we do not handle parent
            guid and just import parents as tags
            @param chrome as bool
        """
        try:
            SqlCursor.add(self)
            import json
            homedir = GLib.get_home_dir()
            if chrome:
                path = homedir + "/.config/chrome/Default/Bookmarks"
            else:
                path = homedir + "/.config/chromium/Default/Bookmarks"
            status = False
            f = Gio.File.new_for_path(path)
            if f.query_exists():
                (status, content, tag) = f.load_contents(None)
            if status:
                data = content.decode("utf-8")
                j = json.loads(data)
                parents = []
                # Setup initial parents
                for root in j["roots"]:
                    parents.append(("", j["roots"][root]["children"]))
                # Walk parents and children
                while parents:
                    (parent_name, children) = parents.pop(0)
                    bookmarks = []
                    for child in children:
                        if child["type"] == "folder":
                            parents.append((child["name"], child["children"]))
                        elif child["type"] == "url":
                            bookmarks.append((child["name"],
                                              child["url"]))
                    position = 0
                    for bookmark in bookmarks:
                        tags = [parent_name]
                        title = bookmark[0]
                        uri = bookmark[1]
                        if not uri.startswith('http') or not title:
                            continue
                        uri = uri.rstrip('/')
                        rowid = self.get_id(uri)
                        if rowid is None:
                            # Add bookmark
                            bookmark_id = self.add(title, uri, None,
                                                   tags, 0)
                            # Set position
                            self.set_position(bookmark_id, position)
                            position += 1
            SqlCursor.remove(self)
        except Exception as e:
            Logger.error("DatabaseBookmarks::import_chromium(): %s", e)

    def import_firefox(self, profile):
        """
            Mozilla Firefox importer
            @param profile as str
        """
        try:
            SqlCursor.add(self)
            path = "%s/.mozilla/firefox/%s/places.sqlite" % \
                (GLib.get_home_dir(),
                 profile)
            f = Gio.File.new_for_path(path)
            if f.query_exists():
                c = sqlite3.connect(path, 600.0)
                # Add bookmarks
                bookmarks = self.__get_firefox_bookmarks(c)
                for (title, uri, parent_name, bookmark_guid,
                     parent_guid, position) in bookmarks:
                    tags = self.__get_tags_for_firefox_bookmark(c,
                                                                bookmark_guid)
                    bookmark_guid = self.__clean_guid(bookmark_guid)
                    parent_guid = self.__clean_guid(parent_guid)
                    if not uri.startswith('http') or not title:
                        continue
                    uri = uri.rstrip('/')
                    rowid = self.get_id(uri)
                    if rowid is None:
                        # If bookmark is not tagged, we use parent name
                        if not tags:
                            tags = [parent_name]
                        # Bookmarks and folder
                        bookmark_id = self.add(title, uri, bookmark_guid,
                                               tags, 0)
                        self.set_parent(bookmark_id, parent_guid,
                                        parent_name)
                        self.set_position(bookmark_id, position)
                # Add folders, we need to get them
                # as Firefox needs children order
                parents = self.__get_firefox_parents(c)
                for (title, parent_name, bookmark_guid,
                     parent_guid, position) in parents:
                    bookmark_guid = self.__clean_guid(bookmark_guid)
                    parent_guid = self.__clean_guid(parent_guid)
                    if not title or bookmark_guid == "root":
                        continue
                    uri = bookmark_guid
                    rowid = self.get_id(uri)
                    if rowid is None:
                        # Bookmarks and folder
                        bookmark_id = self.add(title, uri, bookmark_guid,
                                               [], 0)
                        self.set_parent(bookmark_id, parent_guid,
                                        parent_name)
                        self.set_position(bookmark_id, position)
            SqlCursor.remove(self)
        except Exception as e:
            Logger.error("DatabaseBookmarks::import_firefox(): %s", e)

    def exists_guid(self, guid):
        """
            Check if guid exists in db
            @return bool
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT guid FROM bookmarks\
                                  WHERE guid=?", (guid,))
            v = result.fetchone()
            return v is not None

    def search(self, search, limit):
        """
            Search string in db (uri and title)
            @param search as str
            @param limit as int
            @return [(id, title, uri)] as [(int, str, str)]
        """
        words = search.lower().split()
        items = []
        with SqlCursor(self) as sql:
            filters = ()
            for word in words:
                filters += ("%" + word + "%", "%" + word + "%")
            filters += (limit,)

            # Search items matching all words
            request = "SELECT rowid, title, uri\
                       FROM bookmarks WHERE "
            words_copy = list(words)
            while words_copy:
                word = words_copy.pop(0)
                if word:
                    request += " (title LIKE ? OR uri LIKE ?) AND"
            request += " guid != uri ORDER BY length(uri) ASC LIMIT ?"

            result = sql.execute(request, filters)
            items = list(result)
        return items

    def get_cursor(self):
        """
            Return a new sqlite cursor
        """
        try:
            c = sqlite3.connect(self.DB_PATH, 600.0)
            c.create_collation('LOCALIZED', LocalizedCollation())
            c.create_function("noaccents", 1, noaccents)
            return c
        except Exception as e:
            Logger.error("DatabaseBookmarks::get_cursor(): %s", e)
            exit(-1)

#######################
# PRIVATE             #
#######################
    def __get_firefox_bookmarks(self, c):
        """
            Return firefox bookmarks
            @param c as Sqlite cursor
            @return (title, url, parent title, guid, parent guid, position)
             as (str, str, str, str, str, int)
        """
        result = c.execute("SELECT bookmarks.title,\
                                   moz_places.url,\
                                   parent.title,\
                                   bookmarks.guid,\
                                   parent.guid,\
                                   bookmarks.position\
                            FROM moz_bookmarks AS bookmarks,\
                                 moz_bookmarks AS parent,\
                                 moz_places\
                            WHERE bookmarks.fk=moz_places.id\
                            AND parent.id=bookmarks.parent\
                            AND bookmarks.type=1")
        return list(result)

    def __get_tags_for_firefox_bookmark(self, c, guid):
        """
            Return firefox bookmarks
            @param c as Sqlite cursor
            @param guid as str
            @return (title, url, parent title, guid, parent guid, position)
             as (str, str, str, str, str, int)
        """
        result = c.execute("SELECT parent.title\
                            FROM moz_bookmarks AS bookmarks,\
                                 moz_bookmarks AS tag,\
                                 moz_bookmarks AS parent\
                            WHERE bookmarks.fk=tag.fk\
                            AND tag.fk=bookmarks.fk\
                            AND tag.title is null\
                            AND parent.id=tag.parent\
                            AND bookmarks.guid=?", (guid,))
        return list(itertools.chain(*result))

    def __get_firefox_parents(self, c):
        """
            Return firefox parents
            @param c as Sqlite cursor
            @return (title, parent title, guid, parent guid, position)
             as (str, str, str, str, str, int)
        """
        result = c.execute("SELECT bookmarks.title,\
                                   parent.title,\
                                   bookmarks.guid,\
                                   parent.guid,\
                                   bookmarks.position\
                            FROM moz_bookmarks AS bookmarks,\
                                 moz_bookmarks AS parent\
                            WHERE parent.id=bookmarks.parent\
                            AND bookmarks.type=2")
        return list(result)

    def __clean_guid(self, guid):
        """
            Clean guid to match sync API
            @param guid as str
            @return str
        """
        if guid == "root________":
            return "places"
        elif guid == "menu________":
            return "menu"
        elif guid == "toolbar_____":
            return "toolbar"
        elif guid == "unfiled_____":
            return "unfiled"
        elif guid == "mobile______":
            return "mobile"
        else:
            return guid
