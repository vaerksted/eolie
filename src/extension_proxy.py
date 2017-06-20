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

from eolie.define import PROXY_BUS, PROXY_PATH
from eolie.list import LinkedList


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


class ProxyExtension(Server):
    '''
    <!DOCTYPE node PUBLIC
    '-//freedesktop//DTD D-BUS Object Introspection 1.0//EN'
    'http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd'>
    <node>
    <interface name="org.gnome.Eolie.Proxy">

    <method name="FormsFilled">
        <arg type="i" name="page_id" direction="in" />
        <arg type="b" name="results" direction="out" />
    </method>
    <method name="SetPreviousForm">
    </method>
    <method name="SetNextForm">
    </method>
    <method name="GetAuthForms">
      <arg type="as" name="forms" direction="in" />
      <arg type="i" name="page_id" direction="in" />
      <arg type="as" name="results" direction="out" />
    </method>
    <method name="GetImages">
      <arg type="i" name="page_id" direction="in" />
      <arg type="as" name="results" direction="out" />
    </method>
    <method name="GetImageLinks">
      <arg type="i" name="page_id" direction="in" />
      <arg type="as" name="results" direction="out" />
    </method>

    <signal name='UnsecureFormFocused'>
    </signal>
    <signal name='VideoInPage'>
        <arg type="as" name="results" direction="out" />
    </signal>
    </interface>
    </node>
    '''

    def __init__(self, extension, forms):
        """
            Init server
            @param extension as WebKit2WebExtension.WebExtension
            @param forms as FormsExtension
        """
        self.__proxy_bus = None
        self.__forms = forms
        self.__focused = None
        self.__form_history = {}
        self.__password_forms = []
        self.__listened_forms = []
        extension.connect("page-created", self.__on_page_created)
        self.__bus = None

    def FormsFilled(self, page_id):
        """
            True if form contains data
            @param page_id as int
        """
        page = self.__extension.get_page(page_id)
        forms = self.__forms.get_textarea_forms(page)

        # Check for unsecure content
        for form in forms:
            value = form.get_value()
            default = form.get_default_value()
            if value is not None and value != default and len(value) > 30:
                return True
        return False

    def GetAuthForms(self, forms, page_id):
        """
            Get password forms for page id
            @param forms as [str]
            @param page id as int
            @return (username_form, password_form) as (str, str)
        """
        try:
            page = self.__extension.get_page(page_id)
            if page is None:
                return ("", "", "", "")
            (username, password) = self.__forms.get_auth_forms(forms, page)
            if username is not None and password is not None:
                return (username.get_value(),
                        username.get_name(),
                        password.get_value(),
                        password.get_name())
        except Exception as e:
            print("ProxyExtension::GetAuthForms():", e)
        return ("", "", "", "")

    def GetImages(self, page_id):
        """
            Get images for page id
            @param page id as int
            @return [str]
        """
        try:
            page = self.__extension.get_page(page_id)
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

    def GetImageLinks(self, page_id):
        """
            Get image links for page id
            @param page id as int
            @return [str]
        """
        try:
            page = self.__extension.get_page(page_id)
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

    def SetPreviousForm(self):
        """
            Set focused form to previous value
        """
        if self.__focused is None:
            return
        try:
            if self.__focused in self.__form_history.keys():
                current_value = self.__focused.get_value()
                item = self.__form_history[self.__focused]
                # User added some text, keep it
                if item.value != current_value:
                    next = LinkedList(current_value.rstrip(" "), None, item)
                    if item is not None:
                        item.set_next(next)
                    item = next
                if item.prev:
                    self.__form_history[self.__focused] = item.prev
                    self.__focused.set_value(item.prev.value)
            else:
                new_value = self.__focused.get_value().rstrip(" ")
                if new_value:
                    item = LinkedList(new_value, None, None)
                    next = LinkedList("", item, None)
                    self.__form_history[self.__focused] = next
                    self.__focused.set_value("")
        except Exception as e:
            print("ProxyExtension::SetPreviousForm():", e)

    def SetNextForm(self):
        """
            Set focused form to next value
        """
        if self.__focused is None:
            return
        try:
            if self.__focused in self.__form_history.keys():
                item = self.__form_history[self.__focused]
                if item.next:
                    self.__form_history[self.__focused] = item.next
                    self.__focused.set_value(item.next.value)
        except Exception as e:
            print("ProxyExtension::SetNextForm():", e)

