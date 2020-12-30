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

from gi.repository import Gtk, GObject, Pango, GLib

from eolie.helper_passwords import PasswordsHelper
from eolie.define import App, MARGIN_SMALL
from eolie.utils import emit_signal
from eolie.logger import Logger


class Row(Gtk.ListBoxRow):
    """
        A row
    """

    def __init__(self, scheme, host):
        """
            Init Row
            @param scheme as str
            @param host as str
        """
        Gtk.ListBoxRow.__init__(self)
        self.__scheme = scheme
        self.__host = host
        label = Gtk.Label.new("%s://%s" % (scheme, host))
        label.show()
        label.set_halign(Gtk.Align.START)
        label.set_property("margin", MARGIN_SMALL)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        self.add(label)

    @property
    def scheme(self):
        """
            Get scheme
            @return str
        """
        return self.__scheme

    @property
    def host(self):
        """
            Get host
            @return str
        """
        return self.__host


class NotificationsDialog(Gtk.Bin):
    """
        Show notifications authorizations
    """

    __gsignals__ = {
        "destroy-me": (GObject.SignalFlags.RUN_FIRST, None, ())
    }

    def __init__(self):
        """
            Init dialog
        """
        Gtk.Bin.__init__(self)
        self.__filter = ""
        self.__helper = PasswordsHelper()
        builder = Gtk.Builder()
        builder.add_from_resource('/org/gnome/Eolie/DialogNotifications.ui')
        builder.connect_signals(self)
        self.__search_bar = builder.get_object("search_bar")
        self.__remove_button = builder.get_object("remove_button")
        self.__listbox = builder.get_object("listbox")
        self.__listbox.set_filter_func(self.__filter_func)
        self.__listbox.set_sort_func(self.__sort_func)
        self.add(builder.get_object('widget'))
        self.__populate()

#######################
# PROTECTED           #
#######################
    def _on_back_clicked(self, button):
        """
            Ask to be destroyed
            @param button as Gtk.Button
        """
        emit_signal(self, "destroy-me")

    def _on_search_changed(self, entry):
        """
            Update filter
            @param entry as Gtk.Entry
        """
        self.__filter = entry.get_text()
        self.__listbox.invalidate_filter()

    def _on_remove_clicked(self, button):
        """
            Remove all passwords
            @param button as Gtk.Button
        """
        values = list(App().settings.get_value("notification-domains"))
        for row in self.__listbox.get_selected_rows():
            values.remove("%s;%s" % (row.scheme, row.host))
            row.destroy()
        App().settings.set_value("notification-domains",
                                 GLib.Variant("as", values))

    def _on_row_selected(self, listbox, row):
        """
            Update clear button state
            @param listbox as Gtk.ListBox
            @param row as Gtk.ListBoxRow
        """
        self.__remove_button.set_sensitive(
            len(listbox.get_selected_rows()) != 0)

    def _on_search_toggled(self, button):
        """
            Show entry
            @param button as Gtk.Button
        """
        self.__search_bar.set_search_mode(button.get_active())

#######################
# PRIVATE             #
#######################
    def __filter_func(self, row):
        """
            Filter rows
            @param row as Row
        """
        return self.__filter in row.host

    def __sort_func(self, row1, row2):
        """
            Sort rows
            @param row1 as Row
            @param row2 as Row
        """
        return row2.host < row1.host

    def __populate(self):
        """
            Populate view
        """
        values = App().settings.get_value("notification-domains")
        try:
            for value in values:
                (scheme, host) = value.split(";")
                row = Row(scheme, host)
                row.show()
                self.__listbox.add(row)
        except Exception as e:
            Logger.error("NotificationsDialog::__populate(): %s", e)
