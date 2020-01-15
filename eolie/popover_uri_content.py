# Copyright (c) 2017-2019 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from gi.repository import GLib, Gio

from gettext import gettext as _

from eolie.define import App, Type
from eolie.popover_uri_item import Item
from eolie.popover_uri_row import Row
from eolie.popover_uri_input import Input


class UriPopoverContent:
    """
        Content handler for UriPopover
    """

    def __init__(self):
        """
            Init handler
        """
        self._input = None
        self._bookmarks_model = Gio.ListStore()
        self._history_model = Gio.ListStore()

    def search_value(self, value, cancellable):
        """
           Search value
           @param value as str
           @param cancellable as Gio.Cancellable
        """
        self._task_helper.run(self.__search_value, value, cancellable)

#######################
# PROTECTED           #
#######################
    def _add_bookmarks(self, bookmarks):
        """
            Add bookmarks to model
            @param [(bookmark_id, title, uri)] as [(int, str, str)]
        """
        if bookmarks:
            (bookmark_id, uri, title) = bookmarks.pop(0)
            item = Item()
            item.set_property("id", bookmark_id)
            item.set_property("type", Type.BOOKMARK)
            item.set_property("title", title)
            item.set_property("uri", uri)
            self._bookmarks_model.append(item)
            GLib.idle_add(self._add_bookmarks, bookmarks)

    def _add_tags(self, tags, select, position=0):
        """
            Add tags to model
            @param [(tag_id, title)] as [(int, str)]
            @param select as int
        """
        if tags:
            (tag_id, title) = tags.pop(0)
            item = Item()
            item.set_property("id", tag_id)
            item.set_property("type", Type.TAG)
            item.set_property("title", title)
            child = Row(item, self._window)
            child.connect("activate", self.__on_row_activated)
            child.connect("moved", self.__on_row_moved)
            child.show()
            self._tags_box.add(child)
            GLib.idle_add(self._add_tags, tags, select)
        else:
            if select is None:
                select = Type.POPULARS
            # Search for previous current row
            for row in self._tags_box.get_children():
                if row.item.get_property("id") == select:
                    self._tags_box.select_row(row)
                    break
            self._set_bookmarks(select)

    def _add_history_items(self, items, date):
        """
            Add history items to model
            @param [(history_id, title, uri, atime)]  as [(int, str, str, int)]
            @param date (jj, mm, aaaa) as (int, int, int)
        """
        if items:
            if date != self._calendar.get_date():
                return
            (history_id, title, uri, atime) = items.pop(0)
            item = Item()
            item.set_property("id", history_id)
            item.set_property("type", Type.HISTORY)
            item.set_property("title", title)
            item.set_property("uri", uri)
            item.set_property("atime", atime)
            self._history_model.append(item)
            GLib.idle_add(self._add_history_items, items, date)

    def _set_bookmarks(self, tag_id):
        """
            Set bookmarks for tag id
            @param tag id as int
        """
        self._bookmarks_model.remove_all()
        self._remove_button.hide()
        if tag_id == Type.POPULARS:
            items = App().bookmarks.get_populars(50)
        elif tag_id == Type.RECENTS:
            items = App().bookmarks.get_recents()
        elif tag_id == Type.UNCLASSIFIED:
            items = App().bookmarks.get_unclassified()
        else:
            items = App().bookmarks.get_bookmarks(tag_id)
        self._bookmarks_count.set_text(_("%s bookmarks") % len(items))
        GLib.idle_add(self._add_bookmarks, items)

    def _get_current_box(self):
        """
            Get current box
            @return Gtk.ListBox
        """
        name = self._stack.get_visible_child_name()
        box = None
        if name == "bookmarks":
            box = self._bookmarks_box
        elif name == "history":
            box = self._history_box
        elif name == "search":
            box = self._search_box
        return box

    def _get_current_input_box(self):
        """
            Get current box with input
            @return Gtk.ListBox
        """
        box = None
        if self._input == Input.SEARCH:
            box = self._search_box
        elif self._input == Input.TAGS:
            box = self._tags_box
        elif self._input == Input.BOOKMARKS:
            box = self._bookmarks_box
        return box

#######################
# PRIVATE             #
#######################
    def __search_value(self, value, cancellable):
        """
            Search for value in DB
            @param value as str
            @param cancellable as Gio.Cancellable
        """
        if value == '':
            result = App().history.search(value, 50)
        else:
            result = App().history.search(value, 15)
            result += App().bookmarks.search(value, 15)
        GLib.idle_add(self.__add_searches, result, cancellable)

    def __add_searches(self, result, cancellable):
        """
            Add searches to model
            @param result as [(str, str, int)]
            @param cancellable as Gio.Cancellable
        """
        if cancellable.is_cancelled():
            return
        if result:
            (rowid, title, uri, score) = result.pop(0)
            item = Item()
            item.set_property("id", rowid)
            item.set_property("type", Type.SEARCH)
            item.set_property("title", title)
            item.set_property("uri", uri)
            item.set_property("score", score)
            child = Row(item, self._window)
            child.show()
            self._search_box.add(child)
            GLib.idle_add(self.__add_searches, result, cancellable)

    def __on_row_activated(self, row):
        """
            Select row
            @param row as Row
        """
        item_id = row.item.get_property("id")
        self._set_bookmarks(item_id)

    def __on_row_moved(self, row, items):
        """
            Move bookmark from current selected tag to tag
            @param row as Row
            @param items [(bookmark_id, tag_id)] as [(int, int)]
            @param tag id as int
        """
        tag_row = self._tags_box.get_selected_row()
        current_tag_id = tag_row.item.get_property("id")
        for item in items:
            if current_tag_id >= 0:
                App().bookmarks.del_tag_from(current_tag_id, item[0])
            App().bookmarks.add_tag_to(item[1], item[0])
        self.__on_row_activated(tag_row)
        App().bookmarks.clean_tags()
        if App().sync_worker is not None:
            App().sync_worker.push_bookmark(item[0])
