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

from gi.repository import Gtk, GLib, GObject, Gdk, Pango

import sqlite3

from eolie.define import EOLIE_DATA_PATH, COOKIES_PATH, MARGIN_SMALL
from eolie.logger import Logger
from eolie.utils import emit_signal


class Cookie(GObject.GObject):
    name = GObject.Property(type=str,
                            default="")
    value = GObject.Property(type=str,
                             default="")

    def __init__(self):
        GObject.GObject.__init__(self)


class Row(Gtk.ListBoxRow):
    """
        A profile row
    """
    __gsignals__ = {
        'moved': (GObject.SignalFlags.RUN_FIRST, None, (str, bool))
    }

    def __init__(self, item):
        """
            Init row
            @param item as Item
        """
        Gtk.ListBoxRow.__init__(self)
        self.__item = item
        value = GLib.uri_escape_string(item.get_property("value"), None, True)
        markup = "%s <b>%s</b>" % (item.get_property("name"), value)
        self.__label = Gtk.Label.new()
        self.__label.set_markup(markup)
        self.__label.set_ellipsize(Pango.EllipsizeMode.END)
        self.__label.set_property("margin", MARGIN_SMALL)
        self.__label.set_property("halign", Gtk.Align.START)
        self.__label.show()
        eventbox = Gtk.EventBox()
        eventbox.show()
        eventbox.add(self.__label)
        self.add(eventbox)
        self.drag_source_set(Gdk.ModifierType.BUTTON1_MASK, [],
                             Gdk.DragAction.MOVE)
        self.drag_source_add_text_targets()
        self.connect("drag-data-get", self.__on_drag_data_get)
        self.drag_dest_set(Gtk.DestDefaults.DROP | Gtk.DestDefaults.MOTION,
                           [], Gdk.DragAction.MOVE)
        self.drag_dest_add_text_targets()
        self.connect("drag-data-received", self.__on_drag_data_received)
        self.connect("drag-motion", self.__on_drag_motion)
        self.connect("drag-leave", self.__on_drag_leave)

    def set_name(self, name):
        """
            Set name
            @param name as str
        """
        self.__label.set_text(name)

    @property
    def item(self):
        """
            Get associated item
            @return item
        """
        return self.__item

#######################
# PRIVATE             #
#######################
    def __on_drag_data_get(self, widget, context, data, info, time):
        """
            Set data to name
            @param widget as Gtk.Widget
            @param context as Gdk.DragContext
            @param data as Gtk.SelectionData
            @param info as int
            @param time as int
        """
        name = self.item.get_property("name")
        data.set_text(name, len(name))

    def __on_drag_data_received(self, widget, context, x, y, data, info, time):
        """
            Move row
            @param widget as Gtk.Widget
            @param context as Gdk.DragContext
            @param x as int
            @param y as int
            @param data as Gtk.SelectionData
            @param info as int
            @param time as int
        """
        height = self.get_allocated_height()
        if y > height / 2:
            up = False
        else:
            up = True
        try:
            name = data.get_text()
            emit_signal(self, "moved", name, up)
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
        height = self.get_allocated_height()
        if y > height / 2:
            self.get_style_context().add_class("drag-up")
            self.get_style_context().remove_class("drag-down")
        else:
            self.get_style_context().remove_class("drag-up")
            self.get_style_context().add_class("drag-down")

    def __on_drag_leave(self, widget, context, time):
        """
            Remove style
            @param widget as Gtk.Widget
            @param context as Gdk.DragContext
            @param time as int
        """
        self.get_style_context().remove_class("drag-up")
        self.get_style_context().remove_class("drag-down")


class CookiesDialog(Gtk.Bin):
    """
        A cookie management dialog
    """

    __gsignals__ = {
        "destroy-me": (GObject.SignalFlags.RUN_FIRST, None, ())
    }

    def __init__(self):
        """
            Init widget
        """
        Gtk.Bin.__init__(self)
        self.__filter = ""
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/DialogCookies.ui")
        self.__entry = builder.get_object("entry")
        self.__cookies = builder.get_object("cookies")
        self.__delete_button = builder.get_object("delete_button")
        builder.connect_signals(self)
        self.add(builder.get_object("widget"))
        self.__populate()

#######################
# PROTECTED           #
#######################
    def _on_back_clicked(self, button):
        """
            Ask to be destroyed
            @param button as Gtk.Button
        """
        emit_signal(self, "destroy-me")

    def _on_delete_clicked(self, button):
        """
            Delete selected cookies
            @param button as Gtk.Button
        """
        try:
            rows = self.__cookies.get_selected_rows()
            path = COOKIES_PATH % (EOLIE_DATA_PATH,
                                   "default")
            request = "DELETE FROM moz_cookies WHERE "
            filters = ()
            for row in rows:
                request += "host=? OR "
                filters += (row.item.name,)
                row.destroy()
            request += " 0"
            sql = sqlite3.connect(path, 600.0)
            sql.execute(request, filters)
            sql.commit()
        except Exception as e:
            Logger.error("CookiesDialog::_on_delete_clicked(): %s", e)

    def _on_entry_changed(self, entry):
        """
            Update add button
        """
        self.__add_button.set_sensitive(entry.get_text())

    def _on_search_changed(self, entry):
        """
            Update filter
            @param entry as Gtk.SearchEntry
        """
        self.__filter = entry.get_text()
        self.__cookies.invalidate_filter()

    def _on_cookie_selected(self, listbox, row):
        """
            Update cookies
            @param listbox as Gtk.ListBox
            @param row as Row
        """
        rows = self.__cookies.get_selected_rows()
        if len(rows) > 1:
            if not row.is_selected():
                listbox.unselect_row(row)
        self.__delete_button.set_sensitive(rows)

#######################
# PRIVATE             #
#######################
    def __filter_func(self, row):
        """
            Filter cookies
            @param row as Row
        """
        name = row.item.get_property("name")
        value = row.item.get_property("value")
        return name.find(self.__filter) != -1 or\
            value.find(self.__filter) != -1

    def __add_cookies(self, cookies):
        """
            Add cookies to model
            @param [host]  as [str]
        """
        if cookies:
            (host, value) = cookies.pop(0)
            item = Cookie()
            item.set_property("name", host)
            item.set_property("value", value)
            row = Row(item)
            row.show()
            self.__cookies.add(row)
            GLib.idle_add(self.__add_cookies, cookies)

    def __populate(self):
        """
            Populate profile
        """
        try:
            path = COOKIES_PATH % (EOLIE_DATA_PATH, "default")
            sql = sqlite3.connect(path, 600.0)
            result = sql.execute("SELECT DISTINCT host, value\
                                  FROM moz_cookies")
            self.__add_cookies(list(result))
        except Exception as e:
            Logger.error("DialogSearchEngine::__populate(): %s", e)
