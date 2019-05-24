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

from gi.repository import Gtk, Gdk, GObject, GLib, Gio, Pango

from gettext import gettext as _
from time import mktime, time
from datetime import datetime
from locale import strcoll
from urllib.parse import urlparse

from eolie.helper_task import TaskHelper
from eolie.define import App, Type, TimeSpan, TimeSpanValues, LoadingType
from eolie.utils import wanted_loading_type


class Item(GObject.GObject):
    id = GObject.Property(type=int,
                          default=0)
    type = GObject.Property(type=int,
                            default=0)
    title = GObject.Property(type=str,
                             default="")
    uri = GObject.Property(type=str,
                           default="")
    atime = GObject.Property(type=int,
                             default=0)
    score = GObject.Property(type=int,
                             default=0)
    search = GObject.Property(type=str,
                              default="")

    def __init__(self):
        GObject.GObject.__init__(self)


class Row(Gtk.ListBoxRow):
    """
        A row
    """
    __gsignals__ = {
        'edited': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'moved': (GObject.SignalFlags.RUN_FIRST, None, (GLib.Variant,))
    }

    def __init__(self, item, window):
        """
            Init row
            @param item as Item
            @param window as Window
        """
        self.__item = item
        self.__window = window
        self.__search = ""
        eventbox = None
        favicon = None
        Gtk.ListBoxRow.__init__(self)
        self.get_style_context().add_class("row")
        item_id = item.get_property("id")
        item_type = item.get_property("type")
        uri = item.get_property("uri")
        title = item.get_property("title")
        grid = Gtk.Grid()
        grid.set_margin_start(5)
        grid.set_margin_end(5)
        grid.set_column_spacing(10)
        grid.set_hexpand(True)
        grid.set_property("valign", Gtk.Align.CENTER)
        if item_type in [Type.BOOKMARK, Type.SEARCH, Type.HISTORY]:
            favicon = Gtk.Image()
            self.__set_favicon(favicon)
        elif item_type == Type.SUGGESTION:
            favicon = Gtk.Image.new_from_icon_name("system-search-symbolic",
                                                   Gtk.IconSize.MENU)
            favicon.show()
        elif item_type == Type.VIEW:
            favicon = Gtk.Image.new_from_icon_name("view-paged-symbolic",
                                                   Gtk.IconSize.MENU)
            favicon.show()
        if favicon is not None:
            grid.attach(favicon, 0, 0, 1, 2)

        uri = item.get_property("uri")
        self.__title = Gtk.Label.new()
        self.__title.set_ellipsize(Pango.EllipsizeMode.END)
        self.__title.set_property("halign", Gtk.Align.START)
        self.__title.set_hexpand(True)
        self.__title.set_property('has-tooltip', True)
        self.__title.connect('query-tooltip', self.__on_query_tooltip)
        self.__title.show()
        if uri:
            self.__title.set_markup("%s\n<span alpha='40000'>%s</span>" %
                                    (GLib.markup_escape_text(title),
                                     GLib.markup_escape_text(uri)))
        else:
            self.__title.set_text(title)
        grid.attach(self.__title, 1, 0, 1, 2)

        if item_type == Type.HISTORY:
            dt = datetime.fromtimestamp(item.get_property("atime"))
            hour = str(dt.hour).rjust(2, "0")
            minute = str(dt.minute).rjust(2, "0")
            atime = Gtk.Label.new("%s:%s" % (hour, minute))
            atime.set_property("valign", Gtk.Align.CENTER)
            atime.get_style_context().add_class("dim-label")
            atime.set_margin_end(2)
            atime.show()
            grid.attach(atime, 2, 0, 1, 2)

        if item_type in [Type.HISTORY, Type.SEARCH]:
            delete_button = Gtk.Button.new_from_icon_name(
                "user-trash-symbolic",
                Gtk.IconSize.MENU)
            delete_button.get_image().set_opacity(0.5)
            delete_button.set_margin_end(5)
            delete_button.set_property("valign", Gtk.Align.CENTER)
            delete_button.connect("clicked", self.__on_delete_clicked)
            delete_button.get_style_context().add_class("overlay-button")
            delete_button.set_tooltip_text(_("Delete page from history"))
            delete_button.show()
            grid.attach(delete_button, 3, 0, 1, 2)
        elif item_type == Type.BOOKMARK:
            edit_button = Gtk.Button.new_from_icon_name(
                "document-edit-symbolic",
                Gtk.IconSize.MENU)
            edit_button.get_image().set_opacity(0.5)
            edit_button.set_margin_end(5)
            edit_button.connect("clicked", self.__on_edit_clicked)
            edit_button.get_style_context().add_class("overlay-button")
            edit_button.set_property("valign", Gtk.Align.CENTER)
            edit_button.set_tooltip_text(_("Edit bookmark"))
            edit_button.show()
            grid.attach(edit_button, 2, 0, 1, 2)
        elif item_type == Type.TAG:
            if item_id == Type.NONE:
                icon_name = "folder-visiting-symbolic"
            elif item_id == Type.POPULARS:
                icon_name = "emote-love-symbolic"
            elif item_id == Type.RECENTS:
                icon_name = "document-open-recent-symbolic"
            else:
                icon_name = "folder-symbolic"
            open_button = Gtk.Button.new_from_icon_name(
                icon_name,
                Gtk.IconSize.MENU)
            open_button.connect("clicked", self.__on_open_clicked)
            open_button.get_style_context().add_class("overlay-button2")
            open_button.set_tooltip_text(_("Open all pages with this tag"))
            open_button.show()
            grid.attach(open_button, 0, 0, 1, 1)
        grid.show()
        if item_type in [Type.BOOKMARK, Type.SEARCH, Type.HISTORY]:
            grid.get_style_context().add_class("bigrow")
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
    def __set_favicon(self, favicon):
        """
            Try to get a favicon for current URI
            @param favicon as Gtk.Image
            @param uri as str
        """
        uri = self.__item.get_property("uri")
        favicon_path = App().art.get_favicon_path(uri)
        if favicon_path is not None:
            favicon.set_from_file(favicon_path)
        else:
            favicon.set_from_icon_name("applications-internet",
                                       Gtk.IconSize.LARGE_TOOLBAR)
        favicon.show()

    def __on_query_tooltip(self, widget, x, y, keyboard, tooltip):
        """
            Show tooltip if needed
            @param widget as Gtk.Widget
            @param x as int
            @param y as int
            @param keyboard as bool
            @param tooltip as Gtk.Tooltip
        """
        text = ''
        layout = widget.get_layout()
        label = widget.get_text()
        if layout.is_ellipsized():
            text = "%s" % (GLib.markup_escape_text(label))
        widget.set_tooltip_markup(text)

    def __on_drag_begin(self, widget, context):
        """
            We need to select self
            @param widget as Gtk.Widget
            @param context as Gdk.DragContext
        """
        # add current drag to selected rows
        self.get_parent().select_row(self)

    def __on_drag_data_get(self, widget, context, data, info, time):
        """
            Send item ids
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
            Move items
            @param widget as Gtk.Widget
            @param context as Gdk.DragContext
            @param x as int
            @param y as int
            @param data as Gtk.SelectionData
            @param info as int
            @param time as int
        """
        try:
            items = []
            for rowid in data.get_text().split("@"):
                if not rowid:
                    continue
                bookmark_id = int(rowid)
                tag_id = self.__item.get_property("id")
                items.append((bookmark_id, tag_id))
            self.emit("moved", GLib.Variant("aai", items))
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
            Handle button press in popover
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        # Lets user select item
        if event.state & Gdk.ModifierType.CONTROL_MASK or\
                event.state & Gdk.ModifierType.SHIFT_MASK:
            if self.is_selected():
                self.get_parent().unselect_row(self)
            else:
                self.get_parent().select_row(self)
            return True
        # Event is for internal button
        if eventbox.get_window() != event.window:
            return True
        uri = self.__item.get_property("uri")
        type_id = self.__item.get_property("type")
        if type_id in [Type.HISTORY, Type.SUGGESTION,
                       Type.SEARCH, Type.BOOKMARK]:
            if event.button == 1:
                self.__window.container.current.webview.load_uri(uri)
                self.__window.container.set_expose(False)
                self.__window.close_popovers()
            else:
                self.__window.container.add_webview(uri,
                                                    LoadingType.FOREGROUND)
                if event.button == 2:
                    self.__window.close_popovers()
        elif type_id == Type.VIEW:
            title = self.__item.get_property("title")
            for view in self.__window.container.views:
                if view.webview.uri == uri and view.webview.title == title:
                    self.__window.container.set_current(view, True)
                    self.__window.close_popovers()
                    break
        else:
            self.emit("activate")
            # We force focus to stay on title entry
            GLib.idle_add(self.__window.toolbar.title.focus_entry)

    def __on_edit_clicked(self, button):
        """
            Edit self
            @param button as Gtk.Button
        """
        self.emit("edited")

    def __on_open_clicked(self, button):
        """
            Open all bookmarks
            @param button as Gtk.Button
        """
        self.__window.close_popovers()
        tag_id = self.__item.get_property("id")
        if tag_id == Type.POPULARS:
            items = App().bookmarks.get_populars(50)
        elif tag_id == Type.RECENTS:
            items = App().bookmarks.get_recents()
        elif tag_id == Type.UNCLASSIFIED:
            items = App().bookmarks.get_unclassified()
        else:
            items = App().bookmarks.get_bookmarks(tag_id)
        pages = []
        i = 0
        for (bid, uri, title) in items:
            loading_type = wanted_loading_type(i)
            pages.append((uri, title, 0, False, None, loading_type))
            i += 1
        self.__window.container.add_webviews(pages)

    def __on_delete_clicked(self, button):
        """
            Delete self
            @param button as Gtk.Button
        """
        history_id = self.__item.get_property("id")
        guid = App().history.get_guid(history_id)
        if App().sync_worker is not None:
            App().sync_worker.remove_from_history(guid)
        App().history.remove(history_id)
        GLib.idle_add(self.destroy)


