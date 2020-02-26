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

from gi.repository import Gtk, Gdk

from math import pi


class LabelIndicator(Gtk.Label):
    """
        Label with an indicator
    """

    def __init__(self, is_count):
        """
            Init label
            @param count as bool
        """
        Gtk.Label.__init__(self)
        self.set_size_request(8, 5)
        if is_count:
            self.__margin = 0
            self.get_style_context().add_class("text-x-small")
        else:
            self.__margin = 10
        self.set_xalign(0.0)
        self.set_yalign(1)
        self.__count = 0
        self.__unshown = []

    def add(self):
        """
            Add to count
        """
        self.__count += 1
        self.__update_count()

    def remove(self):
        """
            Remove from count
        """
        self.__count -= 1
        self.__update_count()

    def mark(self, webview):
        """
            Mark view as show or unshown
            @param webview as WebView
        """
        if webview.shown and webview in self.__unshown:
            self.__unshown.remove(webview)
        elif not webview.shown and webview not in self.__unshown:
            self.__unshown.append(webview)
        self.queue_draw()

    def do_get_preferred_width(self):
        """
            Add circle width
        """
        (min, nat) = Gtk.Label.do_get_preferred_width(self)
        return (min + self.__margin, nat + self.__margin)

    def do_draw(self, cr):
        """
            Draw indicator and label
            @param cr as cairo.Context
        """
        Gtk.Label.do_draw(self, cr)
        if self.__unshown:
            w = self.get_allocated_width()
            cr.stroke()
            cr.translate(w - 4, 3)
            cr.set_line_width(1)
            Gdk.cairo_set_source_color(cr, Gdk.Color.parse("red")[1])
            cr.arc(0, 0, 2, 0, 2 * pi)
            cr.stroke_preserve()
            Gdk.cairo_set_source_color(cr, Gdk.Color.parse("red")[1])
            cr.fill()

#######################
# PRIVATE             #
#######################
    def __update_count(self):
        """
            Update view count
        """
        count = max(1, self.__count)
        if count == 1:
            self.set_text(" ")
        else:
            self.set_text(str(count))
