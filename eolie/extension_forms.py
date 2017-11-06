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

from gi.repository import WebKit2WebExtension

from urllib.parse import urlparse

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
        self.__form_inputs = []
        extension.connect("page-created", self.__on_page_created)

    def set_credentials(self, webpage):
        """
            Set credentials on page
            @param webpage as WebKit2WebExtension.WebPage
        """
        # Do not remove this,
        # it's needed because page may have changed
        self.update_inputs_list(webpage)
        for form_input in self.__form_inputs:
            form_input_username = form_input["username"].get_name()
            form_input_password = form_input["password"].get_name()
            if form_input_username is not None and\
                    form_input_password is not None:
                self.__helper.get(form_input["uri"],
                                  form_input_username,
                                  form_input_password,
                                  self.set_input_forms,
                                  webpage,
                                  form_input)

    def get_inputs(self, webpage):
        """
            Return forms for webpage
            @param webpage as WebKit2WebExtension.WebPage
            @return [WebKit2WebExtension.DOMHTMLInputElement]
        """
        forms = []
        dom_document = webpage.get_dom_document()
        inputs = dom_document.get_elements_by_tag_name("input")
        i = 0
        while i < inputs.get_length():
            if inputs.item(i).get_input_type() in ["text", "email", "search"]:
                forms.append(inputs.item(i))
            i += 1
        return forms

    def get_textarea(self, webpage):
        """
            Return textarea for webpage
            @param webpage as WebKit2WebExtension.WebPage
            @return [WebKit2WebExtension.DOMHTMLInputElement]
        """
        forms = []
        dom_document = webpage.get_dom_document()
        textareas = dom_document.get_elements_by_tag_name("textarea")
        i = 0
        while i < textareas.get_length():
            forms.append(textareas.item(i))
            i += 1
        return forms

    def get_form_inputs(self, webpage):
        """
            Return inputs for form
            @param webpage as WebKit2WebExtension.WebPage
            @return {}
        """
        return self.__form_inputs

    def is_input(self, name, input_type, webpage):
        """
            Return True if a password input
            @param name as str
            @param input_type as str
            @param webpage as WebKit2WebExtension.WebPage
            @return WebKit2WebExtension.DOMHTMLInputElement/None
        """
        for form_input in self.__form_inputs:
            input_name = form_input[input_type].get_name()
            if name == input_name:
                return True
        return False

    def set_input_forms(self, attributes, password,
                        uri, index, count, webpage, form_input, username=None):
        """
            Set login/password input
            @param attributes as {}
            @param password as str
            @param uri as str
            @param index as int
            @param count as int
            @param webpage as WebKit2WebExtension.WebPage
            @param form_input as {}
            @param username as str
        """
        if attributes is None:
            return
        # We only set first available password
        if (index != 0 or count > 1) and username is None:
            return
        parsed = urlparse(form_input["uri"])
        # Allow unsecure completion if wanted by user
        if parsed.scheme != "https" and username is None:
            return
        # We want a user, check if it wanted password
        if username is not None and username != attributes["login"]:
            return
        try:
            form_input["username"].set_value(attributes["login"])
            form_input["password"].set_value(password)
        except Exception as e:
            print("FormsExtension::set_input_forms()", e)

    def update_inputs_list(self, webpage):
        """
            Update login and password inputs
            @param webpage as WebKit2WebExtension.WebPage
        """
        self.__form_inputs = []
        collection = webpage.get_dom_document().get_forms()
        i = 0
        while i < collection.get_length():
            form = collection.item(i)
            if form.get_method() == "post":
                form_input = {"uri": form.get_action()}
                elements_collection = form.get_elements()
                h = 0
                while h < elements_collection.get_length():
                    element = elements_collection.item(h)
                    if not isinstance(element,
                                      WebKit2WebExtension.DOMHTMLInputElement):
                        h += 1
                        continue
                    if element.get_input_type() == "password" and\
                            element.get_name() is not None:
                        form_input["password"] = element
                    elif element.get_input_type() in ["text",
                                                      "email",
                                                      "search"] and\
                            element.get_name() is not None:
                        form_input["username"] = element
                    h += 1
                keys = form_input.keys()
                if "username" in keys and "password" in keys:
                    self.__form_inputs.append(form_input)
            i += 1

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
        self.set_credentials(webpage)
