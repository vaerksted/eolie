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

from gi.repository import Gtk, GObject, Pango, GLib

import sqlite3
import itertools

from eolie.define import El


class Item(GObject.GObject):
    host = GObject.Property(type=str,
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
        self.get_style_context().add_class("row")
        grid = Gtk.Grid()
        grid.set_column_spacing(10)
        grid.set_hexpand(True)
        grid.set_property("valign", Gtk.Align.CENTER)
        host = Gtk.Label.new(item.get_property("host"))
        host.set_ellipsize(Pango.EllipsizeMode.END)
        host.set_property("halign", Gtk.Align.START)
        host.set_hexpand(True)
        host.set_property("has-tooltip", True)
        host.connect("query-tooltip", self.__on_query_tooltip)
        host.set_max_width_chars(40)
        host.show()
        delete_button = Gtk.Button.new_from_icon_name(
                                                     "user-trash-symbolic",
                                                     Gtk.IconSize.MENU)
        delete_button.get_image().set_opacity(0.5)
        delete_button.connect("clicked", self.__on_delete_clicked)
        delete_button.get_style_context().add_class("overlay-button")
        delete_button.show()
        grid.add(host)
        grid.add(delete_button)
        grid.show()
        self.add(grid)

    @property
    def item(self):
        """
            Get item for row
            @return Item
        """
        return self.__item

#######################
# PRIVATE             #
#######################
    def __on_delete_clicked(self, button):
        """
            Delete item from cookies
            @param button as Gtk.Button
        """
        sql = sqlite3.connect(El().cookies_path, 600.0)
        sql.execute("DELETE FROM moz_cookies\
                     WHERE host=?", (self.__item.get_property("host"),))
        sql.commit()
        GLib.idle_add(self.destroy)

    def __on_query_tooltip(self, widget, x, y, keyboard, tooltip):
        """
            Show tooltip if needed
            @param widget as Gtk.Widget
            @param x as int
            @param y as int
            @param keyboard as bool
            @param tooltip as Gtk.Tooltip
        """
        text = ""
        layout = widget.get_layout()
        label = widget.get_text()
        if layout.is_ellipsized():
            text = "%s" % (GLib.markup_escape_text(label))
        widget.set_tooltip_markup(text)


class CookiesPopover(Gtk.Popover):
    """
        Show current cookies
    """

    def __init__(self):
        """
            Init popover
        """
        Gtk.Popover.__init__(self)
        self.__filter = ""
        self.set_position(Gtk.PositionType.BOTTOM)
        builder = Gtk.Builder()
        builder.add_from_resource('/org/gnome/Eolie/PopoverCookies.ui')
        builder.connect_signals(self)
        self.__listbox = builder.get_object("listbox")
        self.__listbox.set_filter_func(self.__filter_func)
        self.add(builder.get_object('widget'))
        self.set_size_request(300, 300)

    def populate(self):
        """
            Populate popover
        """
        sql = sqlite3.connect(El().cookies_path, 600.0)
        result = sql.execute("SELECT DISTINCT host\
                              FROM moz_cookies")
        self.__add_cookies(list(itertools.chain(*result)))

#######################
# PROTECTED           #
#######################
    def _on_search_changed(self, entry):
        """
            Update filter
            @param entry as Gtk.Entry
        """
        self.__filter = entry.get_text()
        self.__listbox.invalidate_filter()

    def _on_remove_all_clicked(self, button):
        """
            Remove all cookies
            @param button as Gtk.Button
        """
        sql = sqlite3.connect(El().cookies_path, 600.0)
        sql.execute("DELETE FROM moz_cookies")
        sql.commit()
        self.popdown()

#######################
# PRIVATE             #
#######################
    def __filter_func(self, row):
        """
            Filter rows
            @param row as Row
        """
        return self.__filter in row.item.get_property("host")

    def __add_cookies(self, cookies):
        """
            Add cookies to model
            @param [host]  as [str]
        """
        if cookies:
            host = cookies.pop(0)
            item = Item()
            item.set_property('host', host)
            child = Row(item)
            child.show()
            self.__listbox.add(child)
            GLib.idle_add(self.__add_cookies, cookies)
