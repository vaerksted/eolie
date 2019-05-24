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

from gi.repository import WebKit2WebExtension, GLib, GObject

from urllib.parse import urlparse

from eolie.define import App
from eolie.helper_passwords import PasswordsHelper
from eolie.logger import Logger


class FormsExtension(GObject.Object):
    """
        Handle forms prefill
    """

    __gsignals__ = {
        'submit-form': (GObject.SignalFlags.RUN_FIRST, None, (GLib.Variant,))
    }

    def __init__(self, extension):
        """
            Connect wanted signal
            @param extension as WebKit2WebExtension
        """
        GObject.Object.__init__(self)
        self.__helper = PasswordsHelper()
        self.__extension = extension
        self.__elements_uri = None
        self.__pending_credentials = None
        self.__page_id = None
        extension.connect("page-created", self.__on_page_created)

    def set_credentials(self, form, webpage):
        """
            Set credentials on page
            @param form as {
                           "element":WebKit2WebExtension.DOMHTMLFormElement,
                           "username": WebKit2WebExtension.DOMHTMLInputElement,
                           "password": WebKit2WebExtension.DOMHTMLInputElement}
            @param webpage as WebKit2WebExtension.WebPage
        """
        if App().settings.get_value("remember-passwords"):
            form_input_username = form["username"].get_name()
            form_input_password = form["password"].get_name()
            if form_input_username is not None and\
                    form_input_password is not None:
                self.__helper.get(self.get_form_uri(form["element"]),
                                  form_input_username,
                                  form_input_password,
                                  self.set_input_forms,
                                  webpage,
                                  form)

    def set_input_forms(self, attributes, password,
                        uri, index, count, webpage, form, username=None):
        """
            Set login/password input
            @param attributes as {}
            @param password as str
            @param uri as str
            @param index as int
            @param count as int
            @param webpage as WebKit2WebExtension.WebPage
            @param form as {
                           "element":WebKit2WebExtension.DOMHTMLFormElement,
                           "username": WebKit2WebExtension.DOMHTMLInputElement,
                           "password": WebKit2WebExtension.DOMHTMLInputElement}
            @param username as str
        """
        if attributes is None:
            return
        # We only set first available password
        if (index != 0 or count > 1) and username is None:
            return
        parsed = urlparse(self.get_form_uri(form["element"]))
        # Allow unsecure completion if wanted by user
        if parsed.scheme != "https" and username is None:
            return
        # We want a user, check if it wanted password
        if username is not None and username != attributes["login"]:
            return
        try:
            form["username"].set_value(attributes["login"])
            form["password"].set_value(password)
        except Exception as e:
            Logger.error("FormsExtension::set_input_forms(): %s", e)

    def get_elements(self, elements):
        """
            Get forms as dict and textareas for elements
            @param elements as [WebKit2WebExtension.DOMElement]
            @return elements as
                ([{"element":WebKit2WebExtension.DOMHTMLFormElement,
                   "username": WebKit2WebExtension.DOMHTMLInputElement,
                   "password": WebKit2WebExtension.DOMHTMLInputElement}],
                 [WebKit2WebExtension.DOMHTMLTextAreaElement])
        """
        forms = []
        textareas = []
        for element in elements:
            if isinstance(element, WebKit2WebExtension.DOMHTMLTextAreaElement):
                textareas.append(element)
            elif isinstance(element,
                            WebKit2WebExtension.DOMHTMLFormElement):
                form = {"element": element}
                elements_collection = element.get_elements()
                h = 0
                while h < elements_collection.get_length():
                    element = elements_collection.item(h)
                    if isinstance(element,
                                  WebKit2WebExtension.DOMHTMLInputElement):
                        if element.get_input_type() == "password" and\
                                element.get_name() is not None and\
                                "password" not in form.keys():
                            form["password"] = element
                        elif element.get_input_type() in ["text",
                                                          "email",
                                                          "search"] and\
                                element.get_name() is not None and\
                                "username" not in form.keys():
                            form["username"] = element
                    elif isinstance(
                            element,
                            WebKit2WebExtension.DOMHTMLTextAreaElement):
                        textareas.append(element)
                    h += 1
                keys = form.keys()
                if "username" in keys and "password" in keys:
                    forms.append(form)
        return (forms, textareas)

    def get_hostname_uri(self, page):
        """
            Get form uri for page
            @param page as WebKit2WebExtension.WebPage
            @return str
            @raise Exception
        """
        page = self.__extension.get_page(self.__page_id)
        if page is None:
            raise Exception("Can't find page!")
        uri = page.get_uri()
        parsed = urlparse(uri)
        return "%s://%s" % (parsed.scheme, parsed.netloc)

    def get_form_uri(self, form):
        """
            Get form uri for form
            @param form as WebKit2WebExtension.DOMHTMLFormElement
            @return str
        """
        form_uri = form.get_action()
        if form_uri is None:
            page = self.__extension.get_page(self.__page_id)
            return self.get_hostname_uri(page)
        else:
            parsed_form_uri = urlparse(form_uri)
            return "%s://%s" % (parsed_form_uri.scheme,
                                parsed_form_uri.netloc)

    @property
    def pending_credentials(self):
        """
            Get credentials
            @return (str, str, str, str, str, str) or None
        """
        return self.__pending_credentials

