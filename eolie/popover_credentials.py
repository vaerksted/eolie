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
from uuid import uuid4

from eolie.helper_passwords import PasswordsHelper
from eolie.define import El


class CredentialsPopover(Gtk.Popover):
    """
        Tell user to save form credentials
    """

    def __init__(self, user_form_name, user_form_value, pass_form_name,
                 pass_form_value, uri, form_uri, window):
        """
            Init popover
            @param user_form_name as str
            @param user_form_value as str
            @param pass_form_name as str
            @param pass_form_value as str
            @param uri as str
            @param form_uri as str
            @param window as Window
        """
        Gtk.Popover.__init__(self)
        self.set_modal(False)
        window.register(self)
        self.__helper = PasswordsHelper()
        self.__user_form_name = user_form_name
        self.__user_form_value = user_form_value
        self.__pass_form_name = pass_form_name
        self.__pass_form_value = pass_form_value
        self.__uri = uri
        self.__form_uri = form_uri
        self.__uuid = None
        builder = Gtk.Builder()
        builder.add_from_resource('/org/gnome/Eolie/PopoverCredentials.ui')
        builder.connect_signals(self)
        self.__label = builder.get_object('label')
        parsed = urlparse(uri)
        builder.get_object('uri').set_text(parsed.netloc)
        builder.get_object('username').set_text(user_form_value)
        builder.get_object('password').set_text(pass_form_value)
        self.add(builder.get_object('widget'))

#######################
# PROTECTED           #
#######################
    def _on_save_clicked(self, button):
        """
            Save user_form_name and pass_form_name
            @param button as Gtk.Button
        """
        try:
            parsed = urlparse(self.__uri)
            parsed_form_uri = urlparse(self.__form_uri)
            uri = "%s://%s" % (parsed.scheme, parsed.netloc)
            form_uri = "%s://%s" % (parsed_form_uri.scheme,
                                    parsed_form_uri.netloc)
            if self.__uuid is None:
                self.__uuid = str(uuid4())
                self.__helper.store(self.__user_form_name,
                                    self.__user_form_value,
                                    self.__pass_form_name,
                                    self.__pass_form_value,
                                    uri,
                                    form_uri,
                                    self.__uuid,
                                    None)
            else:
                self.__helper.clear(self.__uuid,
                                    self.__helper.store,
                                    self.__user_form_name,
                                    self.__user_form_value,
                                    self.__pass_form_name,
                                    self.__pass_form_value,
                                    uri,
                                    form_uri,
                                    self.__uuid,
                                    None)
            if El().sync_worker is not None:
                El().sync_worker.push_password(self.__user_form_name,
                                               self.__user_form_value,
                                               self.__pass_form_name,
                                               self.__pass_form_value,
                                               uri,
                                               form_uri,
                                               self.__uuid)
            self.destroy()
        except Exception as e:
            print("CredentialsPopover::_on_save_clicked()", e)

    def popup(self):
        """
            Overwrite popup
        """
        self.__helper.get(self.__uri, self.__user_form_name,
                          self.__pass_form_name, self.__on_get_password,)

#######################
# PRIVATE             #
#######################
    def __on_get_password(self, attributes, password, uri, index, count):
        """
            Set user_form_name/pass_form_name input
            @param attributes as {}
            @param password as str
            @param uri as str
            @param index as int
            @param count as int
        """
        try:
            # No saved pass_form_name
            if attributes is None:
                Gtk.Popover.popup(self)
            # pass_form_name saved and unchanged
            elif attributes["login"] == self.__user_form_value:
                if password == self.__pass_form_value:
                    self.emit("closed")
                    # Prevent popover to be displayed
                    self.set_relative_to(None)
                # login/password changed
                else:
                    Gtk.Popover.popup(self)
                    self.__uuid = attributes["uuid"]
                    self.__label.set_text(_(
                                       "Do you want to modify this password?"))
            else:
                Gtk.Popover.popup(self)
        except Exception as e:
            print("CredentialsPopover::__on_get_password()", e)
