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
from urllib.parse import urlparse

from eolie.define import El


class SitesMenu(Gio.Menu):
    """
        Menu linked to a SitesManagerChild
    """

    # For default gsetting shema translation
    __PROFILES = {"default": _("Default"),
                  "social": _("Social networks"),
                  "work": _("Work"),
                  "shopping": _("Shopping"),
                  "personal": _("Personal"),
                  "finance": _("Finance"),
                  "sport": _("Sport")}

    def __init__(self, views, window):
        """
            Init menu
            @param views as [view]
            @param window as Window
        """
        self.__window = window
        self.__views = views
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
        if views and not views[0].webview.ephemeral:
            parsed = urlparse(views[0].webview.uri)
            if parsed.scheme in ["http", "https"]:
                submenu = self.__get_submenu()
                bottom_section.insert_submenu(0, _("Profiles"), submenu)
        action = Gio.SimpleAction.new("user_agent")
        self.__window.add_action(action)
        # Modify UA
        if El().settings.get_value("developer-extras"):
            item = Gio.MenuItem.new(_("Modify user agent"),
                                    "win.user_agent")
            bottom_section.append_item(item)
            action.connect("activate", self.__on_modify_ua_activate)
        # Close site
        action = Gio.SimpleAction.new("close_site")
        self.__window.add_action(action)
        item = Gio.MenuItem.new(_("Close site"),
                                "win.close_site")
        bottom_section.append_item(item)
        action.connect("activate", self.__on_close_activate)

#######################
# PRIVATE             #
#######################
    def __get_submenu(self):
        """
            Return submenu (profiles) for site
            return Gio.Menu
        """
        menu = Gio.Menu()
        action = Gio.SimpleAction.new_stateful("eolie_profiles",
                                               GLib.VariantType.new("s"),
                                               GLib.Variant("s", "none"))
        action.connect("activate", self.__on_profiles_activate)
        self.__window.add_action(action)
        # Get first view URI
        uri = self.__views[0].webview.uri
        profile = El().websettings.get_profile(uri)
        for key in self.__PROFILES.keys():
            item = self.__PROFILES[key]
            self.__window.add_action(action)
            menu_item = Gio.MenuItem.new(item,
                                         "win.eolie_profiles::%s" % key)
            if profile == key:
                action.change_state(GLib.Variant("s", profile))
            menu.append_item(menu_item)
        return menu

    def __on_profiles_activate(self, action, param):
        """
            Change profile
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        try:
            action.change_state(param)
            # Get first view URI
            webview = self.__views[0].webview
            uri = webview.uri
            El().websettings.set_profile(param.get_string(), uri)
            webview.stop_loading()
            webview.load_uri(uri)
        except Exception as e:
            print("SitesMenu::__on_profiles_activate:", e)

    def __on_close_activate(self, action, param):
        """
            Close wanted page
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        for view in self.__window.container.views:
            if view in self.__views:
                self.__window.container.try_close_view(view)

    def __on_modify_ua_activate(self, action, param):
        """
            Show a dialog allowing user to update User Agent
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        if self.__views:
            from eolie.dialog_modify_ua import ModifyUADialog
            dialog = ModifyUADialog(self.__views[0].webview.uri, self.__window)
            dialog.run()

    def __on_action_clicked(self, action, variant, view):
        """
            Load history
            @param Gio.SimpleAction
            @param GLib.Variant
            @param view as View
        """
        self.__window.container.set_current(view, True)
