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

from gi.repository import Gio, GLib

from urllib.parse import urlparse
import sqlite3
import itertools
from pickle import dump, load
import re
from gettext import gettext as _
from time import time, sleep
from threading import Lock

from eolie.helper_task import TaskHelper
from eolie.sqlcursor import SqlCursor
from eolie.define import EOLIE_DATA_PATH, ADBLOCK_JS
from eolie.utils import remove_www
from eolie.logger import Logger


class DatabaseAdblock:
    """
        Eolie adblock db
    """
    __DB_PATH = "%s/adblock.db" % EOLIE_DATA_PATH

    __URIS = ["https://adaway.org/hosts.txt",
              "https://pgl.yoyo.org/adservers/serverlist.php?" +
              "hostformat=hosts&showintro=0&startdate%5Bday%5D=" +
              "&startdate%5Bmonth%5D=&startdate%5Byear%5D=",
              "http://winhelp2002.mvps.org/hosts.txt",
              "http://hosts-file.net/ad_servers.txt",
              "https://pgl.yoyo.org/adservers/serverlist.php?"
              "hostformat=hosts&showintro=0&mimetype=plaintext"]

    __CSS_URIS = ["https://easylist-downloads.adblockplus.org/easylist.txt"]

    __CSS_LOCALIZED_URIS = {
        "bg": "http://stanev.org/abp/adblock_bg.txt",
        "zh": "https://easylist-downloads.adblockplus.org/easylistchina.txt",
        "sk": "https://raw.github.com/tomasko126/" +
              "easylistczechandslovak/master/filters.txt",
        "cs": "https://raw.github.com/tomasko126/" +
              "easylistczechandslovak/master/filters.txt",
        "nl": "https://easylist-downloads.adblockplus.org/easylistdutch.txt",
        "de": "https://easylist-downloads.adblockplus.org/easylistgermany.txt",
        "he": "https://raw.githubusercontent.com/easylist/" +
              "EasyListHebrew/master/EasyListHebrew.txt",
        "it": "https://easylist-downloads.adblockplus.org/easylistitaly.txt",
        "lt": "http://margevicius.lt/easylistlithuania.txt",
        "es": "https://easylist-downloads.adblockplus.org/easylistspanish.txt",
        "lv": "https://notabug.org/latvian-list/" +
              "adblock-latvian/raw/master/lists/latvian-list.txt",
        "ar": "https://easylist-downloads.adblockplus.org/Liste_AR.txt",
        "fr": "https://easylist-downloads.adblockplus.org/liste_fr.txt",
        "ro": "http://www.zoso.ro/pages/rolist.txt",
        "ru": "https://easylist-downloads.adblockplus.org/advblock.txt",
        "ja": "http://bit.ly/11QrCfx",
        "fi": "https://adb.juvander.net/Finland_adb.txt",
        "cz": "http://adblock.dajbych.net/adblock.txt",
        "et": "http://gurud.ee/ab.txt",
        "hu": "https://raw.githubusercontent.com/szpeter80/" +
              "hufilter/master/hufilter.txt"}

    __SCHEMA_VERSION = 0
    __UPDATE = 172800

    __SPECIAL_CHARS = r"([.$+?{}()\[\]\\])"
    __REPLACE_CHARS = {"^": "(?:[^\w\d_\-.%]|$)",
                       "*": ".*"}

    # SQLite documentation:
    # In SQLite, a column with type INTEGER PRIMARY KEY
    # is an alias for the ROWID.
    # Here, we define an id INT PRIMARY KEY but never feed it,
    # this make VACUUM not destroy rowids...
    __create_adblock = """CREATE TABLE adblock (
                                               id INTEGER PRIMARY KEY,
                                               netloc TEXT TEXT NOT NULL,
                                               mtime INT NOT NULL
                                               )"""
    __create_adblock_re = """CREATE TABLE adblock_re (
                                               id INTEGER PRIMARY KEY,
                                               regex TEXT NOT NULL,
                                               mtime INT NOT NULL
                                               )"""
    __create_adblock_re_domain = """CREATE TABLE adblock_re_domain (
                                               id INTEGER PRIMARY KEY,
                                               domain TEXT NOT NULL,
                                               regex TEXT NOT NULL,
                                               mtime INT NOT NULL
                                               )"""
    __create_adblock_re_domain_ex = """CREATE TABLE adblock_re_domain_ex (
                                               id INTEGER PRIMARY KEY,
                                               domain TEXT NOT NULL,
                                               regex TEXT NOT NULL,
                                               mtime INT NOT NULL
                                               )"""
    __create_adblock_css = """CREATE TABLE adblock_css (
                                               id INTEGER PRIMARY KEY,
                                               rule TEXT NOT NULL,
                                               whitelist TEXT DEFAULT '',
                                               blacklist TEXT DEFAULT '',
                                               mtime INT NOT NULL
                                               )"""
    __create_adblock_cache = """CREATE TABLE adblock_cache (
                                               id INTEGER PRIMARY KEY,
                                               allowed_uri TEXT NOT NULL
                                               )"""
    __create_adblock_idx = """CREATE UNIQUE INDEX idx_adblock ON adblock(
                                               netloc)"""
    __create_adblock_re_idx = """CREATE UNIQUE INDEX idx_adblock_re
                                               ON adblock_re(regex)"""
    __create_adblock_re_domain_idx = """CREATE INDEX
                                               idx_adblock_re_domain
                                               ON adblock_re_domain(domain)"""
    __create_adblock_re_domain_regex_idx = """CREATE INDEX
                                               idx_adblock_re_domain_regex
                                               ON adblock_re_domain(regex)"""
    __create_adblock_re_domain_ex_idx = """CREATE INDEX
                                               idx_adblock_re_domain_ex
                                               ON adblock_re_domain(domain)"""
    __create_adblock_re_domain_regex_ex_idx = """CREATE INDEX
                                               idx_adblock_re_domain_regex_ex
                                               ON adblock_re_domain(regex)"""
    __create_adblock_css_black_idx = """CREATE INDEX
                                               idx_adblock_css_black
                                               ON adblock_css(
                                               blacklist)"""
    __create_adblock_css_white_idx = """CREATE INDEX
                                               idx_adblock_css_white
                                               ON adblock_css(
                                               whitelist)"""
    __create_adblock_cache_idx = """CREATE UNIQUE INDEX idx_adblock_cache
                                               ON adblock_cache(
                                               allowed_uri)"""

    def __init__(self):
        """
            Create database tables or manage update if needed
        """
        self.thread_lock = Lock()
        self.__cancellable = Gio.Cancellable.new()
        self.__task_helper = TaskHelper()
        self.__adblock_mtime = int(time())
        self.__regex = None

    def create_db(self):
        """
            Create databse
        """
        if not GLib.file_test(EOLIE_DATA_PATH, GLib.FileTest.IS_DIR):
            GLib.mkdir_with_parents(EOLIE_DATA_PATH, 0o0750)
        # If DB schema changed, remove it
        if GLib.file_test(self.__DB_PATH, GLib.FileTest.IS_REGULAR):
            with SqlCursor(self) as sql:
                result = sql.execute("PRAGMA user_version")
                v = result.fetchone()
                if v is None or v[0] != self.__SCHEMA_VERSION:
                    f = Gio.File.new_for_path(self.__DB_PATH)
                    f.delete()
        if not GLib.file_test(self.__DB_PATH, GLib.FileTest.IS_REGULAR):
            try:
                # Create db schema
                with SqlCursor(self) as sql:
                    sql.execute(self.__create_adblock)
                    sql.execute(self.__create_adblock_re)
                    sql.execute(self.__create_adblock_re_domain)
                    sql.execute(self.__create_adblock_re_domain_ex)
                    sql.execute(self.__create_adblock_css)
                    sql.execute(self.__create_adblock_cache)
                    sql.execute(self.__create_adblock_idx)
                    sql.execute(self.__create_adblock_re_idx)
                    sql.execute(self.__create_adblock_re_domain_idx)
                    sql.execute(self.__create_adblock_re_domain_regex_idx)
                    sql.execute(self.__create_adblock_re_domain_ex_idx)
                    sql.execute(self.__create_adblock_re_domain_regex_ex_idx)
                    sql.execute(self.__create_adblock_css_black_idx)
                    sql.execute(self.__create_adblock_css_white_idx)
                    sql.execute(self.__create_adblock_cache_idx)
                    sql.execute("PRAGMA user_version=%s" %
                                self.__SCHEMA_VERSION)
            except Exception as e:
                Logger.error("DatabaseAdblock::__init__(): %s", e)

    def update(self):
        """
            Update database
        """
        if not Gio.NetworkMonitor.get_default().get_network_available():
            return
        # Update adblock_js repo
        git = GLib.find_program_in_path("git")
        if git is None:
            Logger.info(_("For stronger ad blocking, install git command"))
        else:
            if GLib.file_test(ADBLOCK_JS, GLib.FileTest.IS_DIR):
                argv = [git,
                        "-C",
                        ADBLOCK_JS,
                        "pull",
                        "https://gitlab.gnome.org/gnumdk/eolie-adblock.git"]
            else:
                argv = [git,
                        "clone",
                        "https://gitlab.gnome.org/gnumdk/eolie-adblock.git",
                        ADBLOCK_JS]
            (pid, a1, a2, a3) = GLib.spawn_async(
                                    argv,
                                    flags=GLib.SpawnFlags.STDOUT_TO_DEV_NULL)
            GLib.spawn_close_pid(pid)

        # DB version is last successful sync mtime
        try:
            version = load(open(EOLIE_DATA_PATH + "/adblock.bin", "rb"))
        except:
            version = 0
        self.__cancellable.reset()
        if self.__adblock_mtime - version > self.__UPDATE:
            # Update host rules
            uris = list(self.__URIS)
            locales = GLib.get_language_names()
            user_locale = locales[0].split("_")[0]
            try:
                uris += self.__CSS_URIS +\
                        [self.__CSS_LOCALIZED_URIS[user_locale]]
            except:
                uris += self.__CSS_URIS
            uri = uris.pop(0)
            self.__task_helper.load_uri_content(uri,
                                                self.__cancellable,
                                                self.__on_load_uri_content,
                                                uris)

    def stop(self):
        """
            Stop update
        """
        self.__cancellable.cancel()

    def get_default_css_rules(self):
        """
            Return default css rules
        """
        rules = ""
        with SqlCursor(self) as sql:
            request = "SELECT rule FROM adblock_css WHERE\
                       blacklist='' AND whitelist=''"
            result = sql.execute(request)
            for rule in list(itertools.chain(*result)):
                rules += "%s,\n" % rule
        return rules[:-2] + "{display: none !important;}"

    def get_css_rules(self, uri):
        """
            Return css rules for uri
            @return str
        """
        rules = ""
        parsed = urlparse(uri)
        if parsed.scheme not in ["http", "https"]:
            return ""
        netloc = remove_www(parsed.netloc)
        with SqlCursor(self) as sql:
            request = "SELECT rule FROM adblock_css WHERE\
                       (blacklist!='' AND blacklist NOT LIKE ?) OR\
                       whitelist LIKE ?"
            result = sql.execute(request, ("%" + netloc + "%",
                                           "%" + netloc + "%"))
            for rule in list(itertools.chain(*result)):
                rules += "%s,\n" % rule
        return rules[:-2] + "{display: none !important;}"

    def is_netloc_blocked(self, netloc):
        """
            Return True if netloc is blocked
            @param netloc as str
            @return bool
        """
        try:
            with SqlCursor(self) as sql:
                result = sql.execute("SELECT mtime FROM adblock\
                                      WHERE netloc=?", (netloc,))
                v = result.fetchone()
                return v is not None
        except Exception as e:
            Logger.error("DatabaseAdblock::is_netloc_blocked(): %s", e)
            return False

    def is_uri_blocked(self, uri, netloc):
        """
            Return True if uri is blocked
            @param uri as str
            @param netloc as str
            @return bool
        """
        # We cache result for allowed uris
        # because regex are quite slow in python
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT allowed_uri\
                                  FROM adblock_cache\
                                  WHERE allowed_uri=?", (uri,))
            v = result.fetchone()
            if v is None:
                # Search in main regexes
                if self.__regex is None:
                    request = "SELECT regex FROM adblock_re"
                    result = sql.execute(request)
                    rules = list(itertools.chain(*result))
                    if rules:
                        regexes = "|".join(regex for regex in rules)
                        self.__regex = re.compile(regexes)
                if self.__regex is not None:
                    blocked_re = bool(self.__regex.search(uri))
                else:
                    blocked_re = False
                # Find in domain regexes
                request = "SELECT regex FROM adblock_re_domain\
                           WHERE domain=?"
                result = sql.execute(request, (netloc,))
                rules = list(itertools.chain(*result))
                if rules:
                    regexes = "|".join(regex for regex in rules)
                    blocked_re_domain = bool(re.search(regexes, uri))
                else:
                    blocked_re_domain = False
                # If previous regexes blocked uri, check for an exception
                if blocked_re_domain:
                    request = "SELECT regex FROM adblock_re_domain_ex\
                               WHERE domain=?"
                    result = sql.execute(request, (netloc,))
                    rules = list(itertools.chain(*result))
                    if rules:
                        regexes = "|".join(regex for regex in rules)
                        if bool(re.search(regexes, uri)):
                            blocked_re_domain = False
                if not blocked_re and not blocked_re_domain:
                    sql.execute("INSERT INTO adblock_cache\
                                (allowed_uri) VALUES (?)",
                                (uri,))
                    return False
                else:
                    return True
            else:
                return False

    def get_cursor(self):
        """
            Return a new sqlite cursor
        """
        try:
            c = sqlite3.connect(self.__DB_PATH, 600.0)
            return c
        except Exception as e:
            Logger.error("DatabaseAdblock::get_cursor(): %s", e)
            exit(-1)

