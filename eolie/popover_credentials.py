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

from gi.repository import Gtk

from urllib.parse import urlparse


class CredentialsPopover(Gtk.Popover):
    """
        Tell user to save form credentials
    """

    def __init__(self, window):
        """
            Init popover
            @param window as Window
        """
        Gtk.Popover.__init__(self)
        self.__webview = window.container.webview
        self.set_modal(False)
        window.register(self)
        builder = Gtk.Builder()
        builder.add_from_resource('/org/gnome/Eolie/PopoverCredentials.ui')
        builder.connect_signals(self)
        self.__label = builder.get_object('label')
        parsed = urlparse(self.__webview.credentials_uri)
        builder.get_object('uri').set_text(parsed.netloc)
        self.add(builder.get_object('widget'))

#######################
# PROTECTED           #
#######################
    def _on_cancel_button_clicked(self, button):
        """
            Close popover
            @param button as Gtk.Button
        """
        self.popdown()

    def _on_save_button_clicked(self, button):
        """
            Save user_form_name and pass_form_name
            @param button as Gtk.Button
        """
        self.__webview.save_credentials()
        self.destroy()
