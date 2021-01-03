# Copyright (c) 2017-2021 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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


class SmoothProgressBar(Gtk.ProgressBar):
    """
        Gtk.ProgressBar with full progression
        If faction is 0.1 and you set it to 0.5, it will be udpated
        to show all steps
    """

    def __init__(self):
        """
            Init widget
        """
        Gtk.ProgressBar.__init__(self)
        self.__timeout_id = None
        self.set_property("valign", Gtk.Align.END)
        self.get_style_context().add_class("progressbar")

    def set_fraction(self, fraction):
        """
            Set fraction smoothly
            @param fraction as float
        """
        if self.__timeout_id is not None:
            GLib.source_remove(self.__timeout_id)
        self.__set_fraction(fraction)

    def hide(self):
        """
            Hide widget and reset fraction
        """
        Gtk.ProgressBar.hide(self)
        Gtk.ProgressBar.set_fraction(self, 0)
        if self.__timeout_id is not None:
            GLib.source_remove(self.__timeout_id)
            self.__timeout_id = None

#######################
# PRIVATE             #
#######################
    def __set_fraction(self, fraction):
        """
            Set fraction smoothly
            @param fraction as float
        """
        Gtk.ProgressBar.show(self)
        self.__timeout_id = None
        current = self.get_fraction()
        if fraction < current:
            progress = fraction
        else:
            if current > 0.95:
                delta = 1.0 - current
            elif fraction - current > 0.5 or fraction == 1.0:
                delta = (fraction - current) / 10
            else:
                delta = (fraction - current) / 100
            progress = current + delta
        Gtk.ProgressBar.set_fraction(self, progress)
        if progress < 1.0:
            self.__timeout_id = GLib.timeout_add(10,
                                                 self.__set_fraction,
                                                 fraction)
        else:
            self.__timeout_id = GLib.timeout_add(500, self.hide)
