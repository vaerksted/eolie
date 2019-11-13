# Copyright (c) 2017-2019 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from gi.repository import Gtk, Gdk, GLib, Gio, Pango

from gettext import gettext as _
from urllib.parse import urlparse
from time import time

from eolie.helper_task import TaskHelper
from eolie.define import App
from eolie.popover_uri import UriPopover
from eolie.widget_smooth_progressbar import SmoothProgressBar
from eolie.widget_uri_entry_icons import UriEntryIcons
from eolie.helper_gestures import GesturesHelper
from eolie.helper_size_allocation import SizeAllocationHelper


class UriEntry(Gtk.Overlay, SizeAllocationHelper):
    """
        URI Entry for toolbar
    """

    def __init__(self, window):
        """
            Init toolbar
            @param window as Window
        """
        Gtk.Overlay.__init__(self)
        self.get_style_context().add_class("input")
        self.__window = window
        self.__input_warning_shown = False
        self.__entry_changed_id = None
        self.__suggestion_id = None
        self.__secure_content = True
        self.__size_allocation_timeout = None

        self.__cancellable = Gio.Cancellable.new()
        self.__dns_suffixes = ["com", "org"]
        for string in reversed(GLib.get_language_names()):
            if len(string) == 2:
                self.__dns_suffixes.insert(0, string)
                break

        self.__entry = Gtk.Entry.new()
        self.__entry.show()
        self.__entry.get_style_context().add_class("uribar")
        self.__signal_id = self.__entry.connect("changed",
                                                self.__on_entry_changed)
        self.__entry.connect("populate-popup", self.__on_entry_populate_popup)
        self.__entry_gesture = GesturesHelper(
            self.__entry,
            primary_press_callback=self.__on_entry_press)
        self.__entry_controller = Gtk.EventControllerKey.new(self.__entry)
        self.__entry_controller.connect("focus-in", self.__on_entry_focus_in)
        self.__entry_controller.connect("focus-out", self.__on_entry_focus_out)
        self.__entry_controller.connect("key-pressed",
                                        self.__on_entry_key_pressed)

        self.__icons = UriEntryIcons(window)
        self.__icons.show()

        self.__placeholder = Gtk.Label.new()
        self.__placeholder.show()
        self.__placeholder.set_property("halign", Gtk.Align.START)
        self.__placeholder.set_hexpand(True)
        self.__placeholder.set_ellipsize(Pango.EllipsizeMode.END)
        self.__placeholder.get_style_context().add_class("placeholder")

        grid = Gtk.Grid()
        grid.show()
        grid.add(self.__placeholder)
        grid.add(self.__icons)

        self.__progress = SmoothProgressBar()

        self.add(self.__entry)
        self.add_overlay(grid)
        self.add_overlay(self.__progress)
        self.set_overlay_pass_through(grid, True)

        # Inline completion
        self.__completion_model_append_timeout_id = None
        self.__completion_model_clear_timeout_id = None
        self.__completion_model = Gtk.ListStore(str)
        self.__completion = Gtk.EntryCompletion.new()
        self.__completion.set_model(self.__completion_model)
        self.__completion.set_text_column(0)
        self.__completion.set_inline_completion(True)
        self.__completion.set_popup_completion(False)
        self.__entry.set_completion(self.__completion)

        self.__popover = UriPopover(window)
        self.__popover.set_relative_to(self.__entry)
        self.__popover.connect("closed", self.__on_popover_closed)

        # Some on the fly css styling
        context = self.__entry.get_style_context()
        self.__css_provider = Gtk.CssProvider()
        context.add_provider_for_screen(Gdk.Screen.get_default(),
                                        self.__css_provider,
                                        Gtk.STYLE_PROVIDER_PRIORITY_USER)
        SizeAllocationHelper.__init__(self, self.__icons)

    def set_text_entry(self, text):
        """
            Set uri in Gtk.Entry
            @param text as str
        """
        if self.__entry.get_text() == text:
            return
        if self.__signal_id is not None:
            self.__entry.disconnect(self.__signal_id)
        self.__completion_model.clear()
        # Do not show this in titlebar
        parsed = urlparse(text)
        if parsed.scheme in ["populars", "about"]:
            text = ""
        # Should not be needed but set_text("") do not clear text
        self.__entry.delete_text(0, -1)
        self.__entry.set_text(text)
        self.__entry.set_position(-1)
        if text:
            self.__placeholder.set_opacity(0)
        else:
            self.__placeholder.set_opacity(1)
        self.__signal_id = self.__entry.connect("changed",
                                                self.__on_entry_changed)

    def set_uri(self, uri):
        """
            Set toolbar URI
            @param uri as str
        """
        self.set_tooltip_text(uri)
        self.__input_warning_shown = False
        self.__secure_content = True
        self.__update_secure_content_indicator()
        bookmark_id = App().bookmarks.get_id(uri)
        self.__icons.set_bookmarked(bookmark_id is not None)

    def set_title(self, title):
        """
            Set toolbar title
            @param title as str
        """
        self.__window.set_title(title)
        markup = False
        # Do not show this in titlebar
        uri = self.__window.container.webview.uri
        parsed = urlparse(uri)
        if parsed.scheme in ["populars", "about"]:
            self.set_default_placeholder()
            return
        if title:
            if markup:
                self.__placeholder.set_markup(title)
            else:
                self.__placeholder.set_text(title)
        else:
            self.__placeholder.set_text(uri)
        if not self.__popover.is_visible():
            self.__placeholder.set_opacity(0.8)
            self.set_text_entry("")

    def set_insecure_content(self):
        """
            Mark uri as insecure
        """
        self.__secure_content = False
        self.__entry.set_icon_tooltip_text(
            Gtk.EntryIconPosition.PRIMARY,
            _("This page contains insecure content"))
        self.__entry.set_icon_from_icon_name(
            Gtk.EntryIconPosition.PRIMARY,
            "channel-insecure-symbolic")

    def focus(self, child="bookmarks"):
        """
            Focus wanted child entry
            @param child as str
        """
        self.get_toplevel().set_focus(self.__entry)
        uri = self.__window.container.webview.uri
        parsed = urlparse(uri)
        if parsed.scheme in ["http", "https", "file"]:
            self.set_text_entry(uri)
            self.__entry.select_region(0, -1)
        self.__popover.popup(child)

    def set_default_placeholder(self):
        """
            Show search placeholder
        """
        if self.__placeholder.get_text() == _("Search or enter address"):
            return
        self.set_text_entry("")
        self.__placeholder.set_text(_("Search or enter address"))
        self.__placeholder.set_opacity(0.8)
        self.__entry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY,
                                             "system-search-symbolic")
        self.__entry.set_icon_tooltip_text(Gtk.EntryIconPosition.PRIMARY,
                                           "")

    @property
    def widget(self):
        """
            Get main entry widget
            @return Gtk.entry
        """
        return self.__entry

    @property
    def placeholder(self):
        """
            Get placeholder
            @return Gtk.Label
        """
        return self.__placeholder

    @property
    def popover(self):
        """
            Get main URI popover
            @return UriPopover
        """
        return self.__popover

    @property
    def icons(self):
        """
            Get entry icons
            @return UriEntryIcons
        """
        return self.__icons

    @property
    def progress(self):
        """
            Get progress bar
            @return Gtk.ProgressBar
        """
        return self.__progress

