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

from gi.repository import Gtk, GLib, WebKit2

from eolie.pages_manager_flowbox_child import PagesManagerFlowBoxChild


class PageOverlayChild(PagesManagerFlowBoxChild):
    """
        A movable PagesManagerFlowBoxChild
    """

    __TIMEOUT = 15000

    def __init__(self, view, window):
        """
            Init child
            @param view as View
            @param window as Window
        """
        PagesManagerFlowBoxChild.__init__(self, view, window)
        self.get_style_context().add_class("box-dark-shadow")
        self.set_property("halign", Gtk.Align.START)
        self.set_property("valign", Gtk.Align.END)
        self.show()
        view.webview.connect("destroy", self.__on_webview_destroy)

    def set_view(self, view):
        """
            Set a new view
            @param view as View
        """
        if self.__timeout_id is not None:
            GLib.source_remove(self.__timeout_id)
            self.__timeout_id = None
        self._view.webview.disconnect_by_func(self.__on_webview_destroy)
        view.webview.connect("destroy", self.__on_webview_destroy)
        PagesManagerFlowBoxChild.set_view(self, view)
        self.update()
        self.show()

#######################
# PROTECTED           #
#######################
    def _on_button_press_event(self, eventbox, event):
        """
            Hide popover or close view
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        ret = PagesManagerFlowBoxChild._on_button_press_event(self,
                                                              eventbox,
                                                              event)
        if not ret and event.button == 1:
            self._window.container.set_visible_view(self._view)
            self._window.container.set_expose(False)
            self._window.container.pages_manager.update_visible_child()
            self.hide()
            if self.__timeout_id is not None:
                GLib.source_remove(self.__timeout_id)
                self.__timeout_id = None

    def _on_close_button_press_event(self, eventbox, event):
        """
            Hide self
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        ret = PagesManagerFlowBoxChild._on_close_button_press_event(self,
                                                                    eventbox,
                                                                    event)
        if ret:
            self.hide()
            if self.__timeout_id is not None:
                GLib.source_remove(self.__timeout_id)
                self.__timeout_id = None

    def _on_load_changed(self, webview, event):
        """
            Update widget content
            @param webview as WebView
            @param event as WebKit2.LoadEvent
        """
        PagesManagerFlowBoxChild._on_load_changed(self, webview, event)
        if event == WebKit2.LoadEvent.FINISHED:
            self.__timeout_id = GLib.timeout_add(self.__TIMEOUT,
                                                 self.__hide_timeout)

#######################
# PRIVATE             #
#######################
    def __hide_timeout(self):
        """
            Hide by opacity change
            @param count as int
        """
        self.hide()
        self.__timeout_id = None

    def __on_webview_destroy(self, webview):
        """
            Destroy self and disconnect signals
            @param webview as WebView
        """
        self.disconnect_signals()
