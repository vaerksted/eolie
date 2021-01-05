# Copyright (c) 2017-2021 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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
        # Initial password lookup, prevent a lock issue in Flatpak backend
        if GLib.file_test("/app", GLib.FileTest.EXISTS):
            SecretSchema = {"type": Secret.SchemaAttributeType.STRING}
            SecretAttributes = {"type": "eolie web login"}
            schema = Secret.Schema.new("org.gnome.Eolie",
                                       Secret.SchemaFlags.NONE,
                                       SecretSchema)
            Secret.password_lookup_sync(schema, SecretAttributes)

    def get_all(self, callback, *args):
        """
            Call function
            @param callback as function
            @param args
        """
        try:
            SecretSchema = {
                "type": Secret.SchemaAttributeType.STRING,
            }
            SecretAttributes = {
                "type": "eolie web login",
            }
            schema = Secret.Schema.new("org.gnome.Eolie",
                                       Secret.SchemaFlags.NONE,
                                       SecretSchema)
            Secret.password_search(schema, SecretAttributes,
                                   Secret.SearchFlags.ALL |
                                   Secret.SearchFlags.UNLOCK |
                                   Secret.SearchFlags.LOAD_SECRETS,
                                   None,
                                   self.__on_secret_search,
                                   None,
                                   callback,
                                   *args)
        except Exception as e:
            Logger.debug("PasswordsHelper::get_all(): %s", e)

    def get(self, uri, userform, passform, callback, *args):
        """
            Call function
            @param uri as str
            @param userform as str
            @param passform as str
            @param callback as function
            @param args
        """
        try:
            SecretSchema = {
                "type": Secret.SchemaAttributeType.STRING,
                "hostname": Secret.SchemaAttributeType.STRING,
                "userform": Secret.SchemaAttributeType.STRING,
            }
            SecretAttributes = {
                "type": "eolie web login",
                "hostname": uri,
                "userform": userform,
            }
            if passform is not None:
                SecretSchema["passform"] = Secret.SchemaAttributeType.STRING
                SecretAttributes["passform"] = passform

            schema = Secret.Schema.new("org.gnome.Eolie",
                                       Secret.SchemaFlags.NONE,
                                       SecretSchema)
            Secret.password_search(schema, SecretAttributes,
                                   Secret.SearchFlags.ALL |
                                   Secret.SearchFlags.UNLOCK |
                                   Secret.SearchFlags.LOAD_SECRETS,
                                   None,
                                   self.__on_secret_search,
                                   uri,
                                   callback,
                                   *args)
        except Exception as e:
            Logger.debug("PasswordsHelper::get(): %s", e)

    def get_by_uuid(self, uuid, callback, *args):
        """
            Get password attributes by uri
            @param uuid as str
            @param callback as function
            @param args
        """
        try:
            SecretSchema = {
                "type": Secret.SchemaAttributeType.STRING,
                "uuid": Secret.SchemaAttributeType.STRING,
            }
            SecretAttributes = {
                "type": "eolie web login",
                "uuid": uuid,
            }

            schema = Secret.Schema.new("org.gnome.Eolie",
                                       Secret.SchemaFlags.NONE,
                                       SecretSchema)
            Secret.password_search(schema, SecretAttributes,
                                   Secret.SearchFlags.ALL |
                                   Secret.SearchFlags.UNLOCK |
                                   Secret.SearchFlags.LOAD_SECRETS,
                                   None,
                                   self.__on_secret_search,
                                   uuid,
                                   callback,
                                   *args)
        except Exception as e:
            Logger.debug("PasswordsHelper::get_by_uuid(): %s", e)

    def get_sync(self, callback, *args):
        """
            Get sync password
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
            Secret.password_search(schema, SecretAttributes,
                                   Secret.SearchFlags.UNLOCK |
                                   Secret.SearchFlags.LOAD_SECRETS,
                                   None,
                                   self.__on_secret_search,
                                   None,
                                   callback,
                                   *args)
        except Exception as e:
            Logger.debug("PasswordsHelper::get_sync(): %s", e)

    def store(self, user_form_name, user_form_value, pass_form_name,
              pass_form_value, hostname_uri, uri, uuid, callback, *args):
        """
            Store password
            @param user_form_name as str
            @param user_form_value as str
            @param pass_form_name as str
            @param pass_form_value as str
            @param hostname_uri as str
            @param uri as str
            @param uuid as str
            @param callback as function
        """
        # seems to happen, thanks firefox
        if uri is None:
            return
        try:
            # Clear item if exists
            SecretSchema = {
                "type": Secret.SchemaAttributeType.STRING,
                "login": Secret.SchemaAttributeType.STRING,
                "hostname": Secret.SchemaAttributeType.STRING,
                "formSubmitURL": Secret.SchemaAttributeType.STRING,
                "userform": Secret.SchemaAttributeType.STRING,
                "passform": Secret.SchemaAttributeType.STRING,
            }
            SecretAttributes = {
                "type": "eolie web login",
                "login": user_form_value,
                "hostname": hostname_uri,
                "formSubmitURL": uri,
                "userform": user_form_name,
                "passform": pass_form_name
            }
            schema = Secret.Schema.new("org.gnome.Eolie",
                                       Secret.SchemaFlags.NONE,
                                       SecretSchema)
            Secret.password_clear(schema,
                                  SecretAttributes,
                                  None,
                                  self.__on_clear_search,
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
                "formSubmitURL": uri,
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

    def store_sync(self, login, password, callback=None, *args):
        """
            Store Firefox Sync password
            @param login as str
            @param password as str
            @param callback as function
            @param data
        """
        try:
            schema_string = "org.gnome.Eolie.sync"
            SecretSchema = {
                "sync": Secret.SchemaAttributeType.STRING,
                "login": Secret.SchemaAttributeType.STRING,
            }
            schema = Secret.Schema.new("org.gnome.Eolie",
                                       Secret.SchemaFlags.NONE,
                                       SecretSchema)
            SecretAttributes = {
                "sync": "mozilla",
                "login": login,
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
            Secret.password_clear(schema,
                                  SecretAttributes,
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
            Secret.password_clear(schema,
                                  SecretAttributes,
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
            SecretSchema = {
                "type": Secret.SchemaAttributeType.STRING
            }
            SecretAttributes = {
                "type": "eolie web login"
            }
            schema = Secret.Schema.new("org.gnome.Eolie",
                                       Secret.SchemaFlags.NONE,
                                       SecretSchema)
            Secret.password_clear(schema,
                                  SecretAttributes,
                                  None,
                                  self.__on_clear_search)
        except Exception as e:
            Logger.debug("PasswordsHelper::clear_all(): %s", e)

#######################
# PRIVATE             #
#######################
    def __on_clear_search(self, source, result, callback=None, *args):
        """
            Clear passwords
            @param source as GObject.Object
            @param result as Gio.AsyncResult
            @param callback as function
        """
        try:
            if result is not None:
                Secret.password_clear_finish(result)
            if callback is not None:
                callback(*args)
        except Exception as e:
            Logger.error("PasswordsHelper::__on_clear_search(): %s" % e)

    def __on_secret_search(self, source, result, uri, callback, *args):
        """
            Set username/password input
            @param source as GObject.Object
            @param result as Gio.AsyncResult
            @param uri as str
            @param callback as function
            @param args
        """
        try:
            items = []
            if result is not None:
                items = Secret.password_search_finish(result)
                count = len(items)
                index = 0
                for item in items:
                    attributes = item.get_attributes()
                    secret = item.retrieve_secret_sync()
                    callback(attributes,
                             secret.get().decode('utf-8'),
                             uri,
                             index,
                             count,
                             *args)
                    index += 1
            if not items:
                callback(None, None, uri, 0, 0, *args)
        except Exception as e:
            Logger.debug("PasswordsHelper::__on_secret_search(): %s", e)
            callback(None, None, uri, 0, 0, *args)
