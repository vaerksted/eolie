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

from eolie.define import El


class ToolbarTitle(Gtk.Bin):
    """
        Title toolbar
    """

    def __init__(self):
        """
            Init toolbar
        """
        Gtk.Bin.__init__(self)
        builder = Gtk.Builder()
        builder.add_from_resource('/org/gnome/Eolie/ToolbarTitle.ui')
        builder.connect_signals(self)
        self.__entry = builder.get_object('entry')
        self.__reload_image = builder.get_object('reload_image')
        self.add(builder.get_object('widget'))
        self.set_width(400)

    def set_width(self, width):
        """
            Set Gtk.Scale progress width
            @param width as int
        """
        self.set_property("width_request", width)

    def set_uri(self, uri):
        """
            Update entry
            @param text as str
        """
        self.__entry.set_text(uri)

#######################
# PROTECTED           #
#######################
    def _on_reload_press(self, eventbox, event):
        """
            Reload current view
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        El().window.container.current.reload()

    def _on_reload_enter_notify(self, eventbox, event):
        """
            Change opacity
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
            @param image as Gtk.Image
        """
        self.__reload_image.set_opacity(1)

    def _on_reload_leave_notify(self, eventbox, event):
        """
            Change opacity
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
            @param image as Gtk.Image
        """
        self.__reload_image.set_opacity(0.8)

    def _on_activate(self, entry):
        """
            Go to url or search for words
            @param entry as Gtk.Entry
        """
        text = entry.get_text()
        El().window.container.load_uri(text)
#######################
# PRIVATE             #
#######################
