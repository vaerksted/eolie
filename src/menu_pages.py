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

from eolie.define import El


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

        # Setup actions
        action = Gio.SimpleAction(name="new-private")
        app.add_action(action)
        action.connect('activate',
                       self.__on_private_clicked)
        action = Gio.SimpleAction(name="openall")
        app.add_action(action)
        action.connect('activate',
                       self.__on_openall_clicked)
        panel_mode = app.settings.get_enum("panel-mode")
        self.__panel_action = Gio.SimpleAction.new_stateful(
                                                 "panel_mode",
                                                 GLib.VariantType.new("i"),
                                                 GLib.Variant("i", panel_mode))
        self.__panel_action.connect("activate",
                                    self.__on_panel_mode_active)
        app.add_action(self.__panel_action)

        # Setup submenu
        submenu = Gio.Menu.new()
        items = [Gio.MenuItem.new(_("Show preview"),
                                  "app.panel_mode(0)"),
                 Gio.MenuItem.new(_("Do not show preview"),
                                  "app.panel_mode(1)"),
                 Gio.MenuItem.new(_("Minimal panel"),
                                  "app.panel_mode(2)")]
        for item in items:
            submenu.append_item(item)
        # Setup menu
        item = Gio.MenuItem.new(_("New private page"), "app.new-private")
        item.set_icon(Gio.ThemedIcon.new("user-not-tracked-symbolic"))
        self.append_item(item)
        self.append_submenu(_("View"), submenu)
        self.__closed_section = Gio.Menu()
        self.append_section(_("Closed pages"), self.__closed_section)
        remember_session = El().settings.get_value("remember-session")
        opened_pages = El().history.get_opened_pages()
        if not remember_session and opened_pages:
            item = Gio.MenuItem.new(_("Open all pages"), "app.openall")
            item.set_icon(Gio.ThemedIcon.new("document-open-symbolic"))
            self.append_item(item)
            # Delayed to not slow down startup
            GLib.timeout_add(1000, self.__append_opened_pages)

    def activate_last_action(self):
        """
            Activate last action
        """
        if self.__closed_section.get_n_items():
            uri = self.__closed_section.get_item_attribute_value(0, "uri")
            encoded = sha256(uri.get_string().encode("utf-8")).hexdigest()
            action = self.__app.lookup_action(encoded)
            action.activate(None)

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
            for i in range(0, self.__closed_section.get_n_items() - 1):
                attribute = self.__closed_section.get_item_attribute_value(
                                                                         i,
                                                                         "uri")
                if attribute is None:
                    continue
                _uri = attribute.get_string()
                if uri == _uri:
                    self.__closed_section.remove(i)
                    break

#######################
# PRIVATE             #
#######################
    def __append_opened_pages(self, opened_pages):
        """
            Append opened pages ie pages opened on last session
            @param opened_pages as [(str, str)]
        """
        for (uri, title) in opened_pages:
            self.add_action(title, uri, False, None)

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
        if uri == "populars://":
            item.set_icon(Gio.ThemedIcon.new("emote-love-symbolic"))
        elif surface is not None:
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
        self.__app.active_window.container.add_webview(self.__app.start_page,
                                                       Gdk.WindowType.CHILD,
                                                       True)

    def __on_openall_clicked(self, action, variant):
        """
            Add all entries
            @param Gio.SimpleAction
            @param GVariant
        """
        for i in range(0, self.__closed_section.get_n_items()):
            uri_attr = self.__closed_section.get_item_attribute_value(i,
                                                                      "uri")
            if uri_attr is None:
                continue
            GLib.idle_add(self.__app.active_window.container.add_webview,
                          uri_attr.get_string(), Gdk.WindowType.OFFSCREEN,
                          False,
                          None, None, False)
            self.__closed_section.remove(i)

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
        GLib.idle_add(self.__app.active_window.container.add_webview,
                      uri, Gdk.WindowType.CHILD, private, None, state)
        self.remove_action(uri)

    def __on_panel_mode_active(self, action, param):
        """
            Update panel mode
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        action.set_state(param)
        self.__app.settings.set_enum('panel-mode', param.get_int32())
        for window in self.__app.windows:
            window.container.sidebar.set_panel_mode()
