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

from gi.repository import Gtk, Pango

from eolie.define import El


class ModifyUADialog:
    """
        Modify user agent for uri
    """
    def __init__(self, uri, window):
        """
            Init widget
            @param uri as str
            @param window as Gtk.Window
        """
        self.__uri = uri
        self.__window = window
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/DialogModifyUA.ui")
        builder.connect_signals(self)
        self.__dialog = builder.get_object("dialog")
        self.__dialog.set_transient_for(window)
        headerbar = builder.get_object("headerbar")
        view = builder.get_object("view")
        self.__model = builder.get_object("model")
        self.__selection = builder.get_object("selection")
        self.__entry = builder.get_object("entry")
        self.__entry.connect("changed", self.__on_entry_changed)
        self.__dialog.set_titlebar(headerbar)
        renderer0 = Gtk.CellRendererText()
        renderer0.set_property("ellipsize-set", True)
        renderer0.set_property("ellipsize", Pango.EllipsizeMode.END)
        column = Gtk.TreeViewColumn("")
        column.set_expand(True)
        column.pack_start(renderer0, True)
        column.add_attribute(renderer0, "text", 0)
        view.append_column(column)
        user_agent = El().websettings.get_user_agent(self.__uri)
        self.__select_matching(user_agent)

    def run(self):
        """
            Run dialog
        """
        self.__dialog.run()
        self.__dialog.destroy()

#######################
# PROTECTED           #
#######################
    def _on_selection_changed(self, selection):
        """
            Update entry
            @param selection as Gtk.TreeSelection
        """
        (model, items) = selection.get_selected_rows()
        if items:
            value = model[items[0]][1]
            # Can't set a null value in glade :-/
            if value == "None":
                value = ""
            self.__entry.disconnect_by_func(self.__on_entry_changed)
            self.__entry.set_text(value)
            self.__entry.connect("changed", self.__on_entry_changed)

    def _on_dialog_response(self, dialog, response_id):
        """
            Save user agent
            @param dialog as Gtk.Dialog
            @param response_id as int
        """
        if response_id != Gtk.ResponseType.DELETE_EVENT:
            user_agent = self.__entry.get_text()
            El().websettings.set_user_agent(user_agent, self.__uri)

#######################
# PRIVATE             #
#######################
    def __select_matching(self, user_agent):
        """
            Select matching element
            @param user_agent as str
        """
        for item in self.__model:
            value = "" if item[1] == "None" else item[1]
            if value == user_agent:
                self.__selection.select_iter(item.iter)
                return
        self.__selection.unselect_all()

    def __on_entry_changed(self, entry):
        """
            Update matching
            @param entry as Gtk.Entry
        """
        self.__select_matching(entry.get_text())
