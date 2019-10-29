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

import json

from eolie.content_blocker import ContentBlocker
from eolie.logger import Logger


class ImagesContentBlocker(ContentBlocker):
    """
        A WebKit Content Blocker for images
    """

    DEFAULT = [
        {
            "trigger": {
                "url-filter": ".*",
                "resource-type": ["image"]
            },
            "action": {
                "type": "block"
            }
        }
    ]

    def __init__(self):
        """
            Init adblock helper
        """
        try:
            ContentBlocker.__init__(self, "block-images")
            rules = self.DEFAULT + self.exceptions.rules
            bytes = json.dumps(rules).encode("utf-8")
            self.save(bytes)
        except Exception as e:
            Logger.error("PopupsContentBlocker::__init__(): %s", e)
