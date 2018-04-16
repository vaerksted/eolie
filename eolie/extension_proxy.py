# Copyright (c) 2017-2018 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
# Copyright (c) 2016 Felipe Borges <felipeborges@gnome.org>
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

from eolie.define import PROXY_BUS, PROXY_PATH, Type
from eolie.list import LinkedList
from eolie.helper_passwords import PasswordsHelper
from eolie.logger import Logger


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
    <method name="SetPreviousElementValue">
    </method>
    <method name="SetNextElementValue">
    </method>
    <method name="EnableJS">
        <arg type="s" name="netloc" direction="in" />
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
    <method name="GetScripts">
      <arg type="as" name="results" direction="out" />
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
    <signal name='ShowCredentials'>
        <arg type="as" name="forms" direction="out" />
        <arg type="as" name="form_uri" direction="out" />
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

    def __init__(self, extension, page, form_extension, jsblock_extension):
        """
            Init server
            @param extension as WebKit2WebExtension.WebExtension
            @param page as WebKit2WebExtension.WebPage
            @param form_extension as FormsExtension
            @param jsblock_extension as JSBlockExtension
        """
        self.__extension = extension
        self.__page = page
        self.__form_extension = form_extension
        self.__jsblock_extension = jsblock_extension
        self.__focus_element = None
        self.__mouse_down_element = None
        self.__on_input_timeout_id = None
        self.__elements_history = {}
        self.__send_requests = []
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
        page.connect("send-request", self.__on_send_request)
        page.connect("context-menu", self.__on_context_menu)
        page.connect("notify::uri", self.__on_notify_uri)
        page.connect("form-controls-associated",
                     self.__on_form_control_associated)

    def FormsFilled(self):
        """
            True if form contains data
            @return bool
        """
        dom = self.__page.get_dom_document()
        collection = dom.get_elements_by_tag_name("textarea")
        for i in range(0, collection.get_length()):
            if collection.item(i).is_edited():
                return True
        return False

    def EnableJS(self, netloc):
        """
            Enable JS for netloc
            @param netloc as JS
        """
        self.__jsblock_extension.enable_for(netloc)

    def SaveCredentials(self, uuid, user_form_name,
                        pass_form_name, hostname_uri, form_uri):
        """
            Save credentials to org.freedesktop.Secrets
            @param uuid as str
            @param user_form_name as str
            @param pass_form_name as str
            @param hostname_uri as str
            @param form_uri as str
        """
        if self.__form_extension.pending_credentials in [None, Type.NONE]:
            return
        try:
            (_uuid,
             _user_form_name,
             user_form_value,
             _pass_form_name,
             pass_form_value,
             _hostname_uri,
             _form_uri) = self.__form_extension.pending_credentials
            if user_form_name != _user_form_name or\
                    pass_form_name != _pass_form_name or\
                    hostname_uri != _hostname_uri or\
                    form_uri != _form_uri:
                return
            if not uuid:
                uuid = str(uuid4())
                self.__helper.store(user_form_name,
                                    user_form_value,
                                    pass_form_name,
                                    pass_form_value,
                                    hostname_uri,
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
                                    hostname_uri,
                                    form_uri,
                                    uuid,
                                    None)
        except Exception as e:
            Logger.error("ProxyExtension::SaveCredentials(): %s", e)

    def SetAuthForms(self, userform, username):
        """
            Get password forms
            @param userform as str
        """
        try:
            collection = self.__page.get_dom_document().get_forms()
            elements = []
            for i in range(0, collection.get_length()):
                elements.append(collection.item(i))
            (forms, textareas) = self.__form_extension.get_elements(elements)
            for form in forms:
                if form["username"].get_name() == userform:
                    self.__helper.get(self.__form_extension.get_form_uri(form),
                                      userform,
                                      form["password"].get_name(),
                                      self.__form_extension.set_input_forms,
                                      self.__page,
                                      form,
                                      username)
                    return
        except Exception as e:
            Logger.error("ProxyExtension::SetAuthForms(): %s", e)

    def GetScripts(self):
        """
            Get images
            @return [str]
        """
        try:
            return self.__jsblock_extension.scripts
        except Exception as e:
            Logger.error("ProxyExtension::GetScripts(): %s", e)
        return []

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
            Logger.error("ProxyExtension::GetImages(): %s", e)
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
        for uri in self.__send_requests:
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
            Logger.error("ProxyExtension::GetImagesLinks(): %s", e)
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

    def SetPreviousElementValue(self):
        """
            Set focused form to previous value
        """
        if self.__focus_element is None:
            return
        try:
            value = self.__focus_element.get_value().rstrip(" ")
            if self.__focus_element in self.__elements_history.keys():
                current = self.__elements_history[self.__focus_element]
                if current.prev is not None:
                    self.__elements_history[self.__focus_element] =\
                        current.prev
                    self.__focus_element.set_value(current.prev.value)
            elif value:
                next = LinkedList(value, None, None)
                current = LinkedList("", next, None)
                next.set_prev(current)
                self.__elements_history[self.__focus_element] = current
                self.__focus_element.set_value("")
        except Exception as e:
            Logger.error("ProxyExtension::SetPreviousForm(): %s", e)

    def SetNextElementValue(self):
        """
            Set focused form to next value
        """
        if self.__focus_element is None:
            return
        try:
            if self.__focus_element in self.__elements_history.keys():
                current = self.__elements_history[self.__focus_element]
                if current.next is not None:
                    self.__elements_history[self.__focus_element] =\
                        current.next
                    self.__focus_element.set_value(current.next.value)
        except Exception as e:
            Logger.error("ProxyExtension::SetNextForm(): %s", e)

