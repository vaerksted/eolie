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

from gi.repository import Gtk, Gio, WebKit2

from eolie.widget_find import FindWidget
from eolie.widget_uri_label import UriLabelWidget


class OverlayContainer(Gtk.Overlay):
    """
        Overlay management for container
    """

    def __init__(self):
        """
            Init container
        """
        Gtk.Overlay.__init__(self)
        self.__reading_view = None
        self.__find_widget = FindWidget(self._window)
        self.__find_widget.show()
        self.__uri_label = UriLabelWidget()
        self.add_overlay(self.__uri_label)

    def stop_reading(self):
        """
            Destroy reading view
        """
        if self.__reading_view is not None:
            self.__reading_view.destroy()
            self.__reading_view = None

    @property
    def reading(self):
        """
            True if reading
            @return bool
        """
        return self.__reading_view is not None

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
    def __on_readability_content(self, webview, content):
        """
            Show reading view
            @param webview as WebView
            @param content as str
        """
        system = Gio.Settings.new("org.gnome.desktop.interface")
        document_font_name = system.get_value("document-font-name").get_string(
        )
        document_font_size = str(int(document_font_name[-2:]) * 1.3) + "pt"
        if self.__reading_view is None:
            self.__reading_view = WebKit2.WebView.new()
            self.__reading_view.connect("decide-policy",
                                        self.__on_decide_policy)
            self.__reading_view.show()
            self.add_overlay(self.__reading_view)
            html = "<html><head>\
                    <style type='text/css'>\
                    *:not(img) {font-size: %s;\
                        background-color: #333333;\
                        color: #e6e6e6;\
                        margin-left: auto;\
                        margin-right: auto;\
                        width: %s}\
                    </style></head>" % (document_font_size,
                                        self.get_allocated_width() / 1.5)
            html += "<title>%s</title>" % self.__webview.title
            html += content
            html += "</html>"
            self.__reading_view.load_html(html, None)
