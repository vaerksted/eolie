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


class MessagePopover(Gtk.Popover):
    """
        Show  message
        @warning: will block current execution
    """

    def __init__(self, message, window):
        """
            Init popover
            @param message as str
            @param window as window
        """
        Gtk.Popover.__init__(self)
        self.set_modal(False)
        window.register(self)
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/PopoverJavaScript.ui")
        widget = builder.get_object("widget")
        label = builder.get_object("label")
        image = builder.get_object("image")
        image.set_from_icon_name("dialog-warning-symbolic",
                                 Gtk.IconSize.DIALOG)
        label.set_text(message)
        self.add(widget)
        self.__loop = GLib.MainLoop.new(None, False)
        self.connect("closed", self.__on_closed)

    def popup(self):
        """
            Popup widget and run loop
        """
        Gtk.Popover.popup(self)
        self.__loop.run()

#######################
# PROTECTED           #
#######################

#######################
# PRIVATE             #
#######################
    def __on_closed(self, popover):
        """
            Quit main loop
            @param popover as Gtk.Popover
        """
        self.__loop.quit()
        self.__loop.unref()
