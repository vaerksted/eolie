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

from gi.repository import Gio, GLib, Gdk, WebKit2

from gettext import gettext as _
from hashlib import sha256


class PagesMenu(Gio.Menu):
    """
        Menu showing closed page
    """

    def __init__(self, app):
        """
            Init menu
            @param app as Gio.Application
        """
        Gio.Menu.__init__(self)
        self.__app = app
        action = Gio.SimpleAction(name="new-private")
        app.add_action(action)
        action.connect('activate',
                       self.__on_private_clicked)
        item = Gio.MenuItem.new(_("New private page"), "app.new-private")
        item.set_icon(Gio.ThemedIcon.new("user-not-tracked-symbolic"))
        self.insert_item(0, item)
        self.__closed_section = Gio.Menu()
        self.insert_section(1, _("Closed pages"), self.__closed_section)

    def add_action(self, title, uri, private, state):
        """
            Add a new action to menu
            @param title as str
            @param uri as str
            @param private as bool
            @param state as WebKit2.WebViewSessionState
        """
        self.__clean_actions()
        if not title:
            title = uri
        encoded = sha256(uri.encode("utf-8")).hexdigest()
        action = self.__app.lookup_action(encoded)
        if action is not None:
            self.__app.remove_action(encoded)
        action = Gio.SimpleAction(name=encoded)
        self.__app.add_action(action)
        action.connect('activate',
                       self.__on_action_clicked,
                       (uri, private, state))
        if len(title) > 60:
            title = title[0:60] + "…"
        item = Gio.MenuItem.new(title, "app.%s" % encoded)
        item.set_attribute_value("uri", GLib.Variant("s", uri))
        # Try to set icon
        context = WebKit2.WebContext.get_default()
        favicon_db = context.get_favicon_database()
        favicon_db.get_favicon(uri, None,
                               self.__set_favicon_result, item, uri)

    def remove_action(self, uri):
        """
            Remove action from menu
        """
        encoded = sha256(uri.encode("utf-8")).hexdigest()
        action = self.__app.lookup_action(encoded)
        if action is not None:
            self.__app.remove_action(encoded)
            for i in range(0, self.__closed_section.get_n_items()):
                _uri = self.get_item_attribute_value(i, "uri").get_string()
                if uri == _uri:
                    self.__closed_section.remove(i)
                    break

#######################
# PRIVATE             #
#######################
    def __set_favicon_result(self, db, result, item, uri):
        """
            Set favicon db result
            @param db as WebKit2.FaviconDatabase
            @param result as Gio.AsyncResult
            @param item as Gio.MenuItem
            @param uri as str
        """
        try:
            surface = db.get_favicon_finish(result)
        except:
            surface = None
        if surface is not None:
            pixbuf = Gdk.pixbuf_get_from_surface(surface,
                                                 0,
                                                 0,
                                                 surface.get_width(),
                                                 surface.get_height())
            del surface
            (saved, bytes) = pixbuf.save_to_bufferv("png",
                                                    [None],
                                                    [])
            del pixbuf
            item.set_icon(Gio.BytesIcon.new(GLib.Bytes.new(bytes)))
        elif uri == "populars://":
            item.set_icon(Gio.ThemedIcon.new("emote-love-symbolic"))
        else:
            item.set_icon(Gio.ThemedIcon.new("applications-internet"))
        self.__closed_section.insert_item(0, item)

    def __clean_actions(self):
        """
            Remove one action from history if needed
        """
        count = self.get_n_items()
        if count > 20:
            uri = self.__closed_section.get_item_attribute_value(
                                                         0, "uri").get_string()
            encoded = sha256(uri.encode("utf-8")).hexdigest()
            action = self.__app.lookup_action(encoded)
            if action is not None:
                self.__app.remove_action(encoded)
            self.__closed_section.remove(0)

    def __on_private_clicked(self, action, variant):
        """
            Add a new private view
            @param Gio.SimpleAction
            @param GVariant
        """
        self.__app.active_window.container.add_web_view(self.__app.start_page,
                                                        True,
                                                        True)

    def __on_action_clicked(self, action, variant, data):
        """
            Add to playlists
            @param Gio.SimpleAction
            @param GVariant
            @param data as (str, WebKit2.WebViewSessionState)
        """
        uri = data[0]
        private = data[1]
        state = data[2]
        GLib.idle_add(self.__app.active_window.container.add_web_view,
                      uri, True, private, None, None, state)
        self.remove_action(uri)
