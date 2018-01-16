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

from gi.repository import Gio, GLib

from gettext import gettext as _
from hashlib import sha256

from eolie.define import El, LoadingType
from eolie.utils import wanted_loading_type


class PagesMenu(Gio.Menu):
    """
        Menu showing closed page
    """

    def __init__(self):
        """
            Init menu
        """
        Gio.Menu.__init__(self)

        # Setup actions
        action = Gio.SimpleAction(name="new-private")
        El().add_action(action)
        action.connect('activate',
                       self.__on_private_clicked)
        action = Gio.SimpleAction(name="openall")
        action.set_enabled(False)
        El().add_action(action)
        action.connect('activate',
                       self.__on_openall_clicked)
        # Setup menu
        item = Gio.MenuItem.new(_("New private page"), "app.new-private")
        item.set_icon(Gio.ThemedIcon.new("user-not-tracked-symbolic"))
        self.append_item(item)
        self.__closed_section = Gio.Menu()
        self.append_section(_("Closed pages"), self.__closed_section)
        item = Gio.MenuItem.new(_("Open all pages"), "app.openall")
        item.set_icon(Gio.ThemedIcon.new("document-open-symbolic"))
        self.append_item(item)
        remember_session = El().settings.get_value("remember-session")
        opened_pages = El().history.get_opened_pages()
        if not remember_session and opened_pages:
            # Delayed to not slow down startup
            GLib.timeout_add(1000, self.__append_opened_pages, opened_pages)

    def activate_last_action(self):
        """
            Activate last action
        """
        if self.__closed_section.get_n_items():
            uri = self.__closed_section.get_item_attribute_value(0, "uri")
            encoded = sha256(uri.get_string().encode("utf-8")).hexdigest()
            action = El().lookup_action(encoded)
            if action is not None:
                action.activate(None)

    def add_action(self, title, uri, private, state):
        """
            Add a new action to menu
            @param title as str
            @param uri as str
            @param private as bool
            @param state as WebKit2.WebViewSessionState
        """
        # Close all item
        if not uri:
            return
        if not title:
            title = uri
        self.__clean_actions()
        encoded = sha256(uri.encode("utf-8")).hexdigest()
        action = Gio.SimpleAction(name=encoded)
        El().add_action(action)
        action.connect('activate',
                       self.__on_action_clicked,
                       (uri, private, state))
        if len(title) > 40:
            title = title[0:40] + "…"
        item = Gio.MenuItem.new(title, "app.%s" % encoded)
        item.set_attribute_value("uri", GLib.Variant("s", uri))
        if uri == "populars://":
            item.set_icon(Gio.ThemedIcon.new("emote-love-symbolic"))
        else:
            # Try to set icon
            favicon_path = El().art.get_favicon_path(uri)
            if favicon_path is not None:
                f = Gio.File.new_for_path(favicon_path)
                icon = Gio.FileIcon.new(f)
                if icon is not None:
                    item.set_icon(icon)
            else:
                item.set_icon(Gio.ThemedIcon.new("applications-internet"))
        self.__closed_section.insert_item(0, item)
        action = El().lookup_action("openall")
        if action is not None:
            action.set_enabled(self.__closed_section.get_n_items() > 1)

    def remove_action(self, uri):
        """
            Remove action from menu
        """
        encoded = sha256(uri.encode("utf-8")).hexdigest()
        action = El().lookup_action(encoded)
        if action is not None:
            El().remove_action(encoded)
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
        action = El().lookup_action("openall")
        if action is not None:
            action.set_enabled(self.__closed_section.get_n_items() < 2)

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

    def __clean_actions(self):
        """
            Manager an history of max 20 items
        """
        if self.__closed_section.get_n_items() > 21:
            uri = self.__closed_section.get_item_attribute_value(
                                                         0, "uri").get_string()
            encoded = sha256(uri.encode("utf-8")).hexdigest()
            action = El().lookup_action(encoded)
            if action is not None:
                El().remove_action(encoded)
            self.__closed_section.remove(0)

    def __on_private_clicked(self, action, variant):
        """
            Add a new private view
            @param Gio.SimpleAction
            @param GVariant
        """
        El().active_window.container.add_webview(El().start_page,
                                                 LoadingType.FOREGROUND,
                                                 True)

    def __on_openall_clicked(self, action, variant):
        """
            Add all entries
            @param Gio.SimpleAction
            @param GVariant
        """
        items = []
        for i in range(0, self.__closed_section.get_n_items()):
            uri_attr = self.__closed_section.get_item_attribute_value(i,
                                                                      "uri")
            title_attr = self.__closed_section.get_item_attribute_value(
                                                                       i,
                                                                       "label")
            if uri_attr is None or title_attr is None:
                continue
            uri = uri_attr.get_string()
            title = title_attr.get_string()
            loading_type = wanted_loading_type(i)
            items.append((uri, title, 0, False, None, loading_type))
            i += 1
        El().active_window.container.add_webviews(items)
        self.__closed_section.remove_all()

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
        El().active_window.container.add_webview(uri,
                                                 LoadingType.FOREGROUND,
                                                 private,
                                                 state)
        self.remove_action(uri)
