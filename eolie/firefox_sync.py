# Copyright (c) 2017-2018 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
# Fork of https://github.com/firefox-services/syncclient
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

from gi.repository import Gio, GLib, GObject

from pickle import dump, load
from hashlib import sha256
import json
from fcntl import flock, LOCK_EX, LOCK_NB, LOCK_UN
from time import time, sleep

from eolie.helper_task import TaskHelper
from eolie.define import App, EOLIE_DATA_PATH
from eolie.sqlcursor import SqlCursor
from eolie.helper_passwords import PasswordsHelper
from eolie.logger import Logger


TOKENSERVER_URL = "https://token.services.mozilla.com/"
FXA_SERVER_URL = "https://api.accounts.mozilla.com"


class SyncWorker(GObject.Object):
    """
       Manage sync with firefox server, will start syncing on init
    """

    __gsignals__ = {
        'syncing': (GObject.SignalFlags.RUN_FIRST, None, (bool,))
    }

    def check_modules():
        """
            True if deps are installed
            @return bool
        """
        from importlib import util
        fxa = util.find_spec("fxa")
        crypto = util.find_spec("Crypto")
        if fxa is None:
            Logger.info("PyFxA missing: pip3 install --user pyfxa")
        if crypto is None:
            Logger.info("Cyrpto missing: pip3 install --user pycrypto")
        return fxa is not None and crypto is not None

    def __init__(self):
        """
            Init worker
        """
        GObject.Object.__init__(self)
        self.__sync_cancellable = Gio.Cancellable()
        self.__username = ""
        self.__password = ""
        self.__token = ""
        self.__uid = ""
        self.__keyB = b""
        self.__mtimes = {"bookmarks": 0.1, "history": 0.1, "passwords": 0.1}
        # We do not create this here because it's slow down Eolie startup
        # See __firefox_sync property
        self.__mz = None
        self.__state_lock = True
        self.__session = None
        self.__syncing = False
        self.__syncing_pendings = False
        try:
            self.__pending_records = load(open(EOLIE_DATA_PATH +
                                               "/firefox_sync_pendings.bin",
                                               "rb"))
            self.__sync_pendings()
        except:
            self.__pending_records = {"history": [],
                                      "passwords": [],
                                      "bookmarks": []}
        self.__helper = PasswordsHelper()
        self.set_credentials()

    def login(self, attributes, password, code):
        """
            Login to service
            @param attributes as {}
            @param password as str
            @param code as str
        """
        self.__username = ""
        self.__password = ""
        self.__uid = ""
        self.__token = ""
        self.__keyB = b""
        if attributes is None or not attributes["login"] or not password:
            Logger.warning("SyncWorker::login(): %s", attributes)
            return
        from base64 import b64encode
        import json
        session = None
        self.__username = attributes["login"]
        self.__password = password
        # Connect to firefox sync
        try:
            session = self.__firefox_sync.login(
                self.__username, password, code)
            bid_assertion, key = self.__firefox_sync.\
                get_browserid_assertion(session)
            self.__token = session.token
            self.__uid = session.uid
            self.__keyB = session.keys[1]
            keyB_encoded = b64encode(self.__keyB).decode("utf-8")
            record = {"uid": self.__uid,
                      "token": self.__token,
                      "keyB": keyB_encoded}
            self.__helper.clear_sync(self.__helper.store_sync,
                                     self.__username,
                                     json.dumps(record))
        except Exception as e:
            self.__helper.clear_sync(self.__helper.store_sync,
                                     self.__username,
                                     "")
            raise(e)

    def new_session(self):
        """
            Start a new session
        """
        # Just reset session, will be set by get_session_bulk_keys()
        self.__session = None

    def set_credentials(self):
        """
            Set credentials using Secret
        """
        self.__helper.get_sync(self.__set_credentials)

    def pull_loop(self):
        """
            Start pulling every hours
        """
        def loop():
            self.pull()
            return True
        self.pull()
        GLib.timeout_add_seconds(3600, loop)

    def pull(self, force=False):
        """
            Start pulling from Firefox sync
            @param force as bool
        """
        if Gio.NetworkMonitor.get_default().get_network_available() and\
                self.__username:
            task_helper = TaskHelper()
            task_helper.run(self.__pull, force)

    def push(self):
        """
            Start pushing to Firefox sync
            Will push all data
        """
        if Gio.NetworkMonitor.get_default().get_network_available() and\
                self.__username:
            task_helper = TaskHelper()
            task_helper.run(self.__push,)

    def push_history(self, history_id):
        """
            Push history id
            @param history_id as int
        """
        if self.__username:
            task_helper = TaskHelper()
            task_helper.run(self.__push_history, history_id)

    def push_bookmark(self, bookmark_id):
        """
            Push bookmark id
            @param bookmark_id as int
        """
        if self.__username:
            task_helper = TaskHelper()
            task_helper.run(self.__push_bookmark, bookmark_id)

    def push_password(self, user_form_name, user_form_value, pass_form_name,
                      pass_form_value, uri, form_uri, uuid):
        """
            Push password
            @param user_form_name as str
            @param user_form_value as str
            @param pass_form_name as str
            @param pass_form_value as str
            @param uri as str
            @param form_uri as str
            @param uuid as str
        """
        if self.__username:
            task_helper = TaskHelper()
            task_helper.run(self.__push_password,
                            user_form_name, user_form_value, pass_form_name,
                            pass_form_value, uri, form_uri, uuid)

    def remove_from_history(self, guid):
        """
            Remove history guid from remote history
            @param guid as str
        """
        if self.__username:
            task_helper = TaskHelper()
            task_helper.run(self.__remove_from_history, guid)

    def remove_from_bookmarks(self, guid):
        """
            Remove bookmark guid from remote bookmarks
            @param guid as str
        """
        if self.__username:
            task_helper = TaskHelper()
            task_helper.run(self.__remove_from_bookmarks, guid)

    def remove_from_passwords(self, uuid):
        """
            Remove password from passwords collection
            @param uuid as str
        """
        if self.__username:
            task_helper = TaskHelper()
            task_helper.run(self.__remove_from_passwords, uuid)

    def delete_secret(self):
        """
            Delete sync secret
        """
        self.__username = ""
        self.__password = ""
        self.__session = None
        self.__helper.clear_sync(None)

    def stop(self, force=False):
        """
            Stop update, if force, kill session too
            @param force as bool
        """
        self.__sync_cancellable.cancel()
        self.__sync_cancellable = Gio.Cancellable()
        if force:
            self.__session = None

    def save_pendings(self):
        """
            Save pending records
        """
        try:
            dump(self.__pending_records,
                 open(EOLIE_DATA_PATH + "/firefox_sync_pendings.bin", "wb"))
        except Exception as e:
            Logger.Error("SyncWorker::save_pendings(): %s", e)

    @property
    def syncing(self):
        """
            True if syncing
            @return bool
        """
        return self.__syncing

    @property
    def status(self):
        """
            True if sync is working
            @return bool
        """
        try:
            if self.__username:
                self.__get_session_bulk_keys()
                self.__firefox_sync.client.info_collections()
                return True
        except Exception as e:
            Logger.error("SyncWorker::status(): %s", e)

    @property
    def username(self):
        """
            Get username
            @return str
        """
        return self.__username

