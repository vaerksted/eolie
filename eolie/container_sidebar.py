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

from eolie.sites_manager import SitesManager
from eolie.define import App


class SidebarContainer:
    """
        Sidebar management for container
    """

    def __init__(self):
        """
            Init container
        """
        self.__sites_manager = SitesManager(self._window)
        if App().settings.get_value("show-sidebar"):
            self.__sites_manager.show()
        App().settings.connect("changed::show-sidebar",
                               self.__on_show_sidebar_changed)

    @property
    def sites_manager(self):
        """
            Get sites manager
            @return SitesManager
        """
        return self.__sites_manager

#######################
# PRIVATE             #
#######################

    def __on_show_sidebar_changed(self, settings, value):
        """
            Show/hide panel
            @param settings as Gio.Settings
            @param value as bool
        """
        if App().settings.get_value("show-sidebar"):
            self.__sites_manager.show()
        else:
            self.__sites_manager.hide()
