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

from gi.repository import Gtk, GLib, GObject, Gio, Gdk

import json
import sqlite3

from eolie.define import El, EOLIE_DATA_PATH, COOKIES_PATH


class Profile(GObject.GObject):
    name = GObject.Property(type=str,
                            default="")
    profile = GObject.Property(type=str,
                               default="")
    value = GObject.Property(type=str,
                             default="")

    def __init__(self):
        GObject.GObject.__init__(self)


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
        self.__label = Gtk.Label()
        self.__label.set_markup(markup)
        self.__label.set_max_width_chars(20)
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
        if y > height/2:
            up = False
        else:
            up = True
        try:
            name = data.get_text()
            self.emit("moved", name, up)
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
        if y > height/2:
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


class CookiesDialog:
    """
        A cookie management dialog
    """

    def __init__(self, hide_cookies, parent):
        """
            Init widget
            @param hide_cookies as bool
            @param parent as Gtk.Window
        """
        self.__hide_cookies = hide_cookies
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/DialogCookies.ui")
        self.__dialog = builder.get_object("dialog")
        self.__dialog.set_transient_for(parent)
        self.__entry = builder.get_object("entry")
        self.__profiles = builder.get_object("profiles")
        self.__cookies = builder.get_object("cookies")
        self.__add_button = builder.get_object("add_button")
        self.__remove_button = builder.get_object("remove_button")
        self.__delete_button = builder.get_object("delete_button")
        if self.__hide_cookies:
            builder.get_object("scrolled").hide()
            self.__delete_button.hide()
            self.__dialog.set_size_request(300, 400)
        else:
            self.__dialog.set_size_request(600, 500)
        self.__remove_button.set_sensitive(False)
        builder.connect_signals(self)

    def run(self):
        """
            Run dialog
        """
        self.__populate()
        self.__dialog.run()
        self.__dialog.destroy()

#######################
# PROTECTED           #
#######################
    def _on_dialog_response(self, dialog, response_id):
        """
            Save user agent
            @param dialog as Gtk.Dialog
            @param response_id as int
        """
        try:
            profiles = {}
            for child in self.__profiles.get_children():
                profile = child.item.get_property("profile")
                name = child.item.get_property("name")
                profiles[profile] = name
            content = json.dumps(profiles)
            f = Gio.File.new_for_path(EOLIE_DATA_PATH +
                                      "/profiles.json")
            f.replace_contents(content.encode("utf-8"),
                               None,
                               False,
                               Gio.FileCreateFlags.REPLACE_DESTINATION,
                               None)
            if response_id != Gtk.ResponseType.DELETE_EVENT:
                rows = self.__cookies.get_selected_rows()
                row = self.__profiles.get_selected_row()
                path = COOKIES_PATH % (EOLIE_DATA_PATH,
                                       row.item.get_property("profile"))
                request = "DELETE FROM moz_cookies WHERE "
                filters = ()
                for row in rows:
                    request += "host=? AND"
                    filters += (row.item.name,)
                request += " 1"
                sql = sqlite3.connect(path, 600.0)
                sql.execute(request, filters)
                sql.commit()
        except Exception as e:
            print("CookiesDialog::_on_dialog_response():", e)

    def _on_entry_changed(self, entry):
        """
            Update add button
        """
        self.__add_button.set_sensitive(entry.get_text())

    def _on_add_button_clicked(self, button):
        """
            Add a new engine
            @param button as Gtk.Button
        """
        text = self.__entry.get_text()
        self.__entry.set_text("")
        # Only one New engine
        for child in self.__profiles.get_children():
            if child.item.name == text:
                return

        item = Profile()
        item.set_property("name",  text)
        item.set_property("profile", GLib.uri_escape_string(text.lower(),
                                                            None,
                                                            True))
        child = Row(item)
        child.connect("moved", self.__on_moved)
        child.show()
        self.__profiles.add(child)
        self.__profiles.select_row(child)
        self.__remove_button.set_sensitive(True)

    def _on_remove_button_clicked(self, button):
        """
            Remove engine
            @param button as Gtk.Button
        """
        row = self.__profiles.get_selected_row()
        if row is not None:
            profile = row.item.get_property("profile")
            El().websettings.remove_profile(profile)
            try:
                path = COOKIES_PATH % (EOLIE_DATA_PATH, profile)
                f = Gio.File.new_for_path(path)
                if f.query_exists():
                    f.trash()
            except Exception as e:
                print("DialogSearchEngine::_on_remove_button_clicked():", e)
            row.destroy()

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

    def _on_profile_selected(self, listbox, row):
        """
            Update cookies
            @param listbox as Gtk.ListBox
            @param row as Row
        """
        if row is not None:
            profile = row.item.get_property("profile")
            self.__remove_button.set_sensitive(profile != "default")
            if not self.__hide_cookies:
                for child in self.__cookies.get_children():
                    GLib.idle_add(child.destroy)
                self.__cookies.set_sensitive(True)
                try:
                    path = COOKIES_PATH % (EOLIE_DATA_PATH, profile)
                    sql = sqlite3.connect(path, 600.0)
                    result = sql.execute("SELECT DISTINCT host, value\
                                          FROM moz_cookies")
                    self.__add_cookies(list(result))
                except Exception as e:
                    print("DialogCookies::_on_profile_selected():", e)

#######################
# PRIVATE             #
#######################
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

    def __add_profiles(self, profiles):
        """
            Add profile to the list
            @param profiles as {}
        """
        if profiles:
            (profile, name) = profiles.popitem()
            item = Profile()
            item.set_property("profile", profile)
            item.set_property("name", name)
            row = Row(item)
            row.connect("moved", self.__on_moved)
            row.show()
            self.__profiles.prepend(row)
            if profiles:
                GLib.idle_add(self.__add_profiles, profiles)
            else:
                row.activate()

    def __populate(self):
        """
            Populate profile
        """
        # Load user profiles
        try:
            f = Gio.File.new_for_path(EOLIE_DATA_PATH +
                                      "/profiles.json")
            if f.query_exists():
                (status, contents, tag) = f.load_contents(None)
                profiles = json.loads(contents.decode("utf-8"))
                self.__add_profiles(profiles)
        except Exception as e:
            print("DialogSearchEngine::__populate():", e)

    def __get_index(self, name):
        """
            Get child index
            @param name as str
            @return int
        """
        # Search current index
        children = self.__profiles.get_children()
        index = 0
        for child in children:
            if child.item.get_property("name") == name:
                break
            index += 1
        return index

    def __on_moved(self, child, name, up):
        """
            Move child row
            @param child as SidebarChild
            @param name as str
            @param up as bool
        """
        index = self.__get_index(name)
        row = self.__profiles.get_row_at_index(index)
        if row is None:
            return
        self.__profiles.remove(row)
        child_index = self.__get_index(child.item.get_property("name"))
        if not up:
            child_index += 1
        self.__profiles.insert(row, child_index)
