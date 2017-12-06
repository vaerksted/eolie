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

from gettext import gettext as _
import json

from eolie.define import El, EOLIE_DATA_PATH


class ProfilesMenu(Gio.Menu):
    """
        Menu allowing to switch current view to a new profile
    """

    def __init__(self, webview, window):
        """
            Init menu
            @param webview as WebView
            @param window as Window
        """
        self.__window = window
        Gio.Menu.__init__(self)
        action = Gio.SimpleAction.new_stateful("eolie_profiles",
                                               GLib.VariantType.new("s"),
                                               GLib.Variant("s", "none"))
        action.connect("activate",
                       self.__on_profiles_activate,
                       webview)
        self.__window.add_action(action)
        # Get first view URI
        uri = webview.uri
        profile = El().websettings.get_profile(uri)
        # Load user profiles
        try:
            f = Gio.File.new_for_path(EOLIE_DATA_PATH +
                                      "/profiles.json")
            if f.query_exists():
                (status, contents, tag) = f.load_contents(None)
                profiles = json.loads(contents.decode("utf-8"))

            for key in profiles.keys():
                item = profiles[key]
                self.__window.add_action(action)
                menu_item = Gio.MenuItem.new(item,
                                             "win.eolie_profiles::%s" % key)
                if profile == key:
                    action.change_state(GLib.Variant("s", profile))
                self.append_item(menu_item)
        except Exception as e:
            print("ProfilesMenu::__init__():", e)
        action = Gio.SimpleAction(name="eolie_edit_profiles")
        self.__window.add_action(action)
        menu_item = Gio.MenuItem.new(_("Edit profiles"),
                                     "win.eolie_edit_profiles")
        self.append_item(menu_item)
        action.connect('activate',
                       self.__on_edit_profiles_activate)

#######################
# PRIVATE             #
#######################
    def __on_edit_profiles_activate(self, action, param):
        """
            Show edit cookies dialog
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        from eolie.dialog_cookies import CookiesDialog
        dialog = CookiesDialog(True, self.__window)
        dialog.run()

    def __on_profiles_activate(self, action, param, webview):
        """
            Change profile
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
            @param webview as WebView
        """
        try:
            action.change_state(param)
            uri = webview.uri
            El().websettings.set_profile(param.get_string(), uri)
            webview.stop_loading()
            # We need to reset URI before reloading
            # This allow WebViewNavigation to operate profile switching
            webview.load_uri("about:blank")
            webview.load_uri(uri)
        except Exception as e:
            print("ProfilesMenu::__on_profiles_activate:", e)
