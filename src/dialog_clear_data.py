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

from gi.repository import Gtk, GLib, WebKit2

from gettext import gettext as _


class ClearDataDialog:
    """
        A clear data dialog
    """

    class TimeSpan:
        HOUR = 0
        DAY = 1
        WEEK = 2
        FOUR_WEEK = 3
        FOREVER = 4

    class ModelColumn:
        TOGGLE = 0
        TYPE = 1
        NAME = 2
        DATA = 3
        INCONSISTENT = 4

    TimeSpanValues = {
        TimeSpan.HOUR: GLib.TIME_SPAN_HOUR,
        TimeSpan.DAY: GLib.TIME_SPAN_DAY,
        TimeSpan.WEEK: GLib.TIME_SPAN_DAY * 7,
        TimeSpan.FOUR_WEEK: GLib.TIME_SPAN_DAY * 7 * 4,
        TimeSpan.FOREVER: 0
    }

    def __init__(self, parent):
        """
            Init widget
            @param parent as Gtk.Window
        """
        self.__search = ""
        self.__parent_iters = {}
        self.__timespan = 0
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/ClearData.ui")
        builder.connect_signals(self)
        self.__dialog = builder.get_object("dialog")
        self.__dialog.set_transient_for(parent)
        self.__stack = builder.get_object("stack")
        self.__stack.set_visible_child_name("view")
        headerbar = builder.get_object("headerbar")
        self.__dialog.set_titlebar(headerbar)
        self.__model = Gtk.TreeStore(bool,                 # Selected
                                     int,                  # Type
                                     str,                  # Value
                                     WebKit2.WebsiteData,  # Data
                                     bool)                 # Inconsistent
        self.__filter = self.__model.filter_new()
        self.__filter.set_visible_func(self.__on_treeview_filter)
        builder.get_object("treeview").set_model(self.__filter)

    def run(self):
        """
            Run dialog
        """
        self.__populate()
        self.__dialog.run()
        self.__dialog.destroy()

#######################
# PROTECTED           #
#######################
    def _on_item_toggled(self, renderer, path):
        """
            Check item and update parent/child
            @param renderer as Gtk.CellRendererToggle
            @param path as Gtk.TreePath
        """
        iterator = self.__filter.get_iter(path)
        item = self.__filter.get_value(iterator, self.ModelColumn.DATA)
        toggle = not self.__filter.get_value(iterator, self.ModelColumn.TOGGLE)
        self.__filter.set_value(iterator, self.ModelColumn.TOGGLE, toggle)
        # Check children
        if item is None:
            self.__filter.set_value(iterator,
                                    self.ModelColumn.INCONSISTENT,
                                    False)
            child = self.__filter.iter_children(iterator)
            while child is not None:
                self.__filter.set_value(child, self.ModelColumn.TOGGLE, toggle)
                child = self.__filter.iter_next(child)
        else:
            self.__check_parent(iterator)

    def _on_combo_changed(self, combobox):
        """
            Update model
            @param combobox as Gtk.ComboBox
        """
        active = combobox.get_active()
        self.__timespan = self.TimeSpanValues[active]
        self.__filter.refilter()

    def _on_search_changed(self, entry):
        """
            Filter model
            @param entry as Gtk.SearchEntry
        """
        self.__search = entry.get_text()
        self.__filter.refilter()

    def _on_dialog_response(self, dialog, response_id):
        """
            Clear data
            @param dialog as Gtk.Dialog
            @param response_id as int
        """
        context = WebKit2.WebContext.get_default()
        data_manager = context.get_property("website-data-manager")
        # Remove items
        if self.__timespan == 0:
            items = {}
            # Assemble item and its types
            for parent in self.__filter:
                child = self.__filter.iter_children(parent.iter)
                while child is not None:
                    if not self.__filter.get_value(child,
                                                   self.ModelColumn.TOGGLE):
                        child = self.__filter.iter_next(child)
                        continue
                    data = self.__filter.get_value(child,
                                                   self.ModelColumn.DATA)
                    type = self.__filter.get_value(child,
                                                   self.ModelColumn.TYPE)
                    flag = WebKit2.WebsiteDataTypes(type)
                    if data not in items.keys():
                        items[data] = WebKit2.WebsiteDataTypes(0)
                    items[data] |= flag
                    child = self.__filter.iter_next(child)
            for data in items.keys():
                types = items[data]
                data_manager.remove(types, [data], None, None)
        # Clear data for types
        else:
            types = WebKit2.WebsiteDataTypes(0)
            for item in self.__filter:
                if item[self.ModelColumn.TOGGLE]:
                    types |= WebKit2.WebsiteDataTypes(
                                                   item[self.ModelColumn.TYPE])
            data_manager.clear(types, self.__timespan, None, None)

