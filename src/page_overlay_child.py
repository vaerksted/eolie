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

from gi.repository import Gtk, GLib

from eolie.pages_manager_flowbox_child import PagesManagerFlowBoxChild


class PageOverlayChild(Gtk.EventBox):
    """
        A movable PagesManagerFlowBoxChild
    """

    def __init__(self, view, window):
        """
            Init child
            @param view as View
            @param window as Window
        """
        Gtk.EventBox.__init__(self)
        self.__window = window
        self.__view = view
        self.__press = False
        self.__moved = False
        self.__x_root = 0
        self.__child = PagesManagerFlowBoxChild(view, window)
        self.__child.get_style_context().add_class("box-dark-shadow")
        self.__child.show()
        self.connect("button-press-event", self.__on_button_press_event)
        self.connect("button-release-event", self.__on_button_release_event)
        self.connect("motion-notify-event", self.__on_motion_notify_event)
        self.add(self.__child)
        self.set_property("halign", Gtk.Align.START)
        self.set_property("valign", Gtk.Align.END)
        self.show()
        self.__timeout_id = GLib.timeout_add(15000, self.__hide_timeout)

    def set_view(self, view):
        """
            Set a new view
            @param view as View
        """
        self.__view = view
        if self.__timeout_id is not None:
            GLib.source_remove(self.__timeout_id)
        self.__child.set_view(view)
        self.__child.update()
        self.__timeout_id = GLib.timeout_add(15000, self.__hide_timeout)
        self.__moved = False
        self.show()

#######################
# PROTECTED           #
#######################

#######################
# PRIVATE             #
#######################
    def __hide_timeout(self):
        """
            Hide by opacity change
            @param count as int
        """
        if self.__view.webview.is_loading():
            return True
        else:
            self.hide()
            self.__timeout_id = None

    def __on_button_press_event(self, evenbox, event):
        """
            Mark as pressed
            @param eventbox as Gtk.EventBox
            @param event as Gdk.EventButton
        """
        if event.button == 1:
            self.__press = True
            self.__x_root = event.x_root
        else:
            self.__press = False

    def __on_button_release_event(self, evenbox, event):
        """
            Unmark as pressed
            @param eventbox as Gtk.EventBox
            @param event as Gdk.EventButton
        """
        if not self.__moved:
            self.hide()
            if self.__timeout_id is not None:
                GLib.source_remove(self.__timeout_id)
                self.__timeout_id = None
            self.__window.container.set_visible_view(self.__view)
            self.__window.container.set_expose(False)
            self.__window.container.pages_manager.update_visible_child()
        self.__press = False

    def __on_motion_notify_event(self, eventbox, event):
        """
            Move widget
            @param eventbox as Gtk.EventBox
            @param event as Gdk.EventMotion
        """
        if self.__press:
            if event.x_root > self.__x_root:
                self.set_property("halign", Gtk.Align.END)
            else:
                self.set_property("halign", Gtk.Align.START)
            self.__x_root = event.x_root
            self.__moved = True
