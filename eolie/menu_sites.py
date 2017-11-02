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
            uri = view.webview.uri
            if uri is None:
                continue
            title = view.webview.title
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
            self.append_item(item)
        bottom_section = Gio.Menu()
        self.append_section(None, bottom_section)
        action = Gio.SimpleAction.new("user_agent")
        self.__window.add_action(action)
        # Modify UA
        if El().settings.get_value("developer-extras"):
            item = Gio.MenuItem.new(_("Modify user agent"),
                                    "win.user_agent")
            bottom_section.append_item(item)
            action.connect("activate", self.__on_modify_ua_activate, views)
        # Close site
        action = Gio.SimpleAction.new("close_site")
        self.__window.add_action(action)
        item = Gio.MenuItem.new(_("Close site"),
                                "win.close_site")
        bottom_section.append_item(item)
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
                self.__window.container.try_close_view(view)

    def __on_modify_ua_activate(self, action, param, views):
        """
            Show a dialog allowing user to update User Agent
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
            @param views as [View]
        """
        if views:
            from eolie.dialog_modify_ua import ModifyUADialog
            dialog = ModifyUADialog(views[0].webview.uri, self.__window)
            dialog.run()

    def __on_action_clicked(self, action, variant, view):
        """
            Load history
            @param Gio.SimpleAction
            @param GLib.Variant
            @param view as View
        """
        self.__window.container.set_current(view, True)
