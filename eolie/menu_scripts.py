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

from gi.repository import Gtk, Pango, GObject

from gettext import gettext as _
from urllib.parse import urlparse

from eolie.logger import Logger
from eolie.define import App
from eolie.utils import emit_signal
from eolie.helper_gestures import GesturesHelper


class ScriptRow(Gtk.ListBoxRow, GesturesHelper):
    """
        Script row (Allowing to select a script for uri)
    """

    __gsignals__ = {
        "activated": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, uri, toggled):
        """
            Init row
            @param uri as str
            @param toggled as bool
        """
        Gtk.ListBoxRow.__init__(self)
        self.__uri = uri
        grid = Gtk.Grid()
        grid.set_column_spacing(5)
        grid.show()
        label = Gtk.Label.new(uri)
        label.set_hexpand(True)
        label.set_property("halign", Gtk.Align.START)
        label.set_max_width_chars(30)
        label.set_ellipsize(Pango.EllipsizeMode.START)
        label.set_tooltip_text(uri)
        label.show()
        self.__check = Gtk.CheckButton()
        self.__check.set_active(toggled)
        self.__check.connect("toggled", self.__on_check_toggled)
        self.__check.show()
        grid.add(self.__check)
        grid.add(label)
        eventbox = Gtk.EventBox.new()
        eventbox.show()
        eventbox.add(grid)
        self.add(eventbox)
        GesturesHelper.__init__(self, eventbox)

    def set_active(self, active):
        """
            Set row active
            @param active as bool
        """
        self.__check.set_active(active)

    @property
    def uri(self):
        """
            Get uri
            @return str
        """
        return self.__uri

    @property
    def is_active(self):
        """
            Get Check button
            @return bool
        """
        return self.__check.get_active()

#######################
# PROTECTED           #
#######################
    def _on_primary_press_gesture(self, x, y, event):
        """
            Toggle check button
            @param x as int
            @param y as int
            @param event as Gdk.Event
        """
        toggled = not self.__check.get_active()
        self.__check.set_active(toggled)

#######################
# PRIVATE             #
#######################
    def __on_check_toggled(self, button):
        """
            Emit activated signal
            @param button as Gtk.CheckButton
        """
        emit_signal(self, "activated")


class ScriptsMenu(Gtk.Grid):
    """
        Menu allowing user to enable scripts for URI
    """

    __ALLOW_ALL = _("Allow all scripts")

    def __init__(self, uri, window):
        """
            Init widget
            @param uri as str
            @param window as Window
        """
        Gtk.Grid.__init__(self)
        self.set_column_spacing(10)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.__uri = uri
        self.__window = window
        self.__back_button = Gtk.ModelButton.new()
        self.__back_button.show()
        self.__back_button.set_property("menu_name", "main")
        self.__back_button.set_property("inverted", True)
        self.__back_button.set_property("centered", True)
        self.__back_button.set_property("text", _("Scripts"))
        self.__listbox = Gtk.ListBox.new()
        self.__listbox.show()
        self.__listbox.get_style_context().add_class("menu-listbox")
        self.__listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.__listbox.connect("map", self.__on_map)
        self.set_property("margin", 5)
        self.add(self.__back_button)
        self.add(self.__listbox)

#######################
# PRIVATE             #
#######################
    def __is_script_active(self, script, netloc, internal):
        """
            True if script active for netloc
            @param script as str
            @param netloc as str
            @param internal as bool
            @return bool
        """
        content_blocker = App().get_content_blocker("block-scripts")
        if script == ".*":
            uri = ".*"
        else:
            script_parsed = urlparse(script)
            uri = "%s%s.*" % (script_parsed.netloc, script_parsed.path)
        result = content_blocker.exceptions.is_domain_exception(
            netloc, uri, internal)
        return result

    def __on_map(self, listbox):
        """
            Populate languages
            @param listbox as Gtk.ListBox
        """
        if listbox.get_children():
            return
        webview = self.__window.container.webview
        webview.run_javascript_from_gresource(
                "/org/gnome/Eolie/javascript/GetScripts.js", None,
                self.__on_get_scripts)

    def __on_get_scripts(self, source, result):
        """
            Add scripts to menu
            @param source as GObject.Object
            @param result as Gio.AsyncResult
        """
        scripts = []
        try:
            data = source.run_javascript_from_gresource_finish(result)
            scripts = data.get_js_value().to_string().split("@@@")
        except Exception as e:
            Logger.warning("ScriptsMenu::__on_get_scripts(): %s", e)
        parsed = urlparse(self.__window.container.webview.uri)
        allow_all_active = self.__is_script_active('.*', parsed.netloc, False)
        row = ScriptRow(self.__ALLOW_ALL, allow_all_active)
        row.connect("activated", self.__on_row_activated, False)
        row.show()
        self.__listbox.add(row)
        for script in scripts:
            if not script:
                continue
            internal = script.find(parsed.netloc) != -1
            row = ScriptRow(script,
                            self.__is_script_active(script,
                                                    parsed.netloc,
                                                    internal))
            row.connect("activated", self.__on_row_activated, internal)
            if allow_all_active:
                row.set_sensitive(False)
            row.show()
            self.__listbox.add(row)

    def __on_row_activated(self, row, internal):
        """
            Update exceptions
            @param row as ScriptRow
            @param internal as bool
        """
        parsed = urlparse(self.__window.container.webview.uri)
        content_blocker = App().get_content_blocker("block-scripts")
        if row.uri == self.__ALLOW_ALL:
            uri = ".*"
            for _row in self.__listbox.get_children()[1:]:
                _row.set_active(False)
                _row.set_sensitive(not row.is_active)
        else:
            script_parsed = urlparse(row.uri)
            uri = "%s%s.*" % (script_parsed.netloc, script_parsed.path)
        if row.is_active:
            content_blocker.exceptions.add_domain_exception(
                parsed.netloc, uri, internal)
        else:
            content_blocker.exceptions.remove_domain_exception(
                parsed.netloc, uri, internal)
        content_blocker.exceptions.save()
        content_blocker.update()
        self.__window.container.webview.reload()
