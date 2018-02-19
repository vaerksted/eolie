# Copyright (c) 2017-2018 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from gi.repository import Gtk, WebKit2


class WebViewPopover(Gtk.Popover):
    """
        Show a popover with a webview stack
    """

    def __init__(self, window):
        """
            Init popover
            @param window as Window
        """
        Gtk.Popover.__init__(self)
        self.set_modal(False)
        window.register(self, False)
        self.__window = window
        self.__to_destroy = []
        builder = Gtk.Builder()
        builder.add_from_resource('/org/gnome/Eolie/PopoverWebView.ui')
        builder.connect_signals(self)
        self.__stack = builder.get_object("stack")
        self.__title = builder.get_object("title")
        self.__prev_button = builder.get_object("prev_button")
        self.__next_button = builder.get_object("next_button")
        self.__spinner = builder.get_object("spinner")
        self.__combobox = builder.get_object("combobox")
        self.__label = builder.get_object("label")
        self.add(builder.get_object("widget"))
        self.connect("closed", self.__on_closed)

    def add_view(self, view, destroy):
        """
            Add view to popover
            @param view as View
            @param destroy webview as bool
        """
        size = self.__window.get_size()
        width = min(800, size[0])
        height = min(800, size[1] * 0.9)
        position = len(self.__stack.get_children())
        self.__stack.add(view)
        self.__stack.set_visible_child(view)
        view.webview.connect("close", self.__on_webview_close, destroy)
        view.webview.connect("title-changed", self.__on_webview_title_changed)
        view.webview.connect("load-changed", self.__on_webview_load_changed)
        title = view.webview.title or view.webview.uri or ""
        self.__combobox.append(str(view), title)

        # Setup widget size request
        properties = view.webview.get_window_properties()
        geometry = properties.get_geometry()
        current_width = self.__stack.get_allocated_width()
        current_height = self.__stack.get_allocated_height()
        if geometry.width and current_width < geometry.width:
            current_width = min(width, geometry.width + 50)
        elif current_width < 100:
            current_width = width
        if geometry.height and current_height < geometry.height:
            current_height = min(height, geometry.height + 50)
        elif current_height < 100:
            current_height = height
        self.__stack.set_size_request(current_width, current_height)

        if position == 0:
            self.__label.set_text(title)
            self.__label.show()
            self.__combobox.set_active_id(str(view))
            self.__combobox.hide()
        else:
            self.__label.hide()
            self.__combobox.show()
        if destroy:
            self.__to_destroy.append(view.webview)

    def do_get_preferred_width(self):
        """
            Only accept min width to ellipsize label
        """
        (min, nat) = Gtk.Popover.do_get_preferred_width(self)
        return (min, min)

#######################
# PROTECTED           #
#######################
    def _on_combobox_changed(self, combobox):
        """
            Update visible view
            @param combobox as Gtk.ComboBoxText
        """
        active_id = combobox.get_active_id()
        for child in self.__stack.get_children():
            if str(child) == active_id:
                self.__stack.set_visible_child(child)
                break

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

    def __on_webview_title_changed(self, webview, title):
        """
            Update title if webview is current
            @param webview as WebView
            @param title as str
        """
        # Search previous entry
        position = 0
        for child in self.__stack.get_children():
            if webview.view == child:
                break
            position += 1
        self.__combobox.remove(position)
        self.__combobox.insert(position, str(webview.view), title)
        self.__label.set_text(title)
        view = self.__stack.get_visible_child()
        if view == webview.view:
            self.__combobox.set_active_id(str(view))

    def __on_webview_load_changed(self, webview, event):
        """
            Update spinner
            @param webview as WebView
            @param event as WebKit2.LoadEvent
        """
        if event == WebKit2.LoadEvent.STARTED:
            self.__spinner.start()
        elif event == event == WebKit2.LoadEvent.FINISHED:
            self.__spinner.stop()

    def __on_webview_close(self, webview, destroy):
        """
            Remove view from stack, destroy it if wanted
            @param webview as WebView
            @param destroy as bool
        """
        webview.disconnect_by_func(self.__on_webview_title_changed)
        webview.disconnect_by_func(self.__on_webview_load_changed)
        for view in self.__stack.get_children():
            if view.webview == webview:
                self.__stack.remove(view)
                break
        if self.__stack.get_children():
            pass
        else:
            self.hide()
        if destroy:
            webview.destroy()

    def __on_closed(self, popover):
        """
            Clean up popover
            Remove children
            @param popover as Gtk.Popover
        """
        for view in self.__stack.get_children():
            view.webview.disconnect_by_func(self.__on_webview_title_changed)
            view.webview.disconnect_by_func(self.__on_webview_load_changed)
            view.free_webview()
            self.__stack.remove(view)
        for webview in self.__to_destroy:
            webview.destroy()
        self.__to_destroy = []
