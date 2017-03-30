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

from gi.repository import Gtk, Secret

from gettext import gettext as _


class PasswordPopover(Gtk.Popover):
    """
        Tell user to save form password
    """

    def __init__(self, username, password, netloc):
        """
            Init popover
            @param username as str
            @param password as str
            @param netloc as str
        """
        Gtk.Popover.__init__(self)
        self.__secret_item = None
        self.__username = username
        self.__password = password
        self.__netloc = netloc
        builder = Gtk.Builder()
        builder.add_from_resource('/org/gnome/Eolie/PopoverPassword.ui')
        builder.connect_signals(self)
        self.__label = builder.get_object('label')
        builder.get_object('uri').set_text(netloc)
        builder.get_object('username').set_text(username)
        builder.get_object('password').set_text(password)
        self.add(builder.get_object('widget'))

#######################
# PROTECTED           #
#######################
    def _on_save_clicked(self, button):
        """
            Save username and password
            @param button as Gtk.Button
        """
        try:
            schema_string = "org.gnome.Eolie: %s@%s" % (self.__username,
                                                        self.__netloc)
            if self.__secret_item is None:
                SecretSchema = {
                    "type": Secret.SchemaAttributeType.STRING,
                    "uri": Secret.SchemaAttributeType.STRING,
                    "login": Secret.SchemaAttributeType.STRING,
                }
                SecretAttributes = {
                    "type": "eolie web login",
                    "uri": self.__netloc,
                    "login": self.__username
                }
                schema = Secret.Schema.new("org.gnome.Eolie",
                                           Secret.SchemaFlags.NONE,
                                           SecretSchema)
                Secret.password_store(schema, SecretAttributes,
                                      Secret.COLLECTION_DEFAULT,
                                      schema_string,
                                      self.__password,
                                      None, None)
            else:
                value = Secret.Value.new(self.__password,
                                         len(self.__password),
                                         "")
                self.__secret_item.set_secret(value, None, None)
                self.__secret_item.set_label(schema_string, None, None)
            self.destroy()
        except Exception as e:
            print("PasswordPopover::_on_save_clicked()", e)

    def show(self):
        """
            Overwrite show
        """
        self.__search_for_password()

#######################
# PRIVATE             #
#######################
    def __search_for_password(self):
        """
           Search for password
        """
        Secret.Service.get(Secret.ServiceFlags.NONE,
                           None, self.__on_get_secret)

    def __on_load_secret(self, item, result):
        """
            Set username/password input
            @param item as Secret.Item
            @param result as Gio.AsyncResult
        """
        try:
            self.__secret_item = item
            secret = item.get_secret()
            if self.__secret_item is not None:
                username = item.get_attributes()["login"]
                password = secret.get().decode('utf-8')
                if username == self.__username and self.__password == password:
                    self.emit("closed")
                    return
                else:
                    self.__label.set_text(_(
                                       "Do you want to modify this password?"))
            Gtk.Popover.show(self)
        except Exception as e:
            print("PasswordPopover::on_load_secret()", e)

    def __on_secret_search(self, secret, result):
        """
            Set username/password input
            @param secret as Secret.secret
            @param result as Gio.AsyncResult
        """
        try:
            if result is not None:
                items = secret.search_finish(result)
                if not items:
                    Gtk.Popover.show(self)
                    return
                items[0].load_secret(None,
                                     self.__on_load_secret)
            else:
                Gtk.Popover.show(self)
        except Exception as e:
            print("PasswordPopover::__on_secret_search()", e)

    def __on_get_secret(self, source, result):
        """
            Store secret proxy
            @param source as GObject.Object
            @param result as Gio.AsyncResult
        """
        try:
            secret = Secret.Service.get_finish(result)
            SecretSchema = {
                "uri": Secret.SchemaAttributeType.STRING,
                "login": Secret.SchemaAttributeType.STRING,
            }
            SecretAttributes = {
                "uri": self.__netloc,
                "login": self.__username
            }
            schema = Secret.Schema.new("org.gnome.Eolie",
                                       Secret.SchemaFlags.NONE,
                                       SecretSchema)
            secret.search(schema, SecretAttributes, Secret.ServiceFlags.NONE,
                          None, self.__on_secret_search)
        except Exception as e:
            print("PasswordPopover::__on_get_secret()", e)
