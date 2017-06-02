# Copyright (c) 2014-2017 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from eolie.sqlcursor import SqlCursor
from eolie.define import El


class DatabaseUpgrade:
    """
        Manage database schema upgrades
    """

    def __init__(self, version):
        """
            Init object
            @param version as int
        """
        self._version = version
        self._UPGRADES = {
            1: self.__upgrade_1,
        }

    def do_db_upgrade(self):
        """
            Upgrade database based on version
            @return new db version as int
        """
        for i in range(self._version+1, len(self._UPGRADES)+1):
            self._UPGRADES[i]()
        return len(self._UPGRADES)

#######################
# PRIVATE             #
#######################
    def __upgrade_1(self):
        """
            Add a sorted field to artists
        """
        with SqlCursor(El().history) as sql:
            try:
                sql.execute("ALTER TABLE history ADD"
                            " opened INT NOT NULL DEFAULT 0")
                sql.commit()
            except:
                pass
