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

from gi.repository import Gtk, GLib, GObject

from gettext import gettext as _
from urllib.parse import urlparse

from eolie.search import Search
from eolie.define import App
from eolie.logger import Logger


class Item(GObject.GObject):
    name = GObject.Property(type=str,
                            default="")
    uri = GObject.Property(type=str,
                           default="")
    search = GObject.Property(type=str,
                              default="")
    keyword = GObject.Property(type=str,
                               default="")
    encoding = GObject.Property(type=str,
                                default="")
    bang = GObject.Property(type=str,
                            default="")

    def __init__(self):
        GObject.GObject.__init__(self)


class Row(Gtk.ListBoxRow):
    """
        A cookie row
    """

    def __init__(self, item):
        """
            Init row
            @param item as Item
        """
        Gtk.ListBoxRow.__init__(self)
        self.__item = item
        self.__label = Gtk.Label.new(item.get_property("name"))
        self.__label.set_max_width_chars(20)
        self.__label.set_property("halign", Gtk.Align.START)
        self.__label.show()
        self.add(self.__label)

    def set_name(self, name):
        """
            Set name
            @param name as str
        """
        self.__label.set_text(name)

    @property
    def is_valid(self):
        """
            True if item is valid
            @return bool
        """
        uri = self.__item.get_property("uri")
        search = self.__item.get_property("search")
        parsed = urlparse(uri)
        if parsed.scheme not in ["http", "https"] or not parsed.netloc:
            return False
        parsed = urlparse(search)
        if parsed.scheme not in ["http", "https"] or search.find("%s") == -1:
            return False
        return True

    @property
    def item(self):
        """
            Get associated item
            @return item
        """
        return self.__item


class SearchEngineDialog:
    """
        A search engine dialog
        THANKS TO EPIPHANY DEVS FOR UI FILE!
    """

    def __init__(self, parent):
        """
            Init widget
            @param parent as Gtk.Window
        """
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/DialogSearchEngine.ui")
        self.__dialog = builder.get_object("dialog")
        self.__dialog.set_transient_for(parent)
        self.__edit_box = builder.get_object("edit_box")
        self.__listbox = builder.get_object("list_box")
        self.__name_entry = builder.get_object("name_entry")
        self.__uri_entry = builder.get_object("uri_entry")
        self.__search_entry = builder.get_object("search_entry")
        self.__bang_entry = builder.get_object("bang_entry")
        self.__default_switch = builder.get_object("default_switch")
        self.__add_button = builder.get_object("add_button")
        self.__remove_button = builder.get_object("remove_button")
        self.__remove_button.set_sensitive(False)
        builder.connect_signals(self)

    def run(self):
        """
            Run dialog
        """
        self.__populate()
        self.__dialog.run()
        # Save engines
        engines = {}
        for child in self.__listbox.get_children():
            if child.is_valid:
                name = child.item.get_property("name")
                uri = child.item.get_property("uri")
                search = child.item.get_property("search")
                keyword = child.item.get_property("keyword")
                encoding = child.item.get_property("encoding")
                bang = child.item.get_property("bang")
                if name and search:
                    engines[name] = [uri, search, keyword, encoding, bang]
        App().search.save_engines(engines)
        App().search.update_default_engine()
        self.__dialog.destroy()

