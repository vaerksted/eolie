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

from gi.repository import Gtk, Gdk, GLib, Gio

from eolie.widget_find import FindWidget
from eolie.webview import WebView
from eolie.widget_uri_label import UriLabelWidget
from eolie.define import El


class View(Gtk.Overlay):
    """
        An overlay with a webview and a find widget
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

    def __init__(self, webview, window):
        """
            Init view
            @param webview as WebView
            @param window as window
        """
        Gtk.Overlay.__init__(self)
        self.__reading_view = None
        self._window = window
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
        self.__uri_label = UriLabelWidget()
        self.add_overlay(self.__uri_label)
        if webview.ephemeral:
            image = Gtk.Image.new_from_icon_name("user-not-tracked-symbolic",
                                                 Gtk.IconSize.DIALOG)
            image.set_opacity(0.5)
            image.set_property("halign", Gtk.Align.END)
            image.set_property("valign", Gtk.Align.END)
            image.get_style_context().add_class("image-border")
            image.show()
            self.add_overlay(image)
            self.set_overlay_pass_through(image, True)
        # Connect signals
        self.connect("key-press-event", self.__on_key_press_event)
        webview.connect("mouse-target-changed", self.__on_mouse_target_changed)
        webview.connect("readable", self.__on_readable)

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
            self.__reading_view = WebView.new(self._window)
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

    def free_webview(self):
        """
            Free the webview associated with view
        """
        self.__grid.remove(self.__webview)

    def destroy(self):
        """
            Destroy view and webview
        """
        Gtk.Overlay.destroy(self)
        self.__webview.destroy()

    @property
    def reading(self):
        """
            True if reading
            @return bool
        """
        return self.__reading_view is not None

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
                El().helper.call("SetPreviousForm", None, None, page_id)
            elif event.keyval == Gdk.KEY_Z:
                El().helper.call("SetNextForm", None, None, page_id)

    def __on_mouse_target_changed(self, webview, hit, modifiers):
        """
            Show uri label
            @param webview as WebView
            @param hit as WebKit2.HitTestResult
            @param modifiers as Gdk.ModifierType
        """
        if hit.context_is_link():
            self.__uri_label.set_text(hit.get_link_uri())
            self.__uri_label.show()
        else:
            self.__uri_label.hide()

    def __on_readable(self, webview):
        """
            Show readable button in titlebar
            @param webview as WebView
        """
        if webview.get_mapped():
            self._window.toolbar.title.show_readable_button(True)
