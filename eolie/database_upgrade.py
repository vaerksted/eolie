# Copyright (c) 2014-2018 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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
from eolie.define import Type


class DatabaseUpgrade:
    """
        Manage database schema upgrades
    """

    def __init__(self, t):
        """
            Init object
            @param t as Type
        """
        # Here are schema upgrade, key is database version,
        # value is sql request
        if t == Type.BOOKMARK:
            self.__UPGRADES = {
            }
        elif t == Type.HISTORY:
            self.__UPGRADES = {
                1: "ALTER TABLE history ADD opened INT NOT NULL DEFAULT 0",
                2: "ALTER TABLE history ADD netloc TEXT NOT NULL DEFAULT ''",
                3: "DELETE FROM history WHERE popularity=0",
                4: "DELETE FROM history_atime WHERE NOT EXISTS (SELECT * FROM\
                    history WHERE history.rowid=history_atime.history_id)",
            }

    def upgrade(self, db):
        """
            Upgrade db
            @param db as Database
        """
        version = 0
        with SqlCursor(db) as sql:
            result = sql.execute("PRAGMA user_version")
            v = result.fetchone()
            if v is not None:
                version = v[0]
            if version < self.version:
                for i in range(version + 1, self.version + 1):
                    try:
                        if isinstance(self.__UPGRADES[i], str):
                            sql.execute(self.__UPGRADES[i])
                        else:
                            self.__UPGRADES[i](db)
                    except Exception as e:
                        print("History DB upgrade %s failed: %s" % (i, e))
                sql.execute("PRAGMA user_version=%s" % self.version)

    @property
    def version(self):
        """
            Current wanted version
        """
        return len(self.__UPGRADES)

#######################
# PRIVATE             #
#######################
