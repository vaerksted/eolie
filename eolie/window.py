# Copyright (c) 2017-2019 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from eolie.define import App, Indicator, LoadingType
from eolie.toolbar import Toolbar
from eolie.container import Container
from eolie.utils import get_current_monitor_model
from eolie.helper_task import TaskHelper
from eolie.logger import Logger
from eolie.window_state import WindowState


class Window(Gtk.ApplicationWindow, WindowState):
    """
        Main window
    """

    def __init__(self, size, is_maximized):
        """
            Init window
            @param app as Gtk.Application
            @param size as (int, int)
            @param is_maximized as bool
        """
        Gtk.ApplicationWindow.__init__(self,
                                       application=App(),
                                       title="Eolie",
                                       icon_name="org.gnome.Eolie")
        WindowState.__init__(self)
        self.__monitor_model = ""
        self.__popovers = []
        self.__zoom_level = 1.0
        self.__container = None
        self.__modifiers = 0
        self.__window_state = 0
        self.__timeout_configure = None
        self.__size = size
        self.set_default_size(size[0], size[1])
        self.__setup_content()
        self.connect("realize", self.__on_realize, is_maximized)
        self.connect("key-press-event", self.__on_key_press_event)
        self.connect("key-release-event", self.__on_key_release_event)
        self.connect("window-state-event", self.__on_window_state_event)
        self.connect("configure-event", self.__on_configure_event)

        # Set window actions
        shortcut_action = Gio.SimpleAction.new("shortcut",
                                               GLib.VariantType.new("s"))
        shortcut_action.connect("activate", self.__on_shortcut_action)
        self.add_action(shortcut_action)
        self.set_auto_startup_notification(False)

    def update_zoom_level(self, force):
        """
            Update zoom level
            @param force as bool
        """
        try:
            monitor_model = get_current_monitor_model(self)
            if force or monitor_model != self.__monitor_model:
                # Update window default zoom level
                self.__update_zoom_level()
                self.__monitor_model = monitor_model
                # Update view zoom level
                for view in self.__container.views:
                    view.webview.update_zoom_level()
        except Exception as e:
            Logger.error("Window::update_zoom_level(): %s", e)

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
        if App().settings.get_value("show-sidebar"):
            self.__container.sites_manager.show()
        self.__fullscreen_toolbar = None
        self.__fullscreen_revealer = None
        self.update(self.container.current.webview)
        # Do not count container views as destroy may be pending on somes
        # Reason: we do not remove/destroy view to let stack animation run
        count = len(self.container.pages_manager.children)
        self.toolbar.actions.count_label.set_text(str(count))
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
        uri = webview.uri
        if uri is not None:
            self.toolbar.title.update()
            accept_tls = App().websettings.get_accept_tls(uri)
            self.toolbar.end.show_tls_button(accept_tls)
        self.toolbar.title.show_indicator(Indicator.NONE)
        if webview.is_loading():
            self.toolbar.title.set_loading(True)
            self.toolbar.title.progress.show()
        else:
            self.toolbar.title.progress.hide()
            self.toolbar.title.set_loading(False)
        self.toolbar.title.show_readable_button(webview.readable)
        title = webview.title
        if title:
            self.toolbar.title.set_title(title)
        elif uri:
            self.toolbar.title.set_title(uri)
        self.toolbar.actions.set_actions(webview)

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

    def mark(self, mark):
        """
            Change window toolbar color
        """
        style = self.__toolbar.headerbar.get_style_context()
        if mark:
            style.add_class("toolbar-mark")
        else:
            style.remove_class("toolbar-mark")

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

    @property
    def size(self):
        """
            Unis_maximized window size
            return (int, int)
        """
        return self.__size