class Input:
    NONE = 0
    SEARCH = 1
    TAGS = 2
    BOOKMARKS = 3


class UriPopover(Gtk.Popover):
    """
        Show user bookmarks or search
    """

    def __init__(self, window):
        """
            Init popover
            @param window as Window
        """
        Gtk.Popover.__init__(self)
        self.set_modal(False)
        window.register(self, False)
        self.__window = window
        self.__input = False
        self.__modifier = 0
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
        self.__history_model = Gio.ListStore()
        self.__history_box = builder.get_object("history_box")
        self.__history_box.bind_model(self.__history_model,
                                      self.__on_item_create)
        self.__search_box = builder.get_object("search_box")
        self.__stack = builder.get_object("stack")
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
            self.__stack.add(grid)
            self.__stack.set_visible_child(grid)
        else:
            self.__stack.set_visible_child_name(child)
        Gtk.Popover.popup(self)

    def set_search_text(self, search):
        """
            Set search model
            @param search as str
        """
        self.__set_search_text(search)
        self.add_suggestions([search], Type.SEARCH, True)
        self.__stack.set_visible_child_name("search")

    def add_views(self, views):
        """
            Add a row representing view
            @param views as [View]
        """
        if self.__stack.get_visible_child_name() != "search":
            return
        for view in views:
            item = Item()
            item.set_property("type", Type.VIEW)
            item.set_property("title", view.webview.title)
            item.set_property("uri", view.webview.uri)
            item.set_property("search", self.__search)
            item.set_property("score", Type.VIEW)
            child = Row(item, self.__window)
            child.show()
            self.__search_box.insert(child, 0)

    def add_suggestions(self, suggestions, score=Type.SUGGESTION, force=False):
        """
            Add suggestion to search
            @param suggestion as [str]
            @param score as int
            @param force as bool
        """
        if self.__stack.get_visible_child_name() != "search":
            return
        for suggestion in suggestions[:2]:
            if suggestion and (suggestion != self.__search or force):
                item = Item()
                item.set_property("type", Type.SUGGESTION)
                item.set_property("title", suggestion)
                item.set_property("uri",
                                  App().search.get_search_uri(suggestion))
                item.set_property("search", self.__search)
                item.set_property("score", score)
                child = Row(item, self.__window)
                child.show()
                self.__search_box.insert(child, 1)
                # We do not need to sort Type.SUGGESTION score because
                # this happend at the end
                if score == Type.SEARCH:
                    self.__do_sort_search()

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
            self.__tags_box.get_style_context().add_class("kbd-input")
            self.__bookmarks_box.get_style_context().remove_class("kbd-input")
            self.__window.toolbar.title.set_text_entry("")
            return True
        elif event.keyval == Gdk.KEY_Right and self.__input == Input.TAGS:
            self.__input = Input.BOOKMARKS
            self.__bookmarks_box.get_style_context().add_class("kbd-input")
            self.__tags_box.get_style_context().remove_class("kbd-input")
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
                    self.__tags_box.get_style_context().add_class("kbd-input")
                    self.__input = Input.TAGS
                else:
                    self.__input = Input.NONE
                box = self.__get_current_input_box()
                if box is not None:
                    rows = box.get_children()
                    if rows:
                        box.select_row(None)
                        box.select_row(rows[0])
                return True
            box = self.__get_current_input_box()
            rows = box.get_children()
            if box is None or not rows:
                self.__input = Input.NONE
                return False
            selected = box.get_selected_row()
            # If nothing selected, select first row
            if selected is None:
                box.select_row(rows[0])
                if self.__input == Input.TAGS:
                    item_id = rows[0].item.get_property("id")
                    self.__set_bookmarks(item_id)
            else:
                idx = -1 if event.keyval == Gdk.KEY_Up else 1
                for row in rows:
                    if row == selected:
                        break
                    idx += 1
                box.select_row(None)
                if idx >= len(rows):
                    box.select_row(rows[0])
                    if self.__input == Input.TAGS:
                        item_id = rows[0].item.get_property("id")
                        self.__set_bookmarks(item_id)
                    return True
                elif idx < 0:
                    # Do not go to uribar for bookmarks & search
                    if self.__input in [Input.BOOKMARKS, Input.SEARCH]:
                        box.select_row(rows[-1])
                        return True
                    else:
                        box.select_row(None)
                        self.__input = Input.NONE
                        box.get_style_context().remove_class("kbd-input")
                else:
                    box.select_row(rows[idx])
                    if self.__input == Input.TAGS:
                        item_id = rows[idx].item.get_property("id")
                        self.__set_bookmarks(item_id)
                    return True
        elif event.keyval in [Gdk.KEY_Return, Gdk.KEY_KP_Enter]:
            box = self.__get_current_input_box()
            if box is not None:
                selected = box.get_selected_row()
                if selected is not None:
                    container = self.__window.container
                    item = selected.item
                    # Switch to view
                    if item.get_property("type") == Type.VIEW:
                        title = item.get_property("title")
                        uri = item.get_property("uri")
                        for view in container.views:
                            if view.webview.uri == uri and\
                                    view.webview.title == title:
                                container.set_current(view, True)
                                self.__window.close_popovers()
                                break
                    # Load URI
                    else:
                        uri = selected.item.get_property("uri")
                        if uri:
                            self.__window.close_popovers()
                            container.current.webview.load_uri(uri)
                            container.set_expose(False)
                            return True
            else:
                self.__input = Input.NONE
        else:
            self.__input = Input.NONE
        return False

    @property
    def input(self):
        """
            Get input type
            @return Input
        """
        return self.__input

