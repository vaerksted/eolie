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
from eolie.define import PHISHING_URI, App
from eolie.logger import Logger


class PhishingContentBlocker(ContentBlocker):
    """
        A WebKit Content Blocker for phishing
    """

    def __init__(self):
        """
            Init adblock helper
        """
        try:
            ContentBlocker.__init__(self, "block-phishing")
            if App().settings.get_value("block-phishing"):
                self.__download_uri(PHISHING_URI)
        except Exception as e:
            Logger.error("PhishingContentBlocker::__init__(): %s", e)

#######################
# PRIVATE             #
#######################
    def __download_uri(self, uri):
        """
            Update database from the web
            @param uris as [str]
            @param data as []
        """
        if not Gio.NetworkMonitor.get_default().get_network_available():
            return
        self._task_helper.load_uri_content(uri,
                                           self._cancellable,
                                           self.__on_load_uri_content)

    def __on_load_uri_content(self, uri, status, content):
        """
            Save loaded values
            @param uri as str
            @param status as bool
            @param content as bytes
        """
        try:
            Logger.debug(
                "PhishingContentBlocker::__on_load_uri_content(): %s", uri)
            if status:
                rules = json.loads(content.decode("utf-8"))
                # Save to sources
                f = Gio.File.new_for_path(
                    "%s/block-phishing.json" % self._JSON_PATH)
                content = json.dumps(rules).encode("utf-8")
                f.replace_contents(content,
                                   None,
                                   False,
                                   Gio.FileCreateFlags.REPLACE_DESTINATION,
                                   None)
                self._task_helper.run(self._save_rules, rules)
        except Exception as e:
            Logger.error(
                "PhishingContentBlocker::__on_load_uri_content(): %s", e)
