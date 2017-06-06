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

from gi.repository import Gio

from eolie.define import PROXY_BUS, PROXY_PATH, PROXY_INTERFACE


class DBusHelper:
    """
        Simpler helper for DBus
    """

    def __init__(self):
        pass

    def call(self, call, args, callback, data, page_id):
        """
            Call function
            @param call as str
            @param args as GLib.Variant()/None
            @param callback as function
            @param data
            @param page_id as int
        """
        try:
            Gio.bus_get(Gio.BusType.SESSION, None,
                        self.__on_get_bus, call,
                        args,
                        callback, data, page_id)
        except Exception as e:
            print("DBusHelper::call():", e)

    def connect(self, signal_name, callback, page_id):
        """
            Connect callback to object signals
            @param signal_name as str
            @param callback as function
            @param page_id as int
        """
        try:
            Gio.bus_get(Gio.BusType.SESSION, None,
                        self.__on_get_bus, None,
                        None,
                        callback, signal_name, page_id)
        except Exception as e:
            print("DBusHelper::connect():", e)

#######################
# PRIVATE             #
#######################
    def __on_get_bus(self, source, result, call,
                     args, callback, data, page_id):
        """
            Get DBus proxy
            @param source as GObject.Object
            @param result as Gio.AsyncResult
            @param call as str
            @param args as GLib.Variant()/None
            @param callback as function
            @param data
            @param page_id as int
        """
        proxy_bus = PROXY_BUS % page_id
        bus = Gio.bus_get_finish(result)
        if call is None:
            bus.signal_subscribe(None, proxy_bus, data,
                                 PROXY_PATH, None,
                                 Gio.DBusSignalFlags.NONE,
                                 callback, None)
        else:
            Gio.DBusProxy.new(bus, Gio.DBusProxyFlags.NONE, None,
                              proxy_bus,
                              PROXY_PATH,
                              PROXY_INTERFACE, None,
                              self.__on_get_proxy, call, args, callback, data)

    def __on_get_proxy(self, source, result, call, args, callback, data):
        """
            Launch call and connect it to callback
            @param source as GObject.Object
            @param result as Gio.AsyncResult
            @param call as str
            @param args as GLib.Variant()/None
            @param callback as function
            @param data
        """
        try:
            proxy = source.new_finish(result)
            proxy.call(call, args, Gio.DBusCallFlags.NO_AUTO_START,
                       500, None, callback, data)
        except Exception as e:
            print("DBusHelper::__on_get_proxy():", e)
