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

from gi.repository import Gdk

from eolie.popover_uri_input import Input
from eolie.define import Type


class UriPopoverEvents:
    """
        Events handler for UriPopover
    """

    def __init__(self):
        """
            Init handler
        """
        pass

    def forward_event(self, keyval, state):
        """
            Forward event, smart navigation between boxes
            @param keyval as bool
            @param state as state as Gdk.ModifierType
            @return True if event forwarded
        """
        if not self.is_visible():
            return False
        if keyval == Gdk.KEY_Up and self._input == Input.NONE:
            return False
        elif keyval == Gdk.KEY_Left and self._input == Input.BOOKMARKS:
            self._input = Input.TAGS
            self._tags_box.get_style_context().add_class("kbd-input")
            self._bookmarks_box.get_style_context().remove_class("kbd-input")
            self._window.toolbar.title.entry.set_text_entry("")
            return True
        elif keyval == Gdk.KEY_Right and self._input == Input.TAGS:
            self._input = Input.BOOKMARKS
            self._bookmarks_box.get_style_context().add_class("kbd-input")
            self._tags_box.get_style_context().remove_class("kbd-input")
            return True
        elif keyval in [Gdk.KEY_Left, Gdk.KEY_Right] and\
                self._input == Input.SEARCH:
            return False
        elif keyval in [Gdk.KEY_Left, Gdk.KEY_Right] and\
                self._input != Input.NONE:
            return True
        elif keyval in [Gdk.KEY_Down, Gdk.KEY_Up]:
            # If nothing selected, detect default widget
            if self._input == Input.NONE:
                if self._stack.get_visible_child_name() == "search":
                    self._input = Input.SEARCH
                elif self._stack.get_visible_child_name() == "bookmarks":
                    self._tags_box.get_style_context().add_class("kbd-input")
                    self._input = Input.TAGS
                else:
                    self._input = Input.NONE
                box = self._get_current_input_box()
                if box is not None:
                    rows = box.get_children()
                    if rows:
                        box.select_row(None)
                        box.select_row(rows[0])
                return True
            box = self._get_current_input_box()
            rows = box.get_children()
            if box is None or not rows:
                self._input = Input.NONE
                return False
            selected = box.get_selected_row()
            # If nothing selected, select first row
            if selected is None:
                box.select_row(rows[0])
                if self._input == Input.TAGS:
                    item_id = rows[0].item.get_property("id")
                    self._set_bookmarks(item_id)
            else:
                idx = -1 if keyval == Gdk.KEY_Up else 1
                for row in rows:
                    if row == selected:
                        break
                    idx += 1
                box.select_row(None)
                if idx >= len(rows):
                    box.select_row(rows[0])
                    if self._input == Input.TAGS:
                        item_id = rows[0].item.get_property("id")
                        self._set_bookmarks(item_id)
                    return True
                elif idx < 0:
                    # Do not go to uribar for bookmarks & search
                    if self._input in [Input.BOOKMARKS, Input.SEARCH]:
                        box.select_row(rows[-1])
                        return True
                    else:
                        box.select_row(None)
                        self._input = Input.NONE
                        box.get_style_context().remove_class("kbd-input")
                else:
                    box.select_row(rows[idx])
                    if self._input == Input.TAGS:
                        item_id = rows[idx].item.get_property("id")
                        self._set_bookmarks(item_id)
                    return True
        elif keyval in [Gdk.KEY_Return, Gdk.KEY_KP_Enter]:
            box = self._get_current_input_box()
            if box is not None:
                selected = box.get_selected_row()
                if selected is not None:
                    container = self._window.container
                    item = selected.item
                    # Switch to view
                    if item.get_property("type") == Type.WEBVIEW:
                        title = item.get_property("title")
                        uri = item.get_property("uri")
                        for webview in container.webviews:
                            if webview.uri == uri and webview.title == title:
                                container.set_visible_webview(webview)
                                self._window.close_popovers()
                                break
                    # Load URI
                    else:
                        uri = selected.item.get_property("uri")
                        if uri:
                            self._window.close_popovers()
                            container.webview.load_uri(uri)
                            container.set_expose(False)
                            return True
            else:
                self._input = Input.NONE
        else:
            self._input = Input.NONE
        return False
