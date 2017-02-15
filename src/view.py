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

from gi.repository import Gtk, GLib, Pango

from eolie.widget_find import FindWidget
from eolie.web_view import WebView


class UriLabel(Gtk.EventBox):
    """
        Small label trying to not be under mouse pointer
    """

    def __init__(self):
        """
            Init label
        """
        Gtk.EventBox.__init__(self)
        self.__label = Gtk.Label()
        self.__label.set_ellipsize(Pango.EllipsizeMode.END)
        self.__label.get_style_context().add_class("urilabel")
        self.__label.show()
        self.add(self.__label)
        self.connect("enter-notify-event", self.__on_enter_notify)

    def set_text(self, text):
        """
            Set label text
            @param text as str
        """
        if text == self.__label.get_text():
            return
        self.set_property("halign", Gtk.Align.START)
        self.set_property("valign", Gtk.Align.END)
        self.__label.get_style_context().remove_class("bottom-right")
        self.__label.get_style_context().add_class("bottom-left")
        self.__label.set_text(text)

#######################
# PRIVATE             #
#######################
    def __on_enter_notify(self, widget, event):
        """
            Try to go away from mouse cursor
            @param widget as Gtk.Widget
            @param event as Gdk.Event
        """
        self.hide()
        # Move label at the right
        if self.get_property("halign") == Gtk.Align.START:
            self.set_property("halign", Gtk.Align.END)
            self.__label.get_style_context().remove_class("bottom-left")
            self.__label.get_style_context().add_class("bottom-right")
        # Move label at top
        else:
            self.set_property("halign", Gtk.Align.START)
            self.set_property("valign", Gtk.Align.START)
            self.__label.get_style_context().add_class("top-left")
            self.__label.get_style_context().remove_class("bottom-right")
        GLib.idle_add(self.show)


class View(Gtk.Overlay):
    """
        A webview with a find widget
    """

    def __init__(self, parent=None, webview=None):
        """
            Init view
            @param as parent as View
            @param webview as WebView
        """
        Gtk.Overlay.__init__(self)
        self.__parent = parent
        if parent is not None:
            parent.connect("destroy", self.__on_parent_destroy)
        if webview is None:
            self.__webview = WebView()
            self.__webview.show()
        else:
            self.__webview = webview
        self.__find_widget = FindWidget(self.__webview)
        self.__find_widget.show()
        grid = Gtk.Grid()
        grid.set_orientation(Gtk.Orientation.VERTICAL)
        grid.add(self.__find_widget)
        grid.add(self.__webview)
        grid.show()
        self.add(grid)
        self.__uri_label = UriLabel()
        self.add_overlay(self.__uri_label)
        self.__webview.connect("mouse-target-changed",
                               self.__on_mouse_target_changed)

    @property
    def parent(self):
        """
            Get parent web view
            @return View/None
        """
        return self.__parent

    @property
    def webview(self):
        """
            Get webview
            @return WebView
        """
        return self.__webview

    @property
    def find_widget(self):
        """
            Get find widget
            @return FindWidget
        """
        return self.__find_widget

#######################
# PRIVATE             #
#######################
    def __on_mouse_target_changed(self, view, hit, modifiers):
        """
            Show uri in title bar
            @param view as WebView
            @param hit as WebKit2.HitTestResult
            @param modifier as Gdk.ModifierType
        """
        if hit.context_is_link():
            self.__uri_label.set_text(hit.get_link_uri())
            self.__uri_label.show()
        else:
            self.__uri_label.hide()

    def __on_parent_destroy(self, view):
        """
            Remove parent
            @param view as WebView
        """
        self.__parent = None
