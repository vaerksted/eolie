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

from gi.repository import Gtk, GLib

from eolie.pages_manager import PagesManager
from eolie.define import App


class ExposeContainer:
    """
        Expose management for container
    """

    def __init__(self):
        """
            Init container
        """
        self.__next_timeout_id = None
        self.__previous_timeout_id = None
        self.__expose_stack = Gtk.Stack()
        self.__expose_stack.set_hexpand(True)
        self.__expose_stack.set_vexpand(True)
        self.__expose_stack.set_transition_type(
            Gtk.StackTransitionType.CROSSFADE)
        self.__expose_stack.set_transition_duration(150)
        self.__expose_stack.show()
        self.__pages_manager = PagesManager(self._window)
        self.__pages_manager.show()
        self._paned.add2(self.__expose_stack)
        self.__expose_stack.add_named(self._stack, "stack")
        self.__expose_stack.add_named(self.__pages_manager, "expose")

    def set_expose(self, expose):
        """
            Show current views
            @param expose as bool
        """
        if expose:
            self.__pages_manager.update_sort(self.sites_manager.sort)
            self.__pages_manager.set_filtered(True)
        else:
            self._window.toolbar.actions.view_button.set_active(False)
            self._window.container.pages_manager.set_filter("")
            self.__pages_manager.set_filtered(False)
        self.__set_expose(expose)

    def set_current(self, view, switch=False):
        """
            Set visible view
            @param view as View
            @param switch as bool
        """
        self._current = view
        self.pages_manager.update_visible_child()
        self.sites_manager.update_visible_child()
        if switch:
            self._stack.set_visible_child(view)

    def try_close_view(self, view):
        """
            Ask user before closing view if forms filled
            @param view as View
        """
        page_id = view.webview.get_page_id()
        App().helper.call("FormsFilled", page_id, None,
                          self.__on_forms_filled, view)

    def next(self):
        """
            Show next view
        """
        if self.__next_timeout_id is None and\
                self.__next_timeout_id != -1:
            self.__next_timeout_id = GLib.timeout_add(
                100,
                self.__on_prev_next_timeout,
                self.__pages_manager.next)
        else:
            self.__pages_manager.next()

    def previous(self):
        """
            Show next view
        """
        if self.__previous_timeout_id is None and\
                self.__previous_timeout_id != -1:
            self.__previous_timeout_id = GLib.timeout_add(
                100,
                self.__on_prev_next_timeout,
                self.__pages_manager.previous)
        else:
            self.__pages_manager.previous()

    def ctrl_released(self):
        """
            Disable any pending expose
        """
        if self.__next_timeout_id is not None:
            if self.__next_timeout_id != -1:
                self.pages_manager.next()
                GLib.source_remove(self.__next_timeout_id)
        if self.__previous_timeout_id is not None:
            if self.__previous_timeout_id != -1:
                self.pages_manager.previous()
                GLib.source_remove(self.__previous_timeout_id)

        self.__next_timeout_id = None
        self.__previous_timeout_id = None
        self.set_expose(False)

    @property
    def in_expose(self):
        """
            True if in expose mode
            @return bool
        """
        return self.__expose_stack.get_visible_child_name() == "expose"

    @property
    def pages_manager(self):
        """
            Get pages manager
            @return PagesManager
        """
        return self.__pages_manager

    @property
    def views(self):
        """
            Get views
            @return views as [View]
        """
        return self._stack.get_children()

    @property
    def current(self):
        """
            Current view
            @return WebView
        """
        return self._current

#######################
# PRIVATE             #
#######################
    def __on_prev_next_timeout(self, callback):
        """
            Set expose on and call callback
            @param callback as __next()/__previous()
        """
        self.__next_timeout_id = -1
        self.__previous_timeout_id = -1
        if not self.in_expose:
            self.__set_expose(True)
        callback()

    def __set_expose(self, expose):
        """
            Show current views
            @param expose as bool
            @param search as bool
        """
        # Show expose mode
        if expose:
            self.__expose_stack.set_visible_child_name("expose")
        else:
            if self._stack.get_visible_child() != self._current:
                self._stack.set_visible_child(self._current)
            self.__expose_stack.set_visible_child_name("stack")
            self.__pages_manager.update_visible_child()
