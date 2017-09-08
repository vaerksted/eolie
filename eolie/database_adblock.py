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

from urllib.parse import urlparse
import sqlite3
import itertools
from gettext import gettext as _
from time import time

from eolie.helper_task import TaskHelper
from eolie.sqlcursor import SqlCursor
from eolie.define import EOLIE_LOCAL_PATH, ADBLOCK_JS, El


class DatabaseAdblock:
    """
        Eolie adblock db
    """
    DB_PATH = "%s/adblock2.db" % EOLIE_LOCAL_PATH

    __URIS = ["https://adaway.org/hosts.txt",
              "http://winhelp2002.mvps.org/hosts.txt",
              "http://hosts-file.net/ad_servers.txt",
              "https://pgl.yoyo.org/adservers/serverlist.php?"
              "hostformat=hosts&showintro=0&mimetype=plaintext"]

    __CSS_URIS = ["https://easylist-downloads.adblockplus.org/easylist.txt"]

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
    __create_adblock_css = '''CREATE TABLE adblock_css (
                                               id INTEGER PRIMARY KEY,
                                               name TEXT NOT NULL,
                                               whitelist TEXT DEFAULT "",
                                               blacklist TEXT DEFAULT "",
                                               mtime INT NOT NULL
                                               )'''

    def __init__(self):
        """
            Create database tables or manage update if needed
        """
        self.__cancellable = Gio.Cancellable.new()
        self.__task_helper = TaskHelper()
        self.__adblock_mtime = 0

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
                    sql.execute(self.__create_adblock_css)
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

        # Get in db mtime, only use main table values
        # Only update if filters older than one week
        mtime = 0
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT mtime FROM adblock LIMIT 1")
            v = result.fetchone()
            if v is not None:
                mtime = v[0]
        self.__adblock_mtime = int(time())
        # We ignore update value from rules file
        if self.__adblock_mtime - mtime < 604800:
            return
        # Update adblock db rules
        self.__cancellable.reset()
        self.__on_load_uri_content(None, False, b"", self.__URIS, False)
        self.__on_load_uri_content(None, False, b"", self.__CSS_URIS, True)

    def stop(self):
        """
            Stop update
        """
        self.__cancellable.cancel()

    def get_css_rules(self, uri):
        """
            Return css rules
            @return str
        """
        rules = ""
        parsed = urlparse(uri)
        if parsed.scheme not in ["http", "https"]:
            return ""
        netloc = parsed.netloc.lstrip("www.")
        with SqlCursor(self) as sql:
            request = "SELECT name FROM adblock_css WHERE\
                       (blacklist='' AND whitelist='') OR\
                       (blacklist!=? AND whitelist=?)"
            result = sql.execute(request, (netloc, netloc))
            for name in list(itertools.chain(*result)):
                rules += "%s,\n" % name
        return rules[:-2] + "{display: none !important;}"

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
    def __save_rules(self, params):
        """
            Save rules to db
            @param params as (bytes, str)
            @param uris as [str]
        """
        (rules, uris) = params
        SqlCursor.add(self)
        result = rules.decode('utf-8')
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
                            (dns, self.__adblock_mtime))
                count += 1
                if count == 1000:
                    sql.commit()
                    count = 0
        # We are the last call to save_rules()?
        # Delete removed entries and commit
        if not uris:
            with SqlCursor(self) as sql:
                sql.execute("DELETE FROM adblock\
                             WHERE mtime!=?", (self.__adblock_mtime,))
                sql.commit()
        SqlCursor.remove(self)

    def __save_css_default_rule(self, line):
        """
            Save default (without blacklist, whitelist) rule to db
            @param line as str
        """
        name = line[2:]
        # Update entry if exists, create else
        with SqlCursor(self) as sql:
            sql.execute("INSERT INTO adblock_css\
                              (name, mtime)\
                              VALUES (?, ?)",
                        (name, self.__adblock_mtime))

    def __save_css_domain_rule(self, line):
        """
            Save domain rule to db
            @param line as str
        """
        whitelist = ""
        blacklist = ""
        (domains, name) = line.split("##")
        for domain in domains.split(","):
            if domain.startswith("~"):
                blacklist += "@%s@" % domain[1:]
            else:
                whitelist += domain
        with SqlCursor(self) as sql:
            sql.execute("INSERT INTO adblock_css\
                         (name, whitelist, blacklist, mtime)\
                         VALUES (?, ?, ?, ?)",
                        (name, whitelist, blacklist, self.__adblock_mtime))

    def __save_css_rules(self, params):
        """
            Save rules to db
            @param params as (bytes, str)
            @param uris as [str]
        """
        (rules, uris) = params
        SqlCursor.add(self)
        result = rules.decode("utf-8")
        count = 0
        for line in result.split('\n'):
            if self.__cancellable.is_cancelled():
                raise IOError("Cancelled")
            if line.find("-abp-") != -1:
                continue
            elif line.startswith("##"):
                self.__save_css_default_rule(line)
            elif line.find("##") != -1:
                self.__save_css_domain_rule(line)
            count += 1
            if count == 1000:
                with SqlCursor(self) as sql:
                    sql.commit()
                count = 0
        # We are the last rule
        # Delete old entries
        if not uris:
            with SqlCursor(self) as sql:
                sql.execute("DELETE FROM adblock_css\
                             WHERE mtime!=?", (self.__adblock_mtime,))
                sql.commit()
        SqlCursor.remove(self)

    def __on_load_uri_content(self, uri, status, content, uris, is_css):
        """
            Load pending uris
            @param uri as str
            @param status as bool
            @param content as bytes
            @param uris as [str]
            @param is_css as bool
        """
        if status:
            if is_css:
                self.__task_helper.run(self.__save_css_rules, (content, uris))
            else:
                self.__task_helper.run(self.__save_rules, (content, uris))
        if uris:
            uri = uris.pop(0)
            self.__task_helper.load_uri_content(uri,
                                                self.__cancellable,
                                                self.__on_load_uri_content,
                                                uris,
                                                is_css)
