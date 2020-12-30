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

from gi.repository import Gtk, GObject, Pango, GLib

from eolie.helper_passwords import PasswordsHelper
from eolie.define import App, MARGIN_SMALL
from eolie.utils import emit_signal


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
        uri = Gtk.Label.new()
        uri.set_markup("%s <span alpha='40000'>%s</span>" % (
            GLib.markup_escape_text(item.get_property("uri")),
            GLib.markup_escape_text(item.get_property("username"))))
        uri.set_ellipsize(Pango.EllipsizeMode.END)
        uri.set_property("margin", MARGIN_SMALL)
        uri.set_property("halign", Gtk.Align.START)
        uri.set_hexpand(True)
        uri.set_property("has-tooltip", True)
        uri.connect("query-tooltip", self.__on_query_tooltip)
        uri.show()
        self.add(uri)

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


class CredentialsDialog(Gtk.Bin):
    """
        Show saved credentials
    """

    __gsignals__ = {
        "destroy-me": (GObject.SignalFlags.RUN_FIRST, None, ())
    }

    def __init__(self):
        """
            Init dialog
        """
        Gtk.Bin.__init__(self)
        self.__filter = ""
        self.__helper = PasswordsHelper()
        builder = Gtk.Builder()
        builder.add_from_resource('/org/gnome/Eolie/DialogCredentials.ui')
        builder.connect_signals(self)
        self.__search_bar = builder.get_object("search_bar")
        self.__remove_button = builder.get_object("remove_button")
        self.__listbox = builder.get_object("listbox")
        self.__listbox.set_filter_func(self.__filter_func)
        self.__listbox.set_sort_func(self.__sort_func)
        self.add(builder.get_object('widget'))
        self.__helper.get_all(self.__add_password)

#######################
# PROTECTED           #
#######################
    def _on_back_clicked(self, button):
        """
            Ask to be destroyed
            @param button as Gtk.Button
        """
        emit_signal(self, "destroy-me")

    def _on_search_changed(self, entry):
        """
            Update filter
            @param entry as Gtk.Entry
        """
        self.__filter = entry.get_text()
        self.__listbox.invalidate_filter()

    def _on_remove_clicked(self, button):
        """
            Remove all passwords
            @param button as Gtk.Button
        """
        for row in self.__listbox.get_selected_rows():
            row.delete()

    def _on_row_selected(self, listbox, row):
        """
            Update clear button state
            @param listbox as Gtk.ListBox
            @param row as Gtk.ListBoxRow
        """
        self.__remove_button.set_sensitive(
            len(listbox.get_selected_rows()) != 0)

    def _on_search_toggled(self, button):
        """
            Show entry
            @param button as Gtk.Button
        """
        self.__search_bar.set_search_mode(button.get_active())

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