#######################
# PRIVATE             #
#######################
    @property
    def __firefox_sync(self):
        """
            Get firefox sync, create if None
        """
        if self.__mz is None:
            self.__mz = FirefoxSync()
        return self.__mz

    def __get_session_bulk_keys(self):
        """
            Get session decrypt keys
            @return keys as (b"", b"")
        """
        if self.__session is None:
            from fxa.core import Session as FxASession
            from fxa.crypto import quick_stretch_password
            self.__session = FxASession(self.__firefox_sync.fxa_client,
                                        self.__username,
                                        quick_stretch_password(
                                            self.__username,
                                            self.__password),
                                        self.__uid,
                                        self.__token)
            self.__session.keys = [b"", self.__keyB]
        self.__session.check_session_status()
        bid_assertion, key = self.__firefox_sync.get_browserid_assertion(
            self.__session)
        bulk_keys = self.__firefox_sync.connect(bid_assertion, key)
        return bulk_keys

    def __update_state(self):
        """
            Update state file
        """
        try:
            f = open(EOLIE_DATA_PATH + "/firefox_sync.bin", "wb")
            # Lock file
            flock(f, LOCK_EX | LOCK_NB)
            self.__mtimes = self.__firefox_sync.client.info_collections()
            dump(self.__mtimes, f)
            # Unlock file
            flock(f, LOCK_UN)
        except Exception as e:
            # Not an error, just the lock exception
            Logger.info("SyncWorker::__update_state(): %s", e)

    def __sync_pendings(self):
        """
            Sync pendings record
        """
        try:
            if Gio.NetworkMonitor.get_default().get_network_available() and\
                    self.__username and not self.__syncing_pendings:
                self.__syncing_pendings = True
                Logger.debug("Elements to push to Firefox sync: %s",
                             self.__pending_records)
                self.__check_worker()
                bulk_keys = self.__get_session_bulk_keys()
                for key in self.__pending_records.keys():
                    while self.__pending_records[key]:
                        try:
                            record = self.__pending_records[key].pop(0)
                            Logger.sync_debug("syncing %s", record)
                            self.__firefox_sync.add(record, key, bulk_keys)
                        except:
                            self.__pending_records[key].append(record)
                self.__update_state()
                self.__syncing_pendings = False
        except Exception as e:
            Logger.error("SyncWorker::__sync_pendings(): %s", e)
            self.__syncing_pendings = False

    def __push_history(self, history_id, sync=True):
        """
            Push history item
            @param history is as int
            @param sync as bool
        """
        try:
            record = {}
            atimes = App().history.get_atimes(history_id)
            guid = App().history.get_guid(history_id)
            record["histUri"] = App().history.get_uri(history_id)
            record["id"] = guid
            record["title"] = App().history.get_title(history_id)
            record["visits"] = []
            for atime in atimes:
                record["visits"].append({"date": atime * 1000000,
                                         "type": 1})
            self.__pending_records["history"].append(record)
            if sync:
                self.__sync_pendings()
        except Exception as e:
            Logger.error("SyncWorker::__push_history(): %s", e)

    def __push_bookmark(self, bookmark_id, sync=True):
        """
            Push bookmark
            @param bookmark_id as int
            @param sync as bool
        """
        try:
            parent_guid = App().bookmarks.get_parent_guid(bookmark_id)
            # No parent, move it to unfiled
            if parent_guid is None:
                parent_guid = "unfiled"
            parent_id = App().bookmarks.get_id_by_guid(parent_guid)
            record = {}
            record["bmkUri"] = App().bookmarks.get_uri(bookmark_id)
            record["id"] = App().bookmarks.get_guid(bookmark_id)
            record["title"] = App().bookmarks.get_title(bookmark_id)
            record["tags"] = App().bookmarks.get_tags(bookmark_id)
            record["parentid"] = parent_guid
            record["parentName"] = App().bookmarks.get_parent_name(bookmark_id)
            record["type"] = "bookmark"
            self.__pending_records["bookmarks"].append(record)
            parent_guid = App().bookmarks.get_guid(parent_id)
            parent_name = App().bookmarks.get_title(parent_id)
            children = App().bookmarks.get_children(parent_guid)
            record = {}
            record["id"] = parent_guid
            record["type"] = "folder"
            # A parent with parent as unfiled needs to be moved to places
            # Firefox internal
            grand_parent_guid = App().bookmarks.get_parent_guid(parent_id)
            if grand_parent_guid == "unfiled":
                grand_parent_guid = "places"
            record["parentid"] = grand_parent_guid
            record["parentName"] = App().bookmarks.get_parent_name(parent_id)
            record["title"] = parent_name
            record["children"] = children
            self.__pending_records["bookmarks"].append(record)
            if sync:
                self.__sync_pendings()
        except Exception as e:
            Logger.error("SyncWorker::__push_bookmark(): %s", e)

    def __push_password(self, user_form_name, user_form_value, pass_form_name,
                        pass_form_value, uri, form_uri, uuid, sync=True):
        """
            Push password
            @param user_form_name as str
            @param user_form_value as str
            @param pass_form_name as str
            @param pass_form_value as str
            @param uri as str
            @param uuid as str
            @param sync as bool
        """
        try:
            record = {}
            record["id"] = "{%s}" % uuid
            record["hostname"] = uri
            record["formSubmitURL"] = form_uri
            record["httpRealm"] = None
            record["username"] = user_form_value
            record["password"] = pass_form_value
            record["usernameField"] = user_form_name
            record["passwordField"] = pass_form_name
            mtime = int(time() * 1000)
            record["timeCreated"] = mtime
            record["timePasswordChanged"] = mtime
            self.__pending_records["passwords"].append(record)
            if sync:
                self.__sync_pendings()
        except Exception as e:
            Logger.error("SyncWorker::__push_password(): %s", e)

    def __remove_from_history(self, guid, sync=True):
        """
            Remove from history
            @param guid as str
            @param sync as bool
        """
        try:
            record = {}
            record["id"] = guid
            record["type"] = "item"
            record["deleted"] = True
            self.__pending_records["history"].append(record)
            if sync:
                self.__sync_pendings()
        except Exception as e:
            Logger.sync_debug("SyncWorker::__remove_from_history(): %s", e)

    def __remove_from_bookmarks(self, guid, sync=True):
        """
            Remove from history
            @param guid as str
            @param sync as bool
        """
        try:
            record = {}
            record["id"] = guid
            record["type"] = "bookmark"
            record["deleted"] = True
            self.__pending_records["bookmarks"].append(record)
            if sync:
                self.__sync_pendings()
        except Exception as e:
            Logger.sync_debug("SyncWorker::__remove_from_bookmarks(): %s", e)

    def __remove_from_passwords(self, uuid, sync=True):
        """
            Remove password from passwords collection
            @param uuid as str
            @param sync as bool
        """
        try:
            record = {}
            record["id"] = uuid
            record["deleted"] = True
            self.__pending_records["passwords"].append(record)
            if sync:
                self.__sync_pendings()
        except Exception as e:
            Logger.sync_debug("SyncWorker::__remove_from_passwords(): %s", e)

    def __pull(self, force):
        """
            Pull bookmarks, history, ... from Firefox Sync
            @param force as bool
        """
        if self.__syncing:
            return
        Logger.sync_debug("Start pulling")
        GLib.idle_add(self.emit, "syncing", True)
        self.__syncing = True
        self.__sync_cancellable.cancel()
        self.__sync_cancellable = Gio.Cancellable()
        try:
            if force:
                raise
            self.__mtimes = load(open(EOLIE_DATA_PATH + "/firefox_sync.bin",
                                      "rb"))
        except:
            self.__mtimes = {"bookmarks": 0.1,
                             "history": 0.1,
                             "passwords": 0.1}
        try:
            self.__check_worker()

            bulk_keys = self.__get_session_bulk_keys()
            new_mtimes = self.__firefox_sync.client.info_collections()

            self.__check_worker()
            ########################
            # Passwords Management #
            ########################
            try:
                Logger.sync_debug("local passwords: %s, remote passwords: %s",
                                  self.__mtimes["passwords"],
                                  new_mtimes["passwords"])
                # Only pull if something new available
                if self.__mtimes["passwords"] != new_mtimes["passwords"]:
                    self.__pull_passwords(bulk_keys)
            except:
                pass  # No passwords in sync

            self.__check_worker()
            ######################
            # History Management #
            ######################
            try:
                Logger.sync_debug("local history: %s, remote history: %s",
                                  self.__mtimes["history"],
                                  new_mtimes["history"])
                # Only pull if something new available
                if self.__mtimes["history"] != new_mtimes["history"]:
                    self.__pull_history(bulk_keys)
            except:
                pass

            self.__check_worker()
            ########################
            # Bookmarks Management #
            ########################
            try:
                Logger.sync_debug("local bookmarks: %s, remote bookmarks: %s",
                                  self.__mtimes["bookmarks"],
                                  new_mtimes["bookmarks"])
                # Only pull if something new available
                if self.__mtimes["bookmarks"] != new_mtimes["bookmarks"]:
                    self.__pull_bookmarks(bulk_keys)
            except:
                pass
            self.__update_state()
            Logger.sync_debug("Stop pulling")
        except Exception as e:
            Logger.error("SyncWorker::__pull(): %s", e)
        GLib.idle_add(self.emit, "syncing", False)
        self.__syncing = False

    def __push(self):
        """
            Push bookmarks, history, ... to Firefox Sync
            @param force as bool
        """
        if self.__syncing:
            return
        Logger.sync_debug("Start pushing")
        GLib.idle_add(self.emit, "syncing", True)
        self.__syncing = True
        self.__sync_cancellable.cancel()
        self.__sync_cancellable = Gio.Cancellable()
        try:
            self.__check_worker()

            ########################
            # Passwords Management #
            ########################
            self.__helper.get_all(self.__on_helper_get_all)

            self.__check_worker()
            ######################
            # History Management #
            ######################
            for history_id in App().history.get_from_atime(0):
                self.__push_history(history_id, False)

            self.__check_worker()
            ########################
            # Bookmarks Management #
            ########################
            for (bookmark_id, title, uri) in App().bookmarks.get_bookmarks():
                self.__push_bookmark(bookmark_id, False)
            self.__check_worker()
            self.__sync_pendings()
            Logger.sync_debug("Stop pushing")
        except Exception as e:
            Logger.error("SyncWorker::__push(): %s", e)
        GLib.idle_add(self.emit, "syncing", False)
        self.__syncing = False

    def __pull_bookmarks(self, bulk_keys):
        """
            Pull from bookmarks
            @param bulk_keys as KeyBundle
            @raise StopIteration
        """
        Logger.sync_debug("pull bookmarks")
        SqlCursor.add(App().bookmarks)
        records = self.__firefox_sync.get_records("bookmarks", bulk_keys)
        children_array = []
        for record in records:
            self.__check_worker()
            if record["modified"] < self.__mtimes["bookmarks"]:
                continue
            sleep(0.01)
            bookmark = record["payload"]
            bookmark_id = App().bookmarks.get_id_by_guid(bookmark["id"])
            # Nothing to apply, continue
            if App().bookmarks.get_mtime(bookmark_id) >= record["modified"]:
                continue
            Logger.sync_debug("pulling %s", record)
            # Deleted bookmark
            if "deleted" in bookmark.keys():
                App().bookmarks.remove(bookmark_id)
            # Keep folder only for firefox compatiblity
            elif "type" in bookmark.keys() and bookmark["type"] == "folder"\
                    and bookmark["id"] is not None\
                    and bookmark["title"]:
                if bookmark_id is None:
                    bookmark_id = App().bookmarks.add(bookmark["title"],
                                                      bookmark["id"],
                                                      bookmark["id"],
                                                      [],
                                                      0)
                # Will calculate position later
                if "children" in bookmark.keys():
                    children_array.append(bookmark["children"])
            # We have a bookmark, add it
            elif "type" in bookmark.keys() and bookmark["type"] == "bookmark"\
                    and bookmark["id"] is not None\
                    and bookmark["title"]:
                # Update bookmark
                if bookmark_id is not None:
                    App().bookmarks.set_title(bookmark_id,
                                              bookmark["title"])
                    App().bookmarks.set_uri(bookmark_id,
                                            bookmark["bmkUri"])
                    # Update tags
                    current_tags = App().bookmarks.get_tags(bookmark_id)
                    for tag in App().bookmarks.get_tags(bookmark_id):
                        if "tags" in bookmark.keys() and\
                                tag not in bookmark["tags"]:
                            tag_id = App().bookmarks.get_tag_id(tag)
                            current_tags.remove(tag)
                            App().bookmarks.del_tag_from(tag_id,
                                                         bookmark_id)
                    if "tags" in bookmark.keys():
                        for tag in bookmark["tags"]:
                            # Tag already associated
                            if tag in current_tags:
                                continue
                            tag_id = App().bookmarks.get_tag_id(tag)
                            if tag_id is None:
                                tag_id = App().bookmarks.add_tag(tag)
                            App().bookmarks.add_tag_to(tag_id,
                                                       bookmark_id)
                # Add a new bookmark
                else:
                    bookmark_id = App().bookmarks.get_id(bookmark["bmkUri"])
                    # Add a new bookmark
                    if bookmark_id is None:
                        # Use parent name if no bookmarks tags
                        if "tags" not in bookmark.keys() or\
                                not bookmark["tags"]:
                            if "parentName" in bookmark.keys() and\
                                    bookmark["parentName"]:
                                bookmark["tags"] = [bookmark["parentName"]]
                            else:
                                bookmark["tags"] = []
                        bookmark_id = App().bookmarks.add(bookmark["title"],
                                                          bookmark["bmkUri"],
                                                          bookmark["id"],
                                                          bookmark["tags"],
                                                          0)
                    else:
                        # Update guid
                        App().bookmarks.set_guid(bookmark_id, bookmark["id"])
            # Update parent name if available
            if bookmark_id is not None and "parentName" in bookmark.keys():
                App().bookmarks.set_parent(bookmark_id,
                                           bookmark["parentid"],
                                           bookmark["parentName"])
            App().bookmarks.set_mtime(bookmark_id,
                                      record["modified"])
        # Update bookmark position
        for children in children_array:
            position = 0
            for child in children:
                bid = App().bookmarks.get_id_by_guid(child)
                App().bookmarks.set_position(bid,
                                             position)
                position += 1
        App().bookmarks.clean_tags()  # Will commit
        SqlCursor.remove(App().bookmarks)

    def __pull_passwords(self, bulk_keys):
        """
            Pull from passwords
            @param bulk_keys as KeyBundle
            @raise StopIteration
        """
        Logger.sync_debug("pull passwords")
        records = self.__firefox_sync.get_records("passwords", bulk_keys)
        for record in records:
            self.__check_worker()
            if record["modified"] < self.__mtimes["passwords"]:
                continue
            sleep(0.01)
            Logger.sync_debug("pulling %s", record)
            password = record["payload"]
            password_id = password["id"].strip("{}")
            if "formSubmitURL" in password.keys():
                self.__helper.clear(password_id,
                                    self.__helper.store,
                                    password["usernameField"],
                                    password["username"],
                                    password["passwordField"],
                                    password["password"],
                                    password["hostname"],
                                    password["formSubmitURL"],
                                    password_id,
                                    None)
            elif "deleted" in password.keys():  # We assume True
                self.__helper.clear(password_id)

    def __pull_history(self, bulk_keys):
        """
            Pull from history
            @param bulk_keys as KeyBundle
            @raise StopIteration
        """
        Logger.sync_debug("pull history")
        records = self.__firefox_sync.get_records("history", bulk_keys)
        for record in records:
            self.__check_worker()
            if record["modified"] < self.__mtimes["history"]:
                continue
            sleep(0.01)
            history = record["payload"]
            keys = history.keys()
            history_id = App().history.get_id_by_guid(history["id"])
            # Check we have a valid history item
            if "histUri" in keys and\
                    "title" in keys and\
                    history["title"] and\
                    App().history.get_mtime(history_id) < record["modified"]:
                # Try to get visit date
                atimes = []
                try:
                    for visit in history["visits"]:
                        atimes.append(round(int(visit["date"]) / 1000000, 2))
                except:
                    continue
                Logger.sync_debug("pulling %s", record)
                title = history["title"].rstrip().lstrip()
                history_id = App().history.add(title,
                                               history["histUri"],
                                               record["modified"],
                                               history["id"],
                                               atimes,
                                               True)
            elif "deleted" in keys:
                history_id = App().history.get_id_by_guid(history_id)
                App().history.remove(history_id)

    def __set_credentials(self, attributes, password, uri, index, count):
        """
            Set credentials
            @param attributes as {}
            @param password as str
            @param uri as None
            @param index as int
            @param count as int
        """
        if attributes is None:
            return
        from base64 import b64decode
        import json
        try:
            self.__username = attributes["login"]
            record = json.loads(password)
            self.__token = record["token"]
            self.__uid = record["uid"]
            self.__keyB = b64decode(record["keyB"])
            self.pull()
        except Exception as e:
            Logger.error("SyncWorker::__set_credentials(): %s" % e)

    def __check_worker(self):
        """
            Raise an exception if worker should not be syncing: error&cancel
        """
        if self.__sync_cancellable.is_cancelled():
            raise StopIteration("SyncWorker: cancelled")
        elif not self.__username:
            raise StopIteration("SyncWorker: missing username")
        elif not self.__token:
            raise StopIteration("SyncWorker: missing token")

    def __on_helper_get_all(self, attributes, password, uri, index, count):
        """
            Push password
            @param attributes as {}
            @param password as str
            @param uri as None
            @param index as int
            @param count as int
        """
        if attributes is None:
            return
        try:
            self.__check_worker()
            user_form_name = attributes["login"]
            user_form_value = attributes["userform"]
            pass_form_name = attributes["passform"]
            pass_form_value = password
            uri = attributes["hostname"]
            form_uri = attributes["formSubmitURL"]
            uuid = attributes["uuid"]
            task_helper = TaskHelper()
            task_helper.run(self.__push_password,
                            user_form_name, user_form_value, pass_form_name,
                            pass_form_value, uri, form_uri, uuid, False)
        except Exception as e:
            Logger.error("SyncWorker::__on_helper_get_all(): %s" % e)


