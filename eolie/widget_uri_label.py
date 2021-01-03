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

from gi.repository import Gtk, Pango, GLib


class UriLabelWidget(Gtk.EventBox):
    """
        Small label trying to not be under mouse pointer
    """

    def __init__(self):
        """
            Init label
        """
        Gtk.EventBox.__init__(self)
        self.__label = Gtk.Label.new()
        self.__label.set_ellipsize(Pango.EllipsizeMode.END)
        self.__label.get_style_context().add_class("urilabel")
        self.__label.show()
        self.add(self.__label)
        self.connect("enter-notify-event", self.__on_enter_notify)

    def set_text(self, text):
        """
            Set label text
            @param text as str
        """
        if text == self.__label.get_text():
            return
        self.set_property("halign", Gtk.Align.END)
        self.set_property("valign", Gtk.Align.END)
        self.__label.get_style_context().add_class("bottom-right")
        self.__label.get_style_context().remove_class("bottom-left")
        self.__label.get_style_context().remove_class("top-left")
        self.__label.set_text(text)

#######################
# PRIVATE             #
#######################
    def __on_enter_notify(self, widget, event):
        """
            Try to go away from mouse cursor
            @param widget as Gtk.Widget
            @param event as Gdk.Event
        """
        GLib.idle_add(self.hide)
        # Move label at the right
        if self.get_property("halign") == Gtk.Align.END:
            self.set_property("halign", Gtk.Align.START)
            self.__label.get_style_context().add_class("bottom-left")
            self.__label.get_style_context().remove_class("bottom-right")
            self.__label.get_style_context().remove_class("top-left")
        # Move label at top
        else:
            self.set_property("halign", Gtk.Align.END)
            self.set_property("valign", Gtk.Align.END)
            self.__label.get_style_context().add_class("top-left")
            self.__label.get_style_context().remove_class("bottom-left")
            self.__label.get_style_context().remove_class("bottom-right")
        GLib.idle_add(self.show)
