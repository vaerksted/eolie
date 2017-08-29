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

from eolie.label_indicator import LabelIndicator
from eolie.define import El, ArtSize


class SitesManagerChild(Gtk.ListBoxRow):
    """
        Child showing snapshot, title and favicon
    """

    def __init__(self, netloc, window):
        """
            Init child
            @param netloc as str
            @param window as Window
        """
        Gtk.ListBoxRow.__init__(self)
        self.__window = window
        self.__netloc = netloc
        self.__views = []
        self.__connected_ids = []
        self.__scroll_timeout_id = None
        self.set_property("has-tooltip", True)
        self.connect("query-tooltip", self.__on_query_tooltip)
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/SitesManagerChild.ui")
        builder.connect_signals(self)
        widget = builder.get_object("widget")
        self.__label = LabelIndicator()
        self.__label.show()
        builder.get_object("grid").add(self.__label)
        self.__image = builder.get_object("image")
        self.__image.set_property("pixel-size", ArtSize.FAVICON)
        self.add(widget)

    def add_view(self, view):
        """
            Add view
            @param view as View
            @param uri as str
        """
        if not self.__views:
            self.__set_initial_artwork(self.__netloc, view.webview.ephemeral)
        if view not in self.__views:
            self.__views.append(view)
        self.update_indicator(view)

    def remove_view(self, view):
        """
            Remove view and destroy self if no more view
            @param view as View
        """
        if view in self.__views:
            self.__views.remove(view)
        self.update_indicator(view)

    def set_favicon(self, surface):
        """
            Set favicon
            @param surface as cairo.Surface
        """
        self.__image.set_from_surface(surface)

    def update_indicator(self, view):
        """
            Update indicator (count and color)
            @param view as View
        """
        i = 0
        unread = False
        for view in self.__views:
            if view.webview.access_time == 0:
                unread = True
            i += 1
        if unread:
            self.__label.show_indicator(True)
        else:
            self.__label.show_indicator(False)
        # We force value to 1, Eolie is going to add a new view
        if i == 0:
            i = 1
        self.__label.set_text(str(i))

    def reset(self, netloc):
        """
            Reset widget to new netloc
            @param netloc as str
        """
        self.__netloc = netloc
        self.__set_initial_artwork(netloc)

    @property
    def empty(self):
        """
            True if no view associated
            @return bool
        """
        return len(self.__views) == 0

    @property
    def views(self):
        """
            Get views
            @return [view]
        """
        return self.__views

    @property
    def netloc(self):
        """
            Get netloc
            @return str
        """
        return self.__netloc

#######################
# PROTECTED           #
#######################
    def _on_button_press_event(self, eventbox, event):
        """
            Hide popover or close view
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        if event.button == 2:
            for view in self.__views:
                self.__window.container.pages_manager.close_view(view)
            return True
        elif event.button == 3:
            from eolie.menu_sites import SitesMenu
            menu = SitesMenu(self.__views, self.__window)
            popover = Gtk.Popover.new_from_model(eventbox, menu)
            popover.set_position(Gtk.PositionType.RIGHT)
            popover.forall(self.__force_show_image)
            popover.show()
            return True

#######################
# PRIVATE             #
#######################
    def __force_show_image(self, widget):
        """
            Little hack to force Gtk.ModelButton to show image
            @param widget as Gtk.Widget
        """
        if isinstance(widget, Gtk.Image):
            GLib.idle_add(widget.show)
        elif hasattr(widget, "forall"):
            GLib.idle_add(widget.forall, self.__force_show_image)

    def __set_initial_artwork(self, uri, ephemeral=False):
        """
            Set initial artwork on widget
            @param uri as str
            @param ephemeral as bool
        """
        artwork = El().art.get_icon_theme_artwork(
                                                 uri,
                                                 ephemeral)
        if artwork is not None:
            self.__image.set_from_icon_name(artwork,
                                            Gtk.IconSize.INVALID)
        else:
            self.__image.set_from_icon_name("applications-internet",
                                            Gtk.IconSize.INVALID)

    def __on_query_tooltip(self, widget, x, y, keyboard, tooltip):
        """
            Show tooltip if needed
            @param widget as Gtk.Widget
            @param x as int
            @param y as int
            @param keyboard as bool
            @param tooltip as Gtk.Tooltip
        """
        tooltip = ""
        for view in self.__views:
            title = view.webview.get_title()
            if not title:
                title = view.webview.get_uri()
            if tooltip:
                tooltip += "\n" + title
            else:
                tooltip += title
        widget.set_tooltip_markup(tooltip)
