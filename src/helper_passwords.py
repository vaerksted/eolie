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
from eolie.utils import debug


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

    def get_all(self, callback, *args):
        """
            Call function
            @param callback as function
            @param args
        """
        try:
            self.__wait_for_secret(self.get_all, callback, *args)
            SecretSchema = {
                "type": Secret.SchemaAttributeType.STRING,
            }
            SecretAttributes = {
                "type": "eolie web login",
            }
            schema = Secret.Schema.new("org.gnome.Eolie",
                                       Secret.SchemaFlags.NONE,
                                       SecretSchema)
            self.__secret.search(schema, SecretAttributes,
                                 Secret.SearchFlags.ALL,
                                 None,
                                 self.__on_secret_search,
                                 None,
                                 callback,
                                 *args)
        except Exception as e:
            debug("PasswordsHelper::get_all(): %s" % e)

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
                "hostname": Secret.SchemaAttributeType.STRING
            }
            SecretAttributes = {
                "type": "eolie web login",
                "hostname": parsed.netloc
            }
            schema = Secret.Schema.new("org.gnome.Eolie",
                                       Secret.SchemaFlags.NONE,
                                       SecretSchema)
            self.__secret.search(schema, SecretAttributes,
                                 Secret.SearchFlags.ALL,
                                 None,
                                 self.__on_secret_search,
                                 uri,
                                 callback,
                                 *args)
        except Exception as e:
            debug("PasswordsHelper::get(): %s" % e)

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
                                 None,
                                 callback,
                                 *args)
        except Exception as e:
            debug("PasswordsHelper::get_sync(): %s" % e)

    def store(self, login, password, uri, uuid, userform, passform, callback):
        """
            Store password
            @param login as str
            @param password as str
            @param uri as str
            @param uuid as str
            @param userform as str
            @param passform as str
            @param callback as function
        """
        try:
            self.__wait_for_secret(self.store,
                                   login,
                                   password,
                                   uri,
                                   callback)
            parsed = urlparse(uri)
            schema_string = "org.gnome.Eolie: %s@%s" % (login,
                                                        parsed.netloc)
            SecretSchema = {
                "type": Secret.SchemaAttributeType.STRING,
                "uuid": Secret.SchemaAttributeType.STRING,
                "login": Secret.SchemaAttributeType.STRING,
                "hostname": Secret.SchemaAttributeType.STRING,
                "formSubmitURL": Secret.SchemaAttributeType.STRING,
                "userform": Secret.SchemaAttributeType.STRING,
                "passform": Secret.SchemaAttributeType.STRING,
            }
            SecretAttributes = {
                "type": "eolie web login",
                "uuid": uuid,
                "login": login,
                "hostname": parsed.netloc,
                "formSubmitURL": "%s://%s%s" % (parsed.scheme,
                                                parsed.netloc,
                                                parsed.path),
                "userform": userform,
                "passform": passform
            }
            schema = Secret.Schema.new("org.gnome.Eolie",
                                       Secret.SchemaFlags.NONE,
                                       SecretSchema)
            Secret.password_store(schema, SecretAttributes,
                                  Secret.COLLECTION_DEFAULT,
                                  schema_string,
                                  password,
                                  None,
                                  callback)
        except Exception as e:
            debug("PasswordsHelper::store(): %s" % e)

    def store_sync(self, login, password, uid, token, keyB, callback, data):
        """
            Store Mozilla Sync password
            @param login as str
            @param password as str
            @param uid as str
            @param token as str
            @param keyB as str
            @param callback as function
            @param data
        """
        try:
            self.__wait_for_secret(self.store_sync,
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
                                  callback,
                                  data)
        except Exception as e:
            debug("PasswordsHelper::store_sync(): %s" % e)

    def clear(self, uuid):
        """
            Clear password
            @param uuid as str
        """
        try:
            self.__wait_for_secret(self.clear, uuid)
            SecretSchema = {
                "type": Secret.SchemaAttributeType.STRING,
                "uuid": Secret.SchemaAttributeType.STRING
            }
            SecretAttributes = {
                "type": "eolie web login",
                "uuid": uuid
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
            debug("PasswordsHelper::clear(): %s" % e)

    def clear_sync(self):
        """
            Clear sync secrets
        """
        try:
            SecretSchema = {
                "sync": Secret.SchemaAttributeType.STRING
            }
            SecretAttributes = {
                "sync": "mozilla"
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
            debug("PasswordsHelper::clear_sync(): %s" % e)

    def clear_all(self):
        """
            Clear passwords
        """
        try:
            self.__wait_for_secret(self.clear_all)
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
            debug("PasswordsHelper::clear_all(): %s" % e)

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
            GLib.timeout_add(250, call, *args)
        if self.__secret in [None, -1]:
            raise Exception("Waiting Secret service")

    def __on_load_secret(self, source, result, uri,
                         index, count, callback, *args):
        """
            Set username/password input
            @param source as GObject.Object
            @param result as Gio.AsyncResult
            @param uri as str
            @param index as int
            @param count as int
            @param callback as function
            @param args
        """
        secret = source.get_secret()
        if secret is not None:
            attributes = source.get_attributes()
            keys = attributes.keys()
            # We ignore old Eolie passwords
            if "userform" in keys or\
                    "sync" in keys:
                callback(source.get_attributes(),
                         secret.get().decode('utf-8'),
                         uri,
                         index,
                         count,
                         *args)
            else:
                callback(None, None, uri, 0, 0, *args)
        else:
            callback(None, None, uri, 0, 0, *args)

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
            debug("SettingsDialog::__on_clear_search(): %s" % e)

    def __on_secret_search(self, source, result, uri, callback, *args):
        """
            Set username/password input
            @param source as GObject.Object
            @param result as Gio.AsyncResult
            @param uri as str/None
            @param callback as function
            @param args
        """
        try:
            if result is not None:
                items = self.__secret.search_finish(result)
                count = len(items)
                index = 0
                for item in items:
                    item.load_secret(None,
                                     self.__on_load_secret,
                                     uri,
                                     index,
                                     count,
                                     callback,
                                     *args)
                    index += 1
                if not items:
                    callback(None, None, uri, 0, 0, *args)
            else:
                callback(None, None, uri, 0, 0, *args)
        except Exception as e:
            debug("PasswordsHelper::__on_secret_search(): %s" % e)
            callback(None, None, uri, 0, 0, *args)

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
            debug("PasswordsHelper::__on_get_secret(): %s" % e)
