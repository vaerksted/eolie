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

from gi.repository import Gtk

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
        self.__webviews = []
        self.__connected_ids = []
        self.__scroll_timeout_id = None
        self.set_property("has-tooltip", True)
        self.connect("query-tooltip", self.__on_query_tooltip)
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/SitesManagerChild.ui")
        builder.connect_signals(self)
        widget = builder.get_object("widget")
        self.__label = builder.get_object("label")
        self.__image = builder.get_object("image")
        self.__image.set_property("pixel-size", ArtSize.FAVICON)
        self.add(widget)

    def add_webview(self, webview):
        """
            Add webview
            @param webview as WebView
            @param uri as str
        """
        if not self.__webviews:
            self.__set_initial_artwork(self.__netloc, webview.ephemeral)
        if webview not in self.__webviews:
            self.__webviews.append(webview)
        self.update_indicator(webview)

    def remove_webview(self, webview):
        """
            Remove webview and destroy self if no more webview
            @param webview as WebView
        """
        if webview in self.__webviews:
            self.__webviews.remove(webview)
        self.update_indicator(webview)

    def set_favicon(self, surface):
        """
            Set favicon
            @param surface as cairo.Surface
        """
        self.__image.set_from_surface(surface)

    def update_indicator(self, webview):
        """
            Update indicator (count and color)
            @param webview as WebView
        """
        i = 0
        unread = False
        for webview in self.__webviews:
            if webview.access_time == 0:
                unread = True
            i += 1
        if unread:
            self.__label.set_markup("<span color='red'><b>%s</b></span>" % i)
        else:
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
            True if no webview associated
            @return bool
        """
        return len(self.__webviews) == 0

    @property
    def webviews(self):
        """
            Webviews
            @return [WebView]
        """
        return self.__webviews

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

#######################
# PRIVATE             #
#######################
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
        for webview in self.__webviews:
            title = webview.get_title()
            if not title:
                title = webview.get_uri()
            if tooltip:
                tooltip += "\n" + title
            else:
                tooltip += title
        widget.set_tooltip_markup(tooltip)
