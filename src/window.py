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

from gi.repository import Gtk, GLib, Gio, Gdk, Soup

from eolie.define import El, Indicator
from eolie.toolbar import Toolbar
from eolie.container import Container
from eolie.utils import get_current_monitor_model
from eolie.helper_task import TaskHelper


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
                                       title="Eolie",
                                       icon_name="org.gnome.Eolie")
        self.__monitor_model = ""
        self.__popovers = []
        self.__zoom_level = 1.0
        self.__container = None
        self.__window_state = 0
        self.__setup_content()
        self.setup_window()
        self.connect("realize", self.__on_realize)
        self.connect("key-release-event", self.__on_key_release_event)
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

    def fullscreen(self, force=True):
        """
            Prepare window to fullscreen and enter fullscreen
            @param force as bool
        """
        if self.__fullscreen_revealer is not None:
            return
        self.__fullscreen_toolbar = Toolbar(self, True)
        # Do not count container views as destroy may be pending on somes
        count = str(len(self.__container.pages_manager.children))
        self.__fullscreen_toolbar.actions.count_label.set_text(count)
        self.__fullscreen_toolbar.show()
        self.update(self.container.current.webview)
        self.__fullscreen_revealer = Gtk.Revealer.new()
        self.__fullscreen_revealer.set_property("valign", Gtk.Align.START)
        self.__fullscreen_revealer.add(self.__fullscreen_toolbar)
        self.__fullscreen_revealer.show()
        self.__container.add_overlay(self.__fullscreen_revealer)
        self.__container.sites_manager.hide()
        if force:
            Gtk.ApplicationWindow.fullscreen(self)
        self.connect("motion-notify-event", self.__on_motion_notify_event)

    def unfullscreen(self, force=True):
        """
            Prepare window to unfullscreen and leave fullscreen
            @param force as bool
        """
        if self.__fullscreen_revealer is None:
            return
        self.disconnect_by_func(self.__on_motion_notify_event)
        GLib.idle_add(self.__fullscreen_toolbar.destroy)
        GLib.idle_add(self.__fullscreen_revealer.destroy)
        self.__container.sites_manager.show()
        self.__fullscreen_toolbar = None
        self.__fullscreen_revealer = None
        self.update(self.container.current.webview)
        if force:
            Gtk.ApplicationWindow.unfullscreen(self)
        self.__container.current.webview.run_javascript(
                                        "document.webkitExitFullscreen();",
                                        None,
                                        None)

    def update(self, webview):
        """
            Update window
            @param webview as WebView
        """
        if webview == self.__container.current.webview:
            uri = webview.delayed_uri
            if uri is None:
                uri = webview.get_uri()
            else:
                webview.load_uri(uri)
            webview.update_access_time()
            self.container.sites_manager.update_indicator(
                                                      self.__container.current)
            title = webview.get_title()
            self.toolbar.title.update_load_indicator(webview)
            if webview.popups:
                self.toolbar.title.show_indicator(Indicator.POPUPS)
            else:
                self.toolbar.title.show_indicator(Indicator.NONE)
            if uri is not None:
                self.toolbar.title.set_uri(uri)
            if webview.is_loading():
                self.toolbar.title.show_spinner(True)
                self.toolbar.title.progress.show()
            else:
                self.toolbar.title.progress.hide()
                self.toolbar.title.show_readable_button(
                                                webview.readable_content != "")
            if title:
                self.toolbar.title.set_title(title)
            elif uri:
                self.toolbar.title.set_title(uri)
            self.toolbar.actions.set_actions(webview)

    def hide(self):
        """
            Hide window
        """
        self.disconnect_by_func(self.__on_window_state_event)
        self.disconnect_by_func(self.__on_configure_event)
        Gtk.ApplicationWindow.hide(self)

    def register(self, popover, monitor=True):
        """
            Add a popover to window
            @param popover as Gtk.Popover
            @param monitor as bool, check if closed
        """
        self.__popovers.append(popover)
        if monitor:
            popover.connect("closed", self.__on_popover_closed)

    def close_popovers(self):
        """
            Close all popovers
            @return closed as bool
        """
        closed = False
        for popover in self.__popovers:
            if popover.is_visible():
                closed = True
            popover.popdown()
        return closed

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
        if self.__fullscreen_toolbar is None:
            return self.__toolbar
        else:
            return self.__fullscreen_toolbar

    @property
    def zoom_level(self):
        """
           Get zoom level for window
           @return float
        """
        return self.__zoom_level

    @property
    def is_fullscreen(self):
        """
            True if fullscreen
            @return bool
        """
        return self.__window_state & Gdk.WindowState.FULLSCREEN

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
        self.__toolbar = Toolbar(self)
        self.__fullscreen_toolbar = None
        self.__fullscreen_revealer = None
        self.__toolbar.show()
        self.__container = Container(self)
        self.__container.show()
        self.set_titlebar(self.__toolbar)
        self.__toolbar.set_show_close_button(True)
        self.add(self.__container)

    def __show_source_code(self, uri):
        """
            Show source code for uri
            @param uri as str
            @thread safe
        """
        # FIXME make this code async using TaskHelper
        try:
            (tmp, tmp_stream) = Gio.File.new_tmp("XXXXXX.html")
            session = Soup.Session.new()
            request = session.request(uri)
            stream = request.send(None)
            bytes = bytearray(0)
            buf = stream.read_bytes(1024, None).get_data()
            while buf:
                bytes += buf
                buf = stream.read_bytes(1024, None).get_data()
            tmp_stream.get_output_stream().write_all(bytes)
            stream.close()
            tmp_stream.close()
            return tmp
        except Exception as e:
            print("Window::__show_source_code():", e)
            return None

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
        # Allow respecting GNOME IHM, should tile on screen == 1280px
        self.toolbar.end.move_control_in_menu(size[0] < 700)
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
            @param: window as Gtk.Window
            @param: event as Gdk.EventWindowState
        """
        if event.changed_mask & Gdk.WindowState.MAXIMIZED:
            size = widget.get_size()
            self.toolbar.end.move_control_in_menu(size[0] < 700)
            self.toolbar.title.set_width(size[0]/3)
            El().settings.set_boolean("window-maximized",
                                      event.new_window_state &
                                      Gdk.WindowState.MAXIMIZED)
        self.__window_state = event.new_window_state

    def __on_motion_notify_event(self, widget, event):
        """
            Reaveal/hide toolbar if needed
            @param: widget as Gtk.Widget
            @param: event as Gdk.EventMotion
        """
        if self.__fullscreen_revealer.get_reveal_child() and\
                not self.__fullscreen_revealer.get_child_revealed():
            return
        if event.y < self.__fullscreen_revealer.get_allocated_height():
            self.__fullscreen_revealer.set_reveal_child(True)
        else:
            lock = False
            for popover in self.__popovers:
                if popover.is_visible():
                    lock = True
                    break
            if not lock:
                self.__fullscreen_revealer.set_reveal_child(False)

    def __on_realize(self, widget):
        """
            Update zoom level
            @param widget as Gtk.Widget
        """
        self.update_zoom_level(False)

    def __on_show_source_code(self, f):
        """
            Launch text editor
            @param f as Gio.File
        """
        if f is not None:
            appinfo = Gio.app_info_get_default_for_type("text/plain", False)
            appinfo.launch([f], None)

    def __on_key_release_event(self, window, event):
        """
            Disable expose if Ctrl released
            @param window as Window
            @param event as Gdk.EventKey
        """
        if event.keyval in [Gdk.KEY_Control_L, Gdk.KEY_Escape]:
            self.__container.pages_manager.ctrl_released()
            self.__container.set_expose(False)
        if self.__container.current.reading and event.keyval == Gdk.KEY_Escape:
            self.__container.current.switch_read_mode()
            self.__toolbar.title.set_reading()

    def __on_shortcut_action(self, action, param):
        """
            Global shortcuts handler
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        string = param.get_string()
        if string == "uri":
            if self.is_fullscreen:
                self.__fullscreen_revealer.set_reveal_child(True)
            self.toolbar.title.focus_entry()
        elif string == "fullscreen":
            if self.is_fullscreen:
                self.unfullscreen()
            else:
                self.fullscreen()
        elif string == "quit":
            El().quit(True)
        elif string == "new_page":
            self.container.add_webview(El().start_page, Gdk.WindowType.CHILD)
        elif string == "close_page":
            if self.is_fullscreen:
                self.container.current.webview.emit("leave-fullscreen")
                Gtk.ApplicationWindow.unfullscreen(self)
            self.__container.pages_manager.close_view(self.container.current)
        elif string == "reload":
            self.container.current.webview.reload()
        elif string == "source":
            uri = self.container.current.webview.get_uri()
            task_helper = TaskHelper()
            task_helper.run(self.__show_source_code,
                            (uri,),
                            self.__on_show_source_code)
        elif string == "find":
            find_widget = self.container.current.find_widget
            find_widget.set_search_mode(True)
            find_widget.search()
        elif string == "backward":
            self.toolbar.actions.backward()
        elif string == "forward":
            self.toolbar.actions.forward()
        elif string == "previous":
            self.__container.pages_manager.previous()
        elif string == "next":
            self.__container.pages_manager.next()
        elif string == "print":
            self.container.current.webview.print()
        elif string == "private":
            self.container.add_webview(El().start_page,
                                       Gdk.WindowType.CHILD,
                                       True)
        elif string == "last_page":
            El().pages_menu.activate_last_action()
        elif string == "zoom_in":
            self.container.current.webview.zoom_in()
        elif string == "zoom_out":
            self.container.current.webview.zoom_out()
        elif string == "zoom_default":
            self.container.current.webview.zoom_default()
        elif string == "history":
            self.toolbar.title.focus_entry("history")
        elif string == "search":
            self.toolbar.title.focus_entry("search")
        elif string == "expose":
            active = self.toolbar.actions.view_button.get_active()
            self.toolbar.actions.view_button.set_active(not active)
        elif string == "show_left_panel":
            value = El().settings.get_value("show-left-panel")
            El().settings.set_value("show-left-panel",
                                    GLib.Variant("b", not value))

    def __on_popover_closed(self, popover):
        """
            Remove popover from registered
            @param popover as Gtk.Popover
        """
        # Needed as popover may belong to another class
        popover.disconnect_by_func(self.__on_popover_closed)
        if popover in self.__popovers:
            self.__popovers.remove(popover)
            GLib.timeout_add(1000, popover.destroy)
