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


class ClosedMenu(Gio.Menu):
    """
        Menu showing closed page
    """

    def __init__(self, app):
        """
            Init menu
            @param app as Gio.Application
        """
        Gio.Menu.__init__(self)
        self.__app = app

    def add_action(self, title, uri, state):
        """
            Add a new action to menu
            @param title as str
            @param uri as str
            @param state as WebKit2.WebViewSessionState
        """
        if not title:
            title = uri
        encoded = sha256(uri.encode("utf-8")).hexdigest()
        action = self.__app.lookup_action(encoded)
        if action is not None:
            self.__app.remove_action(action)
            action.destroy()
        action = Gio.SimpleAction(name=encoded)
        self.__app.add_action(action)
        action.connect('activate',
                       self.__on_action_clicked,
                       (uri, state))
        item = Gio.MenuItem.new(title, "app.%s" % encoded)
        item.set_attribute_value("uri", GLib.Variant("s", uri))
        # Try to set icon
        try:
            f = Gio.File.new_for_path(self.__app.art.get_path(uri, "favicon"))
            icon = Gio.FileIcon.new(f)
            item.set_icon(icon)
        except:
            pass
        self.append_item(item)
        self.__update_toolbar_actions()

    def remove_action(self, uri):
        """
            Remove action from menu
        """
        encoded = sha256(uri.encode("utf-8")).hexdigest()
        action = self.__app.lookup_action(encoded)
        if action is not None:
            self.__app.remove_action(encoded)
            for i in range(0, self.get_n_items()):
                _uri = self.get_item_attribute_value(i, "uri").get_string()
                if uri == _uri:
                    self.remove(i)
                    break
        self.__update_toolbar_actions()

#######################
# PRIVATE             #
#######################
    def __update_toolbar_actions(self):
        """
            Update toolbar actions (ie our button)
        """
        sensitive = self.get_n_items() != 0
        for window in self.__app.windows:
            window.toolbar.actions.closed_button.set_sensitive(sensitive)

    def __on_action_clicked(self, action, variant, data):
        """
            Add to playlists
            @param Gio.SimpleAction
            @param GVariant
            @param data as (str, WebKit2.WebViewSessionState)
        """
        uri = data[0]
        state = data[1]
        GLib.idle_add(self.__app.active_window.container.add_web_view,
                      uri, True, None, None, state)
        self.remove_action(uri)
