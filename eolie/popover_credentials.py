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

from gi.repository import Gtk, GLib

from gettext import gettext as _
from urllib.parse import urlparse

from eolie.helper_passwords import PasswordsHelper
from eolie.define import App


class CredentialsPopover(Gtk.Popover):
    """
        Tell user to save form credentials
    """

    def __init__(self, uuid, user_form_name, user_form_value, pass_form_name,
                 uri, form_uri, page_id, window):
        """
            Init popover
            @param uuid as str
            @param user_form_name as str
            @param user_form_value as str
            @param pass_form_name as str
            @param uri as str
            @param form_uri as str
            @param page_id as int
            @param window as Window
        """
        Gtk.Popover.__init__(self)
        self.set_modal(False)
        window.register(self)
        self.__helper = PasswordsHelper()
        self.__user_form_name = user_form_name
        self.__user_form_value = user_form_value
        self.__pass_form_name = pass_form_name
        self.__uri = uri
        self.__form_uri = form_uri
        self.__uuid = uuid
        self.__page_id = page_id
        builder = Gtk.Builder()
        builder.add_from_resource('/org/gnome/Eolie/PopoverCredentials.ui')
        builder.connect_signals(self)
        self.__label = builder.get_object('label')
        parsed = urlparse(uri)
        builder.get_object('uri').set_text(parsed.netloc)
        if uuid:
            self.__label.set_text(_("Do you want to modify this password?"))
        self.add(builder.get_object('widget'))

#######################
# PROTECTED           #
#######################
    def _on_save_clicked(self, button):
        """
            Save user_form_name and pass_form_name
            @param button as Gtk.Button
        """
        App().helper.call("SaveCredentials", self.__page_id,
                          GLib.Variant("(sssss)",
                                       (self.__uuid, self.__user_form_name,
                                        self.__pass_form_name, self.__uri,
                                        self.__form_uri)),
                          self.__on_save_credentials,
                          self.__form_uri,
                          self.__user_form_name,
                          self.__pass_form_name)
        self.destroy()

#######################
# PRIVATE             #
#######################
    def __on_get_password(self, attributes, password, form_uri, index, count):
        """
            Push credential to sync
            @param attributes as {}
            @param password as str
            @param form_uri as str
            @param index as int
            @param count as int
        """
        try:
            if attributes is not None and App().sync_worker is not None:
                App().sync_worker.push_password(attributes["userform"],
                                                attributes["login"],
                                                attributes["passform"],
                                                password,
                                                attributes["hostname"],
                                                attributes["formSubmitURL"],
                                                attributes["uuid"])
        except Exception as e:
            print("CredentialsPopover::__on_get_password():", e)

    def __on_save_credentials(self, source, result, form_uri,
                              user_form_name, pass_form_name):
        """
            Get password and push credential to sync
            @param source as GObject.Object
            @param result as Gio.AsyncResult
            @param form_uri as str
            @param user_form_name as str
            @param pass_form_name as str
        """
        helper = PasswordsHelper()
        helper.get(form_uri, user_form_name,
                   pass_form_name, self.__on_get_password)
