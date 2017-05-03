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

from gi.repository import Gtk


class WebViewPopover(Gtk.Popover):
    """
        Show a popover with a webview stack
    """

    def __init__(self):
        """
            Init popover
        """
        Gtk.Popover.__init__(self)
        builder = Gtk.Builder()
        builder.add_from_resource('/org/gnome/Eolie/PopoverWebView.ui')
        builder.connect_signals(self)
        self.__stack = builder.get_object("stack")
        self.__title = builder.get_object("title")
        self.__prev_button = builder.get_object("prev_button")
        self.__next_button = builder.get_object("next_button")
        self.add(builder.get_object("widget"))
        self.connect("closed", self.__on_closed)

    def add_webview(self, view):
        """
            Add webview to popover
            @param view as View
        """
        self.__stack.add(view)
        self.__stack.set_visible_child(view)
        view.webview.connect("close", self.__on_webview_close)
        self.__set_title()
        self.__set_button_state()

#######################
# PROTECTED           #
#######################
    def _on_prev_clicked(self, button):
        """
            Show previous view
            @param button as Gtk.Button
        """
        previous = self.__get_prev_child()
        self.__stack.set_visible_child(previous)
        self.__set_button_state()
        self.__set_title()

    def _on_next_clicked(self, button):
        """
            Show next view
            @param button as Gtk.Button
        """
        next = self.__get_next_child()
        self.__stack.set_visible_child(next)
        self.__set_button_state()
        self.__set_title()

#######################
# PRIVATE             #
#######################
    def __get_prev_child(self):
        """
            Get previous child
            @return webview
        """
        current = self.__stack.get_visible_child()
        child = None
        for view in self.__stack:
            if view == current:
                break
            child = view
        return child

    def __get_next_child(self):
        """
            Get next child
            @return webview
        """
        current = self.__stack.get_visible_child()
        at_current = False
        child = None
        for view in self.__stack:
            if at_current:
                child = view
                break
            if view == current:
                at_current = True
        return child

    def __set_button_state(self):
        """
            Check if buttons are sensitive
        """
        previous = self.__get_prev_child()
        self.__prev_button.set_sensitive(previous is not None)
        next = self.__get_next_child()
        self.__next_button.set_sensitive(next is not None)

    def __set_title(self):
        """
            Set popover title
        """
        view = self.__stack.get_visible_child()
        if view is not None:
            title = view.webview.get_title()
            if not title:
                title = view.webview.get_uri()
            if title:
                self.__title.set_text(title)

    def __on_webview_close(self, webview):
        """
            Remove view from stack
            @param webview as WebView
        """
        for view in self.__stack.get_children():
            if view.webview == webview:
                self.__stack.remove(view)
                break
        self.__set_button_state()

    def __on_closed(self, popover):
        """
            Remove children
            @param popover as Gtk.Popover
        """
        for view in self.__stack.get_children():
            view.free_webview()
            self.__stack.remove(view)