#######################
# PRIVATE             #
#######################
    def __on_get_password(self, attributes, password, form_uri, index, count,
                          user_form_name, user_form_value, pass_form_name,
                          pass_form_value, hostname_uri, page_id):
        """
            Ask for credentials through DBus
            @param attributes as {}
            @param password as str
            @param form_uri as str
            @param index as int
            @param count as int
            @param user_form_name as str
            @param user_form_value as str
            @param pass_form_name as str
            @param pass_form_value as str
            @param hostname_uri as str
            @param page_id as int
        """
        try:
            self.__pending_credentials = (user_form_name,
                                          user_form_value,
                                          pass_form_name,
                                          pass_form_value,
                                          hostname_uri,
                                          form_uri)

            # New credential
            if count == 0:
                args = ("", user_form_name, user_form_value,
                        pass_form_name, hostname_uri, form_uri)
                variant = GLib.Variant.new_tuple(GLib.Variant("(ssssss)",
                                                              args))
                self.emit("submit-form", variant)
            # Last credential
            elif index == count - 1:
                if attributes is not None:
                    uuid = attributes["uuid"]
                    # No password change
                    if attributes["login"] == user_form_value and\
                            password == pass_form_value:
                        return
                    # New password
                    elif attributes["login"] != user_form_value:
                        uuid = ""
                args = (uuid, user_form_name, user_form_value,
                        pass_form_name, hostname_uri, form_uri)
                variant = GLib.Variant.new_tuple(GLib.Variant("(ssssss)",
                                                              args))
                self.emit("submit-form", variant)
        except Exception as e:
            Logger.error("FormsExtension::__on_get_password(): %s", e)

    def __on_will_submit_form(self, webpage, form, step,
                              source, target, names, values):
        """
            @param webpage as WebKit2WebExtension.WebPage
            @param form as WebKit2WebExtension.DOMHTMLFormElement
            @param step as WebKit2WebExtension.FormSubmissionStep
            @param source as WebKit2WebExtension.Frame
            @param target as WebKit2WebExtension.Frame
            @param names as [str]
            @param values as [str]
        """
        if step != WebKit2WebExtension.FormSubmissionStep.SEND_DOM_EVENT or\
                not names or not values:
            return
        try:
            # Check elements
            self.__pending_credentials = None
            document = webpage.get_dom_document()
            username_idx = None
            password_idx = None
            idx = 0
            for name in names:
                if username_idx is not None and password_idx is not None:
                    break
                elements = document.get_elements_by_name(name)
                for elements_idx in range(0, elements.get_length()):
                    element = elements.item(elements_idx)
                    if isinstance(element,
                                  WebKit2WebExtension.DOMHTMLInputElement):
                        if element.get_input_type() == "password" and\
                                element.get_name() is not None:
                            password_idx = idx
                            break
                        elif element.get_input_type() in ["text",
                                                          "email",
                                                          "search"] and\
                                element.get_name() is not None:
                            username_idx = idx
                            break
                idx += 1
            if username_idx is not None and password_idx is not None:
                hostname_uri = self.get_hostname_uri(webpage)
                form_uri = self.get_form_uri(form)
                user_form_name = names[username_idx]
                user_form_value = values[username_idx]
                pass_form_name = names[password_idx]
                pass_form_value = values[password_idx]
                self.__helper.get(form_uri, user_form_name,
                                  pass_form_name, self.__on_get_password,
                                  user_form_name, user_form_value,
                                  pass_form_name, pass_form_value,
                                  hostname_uri,
                                  self.__page_id)
        except Exception as e:
            Logger.error("FormsExtension::__on_will_submit_form(): %s" % e)

    def __on_page_created(self, extension, webpage):
        """
            Connect to send request
            @param extension as WebKit2WebExtension
            @param webpage as WebKit2WebExtension.WebPage
        """
        self.__page_id = webpage.get_id()
        webpage.connect("will-submit-form", self.__on_will_submit_form)
