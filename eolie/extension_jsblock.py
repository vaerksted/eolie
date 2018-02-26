# Copyright (c) 2017-2018 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from eolie.define import App
from eolie.logger import Logger


class JSblockExtension:
    """
        Handle jsblocking
    """

    def __init__(self, extension):
        """
            Connect wanted signal
            @param extension as WebKit2WebExtension
        """
        self.__webpage = None
        self.__document = None
        self.__scripts = None
        self.__whitelist = []
        extension.connect("page-created", self.__on_page_created)

    def enable_for(self, netloc):
        """
            Enable JS for netloc
            @param netloc as str
        """
        self.__whitelist.append(netloc)

    @property
    def scripts(self):
        """
            Get available scripts
            @return str
        """
        script_uris = []
        if self.__scripts is None or self.__webpage is None:
            return []
        uri = self.__webpage.get_uri()
        parsed = urlparse(uri)
        netloc = parsed.netloc.split(".")[-2:]
        for i in range(0, self.__scripts.get_length()):
            script = self.__scripts.item(i)
            script_uri = script.get_src()
            if script_uri is not None:
                parsed_script = urlparse(script_uri)
                netloc_script = parsed_script.netloc.split(".")[-2:]
                if netloc == netloc_script and\
                        App().settings.get_value("trust-websites-js"):
                    continue
                if parsed_script.netloc and\
                        parsed_script.netloc not in script_uris:
                    script_uris.append(parsed_script.netloc)
        return script_uris

#######################
# PRIVATE             #
#######################
    def __on_page_created(self, extension, webpage):
        """
            Connect to document loaded signal
            @param extension as WebKit2WebExtension
            @param webpage as WebKit2WebExtension.WebPage
        """
        self.__webpage = webpage
        webpage.connect("send-request", self.__on_send_request)

    def __on_send_request(self, webpage, request, redirect):
        """
            Filter based on adblock db
            @param webpage as WebKit2WebExtension.WebPage
            @param request as WebKit2.URIRequest
            @param redirect as WebKit2WebExtension.URIResponse
        """
        uri = webpage.get_uri()
        parsed = urlparse(uri)
        request_uri = request.get_uri()
        parsed_request = urlparse(request_uri)
        netloc = parsed.netloc.split(".")[-2:]
        netloc_request = parsed_request.netloc.split(".")[-2:]
        document = webpage.get_dom_document()
        if self.__document != document:
            self.__document = document
            self.__scripts = \
                document.get_elements_by_tag_name_as_html_collection("script")
        if netloc == netloc_request and\
                App().settings.get_value("trust-websites-js"):
            return False
        if App().settings.get_value("jsblock") and\
                parsed.netloc not in self.__whitelist:
            if parsed_request.scheme in ["http", "https"] and\
                    not App().js_exceptions.find(parsed_request.netloc,
                                                 parsed.netloc):
                for i in range(0, self.__scripts.get_length()):
                    script = self.__scripts.item(i)
                    if script.get_src() == request_uri:
                        Logger.debug("JSblockExtension: blocking %s -> %s",
                                     request_uri, uri)
                        return True
