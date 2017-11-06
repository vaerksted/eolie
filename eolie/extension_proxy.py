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

from gi.repository import Gio, GLib

from urllib.parse import urlparse

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
    <method name="SetCredentials">
        <arg type="i" name="page_id" direction="in" />
    </method>
    <method name="SetPreviousForm">
    </method>
    <method name="SetNextForm">
    </method>
    <method name="GetAuthForms">
      <arg type="aas" name="forms" direction="in" />
      <arg type="i" name="page_id" direction="in" />
      <arg type="as" name="results" direction="out" />
    </method>
    <method name="SetAuthForms">
      <arg type="s" name="username" direction="in" />
      <arg type="s" name="username" direction="in" />
      <arg type="i" name="page_id" direction="in" />
    </method>
    <method name="GetImages">
      <arg type="i" name="page_id" direction="in" />
      <arg type="as" name="results" direction="out" />
    </method>
    <method name="GetVideos">
      <arg type="i" name="page_id" direction="in" />
      <arg type="aas" name="results" direction="out" />
    </method>
    <method name="GetImageLinks">
      <arg type="i" name="page_id" direction="in" />
      <arg type="as" name="results" direction="out" />
    </method>
    <method name="GetSelection">
      <arg type="i" name="page_id" direction="in" />
      <arg type="s" name="selection" direction="out" />
    </method>

    <signal name='UnsecureFormFocused'>
        <arg type="as" name="forms" direction="out" />
    </signal>
    <signal name='InputMouseDown'>
        <arg type="as" name="forms" direction="out" />
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
        self.__send_requests = []
        self.__current_uri = None
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
            if form.is_edited():
                return True
        return False

    def GetAuthForms(self, forms, page_id):
        """
            Get password forms for page id
            @param forms as [(str, str)]
            @param page id as int
            @return (username_form, password_form) as (str, str)
        """
        try:
            page = self.__extension.get_page(page_id)
            # Needed as DOM may have changed since last load
            self.__forms.update_inputs_list(page)
            if page is None:
                return ("", "", "", "")
            user_form_name = ""
            user_form_value = ""
            pass_form_name = ""
            pass_form_value = ""
            for (name, value) in forms:
                if self.__forms.is_input(name, "password", page):
                    pass_form_name = name
                    pass_form_value = value
                else:
                    user_form_name = name
                    user_form_value = value
            return (user_form_name,
                    user_form_value,
                    pass_form_name,
                    pass_form_value)
        except Exception as e:
            print("ProxyExtension::GetAuthForms():", e)
        return ("", "", "", "")

    def SetAuthForms(self, userform, username, page_id):
        """
            Get password forms for page id
            @param userform as str
            @param page id as int
        """
        try:
            page = self.__extension.get_page(page_id)
            if page is None:
                return
            # Search form
            for form_input in self.__forms.get_form_inputs(page):
                if form_input["username"].get_name() == userform:
                    helper = PasswordsHelper()
                    helper.get(form_input["uri"],
                               userform,
                               form_input["password"].get_name(),
                               self.__forms.set_input_forms,
                               page,
                               form_input,
                               username)
                    return
        except Exception as e:
            print("ProxyExtension::SetAuthForms():", e)

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

    def GetVideos(self, page_id):
        """
            Get videos for page id
            @param page id as int
            @return [str]
        """
        page = self.__extension.get_page(page_id)
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

    def GetSelection(self, page_id):
        """
            Get selected text for page_id
            @param page id as int
            @return str
        """
        webpage = self.__extension.get_page(page_id)
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

    def SetCredentials(self, page_id):
        """
            Set focused form to previous value
            @param page_id as int
        """
        try:
            webpage = self.__extension.get_page(page_id)
            self.__forms.set_credentials(webpage)
        except Exception as e:
            print("ProxyExtension::SetCredentials():", e)

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

    def __on_focus(self, element, event):
        """
            Keep last focused form
            @param element as WebKit2WebExtension.DOMElement
            @param event as WebKit2WebExtension.DOMUIEvent
        """
        self.__focused = element

    def __on_mouse_down(self, form, event):
        """
           Emit Input mouse down signal
           @param form as WebKit2WebExtension.DOMElement
           @param event as WebKit2WebExtension.DOMUIEvent
        """
        name = form.get_name()
        if name is None:
            return
        # Only send signal on one of the two calls
        if name in self.__mouse_down_forms:
            self.__mouse_down_forms.remove(name)
        else:
            self.__mouse_down_forms.append(name)
            args = GLib.Variant.new_tuple(GLib.Variant("s", name))
            self.__bus.emit_signal(
                              None,
                              PROXY_PATH,
                              self.__proxy_bus,
                              "InputMouseDown",
                              args)

    def __on_input(self, form, event):
        """
            Send input signal
            @param form as WebKit2WebExtension.DOMElement
            @param event as WebKit2WebExtension.DOMUIEvent
        """
        new_value = form.get_value()
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
        # Remove any previous event listener
        for form in self.__listened_forms:
            form.remove_event_listener("input", self.__on_input, False)
            form.remove_event_listener("focus", self.__on_focus, False)
            form.remove_event_listener("mousedown",
                                       self.__on_mouse_down,
                                       False)
        for form in self.__password_forms:
            form.remove_event_listener("focus",
                                       self.__on_password_focus,
                                       False)
        self.__focused = None
        self.__form_history = {}
        self.__listened_forms = []
        self.__password_forms = []
        self.__mouse_down_forms = []

        # Manage forms in page
        parsed = urlparse(webpage.get_uri())

        # Check for unsecure content
        if parsed.scheme == "http":
            for form_input in self.__forms.get_form_inputs(webpage):
                self.__password_forms.append(form_input["password"])
                form_input["password"].add_event_listener(
                                        "focus",
                                        self.__on_password_focus,
                                        False)
        # Manage forms input
        for form in self.__forms.get_inputs(webpage) +\
                self.__forms.get_textarea(webpage):
            self.__listened_forms.append(form)
            form.add_event_listener("input", self.__on_input, False)
            form.add_event_listener("focus", self.__on_focus, False)
            form.add_event_listener("mousedown", self.__on_mouse_down, False)

    def __on_page_created(self, extension, webpage):
        """
            Cache webpage
            @param extension as WebKit2WebExtension.WebExtension
            @param page as WebKit2WebExtension.WebPage
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
        webpage.connect("document-loaded", self.__on_document_loaded)
        webpage.connect("send-request", self.__on_send_request)
        webpage.connect("context-menu", self.__on_context_menu)
        self.__extension = extension

    def __on_context_menu(self, webpage, context_menu, hit):
        """
            Add selection to context menu user data
            @param webpage as WebKit2WebExtension.WebPage
            @param context_menu as WebKit2WebExtension.ContextMenu
            @param hit as WebKit2.HitTestResult
        """
        value = self.GetSelection(webpage.get_id())
        context_menu.set_user_data(GLib.Variant("s", value))

    def __on_send_request(self, webpage, request, redirect):
        """
            Keep send requests
            @param webpage as WebKit2WebExtension.WebPage
            @param request as WebKit2.URIRequest
            @param redirect as WebKit2WebExtension.URIResponse
        """
        # Reset send requests if uri changed
        uri = webpage.get_uri()
        if self.__current_uri != uri:
            self.__current_uri = uri
            self.__send_requests = []
        self.__send_requests.append(request.get_uri())
