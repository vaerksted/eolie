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

from gi.repository import Gio, GLib, WebKit2WebExtension

from urllib.parse import urlparse
from uuid import uuid4

from eolie.define import PROXY_BUS, PROXY_PATH
from eolie.list import LinkedList
from eolie.helper_passwords import PasswordsHelper


class Server:
    def __init__(self, con, path):
        method_outargs = {}
        method_inargs = {}
        for interface in Gio.DBusNodeInfo.new_for_xml(self.__doc__).interfaces:

            for method in interface.methods:
                method_outargs[method.name] = '(' + ''.join(
                              [arg.signature for arg in method.out_args]) + ')'
                method_inargs[method.name] = tuple(
                                       arg.signature for arg in method.in_args)

            con.register_object(object_path=path,
                                interface_info=interface,
                                method_call_closure=self.on_method_call)

        self.method_inargs = method_inargs
        self.method_outargs = method_outargs

    def on_method_call(self,
                       connection,
                       sender,
                       object_path,
                       interface_name,
                       method_name,
                       parameters,
                       invocation):

        args = list(parameters.unpack())
        for i, sig in enumerate(self.method_inargs[method_name]):
            if sig is 'h':
                msg = invocation.get_message()
                fd_list = msg.get_unix_fd_list()
                args[i] = fd_list.get(args[i])

        try:
            result = getattr(self, method_name)(*args)

            # out_args is atleast (signature1).
            # We therefore always wrap the result as a tuple.
            # Refer to https://bugzilla.gnome.org/show_bug.cgi?id=765603
            result = (result,)

            out_args = self.method_outargs[method_name]
            if out_args != '()':
                variant = GLib.Variant(out_args, result)
                invocation.return_value(variant)
            else:
                invocation.return_value(None)
        except Exception as e:
            pass


