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

from gi.repository import Gtk, GLib, Gio, Gdk

from eolie.define import El
from eolie.toolbar import Toolbar
from eolie.container import Container
from eolie.utils import get_current_monitor_model


class Window(Gtk.ApplicationWindow):
    """
        Main window
    """

    def __init__(self, app):
        """
            Init window
            @param app as Gtk.Application
        """
        self.__timeout_configure = None
        Gtk.ApplicationWindow.__init__(self,
                                       application=app,
                                       title="Eolie")
        self.__monitor_model = ""
        self.__zoom_level = 1.0
        self.__container = None
        self.__setup_content()
        self.setup_window()
        self.connect("realize", self.__on_realize)
        self.connect("window-state-event", self.__on_window_state_event)
        self.connect("configure-event", self.__on_configure_event)

        # Set window actions
        shortcut_action = Gio.SimpleAction.new("shortcut",
                                               GLib.VariantType.new("s"))
        shortcut_action.connect("activate", self.__on_shortcut_action)
        self.add_action(shortcut_action)

    def setup_window(self):
        """
            Setup window position and size
        """
        self.__setup_pos()
        if El().settings.get_value("window-maximized"):
            self.maximize()

    def update_zoom_level(self, force):
        """
            Update zoom level
            @param force as bool
        """
        monitor_model = get_current_monitor_model(self)
        if force or monitor_model != self.__monitor_model:
            # Update window default zoom level
            self.__update_zoom_level()
            self.__monitor_model = monitor_model
            # Update view zoom level
            for view in self.__container.views:
                view.webview.update_zoom_level()

    def hide(self):
        """
            Hide window
        """
        self.disconnect_by_func(self.__on_window_state_event)
        self.disconnect_by_func(self.__on_configure_event)
        Gtk.ApplicationWindow.hide(self)

    @property
    def container(self):
        """
            Get window container
            @return Container
        """
        return self.__container

    @property
    def monitor_model(self):
        """
            Get current monitor model
        """
        self.__monitor_model

    @property
    def toolbar(self):
        """
            Get window toolbar
            @return Toolbar
        """
        return self.__toolbar

    @property
    def zoom_level(self):
        """
           Get zoom level for window
           @return float
        """
        return self.__zoom_level

############
# Private  #
############
    def __update_zoom_level(self):
        """
            Update zoom level for default screen
        """
        monitor_model = get_current_monitor_model(self)
        zoom_levels = El().settings.get_value(
                                         "default-zoom-level")
        user_zoom_level = False
        for zoom_level in zoom_levels:
            zoom_splited = zoom_level.split("@")
            if zoom_splited[0] == monitor_model:
                self.__zoom_level = float(zoom_splited[1])
                user_zoom_level = True
                break
        if not user_zoom_level:
            self.__zoom_level = 1.0

    def __setup_content(self):
        """
            Setup window content
        """
        self.set_default_icon_name("web-browser")
        self.__toolbar = Toolbar(self)
        self.__toolbar.show()
        self.__container = Container(self)
        self.__container.show()
        self.set_titlebar(self.__toolbar)
        self.__toolbar.set_show_close_button(True)
        self.add(self.__container)

    def __setup_pos(self):
        """
            Set window position
        """
        size_setting = El().settings.get_value("window-size")
        if len(size_setting) == 2 and\
           isinstance(size_setting[0], int) and\
           isinstance(size_setting[1], int):
            self.resize(size_setting[0], size_setting[1])
        position_setting = El().settings.get_value("window-position")
        if len(position_setting) == 2 and\
           isinstance(position_setting[0], int) and\
           isinstance(position_setting[1], int):
            self.move(position_setting[0], position_setting[1])

    def __save_size_position(self, window):
        """
            Save window state, update current view content size
            @param: window as Gtk.Window
        """
        self.update_zoom_level(False)
        self.__timeout_configure = None
        size = window.get_size()
        El().settings.set_value("window-size",
                                GLib.Variant("ai", [size[0], size[1]]))

        position = window.get_position()
        El().settings.set_value("window-position",
                                GLib.Variant("ai",
                                             [position[0], position[1]]))

    def __on_configure_event(self, window, event):
        """
            Delay event
            @param: window as Gtk.Window
            @param: event as Gdk.Event
        """
        size = window.get_size()
        self.toolbar.title.set_width(size[0]/3)
        if self.__timeout_configure:
            GLib.source_remove(self.__timeout_configure)
            self.__timeout_configure = None
        if not self.is_maximized():
            self.__timeout_configure = GLib.timeout_add(
                                                   1000,
                                                   self.__save_size_position,
                                                   window)

    def __on_window_state_event(self, widget, event):
        """
            Save maximised state
        """
        size = widget.get_size()
        self.toolbar.title.set_width(size[0]/3)
        El().settings.set_boolean("window-maximized",
                                  "GDK_WINDOW_STATE_MAXIMIZED" in
                                  event.new_window_state.value_names)

    def __on_realize(self, widget):
        """
            Update zoom level
            @param widget as Gtk.Widget
        """
        self.update_zoom_level(False)

    def __on_shortcut_action(self, action, param):
        """
            Global shortcuts handler
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        string = param.get_string()
        if string == "uri":
            self.toolbar.title.focus_entry()
        elif string == "new_page":
            self.container.add_web_view(El().start_page, Gdk.WindowType.CHILD)
        elif string == "close_page":
            self.container.sidebar.close_view(self.container.current)
        elif string == "reload":
            self.container.current.webview.reload()
        elif string == "find":
            find_widget = self.container.current.find_widget
            search_mode = find_widget.get_search_mode()
            find_widget.set_search_mode(not search_mode)
            if not search_mode:
                find_widget.search()
                find_widget.grab_focus()
        elif string == "backward":
            self.toolbar.actions.backward()
        elif string == "forward":
            self.toolbar.actions.forward()
        elif string == "previous":
            self.container.sidebar.previous()
        elif string == "next":
            self.container.sidebar.next()
        elif string == "print":
            self.container.current.webview.print()
        elif string == "private":
            self.container.add_web_view(El().start_page,
                                        Gdk.WindowType.CHILD,
                                        True)
        elif string == "last_page":
            El().pages_menu.activate_last_action()
        elif string == "zoom_in":
            self.container.current.webview.zoom_in()
        elif string == "zoom_out":
            self.container.current.webview.zoom_out()
        elif string == "last_page":
            El().pages_menu.activate_last_action()
        elif string == "filter":
            button = self.toolbar.actions.filter_button
            button.set_active(not button.get_active())
