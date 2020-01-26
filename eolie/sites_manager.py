# Copyright (c) 2017-2020 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from gi.repository import Gtk, Gdk, GLib, WebKit2

from eolie.sites_manager_child import SitesManagerChild
from eolie.define import App, LoadingType, MARGIN_SMALL
from eolie.utils import get_safe_netloc, update_popover_internals


class SitesManager(Gtk.Grid):
    """
        Site manager (merged netloc of opened pages)
    """

    def __init__(self, window):
        """
            Init stack
            @param window as Window
        """
        Gtk.Grid.__init__(self)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.__window = window
        self.__initial_sort = []
        self.__show_labels = False
        self.set_property("width-request", 50)
        self.get_style_context().add_class("sidebar")
        self.__scrolled = Gtk.ScrolledWindow()
        self.__scrolled.set_policy(Gtk.PolicyType.NEVER,
                                   Gtk.PolicyType.AUTOMATIC)
        self.__scrolled.set_vexpand(True)
        self.__scrolled.set_hexpand(True)
        self.__scrolled.show()
        viewport = Gtk.Viewport()
        viewport.show()
        self.__scrolled.add(viewport)
        self.set_hexpand(False)

        self.__box = Gtk.ListBox.new()
        self.__box.set_activate_on_single_click(True)
        self.__box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.__box.set_margin_start(2)
        self.__box.set_margin_end(2)
        self.__box.set_margin_top(2)
        self.__box.set_margin_bottom(2)
        self.__box.show()
        self.__box.connect("row-activated", self.__on_row_activated)

        viewport.set_property("valign", Gtk.Align.START)
        viewport.add(self.__box)

        menu_button = Gtk.Button.new_from_icon_name(
            "view-more-horizontal-symbolic", Gtk.IconSize.BUTTON)
        menu_button.show()
        menu_button.get_style_context().add_class("overlay-button")
        menu_button.set_property("margin", MARGIN_SMALL)
        menu_button.connect("clicked", self.__on_menu_button_clicked)

        self.add(self.__scrolled)
        self.add(menu_button)

    def add_webview(self, webview):
        """
            Add a new web view to monitor
            @param webview as WebView
        """
        # Force update
        if webview.uri:
            self.__on_webview_load_changed(webview,
                                           WebKit2.LoadEvent.COMMITTED)
        webview.connect("load-changed", self.__on_webview_load_changed)
        webview.connect("destroy", self.__on_webview_destroy)

    def remove_webview(self, webview):
        """
            Remove web view from pages manager
            @param webview as WebView
        """
        count = len(self.__box.get_children())
        for site in self.__box.get_children():
            site.remove_webview(webview)
            if site.empty and count > 1:
                site.destroy()
        webview.disconnect_by_func(self.__on_webview_load_changed)
        webview.disconnect_by_func(self.__on_webview_destroy)

    def next(self):
        """
            Show next site
        """
        current = None
        children = self.__box.get_children()
        for child in children:
            if child.self.get_state_flags() & Gtk.StateFlags.VISITED:
                current = child
            child.unset_state_flags(Gtk.StateFlags.VISITED)
        index = current.get_index()
        if index + 1 < len(children):
            next_row = self.__box.get_row_at_index(index + 1)
        else:
            next_row = self.__box.get_row_at_index(0)
        if next_row is not None:
            next_row.set_state_flags(Gtk.StateFlags.VISITED, False)
            self.__window.container.set_visible_webview(next_row.webviews[0])
            if len(next_row.webviews) == 1:
                self.__window.container.set_expose(False)
            else:
                self.__window.container.pages_manager.set_filter(
                    next_row.netloc)
                self.__window.container.set_expose(True)

    def previous(self):
        """
            Show previous site
        """
        current = None
        children = self.__box.get_children()
        for child in children:
            if child.self.get_state_flags() & Gtk.StateFlags.VISITED:
                current = child
            child.unset_state_flags(Gtk.StateFlags.VISITED)
        index = current.get_index()
        if index == 0:
            next_row = self.__box.get_row_at_index(len(children) - 1)
        else:
            next_row = self.__box.get_row_at_index(index - 1)
        if next_row is not None:
            next_row.set_state_flags(Gtk.StateFlags.VISITED, False)
            self.__window.container.set_visible_webview(next_row.webviews[0])
            if len(next_row.webviews) == 1:
                self.__window.container.set_expose(False)
            else:
                self.__window.container.pages_manager.set_filter(
                    next_row.netloc)
                self.__window.container.set_expose(True)

    def update_visible_child(self):
        """
            Mark current child as visible
            Unmark all others
        """
        current = self.__window.container.webview
        for child in self.__box.get_children():
            if current in child.webviews:
                child.set_state_flags(Gtk.StateFlags.VISITED, False)
                child.update_favicon()
                # Wait loop empty: will fails otherwise if child just created
                GLib.idle_add(self.__scroll_to_child, child)
            else:
                child.unset_state_flags(Gtk.StateFlags.VISITED)

    def set_initial_sort(self, sort):
        """
            Set initial site sort
            @param sort as [str]
        """
        if sort:
            self.__box.set_sort_func(self.__sort_func)
        else:
            self.__box.set_sort_func(None)
        self.__initial_sort = sort

    def update_shown_state(self, webview):
        """
            Update shown state for webview
            @param webview as WebView
        """
        for child in self.__box.get_children():
            for _webview in child.webviews:
                if _webview == webview:
                    child.indicator_label.mark(webview)
                    return

    def show_labels(self, show):
        """
            Show labels on children
            @param show as bool
        """
        self.__show_labels = show
        for child in self.__box.get_children():
            child.show_label(show)

    @property
    def sort(self):
        """
            Get current sort
            @return [str]
        """
        sort = []
        for child in self.__box.get_children():
            sort.append(child.netloc)
        return sort

