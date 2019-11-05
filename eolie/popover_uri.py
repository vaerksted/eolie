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

from gi.repository import Gtk, GLib

from gettext import gettext as _
from time import mktime, time
from datetime import datetime
from locale import strcoll
from urllib.parse import urlparse

from eolie.helper_task import TaskHelper
from eolie.define import App, Type, TimeSpan, TimeSpanValues
from eolie.popover_uri_row import Row
from eolie.popover_uri_events import UriPopoverEvents
from eolie.popover_uri_content import UriPopoverContent
from eolie.popover_uri_input import Input


class UriPopover(Gtk.Popover, UriPopoverEvents, UriPopoverContent):
    """
        Show user bookmarks or search
    """

    def __init__(self, window):
        """
            Init popover
            @param window as Window
        """
        Gtk.Popover.__init__(self)
        UriPopoverEvents.__init__(self)
        UriPopoverContent.__init__(self)
        self.set_modal(False)
        window.register(self, False)
        self._window = window
        self.get_style_context().add_class("box-shadow")
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/PopoverUri.ui")
        builder.connect_signals(self)
        self.__scrolled_bookmarks = builder.get_object("scrolled_bookmarks")
        self.__infobar = builder.get_object("infobar")
        self.__infobar_confirm = Gtk.Button()
        self.__infobar_confirm.show()
        self.__infobar_select = Gtk.ComboBoxText()
        self.__infobar_select.show()
        self.__infobar.get_content_area().add(self.__infobar_select)
        self.__infobar.add_action_widget(self.__infobar_confirm, 1)
        self.__infobar.add_button(_("Cancel"), 2)
        self._history_box = builder.get_object("history_box")
        self._history_box.bind_model(self._history_model,
                                     self.__on_item_create)
        self._search_box = builder.get_object("search_box")
        self._stack = builder.get_object("stack")
        self.__tags = builder.get_object("tags")
        self._tags_box = builder.get_object("tags_box")
        self._tags_box.set_sort_func(self.__sort_tags)
        self._remove_button = builder.get_object("remove_button")
        self._bookmarks_count = builder.get_object("count")
        self._bookmarks_box = builder.get_object("bookmarks_box")
        self._bookmarks_box.bind_model(self._bookmarks_model,
                                       self.__on_item_create)
        self.__calendar = builder.get_object("calendar")
        self.add(builder.get_object("widget"))
        self.connect("map", self.__on_map)
        self.connect("unmap", self.__on_unmap)

    def popup(self, child):
        """
            Popup popover and wanted child
            @param child as str
        """
        # Add a new view for importing bookmarks
        if child == "bookmarks" and not App().bookmarks.is_empty():
            grid = Gtk.Grid()
            image = Gtk.Image.new_from_icon_name("bookmark-new-symbolic",
                                                 Gtk.IconSize.BUTTON)
            grid.add(image)
            button = Gtk.Button.new_with_label(_("Import bookmarks"))
            button.connect("clicked", self._on_import_button_clicked)
            grid.add(button)
            grid.set_column_spacing(5)
            grid.set_property("valign", Gtk.Align.CENTER)
            grid.set_property("halign", Gtk.Align.CENTER)
            grid.show_all()
            self._stack.add(grid)
            self._stack.set_visible_child(grid)
        else:
            self._stack.set_visible_child_name(child)
        Gtk.Popover.popup(self)

    def set_search_text(self, search):
        """
            Set search model
            @param search as str
        """
        self._set_search_text(search)
        self.add_suggestions([search], Type.SEARCH, True)
        self._stack.set_visible_child_name("search")

    @property
    def input(self):
        """
            Get input type
            @return Input
        """
        return self._input

