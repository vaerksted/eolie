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

from gi.repository import Gtk, Pango

from eolie.define import MARGIN_SMALL, EolieLoadEvent
from eolie.helper_signals import SignalsHelper, signals
from eolie.utils import on_query_tooltip


class PagesManagerRowText(Gtk.ListBoxRow, SignalsHelper):
    """
        Text row for PagesManagerList
    """

    @signals
    def __init__(self, webview, window):
        """
            Init widget
            @param webview as WebView
            @param window as Window
        """
        Gtk.ListBoxRow.__init__(self)
        eventbox = Gtk.EventBox()
        eventbox.show()
        self.__webview = webview
        self.__window = window
        self.__label = Gtk.Label.new(webview.title)
        self.__label.set_property("valign", Gtk.Align.CENTER)
        self.__label.set_ellipsize(Pango.EllipsizeMode.END)
        self.__label.set_hexpand(True)
        self.__label.set_xalign(0)
        self.__label.show()
        button = Gtk.Button.new_from_icon_name("window-close-symbolic",
                                               Gtk.IconSize.MENU)
        button.set_relief(Gtk.ReliefStyle.NONE)
        button.get_style_context().add_class("no-border-button")
        button.set_property("valign", Gtk.Align.CENTER)
        button.set_property("halign", Gtk.Align.END)
        button.connect("clicked", self.__on_button_clicked)
        button.show()
        grid = Gtk.Grid()
        grid.show()
        grid.set_column_spacing(MARGIN_SMALL)
        grid.set_row_spacing(MARGIN_SMALL)
        grid.add(self.__label)
        grid.add(button)
        self.add(grid)
        self.__label.set_property("has-tooltip", True)
        self.__label.connect("query-tooltip", on_query_tooltip)
        if True:
            self.get_style_context().add_class("sidebar-item")
            self.__label.get_style_context().add_class("sidebar-item-title")
        else:
            self.get_style_context().add_class("page-child-row")
        return [
            (webview, "title-changed", "_on_webview_title_changed"),
            (webview, "load-changed", "_on_webview_load_changed")
        ]

    @property
    def webview(self):
        """
            Get associated webview
            @return WebView
        """
        return self.__webview

#######################
# PROTECTED           #
#######################
    def _on_webview_load_changed(self, webview, event):
        """
            Update widget content
            @param webview as WebView
            @param event as EolieLoadEvent
        """
        if event in [EolieLoadEvent.STARTED,
                     EolieLoadEvent.COMMITTED]:
            uri = webview.get_uri()
            if uri is not None:
                self.__label.set_text(uri)

    def _on_webview_title_changed(self, webview, title):
        """
            Update title
            @param webview as WebView
            @param title as str
        """
        self.__label.set_text(title)

#######################
# PRIVATE             #
#######################
    def __on_button_clicked(self, button):
        """
            Close view
            @param button as Gtk.Button
        """
        self.__window.container.try_close_webview(self.__webview)
        self.destroy()