class FirefoxSync(object):
    """
        Sync client
    """

    def __init__(self):
        """
            Init client
        """
        from fxa.core import Client as FxAClient
        self.__fxa_client = FxAClient()

    def login(self, login, password, code):
        """
            Login to FxA and get the keys.
            @param login as str
            @param password as str
            @param code as str
            @return fxaSession
        """
        fxaSession = self.__fxa_client.login(login, password, keys=True)
        if code:
            fxaSession.totp_verify(code)
        fxaSession.fetch_keys()
        return fxaSession

    def connect(self, bid_assertion, key):
        """
            Connect to sync using FxA browserid assertion
            @param session as fxaSession
            @return bundle keys as KeyBundle
        """
        state = None
        if key is not None:
            from binascii import hexlify
            state = hexlify(sha256(key).digest()[0:16])
        self.__client = SyncClient(bid_assertion, state)
        sync_keys = KeyBundle.fromMasterKey(
            key,
            "identity.mozilla.com/picl/v1/oldsync")

        # Fetch the sync bundle keys out of storage.
        # They're encrypted with the account-level key.
        keys = self.__decrypt_payload(self.__client.get_record("crypto",
                                                               "keys"),
                                      sync_keys)

        # There's some provision for using separate
        # key bundles for separate collections
        # but I haven't bothered digging through
        # to see what that's about because
        # it doesn't seem to be in use, at least on my account.
        if keys["collections"]:
            Logger.error("""no support for per-collection
                            key bundles yet sorry :-(""")
            return None

        # Now use those keys to decrypt the records of interest.
        from base64 import b64decode
        bulk_keys = KeyBundle(b64decode(keys["default"][0]),
                              b64decode(keys["default"][1]))
        return bulk_keys

    def get_records(self, collection, bulk_keys):
        """
            Return records payload
            @param collection as str
            @param bulk keys as KeyBundle
            @return [{}]
        """
        records = []
        for record in self.__client.get_records(collection):
            record["payload"] = self.__decrypt_payload(record, bulk_keys)
            records.append(record)
        return records

    def add(self, item, collection, bulk_keys):
        """
            Add bookmark
            @param bookmark as {}
            @param collection as str
            @param bulk_keys as KeyBundle
        """
        payload = self.__encrypt_payload(item, bulk_keys)
        record = {}
        record["modified"] = round(time(), 2)
        record["payload"] = payload
        record["id"] = item["id"]
        self.__client.put_record(collection, record)

    def get_browserid_assertion(self, session,
                                tokenserver_url=TOKENSERVER_URL):
        """
            Get browser id assertion and state
            @param session as fxaSession
            @return (bid_assertion, state) as (str, str)
        """
        bid_assertion = session.get_identity_assertion(tokenserver_url)
        return bid_assertion, session.keys[1]

    @property
    def client(self):
        """
            Get client
        """
        return self.__client

    @property
    def fxa_client(self):
        """
            Get fxa client
        """
        return self.__fxa_client

