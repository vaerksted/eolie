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

from urllib.parse import urlparse

from eolie.settings import Settings
from eolie.database_adblock import DatabaseAdblock


class AdblockExtension:
    """
        Handle adblocking
    """

    def __init__(self, extension):
        """
            Connect wanted signal
            @param extension as WebKit2WebExtension
        """
        self.__settings = Settings.new()
        self.__adblock = DatabaseAdblock()
        extension.connect("page-created", self.__on_page_created)

#######################
# PRIVATE             #
#######################
    def __on_page_created(self, extension, webpage):
        """
            Connect to send request
            @param extension as WebKit2WebExtension
            @param webpage as WebKit2WebExtension.WebPage
        """
        webpage.connect("send-request", self.__on_send_request)

    def __on_send_request(self, webpage, request, redirect):
        """
            Filter based on adblock db
            @param webpage as WebKit2WebExtension.WebPage
            @param request as WebKit2.URIRequest
            @param redirect as WebKit2WebExtension.URIResponse
        """
        uri = request.get_uri()
        parsed = urlparse(webpage.get_uri())
        exception = self.__adblock.is_an_exception(parsed.netloc) or\
            self.__adblock.is_an_exception(parsed.netloc + parsed.path)
        if self.__settings.get_value("adblock") and\
                not exception and\
                self.__adblock.is_blocked(uri):
            return True
        return False
        # This code is not working, get_http_headers() kills page loading
        # if self.__settings.get_value("do-not-track"):
        #    headers = request.get_http_headers()
        #    if headers is not None:
        #        headers.append("DNT", "1")
