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

from gi.repository import Gtk

from eolie.widget_find import FindWidget
from eolie.widget_uri_label import UriLabelWidget


class OverlayContainer:
    """
        Overlay management for container
    """

    def __init__(self):
        """
            Init container
        """
        grid = Gtk.Grid.new()
        grid.show()
        grid.set_orientation(Gtk.Orientation.VERTICAL)
        self.__find_widget = FindWidget(self._window)
        self.__find_widget.show()
        self._uri_label = UriLabelWidget()
        self.__overlay = Gtk.Overlay.new()
        self.__overlay.show()
        self.__overlay.add_overlay(self._uri_label)
        grid.add(self.__find_widget)
        grid.add(self.__overlay)
        self.add2(grid)

    @property
    def overlay(self):
        """
            Get overlay
            @return Gtk.Overlay
        """
        return self.__overlay

    @property
    def find_widget(self):
        """
            Get find widget
            @return FindWidget
        """
        return self.__find_widget

#######################
# PRIVATE             #
#######################
