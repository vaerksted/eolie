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

from gi.repository import Gio, GLib

from hashlib import sha256

from eolie.define import App


class HistoryMenu(Gio.Menu):
    """
        Menu showing closed page
    """

    def __init__(self, items, window):
        """
            Init menu
            @param items as [WebKit2.BackForwardListItem]
        """
        Gio.Menu.__init__(self)
        self.__window = window
        self.__actions = []
        for item in items[:10]:
            uri = item.get_uri()
            if uri is None:
                continue
            title = item.get_title()
            if not title:
                title = uri
            encoded = "HISTORY_" + sha256(uri.encode("utf-8")).hexdigest()
            action = Gio.SimpleAction(name=encoded)
            window.add_action(action)
            self.__actions.append(encoded)
            action.connect('activate',
                           self.__on_action_activate,
                           item)
            item = Gio.MenuItem.new(title, "win.%s" % encoded)
            item.set_attribute_value("uri", GLib.Variant("s", uri))
            if uri == "populars://":
                item.set_icon(Gio.ThemedIcon.new("emote-love-symbolic"))
            else:
                # Try to set icon
                favicon_path = App().art.get_favicon_path(uri)
                if favicon_path is not None:
                    f = Gio.File.new_for_path(favicon_path)
                    icon = Gio.FileIcon.new(f)
                    if icon is not None:
                        item.set_icon(icon)
                else:
                    item.set_icon(Gio.ThemedIcon.new("web-browser-symbolic"))
            self.append_item(item)

    def clean(self):
        """
            Clean menu
        """
        for action in self.__actions:
            self.__window.remove_action(action)

#######################
# PRIVATE             #
#######################
    def __on_action_activate(self, action, variant, item):
        """
            Load history
            @param Gio.SimpleAction
            @param GVariant
            @param item as WebKit2.BackForwardListItem
        """
        App().active_window.\
            container.webview.go_to_back_forward_list_item(item)
