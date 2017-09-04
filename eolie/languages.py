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

from gi.repository import Gtk, GLib, GtkSpell

from eolie.define import El


class LanguageRow(Gtk.EventBox):
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
        check = Gtk.CheckButton()
        check.connect("toggled", self.__on_check_toggled)
        check.show()
        grid.add(check)
        grid.add(label)
        self.add(grid)
        self.connect("button-press-event", self.__on_button_press_event, check)
        user_code = ""
        codes = El().websettings.get_languages(uri)
        if codes is None:
            codes = []
            locales = GLib.get_language_names()
            if locales:
                user_code = locales[0].split(".")[0]
                codes = [user_code]
        check.set_active(codes is not None and code in codes)
        # Here we force add of default language
        if user_code == code:
            check.toggled()

#######################
# PRIVATE             #
#######################
    def __on_button_press_event(self, row, event, check):
        """
            Toggle check box
            @param row as LanguageRow
            @param event as Gdk.ButtonEvent
            @param check as Gtk.CheckButton
        """
        check.set_active(not check.get_active())
        check.toggled()

    def __on_check_toggled(self, check):
        """
            Save state
            @param check as Gtk.CheckButton
        """
        active = check.get_active()
        if active:
            El().websettings.add_language(self.__code, self.__uri)
        else:
            El().websettings.remove_language(self.__code, self.__uri)
        El().active_window.container.current.webview.update_spell_checking()


class LanguagesWidget(Gtk.Bin):
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
        builder.add_from_resource("/org/gnome/Eolie/Languages.ui")
        builder.connect_signals(self)
        self.__switch = builder.get_object("switch")
        self.add(builder.get_object("languages"))

#######################
# PRIVATE             #
#######################
    def _on_map(self, listbox):
        """
            Populate languages
            @param listbox as Gtk.ListBox
        """
        self.__switch.set_active(El().settings.get_value("enable-spell-check"))
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
        El().settings.set_value("enable-spell-check",
                                GLib.Variant("b", state))
        listbox.set_sensitive(state)
        for window in El().windows:
            for view in window.container.views:
                context = view.webview.get_context()
                context.set_spell_checking_enabled(state)
