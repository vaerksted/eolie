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

from gi.repository import Gtk

from gettext import gettext as _

from eolie.define import El


class ImportBookmarksDialog:
    """
        Import bookarks dialog
    """

    class __Choice:
        FIREFOX = 0
        CHROMIUM = 1
        CHROME = 2
        OTHERS = 3

    def __init__(self, parent):
        """
            Init widget
            @param parent as Gtk.Window
        """
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/ImportBookmarks.ui")
        builder.connect_signals(self)
        self.__dialog = builder.get_object("dialog")
        self.__dialog.set_transient_for(parent)
        self.__listbox = builder.get_object("listbox")
        for item in ["Firefox", "Chromium", "Chrome", _("Others")]:
            label = Gtk.Label.new(item)
            label.show()
            self.__listbox.add(label)
        headerbar = builder.get_object("headerbar")
        self.__dialog.set_titlebar(headerbar)

    def run(self):
        """
            Run dialog
        """
        self.__dialog.run()
        self.__dialog.destroy()

#######################
# PROTECTED           #
#######################
    def _on_dialog_response(self, dialog, response_id):
        """
            Import bookmarks
            @param dialog as Gtk.Dialog
            @param response_id as int
        """
        if response_id == Gtk.ResponseType.DELETE_EVENT:
            return
        index = self.__listbox.get_selected_row().get_index()
        if index == self.__Choice.FIREFOX:
            El().bookmarks.import_firefox()
        return

#######################
# PRIVATE             #
#######################
