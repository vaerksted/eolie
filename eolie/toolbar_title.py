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

from gi.repository import Gtk, Gdk, GLib, Gio

from gettext import gettext as _
from urllib.parse import urlparse

from eolie.helper_task import TaskHelper
from eolie.define import El, Indicator, Type
from eolie.popover_uri import UriPopover


class SmoothProgressBar(Gtk.ProgressBar):
    """
        Gtk.ProgressBar with full progression
        If faction is 0.1 and you set it to 0.5, it will be udpated
        to show all steps
    """

    def __init__(self):
        """
            Init widget
        """
        Gtk.ProgressBar.__init__(self)
        self.__timeout_id = None
        self.set_property("valign", Gtk.Align.END)
        self.get_style_context().add_class("progressbar")

    def set_fraction(self, fraction):
        """
            Set fraction smoothly
            @param fraction as float
        """
        if self.__timeout_id is not None:
            GLib.source_remove(self.__timeout_id)
        self.__set_fraction(fraction)

    def hide(self):
        """
            Hide widget and reset fraction
        """
        Gtk.ProgressBar.hide(self)
        Gtk.ProgressBar.set_fraction(self, 0)
        if self.__timeout_id is not None:
            GLib.source_remove(self.__timeout_id)
            self.__timeout_id = None

#######################
# PRIVATE             #
#######################
    def __set_fraction(self, fraction):
        """
            Set fraction smoothly
            @param fraction as float
        """
        self.__timeout_id = None
        current = self.get_fraction()
        if fraction - current > 0.5 or fraction == 1.0:
            ms = 10
        else:
            ms = 25
        progress = current + 0.025
        if progress < fraction:
            Gtk.ProgressBar.set_fraction(self, progress)
            self.__timeout_id = GLib.timeout_add(ms,
                                                 self.__set_fraction,
                                                 fraction)
        else:
            Gtk.ProgressBar.set_fraction(self, fraction)
            if fraction == 1.0:
                self.__timeout_id = GLib.timeout_add(500, self.hide)