#######################
# PRIVATE             #
#######################
    def __focus_out(self):
        """
            Focus out widget
        """
        webview = self.__window.container.webview
        self.__completion_model.clear()
        self.__placeholder.set_opacity(0.8)
        self.set_text_entry("")
        uri = webview.uri
        if uri is not None:
            bookmark_id = App().bookmarks.get_id(uri)
            self.__icons.set_bookmarked(bookmark_id is not None)

    def __update_secure_content_indicator(self):
        """
            Update PRIMARY icon, Gtk.Entry should be set
        """
        webview = self.__window.container.webview
        if time() - webview.ctime < 10:
            self.__entry.set_icon_from_icon_name(
                Gtk.EntryIconPosition.PRIMARY, "dialog-password-symbolic")
            self.__entry.set_icon_tooltip_text(
                Gtk.EntryIconPosition.PRIMARY,
                _("Save password for: %s") % webview.credentials_uri)
        else:
            uri = webview.uri
            parsed = urlparse(uri)
            self.__entry.set_icon_tooltip_text(Gtk.EntryIconPosition.PRIMARY,
                                               "")
            if (parsed.scheme == "https" and self.__secure_content) or\
                    parsed.scheme == "file":
                self.__entry.set_icon_from_icon_name(
                    Gtk.EntryIconPosition.PRIMARY,
                    "channel-secure-symbolic")
            elif parsed.scheme in ["http", "https"]:
                self.set_insecure_content()
            else:
                self.__entry.set_icon_from_icon_name(
                    Gtk.EntryIconPosition.PRIMARY,
                    "system-search-symbolic")

    def __on_search_suggestion(self, uri, status, content, encoding, value):
        """
            Add suggestions
            @param uri as str
            @param status as bool
            @param content as bytes
            @param encoding as str
            @param value as str
        """
        current_text = self.__entry.get_text()
        if status and value == current_text:
            string = content.decode(encoding)
            # format: '["{"words"}",["result1","result2"]]'
            sgs = string.replace('[', '')\
                        .replace(']', '')\
                        .replace('"', '')\
                        .split(',')[1:]
            self.__popover.add_suggestions(sgs)

    def __populate_completion(self, uri):
        """
            @param uri as str
            @thread safe
        """
        # Thread handling
        def model_append_timeout(array):
            self.__completion_model_append_timeout_id = None
            self.__completion_model.append(array)

        def model_clear_timeout():
            self.__completion_model_clear_timeout_id = None
            self.__completion_model.clear()

        def model_append(array):
            if self.__completion_model_clear_timeout_id is not None:
                GLib.source_remove(self.__completion_model_clear_timeout_id)
                self.__completion_model_clear_timeout_id = None
            if self.__completion_model_append_timeout_id is not None:
                GLib.source_remove(self.__completion_model_append_timeout_id)
            self.__completion_model_append_timeout_id = \
                GLib.timeout_add(250, model_append_timeout, array)

        def model_clear():
            if self.__completion_model_clear_timeout_id is not None:
                GLib.source_remove(self.__completion_model_clear_timeout_id)
            self.__completion_model_clear_timeout_id = \
                GLib.timeout_add(1000, model_clear_timeout)

        if self.__entry.get_text() == uri:
            # Look for a match in history
            match = App().history.get_match(uri)
            if match is not None:
                if self.__cancellable.is_cancelled():
                    return
                match_parsed = urlparse(match)
                netloc = match_parsed.netloc.replace("www.", "")
                if netloc.find(uri) == 0:
                    if match_parsed.path.find(uri.split("/")[-1]) != -1:
                        model_append([netloc + match_parsed.path])
                    else:
                        model_append([netloc])
                    return
            if App().settings.get_value("dns-prediction"):
                # Try some DNS request, FIXME Better list?
                from socket import gethostbyname
                parsed = urlparse(uri)
                if parsed.netloc:
                    uri = parsed.netloc
                for suffix in self.__dns_suffixes:
                    for prefix in ["www.", ""]:
                        try:
                            lookup = "%s%s.%s" % (prefix, uri, suffix)
                            gethostbyname(lookup)
                            model_append([lookup.replace("www.", "")])
                            return
                        except:
                            if self.__cancellable.is_cancelled():
                                return
            # Only happen if nothing matched
            model_clear()

    def __search_in_current_views(self, value):
        """
            Search views matching value and add them to popover
            @param value as str
            @thread safe
        """
        webviews = []
        for webview in self.__window.container.webviews:
            uri = webview.uri
            if uri is None:
                continue
            parsed = urlparse(uri)
            if parsed.netloc.lower().find(value) != -1:
                webviews.append(webview)
        GLib.idle_add(self.__popover.add_webviews, webviews)

    def __on_popover_closed(self, popover):
        """
            Clean titlebar
            @param popover as Gtk.popover
        """
        self.__cancellable.cancel()
        self.__cancellable = Gio.Cancellable.new()
        self.__completion_model.clear()
        webview = self.__window.container.webview
        if popover == self.__popover:
            webview.grab_focus()
            self.__focus_out()
            value = self.__entry.get_text().lstrip().rstrip()
            if value:
                webview.add_text_entry(value)
            self.__entry.delete_selection()

    def __on_entry_changed(self, entry):
        """
            Delayed entry changed
            @param entry as Gtk.Entry
        """
        value = entry.get_text()
        if not value:
            webview = self.__window.container.webview
            webview.clear_text_entry()
        # Text change comes from completion validation ie Enter
        for completion in self.__completion_model:
            if completion[0] == value:
                return
        parsed = urlparse(value)
        is_uri = parsed.scheme in ["about, http", "file", "https", "populars"]
        uri = self.__window.container.webview.uri
        parsed = urlparse(uri)
        if value:
            self.__placeholder.set_opacity(0)
            # We are doing a search, show popover
            if not is_uri and not self.__popover.is_visible():
                self.__popover.popup("bookmarks")
        elif parsed.scheme in ["populars", "about"]:
            self.set_default_placeholder()
        if self.__entry_changed_id is not None:
            GLib.source_remove(self.__entry_changed_id)
        self.__entry_changed_id = GLib.timeout_add(
            250,
            self.__on_entry_changed_timeout,
            entry,
            value)

    def __on_entry_changed_timeout(self, entry, value):
        """
            Update popover search if needed
            @param entry as Gtk.Entry
            @param value as str
        """
        task_helper = TaskHelper()
        self.__entry_changed_id = None

        self.__window.container.webview.add_text_entry(value)

        # Populate completion model
        task_helper.run(self.__populate_completion, value)

        self.__cancellable.cancel()
        self.__cancellable = Gio.Cancellable.new()

        network = Gio.NetworkMonitor.get_default().get_network_available()
        parsed = urlparse(value)
        is_uri = parsed.scheme in ["about, http", "file", "https", "populars"]
        if is_uri:
            self.__popover.set_search_text(parsed.netloc + parsed.path)
        else:
            self.__popover.set_search_text(value)

        # Remove any pending suggestion search
        if self.__suggestion_id is not None:
            GLib.source_remove(self.__suggestion_id)
            self.__suggestion_id = None
        # Search for suggestions if needed
        if App().settings.get_value("enable-suggestions") and\
                value and not is_uri and network:
            self.__suggestion_id = GLib.timeout_add(
                50,
                self.__on_suggestion_timeout,
                value)
        task_helper.run(self.__search_in_current_views, value)
        self.__entry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY,
                                             "system-search-symbolic")
        self.__entry.set_icon_tooltip_text(Gtk.EntryIconPosition.PRIMARY, "")

    def __on_suggestion_timeout(self, value):
        """
            Search suggestions
            @param value as str
        """
        self.__suggestion_id = None
        App().search.search_suggestions(value,
                                        self.__cancellable,
                                        self.__on_search_suggestion)

    def __on_entry_focus_in(self, entry, event):
        """
            Block entry on uri
            @param entry as Gtk.Entry
            @param event as Gdk.Event
        """
        if self.__popover.is_visible():
            return
        webview = self.__window.container.webview
        self.__icons.show_clear_button()
        uri = self.__window.container.webview.uri
        parsed = urlparse(uri)
        value = webview.get_current_text_entry()
        if value:
            self.set_text_entry(value)
        elif parsed.scheme in ["http", "https", "file"]:
            self.set_text_entry(uri)
            self.__placeholder.set_opacity(0)
        else:
            self.set_default_placeholder()

    def __on_entry_focus_out(self, entry, event):
        """
            Show title
            @param entry as Gtk.Entry
            @param event as Gdk.Event (do not use)
        """
        if self.__popover.is_visible():
            return
        self.__focus_out()

    def __on_entry_populate_popup(self, entry, menu):
        """
            @param entry as Gtk.Entry
            @param menu as Gtk.Menu
        """
        def on_item_activate(item, clipboard):
            self.__window.container.webview.load_uri(clipboard)
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).wait_for_text()
        if clipboard is not None:
            item = Gtk.MenuItem.new_with_label(_("Paste and load"))
            item.connect("activate", on_item_activate, clipboard)
            item.show()
            menu.attach(item, 0, 1, 3, 4)

    def __on_entry_press(self, x, y, event):
        """
            Show popover if hidden
            @param x as int
            @param y as int
            @param event as Gdk.Event
        """
        if x < 30:
            if self.__entry.get_icon_name(Gtk.EntryIconPosition.PRIMARY) ==\
                    "dialog-password-symbolic":
                self.__update_secure_content_indicator()
                from eolie.popover_credentials import CredentialsPopover
                credentials_popover = CredentialsPopover(self.__window)
                credentials_popover.set_relative_to(self.__entry)
                credentials_popover.set_pointing_to(
                    self.__entry.get_icon_area(Gtk.EntryIconPosition.PRIMARY))
                credentials_popover.popup()
            else:
                from eolie.popover_tls import TLSPopover
                tls_popover = TLSPopover(self.__window)
                tls_popover.set_relative_to(self.__entry)
                tls_popover.set_pointing_to(
                    self.__entry.get_icon_area(Gtk.EntryIconPosition.PRIMARY))
                tls_popover.popup()
        elif not self.__popover.get_visible():
            self.__on_entry_focus_in(self.__entry, event)
            self.__popover.popup("bookmarks")

    def __on_entry_key_pressed(self, controller, keyval, keycode, state):
        """
            Forward to popover history listbox if needed
            @param controller as Gtk.EventControllerKey.
            @param keyval as int
            @param keycode as int
            @param state as Gdk.ModifierType
        """
        webview = self.__window.container.webview
        uri = self.__entry.get_text().lstrip().rstrip()

        # Walk history if Ctrl + [zZ]
        if state & Gdk.ModifierType.CONTROL_MASK:
            value = None
            if keyval == Gdk.KEY_z:
                value = webview.get_prev_text_entry(uri)
            elif keyval == Gdk.KEY_Z:
                value = webview.get_next_text_entry()
            elif keyval == Gdk.KEY_Return:
                bounds = self.__entry.get_selection_bounds()
                if bounds:
                    current = self.__entry.get_text()[:bounds[0]]
                else:
                    current = self.__entry.get_text()
                value = current + ".com"
            if value is not None:
                self.set_text_entry(value)
                self.__entry.emit("changed")
            return

        # Forward event to popover, if not used, handle input
        forwarded = self.__popover.forward_event(keyval, state)
        if forwarded:
            return True
        else:
            # Close popover and save current entry
            if keyval == Gdk.KEY_Escape:
                self.__entry.delete_text(0, -1)
                webview.clear_text_entry()
                GLib.idle_add(self.__window.close_popovers)
                return True
            # Close popover, save current entry and load text content
            elif keyval in [Gdk.KEY_Return, Gdk.KEY_KP_Enter]:
                webview.clear_text_entry()
                GLib.idle_add(self.__window.close_popovers)
                parsed = urlparse(uri)
                # Search a missing scheme
                if uri.find(".") != -1 and\
                        uri.find(" ") == -1 and\
                        not parsed.scheme:
                    # Add missing www.
                    if not uri.startswith("www."):
                        db_uri = App().history.get_match("://www." + uri)
                        if db_uri is not None:
                            uri = "www." + uri
                    # Add missing scheme
                    db_uri = App().history.get_match("https://" + uri)
                    if db_uri is None:
                        uri = "http://" + uri
                    else:
                        uri = "https://" + uri
                self.__window.container.load_uri(uri)
                self.__window.container.set_expose(False)
                if self.__entry_changed_id is not None:
                    GLib.source_remove(self.__entry_changed_id)
                    self.__entry_changed_id = None
                webview.grab_focus()
                self.__completion_model.clear()
                return True

    def _handle_width_allocate(self, allocation):
        """
            @param allocation as Gtk.Allocation
            @return True if allocation is valid
        """
        if SizeAllocationHelper._handle_width_allocate(self, allocation):
            style = self.__entry.get_style_context()
            if Gtk.Widget.get_default_direction() == Gtk.TextDirection.RTL:
                state = Gtk.StateFlags.NORMAL | Gtk.StateFlags.DIR_RTL
            else:
                state = Gtk.StateFlags.NORMAL | Gtk.StateFlags.DIR_LTR
            border = style.get_border(state).bottom
            padding_start = style.get_padding(state).left
            padding_end = style.get_padding(state).right
            margin_start = style.get_margin(state).left
            margin_end = style.get_margin(state).right
            margin_bottom = style.get_margin(state).bottom
            css = ".progressbar { margin-bottom: %spx;\
                   margin-left: %spx;\
                   margin-right: %spx; }" % (margin_bottom,
                                             margin_start + border,
                                             margin_end + border)
            # 5 is grid margin (see ui file)
            uribar_padding = allocation.width + 5
            css += ".uribar { padding-right: %spx; }" % (uribar_padding)
            css += ".uribar:dir(rtl)"\
                   "{ padding-left: %spx;padding-right: %spx}" %\
                   (uribar_padding, padding_end)
            # 22 is Gtk.EntryIconPosition.PRIMARY
            if Gtk.Widget.get_default_direction() == Gtk.TextDirection.RTL:
                placeholder_margin = padding_end + 22 + border
            else:
                placeholder_margin = padding_start + 22 + border
            css += ".placeholder {margin-left: %spx;}" % placeholder_margin
            css += ".placeholder:dir(rtl)"\
                   "{margin-right: %spx;\
                     margin-left: 0px;}" % placeholder_margin
            # Get value from headerbar as not possible in pure CSS
            color = style.get_color(Gtk.StateFlags.ACTIVE).to_string()
            css += ".uribar { color: %s; caret-color:%s}" % (color, color)
            self.__css_provider.load_from_data(css.encode("utf-8"))
