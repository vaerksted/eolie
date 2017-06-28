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

from eolie.define import El


class FormMenu(Gio.Menu):
    """
        Menu showing form username
    """

    def __init__(self, app, name, page_id):
        """
            Init menu
            @param app as Gio.Application
            @param name as str
            @param page_id as int
        """
        Gio.Menu.__init__(self)
        self.__app = app
        self.__page_id = page_id

    def add_attributes(self, attributes, uri):
        """
            Add username to model
            @param attributes as {}
            @param uri as str
        """
        if attributes is None:
            return
        encoded = "FORM_" + sha256(
                               attributes["login"].encode("utf-8")).hexdigest()
        action = self.__app.lookup_action(encoded)
        if action is not None:
            self.__app.remove_action(encoded)
        action = Gio.SimpleAction(name=encoded)
        self.__app.add_action(action)
        action.connect('activate',
                       self.__on_action_clicked,
                       attributes)
        item = Gio.MenuItem.new(attributes["login"], "app.%s" % encoded)
        self.append_item(item)

#######################
# PRIVATE             #
#######################
    def __on_action_clicked(self, action, variant, attributes):
        """
            Update form
            @param Gio.SimpleAction
            @param GVariant
            @param attributes as {}
        """
        forms = (attributes["userform"], attributes["passform"])
        El().helper.call("SetAuthForms",
                         GLib.Variant("(sasi)",
                                      (attributes["login"],
                                       forms,
                                       self.__page_id)),
                         None, None,
                         self.__page_id)