############
# Private  #
############
    def __update_zoom_level(self):
        """
            Update zoom level for default screen
        """
        monitor_model = get_current_monitor_model(self)
        zoom_levels = App().settings.get_value(
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
        self.__toolbar.headerbar.set_show_close_button(True)
        self.add(self.__container)

    def __setup_window(self, is_maximized):
        """
            Set window
            @param is_maximized as bool
        """
        try:
            if is_maximized:
                # Lets resize happen
                GLib.idle_add(self.maximize)
        except Exception as e:
            Logger.error("Window::__setup_window(): %s", e)

    def __on_configure_event(self, window, event):
        """
            Delay event
            @param: window as Gtk.Window
            @param: event as Gdk.Event
        """
        size = window.get_size()
        # Allow respecting GNOME IHM, should tile on screen == 1280px
        self.toolbar.end.move_control_in_menu(size[0] < 700)
        self.toolbar.title.set_width(size[0] / 3)
        if self.__timeout_configure:
            GLib.source_remove(self.__timeout_configure)
            self.__timeout_configure = None
        self.__timeout_configure = GLib.timeout_add(
            250,
            self.__on_configure_timeout)

    def __on_source_loaded(self, uri, status, content):
        """
            Show source code for uri
            @param uri as str
            @param status as bool
            @param content as bytes
        """
        try:
            (tmp, tmp_stream) = Gio.File.new_tmp("XXXXXX.html")
            tmp_stream.get_output_stream().write_all(content)
            tmp_stream.close()
            appinfo = Gio.app_info_get_default_for_type("text/plain", False)
            appinfo.launch([tmp], None)
        except Exception as e:
            Logger.error("Window::__on_source_loaded(): %s", e)

    def __on_configure_timeout(self):
        """
            Update zoom level
        """
        self.__timeout_configure = None
        self.update_zoom_level(False)
        if not self.is_maximized():
            self.__size = self.get_size()

    def __on_window_state_event(self, widget, event):
        """
            Save maximised state
            @param: window as Gtk.Window
            @param: event as Gdk.EventWindowState
        """
        if event.changed_mask & Gdk.WindowState.MAXIMIZED:
            size = widget.get_size()
            self.toolbar.end.move_control_in_menu(size[0] < 700)
            self.toolbar.title.set_width(size[0] / 3)
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

    def __on_realize(self, widget, is_maximized):
        """
            Update zoom level
            @param widget as Gtk.Widget
            @param is_maximized as bool
        """
        self.__setup_window(is_maximized)
        self.update_zoom_level(False)

    def __on_key_press_event(self, window, event):
        """
            Update PagesManager sort on Ctrl<Tab>
            @param window as Window
            @param event as Gdk.EventKey
        """
        if event.state & Gdk.ModifierType.CONTROL_MASK and\
                event.keyval == Gdk.KEY_Tab:
            if not self.container.in_expose:
                self.container.pages_manager.update_sort()

    def __on_key_release_event(self, window, event):
        """
            Handle Esc/Ctrl release
            @param window as Window
            @param event as Gdk.EventKey
        """
        if event.keyval == Gdk.KEY_Control_L:
            self.__container.ctrl_released()
        elif event.keyval == Gdk.KEY_Escape:
            self.__container.set_expose(False)
            if self.__container.current is not None and\
                    self.__container.current.reading:
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
            App().quit(True)
        elif string == "new_page":
            self.container.add_webview_for_uri(App().start_page,
                                               LoadingType.FOREGROUND)
            self.toolbar.title.start_search()
        elif string == "close_page":
            if self.is_fullscreen:
                self.container.current.webview.emit("leave-fullscreen")
                Gtk.ApplicationWindow.unfullscreen(self)
            self.__container.try_close_view(self.container.current)
        elif string == "reload":
            self.container.current.webview.reload()
        elif string == "settings":
            # Rework all this code to use actions like in Lollypop
            from eolie.settings import SettingsDialog
            dialog = SettingsDialog(self)
            dialog.show()
        elif string == "home":
            self.container.current.webview.load_uri(App().start_page)
        elif string == "source":
            uri = self.container.current.webview.uri
            task_helper = TaskHelper()
            task_helper.load_uri_content(uri, None, self.__on_source_loaded)
        elif string == "find":
            find_widget = self.container.current.find_widget
            find_widget.set_search_mode(True)
            find_widget.search()
        elif string == "backward":
            self.toolbar.actions.backward()
        elif string == "forward":
            self.toolbar.actions.forward()
        elif string == "previous":
            self.__container.previous()
        elif string == "next":
            self.__container.next()
        elif string == "previous_site":
            self.__container.sites_manager.previous()
        elif string == "next_site":
            self.__container.sites_manager.next()
        elif string == "print":
            self.container.current.webview.print()
        elif string == "private":
            self.container.add_webview(App().start_page,
                                       LoadingType.FOREGROUND,
                                       True)
        elif string == "last_page":
            App().pages_menu.activate_last_action()
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
        elif string == "save":
            self.toolbar.end.save_page()
        elif string == "expose":
            active = self.toolbar.actions.view_button.get_active()
            self.toolbar.actions.view_button.set_active(not active)
        elif string == "jsblock":
            pass
        elif string == "show_sidebar":
            value = App().settings.get_value("show-sidebar")
            App().settings.set_value("show-sidebar",
                                     GLib.Variant("b", not value))
        elif string == "mse_enabled":
            self.container.current.webview.set_setting("enable-mediasource",
                                                       True)
            self.container.current.webview.reload()

    def __on_js_enabled(self, proxy, task, webview):
        """
            Reload page
            @param proxy as Gio.DBusProxy
            @param task as Gio.Task
            @param webview as WebView
        """
        webview.reload()

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
