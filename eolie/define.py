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

from gi.repository import Gio, GLib

App = Gio.Application.get_default

PROXY_BUS = 'org.gnome.Eolie.Proxy.Page%s'
PROXY_PATH = '/org/gnome/EolieProxy'
PROXY_INTERFACE = 'org.gnome.Eolie.Proxy'

# Setup common paths
EOLIE_DATA_PATH = GLib.get_user_data_dir() + "/eolie"
EOLIE_CACHE_PATH = GLib.get_user_cache_dir() + "/eolie"

COOKIES_PATH = "%s/cookies_%s.db"

ADBLOCK_URIS = ["https://easylist-downloads.adblockplus.org/" +
                "easylist_content_blocker.json"]

PHISHING_URI = "https://raw.githubusercontent.com/bellegarde-c/" +\
    "webkit-blocker-phishing/master/phishing.json"

MARGIN = 15
MARGIN_SMALL = 5


class TimeSpan:
    HOUR = "0"
    DAY = "1"
    WEEK = "2"
    FOUR_WEEK = "3"
    YEAR = "4"
    FOREVER = "5"
    NEVER = "6"
    CUSTOM = "7"


TimeSpanValues = {
    TimeSpan.HOUR: GLib.TIME_SPAN_HOUR,
    TimeSpan.DAY: GLib.TIME_SPAN_DAY,
    TimeSpan.WEEK: GLib.TIME_SPAN_DAY * 7,
    TimeSpan.FOUR_WEEK: GLib.TIME_SPAN_DAY * 7 * 4,
    TimeSpan.YEAR: GLib.TIME_SPAN_DAY * 365,
    TimeSpan.FOREVER: 0
}


class ArtSize:
    FAVICON_MIN = 16
    FAVICON = 22
    PREVIEW_WIDTH = 192
    PREVIEW_HEIGHT = 60
    START_WIDTH = 300
    START_HEIGHT = 200


class Indicator:
    NONE = 0
    GEOLOCATION = 1


class LoadingType:
    FOREGROUND = 0
    BACKGROUND = 1
    OFFLOAD = 2
    POPOVER = 3


class Type:
    NONE = -1
    POPULARS = -2
    RECENTS = -3
    BOOKMARK = -4
    SUGGESTION = -5
    HISTORY = -6
    SEARCH = -7
    TAG = -8
    UNCLASSIFIED = -9
    WEBVIEW = -10
    SEPARATOR = -11
