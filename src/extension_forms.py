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
        self.__input_logins = []
        self.__input_passwords = []
        extension.connect("page-created", self.__on_page_created)

    def set_credentials(self, webpage):
        """
            Set credentials on page
            @param webpage as WebKit2WebExtension.WebPage
        """
        forms = self.update_inputs_list(webpage)
        for form in forms:
            self.__helper.get(form.get_action(),
                              self.set_input_forms,
                              webpage)

    def get_input_forms(self, webpage):
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

    def get_textarea_forms(self, webpage):
        """
            Return forms for webpage
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

    def get_password_inputs(self, webpage):
        """
            Return password inputs
            @param webpage as WebKit2WebExtension.WebPage
            @return [WebKit2WebExtension.DOMHTMLInputElement]
        """
        return self.__input_passwords

    def get_password_input(self, name, webpage):
        """
            Return password input with name
            @param name as str
            @param webpage as WebKit2WebExtension.WebPage
            @return WebKit2WebExtension.DOMHTMLInputElement/None
        """
        wanted_input_password = None
        unwanted_input_password = None
        for input_password in self.__input_passwords:
            input_name = input_password.get_attribute("name")
            input_id = input_password.get_attribute("id")
            # We search for wanted name
            if name and (name == input_name or name == input_id):
                wanted_input_password = input_password
                break
            elif unwanted_input_password is None:
                unwanted_input_password = input_password
        if wanted_input_password is not None:
            return wanted_input_password
        else:
            return unwanted_input_password

    def get_login_input(self, name, webpage):
        """
            Return login input with name
            @param name as str
            @param webpage as WebKit2WebExtension.WebPage
            @return WebKit2WebExtension.DOMHTMLInputElement/None
        """
        wanted_input_login = None
        unwanted_input_login = None
        for input_login in self.__input_logins:
            input_name = input_login.get_attribute("name")
            input_id = input_login.get_attribute("id")
            # We search for wanted name
            if name and (name == input_name or name == input_id):
                wanted_input_login = input_login
                break
            elif unwanted_input_login is None:
                unwanted_input_login = input_login
        if wanted_input_login is not None:
            return wanted_input_login
        else:
            return unwanted_input_login

    def set_input_forms(self, attributes, password,
                        uri, index, count, webpage, login=None):
        """
            Set login/password input
            @param attributes as {}
            @param password as str
            @param uri as str
            @param index as int
            @param count as int
            @param webpage as WebKit2WebExtension.WebPage
            @param login as str/None
        """
        # We only set first available password
        if (index != 0 or count > 1) and login is None:
            return
        parsed = urlparse(uri)
        # Allow unsecure completion if wanted by user
        if parsed.scheme != "https" and login is None:
            return
        submit_uri = "%s://%s" % (parsed.scheme, parsed.netloc)
        # Do not set anything if no attributes or
        # If we have already text in input
        if attributes is None or\
                (login is not None and attributes["login"] != login) or\
                attributes["formSubmitURL"] != submit_uri:
            return
        try:
            wanted_input_login = None
            name = attributes["userform"]
            for input_login in self.__input_logins:
                input_name = input_login.get_attribute("name")
                input_id = input_login.get_attribute("id")
                # We search for wanted name
                if name and (name == input_name or name == input_id):
                    wanted_input_login = input_login
                    break
            if wanted_input_login is None:
                return
            wanted_input_password = None
            name = attributes["passform"]
            for input_password in self.__input_passwords:
                input_name = input_password.get_attribute("name")
                input_id = input_password.get_attribute("id")
                if not name or name == input_name or name == input_id:
                    wanted_input_password = input_password
                    break
            if wanted_input_password is None:
                return
            wanted_input_login.set_value(attributes["login"])
            wanted_input_password.set_value(password)
        except Exception as e:
            print("FormsExtension::set_input_forms()", e)

    def is_login_form(self, form):
        """
            Return True if form is a login form
            @param form as WebKit2WebExtension.DOMHTMLInputElement
            @return bool
        """
        input_name = form.get_attribute("name")
        input_id = form.get_attribute("id")
        # We search for common name
        for search in LOGINS:
            if (input_name is not None and
                    input_name.lower().find(search) != -1) or\
                    (input_id is not None and
                        input_id.lower().find(search) != -1):
                return True
        return False

    def update_inputs_list(self, webpage):
        """
            Update login and password inputs
            @param webpage as WebKit2WebExtension.WebPage
            @return forms with a password input
        """
        self.__input_logins = []
        self.__input_passwords = []
        forms = []
        collection = webpage.get_dom_document().get_forms()
        i = 0
        while i < collection.get_length():
            form = collection.item(i)
            if form.get_method() == "post":
                elements_collection = form.get_elements()
                h = 0
                while h < elements_collection.get_length():
                    element = elements_collection.item(h)
                    if not isinstance(element,
                                      WebKit2WebExtension.DOMHTMLInputElement):
                        h += 1
                        continue
                    if element.get_input_type() == "password":
                        self.__input_passwords.append(element)
                        if form not in forms:
                            forms.append(form)
                    elif element.get_input_type() in ["text",
                                                      "email",
                                                      "search"]:
                        self.__input_logins.append(element)
                    h += 1
            i += 1
        return forms

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