#######################
# PRIVATE             #
#######################
    def __sort_func(self, row1, row2):
        """
            Sort rows based on inital sort
            @param row1 as Gtk.ListBoxRow
            @param row2 as Gtk.ListBoxRow
        """
        try:
            index1 = self.__initial_sort.index(row1.netloc)
            index2 = self.__initial_sort.index(row2.netloc)
            return index1 > index2
        except:
            return False

    def __get_index(self, netloc):
        """
            Get child index
            @param netloc as str
            @return int
        """
        # Search current index
        children = self.__box.get_children()
        index = 0
        for child in children:
            if child.netloc == netloc:
                break
            index += 1
        return index

    def __scroll_to_child(self, child):
        """
            Scroll to child
            @param child as SitesManagerChild
        """
        adj = self.__scrolled.get_vadjustment()
        if adj is None:
            return
        value = adj.get_value()
        coordinates = child.translate_coordinates(self.__box, 0, 0)
        if coordinates is None:
            return
        y = coordinates[1]
        if y + child.get_allocated_height() >\
                self.__scrolled.get_allocated_height() + value or\
                y - child.get_allocated_height() < 0 + value:
            self.__scrolled.get_vadjustment().set_value(y)

    def __on_webview_destroy(self, webview):
        """
            Clean children
            @param webview as WebView
        """
        self.remove_webview(webview)

    def __on_webview_load_changed(self, webview, event):
        """
            Update children
            @param webview as WebView
            @param event as WebKit2.LoadEvent
        """
        if event != WebKit2.LoadEvent.COMMITTED:
            return
        netloc = get_safe_netloc(webview.uri)
        child = None
        empty_child = None
        # Do not group by netloc
        if webview.is_ephemeral:
            for site in self.__box.get_children():
                if site.is_ephemeral:
                    child = site
                    break
        else:
            # Search for a child for wanted netloc
            # Clean up any child matching webview, allowing us to reuse it
            for site in self.__box.get_children():
                if site.netloc == netloc and site.is_ephemeral is False:
                    child = site
                else:
                    site.remove_webview(webview)
                    if site.empty:
                        empty_child = site

        if child is None:
            # We need to create a new child
            if empty_child is None:
                child = SitesManagerChild(netloc,
                                          self.__window,
                                          webview.is_ephemeral)
                child.show()
                child.add_webview(webview)
                child.show_label(self.__show_labels)
                self.__box.add(child)
                self.update_visible_child()
            # Use empty child
            else:
                child = empty_child
                child.reset(netloc)
                child.add_webview(webview)
        # We already have a child for this netloc
        else:
            # Webview previous child is empty, destroy it
            if empty_child is not None:
                empty_child.destroy()
            child.add_webview(webview)
            self.update_visible_child()
        # Webview really loaded
        if webview.get_uri() is not None:
            child.on_webview_load_changed(webview, event)

    def __on_row_activated(self, listbox, child):
        """
            Show wanted expose
            @param listbox as Gtk.ListBox
            @param child as SitesManagerChild
        """
        webviews = child.webviews
        if len(webviews) == 1:
            self.__window.container.set_visible_webview(webviews[0])
        else:
            from eolie.pages_manager_list import PagesManagerList
            widget = PagesManagerList(self.__window)
            widget.show()
            widget.populate(webviews)
            popover = Gtk.Popover.new(child)
            popover.set_modal(False)
            self.__window.register(popover)
            popover.get_style_context().add_class("box-shadow")
            popover.set_position(Gtk.PositionType.RIGHT)
            popover.add(widget)
            popover.popup()

    def __on_button_press(self, widget, event):
        """
            Hide popover if visible
            @param widget as Gtk.Widget
            @param event as Gdk.EventButton
        """
        if event.type == Gdk.EventType._2BUTTON_PRESS:
            self.__window.container.add_webview(App().start_page,
                                                LoadingType.FOREGROUND)
        return self.__window.close_popovers()

    def __on_menu_button_clicked(self, button):
        """
            Show pages menu
            @param button as Gtk.Button
        """
        self.__window.close_popovers()
        popover = Gtk.Popover.new_from_model(button, App().pages_menu)
        popover.set_modal(False)
        self.__window.register(popover)
        popover.forall(update_popover_internals)
        popover.popup()