#######################
# PRIVATE             #
#######################
    def __encrypt_payload(self, record, key_bundle):
        """
            Encrypt payload
            @param record as {}
            @param key bundle as KeyBundle
            @return encrypted record payload
        """
        from Crypto.Cipher import AES
        from Crypto import Random
        from hmac import new
        from base64 import b64encode
        plaintext = json.dumps(record).encode("utf-8")
        # Input strings must be a multiple of 16 in length
        length = 16 - (len(plaintext) % 16)
        plaintext += bytes([length]) * length
        iv = Random.new().read(16)
        aes = AES.new(key_bundle.encryption_key, AES.MODE_CBC, iv)
        ciphertext = b64encode(aes.encrypt(plaintext))
        _hmac = new(key_bundle.hmac_key, ciphertext, sha256).hexdigest()
        payload = {"ciphertext": ciphertext.decode("utf-8"),
                   "IV": b64encode(iv).decode("utf-8"), "hmac": _hmac}
        return json.dumps(payload)

    def __decrypt_payload(self, record, key_bundle):
        """
            Descrypt payload
            @param record as str (json)
            @param key bundle as KeyBundle
            @return uncrypted record payload
        """
        from Crypto.Cipher import AES
        from hmac import new
        from base64 import b64decode
        j = json.loads(record["payload"])
        # Always check the hmac before decrypting anything.
        expected_hmac = new(key_bundle.hmac_key,
                            j['ciphertext'].encode("utf-8"),
                            sha256).hexdigest()
        if j['hmac'] != expected_hmac:
            raise ValueError("HMAC mismatch: %s != %s" % (j['hmac'],
                                                          expected_hmac))
        ciphertext = b64decode(j['ciphertext'])
        iv = b64decode(j['IV'])
        aes = AES.new(key_bundle.encryption_key, AES.MODE_CBC, iv)
        plaintext = aes.decrypt(ciphertext).strip().decode("utf-8")
        # Remove any CBC block padding,
        # assuming it's a well-formed JSON payload.
        plaintext = plaintext[:plaintext.rfind("}") + 1]
        return json.loads(plaintext)


