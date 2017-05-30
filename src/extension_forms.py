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

from eolie.define import LOGINS
from eolie.helper_passwords import PasswordsHelper


class FormsExtension:
    """
        Handle forms prefill
    """

    def __init__(self, extension, settings):
        """
            Connect wanted signal
            @param extension as WebKit2WebExtension
            @param settings as Settings
        """
        self.__helper = PasswordsHelper()
        self.__cache = {}
        self.__settings = settings
        extension.connect("page-created", self.__on_page_created)

    def get_forms(self, webpage):
        """
            Return forms for webpage
            @param webpage as WebKit2WebExtension.WebPage
        """
        uri = webpage.get_uri()
        # Return cached result if exists
        if uri in self.__cache.keys():
            return self.__cache[uri]
        inputs = webpage.get_dom_document().get_elements_by_tag_name('input')
        i = 0
        username_input = None
        password_input = None
        while i < inputs.get_length():
            name = inputs.item(i).get_attribute('name')
            if name is None:
                i += 1
                continue
            if password_input is None and\
                    inputs.item(i).get_input_type() == "password":
                password_input = inputs.item(i)
                i += 1
                continue
            if username_input is None and\
                    inputs.item(i).get_input_type() != "hidden":
                for search in LOGINS:
                    if name.lower().find(search) != -1:
                        username_input = inputs.item(i)
                        break
            i += 1
        # Cache result
        if username_input is not None and password_input is not None:
            self.__cache[uri] = (username_input, password_input)
        return (username_input, password_input)

#######################
# PRIVATE             #
#######################
    def __on_page_created(self, extension, webpage):
        """
            Connect to send request
            @param extension as WebKit2WebExtension
            @param webpage as WebKit2WebExtension.WebPage
        """
        webpage.connect("document-loaded", self.__on_document_loaded)

    def __on_document_loaded(self, webpage):
        """
            Restore forms
            @param webpage as WebKit2WebExtension.WebPage
        """
        if not self.__settings.get_value("remember-passwords"):
            return

        (username_input, password_input) = self.get_forms(webpage)

        if username_input is None or password_input is None:
            return
        self.__helper.get(webpage.get_uri(),
                          self.__set_input,
                          username_input,
                          password_input)

    def __set_input(self, attributes, password,
                    username_input, password_input):
        """
            Set username/password input
            @param attributes as {}
            @param password as str
            @param username_input as WebKit2WebExtension.DOMElement
            @param password_input as WebKit2WebExtension.DOMElement
        """
        try:
            username_input.set_value(attributes["login"])
            password_input.set_value(password)
        except Exception as e:
            print("FormsExtension::__set_input()", e)
