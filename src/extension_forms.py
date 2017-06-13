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
        self.__settings = settings
        extension.connect("page-created", self.__on_page_created)

    def get_forms(self, webpage):
        """
            Return forms for webpage
            @param webpage as WebKit2WebExtension.WebPage
            @return (WebKit2WebExtension.DOMElement,   => username
                     WebKit2WebExtension.DOMElement,   => password
                     [WebKit2WebExtension.DOMElement]) => others
        """
        others = []
        dom_document = webpage.get_dom_document()
        inputs = dom_document.get_elements_by_tag_name("input")
        textareas = dom_document.get_elements_by_tag_name("textarea")
        i = 0
        username_input = None
        password_input = None
        while i < inputs.get_length():
            if inputs.item(i).get_input_type() == "hidden":
                i += 1
                continue
            name = inputs.item(i).get_attribute("name")
            input_id = inputs.item(i).get_attribute("id")
            if password_input is None and\
                    inputs.item(i).get_input_type() == "password":
                password_input = inputs.item(i)
                i += 1
                continue
            if username_input is None:
                for search in LOGINS:
                    if (name is not None and
                            name.lower().find(search) != -1) or\
                            (input_id is not None and
                                input_id.lower().find(search) != -1):
                        username_input = inputs.item(i)
                        break
            if username_input is None:
                others.append(inputs.item(i))
            i += 1
        i = 0
        while i < textareas.get_length():
            others.append(textareas.item(i))
            i += 1
        return (username_input, password_input, others)

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

        (username_input, password_input, others) = self.get_forms(webpage)

        if username_input is None or password_input is None:
            return
        self.__helper.get(webpage.get_uri(),
                          self.__set_input,
                          username_input,
                          password_input)

    def __set_input(self, attributes, password, uri,
                    username_input, password_input):
        """
            Set username/password input
            @param attributes as {}
            @param password as str
            @param uri as str
            @param username_input as WebKit2WebExtension.DOMElement
            @param password_input as WebKit2WebExtension.DOMElement
        """
        # Do not set anything if no attributes or
        # If we have already text in input and we are not a perfect completion
        if attributes is None or (
                password_input.get_value() and
                uri != attributes["formSubmitURL"]):
            return
        try:
            username_input.set_value(attributes["login"])
            password_input.set_value(password)
        except Exception as e:
            print("FormsExtension::__set_input()", e)
