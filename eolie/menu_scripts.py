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

from gi.repository import Gtk, GLib

from eolie.define import App


class ScriptRow(Gtk.EventBox):
    """
        Script row
    """

    def __init__(self, uri, domain):
        """
            Init row
            @param uri as str
            @param domain as str
        """
        Gtk.EventBox.__init__(self)
        self.__uri = uri
        self.__domain = domain
        grid = Gtk.Grid()
        grid.set_column_spacing(5)
        grid.show()
        label = Gtk.Label.new(uri)
        label.set_hexpand(True)
        label.set_property("halign", Gtk.Align.START)
        label.show()
        check = Gtk.CheckButton()
        check.show()
        grid.add(check)
        grid.add(label)
        self.add(grid)
        self.connect("button-press-event", self.__on_button_press_event, check)
        check.set_active(not App().js_exceptions.find(uri, domain))
        check.connect("toggled", self.__on_check_toggled)

#######################
# PRIVATE             #
#######################
    def __on_button_press_event(self, row, event, check):
        """
            Toggle check box
            @param row as ScriptRow
            @param event as Gdk.ButtonEvent
            @param check as Gtk.CheckButton
        """
        check.set_active(not check.get_active())

    def __on_check_toggled(self, check):
        """
            Save state
            @param check as Gtk.CheckButton
        """
        active = check.get_active()
        if active:
            App().js_exceptions.remove_exception(self.__uri, self.__domain)
        else:
            App().js_exceptions.add_exception(self.__uri, self.__domain)


class ScriptsMenu(Gtk.Bin):
    """
        Widget showing Scripts and allowing user to enable/disable
        spell check
    """

    def __init__(self, netloc):
        """
            Init widget
            @param netloc as str
        """
        self.__domain = netloc
        Gtk.Bin.__init__(self)
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/ScriptsMenu.ui")
        builder.connect_signals(self)
        self.__switch = builder.get_object("switch")
        self.add(builder.get_object("scripts"))

#######################
# PROTECTED           #
#######################
    def _on_map(self, listbox):
        """
            Populate Scripts
            @param listbox as Gtk.ListBox
        """
        for child in listbox.get_children():
            child.destroy()
        state = App().settings.get_value("jsblock")
        self.__switch.set_active(state)
        listbox.set_sensitive(state)
        page_id = App().active_window.container.current.webview.get_page_id()
        App().helper.call("GetScripts", page_id, None,
                          self.__on_get_scripts, listbox)

    def _on_state_set(self, listbox, state):
        """
            Save js blocker state
            @param listbox as Gtk.ListBox
            @param state as bool
        """
        App().settings.set_value("jsblock",
                                 GLib.Variant("b", state))
        listbox.set_sensitive(state)

#######################
# PRIVATE             #
#######################
    def __on_get_scripts(self, source, result, listbox):
        """
            Populate listbox with scripts
            @param source as GObject.Object
            @param result as Gio.AsyncResult
            @param listbox as Gtk.ListBox
        """
        try:
            uris = source.call_finish(result)[0]
            db_uris = App().js_exceptions.get_values_for_domain(self.__domain)
            for uri in list(set(db_uris) | set(uris)):
                row = ScriptRow(uri, self.__domain)
                row.show()
                listbox.add(row)
        except Exception as e:
            print("ScriptsMenu::__on_get_scripts()", e)
