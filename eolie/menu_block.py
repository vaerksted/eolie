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

from gi.repository import Gtk, Gio, GLib

from hashlib import sha256
from urllib.parse import urlparse

from eolie.define import App


class BlockMenu(Gtk.Bin):
    """
        Menu for block policy management
    """

    def __init__(self, uri, window, trust):
        """
            Init widget
            @param uri as str
            @param window as Window
            @param trust a bool
        """
        Gtk.Bin.__init__(self)
        self._actions = []
        self.connect("map", self._on_map)
        self.connect("unmap", self._on_unmap)
        self.__uri = uri
        self.__window = window
        # Enable blocking
        option_value = App().settings.get_value(self._option_block)
        action = Gio.SimpleAction.new_stateful(
               self._option_block,
               None,
               GLib.Variant.new_boolean(option_value))
        action.connect("change-state",
                       self.__on_action_change_state,
                       self._option_block)
        window.add_action(action)

        # Trust JS blocking
        if trust:
            option_value = App().settings.get_value(self._option_trust)
            action = Gio.SimpleAction.new_stateful(
                   self._option_trust,
                   None,
                   GLib.Variant.new_boolean(option_value))
            action.connect("change-state",
                           self.__on_action_change_state,
                           self._option_trust)
            window.add_action(action)

    @property
    def window(self):
        """
            Get related window
            @return Window
        """
        return self.__window

    @property
    def uri(self):
        """
            Get related uri
            @return str
        """
        return self.__uri

#######################
# PROTECTED           #
#######################
    def _on_map(self, widget):
        """
            @param widget as Gtk.Widget
        """
        pass

    def _on_unmap(self, widget):
        """
            Remove registered actions
            @param widget as Gtk.Widget
        """
        for action in self._actions:
            self.window.remove_action(action)

#######################
# PRIVATE             #
#######################
    def __on_action_change_state(self, action, param, option):
        """
            Set option value
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
            @param option as str
        """
        action.set_state(param)
        App().settings.set_value(option, param)
        self.window.container.current.webview.reload()


class ExceptionBlockMenu(BlockMenu):
    """
        Menu for policy management with exceptions
    """
    def __init__(self, uri, window, trust, exception, database):
        """
            Init menu
            @param uri as str
            @param window as Window
            @param trust as bool
            @param exception as str
            @param database as DatabaseExceptions
        """
        BlockMenu.__init__(self, uri, window, trust)
        self.__database = database
        self.__action = Gio.SimpleAction.new_stateful(
                                                   exception,
                                                   GLib.VariantType.new("s"),
                                                   GLib.Variant("s", "none"))
        self.__action.connect("activate", self.__on_action_change_state)
        window.add_action(self.__action)

        parsed = urlparse(uri)
        if parsed.scheme in ["http", "https"]:
            page_ex = database.find(parsed.netloc + parsed.path)
            site_ex = database.find(parsed.netloc)
            if not page_ex and not site_ex:
                self.__action.change_state(GLib.Variant("s", "none"))
            elif site_ex:
                self.__action.change_state(GLib.Variant("s", "site"))
            else:
                self.__action.change_state(GLib.Variant("s", "page"))

