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

from gi.repository import Gtk, Gdk, Gio, GLib, WebKit2

from gettext import gettext as _

from eolie.define import App


class FindWidget(Gtk.SearchBar):
    """
        Show a find in webpage widget
    """

    def __init__(self, webview):
        """
            Init widget
            @param webview as WebKit2.WebView
        """
        Gtk.SearchBar.__init__(self)
        self.__webview = webview
        self.__action = None
        self.__count = 0
        self.__current = 0
        self.__find_controller = webview.get_find_controller()
        self.__find_controller.connect("counted-matches",
                                       self.__on_counted_matches)
        self.__search_entry = Gtk.SearchEntry.new()
        self.__search_entry.set_size_request(300, -1)
        self.__search_entry.connect("search-changed", self.__on_search_changed)
        self.__search_entry.connect("key-press-event", self.__on_key_press)
        self.__search_entry.connect("map", self.__on_map)
        self.__search_entry.connect("unmap", self.__on_unmap)
        self.__search_entry.show()
        backward_button = Gtk.Button.new_from_icon_name("go-up-symbolic",
                                                        Gtk.IconSize.BUTTON)
        backward_button.set_tooltip_text(_("Search previous occurrence"))
        backward_button.connect("clicked",
                                lambda x:
                                self.__on_shortcut_action(
                                                  None,
                                                  GLib.Variant("s", "prev")))
        backward_button.show()
        forward_button = Gtk.Button.new_from_icon_name("go-down-symbolic",
                                                       Gtk.IconSize.BUTTON)
        forward_button.set_tooltip_text(_("Search next occurrence"))
        forward_button.connect("clicked",
                               lambda x:
                               self.__on_shortcut_action(
                                                  None,
                                                  GLib.Variant("s", "next")))
        forward_button.show()

        self.__label = Gtk.Label()
        self.__label.set_property("halign", Gtk.Align.START)
        self.__label.show()

        linked = Gtk.Grid()
        linked.add(self.__search_entry)
        linked.add(backward_button)
        linked.add(forward_button)
        linked.show()
        linked.get_style_context().add_class('linked')
        grid = Gtk.Grid()
        grid.set_column_spacing(5)
        grid.add(linked)
        grid.add(self.__label)
        grid.show()
        self.connect_entry(self.__search_entry)
        self.set_show_close_button(True)
        self.add(grid)

    def search(self):
        """
            Search for current clipboard
        """
        page_id = self.__webview.get_page_id()
        App().helper.call("GetSelection", page_id, None,
                          self.__on_get_selection)

#######################
# PRIVATE             #
#######################
    def __on_counted_matches(self, find_controller, count):
        """
            Update count label
            @param find_controller as WebKit2.FindController
            @param count as str
        """
        self.__count = count
        self.__label.set_text("%s matches" % self.__count)

    def __on_key_press(self, widget, event):
        """
            If Esc, hide widget, why GTK doesn't do that?
            Otherwise, we get an ugly frame
            @param widget as Gtk.SearchEntry
            @param event as Gdk.Event
        """
        if event.keyval == Gdk.KEY_Escape:
            self.__search_entry.set_text("")
            self.set_search_mode(False)
        elif event.keyval == Gdk.KEY_Return:
            self.__find_controller.search_next()
            self.__current += 1

    def __on_map(self, entry):
        """
            Set shortcuts
            @param entry as Gtk.Entry
        """
        self.__label.set_width_chars(len(_("1000 of 1000 matches")))
        self.__action = Gio.SimpleAction.new("find_shortcut",
                                             GLib.VariantType.new('s'))
        self.__action.connect("activate", self.__on_shortcut_action)
        App().add_action(self.__action)
        App().set_accels_for_action("app.find_shortcut::next", ["F3"])
        App().set_accels_for_action("app.find_shortcut::prev", ["<Shift>F3"])

    def __on_unmap(self, entry):
        """
            Unset shortcuts
            @param entry as Gtk.Entry
        """
        self.__label.set_width_chars(-1)
        App().remove_action("find_shortcut")
        self.__find_controller.search_finish()

    def __on_shortcut_action(self, action, param):
        """
            Global shortcuts handler
            @param action as Gio.SimpleAction/None
            @param param as GLib.Variant
        """
        string = param.get_string()
        if string == "next":
            self.__current += 1
            if self.__current > self.__count:
                self.__current = 1
            self.__find_controller.search_next()
        elif string == "prev":
            self.__current -= 1
            if self.__current < 1:
                self.__current = self.__count
            self.__find_controller.search_previous()
        self.__label.set_text("%s of %s matches" % (self.__current,
                                                    self.__count))

    def __on_search_changed(self, entry):
        """
            Update highlight
            @param entry as Gtk.Entry
        """
        text = entry.get_text()
        self.__label.set_text("")
        if len(text) < 2:
            return
        self.__current = 0
        # FIXME Can't understand what is max count :/
        self.__find_controller.count_matches(
                                text,
                                WebKit2.FindOptions.CASE_INSENSITIVE,
                                100)
        self.__find_controller.search(
                                text,
                                WebKit2.FindOptions.CASE_INSENSITIVE,
                                100)

    def __on_get_selection(self, source, result):
        """
            Start search with selection
            @param source as GObject.Object
            @param result as Gio.AsyncResult
        """
        selection = None
        try:
            selection = source.call_finish(result)[0]
        except:
            pass
        if selection is None:
            selection = ""
        self.__search_entry.set_text(selection)
        self.__search_entry.grab_focus()
