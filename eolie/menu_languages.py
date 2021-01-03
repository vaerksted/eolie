# Copyright (c) 2017-2021 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from gi.repository import Gtk, GLib, GtkSpell

from eolie.helper_gestures import GesturesHelper
from eolie.define import App


class LanguageRow(Gtk.ListBoxRow, GesturesHelper):
    """
        Language row (Allowing to select a language for uri)
    """

    def __init__(self, uri, name, code):
        """
            Init row
            @param uri as str
            @param name as str
            @param code as str
        """
        Gtk.EventBox.__init__(self)
        self.__uri = uri
        self.__code = code
        grid = Gtk.Grid()
        grid.set_column_spacing(5)
        grid.show()
        label = Gtk.Label.new(name)
        label.set_hexpand(True)
        label.set_property("halign", Gtk.Align.START)
        label.show()
        self.__check = Gtk.CheckButton()
        self.__check.show()
        grid.add(self.__check)
        grid.add(label)
        eventbox = Gtk.EventBox.new()
        eventbox.show()
        eventbox.add(grid)
        self.add(eventbox)
        GesturesHelper.__init__(self, eventbox)
        user_code = ""
        codes = App().websettings.get_languages(uri)
        if not codes:
            codes = []
            locales = GLib.get_language_names()
            if locales:
                user_code = locales[0].split(".")[0]
                codes = [user_code]
        self.__check.set_active(codes is not None and code in codes)
        self.__check.connect("toggled", self.__on_check_toggled)
        GesturesHelper.__init__(self, eventbox)

#######################
# PROTECTED           #
#######################
    def _on_primary_press_gesture(self, x, y, event):
        """
            Toggle check button
            @param x as int
            @param y as int
            @param event as Gdk.Event
        """
        toggled = not self.__check.get_active()
        self.__check.set_active(toggled)

#######################
# PRIVATE             #
#######################
    def __on_check_toggled(self, check):
        """
            Save state
            @param check as Gtk.CheckButton
        """
        active = check.get_active()
        if active:
            App().websettings.add_language(self.__code, self.__uri)
        else:
            App().websettings.remove_language(self.__code, self.__uri)
        App().active_window.container.webview.update_spell_checking(
            self.__uri)


class LanguagesMenu(Gtk.Bin):
    """
        Widget showing languages and allowing user to enable/disable
        spell check
    """

    def __init__(self, uri):
        """
            Init widget
            @param uri as str
        """
        Gtk.Bin.__init__(self)
        self.__uri = uri
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/LanguagesMenu.ui")
        builder.connect_signals(self)
        self.__switch = builder.get_object("switch")
        self.add(builder.get_object("languages"))

#######################
# PROTECTED           #
#######################
    def _on_map(self, listbox):
        """
            Populate languages
            @param listbox as Gtk.ListBox
        """
        enable_spell_checking = App().settings.get_value("enable-spell-check")
        self.__switch.set_active(enable_spell_checking)
        if not listbox.get_children():
            checker = GtkSpell.Checker()
            for language in checker.get_language_list():
                name = checker.decode_language_code(language)
                row = LanguageRow(self.__uri, name, language)
                row.show()
                listbox.add(row)

    def _on_state_set(self, listbox, state):
        """
            Save spell checking state
            @param listbox as Gtk.ListBox
            @param state as bool
        """
        App().settings.set_value("enable-spell-check",
                                 GLib.Variant("b", state))
        listbox.set_sensitive(state)
        for window in App().windows:
            for webview in window.container.webviews:
                context = webview.get_context()
                context.set_spell_checking_enabled(state)
