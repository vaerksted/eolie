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

from gi.repository import Gtk, Gdk, GLib, Gio, Pango

from eolie.widget_find import FindWidget
from eolie.view_web import WebView
from eolie.define import El


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
        GLib.idle_add(self.hide)
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

    def get_new_webview(ephemeral, window):
        """
            Get a new webview
            @return webview as WebView
            @param window as Window
        """
        if ephemeral:
            return WebView.new_ephemeral(window)
        else:
            return WebView.new(window)

    def __init__(self, webview, parent, window):
        """
            Init view
            @param webview as WebView
            @param as parent as View
            @param window as window
        """
        Gtk.Overlay.__init__(self)
        self.__reading_view = None
        self.__parent = parent
        self.__window = window
        if parent is not None:
            parent.connect("destroy", self.__on_parent_destroy)
        self.__webview = webview
        self.__webview.show()
        self.__find_widget = FindWidget(self.__webview)
        self.__find_widget.show()
        self.__grid = Gtk.Grid()
        self.__grid.set_orientation(Gtk.Orientation.VERTICAL)
        self.__grid.add(self.__find_widget)
        self.__grid.add(self.__webview)
        self.__grid.show()
        self.add(self.__grid)
        self.__uri_label = UriLabel()
        self.add_overlay(self.__uri_label)
        self.connect("key-press-event", self.__on_key_press_event)
        self.__webview.connect("mouse-target-changed",
                               self.__on_mouse_target_changed)

    def switch_read_mode(self):
        """
            Show a readable version of page if available.
            If in read mode, switch back to page
            If force, always go in read mode
            @param force as bool
        """
        system = Gio.Settings.new("org.gnome.desktop.interface")
        document_font_name = system.get_value("document-font-name").get_string(
                                                                              )
        document_font_size = str(int(document_font_name[-2:]) * 1.3) + "pt"
        if self.__reading_view is None:
            self.__reading_view = WebView.new(self.__window)
            self.__reading_view.show()
            self.add_overlay(self.__reading_view)
            if self.__webview.readable_content:
                self.__in_read_mode = True
                html = "<html><head>\
                        <style type='text/css'>\
                        *:not(img) {font-size: %s;\
                            background-color: #333333;\
                            color: #e6e6e6;\
                            margin-left: auto;\
                            margin-right: auto;\
                            width: %s}\
                        </style></head>" % (document_font_size,
                                            self.get_allocated_width() / 1.5)
                html += "<title>%s</title>" % self.__webview.get_title()
                html += self.__webview.readable_content
                html += "</html>"
                GLib.idle_add(self.__reading_view.load_html, html, None)
        else:
            self.__reading_view.destroy()
            self.__reading_view = None

    def set_parent(self, view):
        """
            Set parent
            @param view as View
        """
        self.__parent = view

    def free_webview(self):
        """
            Free the webview associated with view
        """
        self.__grid.remove(self.__webview)

    @property
    def reading(self):
        """
            True if reading
            @return bool
        """
        return self.__reading_view is not None

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
    def __on_key_press_event(self, widget, event):
        """
            Handle Ctrl+Z and Ctrl+Shift+Z (forms undo/redo)
            @param widget as Gtk.Widget
            @param event as Gdk.Event
        """
        page_id = self.webview.get_page_id()
        if event.state & Gdk.ModifierType.CONTROL_MASK:
            if event.keyval == Gdk.KEY_z:
                El().helper.call("SetPreviousForm", None, None, None, page_id)
            elif event.keyval == Gdk.KEY_Z:
                El().helper.call("SetNextForm", None, None, None, page_id)

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
