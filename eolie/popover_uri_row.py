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

from gi.repository import Gtk, Gdk, GObject, GLib, Pango

from gettext import gettext as _
from datetime import datetime

from eolie.define import App, Type, LoadingType, MARGIN_SMALL
from eolie.utils import wanted_loading_type


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
        item_id = item.get_property("id")
        item_type = item.get_property("type")
        uri = item.get_property("uri")
        title = item.get_property("title")
        grid = Gtk.Grid()
        grid.set_property("margin", MARGIN_SMALL)
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
        elif item_type == Type.WEBVIEW:
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

        if item_type == Type.HISTORY:
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
            open_button.get_style_context().add_class("overlay-button-alt")
            open_button.set_tooltip_text(_("Open all pages with this tag"))
            open_button.show()
            grid.attach(open_button, 0, 0, 1, 1)
        grid.show()
        style_context = self.get_style_context()
        style_context.add_class("row")
        eventbox = Gtk.EventBox()
        eventbox.add(grid)
        eventbox.set_size_request(-1, 30)
        eventbox.connect("button-release-event",
                         self.__on_button_release_event)
        eventbox.show()
        self.add(eventbox)

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
            favicon.set_from_icon_name("web-browser-symbolic",
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

    def __on_button_release_event(self, eventbox, event):
        """
            Handle button press in popover
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
        type_id = self.__item.get_property("type")
        if type_id in [Type.HISTORY, Type.SUGGESTION,
                       Type.SEARCH, Type.BOOKMARK]:
            if event.button == 1:
                self.__window.container.webview.load_uri(uri)
                self.__window.container.set_expose(False)
                self.__window.close_popovers()
            else:
                self.__window.container.add_webview_for_uri(
                    uri, LoadingType.FOREGROUND)
                if event.button == 2:
                    self.__window.close_popovers()
        elif type_id == Type.WEBVIEW:
            title = self.__item.get_property("title")
            for webview in self.__window.container.webviews:
                if webview.uri == uri and webview.title == title:
                    self.__window.container.set_visible_webview(webview)
                    self.__window.close_popovers()
                    break
        else:
            self.emit("activate")
            # We force focus to stay on title entry
            GLib.idle_add(self.__window.toolbar.title.entry.focus)

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
        i = 0
        for (bid, uri, title) in items:
            loading_type = wanted_loading_type(i)
            self.__window.container.add_webview_for_uri(uri, loading_type)
            i += 1

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