#######################
# PRIVATE             #
#######################
    def __on_action_change_state(self, action, param):
        """
            Set option value
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        action.set_state(param)
        parsed = urlparse(self.uri)
        page_ex = self.__database.find(parsed.netloc + parsed.path)
        site_ex = self.__database.find(parsed.netloc)
        # Clean previous exceptions
        if param.get_string() in ["site", "none"]:
            if page_ex:
                self.__database.remove_exception(parsed.netloc + parsed.path)
        if param.get_string() in ["page", "none"]:
            if site_ex:
                self.__database.remove_exception(parsed.netloc)
        # Add new exceptions
        if param.get_string() == "site":
            self.__database.add_exception(parsed.netloc)
        elif param.get_string() == "page":
            self.__database.add_exception(parsed.netloc + parsed.path)
        self.window.container.current.webview.reload()


class AdblockMenu(ExceptionBlockMenu):
    """
        Menu for Adblock policy management
    """

    def __init__(self, uri, window):
        """
            Init menu
            @param uri as str
            @param window as Window
        """
        self._option_block = "adblock"
        self._option_trust = "trust-websites-adblock"
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/AdblockMenu.ui")
        builder.connect_signals(self)
        self.__submenu = builder.get_object("submenu")
        ExceptionBlockMenu.__init__(self, uri, window, True,
                                    "adblock_exceptions",
                                    App().adblock_exceptions)
        self.add(builder.get_object("menu"))


class PopupBlockMenu(ExceptionBlockMenu):
    """
        Menu for Popup policy management
    """

    def __init__(self, uri, window):
        """
            Init menu
            @param uri as str
            @param window as Window
        """
        self._option_block = "popupblock"
        self._option_trust = "trust-websites-popup"
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/PopupBlockMenu.ui")
        builder.connect_signals(self)
        self.__submenu = builder.get_object("submenu")
        ExceptionBlockMenu.__init__(self, uri, window, True,
                                    "popup_exceptions",
                                    App().popup_exceptions)
        self.add(builder.get_object("menu"))


class ImageBlockMenu(ExceptionBlockMenu):
    """
        Menu for Popup policy management
    """

    def __init__(self, uri, window):
        """
            Init menu
            @param uri as str
            @param window as Window
        """
        self._option_block = "imageblock"
        self._option_trust = "trust-websites-image"
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/ImageBlockMenu.ui")
        builder.connect_signals(self)
        self.__submenu = builder.get_object("submenu")
        ExceptionBlockMenu.__init__(self, uri, window, False,
                                    "image_exceptions",
                                    App().image_exceptions)
        self.add(builder.get_object("menu"))


class JSBlockMenu(BlockMenu):
    """
        Menu for JS block policy management
    """

    def __init__(self, uri, window):
        """
            Init menu
            @param uri as str
            @param window as Window
        """
        self._option_block = "jsblock"
        self._option_trust = "trust-websites-js"
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/JSBlockMenu.ui")
        builder.connect_signals(self)
        self.__submenu = builder.get_object("submenu")
        BlockMenu.__init__(self, uri, window, True)
        self.add(builder.get_object("menu"))

#######################
# PROTECTED           #
#######################
    def _on_map(self, widget):
        """
            Populate Scripts
            @param widget as Gtk.Widget
        """
        BlockMenu._on_map(self, widget)
        self._actions = []
        page_id = self.window.container.current.webview.get_page_id()
        App().helper.call("GetScripts", page_id, None,
                          self.__on_get_scripts)

    def _on_unmap(self, widget):
        """
            Clear submenu
            @param widget a Gtk.Widget
        """
        BlockMenu._on_unmap(self, widget)
        for child in self.__submenu.get_children():
            child.destroy()

#######################
# PRIVATE             #
#######################
    def __on_action_change_state(self, action, param, uri):
        """
            Set option value
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
            @param uri as str
        """
        active = param.get_boolean()
        action.set_state(param)
        parsed = urlparse(self.uri)
        if active:
            App().js_exceptions.remove_exception(uri, parsed.netloc)
        else:
            App().js_exceptions.add_exception(uri, parsed.netloc)

    def __on_get_scripts(self, source, result):
        """
            Populate listbox with scripts
            @param source as GObject.Object
            @param result as Gio.AsyncResult
        """
        try:
            parsed = urlparse(self.uri)
            uris = source.call_finish(result)[0]
            db_uris = App().js_exceptions.get_values_for_domain(parsed.netloc)
            for uri in list(set(db_uris) | set(uris)):
                button = Gtk.ModelButton.new()
                button.set_label(uri)
                button.get_child().set_property("halign", Gtk.Align.START)
                encoded = sha256(uri.encode("utf-8")).hexdigest()
                button.set_action_name("win.%s" % encoded)
                active = not App().js_exceptions.find(uri, parsed.netloc)
                action = Gio.SimpleAction.new_stateful(
                                              encoded,
                                              None,
                                              GLib.Variant.new_boolean(active))
                action.connect("change-state",
                               self.__on_action_change_state,
                               uri)
                self._actions.append(encoded)
                self.window.add_action(action)
                button.show()
                self.__submenu.add(button)
        except Exception as e:
            print("JSBlockMenu::__on_get_scripts()", e)
