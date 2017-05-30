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

from gettext import gettext as _
from urllib.parse import urlparse

from eolie.helper_passwords import PasswordsHelper
from uuid import uuid3, NAMESPACE_DNS


class PasswordPopover(Gtk.Popover):
    """
        Tell user to save form password
    """

    def __init__(self, username, password, uri):
        """
            Init popover
            @param username as str
            @param password as str
            @param netloc as str
        """
        Gtk.Popover.__init__(self)
        self.__helper = PasswordsHelper()
        self.__username = username
        self.__password = password
        self.__uri = uri
        builder = Gtk.Builder()
        builder.add_from_resource('/org/gnome/Eolie/PopoverPassword.ui')
        builder.connect_signals(self)
        self.__label = builder.get_object('label')
        parsed = urlparse(uri)
        builder.get_object('uri').set_text(parsed.netloc)
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
            parsed = urlparse(self.__uri)
            self.__helper.clear(self.__uri)
            self.__helper.store(self.__username,
                                self.__password,
                                self.__uri,
                                str(uuid3(NAMESPACE_DNS, parsed.netloc)),
                                None)
            self.destroy()
        except Exception as e:
            print("PasswordPopover::_on_save_clicked()", e)

    def show(self):
        """
            Overwrite show
        """
        self.__helper.get(self.__uri,
                          self.__on_get_password)

#######################
# PRIVATE             #
#######################
    def __on_get_password(self, attributes, password, uri):
        """
            Set username/password input
            @param attributes as {}
            @param password as str
            @param uri as str
        """
        try:
            if attributes is None:
                Gtk.Popover.show(self)
            elif attributes["login"] == self.__username and\
                    self.__password == password:
                self.emit("closed")
            else:
                Gtk.Popover.show(self)
                self.__label.set_text(_(
                                   "Do you want to modify this password?"))
        except Exception as e:
            print("PasswordPopover::on_load_secret()", e)
