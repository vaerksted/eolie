# Copyright (c) 2017-2018 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from gi.repository import Gio, GLib

from hashlib import sha256
from gettext import gettext as _

from eolie.define import App


class VideosMenu(Gio.Menu):
    """
        Menu showing videos in page
    """

    def __init__(self, page_id, window):
        """
            Init menu
            @param page_id as int
            @param window as Window
        """
        Gio.Menu.__init__(self)
        self.__window = window
        self.__actions = []
        App().helper.call("GetVideos", page_id, None, self.__on_get_videos)

    def clean(self):
        """
            Clean menu
        """
        for action in self.__actions:
            self.__window.remove_action(action)

#######################
# PRIVATE             #
#######################
    def __add_action(self, title, uri):
        """
            Add a new action to menu
            @param title as str
            @param uri as str
        """
        encoded = "VIDEO_" + sha256(uri.encode("utf-8")).hexdigest()
        action = Gio.SimpleAction(name=encoded)
        self.__window.add_action(action)
        self.__actions.append(encoded)
        action.connect('activate',
                       self.__on_action_clicked,
                       uri)
        if len(title) > 40:
            title = title[0:40] + "…"
        item = Gio.MenuItem.new(title, "win.%s" % encoded)
        item.set_attribute_value("uri", GLib.Variant("s", uri))
        self.append_item(item)

    def __on_get_videos(self, source, result):
        """
            Add result to menu
            @param source as GObject.Object
            @param result as Gio.AsyncResult
        """
        try:
            items = source.call_finish(result)[0]
            if items:
                for (title, uri) in items:
                    self.__add_action(title, uri)
            else:
                self.__add_action(_("No videos"), "")
        except Exception as e:
            print("VideosMenu::__on_get_videos()", e)

    def __on_action_clicked(self, action, variant, uri):
        """
            Add to playlists
            @param Gio.SimpleAction
            @param GVariant
            @param uri as str
        """
        if uri:
            context = self.__window.container.current.webview.get_context()
            context.download_uri(uri)