#######################
# PRIVATE             #
#######################
    def __get_name(self, data_type):
        """
            Get name for type
            @param data_type as int
            @return str
        """
        name = ""
        if data_type == WebKit2.WebsiteDataTypes.MEMORY_CACHE:
            name = _("Memory cache")
        elif data_type == WebKit2.WebsiteDataTypes.DISK_CACHE:
            name = _("HTTP disk cache")
        elif data_type == WebKit2.WebsiteDataTypes.OFFLINE_APPLICATION_CACHE:
            name = _("Offline web application cache")
        elif data_type == WebKit2.WebsiteDataTypes.SESSION_STORAGE:
            name = _("Session storage data")
        elif data_type == WebKit2.WebsiteDataTypes.LOCAL_STORAGE:
            name = _("Local storage data")
        elif data_type == WebKit2.WebsiteDataTypes.WEBSQL_DATABASES:
            name = _("WebSQL databases")
        elif data_type == WebKit2.WebsiteDataTypes.INDEXEDDB_DATABASES:
            name = _("IndexedDB databases")
        elif data_type == WebKit2.WebsiteDataTypes.PLUGIN_DATA:
            name = _("Plugins data")
        elif data_type == WebKit2.WebsiteDataTypes.COOKIES:
            name = _("Cookies")
        return name

    def __get_types(self, data_types):
        """
            Extract types from flags
            @param data_types as int
            @return [int]
        """
        types = []
        if data_types & WebKit2.WebsiteDataTypes.MEMORY_CACHE:
            types.append(WebKit2.WebsiteDataTypes.MEMORY_CACHE)
        elif data_types & WebKit2.WebsiteDataTypes.DISK_CACHE:
            types.append(WebKit2.WebsiteDataTypes.DISK_CACHE)
        elif data_types & WebKit2.WebsiteDataTypes.OFFLINE_APPLICATION_CACHE:
            types.append(WebKit2.WebsiteDataTypes.OFFLINE_APPLICATION_CACHE)
        elif data_types & WebKit2.WebsiteDataTypes.SESSION_STORAGE:
            types.append(WebKit2.WebsiteDataTypes.SESSION_STORAGE)
        elif data_types & WebKit2.WebsiteDataTypes.LOCAL_STORAGE:
            types.append(WebKit2.WebsiteDataTypes.LOCAL_STORAGE)
        elif data_types & WebKit2.WebsiteDataTypes.WEBSQL_DATABASES:
            types.append(WebKit2.WebsiteDataTypes.WEBSQL_DATABASES)
        elif data_types & WebKit2.WebsiteDataTypes.INDEXEDDB_DATABASES:
            types.append(WebKit2.WebsiteDataTypes.INDEXEDDB_DATABASES)
        elif data_types & WebKit2.WebsiteDataTypes.PLUGIN_DATA:
            types.append(WebKit2.WebsiteDataTypes.PLUGIN_DATA)
        elif data_types & WebKit2.WebsiteDataTypes.COOKIES:
            types.append(WebKit2.WebsiteDataTypes.COOKIES)
        elif data_types & WebKit2.WebsiteDataTypes.ALL:
            types = [WebKit2.WebsiteDataTypes.MEMORY_CACHE,
                     WebKit2.WebsiteDataTypes.DISK_CACHE,
                     WebKit2.WebsiteDataTypes.OFFLINE_APPLICATION_CACHE,
                     WebKit2.WebsiteDataTypes.SESSION_STORAGE,
                     WebKit2.WebsiteDataTypes.LOCAL_STORAGE,
                     WebKit2.WebsiteDataTypes.WEBSQL_DATABASES,
                     WebKit2.WebsiteDataTypes.INDEXEDDB_DATABASES,
                     WebKit2.WebsiteDataTypes.PLUGIN_DATA,
                     WebKit2.WebsiteDataTypes.COOKIES]
        return types

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
            @param items as [str]
        """
        if items:
            item = items.pop(0)
            for t in self.__get_types(item.get_types()):
                if t not in self.__parent_iters.keys():
                    self.__parent_iters[t] = self.__model.append(
                                                        None,
                                                        (False,
                                                         t,
                                                         self.__get_name(t),
                                                         None,
                                                         False))
                name = item.get_name()
                self.__model.append(self.__parent_iters[t],
                                    (False, t, name, item, False))
            GLib.idle_add(self.__add_items, items)

    def __check_parent(self, iterator):
        """
            Check parent state
            @param iterator as Gtk.TreeIter
        """
        parent = self.__filter.iter_parent(iterator)
        parent_toggle = self.__filter.get_value(parent,
                                                self.ModelColumn.TOGGLE)
        child = self.__filter.iter_children(parent)
        inconsistent = False
        while child is not None:
            toggle = self.__filter.get_value(child, self.ModelColumn.TOGGLE)
            if toggle != parent_toggle:
                inconsistent = True
            child = self.__filter.iter_next(child)
        self.__filter.set_value(parent, self.ModelColumn.INCONSISTENT,
                                inconsistent)

    def __should_be_visible(self, iterator):
        """
            Check if parent should be visible
            @param iterator as Gtk.TreeIter
        """
        child = None
        (result, child_iter) = self.__filter.convert_child_iter_to_iter(
                                                                      iterator)
        if result:
            child = self.__filter.iter_children(child_iter)
        return child is not None

    def __on_treeview_filter(self, model, iterator, data):
        """
            @param model as Gtk.TreeModel
            @param iterator as Gtk.TreeIter
            @param data as object
        """
        if self.__search == "" and self.__timespan == 0:
            return True
        item = model.get_value(iterator, self.ModelColumn.DATA)
        if item is None:
            if self.__timespan != 0:
                return True
            elif self.__should_be_visible(iterator):
                return True
            else:
                return False
        name = model.get_value(iterator, self.ModelColumn.NAME)
        if self.__timespan != 0:
            return False
        elif name.lower().find(self.__search.lower()) != -1:
            return True

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
            print("ClearDataDialog::__on_data_manager_fetch():", e)
