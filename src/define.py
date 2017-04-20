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

from gi.repository import Gio, GLib

El = Gio.Application.get_default

PROXY_BUS = 'org.gnome.Eolie.Proxy'
PROXY_PATH = '/org/gnome/EolieProxy'


# Setup common paths
if GLib.getenv("XDG_DATA_HOME") is None:
    LOCAL_PATH = GLib.get_home_dir() + "/.local/share"
else:
    LOCAL_PATH = GLib.getenv("XDG_DATA_HOME")

EOLIE_LOCAL_PATH = LOCAL_PATH + "/eolie"

if GLib.getenv("XDG_CONFIG_HOME") is None:
    CONFIG_PATH = GLib.get_home_dir() + "/.config"
else:
    CONFIG_PATH = GLib.getenv("XDG_CONFIG_HOME")


class TimeSpan:
    HOUR = "0"
    DAY = "1"
    WEEK = "2"
    FOUR_WEEK = "3"
    FOREVER = "4"
    CUSTOM = "5"


TimeSpanValues = {
    TimeSpan.HOUR: GLib.TIME_SPAN_HOUR,
    TimeSpan.DAY: GLib.TIME_SPAN_DAY,
    TimeSpan.WEEK: GLib.TIME_SPAN_DAY * 7,
    TimeSpan.FOUR_WEEK: GLib.TIME_SPAN_DAY * 7 * 4,
    TimeSpan.FOREVER: 0
}


class ArtSize:
    FAVICON = 22
    PREVIEW_HEIGHT = 60
    PREVIEW_WIDTH_MARGIN = 10
    START_WIDTH = 300
    START_HEIGHT = 200


class Type:
    NONE = -1
    POPULARS = -2
    RECENTS = -3
    BOOKMARK = -4
    KEYWORDS = -5
    HISTORY = -6
    SEARCH = -7
    TAG = -8
    SEPARATOR = -9


LOGINS = ["login", "username", "user", "mail", "email"]
