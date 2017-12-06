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

from gi.repository import Gio

from gettext import gettext as _
from hashlib import sha256

from eolie.define import El


class MoveToMenu(Gio.Menu):
    """
        Menu allowing to move webviews to a window
    """

    def __init__(self, views, current_window):
        """
            Init menu
            @param views as [Views]
            @param current_window as Window
        """
        self.__current_window = current_window
        self.__actions = []
        self.__views = list(views)
        Gio.Menu.__init__(self)
        title = _("New window")
        window_str = "new_window"
        encoded = "SITE_" + sha256(window_str.encode("utf-8")).hexdigest()
        action = Gio.SimpleAction(name=encoded)
        current_window.add_action(action)
        self.__actions.append(encoded)
        action.connect('activate',
                       self.__on_action_activate,
                       None)
        item = Gio.MenuItem.new(title, "win.%s" % encoded)
        self.append_item(item)
        for window in El().windows:
            if window == current_window:
                continue
            title = window.get_title()
            window_str = str(window)
            encoded = "SITE_" + sha256(window_str.encode("utf-8")).hexdigest()
            action = Gio.SimpleAction(name=encoded)
            current_window.add_action(action)
            self.__actions.append(encoded)
            action.connect('activate',
                           self.__on_action_activate,
                           window)
            item = Gio.MenuItem.new(title, "win.%s" % encoded)
            self.append_item(item)

    @property
    def actions(self):
        """
            Get stateful action name
            @return [str]
        """
        return self.__actions

#######################
# PRIVATE             #
#######################
    def __on_action_activate(self, action, variant, window):
        """
            Moves views to window
            @param Gio.SimpleAction
            @param GLib.Variant
            @param window as Window
        """
        if window is None:
            window = El().get_new_window()
        for view in self.__views:
            view.hide()
            self.__current_window.container.remove_view(view)
            window.container.add_view(view)
            view.set_window(window)
            view.show()
        window.update(view.webview)
        current_view = self.__current_window.container.current
        if current_view is not None:
            self.__current_window.update(current_view.webview)