#######################
# PROTECTED           #
#######################
    def _on_default_switch_state_set(self, switch, state):
        """
            Update engine state
            @param switch as Gtk.Switch
            @param state as bool
        """
        if state:
            row = self.__listbox.get_selected_row()
            if row is not None:
                name = row.item.get_property("name")
                App().settings.set_value("search-engine",
                                         GLib.Variant("s", name))

    def _on_add_button_clicked(self, button):
        """
            Add a new engine
            @param button as Gtk.Button
        """
        # Only one New engine
        for child in self.__listbox.get_children():
            if child.item.name == _("New engine"):
                return

        item = Item()
        item.set_property("name",  _("New engine"))
        item.set_property("uri", "")
        item.set_property("search", "")
        item.set_property("bang", "")
        child = Row(item)
        child.show()
        self.__listbox.add(child)
        self.__listbox.select_row(child)
        self.__remove_button.set_sensitive(True)

    def _on_remove_button_clicked(self, button):
        """
            Remove engine
            @param button as Gtk.Button
        """
        row = self.__listbox.get_selected_row()
        if row is not None:
            row.destroy()

    def _on_row_selected(self, listbox, row):
        """
            Update entries
            @param listbox as Gtk.ListBox
            @param row as Row
        """
        if row is None:
            children = listbox.get_children()
            if children:
                GLib.idle_add(listbox.select_row, children[0])
            else:
                self.__remove_button.set_sensitive(False)
                self.__edit_box.set_sensitive(False)
            return
        self.__remove_button.set_sensitive(True)
        self.__edit_box.set_sensitive(True)
        self.__name_entry.set_text(row.item.get_property("name"))
        self.__uri_entry.set_text(row.item.get_property("uri"))
        self.__search_entry.set_text(row.item.get_property("search"))
        self.__bang_entry.set_text(row.item.get_property("bang"))
        default_search_engine = App().settings.get_value(
                                                  "search-engine").get_string()
        self.__default_switch.set_active(default_search_engine ==
                                         row.item.get_property("name"))

    def _on_name_entry_changed(self, entry):
        """
            Update search engine name
            @param entry as Gtk.Entry
        """
        new_name = entry.get_text()
        row = self.__listbox.get_selected_row()
        if row is None or not new_name:
            return
        # Update search engine if needed
        name = row.item.get_property("name")
        if name == App().settings.get_value("search-engine").get_string():
            App().settings.set_value("search-engine",
                                     GLib.Variant("s", new_name))
        row.item.set_property("name", new_name)
        row.set_name(new_name)

    def _on_uri_entry_changed(self, entry):
        """
            Update search engine uri
            @param entry as Gtk.Entry
        """
        uri = entry.get_text()
        row = self.__listbox.get_selected_row()
        if row is None or not uri:
            return
        row.item.set_property("uri", uri)
        parsed = urlparse(uri)
        if parsed.scheme not in ["http", "https"] or not parsed.netloc:
            entry.get_style_context().add_class("invalid-entry")
        else:
            entry.get_style_context().remove_class("invalid-entry")

    def _on_search_entry_changed(self, entry):
        """
            Update search engine search uri
            @param entry as Gtk.Entry
        """
        search = entry.get_text()
        row = self.__listbox.get_selected_row()
        if row is None or not search:
            return
        row.item.set_property("search", search)
        parsed = urlparse(search)
        if parsed.scheme not in ["http", "https"] or search.find("%s") == -1:
            entry.get_style_context().add_class("invalid-entry")
        else:
            entry.get_style_context().remove_class("invalid-entry")

    def _on_bang_entry_changed(self, entry):
        """
            Update search engine bang
            @param entry as Gtk.Entry
        """
        row = self.__listbox.get_selected_row()
        if row is None or not entry.get_text():
            return
        row.item.set_property("bang", entry.get_text())

    def _on_bang_key_press_event(self, entry, event):
        """
            Validate bang value
            @param entry as Gtk.Entry
            @param event as Gdk.EventKey
        """
        row = self.__listbox.get_selected_row()
        if row is None:
            return
        # Get all bang
        bangs = []
        for child in self.__listbox.get_children():
            if child == row:
                continue
            bang = child.item.get_property("bang")
            if bang:
                bangs.append(bang)
        if event.string in bangs:
            return True

#######################
# PRIVATE             #
#######################
    def __populate(self):
        """
            Populate the view with engines
        """
        search = Search()
        engines = search.engines
        try:
            # First load static engines
            for key in engines.keys():
                item = Item()
                item.set_property("name", key)
                item.set_property("uri", engines[key][0])
                item.set_property("search", engines[key][1])
                item.set_property("keyword", engines[key][2])
                item.set_property("encoding", engines[key][3])
                item.set_property("bang", engines[key][4])
                child = Row(item)
                child.show()
                self.__listbox.add(child)
        except Exception as e:
            Logger.error("DialogSearchEngine::__populate(): %s", e)
