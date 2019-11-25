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

from eolie.define import EolieLoadEvent


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

    def add_webview(self, webview):
        """
            Add view to popover
            @param webview as WebView
        """
        position = len(self.__stack.get_children())
        self.__stack.add(webview)
        self.__stack.set_visible_child(webview)
        webview.connect("close", self.__on_webview_close)
        webview.connect("title-changed", self.__on_webview_title_changed)
        webview.connect("load-changed", self.__on_webview_load_changed)
        title = webview.title or webview.uri or ""
        self.__combobox.append(str(webview), title)

        size = self.__window.get_size()
        width = min(800, size[0] * 0.8)
        height = min(800, size[1] * 0.6)
        self.set_size_request(width, height)

        if position == 0:
            self.__label.set_text(title)
            self.__label.show()
            self.__combobox.set_active_id(str(webview))
            self.__combobox.hide()
        else:
            self.__label.hide()
            self.__combobox.show()

#######################
# PROTECTED           #
#######################
    def _on_combobox_changed(self, combobox):
        """
            Update visible webview
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
        for webview in self.__stack:
            if webview == current:
                break
            child = webview
        return child

    def __get_next_child(self):
        """
            Get next child
            @return webview
        """
        current = self.__stack.get_visible_child()
        at_current = False
        child = None
        for webview in self.__stack:
            if at_current:
                child = webview
                break
            if webview == current:
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
            if webview == child:
                break
            position += 1
        self.__combobox.remove(position)
        self.__combobox.insert(position, str(webview), title)
        self.__label.set_text(title)
        visible = self.__stack.get_visible_child()
        if visible == webview:
            self.__combobox.set_active_id(str(visible))

    def __on_webview_load_changed(self, webview, event):
        """
            Update spinner
            @param webview as WebView
            @param event as EolieLoadEvent
        """
        if event == EolieLoadEvent.STARTED:
            self.__spinner.start()
        elif event == event == EolieLoadEvent.FINISHED:
            self.__spinner.stop()

    def __on_webview_close(self, webview):
        """
            Remove view from stack, destroy it if wanted
            @param webview as WebView
            @param destroy as bool
        """
        webview.disconnect_by_func(self.__on_webview_title_changed)
        webview.disconnect_by_func(self.__on_webview_load_changed)
        for child in self.__stack.get_children():
            if child == webview:
                self.__stack.remove(child)
                break
        if self.__stack.get_children():
            pass
        else:
            self.hide()
        child.destroy()

    def __on_closed(self, popover):
        """
            Clean up popover
            Remove children
            @param popover as Gtk.Popover
        """
        for webview in self.__stack.get_children():
            webview.destroy()
