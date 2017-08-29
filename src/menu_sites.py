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
from gettext import gettext as _

from eolie.define import El


class SitesMenu(Gio.Menu):
    """
        Menu linked to a SitesManagerChild
    """

    def __init__(self, views, window):
        """
            Init menu
            @param views as [view]
            @param window as Window
        """
        self.__window = window
        Gio.Menu.__init__(self)
        for view in views:
            uri = view.webview.get_uri()
            if uri is None:
                continue
            title = view.webview.get_title()
            if not title:
                title = uri
            encoded = "SITE_" + sha256(uri.encode("utf-8")).hexdigest()
            action = El().lookup_action(encoded)
            if action is not None:
                El().remove_action(encoded)
            action = Gio.SimpleAction(name=encoded)
            El().add_action(action)
            action.connect('activate',
                           self.__on_action_clicked,
                           view)
            item = Gio.MenuItem.new(title, "app.%s" % encoded)
            item.set_attribute_value("uri", GLib.Variant("s", uri))
            if uri == "populars://":
                item.set_icon(Gio.ThemedIcon.new("emote-love-symbolic"))
            else:
                # Try to set icon
                filepath = El().art.get_path(uri, "favicon")
                f = Gio.File.new_for_path(filepath)
                if f.query_exists():
                    icon = Gio.FileIcon.new(f)
                    item.set_icon(icon)
                else:
                    item.set_icon(Gio.ThemedIcon.new("applications-internet"))
            self.append_item(item)
        close_section = Gio.Menu()
        self.append_section(None, close_section)
        action = Gio.SimpleAction.new("close_site")
        self.__window.add_action(action)
        item = Gio.MenuItem.new(_("Close site"),
                                "win.close_site")
        close_section.append_item(item)
        action.connect("activate", self.__on_close_activate, views)

#######################
# PRIVATE             #
#######################
    def __on_close_activate(self, action, param, views):
        """
            Close wanted page
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
            @param views as [View]
        """
        for view in self.__window.container.views:
            if view in views:
                self.__window.container.pages_manager.close_view(view)

    def __on_action_clicked(self, action, variant, view):
        """
            Load history
            @param Gio.SimpleAction
            @param GVariant
            @param view as View
        """
        self.__window.container.set_visible_view(view)
