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
        self.__x_root = 0
        self.__moved = False
        self.__timeout_id = None
        self.__destroyed_id = None
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
        if self.__destroyed_id is not None:
            self._view.webview.disconnect(self.__destroyed_id)
        PagesManagerFlowBoxChild.set_view(self, view)
        self.__destroyed_id = view.webview.connect("destroy",
                                                   self.__on_webview_destroy)
        self.update()
        self.show()

#######################
# PROTECTED           #
#######################
    def _on_button_press_event(self, eventbox, event):
        """
            Hide popover or close view
            @param eventbox as Gtk.EventBox
            @param event as Gdk.EventButton
        """
        self.__moved = False
        self._widget.connect("motion-notify-event",
                             self.__on_motion_notify_event)
        self.__x_root = event.x
        PagesManagerFlowBoxChild._on_button_press_event(self,
                                                        eventbox,
                                                        event)

    def _on_button_release_event(self, eventbox, event):
        """
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        self._widget.disconnect_by_func(self.__on_motion_notify_event)
        ret = PagesManagerFlowBoxChild._on_button_release_event(self,
                                                                eventbox,
                                                                event)
        if not self.__moved and not ret:
            if event.button == 1:
                self._window.container.set_visible_view(self._view)
                self._window.container.set_expose(False)
                self._window.container.pages_manager.update_visible_child()
                self.hide()
                if self.__destroyed_id is not None:
                    self._view.webview.disconnect(self.__destroyed_id)
                    self.__destroyed_id = None
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
            GLib.idle_add(self.hide)
            if self.__destroyed_id is not None:
                self._view.webview.disconnect(self.__destroyed_id)
                self.__destroyed_id = None
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
        GLib.idle_add(self.hide)
        if self.__destroyed_id is not None:
            self._view.webview.disconnect(self.__destroyed_id)
            self.__destroyed_id = None
        self.__timeout_id = None

    def __on_motion_notify_event(self, eventbox, event):
        """
            Move widget
            @param eventbox as Gtk.EventBox
            @param event as Gdk.EventMotion
        """
        self.__moved = True
        if event.x_root > self.__x_root:
            self.set_property("halign", Gtk.Align.END)
        else:
            self.set_property("halign", Gtk.Align.START)
        self.__x_root = event.x_root

    def __on_webview_destroy(self, webview):
        """
            Destroy self and disconnect signals
            @param webview as WebView
        """
        self.__destroyed_id = None
        self.disconnect_signals()
        if webview == self._view.webview:
            self.hide()