#######################
# PRIVATE             #
#######################
    def __add_event_listeners(self, forms, textareas, webpage):
        """
            Add event listeners on inputs and textareas
            @param forms as {}
            @param textareas as [WebKit2WebExtension.DOMHTMLTextAreaElement]
            @param webpage as WebKit2WebExtension.WebPage
        """
        self.__mouse_down_element = None
        self.__focus_element = None
        self.__elements_history = {}

        parsed = urlparse(webpage.get_uri())

        # Manage forms events
        for form in forms:
            form["username"].add_event_listener("input",
                                                self.__on_input,
                                                False)
            form["username"].add_event_listener("focus",
                                                self.__on_focus,
                                                False)
            form["username"].add_event_listener("blur",
                                                self.__on_blur,
                                                False)
            form["username"].add_event_listener("mousedown",
                                                self.__on_mouse_down,
                                                False)
            # Check for unsecure content
            if parsed.scheme == "http":
                form["password"].add_event_listener("focus",
                                                    self.__on_focus,
                                                    False)
        # Manage textareas events
        for textarea in textareas:
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
            Warn user about a password form on an http page and
            update focused element
            @param element as WebKit2WebExtension.DOMElement
            @param event as WebKit2WebExtension.DOMUIEvent
        """
        self.__focus_element = element
        if isinstance(element, WebKit2WebExtension.DOMHTMLInputElement):
            if element.get_input_type() == "password" and\
                    self.__bus is not None:
                self.__bus.emit_signal(
                    None,
                    PROXY_PATH,
                    self.__proxy_bus,
                    "UnsecureFormFocused",
                    None)

    def __on_blur(self, element, event):
        """
            Loose focus so reset mouse down element
            @param element as WebKit2WebExtension.DOMElement
            @param event as WebKit2WebExtension.DOMUIEvent
        """
        if self.__mouse_down_element == element:
            self.__mouse_down_element = None
        if self.__focus_element == element:
            self.__focus_element = None

    def __on_mouse_down(self, element, event):
        """
           Emit Input mouse down signal
           @param element as WebKit2WebExtension.DOMHTMLInputElement
           @param event as WebKit2WebExtension.DOMUIEvent
        """
        if element.get_name() is None:
            return
        if self.__mouse_down_element != element and\
                self.__bus is not None:
            form_uri = element.get_form().get_action()
            parsed_form_uri = urlparse(form_uri)
            form_uri = "%s://%s" % (parsed_form_uri.scheme,
                                    parsed_form_uri.netloc)
            args = GLib.Variant("(ss)", (element.get_name(), form_uri))
            self.__bus.emit_signal(
                None,
                PROXY_PATH,
                self.__proxy_bus,
                "ShowCredentials",
                args)
        self.__mouse_down_element = element

    def __on_input(self, element, event):
        """
            Run a timeout before saving buffer to history
            @param element as WebKit2WebExtension.DOMElement
            @param event as WebKit2WebExtension.DOMUIEvent
        """
        # input signal does not always work
        self.__focus_element = element
        if self.__on_input_timeout_id is not None:
            GLib.source_remove(self.__on_input_timeout_id)
        self.__on_input_timeout_id = GLib.timeout_add(500,
                                                      self.__on_input_timeout,
                                                      element)

    def __on_input_timeout(self, element):
        """
            Save buffer to history
            @param element as WebKit2WebExtension.DOMElement
        """
        self.__on_input_timeout_id = None
        new_value = element.get_value()
        if new_value is None:
            return
        item = LinkedList("", None, None)
        if element in self.__elements_history.keys():
            item = self.__elements_history[element]
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
        (forms, textareas) = self.__form_extension.get_elements(elements)
        self.__add_event_listeners(forms, textareas, webpage)
        for form in forms:
            self.__form_extension.set_credentials(form, webpage)

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

    def __on_notify_uri(self, webpage, param):
        """
            Reset send requests
            @param webpage as WebKit2WebExtension.WebPage
            @param uri as GObject.ParamSpec
        """
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

    def __init__(self, extension, form_extension, jsblock_extension):
        """
            Init extension
            @param extension as WebKit2WebExtension.WebExtension
            @param form_extension as FormsExtension
            @parma jsblock_extension as JSBlockExtension
        """
        self.__server = None
        extension.connect("page-created",
                          self.__on_page_created,
                          form_extension,
                          jsblock_extension)

#######################
# PRIVATE             #
#######################
    def __on_page_created(self, extension, webpage,
                          form_extension, jsblock_extension):
        """
            Cache webpage
            @param extension as WebKit2WebExtension.WebExtension
            @param webpage as WebKit2WebExtension.WebPage
            @param form_extension as FormsExtension
        """
        self.__server = ProxyExtensionServer(extension,
                                             webpage,
                                             form_extension,
                                             jsblock_extension)
