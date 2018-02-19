# Copyright (c) 2017-2018 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from gi.repository import Gio, GLib, Gtk

from gettext import gettext as _
import json

from eolie.define import App, EOLIE_DATA_PATH


class ProfilesMenu(Gtk.Grid):
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
        Gtk.Grid.__init__(self)
        self.set_margin_start(5)
        self.set_margin_end(5)
        self.set_margin_top(5)
        self.set_margin_bottom(5)
        self.set_orientation(Gtk.Orientation.VERTICAL)

        # Back button
        item = Gtk.ModelButton.new()
        item.set_hexpand(True)
        item.set_property("centered", True)
        item.set_property("text", _("Profiles"))
        item.set_property("inverted", True)
        item.set_property("menu-name", "main")
        item.show()
        self.add(item)

        # Profile buttons
        action = Gio.SimpleAction.new_stateful("switch_profile",
                                               GLib.VariantType.new("s"),
                                               GLib.Variant("s", "none"))
        action.connect("activate",
                       self.__on_profiles_activate,
                       webview)
        self.__window.add_action(action)
        # Get first view URI
        uri = webview.uri
        profile = App().websettings.get_profile(uri)
        # Load user profiles
        try:
            f = Gio.File.new_for_path(EOLIE_DATA_PATH +
                                      "/profiles.json")
            if f.query_exists():
                (status, contents, tag) = f.load_contents(None)
                profiles = json.loads(contents.decode("utf-8"))

            for key in profiles.keys():
                item = Gtk.ModelButton.new()
                item.set_property("text", profiles[key])
                item.set_action_name("win.switch_profile")
                item.set_action_target_value(GLib.Variant("s", key))
                item.show()
                self.add(item)
                if profile == key:
                    action.change_state(GLib.Variant("s", profile))
        except Exception as e:
            print("ProfilesMenu::__init__():", e)

        # Edit button
        item = Gtk.Separator.new(Gtk.Orientation.HORIZONTAL)
        item.show()
        self.add(item)
        action = Gio.SimpleAction(name="edit_profiles")
        action.connect('activate',
                       self.__on_edit_profiles_activate)
        self.__window.add_action(action)
        item = Gtk.ModelButton.new()
        item.set_property("text", _("Edit profiles"))
        item.set_action_name("win.edit_profiles")
        item.show()
        self.add(item)

    def do_hide(self):
        """
            Remove action on hide
        """
        Gtk.Grid.do_hide(self)
        self.__window.remove_action("switch_profile")
        self.__window.remove_action("edit_profiles")

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
            App().websettings.set_profile(param.get_string(), uri)
            webview.stop_loading()
            # We need to reset URI before reloading
            # This allow WebViewNavigation to operate profile switching
            webview.load_uri("about:blank")
            webview.load_uri(uri)
        except Exception as e:
            print("ProfilesMenu::__on_profiles_activate:", e)