class ProxyExtensionServer(Server):
    '''
    <!DOCTYPE node PUBLIC
    '-//freedesktop//DTD D-BUS Object Introspection 1.0//EN'
    'http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd'>
    <node>
    <interface name="org.gnome.Eolie.Proxy">

    <method name="FormsFilled">
        <arg type="b" name="results" direction="out" />
    </method>
    <method name="SetCredentials">
    </method>
    <method name="SetPreviousElementValue">
    </method>
    <method name="SetNextElementValue">
    </method>
    <method name="SaveCredentials">
      <arg type="s" name="uuid" direction="in" />
      <arg type="s" name="user_form_name" direction="in" />
      <arg type="s" name="pass_form_name" direction="in" />
      <arg type="s" name="uri" direction="in" />
      <arg type="s" name="form_uri" direction="in" />
    </method>
    <method name="SetAuthForms">
      <arg type="s" name="username" direction="in" />
      <arg type="s" name="username" direction="in" />
    </method>
    <method name="GetImages">
      <arg type="as" name="results" direction="out" />
    </method>
    <method name="GetVideos">
      <arg type="aas" name="results" direction="out" />
    </method>
    <method name="GetImageLinks">
      <arg type="as" name="results" direction="out" />
    </method>
    <method name="GetSelection">
      <arg type="s" name="selection" direction="out" />
    </method>

    <signal name='UnsecureFormFocused'>
        <arg type="as" name="forms" direction="out" />
    </signal>
    <signal name='InputMouseDown'>
        <arg type="as" name="forms" direction="out" />
    </signal>
    <signal name='AskSaveCredentials'>
        <arg type="s" name="uuid" direction="out" />
        <arg type="s" name="user_form_value" direction="out" />
        <arg type="s" name="uri" direction="out" />
        <arg type="s" name="form_uri" direction="out" />
    </signal>
    </interface>
    </node>
    '''

    def __init__(self, extension, page, form_extension):
        """
            Init server
            @param extension as WebKit2WebExtension.WebExtension
            @param page as WebKit2WebExtension.WebPage
            @param form_extension as FormsExtension
        """
        self.__extension = extension
        self.__page = page
        self.__form_extension = form_extension
        self.__focused = None
        self.__elements_history = {}
        self.__listened_input_elements = []
        self.__listened_mouse_elements = []
        self.__listened_focus_elements = []
        self.__send_requests = []
        self.__sended_requests = []
        self.__helper = PasswordsHelper()
        self.__proxy_bus = PROXY_BUS % self.__page.get_id()
        addr = Gio.dbus_address_get_for_bus_sync(Gio.BusType.SESSION, None)
        self.__bus = None
        Gio.DBusConnection.new_for_address(
                               addr,
                               Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT |
                               Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
                               None,
                               None,
                               self.__on_bus_new_for_address)
        form_extension.connect("submit-form", self.__on_submit_form)
        page.connect("document-loaded", self.__on_document_loaded)
        page.connect("send-request", self.__on_send_request)
        page.connect("context-menu", self.__on_context_menu)
        page.connect("form-controls-associated",
                     self.__on_form_control_associated)

    def FormsFilled(self):
        """
            True if form contains data
        """
        # Check for unsecure content
        for textarea in self.__form_extension.textareas:
            if textarea.is_edited():
                return True
        return False

    def SaveCredentials(self, uuid, user_form_name,
                        pass_form_name, uri, form_uri):
        """
            Save credentials to org.freedesktop.Secrets
            @param uuid as str
            @param user_form_name as str
            @param pass_form_name as str
            @param uri as str
            @param form_uri as str
        """
        if self.__form_extension.pending_credentials is None:
            return
        try:
            (_user_form_name, user_form_value,
             _pass_form_name, pass_form_value,
             _uri, _form_uri) = self.__form_extension.pending_credentials
            if user_form_name != _user_form_name or\
                    pass_form_name != _pass_form_name or\
                    uri != _uri or\
                    form_uri != _form_uri:
                return
            parsed = urlparse(uri)
            parsed_form_uri = urlparse(form_uri)
            uri = "%s://%s" % (parsed.scheme, parsed.netloc)
            form_uri = "%s://%s" % (parsed_form_uri.scheme,
                                    parsed_form_uri.netloc)
            if not uuid:
                uuid = str(uuid4())
                self.__helper.store(user_form_name,
                                    user_form_value,
                                    pass_form_name,
                                    pass_form_value,
                                    uri,
                                    form_uri,
                                    uuid,
                                    None)
            else:
                self.__helper.clear(uuid,
                                    self.__helper.store,
                                    user_form_name,
                                    user_form_value,
                                    pass_form_name,
                                    pass_form_value,
                                    uri,
                                    form_uri,
                                    uuid,
                                    None)
        except Exception as e:
            print("ProxyExtension::SaveCredentials():", e)

    def SetAuthForms(self, userform, username):
        """
            Get password forms
            @param userform as str
        """
        try:
            page = self.__extension.get_page(self.__page.get_id())
            # Search form
            for form in self.__form_extension.forms:
                if form["username"].get_name() == userform:
                    self.__helper.get(form["element"].get_action(),
                                      userform,
                                      form["password"].get_name(),
                                      self.__form_extension.set_input_forms,
                                      page,
                                      form,
                                      username)
                    return
        except Exception as e:
            print("ProxyExtension::SetAuthForms():", e)

    def GetImages(self):
        """
            Get images
            @return [str]
        """
        try:
            page = self.__extension.get_page(self.__page.get_id())
            if page is None:
                return []
            dom_list = page.get_dom_document().get_elements_by_tag_name("img")
            uris = []
            for i in range(0, dom_list.get_length()):
                uri = dom_list.item(i).get_src()
                if uri not in uris:
                    uris.append(uri)
            return uris
        except Exception as e:
            print("ProxyExtension::GetImages():", e)
        return []

    def GetVideos(self):
        """
            Get videos
            @return [str]
        """
        page = self.__extension.get_page(self.__page.get_id())
        if page is None:
            return []
        videos = []
        extensions = ["avi", "flv", "mp4", "mpg", "mpeg", "webm"]
        for uri in self.__sended_requests:
            parsed = urlparse(uri)
            title = None
            # Search for video in page
            if uri.split(".")[-1] in extensions:
                title = uri
            elif parsed.netloc.endswith("googlevideo.com") and\
                    parsed.path == "/videoplayback":
                title = page.get_dom_document().get_title()
                if title is None:
                    title = uri
                # For youtube, we only want one video:
                return [(title, uri)]
            if title is not None and (title, uri) not in videos:
                videos.append((title, uri))
        return videos

    def GetImageLinks(self):
        """
            Get image links
            @return [str]
        """
        try:
            page = self.__extension.get_page(self.__page.get_id())
            if page is None:
                return []
            dom_list = page.get_dom_document().get_elements_by_tag_name("a")
            uris = []
            for i in range(0, dom_list.get_length()):
                uri = dom_list.item(i).get_href()
                if uri is None or uri in uris:
                    continue
                ext = uri.split(".")[-1]
                if ext in ["gif", "jpg", "png", "jpeg"]:
                    uris.append(uri)
            return uris
        except Exception as e:
            print("ProxyExtension::GetImagesLinks():", e)
        return []

    def GetSelection(self):
        """
            Get selected text
            @param page id as int
            @return str
        """
        webpage = self.__extension.get_page(self.__page.get_id())
        document = webpage.get_dom_document()
        if document is None:
            return ""
        window = document.get_default_view()
        if window is None:
            return ""
        selection = window.get_selection()
        if selection is None:
            return ""
        try:
            dom_range = selection.get_range_at(0)
        except:
            dom_range = None
        value = ""
        if dom_range is not None:
            value = dom_range.to_string()
        if value is None:
            value = ""
        return value

    def SetCredentials(self):
        """
            Set focused form to previous value
        """
        try:
            webpage = self.__extension.get_page(self.__page.get_id())
            self.__form_extension.set_credentials(webpage)
        except Exception as e:
            print("ProxyExtension::SetCredentials():", e)

    def SetPreviousElementValue(self):
        """
            Set focused form to previous value
        """
        if self.__focused is None:
            return
        try:
            if self.__focused in self.__elements_history.keys():
                current_value = self.__focused.get_value()
                item = self.__elements_history[self.__focused]
                # User added some text, keep it
                if item.value != current_value:
                    next = LinkedList(current_value.rstrip(" "), None, item)
                    if item is not None:
                        item.set_next(next)
                    item = next
                if item.prev:
                    self.__elements_history[self.__focused] = item.prev
                    self.__focused.set_value(item.prev.value)
            else:
                new_value = self.__focused.get_value().rstrip(" ")
                if new_value:
                    item = LinkedList(new_value, None, None)
                    next = LinkedList("", item, None)
                    self.__elements_history[self.__focused] = next
                    self.__focused.set_value("")
        except Exception as e:
            print("ProxyExtension::SetPreviousForm():", e)

    def SetNextElementValue(self):
        """
            Set focused form to next value
        """
        if self.__focused is None:
            return
        try:
            if self.__focused in self.__elements_history.keys():
                item = self.__elements_history[self.__focused]
                if item.next:
                    self.__elements_history[self.__focused] = item.next
                    self.__focused.set_value(item.next.value)
        except Exception as e:
            print("ProxyExtension::SetNextForm():", e)

