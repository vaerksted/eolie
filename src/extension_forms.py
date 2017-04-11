# Copyright (c) 2014-2016 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

import gi
gi.require_version('Secret', '1')
from gi.repository import Secret

from urllib.parse import urlparse

from eolie.database_extensions import DatabaseExtensions
from eolie.define import LOGINS


class FormsExtension:
    """
        Handle forms prefill
    """

    def __init__(self, extension):
        """
            Connect wanted signal
            @param extension as WebKit2WebExtension
        """
        self.__secret = None
        self.__extensions = DatabaseExtensions()
        Secret.Service.get(Secret.ServiceFlags.NONE, None,
                           self.__on_get_secret)
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
        webpage.connect("document-loaded", self.__on_document_loaded)

    def __on_document_loaded(self, webpage):
        """
            Restore forms
            @param webpage as WebKit2WebExtension.WebPage
        """
        if self.__secret is None:
            return
        uri = webpage.get_uri()
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
                self.__extensions.add_password(uri, name)
                i += 1
                continue
            if username_input is None and\
                    inputs.item(i).get_input_type() != "hidden":
                for search in LOGINS:
                    if name.lower().find(search) != -1:
                        username_input = inputs.item(i)
                        break
            i += 1

        if username_input is None or password_input is None:
            return
        parsed = urlparse(uri)
        SecretSchema = {
            "type": Secret.SchemaAttributeType.STRING,
            "uri": Secret.SchemaAttributeType.STRING,
        }
        SecretAttributes = {
            "type": "eolie web login",
            "uri": parsed.netloc,
        }
        schema = Secret.Schema.new("org.gnome.Eolie",
                                   Secret.SchemaFlags.NONE,
                                   SecretSchema)
        self.__secret.search(schema, SecretAttributes,
                             Secret.ServiceFlags.NONE,
                             None,
                             self.__on_secret_search,
                             username_input,
                             password_input)

    def __on_load_secret(self, source, result,
                         username_input, password_input):
        """
            Set username/password input
            @param source as GObject.Object
            @param result as Gio.AsyncResult
            @param username_input as WebKit2WebExtension.DOMElement
            @param password_input as WebKit2WebExtension.DOMElement
        """
        try:
            secret = source.get_secret()
            attributes = source.get_attributes()
            if secret is not None:
                username_input.set_value(attributes["login"])
                password_input.set_value(secret.get().decode('utf-8'))
        except Exception as e:
            print("FormsExtension::__on_load_secret()", e)

    def __on_secret_search(self, source, result,
                           username_input, password_input):
        """
            Set username/password input
            @param source as GObject.Object
            @param result as Gio.AsyncResult
            @param username_input as WebKit2WebExtension.DOMElement
            @param password_input as WebKit2WebExtension.DOMElement
        """
        try:
            if result is not None:
                items = self.__secret.search_finish(result)
                if not items:
                    return
                items[0].load_secret(None,
                                     self.__on_load_secret,
                                     username_input,
                                     password_input)
        except Exception as e:
            print("FormsExtension::__on_secret_search()", e)

    def __on_get_secret(self, source, result):
        """
            Store secret proxy
            @param source as GObject.Object
            @param result as Gio.AsyncResult
        """
        try:
            self.__secret = Secret.Service.get_finish(result)
        except Exception as e:
            print("FormsExtension::__on_get_secret()", e)
