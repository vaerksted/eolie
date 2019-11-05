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
        Gtk.Overlay.__init__(self)
        self.__find_widget = FindWidget(self._window)
        self.__find_widget.show()
        self.__uri_label = UriLabelWidget()
        self._overlay = Gtk.Overlay.new()
        self._overlay.show()
        self._overlay.add_overlay(self.__uri_label)

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
