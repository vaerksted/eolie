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

from gi.repository import Gtk, GObject, Pango, GLib

from eolie.helper_passwords import PasswordsHelper
from eolie.define import App


class Item(GObject.GObject):
    username = GObject.Property(type=str,
                                default="")
    uri = GObject.Property(type=str,
                           default="")
    uuid = GObject.Property(type=str,
                            default="")

    def __init__(self):
        GObject.GObject.__init__(self)


class Row(Gtk.ListBoxRow):
    """
        A cookie row
    """

    def __init__(self, item, helper):
        """
            Init row
            @param item as Item
            @param helper as PasswordsHelper
        """
        Gtk.ListBoxRow.__init__(self)
        self.__item = item
        self.__helper = helper
        self.get_style_context().add_class("row")
        grid = Gtk.Grid()
        grid.set_column_spacing(10)
        grid.set_hexpand(True)
        grid.set_property("valign", Gtk.Align.CENTER)
        uri = Gtk.Label.new("%s@%s" % (item.get_property("username"),
                                       item.get_property("uri")))
        uri.set_ellipsize(Pango.EllipsizeMode.END)
        uri.set_property("halign", Gtk.Align.START)
        uri.set_hexpand(True)
        uri.set_property("has-tooltip", True)
        uri.connect("query-tooltip", self.__on_query_tooltip)
        uri.set_max_width_chars(40)
        uri.show()
        delete_button = Gtk.Button.new_from_icon_name(
                                                     "user-trash-symbolic",
                                                     Gtk.IconSize.MENU)
        delete_button.get_image().set_opacity(0.5)
        delete_button.connect("clicked", self.__on_delete_clicked)
        delete_button.get_style_context().add_class("overlay-button")
        delete_button.show()
        grid.add(uri)
        grid.add(delete_button)
        grid.show()
        self.add(grid)

    def delete(self):
        """
            Delete password
        """
        self.hide()
        uuid = self.__item.get_property("uuid")
        self.__helper.clear(uuid)
        if App().sync_worker is not None:
            App().sync_worker.remove_from_passwords(uuid)

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
        self.delete()

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


class PasswordsPopover(Gtk.Popover):
    """
        Show saved passwords
    """

    def __init__(self):
        """
            Init popover
        """
        Gtk.Popover.__init__(self)
        self.__filter = ""
        self.__helper = PasswordsHelper()
        self.set_position(Gtk.PositionType.BOTTOM)
        builder = Gtk.Builder()
        builder.add_from_resource('/org/gnome/Eolie/PopoverPasswords.ui')
        builder.connect_signals(self)
        self.__listbox = builder.get_object("listbox")
        self.__listbox.set_filter_func(self.__filter_func)
        self.__listbox.set_sort_func(self.__sort_func)
        self.add(builder.get_object('widget'))
        self.set_size_request(400, 300)

    def populate(self):
        """
            Populate popover
        """
        self.__helper.get_all(self.__add_password)

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
            Remove all passwords
            @param button as Gtk.Button
        """
        for child in self.__listbox.get_children():
            child.delete()

#######################
# PRIVATE             #
#######################
    def __filter_func(self, row):
        """
            Filter rows
            @param row as Row
        """
        return self.__filter in row.item.get_property("uri")

    def __sort_func(self, row1, row2):
        """
            Sort rows
            @param row1 as Row
            @param row2 as Row
        """
        return row2.item.get_property("username") <\
            row1.item.get_property("username")

    def __add_password(self, attributes, password, uri, index, count):
        """
            Add password to model
            @param attributes as {}
            @param password as str
            @param uri as None
            @param index as int
            @param count as int
        """
        if attributes is None:
            return
        try:
            item = Item()
            item.set_property("username", attributes["login"])
            item.set_property("uri", attributes["formSubmitURL"])
            item.set_property("uuid", attributes["uuid"])
            child = Row(item, self.__helper)
            child.show()
            self.__listbox.add(child)
        except:
            # Here because firsts Eolie releases do not
            # provide formSubmitURL
            # FIXME Remove later
            pass