#######################
# PROTECTED           #
#######################
    def _on_button_press_event(self, widget, event):
        """
            Store state for current click
            @param widget as Gtk.Widget
            @param event as Gdk.EventButton
        """
        # https://gitlab.gnome.org/GNOME/gtk/issues/497
        self.__modifier = event.state

    def _on_import_button_clicked(self, button):
        """
            Sync with Firefox Sync
            @param button as Gtk.Button
        """
        self.hide()
        from eolie.dialog_import_bookmarks import ImportBookmarksDialog
        dialog = ImportBookmarksDialog(self.__window)
        dialog.run()

    def _on_remove_button_clicked(self, button):
        """
            Remove bookmarks
            @param button as Gtk.Button
        """
        for row in self.__bookmarks_box.get_selected_rows():
            item_id = row.item.get_property("id")
            if App().sync_worker is not None:
                guid = App().bookmarks.get_guid(item_id)
                App().sync_worker.remove_from_bookmarks(guid)
            App().bookmarks.remove(item_id)
            self.__bookmarks_box.remove(row)
            self.__remove_button.hide()
        App().bookmarks.clean_tags()

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

        if self.__modifier & Gdk.ModifierType.SHIFT_MASK:
            self.__fix_bug_733108(listbox, row)

        if row is None:
            return

        # Update titlebar
        if row.item.get_property("type") == Type.SUGGESTION:
            title = row.item.get_property("title")
            self.__window.toolbar.title.set_text_entry(title)
        else:
            uri = row.item.get_property("uri")
            if not uri:
                return
            parsed = urlparse(uri)
            if parsed.scheme not in ["http", "https", "file"]:
                uri = ""
            self.__window.toolbar.title.set_text_entry(uri)
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
        self.__input = Input.NONE
        if not self.__search_box.get_children():
            self.set_search_text("")

    def _on_history_map(self, widget):
        """
            Init search
            @param widget as Gtk.Widget
        """
        self.__input = Input.NONE
        now = datetime.now()
        self.__calendar.select_month(now.month - 1, now.year)
        self.__calendar.select_day(now.day)

    def _on_close_map(self, widget):
        """
            Close popover
            @param widget as Gtk.Widget
        """
        self.__window.close_popovers()

    def _on_bookmarks_map(self, widget):
        """
            Init bookmarks
            @param widget as Gtk.Widget/None
        """
        current = None
        row = self.__tags_box.get_selected_row()
        if row is not None:
            current = row.item.get_property("id")
        self.__input == Input.TAGS
        for child in self.__tags_box.get_children():
            self.__tags_box.remove(child)
        static = [(Type.POPULARS,
                   # Translators: Plural
                   _("Popular")),
                  (Type.RECENTS,
                   # Translators: Plural
                   _("Recent")),
                  (Type.UNCLASSIFIED,
                   _("Unclassified"))]
        self.__add_tags(static + App().bookmarks.get_all_tags(), current)

    def _on_day_selected(self, calendar):
        """
            Show history for day
            @param calendar as Gtk.Calendar
        """
        (year, month, day) = calendar.get_date()
        date = datetime(year, month + 1, day, 0, 0)
        atime = mktime(date.timetuple())
        result = App().history.get(atime)
        self.__history_model.remove_all()
        self.__add_history_items(result, (year, month, day))
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
    def __fix_bug_733108(self, listbox, selected_row):
        """
            Make selection
            @param listbox as Gtk.ListBox
            @param selected_row as Row
        """
        self.__modifier = 0
        # Search for first and last selected rows
        another_selected_row = None
        found_selected = False
        for row in listbox.get_selected_rows():
            if row == selected_row:
                found_selected = True
            else:
                another_selected_row = row
                # Descending selection, we do not need to check for another
                # selected row
                if not found_selected:
                    break
        if another_selected_row is not None:
            another_index = another_selected_row.get_index()
            current_index = selected_row.get_index()
            if found_selected:
                r = range(current_index, another_index)
            else:
                r = range(another_index + 1, current_index)
            for i in r:
                row = listbox.get_row_at_index(i)
                listbox.select_row(row)

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

    def __do_sort_search(self):
        """
            Run a new sort after cleaning obsolete results
            @param force as bool
        """
        for child in self.__search_box.get_children():
            if child.item.get_property("search") != self.__search:
                child.destroy()
        self.__search_box.set_sort_func(self.__sort_search)
        self.__search_box.invalidate_sort()
        self.__search_box.set_sort_func(None)

    def __sort_search(self, row1, row2):
        """
            Sort search
            @param row1 as Row
            @param row2 as Row
        """
        pos1 = row1.item.get_property("score")
        pos2 = row2.item.get_property("score")
        return pos2 > pos1 or pos2 == Type.SEARCH

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

    def __add_searches(self, searches, search):
        """
            Add searches to model
            @param [(title, uri, score)] as [(str, strn int)]
            @param search as str
        """
        # Another search running, quit
        if search != self.__search:
            return
        elif searches:
            (rowid, title, uri, score) = searches.pop(0)
            for child in self.__search_box.get_children():
                if child.item.get_property("uri") == uri:
                    child.item.set_property("search", self.__search)
                    child.item.set_property("score", score)
                    GLib.idle_add(self.__add_searches, searches, search)
                    return
            item = Item()
            item.set_property("id", rowid)
            item.set_property("type", Type.SEARCH)
            item.set_property("title", title)
            item.set_property("uri", uri)
            item.set_property("search", self.__search)
            item.set_property("score", score)
            child = Row(item, self.__window)
            child.show()
            self.__search_box.add(child)
            GLib.idle_add(self.__add_searches, searches, search)
        else:
            self.__do_sort_search()

    def __add_bookmarks(self, bookmarks):
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
            self.__bookmarks_model.append(item)
            GLib.idle_add(self.__add_bookmarks, bookmarks)

    def __add_tags(self, tags, select, position=0):
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
            child = Row(item, self.__window)
            child.connect("activate", self.__on_row_activated)
            child.connect("moved", self.__on_row_moved)
            child.show()
            self.__tags_box.add(child)
            GLib.idle_add(self.__add_tags, tags, select)
        else:
            if select is None:
                select = Type.POPULARS
            # Search for previous current row
            for row in self.__tags_box.get_children():
                if row.item.get_property("id") == select:
                    self.__tags_box.select_row(row)
                    break
            self.__set_bookmarks(select)

    def __add_history_items(self, items, date):
        """
            Add history items to model
            @param [(history_id, title, uri, atime)]  as [(int, str, str, int)]
            @param date (jj, mm, aaaa) as (int, int, int)
        """
        if items:
            if date != self.__calendar.get_date():
                return
            (history_id, title, uri, atime) = items.pop(0)
            item = Item()
            item.set_property("id", history_id)
            item.set_property("type", Type.HISTORY)
            item.set_property("title", title)
            item.set_property("uri", uri)
            item.set_property("atime", atime)
            self.__history_model.append(item)
            GLib.idle_add(self.__add_history_items, items, date)

    def __get_current_box(self):
        """
            Get current box
            @return Gtk.ListBox
        """
        name = self.__stack.get_visible_child_name()
        box = None
        if name == "bookmarks":
            box = self.__bookmarks_box
        elif name == "history":
            box = self.__history_box
        elif name == "search":
            box = self.__search_box
        return box

    def __get_current_input_box(self):
        """
            Get current box with input
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
        self.__search = search
        if search == '':
            result = App().history.search(search, 50)
        else:
            result = App().history.search(search, 15)
            result += App().bookmarks.search(search, 15)

        self.__add_searches(result, search)

    def __set_bookmarks(self, tag_id):
        """
            Set bookmarks for tag id
            @param tag id as int
        """
        self.__bookmarks_model.remove_all()
        self.__remove_button.hide()
        if tag_id == Type.POPULARS:
            items = App().bookmarks.get_populars(50)
        elif tag_id == Type.RECENTS:
            items = App().bookmarks.get_recents()
        elif tag_id == Type.UNCLASSIFIED:
            items = App().bookmarks.get_unclassified()
        else:
            items = App().bookmarks.get_bookmarks(tag_id)
        self.__bookmarks_count.set_text(_("%s bookmarks") % len(items))
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
        self.__search_box.get_style_context().remove_class("kbd-input")
        self.__bookmarks_box.get_style_context().remove_class("kbd-input")
        self.__tags_box.get_style_context().remove_class("kbd-input")
        size = self.__window.get_size()
        width = min(800, size[0])
        height = min(700, size[1] * 0.9)
        self.set_size_request(width, height)
        self.__scrolled_bookmarks.set_size_request(width * 0.4, -1)

    def __on_unmap(self, widget):
        """
            Switch to bookmarks
            @param widget as Gtk.Widget
        """
        self.__stack.set_visible_child_name("bookmarks")
        self.__bookmarks_model.remove_all()
        for child in self.__tags_box.get_children():
            child.destroy()
        for child in self.__search_box.get_children():
            child.destroy()

    def __on_row_activated(self, row):
        """
            Select row
            @param row as Row
        """
        item_id = row.item.get_property("id")
        self.__set_bookmarks(item_id)

    def __on_row_moved(self, row, items):
        """
            Move bookmark from current selected tag to tag
            @param row as Row
            @param items [(bookmark_id, tag_id)] as [(int, int)]
            @param tag id as int
        """
        tag_row = self.__tags_box.get_selected_row()
        current_tag_id = tag_row.item.get_property("id")
        for item in items:
            if current_tag_id >= 0:
                App().bookmarks.del_tag_from(current_tag_id, item[0])
            App().bookmarks.add_tag_to(item[1], item[0])
        self.__on_row_activated(tag_row)
        App().bookmarks.clean_tags()
        if App().sync_worker is not None:
            App().sync_worker.push_bookmark(item[0])

    def __on_row_edited(self, row):
        """
            Edit bookmark associated to row
            @param row as Row
        """
        from eolie.widget_bookmark_edit import BookmarkEditWidget
        widget = BookmarkEditWidget(row.item.get_property("id"))
        widget.show()
        self.__stack.add(widget)
        self.__stack.set_visible_child(widget)

    def __on_item_create(self, item):
        """
            Add child to box
            @param item as Item
        """
        child = Row(item, self.__window)
        child.connect("edited", self.__on_row_edited)
        return child