class KeyBundle:
    """
        RFC-5869
    """

    def __init__(self, encryption_key, hmac_key):
        self.encryption_key = encryption_key
        self.hmac_key = hmac_key

    @classmethod
    def fromMasterKey(cls, master_key, info):
        key_material = KeyBundle.HKDF(master_key, None, info, 2 * 32)
        return cls(key_material[:32], key_material[32:])

    def HKDF_extract(salt, IKM, hashmod=sha256):
        """
            Extract a pseudorandom key suitable for use with HKDF_expand
            @param salt as str
            @param IKM as str
        """
        from hmac import new
        if salt is None:
            salt = b"\x00" * hashmod().digest_size
        return new(salt, IKM, hashmod).digest()

    def HKDF_expand(PRK, info, length, hashmod=sha256):
        """
            Expand pseudo random key and info
            @param PRK as str
            @param info as str
            @param length as int
        """
        from hmac import new
        from math import ceil
        digest_size = hashmod().digest_size
        N = int(ceil(length * 1.0 / digest_size))
        assert N <= 255
        T = b""
        output = []
        for i in range(1, N + 1):
            data = T + (info + chr(i)).encode()
            T = new(PRK, data, hashmod).digest()
            output.append(T)
        return b"".join(output)[:length]

    def HKDF(secret, salt, info, length, hashmod=sha256):
        """
            HKDF-extract-and-expand as a single function.
            @param secret as str
            @param salt as str
            @param info as str
            @param length as int
        """
        PRK = KeyBundle.HKDF_extract(salt, secret, hashmod)
        return KeyBundle.HKDF_expand(PRK, info, length, hashmod)


