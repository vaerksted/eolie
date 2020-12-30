# Copyright (c) 2017-2020 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from gi.repository import Handy

from eolie.toolbar_actions import ToolbarActions
from eolie.toolbar_title import ToolbarTitle
from eolie.toolbar_end import ToolbarEnd
from eolie.helper_gestures import GesturesHelper


class Toolbar(Handy.HeaderBar):
    """
        Eolie toolbar
    """

    def __init__(self, window, fullscreen=False):
        """
            Init toolbar
            @param window as Window
            @param fullscreen as bool
        """
        Handy.HeaderBar.__init__(self)
        self.__window = window
        self.set_title("Eolie")
        self.__toolbar_actions = ToolbarActions(window, fullscreen)
        self.__toolbar_actions.show()
        self.__toolbar_title = ToolbarTitle(window)
        self.__toolbar_title.show()
        self.__toolbar_end = ToolbarEnd(window, fullscreen)
        self.__toolbar_end.show()
        self.pack_start(self.__toolbar_actions)
        self.set_custom_title(self.__toolbar_title)
        self.pack_end(self.__toolbar_end)
        self.__gesture = GesturesHelper(
            self,
            primary_press_callback=self.__on_press)

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
    def __on_press(self, x, y, event):
        """
            Hide popovers
            @param x as int
            @param y as int
            @param event as Gdk.Event
        """
        self.__window.close_popovers()
