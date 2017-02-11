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

from gi.repository import Gtk, Gdk, WebKit2

from gettext import gettext as _


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
        self.__find_controller = webview.get_find_controller()
        grid = Gtk.Grid()
        self.__search_entry = Gtk.SearchEntry.new()
        self.__search_entry.set_size_request(300, -1)
        self.__search_entry.connect("search-changed", self.__on_search_changed)
        self.__search_entry.connect('key-press-event', self.__on_key_press)
        self.__search_entry.show()
        backward_button = Gtk.Button.new_from_icon_name("go-up-symbolic",
                                                        Gtk.IconSize.BUTTON)
        backward_button.set_tooltip_text(_("Search previous occurrence"))
        backward_button.connect("clicked",
                                lambda x:
                                self.__find_controller.search_previous())
        backward_button.show()
        forward_button = Gtk.Button.new_from_icon_name("go-down-symbolic",
                                                       Gtk.IconSize.BUTTON)
        forward_button.set_tooltip_text(_("Search next occurrence"))
        forward_button.connect("clicked",
                               lambda x:
                               self.__find_controller.search_next())
        forward_button.show()
        grid.add(self.__search_entry)
        grid.add(backward_button)
        grid.add(forward_button)
        grid.get_style_context().add_class('linked')
        grid.show()
        self.set_show_close_button(True)
        self.add(grid)

    def grab_focus(self):
        """
            Forward to entry
        """
        self.__search_entry.grab_focus()

#######################
# PRIVATE             #
#######################
    def __on_key_press(self, widget, event):
        """
            If Esc, hide widget, why GTK doesn't do that?
            Otherwise, we get an ugly frame
            @param widget as Gtk.SearchEntry
            @param event as Gdk.Event
        """
        if event.keyval == Gdk.KEY_Escape:
            self.set_search_mode(False)

    def __on_search_changed(self, entry):
        """
            Update highlight
            @param entry as Gtk.Entry
        """
        self.__find_controller.search(entry.get_text(),
                                      WebKit2.FindOptions.CASE_INSENSITIVE,
                                      100)
