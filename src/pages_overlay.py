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
from eolie.pages_manager_flowbox import PagesManagerFlowBox


class PagesManagerFlowBoxCustom(PagesManagerFlowBox):
    """
        Flow box linked to a Gtk.Stack
    """

    def __init__(self, window):
        """
            Init stack
            @param window as Window
        """
        PagesManagerFlowBox.__init__(self, window)
        self._box.set_max_children_per_line(1000)
        self._box.set_min_children_per_line(1000)
        self.get_style_context().add_class("no-background")
        self.get_style_context().add_class("no-border")
        self._scrolled.set_policy(Gtk.PolicyType.AUTOMATIC,
                                  Gtk.PolicyType.NEVER)

    def add_child(self, child):
        """
            Add child to flowbox
            @param view as View
        """
        self._box.insert(child, 0)

    def show_next(self):
        """
            Show next page
        """
        for child in self._box.get_children():
            child.show()

    def hide_next(self):
        """
            Hide next page
        """
        first = True
        for child in self._box.get_children():
            if first:
                first = False
            else:
                child.hide()

    @property
    def children(self):
        """
            Get children
            @return [PagesManagerFlowBoxChild]
        """
        return self._box.get_children()

#######################
# PROTECTED           #
#######################
    def _on_child_activated(self, listbox, row):
        """
            Show wanted web view
            @param listbox as Gtk.ListBox
            @param row as PagesManagerFlowBoxChild
        """
        self._window.container.set_visible_view(row.view)
        self._window.container.set_expose(False)
        GLib.idle_add(row.destroy)


class PagesOverlay(Gtk.EventBox):
    """
        Flow box linked to a Gtk.Stack
    """

    def __init__(self, window):
        """
            Init stack
            @param window as Window
        """
        Gtk.EventBox.__init__(self)
        self.__timeout_id = None
        self.__window = window
        self.get_style_context().add_class("no-background")
        self.set_property("halign", Gtk.Align.FILL)
        self.set_property("valign", Gtk.Align.END)

        self.__pages_manager = PagesManagerFlowBoxCustom(window)
        self.__pages_manager.set_hexpand(True)

        # Allow keeping button while main overlay widget is hidden
        self.__fake = Gtk.Label.new(" ")
        self.__fake.set_property("width-request", 24)
        self.__fake.hide()

        self.__grid = Gtk.Grid()
        self.__grid.add(self.__pages_manager)
        self.__grid.add(self.__fake)
        self.__grid.show()

        overlay = Gtk.Overlay.new()
        overlay.add(self.__grid)
        overlay.show()

        button = Gtk.EventBox()
        button.set_opacity(0.7)
        button.set_property("halign", Gtk.Align.START)
        button.set_property("valign", Gtk.Align.START)
        button.get_style_context().add_class("close-button")
        button.connect("button-press-event",
                       self.__on_close_button_press_event)
        button.connect("enter-notify-event",
                       self.__on_close_enter_notify_event)
        button.connect("leave-notify-event",
                       self.__on_close_leave_notify_event)
        self.__image = Gtk.Image.new_from_icon_name("go-down-symbolic",
                                                    Gtk.IconSize.BUTTON)
        self.__image.set_margin_start(5)
        self.__image.set_margin_end(5)
        self.__image.set_margin_top(5)
        self.__image.set_margin_bottom(5)
        self.__image.show()
        button.add(self.__image)
        button.show()
        overlay.add_overlay(button)

        self.connect("enter-notify-event", self.__on_enter_notify_event)
        self.connect("leave-notify-event", self.__on_leave_notify_event)
        self.add(overlay)

    def add_child(self, view):
        """
            Add child to sidebar
            @param view as View
            @return child
        """
        child = PagesManagerFlowBoxChild(view, self.__window)
        child.get_style_context().add_class("box-dark-shadow")
        child.connect("destroy", self.__on_child_destroy)
        child.show()
        self.__pages_manager.add_child(child)
        self.__pages_manager.show()
        self.__pages_manager.hide_next()

    def destroy_child(self, view):
        """
            Destroy child associated with view if exists
            @param view as View
        """
        for child in self.__pages_manager.children:
            if child is None:
                continue
            if child.view == view:
                GLib.idle_add(child.destroy)
                return

#######################
# PROTECTED           #
#######################


#######################
# PRIVATE             #
#######################
    def __on_child_destroy(self, widget):
        """
            Hide self if empty
            @param widget as Gtk.Widget
        """
        if not self.__pages_manager.children:
            self.hide()
            self.__fake.hide()
            self.__pages_manager.hide()

    def __on_button_press_event(self, eventbox, event):
        """
            Show view and hide self
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        current = self.__grid.get_child_at(0, 0)
        if current is not None and event.button == 1:
            self.__window.container.set_visible_view(current.view)
            self.__window.container.set_expose(False)

    def __on_enter_notify_event(self, eventbox, event):
        """
            Reveal children
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        if self.__image.get_icon_name()[0] == "go-down-symbolic":
            self.__pages_manager.show_next()

    def __on_leave_notify_event(self, eventbox, event):
        """
            Unreveal children
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        if self.__image.get_icon_name()[0] == "go-down-symbolic":
            allocation = eventbox.get_allocation()
            if event.x <= 0 or\
               event.x >= allocation.width or\
               event.y <= 0 or\
               event.y >= allocation.height:
                self.__pages_manager.hide_next()

    def __on_close_button_press_event(self, eventbox, event):
        """
            Hide self
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        current = self.__grid.get_child_at(0, 0)
        if self.__image.get_icon_name()[0] == "go-down-symbolic":
            self.__fake.show()
            self.__pages_manager.hide()
            if current is not None:
                current.hide()
            self.__image.set_from_icon_name("go-up-symbolic",
                                            Gtk.IconSize.BUTTON)
        else:
            self.__fake.hide()
            self.__pages_manager.show()
            if current is not None:
                current.show()
            self.__image.set_from_icon_name("go-down-symbolic",
                                            Gtk.IconSize.BUTTON)
        return True

    def __on_close_enter_notify_event(self, eventbox, event):
        """
            Reveal children
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        eventbox.set_opacity(1)

    def __on_close_leave_notify_event(self, eventbox, event):
        """
            Unreveal children
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        eventbox.set_opacity(0.7)