class ToolbarTitle(Gtk.Bin):
    """
        Title toolbar
    """

    def __init__(self, window):
        """
            Init toolbar
            @param window as Window
        """
        Gtk.Bin.__init__(self)
        self.__window = window
        self.__input_warning_shown = False
        self.__signal_id = None
        self.__entry_changed_id = None
        self.__show_related_id = None
        self.__secure_content = True
        self.__size_allocation_timeout = Type.NONE  # CSS update needed
        self.__width = -1
        self.__uri = ""
        self.__cancellable = Gio.Cancellable.new()

        self.__dns_suffixes = ["com", "org"]
        for string in reversed(GLib.get_language_names()):
            if len(string) == 2:
                self.__dns_suffixes.insert(0, string)
                break

        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/ToolbarTitle.ui")
        builder.connect_signals(self)

        self.__entry = builder.get_object("entry")
        # Inline completion
        self.__completion_model = Gtk.ListStore(str)
        self.__completion = Gtk.EntryCompletion.new()
        self.__completion.set_model(self.__completion_model)
        self.__completion.set_text_column(0)
        self.__completion.set_inline_completion(True)
        self.__completion.set_popup_completion(False)
        self.__entry.set_completion(self.__completion)

        self.__popover = UriPopover(window)
        self.__popover.set_relative_to(self)
        self.__popover.connect("closed", self.__on_popover_closed)
        # Reload/Stop
        self.__action_image1 = builder.get_object("action_image1")
        # Bookmarks/Clear
        self.__action_image2 = builder.get_object("action_image2")
        self.add(builder.get_object("widget"))
        # Some on the fly css styling
        context = self.__entry.get_style_context()
        self.__css_provider = Gtk.CssProvider()
        context.add_provider_for_screen(Gdk.Screen.get_default(),
                                        self.__css_provider,
                                        Gtk.STYLE_PROVIDER_PRIORITY_USER)
        self.__progress = SmoothProgressBar()
        builder.get_object("overlay").add_overlay(self.__progress)
        # Used for spinner and reader
        self.__indicator_stack = builder.get_object("indicator_stack")
        # Used for popups and geolocation
        self.__indicator2 = builder.get_object("indicator2")
        self.__indicator2_image = builder.get_object("indicator2_image")

        self.__placeholder = builder.get_object("placeholder")
        self.__signal_id = self.__entry.connect("changed",
                                                self.__on_entry_changed)

    def set_reading(self):
        """
            Mark readable button
        """
        if self.__indicator_stack.get_visible_child_name() != "image":
            return
        child = self.__indicator_stack.get_visible_child()
        if self.__window.container.current.reading:
            child.get_style_context().add_class("selected")
        else:
            child.get_style_context().remove_class("selected")

    def show_spinner(self, b):
        """
            Show/hide spinner
            @param b as bool
        """
        if b:
            self.__indicator_stack.set_visible_child_name("spinner")
            self.__indicator_stack.get_visible_child().start()
            self.__indicator_stack.show()
        elif self.__indicator_stack.get_visible_child_name() == "spinner":
            self.__indicator_stack.get_visible_child().stop()
            self.__indicator_stack.hide()

    def do_get_preferred_width(self):
        """
            Fixed preferred width
        """
        if self.__width == -1:
            (min_width, nat_width) = Gtk.Bin.do_get_preferred_width(self)
        else:
            nat_width = self.__width
        return (-1, nat_width)

    def set_width(self, width):
        """
            Set Gtk.Entry width
            @param width as int
        """
        self.__width = width
        self.queue_resize()

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
            Update internal uri
            @param text as str
        """
        if uri == self.__uri:
            return
        self.__uri = uri
        self.set_tooltip_text(uri)
        self.__input_warning_shown = False
        self.__secure_content = True
        self.__update_secure_content_indicator()
        bookmark_id = El().bookmarks.get_id(uri)
        if bookmark_id is not None:
            icon_name = "starred-symbolic"
        else:
            icon_name = "non-starred-symbolic"
        self.__action_image2.set_from_icon_name(icon_name,
                                                Gtk.IconSize.MENU)

    def set_title(self, title):
        """
            Show title instead of uri
        """
        self.__window.set_title(title)
        # Do not show this in titlebar
        parsed = urlparse(self.__uri)
        if parsed.scheme in ["populars", "about"]:
            self.__set_default_placeholder()
            return
        if title:
            self.__placeholder.set_text(title)
        else:
            self.__placeholder.set_text(self.__uri)
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

    def show_javascript(self, dialog):
        """
            Show a popover with javascript message
            @param dialog as WebKit2.ScriptDialog
        """
        from eolie.popover_javascript import JavaScriptPopover
        popover = JavaScriptPopover(dialog, self.__window)
        popover.set_relative_to(self.__entry)
        popover.connect("closed", self.__on_popover_closed)
        popover.popup()

    def show_geolocation(self, uri, request):
        """
            Show a popover allowing geolocation
            @param uri as str
            @param request as WebKit2.PermissionRequest
        """
        if El().websettings.allowed_geolocation(uri):
            request.allow()
            self.show_indicator(Indicator.GEOLOCATION)
        else:
            from eolie.popover_geolocation import GeolocationPopover
            popover = GeolocationPopover(uri, request, self.__window)
            popover.set_relative_to(self.__entry)
            popover.connect("closed", self.__on_popover_closed)
            popover.popup()

    def show_message(self, message):
        """
            Show a message to user
            @param webview as WebView
            @param msg as str
        """
        from eolie.popover_message import MessagePopover
        popover = MessagePopover(message, self.__window)
        popover.set_relative_to(self.__entry)
        popover.connect("closed", self.__on_popover_closed)
        popover.popup()

    def show_input_warning(self, webview):
        """
            Show a message to user about password input field over http
            @param webview as WebView
        """
        # FIXME should be handled per webview
        if self.__input_warning_shown:
            return
        self.__input_warning_shown = True
        self.show_message(_(
                "Heads-up: this page is not secure.\n"
                "If you type your password,\n it will be "
                "visible to cybercriminals!"))

    def show_readable_button(self, b):
        """
            Show readable button
            @param b as bool
        """
        if b:
            self.__indicator_stack.show()
            self.__indicator_stack.set_visible_child_name("image")
            self.set_reading()
        else:
            self.__indicator_stack.hide()

    def show_password(self, user_form_name, user_form_value, pass_form_name,
                      pass_form_value, uri, form_uri):
        """
            Show a popover allowing user to save password
            @param user_form_name as str
            @param user_form_value as str
            @param pass_form_name as str
            @param pass_form_value as str
            @param uri as str
            @param form_uri as str
        """
        from eolie.popover_credentials import CredentialsPopover
        popover = CredentialsPopover(user_form_name, user_form_value,
                                     pass_form_name, pass_form_value,
                                     uri,
                                     form_uri,
                                     self.__window)
        popover.set_relative_to(self.__entry)
        popover.set_pointing_to(self.__entry.get_icon_area(
                                                Gtk.EntryIconPosition.PRIMARY))
        popover.connect("closed", self.__on_popover_closed)
        popover.popup()

    def show_indicator(self, indicator):
        """
            Show indicator
            @param indicator as Indicator
        """
        if indicator == Indicator.GEOLOCATION:
            self.__indicator2.show()
            self.__indicator2.set_tooltip_text(_("Disallow geolocation"))
            self.__indicator2_image.set_from_icon_name(
                                                    "mark-location-symbolic",
                                                    Gtk.IconSize.MENU)
        elif indicator == Indicator.POPUPS:
            self.__indicator2.show()
            self.__indicator2.set_tooltip_text(_("Blocked popups"))
            self.__indicator2_image.set_from_icon_name(
                                                    "focus-windows-symbolic",
                                                    Gtk.IconSize.MENU)
        else:
            self.__indicator2.hide()

    def focus_entry(self, child="bookmarks"):
        """
            Focus entry
            @param child as str
        """
        self.get_toplevel().set_focus(self.__entry)
        if not self.__popover.is_visible():
            self.__popover.popup(child)

    def update_load_indicator(self, view):
        """
            Update loading indicator
            @param view as WebView
        """
        if view.is_loading():
            self.__action_image1.set_from_icon_name('process-stop-symbolic',
                                                    Gtk.IconSize.MENU)
        else:
            self.__action_image1.set_from_icon_name('view-refresh-symbolic',
                                                    Gtk.IconSize.MENU)

    def start_search(self):
        """
            Focus widget without showing
            popover allowing user to start a search
        """
        if not self.__entry.is_focus():
            self.__entry.grab_focus()

    @property
    def uri(self):
        """
            Get current uri
            @return str
        """
        return self.__uri

    @property
    def progress(self):
        """
            Get progress bar
            @return Gtk.ProgressBar
        """
        return self.__progress

#######################
# PROTECTED           #
#######################
    def _on_icon_press(self, widget, icon_pos, event):
        """
            Show cert dialog or copy uri
            @param widget as Gtk.Widget
            @param icon_pos as Gtk.EntryIconPosition
            @param event as Gdk.Event
        """
        if self.__entry.get_icon_name(Gtk.EntryIconPosition.PRIMARY) ==\
                "edit-copy-symbolic":
            Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(
                                                       self.__entry.get_text(),
                                                       -1)

    def _on_enter_notify(self, widget, event):
        """
            Show uri
            @param widget as Gtk.Widget
            @param event as Gdk.Event
        """
        if self.__popover.is_visible():
            return
        parsed = urlparse(self.__uri)
        if parsed.scheme in ["http", "https", "file"]:
            self.__entry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY,
                                                 "edit-copy-symbolic")
            self.__entry.set_icon_tooltip_text(Gtk.EntryIconPosition.PRIMARY,
                                               _("Copy address"))
            self.set_text_entry(self.__uri)
        else:
            self.__set_default_placeholder()

    def _on_leave_notify(self, widget, event):
        """
            Show uri
            @param widget as Gtk.Widget
            @param event as Gdk.Event
        """
        if self.__popover.is_visible():
            return
        allocation = widget.get_allocation()
        if event.x <= 0 or\
           event.x >= allocation.width or\
           event.y <= 0 or\
           event.y >= allocation.height or\
           not isinstance(widget, Gtk.EventBox):
            self.__leave()

    def _on_entry_focus_in(self, entry, event):
        """
            Block entry on uri
            @param entry as Gtk.Entry
            @param event as Gdk.Event
        """
        if self.__popover.is_visible():
            return
        webview = self.__window.container.current.webview
        self.__action_image2.set_from_icon_name("edit-clear-symbolic",
                                                Gtk.IconSize.MENU)
        parsed = urlparse(self.__uri)
        value = webview.get_current_text_entry()
        if value:
            self.set_text_entry(value)
        elif parsed.scheme in ["http", "https", "file"]:
            self.set_text_entry(self.__uri)
            self.__placeholder.set_opacity(0)
        else:
            self.__set_default_placeholder()

    def _on_entry_focus_out(self, entry, event):
        """
            Show title
            @param entry as Gtk.Entry
            @param event as Gdk.Event (do not use)
        """
        if self.__popover.is_visible():
            return
        self.__focus_out()

    def _on_populate_popup(self, entry, menu):
        """
            @param entry as Gtk.Entry
            @param menu as Gtk.Menu
        """
        def on_item_activate(item, clipboard):
            self.__window.container.current.webview.load_uri(clipboard)
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).wait_for_text()
        if clipboard is not None:
            item = Gtk.MenuItem.new_with_label(_("Paste and load"))
            item.connect("activate", on_item_activate, clipboard)
            item.show()
            menu.attach(item, 0, 1, 3, 4)

    def _on_button_press_event(self, entry, event):
        """
            Show popover if hidden
            @param entry as Gtk.Entry
            @param event as Gdk.Event
        """
        if event.button != 1:
            return
        if event.type == Gdk.EventType.BUTTON_PRESS:
            if not self.__popover.is_visible():
                self._on_entry_focus_in(entry, event)
                self.__popover.popup("bookmarks")
        elif event.type == Gdk.EventType._2BUTTON_PRESS:
            text_len = len(self.__entry.get_text())
            self.__entry.select_region(0, text_len)
            return True

    def _on_key_press_event(self, entry, event):
        """
            Forward to popover history listbox if needed
            @param entry as Gtk.Entry
            @param event as Gdk.EventKey
        """
        webview = self.__window.container.current.webview
        uri = entry.get_text().lstrip().rstrip()

        # Walk history if Ctrl + [zZ]
        if event.state & Gdk.ModifierType.CONTROL_MASK:
            value = None
            if event.keyval == Gdk.KEY_z:
                value = webview.get_prev_text_entry(uri)
            elif event.keyval == Gdk.KEY_Z:
                value = webview.get_next_text_entry()
            if value is not None:
                self.set_text_entry(value)
                self.__entry.emit("changed")
            return

        # Forward event to popover, if not used, handle input
        forwarded = self.__popover.forward_event(event)
        if forwarded:
            return True
        else:
            # Close popover and save current entry
            if event.keyval == Gdk.KEY_Escape:
                self.__entry.delete_text(0, -1)
                webview.clear_text_entry()
                GLib.idle_add(self.__window.close_popovers)
                return True
            # Close popover, save current entry and load text content
            elif event.keyval in [Gdk.KEY_Return, Gdk.KEY_KP_Enter]:
                webview.clear_text_entry()
                GLib.idle_add(self.__window.close_popovers)
                parsed = urlparse(uri)
                # Search a missing scheme
                if uri.find(".") != -1 and not parsed.scheme:
                    db_uri = El().history.get_match(uri)
                    if db_uri is not None:
                        db_parsed = urlparse(db_uri)
                        if db_parsed.netloc.startswith("www.") and\
                                not parsed.netloc.startswith("www."):
                            uri = "%s://www.%s" % (db_parsed.scheme, uri)
                        else:
                            uri = "%s://%s" % (db_parsed.scheme, uri)
                self.__window.container.load_uri(uri)
                self.__window.container.set_expose(False)
                if self.__entry_changed_id is not None:
                    GLib.source_remove(self.__entry_changed_id)
                    self.__entry_changed_id = None
                if self.__show_related_id is not None:
                    GLib.source_remove(self.__show_related_id)
                    self.__show_related_id = None
                webview.grab_focus()
                self.__completion_model.clear()
                return True

    def _on_indicator1_press(self, eventbox, event):
        """
            Switch reading mode
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        self.__window.container.current.switch_read_mode()
        self.set_reading()
        return True

    def _on_indicator2_press(self, eventbox, event):
        """
            Disable geolocation for current or show popups
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        if self.__indicator2_image.get_icon_name()[0] ==\
                "mark-location-symbolic":
            uri = self.__window.container.current.webview.get_uri()
            El().websettings.allow_geolocation(uri, False)
            if self.__window.container.current.webview.popups:
                self.show_indicator(Indicator.POPUPS)
            else:
                self.show_indicator(Indicator.NONE)
        else:
            for popup in self.__window.container.current.webview.popups:
                self.__window.container.popup_webview(popup, False)
            if self.__entry.has_focus():
                self.__window.set_focus(None)
            else:
                self._on_entry_focus_out(self.__entry, None)
            self.__update_secure_content_indicator()
        return True

    def _on_action1_press(self, eventbox, event):
        """
            Reload current view/Stop loading
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        if self.__action_image1.get_icon_name()[0] == 'view-refresh-symbolic':
            if event.button == 1:
                self.__window.container.current.webview.reload()
            else:
                self.__window.container.current.webview.reload_bypass_cache()
        else:
            self.__window.container.current.webview.stop_loading()
        return True

    def _on_action2_press(self, eventbox, event):
        """
            Add/Remove page to/from bookmarks
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        webview = self.__window.container.current.webview
        if self.__action_image2.get_icon_name()[0] == "edit-clear-symbolic":
            self.__entry.delete_text(0, -1)
            webview.clear_text_entry()
        else:
            bookmark_id = El().bookmarks.get_id(webview.get_uri())
            if bookmark_id is None:
                uri = webview.get_uri()
                if not uri or uri == "about:blank":
                    return
                title = webview.get_title()
                if not title:
                    title = uri
                self.__action_image2.set_from_icon_name("starred-symbolic",
                                                        Gtk.IconSize.MENU)
                bookmark_id = El().bookmarks.add(title,
                                                 uri, None, [])
            from eolie.widget_bookmark_edit import BookmarkEditWidget
            widget = BookmarkEditWidget(bookmark_id, False)
            widget.show()
            popover = Gtk.Popover.new()
            popover.set_relative_to(eventbox)
            popover.connect("closed", self.__on_popover_closed)
            popover.connect("closed",
                            lambda x: self._on_entry_focus_out(
                                                       self.__entry, None))
            popover.add(widget)
            popover.popup()
        return True

    def _on_eventbox_enter_notify(self, eventbox, event):
        """
            Change opacity
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        eventbox.set_opacity(1)

    def _on_eventbox_leave_notify(self, eventbox, event):
        """
            Change opacity
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        eventbox.set_opacity(0.8)

    def _on_icon_grid_size_allocate(self, grid, allocation):
        """
            Delayed css update
            @param grid as Gtk.Grid
            @param allocation as Gtk.Allocation
        """
        if self.__size_allocation_timeout not in [None, Type.NONE]:
            GLib.source_remove(self.__size_allocation_timeout)
        # If Type.NONE, we need to create initial css content
        if self.__size_allocation_timeout == Type.NONE:
            self.__on_size_allocation_timeout(allocation)
        else:
            self.__size_allocation_timeout = GLib.timeout_add(
                                             250,
                                             self.__on_size_allocation_timeout,
                                             allocation)

#######################
# PRIVATE             #
#######################
    def __focus_out(self):
        """
            Focus out widget
        """
        view = self.__window.container.current
        self.__completion_model.clear()
        self.__placeholder.set_opacity(0.8)
        self.set_text_entry("")
        self.__update_secure_content_indicator()
        uri = view.webview.get_uri()
        if uri is not None:
            bookmark_id = El().bookmarks.get_id(uri)
            if bookmark_id is not None:
                icon_name = "starred-symbolic"
            else:
                icon_name = "non-starred-symbolic"
            self.__action_image2.set_from_icon_name(icon_name,
                                                    Gtk.IconSize.MENU)

    def __leave(self):
        """
            Leave widget
        """
        self.__update_secure_content_indicator()
        self.__placeholder.set_opacity(0.8)
        parsed = urlparse(self.__uri)
        if parsed.scheme in ["http", "https", "file"]:
            self.set_text_entry("")
        else:
            self.__set_default_placeholder()

    def __set_default_placeholder(self):
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

    def __update_secure_content_indicator(self):
        """
            Update PRIMARY icon, Gtk.Entry should be set
        """
        parsed = urlparse(self.__uri)
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

    def __show_related_view(self, value):
        """
            Walk all available views and show it if related to current uri
            @param value as str
        """
        self.__show_related_id = None
        if not value:
            self.__window.container.set_expose(False)
            return
        elif len(value) < 3:
            return
        for view in self.__window.container.views:
            uri = view.webview.get_uri()
            if uri is not None:
                view_parsed = urlparse(uri)
                if view_parsed.netloc.find(value) != -1:
                    self.__window.container.pages_manager.set_filter(value)
                    self.__window.container.set_expose(True)
                    return
        self.__window.container.set_expose(False)

    def __search_suggestion(self, uri, status, content, encoding, value):
        """
            Add suggestions
            @param uri as str
            @param status as bool
            @param content as bytes
            @param encoding as str
            @param value as str
        """
        if status and value == self.__entry.get_text():
            string = content.decode(encoding)
            # format: '["{"words"}",["result1","result2"]]'
            sgs = string.replace('[', '').replace(']', '').split(',')[1:]
            added = 0
            for suggestion in sgs:
                if suggestion:
                    self.__popover.add_suggestion(suggestion.replace('"', ''))
                    added += 1
                    if added > 2:
                        return

    def __populate_completion(self, uri):
        """
            @param uri as str
            @thread safe
        """
        if self.__entry.get_text() == uri:
            self.__completion_model.clear()
            # Look for a match in history
            match = El().history.get_match(uri)
            if match is not None:
                if self.__cancellable.is_cancelled():
                    return
                match_parsed = urlparse(match)
                netloc = match_parsed.netloc.replace("www.", "")
                if netloc.find(uri) == 0:
                    if match_parsed.path.find(uri.split("/")[-1]) != -1:
                        self.__completion_model.append([netloc +
                                                        match_parsed.path])
                    else:
                        self.__completion_model.append([netloc])

            if not El().settings.get_value("dns-prediction"):
                return
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
                        self.__completion_model.append(
                                          [lookup.replace("www.", "")])
                        return
                    except:
                        if self.__cancellable.is_cancelled():
                            return

    def __on_popover_closed(self, popover):
        """
            Clean titlebar if UriPopover, else update star
            @param popover as Gtk.popover
        """
        self.__cancellable.cancel()
        self.__cancellable.reset()
        webview = self.__window.container.current.webview
        if popover == self.__popover:
            webview.grab_focus()
            self.__focus_out()
            self.__leave()
            value = self.__entry.get_text().lstrip().rstrip()
            if value:
                webview.add_text_entry(value)
            self.__entry.delete_selection()
        from eolie.widget_bookmark_edit import BookmarkEditWidget
        if isinstance(popover, BookmarkEditWidget):
            bookmark_id = El().bookmarks.get_id(webview.get_uri())
            if bookmark_id is None:
                self.__action_image2.set_from_icon_name("non-starred-symbolic",
                                                        Gtk.IconSize.MENU)

    def __on_entry_changed(self, entry):
        """
            Delayed entry changed
            @param entry as Gtk.Entry
        """
        value = entry.get_text()
        if not value:
            webview = self.__window.container.current.webview
            webview.clear_text_entry()
        # Text change comes from completion validation ie Enter
        for completion in self.__completion_model:
            if completion[0] == value:
                return
        parsed = urlparse(value)
        is_uri = parsed.scheme in ["about, http", "file", "https", "populars"]
        parsed = urlparse(self.__uri)
        if value:
            self.__placeholder.set_opacity(0)
            # We are doing a search, show popover
            if not is_uri and not self.__popover.is_visible():
                self.__popover.popup("bookmarks")
        elif parsed.scheme in ["populars", "about"]:
            self.__set_default_placeholder()
        if self.__entry_changed_id is not None:
            GLib.source_remove(self.__entry_changed_id)
        self.__entry_changed_id = GLib.timeout_add(
                                               100,
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

        self.__window.container.current.webview.add_text_entry(value)

        # Populate completion model
        task_helper.run(self.__populate_completion, value)

        self.__cancellable.cancel()
        self.__cancellable.reset()
        parsed = urlparse(value)

        if self.__show_related_id is not None:
            GLib.source_remove(self.__show_related_id)
        self.__show_related_id = GLib.timeout_add(500,
                                                  self.__show_related_view,
                                                  value)
        network = Gio.NetworkMonitor.get_default().get_network_available()
        is_uri = parsed.scheme in ["about, http", "file", "https", "populars"]
        if is_uri:
            self.__popover.set_search_text(parsed.netloc + parsed.path)
        else:
            self.__popover.set_search_text(value)

        parsed = urlparse(self.__uri)
        if value and not is_uri and network:
            El().search.search_suggestions(value,
                                           self.__cancellable,
                                           self.__search_suggestion)

        self.__entry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY,
                                             "system-search-symbolic")
        self.__entry.set_icon_tooltip_text(Gtk.EntryIconPosition.PRIMARY,
                                           "")

    def __on_size_allocation_timeout(self, allocation):
        """
            Update css to match new allocation
            @param allocation as Gtk.Allocation
        """
        self.__size_allocation_timeout = None
        style = self.__entry.get_style_context()
        border = style.get_border(Gtk.StateFlags.NORMAL).bottom
        padding_start = style.get_padding(Gtk.StateFlags.NORMAL).left
        margin_start = style.get_margin(Gtk.StateFlags.NORMAL).left
        margin_end = style.get_margin(Gtk.StateFlags.NORMAL).right
        margin_bottom = style.get_margin(Gtk.StateFlags.NORMAL).bottom
        css = ".progressbar { margin-bottom: %spx;\
               margin-left: %spx;\
               margin-right: %spx; }" % (margin_bottom,
                                         margin_start + border,
                                         margin_end + border)
        # 5 is grid margin (see ui file)
        css += ".uribar { padding-right: %spx; }" % (allocation.width + 5)
        # 22 is Gtk.EntryIconPosition.PRIMARY
        placeholder_margin_start = padding_start + 22 + border
        css += ".placeholder {margin-left: %spx;}" % placeholder_margin_start
        # Get value from headerbar as not possible in pure CSS
        style_context = self.get_style_context()
        color = style_context.get_color(Gtk.StateFlags.NORMAL).to_string()
        css += ".uribar { color: %s; caret-color:%s}" % (color, color)
        self.__css_provider.load_from_data(css.encode("utf-8"))
