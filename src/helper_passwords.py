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

import gi
gi.require_version('Secret', '1')
from gi.repository import Secret, GLib

from urllib.parse import urlparse


class PasswordsHelper:
    """
        Simpler helper for Secret
    """

    def __init__(self):
        """
            Init helper
        """
        self.__secret = None
        Secret.Service.get(Secret.ServiceFlags.NONE, None,
                           self.__on_get_secret)

    def get(self, uri, callback, *args):
        """
            Call function
            @param uri as str
            @param callback as function
            @param args
        """
        try:
            self.__wait_for_secret(self.get, uri, callback, *args)
            parsed = urlparse(uri)
            SecretSchema = {
                "type": Secret.SchemaAttributeType.STRING,
                "uri": Secret.SchemaAttributeType.STRING,
            }
            SecretAttributes = {
                "type": "eolie web login",
                "uri": parsed.netloc,
            }
            schema = Secret.Schema.new("org.gnome.Eolie",
                                       Secret.SchemaFlags.NONE,
                                       SecretSchema)
            self.__secret.search(schema, SecretAttributes,
                                 Secret.SearchFlags.NONE,
                                 None,
                                 self.__on_secret_search,
                                 callback,
                                 *args)
        except Exception as e:
            print("PasswordsHelper::get():", e)

    def get_sync(self, callback, *args):
        """
            Get sync password
            @param callback as function
        """
        try:
            self.__wait_for_secret(self.get_sync, callback, *args)
            SecretSchema = {
                "sync": Secret.SchemaAttributeType.STRING
            }
            SecretAttributes = {
                "sync": "mozilla"
            }
            schema = Secret.Schema.new("org.gnome.Eolie",
                                       Secret.SchemaFlags.NONE,
                                       SecretSchema)
            self.__secret.search(schema, SecretAttributes,
                                 Secret.SearchFlags.NONE,
                                 None,
                                 self.__on_secret_search,
                                 callback,
                                 *args)
        except Exception as e:
            print("PasswordsHelper::get_sync():", e)

    def store_sync_password(self, login, password, uid, token, keyB, callback):
        """
            Store Mozilla Sync password
            @param login as str
            @param password as str
            @param uid as str
            @param token as str
            @param keyB as str
            @param callback as function
        """
        try:
            self.__wait_for_secret(self.store_sync_password,
                                   login,
                                   password,
                                   uid,
                                   token,
                                   keyB,
                                   callback)
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
                                  callback)
        except Exception as e:
            print("PasswordsHelper::store_sync_password():", e)

    def clear(self):
        """
            Clear passwords
        """
        try:
            self.__wait_for_secret(self.clear)
            SecretSchema = {
                "type": Secret.SchemaAttributeType.STRING
            }
            SecretAttributes = {
                "type": "eolie web login"
            }
            schema = Secret.Schema.new("org.gnome.Eolie",
                                       Secret.SchemaFlags.NONE,
                                       SecretSchema)
            self.__secret.search(schema,
                                 SecretAttributes,
                                 Secret.SearchFlags.ALL,
                                 None,
                                 self.__on_clear_search)
        except Exception as e:
            print("PasswordsHelper::clear():", e)

#######################
# PRIVATE             #
#######################
    def __wait_for_secret(self, call, *args):
        """
            Wait for secret
            @param call as function to call
            @param args
            @raise exception if waiting
        """
        # Wait for secret
        if self.__secret is None:
            GLib.timeout_add(1000, call, *args)
        if self.__secret in [None, -1]:
            raise Exception("Waiting Secret service")

    def __on_load_secret(self, source, result, callback, *args):
        """
            Set username/password input
            @param source as GObject.Object
            @param result as Gio.AsyncResult
            @param callback as function
            @param args
        """
        try:
            secret = source.get_secret()
            if secret is not None:
                callback(source.get_attributes(),
                         secret.get().decode('utf-8'),
                         *args)
        except Exception as e:
            print("PasswordsHelper::__on_load_secret()", e)

    def __on_clear_search(self, source, result):
        """
            Clear passwords
            @param source as GObject.Object
            @param result as Gio.AsyncResult
        """
        try:
            if result is not None:
                items = source.search_finish(result)
                for item in items:
                    item.delete(None, None)
        except Exception as e:
            print("SettingsDialog::__on_clear_search()", e)

    def __on_secret_search(self, source, result, callback, *args):
        """
            Set username/password input
            @param source as GObject.Object
            @param result as Gio.AsyncResult
            @param callback as function
            @param args
        """
        try:
            if result is not None:
                items = self.__secret.search_finish(result)
                if not items:
                    return
                items[0].load_secret(None,
                                     self.__on_load_secret,
                                     callback,
                                     *args)
        except Exception as e:
            print("PasswordsHelper::__on_secret_search()", e)

    def __on_get_secret(self, source, result):
        """
            Store secret proxy
            @param source as GObject.Object
            @param result as Gio.AsyncResult
        """
        try:
            self.__secret = Secret.Service.get_finish(result)
        except Exception as e:
            self.__secret = -1
            print("PasswordsHelper::__on_get_secret()", e)
