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

import gi
gi.require_version('Secret', '1')
from gi.repository import Secret, GLib

from eolie.logger import Logger


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
            Logger.debug("PasswordsHelper::get_all(): %s", e)

    def get(self, form_uri, userform, passform, callback, *args):
        """
            Call function
            @param form_uri as str
            @param userform as str
            @param passform as str
            @param callback as function
            @param args
        """
        try:
            self.__wait_for_secret(self.get, form_uri, userform,
                                   passform, callback, *args)
            SecretSchema = {
                "type": Secret.SchemaAttributeType.STRING,
                "formSubmitURL": Secret.SchemaAttributeType.STRING,
                "userform": Secret.SchemaAttributeType.STRING,
            }
            SecretAttributes = {
                "type": "eolie web login",
                "formSubmitURL": form_uri,
                "userform": userform,
            }
            if passform is not None:
                SecretSchema["passform"] = Secret.SchemaAttributeType.STRING
                SecretAttributes["passform"] = passform

            schema = Secret.Schema.new("org.gnome.Eolie",
                                       Secret.SchemaFlags.NONE,
                                       SecretSchema)
            self.__secret.search(schema, SecretAttributes,
                                 Secret.SearchFlags.ALL,
                                 None,
                                 self.__on_secret_search,
                                 form_uri,
                                 callback,
                                 *args)
        except Exception as e:
            Logger.debug("PasswordsHelper::get(): %s", e)

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
            Logger.debug("PasswordsHelper::get_sync(): %s", e)

    def store(self, user_form_name, user_form_value, pass_form_name,
              pass_form_value, hostname_uri, form_uri, uuid, callback, *args):
        """
            Store password
            @param user_form_name as str
            @param user_form_value as str
            @param pass_form_name as str
            @param pass_form_value as str
            @param hostname_uri as str
            @param form_uri as str
            @param uuid as str
            @param callback as function
        """
        # seems to happen, thanks firefox
        if form_uri is None:
            return
        try:
            self.__wait_for_secret(self.store,
                                   user_form_name,
                                   user_form_value,
                                   pass_form_name,
                                   pass_form_value,
                                   hostname_uri,
                                   form_uri,
                                   uuid,
                                   callback,
                                   *args)
            schema_string = "org.gnome.Eolie: %s > %s" % (user_form_value,
                                                          hostname_uri)
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
                "login": user_form_value,
                "hostname": hostname_uri,
                "formSubmitURL": form_uri,
                "userform": user_form_name,
                "passform": pass_form_name
            }

            schema = Secret.Schema.new("org.gnome.Eolie",
                                       Secret.SchemaFlags.NONE,
                                       SecretSchema)
            Secret.password_store(schema, SecretAttributes,
                                  Secret.COLLECTION_DEFAULT,
                                  schema_string,
                                  pass_form_value,
                                  None,
                                  callback)
        except Exception as e:
            Logger.debug("PasswordsHelper::store(): %s", e)

    def store_sync(self, login, password, uid,
                   token, keyB, callback=None, *args):
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
                                  *args)
        except Exception as e:
            Logger.debug("PasswordsHelper::store_sync(): %s", e)

    def clear(self, uuid, callback=None, *args):
        """
            Clear password
            @param uuid as str
            @param callback as function
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
                                 self.__on_clear_search,
                                 callback,
                                 *args)
        except Exception as e:
            Logger.debug("PasswordsHelper::clear(): %s", e)

    def clear_sync(self, callback, *args):
        """
            Clear sync secrets
            @param callback as function
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
                                 self.__on_clear_search,
                                 callback,
                                 *args)
        except Exception as e:
            Logger.debug("PasswordsHelper::clear_sync(): %s", e)

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
            Logger.debug("PasswordsHelper::clear_all(): %s", e)

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

    def __on_load_secret(self, source, result, form_uri,
                         index, count, callback, *args):
        """
            Set username/password input
            @param source as GObject.Object
            @param result as Gio.AsyncResult
            @param form_uri as str
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
                callback(attributes,
                         secret.get().decode('utf-8'),
                         form_uri,
                         index,
                         count,
                         *args)
            else:
                callback(None, None, form_uri, 0, 0, *args)
        else:
            callback(None, None, form_uri, 0, 0, *args)

    def __on_clear_search(self, source, result, callback=None, *args):
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
            if callback is not None:
                callback(*args)
        except Exception as e:
            Logger.debug("PasswordsHelper::__on_clear_search(): %s", e)

    def __on_secret_search(self, source, result, form_uri, callback, *args):
        """
            Set username/password input
            @param source as GObject.Object
            @param result as Gio.AsyncResult
            @param form_uri as str
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
                                     form_uri,
                                     index,
                                     count,
                                     callback,
                                     *args)
                    index += 1
                if not items:
                    callback(None, None, form_uri, 0, 0, *args)
            else:
                callback(None, None, form_uri, 0, 0, *args)
        except Exception as e:
            Logger.debug("PasswordsHelper::__on_secret_search(): %s", e)
            callback(None, None, form_uri, 0, 0, *args)

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
            Logger.debug("PasswordsHelper::__on_get_secret(): %s", e)