#######################
# PRIVATE             #
#######################
    def __add_netloc(self, netloc):
        """
            Add a new netloc
            @param netloc as str
        """
        with SqlCursor(self) as sql:
            try:
                sql.execute("INSERT INTO adblock\
                            (netloc, mtime) VALUES (?, ?)",
                            (netloc, self.__adblock_mtime))
            except:
                sql.execute("UPDATE adblock SET mtime=?\
                             WHERE netloc=?",
                            (self.__adblock_mtime, netloc))

    def __add_regex(self, regex):
        """
            Add a new regex
            @param regex as str
        """
        with SqlCursor(self) as sql:
            try:
                sql.execute("INSERT INTO adblock_re\
                            (regex, mtime) VALUES (?, ?)",
                            (regex, self.__adblock_mtime))
            except:
                sql.execute("UPDATE adblock_re SET mtime=?\
                             WHERE regex=?",
                            (self.__adblock_mtime, regex))

    def __add_regex_domain(self, regex, domain):
        """
            Add a new regex
            @param regex as str
            @param domain
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT mtime FROM adblock_re_domain\
                                  WHERE regex=? AND domain=?",
                                 (regex, domain))
            v = result.fetchone()
            if v is None:
                sql.execute("INSERT INTO adblock_re_domain\
                            (regex, domain, mtime) VALUES (?, ?, ?)",
                            (regex, domain, self.__adblock_mtime))
            else:
                sql.execute("UPDATE adblock_re_domain SET mtime=?\
                             WHERE regex=? AND domain=?",
                            (self.__adblock_mtime, regex, domain))

    def __add_regex_domain_ex(self, regex, domain):
        """
            Add a new exception regex
            @param regex as str
            @param domain
        """
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT mtime FROM adblock_re_domain_ex\
                                  WHERE regex=? AND domain=?",
                                 (regex, domain))
            v = result.fetchone()
            if v is None:
                sql.execute("INSERT INTO adblock_re_domain_ex\
                            (regex, domain, mtime) VALUES (?, ?, ?)",
                            (regex, domain, self.__adblock_mtime))
            else:
                sql.execute("UPDATE adblock_re_domain_ex SET mtime=?\
                             WHERE regex=? AND domain=?",
                            (self.__adblock_mtime, regex, domain))

    def __rule_to_regex(self, rule):
        """
            Convert rule to regex
            @param rule as str
            @return regex as str
        """
        try:
            # Do nothing if rule is already a regex
            if rule[0] == rule[-1] == "/":
                return rule[1:-1]

            rule = re.sub(self.__SPECIAL_CHARS, r"\\\1", rule)

            # Handle ^ separator character, *, etc...
            for key in self.__REPLACE_CHARS.keys():
                rule = rule.replace(key, self.__REPLACE_CHARS[key])
            # End of the address
            if rule[-1] == "|":
                rule = rule[:-1] + "$"
            # Start of the address
            if rule[0] == "|":
                rule = "^" + rule[1:]
            # Escape remaining | but not |$ => see self.__REPLACE_CHARS
            rule = re.sub("(\|)[^$]", r"\|", rule)
            return rule
        except Exception as e:
            Logger.error("DatabaseAdblock::__rule_to_regex(): %s", e)
            return None

    def __save_rules(self, rules):
        """
            Save rules to db
            @param rules bytes
        """
        SqlCursor.add(self)
        result = rules.decode('utf-8')
        count = 0
        for line in result.split('\n'):
            SqlCursor.allow_main_thread_execution(self)
            if self.__cancellable.is_cancelled():
                SqlCursor.remove(self)
                raise Exception("Cancelled")
            if line.startswith('#'):
                continue
            array = line.replace(
                         ' ', '\t', 1).replace('\t', '@', 1).split('@')
            if len(array) <= 1:
                continue
            netloc = array[1].replace(
                               ' ', '').replace('\r', '').split('#')[0]
            # Update entry if exists, create else
            if netloc != "localhost":
                Logger.debug("Add filter: %s", netloc)
                self.__add_netloc(netloc)
            count += 1
            if count == 1000:
                SqlCursor.commit(self)
                # Do not flood sqlite, this allow webkit extension to run
                sleep(0.1)
                count = 0
        SqlCursor.remove(self)

    def __save_css_default_rule(self, line):
        """
            Save default (without blacklist, whitelist) rule to db
            @param line as str
        """
        rule = line[2:]
        # Update entry if exists, create else
        with SqlCursor(self) as sql:
            try:
                sql.execute("INSERT INTO adblock_css\
                            (rule, mtime) VALUES (?, ?)",
                            (rule, self.__adblock_mtime))
            except:
                sql.execute("UPDATE adblock_css SET mtime=?\
                             WHERE rule=?",
                            (self.__adblock_mtime, rule))

    def __save_css_domain_rule(self, line):
        """
            Save domain rule to db
            @param line as str
        """
        whitelist = []
        blacklist = []
        (domains, rule) = line.split("##")
        for domain in domains.split(","):
            if domain.startswith("~"):
                blacklist.append(domain[1:])
            else:
                whitelist.append(domain)
        str_whitelist = ",".join(whitelist)
        str_blacklist = ",".join(blacklist)
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT mtime FROM adblock_css\
                                  WHERE blacklist=? AND whitelist=?\
                                  AND rule=?",
                                 (str_blacklist, str_whitelist, rule))
            v = result.fetchone()
            if v is None:
                sql.execute("INSERT INTO adblock_css\
                             (rule, whitelist, blacklist, mtime)\
                             VALUES (?, ?, ?, ?)",
                            (rule, str_whitelist, str_blacklist,
                             self.__adblock_mtime))
            else:
                sql.execute("UPDATE adblock_css SET mtime=?\
                             WHERE rule=? and blacklist=? and whitelist=?",
                            (self.__adblock_mtime, rule,
                             str_blacklist, str_whitelist))

    def __save_css_exception(self, line):
        """
            Add a new exception
            @param line as str
        """
        (domain, rule) = line.split("#@#")
        with SqlCursor(self) as sql:
            result = sql.execute("SELECT rowid, blacklist FROM adblock_css\
                                  WHERE rule=?", (rule,))
            v = result.fetchone()
            if v is None:
                sql.execute("INSERT INTO adblock_css\
                             (rule, whitelist, blacklist, mtime)\
                             VALUES (?, ?, ?, ?)",
                            (rule, "", domain, self.__adblock_mtime))
            else:
                (rowid, blacklist) = v
                blacklist += ",%s" % domain
                sql.execute("UPDATE adblock_css SET blacklist=?\
                             WHERE rowid=?", (blacklist, rowid))

    def __save_abp_rule(self, rule, exception):
        """
            Save abp rule
            @param rule as str
            @param exception as bool
        """
        # Simple host rule
        if rule[:2] == "||":
            if rule[-1] == "^" and not exception:
                self.__add_netloc(rule[2:-1])
            else:
                regex = self.__rule_to_regex(rule[2:])
                split = re.split("/|\^", rule[2:])
                uri = "http://%s" % split[0]
                parsed = urlparse(uri)
                if parsed.netloc:
                    if exception:
                        self.__add_regex_domain_ex(regex, parsed.netloc)
                    else:
                        self.__add_regex_domain(regex, parsed.netloc)
                elif not exception:
                    self.__add_regex(regex)
        elif not exception:
            regex = self.__rule_to_regex(rule)
            if regex is not None:
                self.__add_regex(regex)

    def __save_abp_rules(self, rules):
        """
            Save rules to db
            @param rules as bytes
        """
        SqlCursor.add(self)
        result = rules.decode("utf-8")
        count = 0
        for line in result.split('\n'):
            SqlCursor.allow_main_thread_execution(self)
            if self.__cancellable.is_cancelled():
                SqlCursor.remove(self)
                raise Exception("Cancelled")
            if "-abp-" in line or "$" in line or "!" in line or "[" in line:
                continue
            elif line.startswith("##"):
                self.__save_css_default_rule(line)
            elif "#@#" in line:
                self.__save_css_exception(line)
            elif "##" in line:
                self.__save_css_domain_rule(line)
            elif line.startswith("@@"):
                self.__save_abp_rule(line[2:], True)
            else:
                self.__save_abp_rule(line, False)
            Logger.debug("Add abp filter: %s", line)
            count += 1
            if count == 1000:
                SqlCursor.commit(self)
                # Do not flood sqlite, this allow webkit extension to run
                sleep(0.1)
                count = 0
        SqlCursor.remove(self)

    def __on_save_rules(self, result, uris=[]):
        """
            Load next uri, if finished, load CSS rules
            @param result (unused)
            @param uris as [str]
        """
        if self.__cancellable.is_cancelled():
            return
        if uris:
            uri = uris.pop(0)
            self.__task_helper.load_uri_content(uri,
                                                self.__cancellable,
                                                self.__on_load_uri_content,
                                                uris)
        else:
            with SqlCursor(self) as sql:
                sql.execute("DELETE FROM adblock\
                             WHERE mtime!=?", (self.__adblock_mtime,))
                sql.execute("DELETE FROM adblock_re\
                             WHERE mtime!=?", (self.__adblock_mtime,))
                sql.execute("DELETE FROM adblock_re_domain\
                             WHERE mtime!=?", (self.__adblock_mtime,))
                sql.execute("DELETE FROM adblock_re_domain_ex\
                             WHERE mtime!=?", (self.__adblock_mtime,))
                sql.execute("DELETE FROM adblock_css\
                             WHERE mtime!=?", (self.__adblock_mtime,))
                sql.execute("DELETE FROM adblock_cache")
                try:
                    dump(self.__adblock_mtime,
                         open(EOLIE_DATA_PATH + "/adblock.bin", "wb"))
                except Exception as e:
                    Logger.error("DatabaseAdblock::__on_save_rules(): %s", e)

    def __on_load_uri_content(self, uri, status, content, uris):
        """
            Save loaded values
            @param uri as str
            @param status as bool
            @param content as bytes
            @param uris as [str]
        """
        Logger.debug("DatabaseAdblock::__on_load_uri_content(): %s", uri)
        if status:
            if uri in self.__URIS:
                self.__task_helper.run(self.__save_rules, content,
                                       callback=(self.__on_save_rules, uris))
            else:
                self.__task_helper.run(self.__save_abp_rules, content,
                                       callback=(self.__on_save_rules, uris))
        else:
            self.__on_save_rules(None, uris)
