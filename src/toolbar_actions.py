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

from gi.repository import Gtk

from eolie.define import El


class ToolbarActions(Gtk.Bin):
    """
        Actions toolbar
    """

    def __init__(self, window):
        """
            Init toolbar
            @param window as Window
        """
        Gtk.Bin.__init__(self)
        self.__window = window
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/ToolbarActions.ui")
        builder.connect_signals(self)

        self.add(builder.get_object("actions"))

        self.__backward = builder.get_object("back_button")
        self.__forward = builder.get_object("forward_button")
        self.__filter = builder.get_object("filter_button")
        self.__closed_button = builder.get_object("closed_button")
        self.__closed_button.set_menu_model(El().closed_menu)
        sensitive = El().closed_menu.get_n_items() != 0
        self.__closed_button.set_sensitive(sensitive)

    def set_actions(self, view):
        """
            Set available actions based on view
            @param view as WebView
        """
        self.__backward.set_sensitive(view.can_go_back())
        self.__forward.set_sensitive(view.can_go_forward())

    def backward(self):
        """
            Click next
        """
        self.__backward.clicked()

    def forward(self):
        """
            Click previous
        """
        self.__forward.clicked()

    @property
    def closed_button(self):
        """
            Get closed pages button
            @return Gtk.MenuButton
        """
        return self.__closed_button

    @property
    def filter_button(self):
        """
            Get filtering toggle button
            @return Gtk.ToggleButton
        """
        return self.__filter

#######################
# PROTECTED           #
#######################
    def _on_back_button_clicked(self, button):
        """
            Go backward on current view
            @param button as Gtk.Button
        """
        self.__window.container.current.webview.go_back()
        self.__window.toolbar.title.hide_popover()

    def _on_forward_button_clicked(self, button):
        """
            Go forward on current view
            @param button as Gtk.Button
        """
        self.__window.container.current.webview.go_forward()
        self.__window.toolbar.title.hide_popover()

    def _on_new_button_clicked(self, button):
        """
            Add a new web view
            @param button as Gtk.Button
        """
        self.__window.container.add_web_view(El().start_page, True)
        self.__window.toolbar.title.hide_popover()

    def _on_filter_button_toggled(self, button):
        """
            Add a new web view
            @param button as Gtk.ToggleButton
        """
        self.__window.container.sidebar.set_filtered(button.get_active())
        self.__window.toolbar.title.hide_popover()
