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
from urllib.parse import urlparse

from eolie.define import App
from eolie.logger import Logger


class SitesMenu(Gtk.Grid):
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
        self.__views = views
        Gtk.Grid.__init__(self)
        self.set_margin_start(5)
        self.set_margin_end(5)
        self.set_margin_top(5)
        self.set_margin_bottom(5)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        # Page switcher
        action = Gio.SimpleAction.new("switch_page",
                                      GLib.VariantType.new("s"))
        self.__window.add_action(action)
        action.connect("activate",
                       self.__on_action_activate)
        for view in views:
            uri = view.webview.uri
            if uri is None:
                continue
            title = view.webview.title
            item = Gtk.ModelButton.new()
            item.set_hexpand(True)
            item.set_property("text", title)
            item.set_action_name("win.switch_page")
            item.set_action_target_value(GLib.Variant("s", str(view)))
            item.show()
            self.add(item)
        # Bottom section
        separator = Gtk.Separator.new(Gtk.Orientation.HORIZONTAL)
        separator.show()
        self.add(separator)
        # Profiles switcher
        webview = views[0].webview
        if not webview.ephemeral:
            parsed = urlparse(webview.uri)
            if parsed.scheme in ["http", "https"]:
                item = Gtk.ModelButton.new()
                item.set_property("text", _("Profiles"))
                item.set_property("menu-name", "profiles")
                item.show()
                self.add(item)
        # Move to
        item = Gtk.ModelButton.new()
        item.set_property("text", _("Move to"))
        item.set_property("menu-name", "moveto")
        item.show()
        self.add(item)
        # Modify UA
        if App().settings.get_value("developer-extras"):
            action = Gio.SimpleAction.new("user_agent")
            action.connect("activate", self.__on_modify_ua_activate)
            self.__window.add_action(action)
            item = Gtk.ModelButton.new()
            item.set_property("text", _("Modify user agent"))
            item.set_action_name("win.user_agent")
            item.show()
            self.add(item)
        # Close site
        action = Gio.SimpleAction.new("close_site")
        action.connect("activate", self.__on_close_activate)
        self.__window.add_action(action)
        item = Gtk.ModelButton.new()
        item.set_property("text", _("Close site"))
        item.set_action_name("win.close_site")
        item.show()
        self.add(item)

    def do_hide(self):
        """
            Remove actions on hide
        """
        Gtk.Grid.do_hide(self)
        self.__window.remove_action("switch_page")
        self.__window.remove_action("user_agent")
        self.__window.remove_action("close_site")

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
            App().websettings.set_profile(param.get_string(), uri)
            webview.stop_loading()
            webview.load_uri(uri)
        except Exception as e:
            Logger.error("SitesMenu::__on_profiles_activate: %s", e)

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

    def __on_action_activate(self, action, variant):
        """
            Switch view
            @param action as Gio.SimpleAction
            @param variant as GLib.Variant
            @param view as View
        """
        view_str = variant.get_string()
        for view in self.__window.container.views:
            if view_str == str(view):
                self.__window.container.set_current(view, True)
                break