#######################
# PRIVATE             #
#######################
    def __add_event_listeners(self, webpage):
        """
            Add event listeners on inputs and textareas
            @param webpage as WebKit2WebExtension.WebPage
        """
        # Remove any previous event listener
        for element in self.__listened_input_elements:
            element.remove_event_listener("input", self.__on_input, False)
        for element in self.__listened_mouse_elements:
            element.remove_event_listener("mousedown",
                                          self.__on_mouse_down,
                                          False)
        for element in self.__listened_focus_elements:
            element.remove_event_listener("focus",
                                          self.__on_focus,
                                          False)
        self.__focused = None
        self.__elements_history = {}
        self.__listened_input_elements = []
        self.__listened_mouse_elements = []
        self.__listened_focus_elements = []
        self.__mouse_down_elements = []

        parsed = urlparse(webpage.get_uri())

        # Manage forms events
        for form in self.__form_extension.forms:
            self.__listened_input_elements.append(form["username"])
            self.__listened_focus_elements.append(form["username"])
            self.__listened_mouse_elements.append(form["username"])
            form["username"].add_event_listener("input",
                                                self.__on_input,
                                                False)
            form["username"].add_event_listener("focus",
                                                self.__on_focus,
                                                False)
            form["username"].add_event_listener("mousedown",
                                                self.__on_mouse_down,
                                                False)
            # Check for unsecure content
            if parsed.scheme == "http":
                self.__listened_focus_elements.append(form["password"])
                form["password"].add_event_listener("focus",
                                                    self.__on_focus,
                                                    False)
        # Manage textareas events
        for textarea in self.__form_extension.textareas:
            self.__listened_input_elements.append(textarea)
            self.__listened_focus_elements.append(textarea)
            textarea.add_event_listener("input", self.__on_input, False)
            textarea.add_event_listener("focus", self.__on_focus, False)

    def __on_bus_new_for_address(self, source, result):
        """
            Init bus
            @param source as GObject.Object
            @param result as Gio.AsyncResult
        """
        self.__bus = source.new_for_address_finish(result)
        Gio.bus_own_name_on_connection(self.__bus,
                                       self.__proxy_bus,
                                       Gio.BusNameOwnerFlags.NONE,
                                       None,
                                       None)
        Server.__init__(self, self.__bus, PROXY_PATH)

    def __on_focus(self, element, event):
        """
            Keep last focused form
            @param element as WebKit2WebExtension.DOMElement
            @param event as WebKit2WebExtension.DOMUIEvent
        """
        if isinstance(element, WebKit2WebExtension.DOMHTMLInputElement):
            if element.get_input_type() == "password" and\
                    self.__bus is not None:
                self.__bus.emit_signal(
                              None,
                              PROXY_PATH,
                              self.__proxy_bus,
                              "UnsecureFormFocused",
                              None)
        self.__focused = element

    def __on_mouse_down(self, element, event):
        """
           Emit Input mouse down signal
           @param element as WebKit2WebExtension.DOMElement
           @param event as WebKit2WebExtension.DOMUIEvent
        """
        name = element.get_name()
        if name is None:
            return
        # Only send signal on one of the two calls
        if name in self.__mouse_down_elements:
            self.__mouse_down_elements.remove(name)
        elif self.__bus is not None:
            self.__mouse_down_elements.append(name)
            args = GLib.Variant.new_tuple(GLib.Variant("s", name))
            self.__bus.emit_signal(
                              None,
                              PROXY_PATH,
                              self.__proxy_bus,
                              "InputMouseDown",
                              args)

    def __on_input(self, element, event):
        """
            Send input signal
            @param element as WebKit2WebExtension.DOMElement
            @param event as WebKit2WebExtension.DOMUIEvent
        """
        new_value = element.get_value()
        previous_value = ""
        item = LinkedList("", None, None)
        if element in self.__elements_history.keys():
            item = self.__elements_history[element]
            previous_value = item.value
        # Here we try to get words
        # If we are LTR then add words on space
        if len(new_value) > len(previous_value):
            if new_value.endswith(" "):
                next = LinkedList(new_value.rstrip(" "), None, item)
                if item is not None:
                    item.set_next(next)
                self.__elements_history[element] = next

    def __on_form_control_associated(self, webpage, elements):
        """
            Add elements to forms
            @param webpage as WebKit2WebExtension.WebPage
            @param elements as [WebKit2WebExtension.DOMElement]
        """
        self.__form_extension.add_elements(elements)
        self.__add_event_listeners(webpage)
        self.__form_extension.set_credentials(webpage)

    def __on_context_menu(self, webpage, context_menu, hit):
        """
            Add selection to context menu user data
            @param webpage as WebKit2WebExtension.WebPage
            @param context_menu as WebKit2WebExtension.ContextMenu
            @param hit as WebKit2.HitTestResult
        """
        value = self.GetSelection()
        context_menu.set_user_data(GLib.Variant("s", value))

    def __on_submit_form(self, forms, variant):
        """
            Ask for credentials save
            @param forms as FormsExtension
            @param variant as GLib.Variant
        """
        if self.__bus is not None:
            self.__bus.emit_signal(
                                  None,
                                  PROXY_PATH,
                                  self.__proxy_bus,
                                  "AskSaveCredentials",
                                  variant)

    def __on_document_loaded(self, webpage):
        """
            Keep some data for extension
        """
        self.__sended_requests = self.__send_requests
        self.__send_requests = []

    def __on_send_request(self, webpage, request, redirect):
        """
            Keep send requests
            @param webpage as WebKit2WebExtension.WebPage
            @param request as WebKit2.URIRequest
            @param redirect as WebKit2WebExtension.URIResponse
        """
        self.__send_requests.append(request.get_uri())


class ProxyExtension:
    """
        Communication proxy for Eolie
    """

    def __init__(self, extension, form_extension):
        """
            Init extension
            @param extension as WebKit2WebExtension.WebExtension
            @param form_extension as FormsExtension
        """
        self.__server = None
        extension.connect("page-created",
                          self.__on_page_created,
                          form_extension)

#######################
# PRIVATE             #
#######################
    def __on_page_created(self, extension, webpage, form_extension):
        """
            Cache webpage
            @param extension as WebKit2WebExtension.WebExtension
            @param webpage as WebKit2WebExtension.WebPage
            @param form_extension as FormsExtension
        """
        self.__server = ProxyExtensionServer(extension,
                                             webpage,
                                             form_extension)
