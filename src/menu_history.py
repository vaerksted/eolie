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


class HistoryMenu(Gio.Menu):
    """
        Menu showing closed page
    """

    def __init__(self, app, items):
        """
            Init menu
            @param app as Gio.Application
            @param items as [WebKit2.BackForwardListItem]
        """
        Gio.Menu.__init__(self)
        self.__app = app
        for item in items:
            uri = item.get_uri()
            if uri is None:
                continue
            title = item.get_title()
            if not title:
                title = uri
            encoded = "HISTORY_" + sha256(uri.encode("utf-8")).hexdigest()
            action = self.__app.lookup_action(encoded)
            if action is not None:
                self.__app.remove_action(encoded)
            action = Gio.SimpleAction(name=encoded)
            self.__app.add_action(action)
            action.connect('activate',
                           self.__on_action_clicked,
                           item)
            if len(title) > 60:
                title = title[0:60] + "…"
            item = Gio.MenuItem.new(title, "app.%s" % encoded)
            item.set_attribute_value("uri", GLib.Variant("s", uri))
            # Try to set icon
            if self.__app.art.exists(uri, "favicon"):
                f = Gio.File.new_for_path(self.__app.art.get_path(uri,
                                                                  "favicon"))
                icon = Gio.FileIcon.new(f)
                item.set_icon(icon)
            elif uri == "populars://":
                item.set_icon(Gio.ThemedIcon.new("emote-love-symbolic"))
            else:
                item.set_icon(Gio.ThemedIcon.new("applications-internet"))
            self.append_item(item)

    def remove_actions(self):
        """
            Remove actions for menu
        """
        for i in range(0, self.get_n_items()):
            uri = self.get_item_attribute_value(i, "uri").get_string()
            encoded = "HISTORY_" + sha256(uri.encode("utf-8")).hexdigest()
            action = self.__app.lookup_action(encoded)
            if action is not None:
                self.__app.remove_action(encoded)

#######################
# PRIVATE             #
#######################
    def __on_action_clicked(self, action, variant, item):
        """
            Add to playlists
            @param Gio.SimpleAction
            @param GVariant
            @param item as WebKit2.BackForwardListItem
        """
        self.__app.active_window.\
            container.current.webview.go_to_back_forward_list_item(item)
