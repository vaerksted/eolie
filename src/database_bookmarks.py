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

from gi.repository import GLib, Gio

import sqlite3
import itertools

from eolie.utils import noaccents, get_random_string
from eolie.localized import LocalizedCollation
from eolie.sqlcursor import SqlCursor


class DatabaseBookmarks:
    """
        Eolie bookmarks db
    """
    if GLib.getenv("XDG_DATA_HOME") is None:
        __LOCAL_PATH = GLib.get_home_dir() + "/.local/share/eolie"
    else:
        __LOCAL_PATH = GLib.getenv("XDG_DATA_HOME") + "/eolie"
    DB_PATH = "%s/bookmarks.db" % __LOCAL_PATH

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
                                               atime INT NOT NULL,
                                               guid TEXT NOT NULL,
                                               mtime REAL NOT NULL,
                                               position INT DEFAULT 0,
                                               del INT DEFAULT 0
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
        f = Gio.File.new_for_path(self.DB_PATH)
        if not f.query_exists():
            try:
                d = Gio.File.new_for_path(self.__LOCAL_PATH)
                if not d.query_exists():
                    d.make_directory_with_parents()
                # Create db schema
                with SqlCursor(self) as sql:
                    sql.execute(self.__create_bookmarks)
                    sql.execute(self.__create_tags)
                    sql.execute(self.__create_bookmarks_tags)
                    sql.execute(self.__create_parents)
                    sql.commit()
                self.import_firefox()
            except Exception as e:
                print("DatabaseBookmarks::__init__(): %s" % e)

    def add(self, title, uri, guid, tags, atime=0, commit=True):
        """
            Add a new bookmark
            @param title as str
            @param uri as str
            @param guid as str
            @param tags as [str]
            @param parent_guid as str
            @param ctime as int
            @param commit as bool
            @return bookmark id as int
        """
        # Find an uniq guid
        while guid is None:
            guid = get_random_string(12)
            if self.exists_guid(guid):
                guid = None

        with SqlCursor(self) as sql:
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
            if commit:
                sql.commit()
            return bookmarks_id

    def delete(self, bookmark_id, delete=True):
        """
            Mark bookmark as deleted
            @param bookmark id as int
            @param delete as bool
        """
        with SqlCursor(self) as sql:
            sql.execute("UPDATE bookmarks\
                         SET del=?\
                         WHERE rowid=?", (delete, bookmark_id))

    def remove(self, bookmark_id, commit=True):
        """
            Remove bookmark from db
            @param bookmark id as int
            @param commit as bool
        """
        with SqlCursor(self) as sql:
            sql.execute("DELETE FROM bookmarks\
                         WHERE rowid=?", (bookmark_id,))
            sql.execute("DELETE FROM bookmarks_tags\
                         WHERE bookmark_id=?", (bookmark_id,))
            sql.execute("DELETE FROM parents\
                         WHERE bookmark_id=?", (bookmark_id,))
            if commit:
                sql.commit()

    def add_tag(self, tag, commit=False):
        """
            Add tag to db, return existing if exists
            @param tag as str
            @return tag id as int
        """
        with SqlCursor(self) as sql:
            result = sql.execute("INSERT INTO tags\
                                  (title) VALUES (?)",
                                 (tag,))
            if commit:
                sql.commit()
            return result.lastrowid

    def del_tag(self, tag, commit=False):
        """
            Add tag to db, return existing if exists
            @param tag as str
        """
        with SqlCursor(self) as sql:
            tag_id = self.get_tag_id(tag)
            if tag_id is None:
                return
            sql.execute("DELETE FROM tags\
                         WHERE rowid=?", (tag_id,))
            sql.execute("DELETE FROM bookmarks_tags\
                         WHERE tag_id=?", (tag_id,))
            if commit:
                sql.commit()

    def rename_tag(self, old, new):
        """
            Rename tag
            @param old as str
            @param new as str
        """
        with SqlCursor(self) as sql:
            sql.execute("UPDATE tags set title=? WHERE title=?", (new, old))
            sql.commit()

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
                                  WHERE tags.title=?\
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
            result = sql.execute("SELECT rowid\
                                  FROM bookmarks\
                                  WHERE uri=?", (uri.rstrip('/'),))
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
                                  WHERE mtime >= ?\
                                  AND uri != guid\
                                  AND del=0", (mtime,))
            return list(itertools.chain(*result))

    def get_deleted_ids(self):
        """
            Get ids that need to be synced related to mtime
            @return [int]
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT rowid\
                                  FROM bookmarks\
                                  WHERE del=1")
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
            if v is not None:
                return v[0]
            return None

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
            if v is not None:
                return v[0]
            return None

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
            return ""

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
                                  WHERE title=?", (title,))
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

    def get_bookmarks(self, tag_id):
        """
            Get all bookmarks
            @param tag id as int
            @return [(id, title, uri)]
        """
        with SqlCursor(self) as sql:
            result = sql.execute("\
                            SELECT bookmarks.rowid,\
                                   bookmarks.title,\
                                   bookmarks.uri\
                            FROM bookmarks, bookmarks_tags\
                            WHERE bookmarks.rowid=bookmarks_tags.bookmark_id\
                            AND bookmarks_tags.tag_id=?\
                            AND bookmarks.guid != bookmarks.uri\
                            AND bookmarks.del=0\
                            ORDER BY bookmarks.popularity DESC", (tag_id,))
            return list(result)

    def get_populars(self):
        """
            Get popular bookmarks
            @return [(id, title, uri)]
        """
        with SqlCursor(self) as sql:
            result = sql.execute("\
                            SELECT bookmarks.rowid,\
                                   bookmarks.title,\
                                   bookmarks.uri\
                            FROM bookmarks\
                            WHERE bookmarks.popularity!=0\
                            AND bookmarks.del=0\
                            AND bookmarks.guid != bookmarks.uri\
                            ORDER BY bookmarks.popularity DESC")
            return list(result)

    def get_unclassified(self):
        """
            Get bookmarks without tag
            @return [(id, title, uri)]
        """
        with SqlCursor(self) as sql:
            result = sql.execute("\
                            SELECT bookmarks.rowid,\
                                   bookmarks.title,\
                                   bookmarks.uri\
                            FROM bookmarks\
                            WHERE NOT EXISTS (\
                                SELECT bookmark_id FROM bookmarks_tags\
                                WHERE bookmark_id=bookmarks.rowid)\
                            AND bookmarks.del=0\
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
                                  bookmarks.title,\
                                  bookmarks.uri\
                                  FROM bookmarks\
                                  WHERE bookmarks.atime != 0\
                                  AND bookmarks.del=0\
                                  AND bookmarks.guid != bookmarks.uri\
                                  ORDER BY bookmarks.atime DESC")
            return list(result)

    def set_title(self, bookmark_id, title, commit=True):
        """
            Set bookmark title
            @param bookmark id as int
            @param title as str
            @param commit as bool
        """
        with SqlCursor(self) as sql:
            sql.execute("UPDATE bookmarks\
                         SET title=?\
                         WHERE rowid=?", (title, bookmark_id,))
            if commit:
                sql.commit()

    def set_uri(self, bookmark_id, uri, commit=True):
        """
            Set bookmark uri
            @param bookmark id as int
            @param uri as str
            @param commit as bool
        """
        with SqlCursor(self) as sql:
            sql.execute("UPDATE bookmarks\
                         SET uri=?\
                         WHERE rowid=?", (uri.rstrip('/'), bookmark_id,))
            if commit:
                sql.commit()

    def set_parent(self, bookmark_id, parent_guid, parent_name, commit=True):
        """
            Set parent id for bookmark
            @param bookmark_id as int
            @param parent_guid as str
            @param parent_name as str
            @param commit as bool
        """
        with SqlCursor(self) as sql:
            previous_guid = self.get_parent_guid(bookmark_id)
            if previous_guid is None:
                sql.execute("INSERT INTO parents\
                             (bookmark_id, parent_guid, parent_name)\
                             VALUES (?, ?, ?)",
                            (bookmark_id, parent_guid, parent_name))
            else:
                sql.execute("UPDATE parents\
                             SET parent_guid=?, parent_name=?\
                             WHERE bookmark_id=?",
                            (parent_guid, parent_name, bookmark_id))
            if commit:
                sql.commit()

    def set_access_time(self, uri, atime):
        """
            Set bookmark access time
            @param uri as str
            @param atime as int
        """
        with SqlCursor(self) as sql:
            sql.execute("UPDATE bookmarks\
                         SET atime=? where uri=?", (atime, uri.rstrip('/')))
            sql.commit()

    def set_mtime(self, bookmark_id, mtime, commit=True):
        """
            Set bookmark sync time
            @param bookmark id as int
            @param mtime as int
            @param commit as bool
        """
        with SqlCursor(self) as sql:
            sql.execute("UPDATE bookmarks\
                         SET mtime=? where rowid=?", (mtime, bookmark_id))
            if commit:
                sql.commit()

    def set_position(self, bookmark_id, position, commit=True):
        """
            Set bookmark position
            @param bookmark id as int
            @param mtime as int
            @param commit as bool
        """
        with SqlCursor(self) as sql:
            sql.execute("UPDATE bookmarks\
                         SET position=? where rowid=?", (position,
                                                         bookmark_id))
            if commit:
                sql.commit()

    def set_tag_title(self, tag_id, title):
        """
            Set tag id title
            @param tag id as int
            @parma title as str
        """
        with SqlCursor(self) as sql:
            sql.execute("UPDATE tags SET title=? WHERE id=?", (title, tag_id,))
            sql.commit()

    def set_more_popular(self, uri):
        """
            Increment bookmark popularity
            @param uri as str
        """
        with SqlCursor(self) as sql:
            uri = uri.rstrip('/')
            result = sql.execute("SELECT popularity FROM bookmarks\
                                  WHERE uri=?", (uri,))
            v = result.fetchone()
            if v is not None:
                sql.execute("UPDATE bookmarks set popularity=?\
                             WHERE uri=?", (v[0]+1, uri))
                sql.commit()

    def add_tag_to(self, tag_id, bookmark_id, commit=True):
        """
            Add tag to bookmark
            @param tag id as int
            @param bookmark id as int
            @param commit as bool
        """
        with SqlCursor(self) as sql:
            sql.execute("INSERT INTO bookmarks_tags\
                         (bookmark_id, tag_id) VALUES (?, ?)",
                        (bookmark_id, tag_id))
            if commit:
                sql.commit()

    def del_tag_from(self, tag_id, bookmark_id, commit=True):
        """
            Remove tag from bookmark
            @param tag id as int
            @param bookmark id as int
            @param commit as bool
        """
        with SqlCursor(self) as sql:
            sql.execute("DELETE from bookmarks_tags\
                         WHERE bookmark_id=? and tag_id=?",
                        (bookmark_id, tag_id))
            if commit:
                sql.commit()

    def clean_tags(self):
        """
            Remove orphan tags
        """
        with SqlCursor(self) as sql:
            sql.execute("DELETE from tags\
                         WHERE NOT EXISTS (\
                            SELECT rowid FROM bookmarks_tags\
                            WHERE tags.rowid = bookmarks_tags.tag_id)")
            sql.commit()

    def import_firefox(self):
        """
            Mozilla Firefox importer
        """
        SqlCursor.add(self)
        firefox_path = GLib.get_home_dir() + "/.mozilla/firefox/"
        d = Gio.File.new_for_path(firefox_path)
        infos = d.enumerate_children(
            'standard::name,standard::type',
            Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS,
            None)
        sqlite_path = None
        for info in infos:
            if info.get_file_type() == Gio.FileType.DIRECTORY:
                f = Gio.File.new_for_path(firefox_path +
                                          info.get_name() + "/places.sqlite")
                if f.query_exists():
                    sqlite_path = f.get_path()
                    break
        if sqlite_path is not None:
            c = sqlite3.connect(sqlite_path, 600.0)
            # Add bookmarks
            result = c.execute("SELECT bookmarks.title,\
                                       moz_places.url,\
                                       tag.title,\
                                       bookmarks.guid,\
                                       tag.guid,\
                                       bookmarks.position\
                                FROM moz_bookmarks AS bookmarks,\
                                     moz_bookmarks AS tag,\
                                     moz_places\
                                WHERE bookmarks.fk=moz_places.id\
                                AND tag.id=bookmarks.parent\
                                AND bookmarks.type=1")
            for (title, uri,  parent_name, bookmark_guid,
                 parent_guid, position) in list(result):
                bookmark_guid = self.__clean_guid(bookmark_guid)
                parent_guid = self.__clean_guid(parent_guid)
                if not uri.startswith('http') or not title:
                    continue
                uri = uri.rstrip('/')
                rowid = self.get_id(uri)
                if rowid is None:
                    # Bookmarks and folder
                    bookmark_id = self.add(title, uri, bookmark_guid,
                                           [parent_name], 0, False)
                    self.set_parent(bookmark_id, parent_guid,
                                    parent_name, False)
                    self.set_position(bookmark_id, position, False)
            # Add folders, we need to get them as Firefox need children order
            result = c.execute("SELECT bookmarks.title,\
                                       tag.title,\
                                       bookmarks.guid,\
                                       tag.guid,\
                                       bookmarks.position\
                                FROM moz_bookmarks AS bookmarks,\
                                     moz_bookmarks AS tag\
                                WHERE tag.id=bookmarks.parent\
                                AND bookmarks.type=2")
            for (title, parent_name, bookmark_guid,
                 parent_guid, position) in list(result):
                bookmark_guid = self.__clean_guid(bookmark_guid)
                parent_guid = self.__clean_guid(parent_guid)
                if not title or bookmark_guid == "root":
                    continue
                uri = bookmark_guid
                rowid = self.get_id(uri)
                if rowid is None:
                    # Bookmarks and folder
                    bookmark_id = self.add(title, uri, bookmark_guid,
                                           [parent_name], 0, False)
                    self.set_parent(bookmark_id, parent_guid,
                                    parent_name, False)
                    self.set_position(bookmark_id, position, False)
        with SqlCursor(self) as sql:
            sql.commit()
        SqlCursor.remove(self)

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
        """
        with SqlCursor(self) as sql:
            filter = '%' + search + '%'
            result = sql.execute("SELECT title, uri\
                                  FROM bookmarks\
                                  WHERE title LIKE ?\
                                   OR uri LIKE ?\
                                  ORDER BY popularity DESC, atime DESC\
                                  LIMIT ?",
                                 (filter, filter, limit))
            return list(result)

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
            print("DatabaseBookmarks::drop_db():", e)

#######################
# PRIVATE             #
#######################
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