#######################
# PRIVATE             #
#######################
    def __on_password_focus(self, password, event):
        """
            Emit unsecure focus form signal
            @param password as WebKit2WebExtension.DOMElement
            @param event as WebKit2WebExtension.DOMUIEvent
        """
        self.__bus.emit_signal(
                          None,
                          PROXY_PATH,
                          self.__proxy_bus,
                          "UnsecureFormFocused",
                          None)

    def __on_focus(self, form, event):
        """
            Emit unsecure focus form signal
            @param form as WebKit2WebExtension.DOMElement
            @param event as WebKit2WebExtension.DOMUIEvent
        """
        self.__focused = form

    def __on_input(self, form, event):
        """
            Send input signal
            @param form as WebKit2WebExtension.DOMElement
            @param event as WebKit2WebExtension.DOMUIEvent
        """
        # Clear history if nothing and return
        new_value = form.get_value()
        if not new_value:
            if form in self.__form_history.keys():
                del self.__form_history[form]
            return

        previous_value = ""
        item = LinkedList("", None, None)
        if form in self.__form_history.keys():
            item = self.__form_history[form]
            previous_value = item.value
        # Here we try to get words
        # If we are LTR then add words on space
        if len(new_value) > len(previous_value):
            if new_value.endswith(" "):
                next = LinkedList(new_value.rstrip(" "), None, item)
                if item is not None:
                    item.set_next(next)
                self.__form_history[form] = next

    def __on_document_loaded(self, webpage):
        """
            Check for unsecure content
            @param webpage as WebKit2WebExtension.WebPage
        """
        # Create proxy if None
        if self.__proxy_bus is None:
            self.__proxy_bus = PROXY_BUS % webpage.get_id()
            self.__bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            Gio.bus_own_name_on_connection(self.__bus,
                                           self.__proxy_bus,
                                           Gio.BusNameOwnerFlags.NONE,
                                           None,
                                           None)
            Server.__init__(self, self.__bus, PROXY_PATH)
        # Remove any previous event listener
        for form in self.__listened_forms:
            form.remove_event_listener("input", self.__on_input, False)
            form.remove_event_listener("focus", self.__on_input, False)
        for form in self.__password_forms:
            form.remove_event_listener("focus",
                                       self.__on_password_focus,
                                       False)
        self.__focused = None
        self.__form_history = {}
        self.__listened_forms = []
        self.__password_forms = []

        # Manage forms in page
        parsed = urlparse(webpage.get_uri())
        forms = self.__forms.get_textarea_forms(webpage)

        # Check for unsecure content
        for form in forms:
            if isinstance(form, WebKit2WebExtension.DOMHTMLInputElement) and\
                    parsed.scheme == "http" and\
                    form.get_input_type() == "password":
                self.__password_forms.append(form)
                form.add_event_listener("focus",
                                        self.__on_password_focus,
                                        False)
            else:
                self.__listened_forms.append(form)
                form.add_event_listener("input", self.__on_input, False)
                form.add_event_listener("focus", self.__on_focus, False)

    def __on_page_created(self, extension, webpage):
        """
            Cache webpage
            @param extension as WebKit2WebExtension.WebExtension
            @param page as WebKit2WebExtension.WebPage
        """
        webpage.connect("document-loaded", self.__on_document_loaded)
        webpage.connect("send-request", self.__on_send_request)
        self.__extension = extension

    def __on_send_request(self, webpage, request, redirect):
        """
            Search for video in page
            @param webpage as WebKit2WebExtension.WebPage
            @param request as WebKit2.URIRequest
            @param redirect as WebKit2WebExtension.URIResponse
        """
        extensions = ["avi", "flv", "mp4", "mpg", "mpeg", "webm"]
        uri = request.get_uri()
        parsed = urlparse(uri)
        # Search for video in page
        if parsed.path.split(".")[-1] in extensions:
            title = parsed.path.split("/")[-1]
            args = GLib.Variant.new_tuple(GLib.Variant("s", uri),
                                          GLib.Variant("s", title),
                                          GLib.Variant("i", webpage.get_id()))
            self.__bus.emit_signal(
                          None,
                          PROXY_PATH,
                          self.__proxy_bus,
                          "VideoInPage",
                          args)
        elif parsed.netloc.endswith("googlevideo.com") and\
                parsed.path == "/videoplayback":
            title = webpage.get_dom_document().get_title()
            if title is None:
                title = uri
            args = GLib.Variant.new_tuple(GLib.Variant("s", uri),
                                          GLib.Variant("s", title),
                                          GLib.Variant("i", webpage.get_id()))
            self.__bus.emit_signal(
                          None,
                          PROXY_PATH,
                          self.__proxy_bus,
                          "VideoInPage",
                          args)
