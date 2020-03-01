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

from gettext import gettext as _

from eolie.define import App, MARGIN_SMALL


class UriEntryIcons(Gtk.Grid):
    """
        Entry for main URI bar
    """

    def __init__(self, window):
        """
            Init toolbar
            @param window as Window
        """
        Gtk.Grid.__init__(self)
        self.set_margin_end(2)
        self.set_margin_start(2)
        self.__window = window

        separator = Gtk.Separator.new(Gtk.Orientation.VERTICAL)
        separator.show()
        separator.set_vexpand(True)
        separator.set_size_request(-1, 32)
        separator.set_margin_top(MARGIN_SMALL)
        separator.set_margin_bottom(MARGIN_SMALL)

        self.__reload_stop_button = Gtk.Button.new_from_icon_name(
            "view-refresh-symbolic", Gtk.IconSize.BUTTON)
        self.__reload_stop_button.show()
        self.__reload_stop_button.get_style_context().add_class(
            "no-border-button")
        self.__reload_stop_button.connect("clicked",
                                          self.__on_reload_button_clicked)

        self.__bookmark_button = Gtk.Button.new_from_icon_name(
            "non-starred-symbolic", Gtk.IconSize.BUTTON)
        self.__bookmark_button.show()
        self.__bookmark_button.get_style_context().add_class(
            "no-border-button")
        self.__bookmark_button.connect("clicked",
                                       self.__on_bookmark_button_clicked)

        self.__spinner = Gtk.Spinner.new()
        self.__spinner.show()
        # Magic value to be aligned with buttons
        self.__spinner.set_margin_end(7)

        self.__readability_button = Gtk.Button.new_from_icon_name(
            "view-dual-symbolic", Gtk.IconSize.BUTTON)
        self.__readability_button.show()
        self.__readability_button.get_style_context().add_class(
            "no-border-button")
        self.__readability_button.connect("clicked",
                                          self.__on_readability_button_clicked)

        self.__geolocation_button = Gtk.Button.new_from_icon_name(
            "mark-location-symbolic", Gtk.IconSize.BUTTON)
        self.__geolocation_button.get_style_context().add_class(
            "no-border-button")
        self.__geolocation_button.set_tooltip_text(_("Deny geolocation"))
        self.__geolocation_button.connect("clicked",
                                          self.__on_geolocation_button_clicked)

        self.add(self.__spinner)
        self.add(self.__geolocation_button)
        self.add(self.__readability_button)
        self.add(self.__bookmark_button)
        self.add(separator)
        self.add(self.__reload_stop_button)

    def set_readable_button_state(self, reading):
        """
            Mark readable button
            @param reading as bool
        """
        image = self.__readability_button.get_image()
        style_context = image.get_style_context()
        if reading:
            style_context.add_class("selected")
        else:
            style_context.remove_class("selected")

    def set_loading(self, loading):
        """
            Mark current webview as loading
            @param loading as bool
        """
        image = self.__reload_stop_button.get_image()
        if loading:
            self.__spinner.start()
            self.__spinner.show()
            image.set_from_icon_name(
                "process-stop-symbolic", Gtk.IconSize.BUTTON)
        else:
            self.__spinner.stop()
            self.__spinner.hide()
            image.set_from_icon_name(
                "view-refresh-symbolic", Gtk.IconSize.BUTTON)

    def set_bookmarked(self, bookmarked):
        """
            Set current webview as bookmarked
            @param bookmarked as bool
        """
        image = self.__bookmark_button.get_image()
        if bookmarked:
            image.set_from_icon_name(
                "starred-symbolic", Gtk.IconSize.BUTTON)
        else:
            image.set_from_icon_name(
                "non-starred-symbolic", Gtk.IconSize.BUTTON)

    def show_readable_button(self, show):
        """
            Show readable button
            @param show as bool
        """
        if show:
            self.__readability_button.show()
            self.set_readable_button_state(False)
        else:
            self.__readability_button.hide()

    def show_geolocation(self, show):
        """
            Show geolocation button
            @param show as bool
        """
        if show:
            self.__geolocation_button.show()
        else:
            self.__geolocation_button.hide()

    def show_clear_button(self):
        """
            Show clear button
        """
        if self.__window.container.webview.uri != "about:blank":
            image = self.__bookmark_button.get_image()
            image.set_from_icon_name("edit-clear-symbolic",
                                     Gtk.IconSize.BUTTON)

#######################
# PRIVATE             #
#######################
    def __on_readability_button_clicked(self, button):
        """
            Switch reading mode
            @param button as Gtk.Button
        """
        reading = self.__window.container.toggle_reading()
        self.set_readable_button_state(reading)

    def __on_geolocation_button_clicked(self, button):
        """
            Disable geolocation for current
            @param button as Gtk.Button
        """
        uri = self.__window.container.webview.uri
        App().websettings.set("geolocation", uri, False)

    def __on_reload_button_clicked(self, button):
        """
            Reload current view/Stop loading
            @param button as Gtk.Button
        """
        icon_name = self.__reload_stop_button.get_image().get_icon_name()[0]
        if icon_name == 'view-refresh-symbolic':
            self.__window.container.webview.reload_bypass_cache()
        else:
            self.__window.container.webview.stop_loading()

    def __on_bookmark_button_clicked(self, button):
        """
            Add/Remove page to/from bookmarks
            @param button as Gtk.Button
        """
        def on_popover_closed(popover, webview):
            bookmark_id = App().bookmarks.get_id(webview.uri)
            image = self.__bookmark_button.get_image()
            if bookmark_id is None:
                image.set_from_icon_name(
                    "non-starred-symbolic", Gtk.IconSize.BUTTON)
            else:
                image.set_from_icon_name(
                    "starred-symbolic", Gtk.IconSize.BUTTON)

        webview = self.__window.container.webview
        icon_name = self.__bookmark_button.get_image().get_icon_name()[0]
        if icon_name == "edit-clear-symbolic":
            self.__entry.delete_text(0, -1)
            webview.clear_text_entry()
        else:
            bookmark_id = App().bookmarks.get_id(webview.uri)
            if bookmark_id is None:
                image = self.__bookmark_button.get_image()
                image.set_from_icon_name(
                    "starred-symbolic", Gtk.IconSize.BUTTON)
                bookmark_id = App().bookmarks.add(webview.title,
                                                  webview.uri, None, [])
            from eolie.widget_bookmark_edit import BookmarkEditWidget
            widget = BookmarkEditWidget(bookmark_id, False)
            widget.show()
            popover = Gtk.Popover.new()
            popover.set_relative_to(button)
            popover.connect("closed", on_popover_closed, webview)
            popover.add(widget)
            popover.popup()
