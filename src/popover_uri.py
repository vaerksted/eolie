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

from gi.repository import Gtk, Gdk, GObject, GLib, Gio, Pango

from gettext import gettext as _
from time import mktime, time
from datetime import datetime
from locale import strcoll

from eolie.define import El, ArtSize, Type


class Item(GObject.GObject):
    id = GObject.Property(type=int,
                          default=0)
    type = GObject.Property(type=int,
                            default=0)
    title = GObject.Property(type=str,
                             default="")
    value = GObject.Property(type=str,
                             default="")
    uri = GObject.Property(type=str,
                           default="")

    def __init__(self):
        GObject.GObject.__init__(self)


class Row(Gtk.ListBoxRow):
    """
        A row
    """
    __gsignals__ = {
        'edit': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'move': (GObject.SignalFlags.RUN_FIRST, None, (int, int))
    }

    def __init__(self, item):
        """
            Init row
            @param item as Item
        """
        self.__item = item
        eventbox = None
        favicon = None
        Gtk.ListBoxRow.__init__(self)
        self.get_style_context().add_class("row")
        item_id = item.get_property("id")
        item_type = item.get_property("type")
        uri = item.get_property("uri")
        title = item.get_property("title")
        grid = Gtk.Grid()
        grid.set_column_spacing(10)
        grid.set_hexpand(True)
        grid.set_property("valign", Gtk.Align.CENTER)
        if item_type in [Type.BOOKMARK, Type.HISTORY]:
            surface = El().art.get_artwork(uri,
                                           "favicon",
                                           self.get_scale_factor(),
                                           ArtSize.FAVICON,
                                           ArtSize.FAVICON)
            favicon = Gtk.Image.new_from_surface(surface)
            favicon.show()
            if surface is None:
                favicon.set_from_icon_name("applications-internet",
                                           Gtk.IconSize.MENU)
            else:
                del surface
        elif item_type == Type.KEYWORDS:
            favicon = Gtk.Image.new_from_icon_name("system-search-symbolic",
                                                   Gtk.IconSize.MENU)
        else:
            if item_id == Type.NONE:
                icon_name = "folder-visiting-symbolic"
            elif item_id == Type.POPULARS:
                icon_name = "starred-symbolic"
            elif item_id == Type.RECENTS:
                icon_name = "document-open-recent-symbolic"
            else:
                icon_name = "folder-symbolic"
            favicon = Gtk.Image.new_from_icon_name(icon_name,
                                                   Gtk.IconSize.MENU)
            favicon.show()
        self.__title = Gtk.Label.new(title)
        self.__title.set_ellipsize(Pango.EllipsizeMode.END)
        self.__title.set_property("halign", Gtk.Align.START)
        self.__title.set_hexpand(True)
        self.__title.show()
        uri = Gtk.Label.new(item.get_property("uri"))
        uri.set_ellipsize(Pango.EllipsizeMode.END)
        uri.set_property("halign", Gtk.Align.END)
        uri.get_style_context().add_class("dim-label")
        uri.set_max_width_chars(40)
        uri.show()
        if favicon is not None:
            favicon.set_margin_start(2)
            grid.add(favicon)
        grid.add(self.__title)
        grid.add(uri)
        if item_type == Type.BOOKMARK:
            edit_button = Gtk.Button.new_from_icon_name(
                                                     "document-edit-symbolic",
                                                     Gtk.IconSize.MENU)
            edit_button.get_image().set_opacity(0.5)
            edit_button.connect("clicked", self.__on_edit_clicked)
            edit_button.get_style_context().add_class("edit-button")
            edit_button.show()
            grid.add(edit_button)
        grid.show()
        eventbox = Gtk.EventBox()
        eventbox.add(grid)
        eventbox.set_size_request(-1, 30)
        eventbox.connect("button-release-event", self.__on_button_release)
        eventbox.show()
        self.add(eventbox)
        if item_type == Type.BOOKMARK:
            self.drag_source_set(Gdk.ModifierType.BUTTON1_MASK, [],
                                 Gdk.DragAction.MOVE)
            self.drag_source_add_text_targets()
            self.connect('drag-begin', self.__on_drag_begin)
            self.connect('drag-data-get', self.__on_drag_data_get)
        # We add bookmark, not useful, only for visual feedback on drag
        if item_type in [Type.TAG, Type.BOOKMARK]:
            self.drag_dest_set(Gtk.DestDefaults.DROP | Gtk.DestDefaults.MOTION,
                               [], Gdk.DragAction.MOVE)
            self.drag_dest_add_text_targets()
            self.connect('drag-data-received', self.__on_drag_data_received)
            self.connect('drag-motion', self.__on_drag_motion)
            self.connect('drag-leave', self.__on_drag_leave)

    def set_title(self, title):
        """
            Set row title
            @param title as str
        """
        self.__item.set_property("title", title)
        self.__title.set_text(title)

    @property
    def item(self):
        """
            Get item
            @return Item
        """
        return self.__item

