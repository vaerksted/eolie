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

from gi.repository import Gtk, GLib, WebKit2, GObject, Pango

from eolie.define import MARGIN_SMALL
from eolie.utils import emit_signal
from eolie.logger import Logger


class Row(Gtk.ListBoxRow):
    """
        A row with a title and a checkbox
    """

    def __init__(self, item):
        """
            Init Row
            @param item as WebKit2.WebsiteData
        """
        Gtk.ListBoxRow.__init__(self)
        self.__item = item
        label = Gtk.Label.new(item.get_name())
        label.show()
        label.set_halign(Gtk.Align.START)
        label.set_property("margin", MARGIN_SMALL)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        self.add(label)

    @property
    def item(self):
        """
            Get title
            @return WebKit2.WebsiteData
        """
        return self.__item


class ClearDataDialog(Gtk.Bin):
    """
        A clear data dialog
        THANKS TO EPIPHANY DEVS FOR UI FILE!
    """

    __gsignals__ = {
        "destroy-me": (GObject.SignalFlags.RUN_FIRST, None, ())
    }

    def __init__(self):
        """
            Init widget
        """
        Gtk.Bin.__init__(self)
        self.__search = ""
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/DialogClearData.ui")
        builder.connect_signals(self)
        self.__search_bar = builder.get_object("search_bar")
        self.__clear_button = builder.get_object("clear_button")
        self.__listbox = builder.get_object("listbox")
        self.__listbox.set_sort_func(self.__sort_func)
        self.__listbox.set_filter_func(self.__filter_func)
        self.__populate()
        self.add(builder.get_object("widget"))

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
            Filter model
            @param entry as Gtk.SearchEntry
        """
        self.__search = entry.get_text()
        self.__listbox.invalidate_filter()

    def _on_clear_clicked(self, button):
        """
            Clear data
            @param button as Gtk.Button
        """
        context = WebKit2.WebContext.get_default()
        data_manager = context.get_property("website-data-manager")
        rows = self.__listbox.get_selected_rows()
        items = [row.item for row in rows]
        data_manager.remove(WebKit2.WebsiteDataTypes.ALL, items, None)
        for row in rows:
            row.destroy()

    def _on_search_toggled(self, button):
        """
            Show entry
            @param button as Gtk.Button
        """
        self.__search_bar.set_search_mode(button.get_active())

    def _on_row_selected(self, listbox, row):
        """
            Update clear button state
            @param listbox as Gtk.ListBox
            @param row as Gtk.ListBoxRow
        """
        self.__clear_button.set_sensitive(
            len(listbox.get_selected_rows()) != 0)

#######################
# PRIVATE             #
#######################
    def __sort_func(self, rowa, rowb):
        """
            Sort listbox
            @param rowa as Row
            @param rowb as Row
            @return bool
        """
        return rowa.item.get_name() > rowb.item.get_name()

    def __filter_func(self, row):
        """
            Filter listbox
            @param row as Row
            @return bool
        """
        return row.item.get_name().find(self.__search) != -1

    def __populate(self):
        """
            Populate treeview
        """
        context = WebKit2.WebContext.get_default()
        data_manager = context.get_property("website-data-manager")
        data_manager.fetch(WebKit2.WebsiteDataTypes.ALL,
                           None,
                           self.__on_data_manager_fetch)

    def __add_items(self, items):
        """
            Add items to model
            @param items as [WebKit2.WebsiteData]
        """
        if items:
            item = items.pop(0)
            row = Row(item)
            row.show()
            self.__listbox.add(row)
            GLib.idle_add(self.__add_items, items)

    def __on_data_manager_fetch(self, data_manager, result):
        """
            Get fetch result
            @param data_manager as WebKit2.WebsiteDataManager
            @param result as Gio.AsyncResult
        """
        try:
            items = data_manager.fetch_finish(result)
            self.__add_items(items)
        except Exception as e:
            Logger.error("ClearDataDialog::__on_data_manager_fetch(): %s", e)
