# Copyright (c) 2017 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
# Copyright (c) 2015 Jean-Philippe Braun <eon@patapon.info>
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

from threading import current_thread
from time import sleep

from eolie.define import El


class SqlCursor:
    """
        Context manager to get the SQL cursor
    """
    def add(obj):
        """
            Add cursor to thread list
            Raise an exception if cursor already exists
        """
        obj.thread_lock.acquire()
        name = current_thread().getName() + obj.__class__.__name__
        El().cursors[name] = obj.get_cursor()

    def remove(obj):
        """
            Remove cursor from thread list and commit
            Raise an exception if cursor already exists
        """
        name = current_thread().getName() + obj.__class__.__name__
        El().cursors[name].commit()
        El().cursors[name].close()
        del El().cursors[name]
        obj.thread_lock.release()

    def commit(obj):
        """
            Commit current obj
        """
        name = current_thread().getName() + obj.__class__.__name__
        El().cursors[name].commit()
        # Flush pending tasks
        obj.thread_lock.release()
        sleep(1)
        obj.thread_lock.acquire()

    def __init__(self, obj):
        """
            Init object
        """
        self.__obj = obj
        self.__creator = False

    def __enter__(self):
        """
            Return cursor for thread, create a new one if needed
        """
        name = current_thread().getName() + self.__obj.__class__.__name__
        if name not in El().cursors:
            self.__obj.thread_lock.acquire()
            self.__creator = True
            El().cursors[name] = self.__obj.get_cursor()
        return El().cursors[name]

    def __exit__(self, type, value, traceback):
        """
            If creator, close cursor and remove it
        """
        if self.__creator:
            name = current_thread().getName() + self.__obj.__class__.__name__
            El().cursors[name].commit()
            El().cursors[name].close()
            del El().cursors[name]
            self.__obj.thread_lock.release()