class TokenserverClient(object):
    """
        Client for the Firefox Sync Token Server.
    """

    def __init__(self, bid_assertion, client_state,
                 server_url=TOKENSERVER_URL):
        """
            Init client
            @param bid assertion as str
            @param client_state as ???
            @param server_url as str
        """
        self.__bid_assertion = bid_assertion
        self.__client_state = client_state
        self.__server_url = server_url

    def get_hawk_credentials(self, duration=None):
        """
            Asks for new temporary token given a BrowserID assertion
            @param duration as str
        """
        from requests import get
        authorization = 'BrowserID %s' % self.__bid_assertion
        headers = {
            'Authorization': authorization,
            'X-Client-State': self.__client_state
        }
        params = {}

        if duration is not None:
            params['duration'] = int(duration)

        url = self.__server_url.rstrip('/') + '/1.0/sync/1.5'
        raw_resp = get(url, headers=headers, params=params, verify=True)
        raw_resp.raise_for_status()
        return raw_resp.json()


class SyncClient(object):
    """
        Client for the Firefox Sync server.
    """

    def __init__(self, bid_assertion=None, client_state=None,
                 credentials={}, tokenserver_url=TOKENSERVER_URL):
        """
            Init client
            @param bid assertion as str
            @param client_state as ???
            @param credentials as {}
            @param server_url as str
        """
        from requests_hawk import HawkAuth
        if bid_assertion is not None and client_state is not None:
            ts_client = TokenserverClient(bid_assertion, client_state,
                                          tokenserver_url)
            credentials = ts_client.get_hawk_credentials()
        self.__user_id = credentials['uid']
        self.__api_endpoint = credentials['api_endpoint']
        self.__auth = HawkAuth(algorithm=credentials['hashalg'],
                               id=credentials['id'],
                               key=credentials['key'])

    def _request(self, method, url, **kwargs):
        """
            Utility to request an endpoint with the correct authentication
            setup, raises on errors and returns the JSON.
            @param method as str
            @param url as str
            @param kwargs as requests.request named args
        """
        from requests import request, exceptions
        url = self.__api_endpoint.rstrip('/') + '/' + url.lstrip('/')
        raw_resp = request(method, url, auth=self.__auth, **kwargs)
        raw_resp.raise_for_status()

        if raw_resp.status_code == 304:
            http_error_msg = '%s Client Error: %s for url: %s' % (
                raw_resp.status_code,
                raw_resp.reason,
                raw_resp.url)
            raise exceptions.HTTPError(http_error_msg, response=raw_resp)
        return raw_resp.json()

    def info_collections(self, **kwargs):
        """
            Returns an object mapping collection names associated with the
            account to the last-modified time for each collection.

            The server may allow requests to this endpoint to be authenticated
            with an expired token, so that clients can check for server-side
            changes before fetching an updated token from the Token Server.
        """
        return self._request('get', '/info/collections', **kwargs)

    def info_quota(self, **kwargs):
        """
            Returns a two-item list giving the user's current usage and quota
            (in KB). The second item will be null if the server
            does not enforce quotas.

            Note that usage numbers may be approximate.
        """
        return self._request('get', '/info/quota', **kwargs)

    def get_collection_usage(self, **kwargs):
        """
            Returns an object mapping collection names associated with the
            account to the data volume used for each collection (in KB).

            Note that these results may be very expensive as it calculates more
            detailed and accurate usage information than the info_quota method.
        """
        return self._request('get', '/info/collection_usage', **kwargs)

    def get_collection_counts(self, **kwargs):
        """
            Returns an object mapping collection names associated with the
            account to the total number of items in each collection.
        """
        return self._request('get', '/info/collection_counts', **kwargs)

    def delete_all_records(self, **kwargs):
        """
            Deletes all records for the user
        """
        return self._request('delete', '/', **kwargs)

    def get_records(self, collection, full=True, ids=None, newer=None,
                    limit=None, offset=None, sort=None, **kwargs):
        """
            Returns a list of the BSOs contained in a collection. For example:

            >>> ["GXS58IDC_12", "GXS58IDC_13", "GXS58IDC_15"]

            By default only the BSO ids are returned, but full objects can be
            requested using the full parameter. If the collection does not
            exist, an empty list is returned.

            :param ids:
                a comma-separated list of ids. Only objects whose id is in
                this list will be returned. A maximum of 100 ids may be
                provided.

            :param newer:
                a timestamp. Only objects whose last-modified time is strictly
                greater than this value will be returned.

            :param full:
                any value. If provided then the response will be a list of full
                BSO objects rather than a list of ids.

            :param limit:
                a positive integer. At most that many objects will be returned.
                If more than that many objects matched the query,
                an X-Weave-Next-Offset header will be returned.

            :param offset:
                a string, as returned in the X-Weave-Next-Offset header of a
                previous request using the limit parameter.

            :param sort:
                sorts the output:
                "newest" - orders by last-modified time, largest first
                "index" - orders by the sortindex, highest weight first
                "oldest" - orders by last-modified time, oldest first
        """
        params = kwargs.pop('params', {})
        if full:
            params['full'] = True
        if ids is not None:
            params['ids'] = ','.join(map(str, ids))
        if newer is not None:
            params['newer'] = newer
        if limit is not None:
            params['limit'] = limit
        if offset is not None:
            params['offset'] = offset
        if sort is not None and sort in ('newest', 'index', 'oldest'):
            params['sort'] = sort

        return self._request('get', '/storage/%s' % collection.lower(),
                             params=params, **kwargs)

    def get_record(self, collection, record_id, **kwargs):
        """Returns the BSO in the collection corresponding to the requested id.
        """
        return self._request('get', '/storage/%s/%s' % (collection.lower(),
                                                        record_id), **kwargs)

    def delete_record(self, collection, record_id, **kwargs):
        """Deletes the BSO at the given location.
        """
        try:
            return self._request('delete', '/storage/%s/%s' % (
                collection.lower(), record_id), **kwargs)
        except Exception as e:
            Logger.error("SyncClient::delete_record(): %s", e)

    def put_record(self, collection, record, **kwargs):
        """
            Creates or updates a specific BSO within a collection.
            The passed record must be a python object containing new data for
            the BSO.

            If the target BSO already exists then it will be updated with the
            data from the request body. Fields that are not provided will not
            be overwritten, so it is possible to e.g. update the ttl field of a
            BSO without re-submitting its payload. Fields that are explicitly
            set to null in the request body will be set to their default value
            by the server.

            If the target BSO does not exist, then fields that are not provided
            in the python object will be set to their default value
            by the server.

            Successful responses will return the new last-modified time for the
            collection.

            Note that the server may impose a limit on the amount of data
            submitted for storage in a single BSO.
        """
        import six
        # XXX: Workaround until request-hawk supports the json parameter. (#17)
        if isinstance(record, six.string_types):
            record = json.loads(record)
        record = record.copy()
        record_id = record.pop('id')
        headers = {}
        if 'headers' in kwargs:
            headers = kwargs.pop('headers')
        headers['Content-Type'] = 'application/json; charset=utf-8'

        return self._request('put', '/storage/%s/%s' % (
            collection.lower(), record_id), data=json.dumps(record),
            headers=headers, **kwargs)
