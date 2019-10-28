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

import json

from eolie.define import EOLIE_DATA_PATH
from eolie.logger import Logger


class AdblockExceptions:
    """
        Eolie adblock exception constructor
    """
    __JSON_PATH = "%s/adblock_sources" % EOLIE_DATA_PATH

    def __init__(self):
        """
            Init constructor
        """
        try:
            self.__rules = []
            f = Gio.File.new_for_path("%s/exceptions.json" % self.__JSON_PATH)
            if f.query_exists():
                (status, contents, tag) = f.load_contents(None)
                if status:
                    self.__rules = json.loads(contents.decode("utf-8"))
        except Exception as e:
            Logger.error("AdblockExceptions::__init__(): %s", e)

    def save(self):
        """
            Save rules to disk
        """
        try:
            f = Gio.File.new_for_path("%s/exceptions.json" % self.__JSON_PATH)
            content = json.dumps(self.__rules)
            f.replace_contents(content.encode("utf-8"),
                               None,
                               False,
                               Gio.FileCreateFlags.REPLACE_DESTINATION,
                               None)
        except Exception as e:
            Logger.error("AdblockExceptions::save(): %s", e)

    def add_domain_exception(self, domain):
        """
            Add an exception for domain
            @param domain as str
        """
        rule = self.__get_rule_for_domain(domain)
        self.__rules.append(rule)

    def remove_domain_exception(self, domain):
        """
            Remove an exception for domain
            @param domain as str
        """
        rule = self.__get_rule_for_domain(domain)
        if rule in self.__rules:
            self.__rules.remove(rule)

    def is_domain_exception(self, domain):
        """
            True if domain exception exists
        """
        rule = self.__get_rule_for_domain(domain)
        return rule in self.__rules

    @property
    def rules(self):
        """
            Get rules
            @return []
        """
        return self.__rules

#######################
# PRIVATE             #
#######################
    def __get_rule_for_domain(self, domain):
        """
            Return rule for domain
            @param domain as str
            @return {}
        """
        return {
            "trigger": {
                "url-filter": ".*",
                "if-domain": [domain]
            },
            "action": {
                "type": "ignore-previous-rules"
            }
        }