#######################
# PROTECTED           #
#######################
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

    def _on_import_button_clicked(self, button):
        """
            Sync with Firefox Sync
            @param button as Gtk.Button
        """
        self.hide()
        from eolie.dialog_import_bookmarks import ImportBookmarksDialog
        dialog = ImportBookmarksDialog(self._window)
        dialog.run()

    def _on_remove_button_clicked(self, button):
        """
            Remove bookmarks
            @param button as Gtk.Button
        """
        for row in self._bookmarks_box.get_selected_rows():
            item_id = row.item.get_property("id")
            if App().sync_worker is not None:
                guid = App().bookmarks.get_guid(item_id)
                App().sync_worker.remove_from_bookmarks(guid)
            App().bookmarks.remove(item_id)
            self._bookmarks_box.remove(row)
            self._remove_button.hide()
        App().bookmarks.clean_tags()

    def _on_selected_rows_changed(self, listbox):
        """
            Show delete button if needed
            @param listbox as Gtk.ListBox
        """
        self._remove_button.show()

    def _on_row_selected(self, listbox, row):
        """
            Scroll to row
            @param listbox as Gtk.ListBox
            @param row as Row
        """
        if row is None:
            return

        # Update titlebar
        if row.item.get_property("type") == Type.SUGGESTION:
            title = row.item.get_property("title")
            self._window.toolbar.title.set_text_entry(title)
        else:
            uri = row.item.get_property("uri")
            if not uri:
                return
            parsed = urlparse(uri)
            if parsed.scheme not in ["http", "https", "file"]:
                uri = ""
            self._window.toolbar.title.set_text_entry(uri)
        # Scroll to row
        scrolled = listbox.get_ancestor(Gtk.ScrolledWindow)
        if scrolled is None:
            return
        y = row.translate_coordinates(listbox, 0, 0)[1]
        adj = scrolled.get_vadjustment().get_value()
        if y + row.get_allocated_height() >\
                scrolled.get_allocated_height() + adj or\
                y - row.get_allocated_height() < 0 + adj:
            scrolled.get_vadjustment().set_value(y)

    def _on_search_map(self, widget):
        """
            Init search
            @param widget as Gtk.Widget
        """
        self._input = Input.NONE
        if not self._search_box.get_children():
            self.set_search_text("")

    def _on_history_map(self, widget):
        """
            Init search
            @param widget as Gtk.Widget
        """
        self._input = Input.NONE
        now = datetime.now()
        self.__calendar.select_month(now.month - 1, now.year)
        self.__calendar.select_day(now.day)

    def _on_close_map(self, widget):
        """
            Close popover
            @param widget as Gtk.Widget
        """
        self._window.close_popovers()

    def _on_bookmarks_map(self, widget):
        """
            Init bookmarks
            @param widget as Gtk.Widget/None
        """
        current = None
        row = self._tags_box.get_selected_row()
        if row is not None:
            current = row.item.get_property("id")
        self._input == Input.TAGS
        for child in self._tags_box.get_children():
            self._tags_box.remove(child)
        static = [(Type.POPULARS,
                   # Translators: Plural
                   _("Popular")),
                  (Type.RECENTS,
                   # Translators: Plural
                   _("Recent")),
                  (Type.UNCLASSIFIED,
                   _("Unclassified"))]
        GLib.idle_add(self._add_tags,
                      static + App().bookmarks.get_all_tags(), current)

    def _on_day_selected(self, calendar):
        """
            Show history for day
            @param calendar as Gtk.Calendar
        """
        (year, month, day) = calendar.get_date()
        date = datetime(year, month + 1, day, 0, 0)
        atime = mktime(date.timetuple())
        result = App().history.get(atime)
        self._history_model.remove_all()
        GLib.idle_add(self._add_history_items, result, (year, month, day))
        self.__infobar.hide()

    def _on_clear_history_clicked(self, button):
        """
            Ask user for confirmation
            @param button as Gtk.Button
        """
        self.__infobar_confirm.set_label(button.get_label())
        self.__infobar_select.remove_all()
        self.__infobar_select.append(TimeSpan.HOUR, _("From the past hour"))
        self.__infobar_select.append(TimeSpan.DAY, _("From the past day"))
        self.__infobar_select.append(TimeSpan.WEEK, _("From the past week"))
        self.__infobar_select.append(TimeSpan.FOUR_WEEK,
                                     _("From the past four weeks"))
        self.__infobar_select.append(TimeSpan.CUSTOM, _("From selected day"))
        self.__infobar_select.append(TimeSpan.FOREVER, _("From the beginning"))
        self.__infobar_select.set_active_id(TimeSpan.HOUR)
        self.__infobar.show()
        # GTK 3.20 https://bugzilla.gnome.org/show_bug.cgi?id=710888
        self.__infobar.queue_resize()

    def _on_infobar_response(self, infobar, response_id):
        """
            Handle user response and remove wanted history ids
            @param infobar as Gtk.InfoBar
            @param response_id as int
        """
        if response_id == 1:
            active_id = self.__infobar_select.get_active_id()
            if active_id == TimeSpan.CUSTOM:
                (year, month, day) = self.__calendar.get_date()
                date = "%02d/%02d/%s" % (day, month + 1, year)
                atime = mktime(
                    datetime.strptime(date, "%d/%m/%Y").timetuple())
            else:
                atime = int(time() - TimeSpanValues[active_id] / 1000000)
            task_helper = TaskHelper()
            task_helper.run(self.__clear_history, atime)
        infobar.hide()

#######################
# PRIVATE             #
#######################
    def __clear_history(self, atime):
        """
            Clear history for wanted atime
            @param atime as double
            @thread safe
        """
        App().history.clear_from(atime)
        GLib.idle_add(self._on_day_selected, self.__calendar)
        if App().sync_worker is not None:
            for history_id in App().history.get_empties():
                App().history.remove(history_id)

    def __sort_tags(self, row1, row2):
        """
            Sort tags
            @param row1 as Row
            @param row2 as Row
        """
        if row1.item.get_property("type") < 0:
            return False
        return strcoll(row1.item.get_property("title"),
                       row2.item.get_property("title"))

    def __on_map(self, widget):
        """
            Resize
            @param widget as Gtk.Widget
        """
        self._input = Input.NONE
        self._search_box.get_style_context().remove_class("kbd-input")
        self._bookmarks_box.get_style_context().remove_class("kbd-input")
        self._tags_box.get_style_context().remove_class("kbd-input")
        size = self._window.get_size()
        width = min(800, size[0])
        height = min(700, size[1] * 0.9)
        self.set_size_request(width, height)
        self.__scrolled_bookmarks.set_size_request(width * 0.4, -1)

    def __on_unmap(self, widget):
        """
            Switch to bookmarks
            @param widget as Gtk.Widget
        """
        self._stack.set_visible_child_name("bookmarks")
        self._bookmarks_model.remove_all()
        for child in self._tags_box.get_children():
            child.destroy()
        for child in self._search_box.get_children():
            child.destroy()

    def __on_row_edited(self, row):
        """
            Edit bookmark associated to row
            @param row as Row
        """
        from eolie.widget_bookmark_edit import BookmarkEditWidget
        widget = BookmarkEditWidget(row.item.get_property("id"))
        widget.show()
        self._stack.add(widget)
        self._stack.set_visible_child(widget)

    def __on_item_create(self, item):
        """
            Add child to box
            @param item as Item
        """
        child = Row(item, self._window)
        child.connect("edited", self.__on_row_edited)
        return child