#######################
# PRIVATE             #
#######################
    def __on_drag_begin(self, widget, context):
        """
            Set icon
            @param widget as Gtk.Widget
            @param context as Gdk.DragContext
        """
        widget.drag_source_set_icon_name('web-browser')
        # add current drag to selected rows
        self.get_parent().select_row(self)

    def __on_drag_data_get(self, widget, context, data, info, time):
        """
            Send track id
            @param widget as Gtk.Widget
            @param context as Gdk.DragContext
            @param data as Gtk.SelectionData
            @param info as int
            @param time as int
        """
        # Get data from parent as multiple row may be selected
        text = ""
        for row in self.get_parent().get_selected_rows():
            text += str(row.item.get_property("id")) + "@"
        data.set_text(text, len(text))

    def __on_drag_data_received(self, widget, context, x, y, data, info, time):
        """
            Move track
            @param widget as Gtk.Widget
            @param context as Gdk.DragContext
            @param x as int
            @param y as int
            @param data as Gtk.SelectionData
            @param info as int
            @param time as int
        """
        try:
            for rowid in data.get_text().split("@"):
                bookmark_id = int(rowid)
                tag_id = self.__item.get_property("id")
                self.emit("move", bookmark_id, tag_id)
        except:
            pass

    def __on_drag_motion(self, widget, context, x, y, time):
        """
            Add style
            @param widget as Gtk.Widget
            @param context as Gdk.DragContext
            @param x as int
            @param y as int
            @param time as int
        """
        if self.__item.get_property("type") == Type.TAG:
            self.get_style_context().add_class('drag')

    def __on_drag_leave(self, widget, context, time):
        """
            Remove style
            @param widget as Gtk.Widget
            @param context as Gdk.DragContext
            @param time as int
        """
        self.get_style_context().remove_class('drag')

    def __on_button_release(self, eventbox, event):
        """
            Got to uri
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        # Lets user select item
        if event.state & Gdk.ModifierType.CONTROL_MASK or\
                event.state & Gdk.ModifierType.SHIFT_MASK:
            return False
        # Event is for internal button
        if eventbox.get_window() != event.window:
            return True
        uri = self.__item.get_property("uri")
        item_id = self.__item.get_property("type")
        if item_id in [Type.HISTORY, Type.KEYWORDS, Type.BOOKMARK]:
            if event.button == 1:
                El().active_window.container.current.load_uri(uri)
            else:
                El().active_window.container.add_web_view(uri, True)
            El().bookmarks.set_access_time(uri, int(time()))
            El().bookmarks.set_more_popular(uri)
            El().active_window.toolbar.title.hide_popover()
        else:
            self.emit("activate")

    def __on_edit_clicked(self, button):
        """
            Edit self
            @param button as Gtk.Button
        """
        self.emit("edit")


class Input:
    NONE = 0
    SEARCH = 1
    TAGS = 2
    BOOKMARKS = 3


class UriPopover(Gtk.Popover):
    """
        Show user bookmarks or search
    """

    def __init__(self):
        """
            Init popover
        """
        Gtk.Popover.__init__(self)
        self.__input = False
        self.set_modal(False)
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/PopoverUri.ui")
        builder.connect_signals(self)
        self.__scrolled_bookmarks = builder.get_object("scrolled_bookmarks")
        self.__history_model = Gio.ListStore()
        self.__history_box = builder.get_object("history_box")
        self.__history_box.bind_model(self.__history_model,
                                      self.__on_item_create)
        self.__search_model = Gio.ListStore()
        self.__search_box = builder.get_object("search_box")
        self.__stack = builder.get_object("stack")
        self.__search_box.bind_model(self.__search_model,
                                     self.__on_item_create)
        self.__bookmarks_model = Gio.ListStore()
        self.__tags = builder.get_object("tags")
        self.__tags_box = builder.get_object("tags_box")
        self.__tags_box.set_sort_func(self.__sort_tags)
        self.__remove_button = builder.get_object("remove_button")
        self.__bookmarks_count = builder.get_object("count")
        self.__bookmarks_box = builder.get_object("bookmarks_box")
        self.__bookmarks_box.bind_model(self.__bookmarks_model,
                                        self.__on_item_create)
        self.__calendar = builder.get_object("calendar")
        self.add(builder.get_object("widget"))
        self.connect("map", self.__on_map)
        self.connect("unmap", self.__on_unmap)

    @property
    def input(self):
        """
            Get input type
            @return Input
        """
        return self.__input

    def set_search_text(self, search):
        """
            Set search model
            @param search as str
        """
        self.__search_model.remove_all()
        self.__stack.set_visible_child_name("search")
        self.__set_search_text(search)

    def add_keywords(self, words):
        """
            Add keywords to search
            @param words as str
        """
        if self.__stack.get_visible_child_name() != "search":
            return
        item = Item()
        item.set_property("type", Type.KEYWORDS)
        item.set_property("title", words)
        item.set_property("uri", El().search.get_search_uri(words))
        self.__search_model.append(item)

    def forward_event(self, event):
        """
            Forward event, smart navigation between boxes
            @param event as Gdk.Event
            @return True if event forwarded
        """
        if not self.is_visible():
            return False
        if event.keyval == Gdk.KEY_Up and self.__input == Input.NONE:
            return False
        elif event.keyval == Gdk.KEY_Left and self.__input == Input.BOOKMARKS:
            self.__input = Input.TAGS
            self.__tags_box.get_style_context().add_class("input")
            self.__bookmarks_box.get_style_context().remove_class("input")
            return True
        elif event.keyval == Gdk.KEY_Right and self.__input == Input.TAGS:
            self.__input = Input.BOOKMARKS
            self.__bookmarks_box.get_style_context().add_class("input")
            self.__tags_box.get_style_context().remove_class("input")
            return True
        elif event.keyval in [Gdk.KEY_Left, Gdk.KEY_Right] and\
                self.__input == Input.SEARCH:
            return False
        elif event.keyval in [Gdk.KEY_Left, Gdk.KEY_Right] and\
                self.__input != Input.NONE:
            return True
        elif event.keyval in [Gdk.KEY_Down, Gdk.KEY_Up]:
            # If nothing selected, detect default widget
            if self.__input == Input.NONE:
                if self.__stack.get_visible_child_name() == "search":
                    self.__input = Input.SEARCH
                elif self.__stack.get_visible_child_name() == "bookmarks":
                    self.__tags_box.get_style_context().add_class("input")
                    self.__input = Input.TAGS
                else:
                    self.__input = Input.NONE
                box = self.__get_current_box()
                if box is not None:
                    rows = box.get_children()
                    if rows:
                        box.select_row(rows[0])
                return True
            box = self.__get_current_box()
            rows = box.get_children()
            if box is None or not rows:
                self.__input = Input.NONE
                return False
            selected = box.get_selected_row()
            # If nothing selected, select first row
            if selected is None:
                box.select_row(rows[0])
                if self.__input == Input.TAGS:
                    item_id = rows[0].item.get_property("type")
                    self.__set_bookmarks(item_id)
            else:
                idx = -1 if event.keyval == Gdk.KEY_Up else 1
                for row in rows:
                    if row == selected:
                        break
                    idx += 1
                if idx >= len(rows):
                    box.select_row(rows[0])
                    if self.__input == Input.TAGS:
                        item_id = rows[0].item.get_property("type")
                        self.__set_bookmarks(item_id)
                    return True
                elif idx < 0:
                    # Do not go to uribar for bookmarks list
                    if self.__input in [Input.BOOKMARKS, Input.SEARCH]:
                        box.select_row(rows[-1])
                        return True
                    else:
                        box.select_row(None)
                        self.__input = Input.NONE
                        box.get_style_context().remove_class("input")
                        return False
                else:
                    box.select_row(rows[idx])
                    if self.__input == Input.TAGS:
                        item_id = rows[idx].item.get_property("type")
                        self.__set_bookmarks(item_id)
                    return True
        elif event.keyval in [Gdk.KEY_Return, Gdk.KEY_KP_Enter]:
            box = self.__get_current_box()
            if box is not None:
                selected = box.get_selected_row()
                if selected is not None:
                    uri = selected.item.get_property("uri")
                    if uri:
                        El().active_window.toolbar.title.hide_popover()
                        El().active_window.container.current.load_uri(uri)
                return True
            else:
                self.__input = Input.NONE
                return False
        else:
            self.__input = Input.NONE
            return False

#######################
# PROTECTED           #
#######################
    def _on_remove_button_clicked(self, button):
        """
            Save bookmarks to tag
            @param button as Gtk.Button
        """
        for row in self.__bookmarks_box.get_selected_rows():
            item_id = row.item.get_property("id")
            El().bookmarks.remove(item_id)
            self.__bookmarks_box.remove(row)
            self.__remove_button.hide()

    def _on_tag_entry_enter_notify(self, entry, event):
        """
            Remove class
            @param entry as Gtk.Entry
            @param event as Gdk.Event
        """
        entry.get_style_context().remove_class('tag-edit')

    def _on_tag_entry_leave_notify(self, entry, event):
        """
            Set class
            @param entry as Gtk.Entry
            @param event as Gdk.Event
        """
        entry.get_style_context().add_class('tag-edit')

    def _on_selected_rows_changed(self, listbox):
        """
            Show delete button if needed
            @param listbox as Gtk.ListBox
        """
        self.__remove_button.show()

    def _on_row_selected(self, listbox, row):
        """
            Scroll to row
            @param listbox as Gtk.ListBox
            @param row as Row
        """
        if row is None:
            return
        scrolled = listbox.get_ancestor(Gtk.ScrolledWindow)
        if scrolled is None:
            return
        y = row.translate_coordinates(listbox, 0, 0)[1]
        if y + row.get_allocated_height() >\
                scrolled.get_allocated_height() or\
                y - row.get_allocated_height() < 0:
            scrolled.get_vadjustment().set_value(y)

    def _on_search_map(self, widget):
        """
            Init search
            @param widget as Gtk.Widget
        """
        self.__input = Input.SEARCH
        self.set_search_text("")

    def _on_history_map(self, widget):
        """
            Init search
            @param widget as Gtk.Widget
        """
        self.__input = Input.NONE
        now = datetime.now()
        self.__calendar.select_month(now.month, now.year)
        self.__calendar.select_day(now.day)

    def _on_bookmarks_map(self, widget):
        """
            Init bookmarks
            @param widget as Gtk.Widget
        """
        self.__input == Input.TAGS
        if not self.__tags_box.get_children():
            static = [(Type.POPULARS,
                       _("Populars")),
                      (Type.RECENTS,
                       _("Recents")),
                      (Type.NONE,
                       _("Unclassified"))]
            self.__add_tags(static + El().bookmarks.get_tags())

    def _on_day_selected(self, calendar):
        """
            Show history for day
            @param calendar as Gtk.Calendar
        """
        (year, month, day) = calendar.get_date()
        date = "%s/%s/%s" % (day, month, year)
        mtime = mktime(datetime.strptime(date, "%d/%m/%Y").timetuple())
        result = El().history.get(mtime)
        self.__history_model.remove_all()
        self.__add_history_items(result)

#######################
# PRIVATE             #
#######################
    def __sort_tags(self, row1, row2):
        """
            Sort tags
        """
        if row1.item.get_property("type") < 0:
            return False
        return strcoll(row1.item.get_property("title"),
                       row2.item.get_property("title"))

    def __add_searches(self, searches, added=[]):
        """
            Add searches to model
            @param [(title, uri)] as [(str, str)]
            @internal added
        """
        if searches:
            (title, uri) = searches.pop(0)
            item = Item()
            item.set_property("type", Type.HISTORY)
            item.set_property("title", title)
            item.set_property("uri", uri)
            added.append(uri)
            self.__search_model.append(item)
            GLib.idle_add(self.__add_searches, searches, added)

    def __add_bookmarks(self, bookmarks):
        """
            Add bookmarks to model
            @param [(bookmark_id, title, uri)] as [(int, str, str)]
        """
        if bookmarks:
            (bookmark_id, title, uri) = bookmarks.pop(0)
            item = Item()
            item.set_property("id", bookmark_id)
            item.set_property("type", Type.BOOKMARK)
            item.set_property("title", title)
            item.set_property("uri", uri)
            self.__bookmarks_model.append(item)
            GLib.idle_add(self.__add_bookmarks, bookmarks)

    def __add_tags(self, tags):
        """
            Add tags to model
            @param [(tag_id, title)] as [(int, str)]
        """
        if tags:
            (tag_id, title) = tags.pop(0)
            item = Item()
            item.set_property("id", tag_id)
            item.set_property("type", Type.TAG)
            item.set_property("title", title)
            child = Row(item)
            child.connect("activate", self.__on_row_activated)
            child.connect("move", self.__on_row_moved)
            child.show()
            self.__tags_box.add(child)
            GLib.idle_add(self.__add_tags, tags)
        else:
            self.__tags_box.select_row(self.__tags_box.get_children()[0])
            self.__set_bookmarks(Type.POPULARS)

    def __add_history_items(self, items):
        """
            Add history items to model
            @param [(title, uri, mtime)]  as [(str, str, int)]
        """
        if items:
            (title, uri, mtime) = items.pop(0)
            item = Item()
            item.set_property("type", Type.HISTORY)
            item.set_property("title", title)
            item.set_property("uri", uri)
            self.__history_model.append(item)
            GLib.idle_add(self.__add_history_items, items)

    def __get_current_box(self):
        """
            Get current box
            @return Gtk.ListBox
        """
        box = None
        if self.__input == Input.SEARCH:
            box = self.__search_box
        elif self.__input == Input.TAGS:
            box = self.__tags_box
        elif self.__input == Input.BOOKMARKS:
            box = self.__bookmarks_box
        return box

    def __set_search_text(self, search):
        """
            Set search model
            @param search as str
        """
        if search == '':
            result = El().history.search(search, 50)
        else:
            result = El().bookmarks.search(search, 10)
            result += El().history.search(search, 10)
        self.__add_searches(result)

    def __set_bookmarks(self, tag_id):
        """
            Set bookmarks for tag id
            @param tag id as int
        """
        self.__bookmarks_model.remove_all()
        self.__remove_button.hide()
        if tag_id == Type.POPULARS:
            items = El().bookmarks.get_populars()
        elif tag_id == Type.RECENTS:
            items = El().bookmarks.get_recents()
        elif tag_id == Type.NONE:
            items = El().bookmarks.get_unclassified()
        else:
            items = El().bookmarks.get_bookmarks(tag_id)
        self.__bookmarks_count.set_text("%s bookmarks" % len(items))
        self.__add_bookmarks(items)

    def __on_tag_entry_changed(self, entry):
        """
            Update tag title
            @param entry as Gtk.Entry
        """
        current = self.__tags_box.get_selected_row()
        value = entry.get_text()
        current_title = current.item.get_property("title")
        if current_title != value:
            self.__remove_button.show()
        else:
            self.__remove_button.hide()

    def __on_map(self, widget):
        """
            Resize
            @param widget as Gtk.Widget
        """
        self.__input = Input.NONE
        self.__search_box.get_style_context().remove_class("input")
        self.__bookmarks_box.get_style_context().remove_class("input")
        self.__tags_box.get_style_context().remove_class("input")
        size = El().active_window.get_size()
        self.set_size_request(size[0]*0.5, size[1]*0.8)
        self.__scrolled_bookmarks.set_size_request(size[1]*0.6*0.5, -1)

    def __on_unmap(self, widget):
        """
            Switch to bookmarks
            @param widget as Gtk.Widget
        """
        self.__stack.set_visible_child_name("bookmarks")

    def __on_row_activated(self, row):
        """
            Select row
            @param row as Row
        """
        item_id = row.item.get_property("id")
        self.__set_bookmarks(item_id)

    def __on_row_moved(self, row, bookmark_id, tag_id):
        """
            Move bookmark from current selected tag to tag
            @param row as Row
            @param bookmark_id as int
            @param tag id as int
        """
        tag_row = self.__tags_box.get_selected_row()
        current_tag_id = tag_row.item.get_property("id")
        if current_tag_id >= 0:
            El().bookmarks.del_tag_from(current_tag_id, bookmark_id)
        El().bookmarks.add_tag_to(tag_id, bookmark_id)
        self.__on_row_activated(tag_row)

    def __on_row_edited(self, row):
        """
            Edit bookmark associated to row
            @param row as Row
        """
        from eolie.widget_edit_bookmark import EditBookmarkWidget
        widget = EditBookmarkWidget(row.item.get_property("id"))
        widget.show()
        self.__stack.add(widget)
        self.__stack.set_visible_child(widget)

    def __on_item_create(self, item):
        """
            Add child to box
            @param item as Item
        """
        child = Row(item)
        child.connect("edit", self.__on_row_edited)
        return child
