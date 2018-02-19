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

from gi.repository import Gtk

from eolie.toolbar_actions import ToolbarActions
from eolie.toolbar_title import ToolbarTitle
from eolie.toolbar_end import ToolbarEnd


class Toolbar(Gtk.EventBox):
    """
        Eolie toolbar
    """

    def __init__(self, window, fullscreen=False):
        """
            Init toolbar
            @param window as Window
            @param fullscreen as bool
        """
        Gtk.EventBox.__init__(self)
        self.__window = window
        self.__headerbar = Gtk.HeaderBar()
        self.__headerbar.show()
        self.__headerbar.set_title("Eolie")
        self.__toolbar_actions = ToolbarActions(window, fullscreen)
        self.__toolbar_actions.show()
        self.__toolbar_title = ToolbarTitle(window)
        self.__toolbar_title.show()
        self.__toolbar_end = ToolbarEnd(window, fullscreen)
        self.__toolbar_end.show()
        self.__headerbar.pack_start(self.__toolbar_actions)
        self.__headerbar.set_custom_title(self.__toolbar_title)
        self.__headerbar.pack_end(self.__toolbar_end)
        self.connect("button-press-event", self.__on_button_press)
        self.add(self.__headerbar)

    @property
    def headerbar(self):
        """
            Get headerbar
            @return Gtk.HeaderBar
        """
        return self.__headerbar

    @property
    def title(self):
        """
            Toolbar title
            @return ToolbarTitle
        """
        return self.__toolbar_title

    @property
    def end(self):
        """
            Toolbar end
            @return ToolbarEnd
        """
        return self.__toolbar_end

    @property
    def actions(self):
        """
            Toolbar actions
            @return ToolbarActions
        """
        return self.__toolbar_actions

#######################
# PRIVATE             #
#######################
    def __on_button_press(self, widget, event):
        """
            Hide popover if visible
            @param widget as Gtk.Widget
            @param event as Gdk.Event
        """
        self.__window.close_popovers()
