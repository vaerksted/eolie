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

from gi.repository import Gio

import json

from eolie.content_blocker import ContentBlocker
from eolie.content_blocker_ad_exceptions import AdContentBlockerExceptions
from eolie.define import ADBLOCK_URIS
from eolie.logger import Logger


class AdContentBlocker(ContentBlocker):
    """
        A WebKit Content Blocker for ads
    """

    def __init__(self):
        """
            Init adblock helper
        """
        try:
            ContentBlocker.__init__(self, "adblock")
            self._exceptions = AdContentBlockerExceptions()
            self.__download_uris(list(ADBLOCK_URIS))
        except Exception as e:
            Logger.error("AdContentBlocker::__init__(): %s", e)

#######################
# PRIVATE             #
#######################
    def __download_uris(self, uris, rules=[]):
        """
            Update database from the web
            @param uris as [str]
            @param data as []
        """
        if not Gio.NetworkMonitor.get_default().get_network_available():
            return
        if uris:
            uri = uris.pop(0)
            self._task_helper.load_uri_content(uri,
                                               self._cancellable,
                                               self.__on_load_uri_content,
                                               uris,
                                               rules)

    def __on_load_uri_content(self, uri, status, content, uris, rules):
        """
            Save loaded values
            @param uri as str
            @param status as bool
            @param content as bytes
            @param uris as [str]
            @param rules as []
        """
        try:
            Logger.debug("AdContentBlocker::__on_load_uri_content(): %s", uri)
            if status:
                rules += json.loads(content.decode("utf-8"))
            if uris:
                self.__download_uris(uris, rules)
            else:
                # Save to sources
                f = Gio.File.new_for_path("%s/adblock.json" % self._JSON_PATH)
                content = json.dumps(rules).encode("utf-8")
                f.replace_contents(content,
                                   None,
                                   False,
                                   Gio.FileCreateFlags.REPLACE_DESTINATION,
                                   None)
                self._task_helper.run(self._save_rules, rules)
        except Exception as e:
            Logger.error("AdContentBlocker::__on_load_uri_content(): %s", e)

    def __on_adblock_changed(self, settings, value):
        """
            Enable disable filtering
            @param settings as Gio.Settings
            @param value as GLib.Variant
        """
        adblock = self.settings.get_value("adblock")
        if adblock:
            self.load()
        else:
            self.save(b"")
