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

from gi.repository import Gtk

from threading import Thread

from eolie.define import El


class SyncAuthPopover(Gtk.Popover):
    """
        Ask user for sync authentication
    """

    def __init__(self):
        """
            Init popover
        """
        Gtk.Popover.__init__(self)
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/PopoverSyncAuth.ui")
        builder.connect_signals(self)
        self.__login = builder.get_object("login")
        self.__password = builder.get_object("password")
        self.__login.set_text(El().sync_worker.username)
        self.add(builder.get_object("widget"))

#######################
# PROTECTED           #
#######################
    def _on_save_clicked(self, button):
        """
            Save username and password
            @param button as Gtk.Button
        """
        try:
            El().sync_worker.delete_secret()
            thread = Thread(target=self.__connect_mozilla_sync,
                            args=(self.__login.get_text(),
                                  self.__password.get_text()))
            thread.daemon = True
            thread.start()
            self.hide()
        except Exception as e:
            print("SyncAuthPopover::_on_save_clicked()", e)

#######################
# PRIVATE             #
#######################
    def __connect_mozilla_sync(self, login, password):
        """
            Connect to mozilla sync
            @param login as str
            @param password as str
            @thread safe
        """
        from eolie.mozilla_sync import MozillaSync
        from gi.repository import Secret
        import base64
        keyB = ""
        session = None
        # Connect to mozilla sync
        try:
            client = MozillaSync()
            session = client.login(login, password)
            bid_assertion, key = client.get_browserid_assertion(session)
            keyB = base64.b64encode(session.keys[1]).decode("utf-8")
        except Exception as e:
            print("SyncAuthPopover::__connect_mozilla_sync()", e)
        # Store credentials
        try:
            schema_string = "org.gnome.Eolie.sync"
            SecretSchema = {
                "sync": Secret.SchemaAttributeType.STRING,
                "login": Secret.SchemaAttributeType.STRING,
                "uid": Secret.SchemaAttributeType.STRING,
                "token": Secret.SchemaAttributeType.STRING,
                "keyB": Secret.SchemaAttributeType.STRING
            }
            schema = Secret.Schema.new("org.gnome.Eolie",
                                       Secret.SchemaFlags.NONE,
                                       SecretSchema)
            if session is None:
                uid = ""
                token = ""
            else:
                uid = session.uid
                token = session.token
            SecretAttributes = {
                    "sync": "mozilla",
                    "login": login,
                    "uid": uid,
                    "token": token,
                    "keyB": keyB
            }

            Secret.password_store(schema, SecretAttributes,
                                  Secret.COLLECTION_DEFAULT,
                                  schema_string,
                                  password,
                                  None,
                                  self.__on_password_stored)
        except Exception as e:
            print("SyncAuthPopover::__connect_mozilla_sync()", e)

    def __on_password_stored(self, secret, result):
        """
            Update credentials
            @param secret as Secret
            @param result as Gio.AsyncResult
        """
        if El().sync_worker is not None:
            El().sync_worker.sync(True)
