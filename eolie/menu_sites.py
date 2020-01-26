# Copyright (c) 2017-2020 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from eolie.define import App


class SitesMenu(Gtk.Grid):
    """
        Menu linked to a SitesManagerChild
    """

    def __init__(self, webviews, window):
        """
            Init menu
            @param webviews as [WebView]
            @param window as Window
        """
        self.__window = window
        self.__webviews = webviews
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
        for webview in webviews:
            uri = webview.uri
            if uri is None:
                continue
            title = webview.title
            item = Gtk.ModelButton.new()
            item.set_hexpand(True)
            item.set_property("text", title)
            item.set_action_name("win.switch_page")
            item.set_action_target_value(GLib.Variant("s", str(webview)))
            item.show()
            self.add(item)
        # Bottom section
        separator = Gtk.Separator.new(Gtk.Orientation.HORIZONTAL)
        separator.show()
        self.add(separator)
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
        # Pinned state
        uri = webviews[0].uri
        pinned = App().websettings.get("pinned", uri)
        action = Gio.SimpleAction.new_stateful(
                    "pinned",
                    None,
                    GLib.Variant.new_boolean(pinned))
        action.connect("change-state",
                       self.__on_pinned_change_state,
                       uri)
        self.__window.add_action(action)
        item = Gtk.ModelButton.new()
        item.set_property("text", _("Pinned site"))
        item.set_action_name("win.pinned")
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

#######################
# PRIVATE             #
#######################
    def __on_pinned_change_state(self, action, param, uri):
        """
            Set option value
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
            @param uri as str
        """
        action.set_state(param)
        App().websettings.set("pinned", uri, param.get_boolean())

    def __on_close_activate(self, action, param):
        """
            Close wanted page
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        for webview in self.__webviews:
            self.__window.container.try_close_webview(webview)

    def __on_modify_ua_activate(self, action, param):
        """
            Show a dialog allowing user to update User Agent
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        if self.__webviews:
            from eolie.dialog_modify_ua import ModifyUADialog
            dialog = ModifyUADialog(self.__webviews[0].uri, self.__window)
            dialog.run()

    def __on_action_activate(self, action, variant):
        """
            Switch view
            @param action as Gio.SimpleAction
            @param variant as GLib.Variant
            @param view as View
        """
        webview_str = variant.get_string()
        for webview in self.__window.container.webviews:
            if webview_str == str(webview):
                self.__window.container.set_visible_webview(webview)
                break
