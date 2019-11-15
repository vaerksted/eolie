# Copyright (c) 2017-2019 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from gi.repository import Gio

from hashlib import sha256
from gettext import gettext as _

from eolie.define import App


class FormMenu(Gio.Menu):
    """
        Menu showing form username
    """

    def __init__(self, webview, window):
        """
            Init menu
            @param webview as Webview
            @param window as Window
        """
        Gio.Menu.__init__(self)
        self.__window = window
        self.__webview = webview
        self.__section = Gio.Menu()
        self.append_section(_("Saved credentials"), self.__section)

    def add_attributes(self, attributes, uri):
        """
            Add username to model
            @param attributes as {}
            @param uri as str
        """
        encoded = "FORM_" + sha256(
            attributes["login"].encode("utf-8")).hexdigest()
        action = Gio.SimpleAction(name=encoded)
        App().add_action(action)
        action.connect('activate',
                       self.__on_action_clicked,
                       attributes["uuid"])
        label = attributes["login"].replace("_", "__")
        item = Gio.MenuItem.new(label, "app.%s" % encoded)
        self.__section.append_item(item)

#######################
# PRIVATE             #
#######################
    def __on_action_clicked(self, action, variant, uuid):
        """
            Update form
            @param Gio.SimpleAction
            @param GVariant
            @param uuid as str
        """
        self.__webview.set_forms_content(uuid)
