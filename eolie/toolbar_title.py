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

from gi.repository import Gtk

from gettext import gettext as _
from urllib.parse import urlparse

from eolie.define import App
from eolie.widget_uri_entry import UriEntry


class ToolbarTitle(Gtk.EventBox):
    """
        Title toolbar
    """

    def __init__(self, window):
        """
            Init toolbar
            @param window as Window
        """
        Gtk.EventBox.__init__(self)
        self.__window = window
        self.__width = -1
        self.connect("enter-notify-event", self.__on_enter_notify_event)
        self.connect("leave-notify-event", self.__on_leave_notify_event)
        self.__entry = UriEntry(window)
        self.__entry.show()
        self.add(self.__entry)

    def start_search(self):
        """
            Focus widget without showing
            popover allowing user to start a search
        """
        if not self.__entry.widget.is_focus():
            self.__entry.widget.grab_focus()

    def show_javascript(self, dialog):
        """
            Show a popover with javascript message
            @param dialog as WebKit2.ScriptDialog
        """
        if dialog.get_message():
            from eolie.popover_javascript import JavaScriptPopover
            popover = JavaScriptPopover(dialog, self.__window)
            popover.set_relative_to(self)
            popover.popup()

    def show_geolocation(self, uri, request):
        """
            Show a popover allowing geolocation
            @param uri as str
            @param request as WebKit2.PermissionRequest
        """
        if App().websettings.allowed_geolocation(uri):
            request.allow()
            self.icons.show_geolocation(True)
        else:
            from eolie.popover_geolocation import GeolocationPopover
            popover = GeolocationPopover(uri, request, self.__window)
            popover.set_relative_to(self)
            popover.popup()

    def show_message(self, message):
        """
            Show a message to user
            @param webview as WebView
            @param msg as str
        """
        from eolie.popover_message import MessagePopover
        popover = MessagePopover(message, self.__window)
        popover.set_relative_to(self)
        popover.popup()

    def show_input_warning(self, webview):
        """
            Show a message to user about password input field over HTTP
            @param webview as WebView
        """
        if self.__input_warning_shown:
            return
        self.__input_warning_shown = True
        self.show_message(_(
            "Heads-up: This page is insecure.\n"
            "If you type your password,\nit will be "
            "visible to cybercriminals!"))

    def do_get_preferred_width(self):
        """
            Fixed preferred width
        """
        if self.__width == -1:
            (min_width, nat_width) = Gtk.Bin.do_get_preferred_width(self)
        else:
            nat_width = self.__width
        return (-1, nat_width)

    def set_width(self, width):
        """
            Set Gtk.Entry width
            @param width as int
        """
        self.__width = width
        self.queue_resize()

    @property
    def entry(self):
        """
            Get entry
            @return UriEntry
        """
        return self.__entry

#######################
# PRIVATE             #
#######################
    def __on_enter_notify_event(self, widget, event):
        """
            Update entry
            @param widget as Gtk.Widget
            @param event as Gdk.Event
        """
        if self.__entry.popover.is_visible():
            return
        uri = self.__window.container.webview.uri
        parsed = urlparse(uri)
        if parsed.scheme in ["http", "https", "file"]:
            self.__entry.set_text_entry(uri)
        else:
            self.__entry.set_default_placeholder()

    def __on_leave_notify_event(self, widget, event):
        """
            Update entry
            @param controller as Gtk.EventControllerMotion
            @param widget as Gtk.Widget
            @param event as Gdk.Event
        """
        if self.__entry.popover.is_visible():
            return
        allocation = widget.get_allocation()
        if event.x <= 0 or\
           event.x >= allocation.width or\
           event.y <= 0 or\
           event.y >= allocation.height:
            self.__entry.placeholder.set_opacity(0.8)
            uri = self.__window.container.webview.uri
            parsed = urlparse(uri)
            if parsed.scheme in ["http", "https", "file"]:
                self.__entry.set_text_entry("")
            else:
                self.__entry.set_default_placeholder()
