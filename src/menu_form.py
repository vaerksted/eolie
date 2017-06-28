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

from gi.repository import Gio, GLib

from hashlib import sha256

from eolie.helper_passwords import PasswordsHelper
from eolie.define import El


class FormMenu(Gio.Menu):
    """
        Menu showing form username
    """

    def __init__(self, app, name, uri, page_id):
        """
            Init menu
            @param app as Gio.Application
            @param name as str
            @param uri as str
            @param page_id as int
        """
        Gio.Menu.__init__(self)
        self.__app = app
        self.__page_id = page_id
        helper = PasswordsHelper()
        helper.get(uri, self.__on_password, name)

#######################
# PRIVATE             #
#######################
    def __on_password(self, attributes, password, uri, name):
        """
            Set username/password input
            @param attributes as {}
            @param password as str
            @param uri as str
            @param name as str
        """
        if attributes is None:
            return
        username = attributes["login"]
        encoded = "FORM_" + sha256(username.encode("utf-8")).hexdigest()
        action = self.__app.lookup_action(encoded)
        if action is not None:
            self.__app.remove_action(encoded)
        action = Gio.SimpleAction(name=encoded)
        self.__app.add_action(action)
        action.connect('activate',
                       self.__on_action_clicked,
                       username, attributes)
        item = Gio.MenuItem.new(username, "app.%s" % encoded)
        self.append_item(item)

    def __on_action_clicked(self, action, variant, username, attributes):
        """
            Update form
            @param Gio.SimpleAction
            @param GVariant
            @param username as str
            @param attributes as {}
        """
        forms = (attributes["userform"], attributes["passform"])
        El().helper.call("SetAuthForms",
                         GLib.Variant("(sasi)",
                                      (username, forms, self.__page_id)),
                         None, None,
                         self.__page_id)
