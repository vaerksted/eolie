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
        self.set_property("width-request", 50)
        # FIXME
        # self.connect("button-press-event", self.__on_button_press)
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
                                           WebKit2.LoadEvent.STARTED)
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

    def set_minimal(self, minimal):
        """
            Set all children as minimal
            @param minimal as bool
        """
        for child in self.__box.get_children():
            child.set_minimal(minimal)

    def update_label(self, webview):
        """
            Update label for view
            @param webview as WebView
        """
        for child in self.__box.get_children():
            for _webview in child.webviews:
                if _webview == webview:
                    child.update_label()
                    return

    def next(self):
        """
            Show next site
        """
        current = None
        children = self.__box.get_children()
        for child in children:
            if child.get_style_context().has_class("item-selected"):
                current = child
            child.get_style_context().remove_class("item-selected")
        index = current.get_index()
        if index + 1 < len(children):
            next_row = self.__box.get_row_at_index(index + 1)
        else:
            next_row = self.__box.get_row_at_index(0)
        if next_row is not None:
            next_row.get_style_context().add_class("item-selected")
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
            if child.get_style_context().has_class("item-selected"):
                current = child
            child.get_style_context().remove_class("item-selected")
        index = current.get_index()
        if index == 0:
            next_row = self.__box.get_row_at_index(len(children) - 1)
        else:
            next_row = self.__box.get_row_at_index(index - 1)
        if next_row is not None:
            next_row.get_style_context().add_class("item-selected")
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
                child.set_selected(True)
                # Wait loop empty: will fails otherwise if child just created
                GLib.idle_add(self.__scroll_to_child, child)
            else:
                child.set_selected(False)

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
        if event not in [WebKit2.LoadEvent.STARTED,
                         WebKit2.LoadEvent.COMMITTED]:
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
            if empty_child is None:
                child = SitesManagerChild(netloc,
                                          self.__window,
                                          webview.is_ephemeral)
                child.connect("moved", self.__on_moved)
                position = App().settings.get_value(
                    "sidebar-position").get_int32()
                child.set_minimal(position < 80)
                child.show()
                child.add_webview(webview)
                self.__box.add(child)
                self.update_visible_child()
            else:
                child = empty_child
                child.reset(netloc)
                child.add_webview(webview)
        else:
            if empty_child is not None:
                empty_child.destroy()
            child.add_webview(webview)
            self.update_visible_child()

    def __on_row_activated(self, listbox, child):
        """
            Show wanted expose
            @param listbox as Gtk.ListBox
            @param child as SitesManagerChild
        """
        if self.__window.toolbar.actions.view_button.get_active() and\
                self.__window.container.pages_manager.filter == child.netloc:
            self.__window.toolbar.actions.view_button.set_active(False)
        elif len(child.webviews) == 1:
            self.__window.toolbar.actions.view_button.set_active(False)
            self.__window.container.set_visible_webview(child.webviews[0])
        else:
            if child.is_ephemeral:
                self.__window.container.pages_manager.set_filter("private://")
            else:
                self.__window.container.pages_manager.set_filter(child.netloc)
            self.__window.toolbar.actions.view_button.set_active(True)

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

    def __on_moved(self, child, netloc, up):
        """
            Move child row
            @param child as SidebarChild
            @param netloc as str
            @param up as bool
        """
        index = self.__get_index(netloc)
        row = self.__box.get_row_at_index(index)
        if row is None:
            return
        self.__box.remove(row)
        child_index = self.__get_index(child.netloc)
        if not up:
            child_index += 1
        self.__box.insert(row, child_index)

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
