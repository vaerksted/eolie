# Copyright (c) 2014-2016 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from eolie.widget_find import FindWidget
from eolie.web_view import WebView


class View(Gtk.Grid):
    """
        A webview with a find widget
    """

    def __init__(self, parent=None, webview=None):
        """
            Init view
            @param as parent as View
            @param webview as WebView
        """
        Gtk.Grid.__init__(self)
        self.__parent = parent
        if parent is not None:
            parent.connect("destroy", self.__on_parent_destroy)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        if webview is None:
            self.__webview = WebView()
            self.__webview.show()
        else:
            self.__webview = webview
        self.__find_widget = FindWidget(self.__webview)
        self.__find_widget.show()
        self.add(self.__find_widget)
        self.add(self.__webview)

    @property
    def parent(self):
        """
            Get parent web view
            @return View/None
        """
        return self.__parent

    @property
    def webview(self):
        """
            Get webview
            @return WebView
        """
        return self.__webview

    @property
    def find_widget(self):
        """
            Get find widget
            @return FindWidget
        """
        return self.__find_widget

#######################
# PRIVATE             #
#######################
    def __on_parent_destroy(self, view):
        """
            Remove parent
            @param view as WebView
        """
        self.__parent = None
