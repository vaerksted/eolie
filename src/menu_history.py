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

from hashlib import sha256


class HistoryMenu(Gio.Menu):
    """
        Menu showing closed page
    """

    def __init__(self, app, items):
        """
            Init menu
            @param app as Gio.Application
            @param items as [WebKit2.BackForwardListItem]
        """
        Gio.Menu.__init__(self)
        self.__app = app
        for item in items[:10]:
            uri = item.get_uri()
            if uri is None:
                continue
            title = item.get_title()
            if not title:
                title = uri
            encoded = "HISTORY_" + sha256(uri.encode("utf-8")).hexdigest()
            action = self.__app.lookup_action(encoded)
            if action is not None:
                self.__app.remove_action(encoded)
            action = Gio.SimpleAction(name=encoded)
            self.__app.add_action(action)
            action.connect('activate',
                           self.__on_action_clicked,
                           item)
            if len(title) > 60:
                title = title[0:60] + "…"
            item = Gio.MenuItem.new(title, "app.%s" % encoded)
            item.set_attribute_value("uri", GLib.Variant("s", uri))
            # Try to set icon
            context = WebKit2.WebContext.get_default()
            favicon_db = context.get_favicon_database()
            favicon_db.get_favicon(uri, None,
                                   self.__set_favicon_result, item, uri)

    def remove_actions(self):
        """
            Remove actions for menu
        """
        for i in range(0, self.get_n_items()):
            uri = self.get_item_attribute_value(i, "uri").get_string()
            encoded = "HISTORY_" + sha256(uri.encode("utf-8")).hexdigest()
            action = self.__app.lookup_action(encoded)
            if action is not None:
                self.__app.remove_action(encoded)

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
        self.append_item(item)

    def __on_action_clicked(self, action, variant, item):
        """
            Add to playlists
            @param Gio.SimpleAction
            @param GVariant
            @param item as WebKit2.BackForwardListItem
        """
        self.__app.active_window.\
            container.current.webview.go_to_back_forward_list_item(item)
