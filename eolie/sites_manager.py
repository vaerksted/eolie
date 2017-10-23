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

from gi.repository import Gtk, GLib

from urllib.parse import urlparse

from eolie.sites_manager_child import SitesManagerChild
from eolie.define import El


class SitesManager(Gtk.EventBox):
    """
        Site manager (merged netloc of opened pages)
    """

    def __init__(self, window):
        """
            Init stack
            @param window as Window
        """
        Gtk.EventBox.__init__(self)
        self.__window = window
        self.set_property("width-request", 50)
        self.connect("button-press-event", self.__on_button_press)
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

        self.add(self.__scrolled)

    def add_view_for_uri(self, view, uri):
        """
            Add view for uri
            @param view as View
            @param uri as str
            @param surface as cairo.SurfaceImage
        """
        if uri is None:
            return
        netloc = self.__get_netloc(uri)
        if not netloc:
            netloc = "%s://" % urlparse(uri).scheme

        child = None
        empty_child = None
        # Do not group by netloc
        if view.webview.ephemeral:
            for site in self.__box.get_children():
                if site.ephemeral:
                    child = site
                    break
        else:
            # Search for a child for wanted netloc
            # Clean up any child matching view, allowing us to reuse it
            for site in self.__box.get_children():
                if site.netloc == netloc and site.ephemeral is False:
                    child = site
                else:
                    site.remove_view(view)
                    if site.empty:
                        empty_child = site

        if child is None:
            if empty_child is None:
                child = SitesManagerChild(netloc,
                                          self.__window,
                                          view.webview.ephemeral)
                child.connect("moved", self.__on_moved)
                position = El().settings.get_value(
                                                "sidebar-position").get_int32()
                child.set_minimal(position < 80)
                child.show()
                child.add_view(view)
                self.__box.add(child)
                self.update_visible_child()
            else:
                child = empty_child
                child.reset(netloc)
                child.add_view(view)
        else:
            if empty_child is not None:
                empty_child.destroy()
            child.add_view(view)
            self.update_visible_child()

    def set_favicon(self, view, surface):
        """
            Set favicon for webview
            @param webview as WebView
            @param surface as cairo.Surface
        """
        for child in self.__box.get_children():
            if view in child.views:
                child.set_favicon(surface)

    def set_minimal(self, minimal):
        """
            Set all children as minimal
            @param minimal as bool
        """
        for child in self.__box.get_children():
            child.set_minimal(minimal)

    def update_label(self, view):
        """
            Update label for view
            @param view as View
        """
        for child in self.__box.get_children():
            if view in child.views:
                child.update_label()
                break

    def remove_view(self, view):
        """
            Remove view
            @param view as View
        """
        count = len(self.__box.get_children())
        for site in self.__box.get_children():
            site.remove_view(view)
            if site.empty and count > 1:
                site.destroy()

    def next(self):
        """
            Show next site
        """
        current = None
        children = self.__box.get_children()
        for child in children:
            if child.get_style_context().has_class("sidebar-item-selected"):
                current = child
            child.get_style_context().remove_class("sidebar-item-selected")
        index = current.get_index()
        if index + 1 < len(children):
            next_row = self.__box.get_row_at_index(index + 1)
        else:
            next_row = self.__box.get_row_at_index(0)
        if next_row is not None:
            next_row.get_style_context().add_class("sidebar-item-selected")
            self.__window.container.set_current(next_row.views[0])
            if len(next_row.views) == 1:
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
            if child.get_style_context().has_class("sidebar-item-selected"):
                current = child
            child.get_style_context().remove_class("sidebar-item-selected")
        index = current.get_index()
        if index == 0:
            next_row = self.__box.get_row_at_index(len(children) - 1)
        else:
            next_row = self.__box.get_row_at_index(index - 1)
        if next_row is not None:
            next_row.get_style_context().add_class("sidebar-item-selected")
            self.__window.container.set_current(next_row.views[0])
            if len(next_row.views) == 1:
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
        visible = self.__window.container.current
        uri = visible.webview.get_uri()
        if uri is None:
            return
        ephemeral = visible.webview.ephemeral
        netloc = self.__get_netloc(uri)
        for child in self.__box.get_children():
            if (child.netloc == netloc and
                    not ephemeral and
                    not child.ephemeral) or\
                    (ephemeral and child.ephemeral):
                child.get_style_context().add_class("sidebar-item-selected")
                # Wait loop empty: will fails otherwise if child just created
                GLib.idle_add(self.__scroll_to_child, child)
            else:
                child.get_style_context().remove_class("sidebar-item-selected")

#######################
# PROTECTED           #
#######################


#######################
# PRIVATE             #
#######################
    def __get_netloc(self, uri):
        """
            Calculate netloc
            @param uri as str
        """
        netloc = urlparse(uri).netloc.lstrip("www.")
        if not netloc:
            netloc = "%s://" % urlparse(uri).scheme
        return netloc

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

    def __on_row_activated(self, listbox, child):
        """
            Show wanted expose
            @param listbox as Gtk.ListBox
            @param child as SitesManagerChild
        """
        if self.__window.toolbar.actions.view_button.get_active() and\
                self.__window.container.pages_manager.filter == child.netloc:
            self.__window.toolbar.actions.view_button.set_active(False)
        elif len(child.views) == 1:
            self.__window.toolbar.actions.view_button.set_active(False)
            self.__window.container.set_current(child.views[0], True)
        else:
            if child.ephemeral:
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
