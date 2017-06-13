# Copyright (c) 2017 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
# Fork of https://github.com/mozilla-services/syncclient
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

from gi.repository import Gio, GObject, GLib

from pickle import dump, load
from hashlib import sha256
import json
from time import time, sleep
from threading import Thread

from eolie.define import El, EOLIE_LOCAL_PATH
from eolie.utils import debug
from eolie.sqlcursor import SqlCursor
from eolie.helper_passwords import PasswordsHelper


TOKENSERVER_URL = "https://token.services.mozilla.com/"
FXA_SERVER_URL = "https://api.accounts.firefox.com"


class SyncWorker(GObject.GObject):
    """
       Manage sync with mozilla server, will start syncing on init
    """
    __gsignals__ = {
        "sync-finished": (GObject.SignalFlags.RUN_FIRST, None, ())
    }

    def __init__(self):
        """
            Init worker
        """
        GObject.GObject.__init__(self)
        self.__stop = True
        self.__username = ""
        self.__password = ""
        self.__mtimes = {"bookmarks": 0.1, "history": 0.1}
        self.__mozilla_sync = None
        self.__session = None
        self.__helper = PasswordsHelper()
        self.__helper.get_sync(self.__set_credentials)

    def login(self, attributes, password):
        """
            Login to service
            @param attributes as {}
            @param password as str
            @raise exceptions
        """
        if attributes is None:
            return
        from base64 import b64encode
        if self.__mozilla_sync is None:
            self.__mozilla_sync = MozillaSync()
        keyB = ""
        session = None
        # Connect to mozilla sync
        session = self.__mozilla_sync.login(attributes["login"], password)
        bid_assertion, key = self.__mozilla_sync.get_browserid_assertion(
                                                                       session)
        keyB = b64encode(session.keys[1]).decode("utf-8")
        # Store credentials
        if session is None:
            uid = ""
            token = ""
        else:
            uid = session.uid
            token = session.token
        self.__helper.store_sync(attributes["login"],
                                 password,
                                 uid,
                                 token,
                                 keyB,
                                 self.on_password_stored,
                                 True)

    def sync(self, loop=False, first_sync=False):
        """
            Start syncing, you need to check sync_status property
            @param loop as bool -> for GLib.timeout_add()
            @param first_sync as bool
        """
        if self.syncing or\
                not Gio.NetworkMonitor.get_default().get_network_available():
            return
        self.__stop = False
        thread = Thread(target=self.__sync, args=(first_sync,))
        thread.daemon = True
        thread.start()
        return loop

    def push_history(self, history_ids):
        """
            Push history ids
            @param history_ids as [int]
        """
        if Gio.NetworkMonitor.get_default().get_network_available():
            thread = Thread(target=self.__push_history,
                            args=(history_ids,))
            thread.daemon = True
            thread.start()

    def push_password(self, username, userform,
                      password, passform, uri, uuid):
        """
            Push password
            @param username as str
            @param userform as str
            @param password as str
            @param passform as str
            @param uri as str
            @param uuid as str
        """
        if Gio.NetworkMonitor.get_default().get_network_available():
            thread = Thread(target=self.__push_password,
                            args=(username, userform,
                                  password, passform,
                                  uri, uuid))
            thread.daemon = True
            thread.start()

    def remove_from_history(self, guid):
        """
            Remove history id from remote history
            A first call to sync() is needed to populate secrets
            @param guid as str
        """
        if Gio.NetworkMonitor.get_default().get_network_available():
            thread = Thread(target=self.__remove_from_history, args=(guid,))
            thread.daemon = True
            thread.start()

    def remove_from_passwords(self, uri):
        """
            Remove password from passwords collection
            @param uri as str
        """
        if Gio.NetworkMonitor.get_default().get_network_available():
            self.__helper.get(uri, self.__remove_from_passwords_thread)

    def delete_secret(self):
        """
            Delete sync secret
        """
        self.__username = ""
        self.__password = ""
        self.__session = None
        self.__stop = True
        self.__helper.clear_sync()

    def stop(self, force=False):
        """
            Stop update, if force, kill session too
            @param force as bool
        """
        self.__stop = True
        if force:
            self.__session = None

    def on_password_stored(self, secret, result, sync):
        """
            Update credentials
            @param secret as Secret
            @param result as Gio.AsyncResult
            @param sync as bool
        """
        if El().sync_worker is not None:
            self.__helper.get_sync(self.__set_credentials)
            # Wait for credentials
            if sync:
                GLib.timeout_add(10, El().sync_worker.sync, True)

    @property
    def mtimes(self):
        """
            Sync engine modification times
            @return {}
        """
        return self.__mtimes

    @property
    def syncing(self):
        """
            True if sync is running
            @return bool
        """
        return not self.__stop

    @property
    def status(self):
        """
            True if sync is working
            @return bool
        """
        try:
            if self.__mozilla_sync is None:
                self.__mozilla_sync = MozillaSync()
            self.__get_session_bulk_keys()
            self.__mozilla_sync.client.info_collections()
            return True
        except:
            return False

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
    def __get_session_bulk_keys(self):
        """
            Get session decrypt keys
            @return keys as (b"", b"")
        """
        if self.__mozilla_sync is None:
            self.__mozilla_sync = MozillaSync()
        if self.__session is None:
            from fxa.core import Session as FxASession
            from fxa.crypto import quick_stretch_password
            self.__session = FxASession(self.__mozilla_sync.fxa_client,
                                        self.__username,
                                        quick_stretch_password(
                                                        self.__username,
                                                        self.__password),
                                        self.__uid,
                                        self.__token)
            self.__session.keys = [b"", self.__keyB]
        self.__session.check_session_status()
        bid_assertion, key = self.__mozilla_sync.get_browserid_assertion(
                                                                self.__session)
        bulk_keys = self.__mozilla_sync.connect(bid_assertion, key)
        return bulk_keys

    def __push_history(self, history_ids):
        """
            Push history ids if atime is available, else, ask to remove
            @param history ids as [int]
        """
        if not self.__username or not self.__password:
            return
        try:
            bulk_keys = self.__get_session_bulk_keys()
            for history_id in history_ids:
                sleep(0.01)
                record = {}
                atimes = El().history.get_atimes(history_id)
                guid = El().history.get_guid(history_id)
                if atimes:
                    record["histUri"] = El().history.get_uri(history_id)
                    record["id"] = guid
                    record["title"] = El().history.get_title(history_id)
                    record["visits"] = []
                    for atime in atimes:
                        record["visits"].append({"date": atime*1000000,
                                                 "type": 1})
                    debug("pushing %s" % record)
                    self.__mozilla_sync.add(record, "history", bulk_keys)
                else:
                    record["id"] = guid
                    record["type"] = "item"
                    record["deleted"] = True
                    debug("deleting %s" % record)
                    self.__mozilla_sync.add(record, "history", bulk_keys)
                self.__mtimes = self.__mozilla_sync.client.info_collections()
                dump(self.__mtimes,
                     open(EOLIE_LOCAL_PATH + "/mozilla_sync.bin", "wb"))
        except Exception as e:
            print("SyncWorker::__push_history():", e)

    def __push_password(self, username, userform,
                        password, passform, uri, uuid):
        """
            Push password
            @param username as str
            @param userform as str
            @param password as str
            @param passform as str
            @param uri as str
            @param uuid as str
        """
        if not self.__username or not self.__password:
            return
        try:
            bulk_keys = self.__get_session_bulk_keys()
            record = {}
            record["id"] = "{%s}" % uuid
            record["hostname"] = uri
            record["formSubmitURL"] = uri
            record["httpRealm"] = None
            record["username"] = username
            record["password"] = password
            record["usernameField"] = userform
            record["passwordField"] = passform
            mtime = int(time()*1000)
            record["timeCreated"] = mtime
            record["timePasswordChanged"] = mtime
            debug("pushing %s" % record)
            self.__mozilla_sync.add(record, "passwords", bulk_keys)
        except Exception as e:
            print("SyncWorker::__push_password():", e)

    def __remove_from_history(self, guid):
        """
            Remove from history
            @param guid as str
        """
        if not self.__username or not self.__password:
            return
        try:
            bulk_keys = self.__get_session_bulk_keys()
            record = {}
            record["id"] = guid
            record["type"] = "item"
            record["deleted"] = True
            debug("deleting %s" % record)
            self.__mozilla_sync.add(record, "history", bulk_keys)
        except Exception as e:
            print("SyncWorker::__remove_from_history():", e)

    def __remove_from_passwords(self, attributes, password, uri):
        """
            Remove password from passwords collection
            @param attributes as {}
            @param password as str
            @param uri as str
        """
        if not self.__username or not self.__password:
            return
        try:
            bulk_keys = self.__get_session_bulk_keys()
            record = {}
            record["id"] = attributes["uuid"]
            record["deleted"] = True
            debug("deleting %s" % record)
            self.__mozilla_sync.add(record, "passwords", bulk_keys)
            self.__helper.clear(uri)
        except Exception as e:
            print("SyncWorker::__remove_from_passwords():", e)

    def __remove_from_passwords_thread(self, attributes, password, uri):
        """
            Remove password from passwords collection
            @param attributes as {}
            @param password as str
            @param uri as str
        """
        thread = Thread(target=self.__remove_from_passwords,
                        args=(attributes, password, uri))
        thread.daemon = True
        thread.start()

    def __sync(self, first_sync):
        """
            Sync Eolie objects (bookmarks, history, ...) with Mozilla Sync
            @param first_sync as bool
        """
        debug("Start syncing")
        if not self.__username or not self.__password or not self.__token:
            self.__stop = True
            return
        try:
            self.__mtimes = load(open(EOLIE_LOCAL_PATH + "/mozilla_sync.bin",
                                 "rb"))
        except:
            self.__mtimes = {"bookmarks": 0.1,
                             "history": 0.1,
                             "passwords": 0.1}
        try:
            bulk_keys = self.__get_session_bulk_keys()
            new_mtimes = self.__mozilla_sync.client.info_collections()
            if self.__stop:
                return

            ########################
            # Passwords Management #
            ########################
            try:
                debug("local passwords: %s, remote passwords: %s" % (
                                                    self.__mtimes["passwords"],
                                                    new_mtimes["passwords"]))
                # Only pull if something new available
                if self.__mtimes["passwords"] != new_mtimes["passwords"]:
                    self.__pull_passwords(bulk_keys)
            except:
                pass  # No passwords in sync

            if self.__stop:
                return
            ######################
            # History Management #
            ######################
            try:
                debug("local history: %s, remote history: %s" % (
                                                     self.__mtimes["history"],
                                                     new_mtimes["history"]))
                # Only pull if something new available
                if self.__mtimes["history"] != new_mtimes["history"]:
                    self.__pull_history(bulk_keys)
            except:
                pass  # No history in sync

            if self.__stop:
                return
            ########################
            # Bookmarks Management #
            ########################
            try:
                debug("local bookmarks: %s, remote bookmarks: %s" % (
                                                    self.__mtimes["bookmarks"],
                                                    new_mtimes["bookmarks"]))
                # Push new bookmarks
                self.__push_bookmarks(bulk_keys)
            except:
                pass  # No bookmarks in sync

            if self.__stop:
                return

            # Only pull if something new available
            if self.__mtimes["bookmarks"] != new_mtimes["bookmarks"]:
                self.__pull_bookmarks(bulk_keys, first_sync)
            # Update last sync mtime
            self.__mtimes = self.__mozilla_sync.client.info_collections()
            dump(self.__mtimes,
                 open(EOLIE_LOCAL_PATH + "/mozilla_sync.bin", "wb"))
            debug("Stop syncing")
            GLib.idle_add(self.emit, "sync-finished")
        except Exception as e:
            print("SyncWorker::__sync():", e)
            if str(e) == "The authentication token could not be found":
                self.__helper.get_sync(self.login)
        self.__stop = True

    def __push_bookmarks(self, bulk_keys):
        """
            Push to bookmarks
            @param bulk keys as KeyBundle
            @param start time as float
            @raise StopIteration
        """
        debug("push bookmarks")
        parents = []
        for bookmark_id in El().bookmarks.get_ids_for_mtime(
                                                   self.__mtimes["bookmarks"]):
            if self.__stop:
                raise StopIteration("Cancelled")
            sleep(0.01)
            parent_guid = El().bookmarks.get_parent_guid(bookmark_id)
            # No parent, move it to unfiled
            if parent_guid is None:
                parent_guid = "unfiled"
            parent_id = El().bookmarks.get_id_by_guid(parent_guid)
            if parent_id not in parents:
                parents.append(parent_id)
            record = {}
            record["bmkUri"] = El().bookmarks.get_uri(bookmark_id)
            record["id"] = El().bookmarks.get_guid(bookmark_id)
            record["title"] = El().bookmarks.get_title(bookmark_id)
            record["tags"] = El().bookmarks.get_tags(bookmark_id)
            record["parentid"] = parent_guid
            record["type"] = "bookmark"
            debug("pushing %s" % record)
            self.__mozilla_sync.add(record, "bookmarks", bulk_keys)
        # Del old bookmarks
        for bookmark_id in El().bookmarks.get_deleted_ids():
            if self.__stop:
                raise StopIteration("Cancelled")
            sleep(0.01)
            parent_guid = El().bookmarks.get_parent_guid(bookmark_id)
            parent_id = El().bookmarks.get_id_by_guid(parent_guid)
            if parent_id not in parents:
                parents.append(parent_id)
            record = {}
            record["id"] = El().bookmarks.get_guid(bookmark_id)
            record["type"] = "item"
            record["deleted"] = True
            debug("deleting %s" % record)
            self.__mozilla_sync.add(record, "bookmarks", bulk_keys)
            El().bookmarks.remove(bookmark_id)
        # Push parents in this order, parents near root are handled later
        # Otherwise, order will be broken by new children updates
        while parents:
            parent_id = parents.pop(0)
            parent_guid = El().bookmarks.get_guid(parent_id)
            parent_name = El().bookmarks.get_title(parent_id)
            children = El().bookmarks.get_children(parent_guid)
            # So search if children in parents
            found = False
            for child_guid in children:
                child_id = El().bookmarks.get_id_by_guid(child_guid)
                if child_id in parents:
                    found = True
                    break
            # Handle children first
            if found:
                parents.append(parent_id)
                debug("later: %s" % parent_name)
                continue
            record = {}
            record["id"] = parent_guid
            record["type"] = "folder"
            # A parent with parent as unfiled needs to be moved to places
            # Firefox internal
            grand_parent_guid = El().bookmarks.get_parent_guid(parent_id)
            if grand_parent_guid == "unfiled":
                grand_parent_guid = "places"
            record["parentid"] = grand_parent_guid
            record["parentName"] = El().bookmarks.get_parent_name(parent_id)
            record["title"] = parent_name
            record["children"] = children
            debug("pushing parent %s" % record)
            self.__mozilla_sync.add(record, "bookmarks", bulk_keys)
        El().bookmarks.clean_tags()

    def __pull_bookmarks(self, bulk_keys, first_sync):
        """
            Pull from bookmarks
            @param bulk_keys as KeyBundle
            @param first_sync as bool
            @raise StopIteration
        """
        debug("pull bookmarks")
        SqlCursor.add(El().bookmarks)
        records = self.__mozilla_sync.get_records("bookmarks", bulk_keys)
        children_array = []
        for record in records:
            if self.__stop:
                raise StopIteration("Cancelled")
            if record["modified"] < self.__mtimes["bookmarks"]:
                continue
            sleep(0.01)
            bookmark = record["payload"]
            bookmark_id = El().bookmarks.get_id_by_guid(bookmark["id"])
            # Nothing to apply, continue
            if El().bookmarks.get_mtime(bookmark_id) >= record["modified"]:
                continue
            debug("pulling %s" % record)
            # Keep folder only for firefox compatiblity
            if "type" in bookmark.keys() and bookmark["type"] == "folder"\
                    and bookmark["id"] is not None\
                    and bookmark["title"]:
                if bookmark_id is None:
                    bookmark_id = El().bookmarks.add(bookmark["title"],
                                                     bookmark["id"],
                                                     bookmark["id"],
                                                     [],
                                                     False)
                # Will calculate position later
                if "children" in bookmark.keys():
                    children_array.append(bookmark["children"])
            # We have a bookmark, add it
            elif "type" in bookmark.keys() and bookmark["type"] == "bookmark"\
                    and bookmark["id"] is not None\
                    and bookmark["title"]:
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
                    bookmark_id = El().bookmarks.add(bookmark["title"],
                                                     bookmark["bmkUri"],
                                                     bookmark["id"],
                                                     bookmark["tags"],
                                                     False)
                # Update bookmark
                else:
                    El().bookmarks.set_title(bookmark_id,
                                             bookmark["title"],
                                             False)
                    El().bookmarks.set_uri(bookmark_id,
                                           bookmark["bmkUri"],
                                           False)
                    # Update tags
                    current_tags = El().bookmarks.get_tags(bookmark_id)
                    for tag in El().bookmarks.get_tags(bookmark_id):
                        if "tags" in bookmark.keys() and\
                                tag not in bookmark["tags"]:
                            tag_id = El().bookmarks.get_tag_id(tag)
                            current_tags.remove(tag)
                            El().bookmarks.del_tag_from(tag_id,
                                                        bookmark_id,
                                                        False)
                    if "tags" in bookmark.keys():
                        for tag in bookmark["tags"]:
                            # Tag already associated
                            if tag in current_tags:
                                continue
                            tag_id = El().bookmarks.get_tag_id(tag)
                            if tag_id is None:
                                tag_id = El().bookmarks.add_tag(tag, False)
                            El().bookmarks.add_tag_to(tag_id,
                                                      bookmark_id,
                                                      False)
                    El().bookmarks.set_mtime(bookmark_id,
                                             record["modified"],
                                             False)
            # Deleted bookmark
            elif "deleted" in bookmark.keys():
                El().bookmarks.remove(bookmark_id)
            # Update parent name if available
            if bookmark_id is not None and "parentName" in bookmark.keys():
                El().bookmarks.set_parent(bookmark_id,
                                          bookmark["parentid"],
                                          bookmark["parentName"],
                                          False)
                El().bookmarks.set_mtime(bookmark_id,
                                         record["modified"],
                                         False)
        # Update bookmark position
        for children in children_array:
            position = 0
            for child in children:
                bid = El().bookmarks.get_id_by_guid(child)
                El().bookmarks.set_position(bid,
                                            position,
                                            False)
                position += 1
        El().bookmarks.clean_tags()  # Will commit
        SqlCursor.remove(El().bookmarks)

    def __pull_passwords(self, bulk_keys):
        """
            Pull from passwords
            @param bulk_keys as KeyBundle
            @raise StopIteration
        """
        debug("pull passwords")
        records = self.__mozilla_sync.get_records("passwords", bulk_keys)
        for record in records:
            if self.__stop:
                raise StopIteration("Cancelled")
            if record["modified"] < self.__mtimes["passwords"]:
                continue
            sleep(0.01)
            debug("pulling %s" % record)
            password = record["payload"]
            if "formSubmitURL" in password.keys():
                self.__helper.clear(password["formSubmitURL"])
                self.__helper.store(password["username"],
                                    password["password"],
                                    password["formSubmitURL"],
                                    password["id"],
                                    password["usernameField"],
                                    password["passwordField"],
                                    None)
            elif "deleted" in password.keys():  # We assume True
                self.__helper.clear(password["id"])

    def __pull_history(self, bulk_keys):
        """
            Pull from history
            @param bulk_keys as KeyBundle
            @raise StopIteration
        """
        debug("pull history")
        records = self.__mozilla_sync.get_records("history", bulk_keys)
        for record in records:
            if self.__stop:
                raise StopIteration("Cancelled")
            if record["modified"] < self.__mtimes["history"]:
                continue
            sleep(0.01)
            El().history.thread_lock.acquire()
            history = record["payload"]
            keys = history.keys()
            history_id = El().history.get_id_by_guid(history["id"])
            # Check we have a valid history item
            if "histUri" in keys and\
                    "title" in keys and\
                    history["title"] and\
                    El().history.get_mtime(history_id) < record["modified"]:
                # Try to get visit date
                atimes = []
                try:
                    for visit in history["visits"]:
                        atimes.append(round(int(visit["date"]) / 1000000, 2))
                except:
                    El().history.thread_lock.release()
                    continue
                debug("pulling %s" % record)
                title = history["title"].rstrip().lstrip()
                history_id = El().history.add(title,
                                              history["histUri"],
                                              record["modified"],
                                              history["id"],
                                              atimes,
                                              True)
            elif "deleted" in keys:
                history_id = El().history.get_id_by_guid(history_id)
                El().history.remove(history_id)
            El().history.thread_lock.release()

    def __set_credentials(self, attributes, password, uri):
        """
            Set credentials
            @param attributes as {}
            @param password as str
            @param uri as None
        """
        if attributes is None:
            return
        from base64 import b64decode
        try:
            self.__username = attributes["login"]
            self.__password = password
            self.__token = attributes["token"]
            self.__uid = attributes["uid"]
            self.__keyB = b64decode(attributes["keyB"])
            # Force login if no token
            if not self.__token:
                self.login(attributes, password)
        except Exception as e:
            print("SyncWorker::__set_credentials()", e)


class MozillaSync(object):
    """
        Sync client
    """
    def __init__(self):
        """
            Init client
        """
        from fxa.core import Client as FxAClient
        self.__fxa_client = FxAClient()

    def login(self, login, password):
        """
            Login to FxA and get the keys.
            @param login as str
            @param password as str
            @return fxaSession
        """
        fxaSession = self.__fxa_client.login(login, password, keys=True)
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
            print("no support for per-collection key bundles yet sorry :-(")
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
            print("SyncClient::delete_record()", e)

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
