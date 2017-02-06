# Copyright (c) 2014-2016 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from gi.repository import Gtk, GLib, Pango

from locale import strcoll

from eolie.define import El


class EditBookmarkWidget(Gtk.Bin):
    """
        Widget allowing to edit a bookmark
    """

    def __init__(self, bookmark_id):
        """
            Init widget
            @param bookmark id as int
        """
        Gtk.Bin.__init__(self)
        self.__bookmark_id = bookmark_id
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/BookmarkEdit.ui")
        builder.connect_signals(self)
        self.__treeview = builder.get_object("treeview")
        self.__add_tag_button = builder.get_object("add_tag_button")
        self.__remove_tag_button = builder.get_object("remove_tag_button")
        self.__new_tag_entry = builder.get_object("new_tag_entry")
        self.__title_entry = builder.get_object("title_entry")
        self.__uri_entry = builder.get_object("uri_entry")
        self.__title_entry.set_text(El().bookmarks.get_title(bookmark_id))
        self.__uri_entry.set_text(El().bookmarks.get_uri(bookmark_id))
        self.__model = builder.get_object("model")
        self.__model.set_sort_column_id(1, Gtk.SortType.ASCENDING)
        self.__model.set_sort_func(1, self.__sort_items)
        renderer0 = Gtk.CellRendererToggle()
        renderer0.set_property('activatable', True)
        renderer0.connect('toggled', self.__on_item_toggled)
        column0 = Gtk.TreeViewColumn("", renderer0, active=1)
        renderer1 = Gtk.CellRendererText()
        renderer1.set_property('ellipsize-set', True)
        renderer1.set_property('ellipsize', Pango.EllipsizeMode.END)
        renderer1.set_property('editable', True)
        renderer1.connect('edited', self.__on_tag_edited)
        column1 = Gtk.TreeViewColumn("", renderer1, markup=0)
        column1.set_expand(True)
        self.__treeview.append_column(column0)
        self.__treeview.append_column(column1)
        for (tag_id, title) in El().bookmarks.get_tags():
            self.__model.append([title, El().bookmarks.has_tag(bookmark_id,
                                                               title)])
        self.add(builder.get_object("widget"))

#######################
# PROTECTED           #
#######################
    def _on_back_clicked(self, button):
        """
            Destroy self
            @param button as Gtk.Button
        """
        self.get_parent().set_visible_child_name("bookmarks")
        GLib.timeout_add(1000, self.destroy)

    def _on_new_tag_changed(self, entry):
        """
            Update button states
            @param entry as Gtk.Entry
        """
        text = entry.get_text()
        sensitive = text != ""
        self.__remove_tag_button.set_sensitive(False)
        for (title, active) in self.__model:
            if title == text:
                sensitive = False
                self.__remove_tag_button.set_sensitive(True)
                break
        self.__add_tag_button.set_sensitive(sensitive)

    def _on_add_tag_clicked(self, button):
        """
            Add new tag
            @param button as Gtk.Button
        """
        tag_title = self.__new_tag_entry.get_text()
        El().bookmarks.add_tag(tag_title, True)
        self.__model.append([tag_title, False])

    def _on_remove_tag_clicked(self, button):
        """
            Remove tag
            @param button as Gtk.Button
        """
        tag_title = self.__new_tag_entry.get_text()
        El().bookmarks.del_tag(tag_title, True)
        for item in self.__model:
            if item[0] == tag_title:
                self.__model.remove(item.iter)
                break

    def _on_row_activated(self, treeview, path, column):
        """
            Set tag entry
            @param treeview as Gtk.TreeView
            @param path as Gtk.TreePath
            @param column as Gtk.TreeView.column
        """
        iterator = self.__model.get_iter(path)
        value = self.__model.get_value(iterator, 0)
        self.__new_tag_entry.set_text(value)

#######################
# PRIVATE             #
#######################
    def __sort_items(self, model, itera, iterb, data):
        """
            Sort model
            @param model as Gtk.ListStore
            @param itera as Gtk.TreeIter
            @param iterb as Gtk.TreeIter
        """
        a = model.get_value(itera, 0)
        b = model.get_value(iterb, 0)
        return strcoll(a, b)

    def __on_tag_edited(self, widget, path, name):
        """
            Rename tag
            @param widget as cell renderer
            @param path as str representation of Gtk.TreePath
            @param name as str
        """
        tag_id = El().bookmarks.get_tag_id(name)
        if tag_id is not None:
            return
        iterator = self.__model.get_iter(path)
        old_name = self.__model.get_value(iterator, 0)
        self.__model.remove(iterator)
        self.__model.append([name, False])
        El().bookmarks.rename_tag(old_name, name)

    def __on_item_toggled(self, view, path):
        """
            When item is toggled, set model
            @param widget as cell renderer
            @param path as str representation of Gtk.TreePath
        """
        iterator = self.__model.get_iter(path)
        toggle = not self.__model.get_value(iterator, 1)
        self.__model.set_value(iterator, 1, toggle)
        tag_title = self.__model.get_value(iterator, 0)
        tag_id = El().bookmarks.get_tag_id(tag_title)
        if toggle:
            El().bookmarks.add_tag_to(tag_id, self.__bookmark_id)
        else:
            El().bookmarks.del_tag_from(tag_id, self.__bookmark_id)
