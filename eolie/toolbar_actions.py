# Copyright (c) 2017-2021 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from gi.repository import Gtk, GLib

from eolie.define import App, LoadingType
from eolie.utils import update_popover_internals
from eolie.helper_gestures import GesturesHelper


class ToolbarActions(Gtk.Bin):
    """
        Actions toolbar
    """

    def __init__(self, window, fullscreen):
        """
            Init toolbar
            @param window as Window
            @param fullscreen as bool
        """
        Gtk.Bin.__init__(self)
        self.__window = window
        self.__timeout_id = None
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/ToolbarActions.ui")
        builder.connect_signals(self)

        self.add(builder.get_object("actions"))
        self.set_hexpand(True)
        self.__backward_button = builder.get_object("back_button")
        self.__forward_button = builder.get_object("forward_button")
        self.__pages_button = builder.get_object("pages_button")
        self.__view_button = builder.get_object("view_button")
        self.__close_button = builder.get_object("close_button")
        self.__count = builder.get_object("count")

        self.__gesture1 = GesturesHelper(
            self.__backward_button,
            primary_press_callback=self.__on_back_primary_press,
            secondary_press_callback=self.__on_back_secondary_press,
            primary_long_callback=self.__on_back_primary_long)
        self.__gesture2 = GesturesHelper(
            self.__forward_button,
            primary_press_callback=self.__on_forward_primary_press,
            secondary_press_callback=self.__on_forward_secondary_press,
            primary_long_callback=self.__on_forward_primary_long)

    def set_actions(self, webview):
        """
            Set available actions based on view
            @param webview as WebView
        """
        self.__backward_button.set_sensitive(webview.can_go_back())
        self.__forward_button.set_sensitive(webview.can_go_forward())

    def backward(self):
        """
            Click next
        """
        webview = self.__window.container.webview
        webview.go_back()

    def forward(self):
        """
            Click previous
        """
        webview = self.__window.container.webview
        webview.go_forward()

    @property
    def count_label(self):
        """
            Get count label
            @return Gtk.Label
        """
        return self.__count

    @property
    def view_button(self):
        """
            Get view pages button
            @return Gtk.MenuButton
        """
        return self.__view_button

#######################
# PROTECTED           #
#######################
    def _on_new_button_clicked(self, button):
        """
            Add a new web view
            @param button as Gtk.Button
        """
        self.__window.container.add_webview_for_uri(App().start_page,
                                                    LoadingType.FOREGROUND)
        self.__window.close_popovers()
        self.__window.toolbar.title.start_search()

    def _on_application_button_toggled(self, button):
        """
            Show pages popover
            @param button as Gtk.ToggleButton
        """
        self.__window.close_popovers()
        if not button.get_active():
            return
        from eolie.menu_application import ApplicationMenu
        menu = ApplicationMenu(self.__window)
        popover = Gtk.Popover.new_from_model(button, menu)
        popover.set_modal(False)
        self.__window.register(popover)
        popover.connect("closed", lambda x: button.set_active(False))
        popover.popup()

    def _on_view_button_toggled(self, button):
        """
            Show current views
            @param button as Gtk.ToggleButton
        """
        active = button.get_active()
        self.__window.container.set_expose(active)
        self.__window.close_popovers()

    def _on_close_button_clicked(self, button):
        """
            Close current page
            @param button as button
        """
        self.__window.container.try_close_webview(
            self.__window.container.webview)

#######################
# PRIVATE             #
#######################
    def __show_menu(self, button):
        """
            Show back history
            @param button as Gtk.Button
        """
        current = self.__window.container.webview
        if button == self.__backward_button:
            history_list = current.get_back_forward_list().get_back_list()
        else:
            history_list = current.get_back_forward_list().get_forward_list()
        if history_list:
            from eolie.menu_history import HistoryMenu
            model = HistoryMenu(history_list, self.__window)
            popover = Gtk.Popover.new_from_model(button, model)
            popover.set_modal(False)
            self.__window.register(popover)
            GLib.idle_add(popover.forall, update_popover_internals)
            popover.connect("closed",
                            self.__on_navigation_popover_closed,
                            model)
            popover.popup()

    def __on_navigation_popover_closed(self, popover, model):
        """
            Clear menu actions
            @param popover
            @param model as HistoryMenu/None
        """
        # Let model activate actions, idle needed to action activate
        GLib.idle_add(model.clean)

    def __on_back_primary_press(self, x, y, event):
        """
            Go backward in history
            @param x as int
            @param y as int
            @param even as Gdk.Event
        """
        self.backward()

    def __on_back_secondary_press(self, x, y):
        """
            Show backward menu
            @param x as int
            @param y as int
        """
        self.__show_menu(self.__backward_button)

    def __on_back_primary_long(self, x, y):
        """
            Show backward menu
            @param x as int
            @param y as int
        """
        self.__show_menu(self.__backward_button)

    def __on_forward_primary_press(self, x, y, event):
        """
            Go forward in history
            @param x as int
            @param y as int
            @param even as Gdk.Event
        """
        self.forward()

    def __on_forward_secondary_press(self, x, y):
        """
            Show forward menu
            @param x as int
            @param y as int
        """
        self.__show_menu(self.__forward_button)

    def __on_forward_primary_long(self, x, y):
        """
            Show forward menu
            @param x as int
            @param y as int
        """
        self.__show_menu(self.__forward_button)
