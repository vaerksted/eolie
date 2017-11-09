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

from gi.repository import WebKit2WebExtension, GLib, GObject

from urllib.parse import urlparse

from eolie.helper_passwords import PasswordsHelper


class FormsExtension(GObject.Object):
    """
        Handle forms prefill
    """

    __gsignals__ = {
        'submit-form': (GObject.SignalFlags.RUN_FIRST, None, (GLib.Variant,))
    }

    def __init__(self, extension, settings):
        """
            Connect wanted signal
            @param extension as WebKit2WebExtension
            @param settings as Settings
        """
        GObject.Object.__init__(self)
        self.__helper = PasswordsHelper()
        self.__extension = extension
        self.__settings = settings
        self.__elements_uri = None
        self.__forms = []
        self.__textareas = []
        self.__pending_credentials = None
        self.__page_id = None
        extension.connect("page-created", self.__on_page_created)

    def set_credentials(self, webpage):
        """
            Set credentials on page
            @param webpage as WebKit2WebExtension.WebPage
        """
        if self.__settings.get_value("remember-passwords"):
            for form in self.__forms:
                form_input_username = form["username"].get_name()
                form_input_password = form["password"].get_name()
                if form_input_username is not None and\
                        form_input_password is not None:
                    self.__helper.get(form["element"].get_action(),
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
            @param form as {}
            @param username as str
        """
        if attributes is None:
            return
        # We only set first available password
        if (index != 0 or count > 1) and username is None:
            return
        parsed = urlparse(form["element"].get_action())
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
            print("FormsExtension::set_input_forms()", e)

    def add_elements(self, elements):
        """
            Update login and password inputs
            @param elements as [WebKit2WebExtension.DOMElement]
        """
        for form in self.__forms:
            form["element"].remove_event_listener("submit",
                                                  self.__on_form_submit,
                                                  False)
        self.__forms = []
        self.__textareas = []

        for element in elements:
            if isinstance(element, WebKit2WebExtension.DOMHTMLTextAreaElement):
                self.__textareas.append(element)
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
                                element.get_name() is not None:
                            form["password"] = element
                        elif element.get_input_type() in ["text",
                                                          "email",
                                                          "search"] and\
                                element.get_name() is not None:
                            form["username"] = element
                    elif isinstance(
                                   element,
                                   WebKit2WebExtension.DOMHTMLTextAreaElement):
                        self.__textareas.append(element)
                    h += 1
                keys = form.keys()
                if "username" in keys and "password" in keys:
                    self.__forms.append(form)
                    form["element"].add_event_listener("submit",
                                                       self.__on_form_submit,
                                                       False)

    @property
    def textareas(self):
        """
            Get textareas
            @return [WebKit2WebExtension.DOMHTMLTextAreaElement]
        """
        return self.__textareas

    @property
    def forms(self):
        """
            Get forms
            @return [WebKit2WebExtension.DOMHTMLFormElement]
        """
        return self.__forms

    @property
    def pending_credentials(self):
        """
            Get credentials
            @return (str, str, str, str, str, str)
        """
        return self.__pending_credentials

#######################
# PRIVATE             #
#######################
    def __on_form_submit(self, element, event):
        """
            Ask user for saving credentials
            @param element as WebKit2WebExtension.DOMElement
            @param event as WebKit2WebExtension.DOMUIEvent
        """
        page = self.__extension.get_page(self.__page_id)
        if page is None:
            return
        # Search for form
        form = None
        for form in self.__forms:
            if form["element"] == element:
                break
        if form is None:
            return
        try:
            uri = page.get_uri()
            form_uri = form["element"].get_action()
            user_form_name = form["username"].get_name()
            user_form_value = form["username"].get_value()
            pass_form_name = form["password"].get_name()
            pass_form_value = form["password"].get_value()
            self.__pending_credentials = (user_form_name,
                                          user_form_value,
                                          pass_form_name,
                                          pass_form_value,
                                          uri,
                                          form_uri)
            self.__helper.get(form_uri, user_form_name,
                              pass_form_name, self.__on_get_password,
                              user_form_name, user_form_value,
                              pass_form_name, pass_form_value,
                              uri,
                              self.__page_id)
        except Exception as e:
            print("FormsExtension::__on_form_submit():", e)

    def __on_get_password(self, attributes, password, form_uri, index, count,
                          user_form_name, user_form_value, pass_form_name,
                          pass_form_value, uri, page_id):
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
            @param uri as str
            @param page_id as int
        """
        try:
            uuid = ""
            if attributes is not None:
                if attributes["login"] != user_form_value:
                    pass  # New login to store
                elif password == pass_form_value:
                    return
                else:
                    uuid = attributes["uuid"]
            args = (uuid, user_form_name, user_form_value,
                    pass_form_name, uri, form_uri)
            variant = GLib.Variant.new_tuple(GLib.Variant("(ssssss)", args))
            self.emit("submit-form", variant)
        except Exception as e:
            print("FormsExtension::__on_get_password()", e)

    def __on_page_created(self, extension, webpage):
        """
            Connect to send request
            @param extension as WebKit2WebExtension
            @param webpage as WebKit2WebExtension.WebPage
        """
        self.__page_id = webpage.get_id()
