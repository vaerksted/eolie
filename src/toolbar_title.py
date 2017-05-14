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

from threading import Thread
from gettext import gettext as _
from urllib.parse import urlparse

from eolie.define import El
from eolie.popover_uri import UriPopover
from eolie.widget_edit_bookmark import EditBookmarkWidget


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
        self.__text_entry_history = {}
        self.__input_warning_shown = False
        self.__lock_focus = False
        self.__signal_id = None
        self.__secure_content = True
        self.__keywords_timeout = None
        self.__icon_grid_width = None
        self.__uri = ""
        self.__keywords_cancellable = Gio.Cancellable.new()
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/ToolbarTitle.ui")
        builder.connect_signals(self)
        self.__entry = builder.get_object("entry")
        self.__popover = UriPopover(window)
        self.__popover.set_relative_to(self)
        self.__popover.connect("closed", self.__on_popover_closed)
        # Reload/Stop
        self.__action_image1 = builder.get_object("action_image1")
        # Bookmarks/Clear
        self.__action_image2 = builder.get_object("action_image2")
        self.__readable_image = builder.get_object("readable_image")
        self.add(builder.get_object("widget"))
        # Some on the fly css styling
        context = self.__entry.get_style_context()
        self.__css_provider = Gtk.CssProvider()
        context.add_provider_for_screen(Gdk.Screen.get_default(),
                                        self.__css_provider,
                                        Gtk.STYLE_PROVIDER_PRIORITY_USER)
        self.__progress = builder.get_object("progress")
        self.__readable_indicator = builder.get_object("readable_indicator")
        self.__popup_indicator = builder.get_object("popup_indicator")
        self.__placeholder = builder.get_object("placeholder")
        self.__signal_id = self.__entry.connect("changed",
                                                self.__on_entry_changed)

    def show_readable_button(self, b):
        """
            Show readable button
            @param b as bool
        """
        if b:
            self.__readable_indicator.show()
            self.set_reading()
        else:
            self.__readable_indicator.hide()

    def set_reading(self):
        """
            Mark readable button
        """
        if self.__window.container.current.reading:
            self.__readable_image.get_style_context().add_class("selected")
        else:
            self.__readable_image.get_style_context().remove_class("selected")

    def set_width(self, width):
        """
            Set Gtk.Scale progress width
            @param width as int
        """
        self.set_property("width_request", width)

    def set_text_entry(self, text):
        """
            Set uri in Gtk.Entry
            @param text as str
        """
        if self.__entry.get_text() == text:
            return
        if self.__signal_id is not None:
            self.__entry.disconnect(self.__signal_id)
        # Do not show this in titlebar
        parsed = urlparse(text)
        if parsed.scheme in ["populars", "about"]:
            text = ""
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
            Update entry
            @param text as str
        """
        if uri == self.__uri:
            return
        self.__uri = uri
        self.__input_warning_shown = False
        self.__secure_content = True
        self.__entry.get_style_context().remove_class('uribar-title')
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
        # Do not show this in titlebar
        parsed = urlparse(self.__uri)
        if parsed.scheme in ["populars", "about"]:
            self.__set_default_placeholder()
            return
        self.__placeholder.set_text(title)
        if not self.__lock_focus and\
                not self.__popover.is_visible():
            self.__placeholder.set_opacity(0.8)
            self.__entry.get_style_context().add_class('uribar-title')
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
        self.__lock_focus = True
        popover = JavaScriptPopover(dialog)
        popover.set_relative_to(self.__entry)
        popover.connect("closed", self.__on_popover_closed)
        popover.show()

    def show_input_warning(self, webview):
        """
            Show a message to user about password input field over http
            @param webview as WebView
        """
        if self.__input_warning_shown:
            return
        self.__input_warning_shown = True
        js = 'alert("%s");' % _(
                "Heads-up: this page is not secure.\\n"
                "If you type your password,\\n it will be "
                "visible to cybercriminals!")
        webview.run_javascript(js, None, None)

    def close_popover(self):
        """
            Close popover if needed
        """
        if self.__popover.is_visible():
            self.__lock_focus = False
            self.__popover.hide()
            self.__keywords_cancellable.cancel()
            self.__keywords_cancellable.reset()
            if self.__entry.has_focus():
                self.__window.set_focus(None)
            else:
                self._on_entry_focus_out(self.__entry, None)
            self.__update_secure_content_indicator()

    def focus_entry(self):
        """
            Focus entry
        """
        self.get_toplevel().set_focus(self.__entry)
        if not self.__popover.is_visible():
            self.__lock_focus = True
            self.__popover.show()

    def save_password(self, username, password, uri):
        """
            Show a popover allowing user to save password
            @param username as str
            @param password as str
            @param uri as str
        """
        from eolie.popover_password import PasswordPopover
        self.__lock_focus = True
        popover = PasswordPopover(username, password, uri)
        popover.set_relative_to(self.__entry)
        popover.set_pointing_to(self.__entry.get_icon_area(
                                                Gtk.EntryIconPosition.PRIMARY))
        popover.connect("closed", self.__on_popover_closed)
        popover.show()

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
        self.__entry.grab_focus()

    def set_lock_focus(self, locked):
        """
            Set focus to be locked
            @param locked as bool
        """
        self.__lock_focus = locked

    def remove_from_text_entry_history(self, webview):
        """
            Remove history for view
            @param view as WebView
        """
        if webview in self.__text_entry_history.keys():
            del self.__text_entry_history[webview]

    def show_popup_indicator(self, b):
        """
            Show popups indicator
            @param b as bool
        """
        if b:
            self.__popup_indicator.show()
        else:
            self.__popup_indicator.hide()

    @property
    def uri(self):
        """
            Get current uri
            @return str
        """
        return self.__uri

    @property
    def lock_focus(self):
        """
            Get lock focus
            @return bool
        """
        return self.__lock_focus

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
        if self.__lock_focus:
            return True
        parsed = urlparse(self.__uri)
        if parsed.scheme in ["http", "https"]:
            self.__entry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY,
                                                 "edit-copy-symbolic")
            self.__entry.set_icon_tooltip_text(Gtk.EntryIconPosition.PRIMARY,
                                               _("Copy address"))
            self.set_text_entry(self.__uri)
        else:
            self.__set_default_placeholder()
            self.set_text_entry("")
        self.__entry.get_style_context().remove_class("uribar-title")

    def _on_leave_notify(self, widget, event):
        """
            Show uri
            @param widget as Gtk.Widget
            @param event as Gdk.Event
        """
        if self.__lock_focus:
            return True
        allocation = widget.get_allocation()
        if event.x <= 0 or\
           event.x >= allocation.width or\
           event.y <= 0 or\
           event.y >= allocation.height or\
           not isinstance(widget, Gtk.EventBox):
            self.__update_secure_content_indicator()
            self.__placeholder.set_opacity(0.8)
            parsed = urlparse(self.__uri)
            if parsed.scheme in ["http", "https"]:
                self.__entry.get_style_context().add_class('uribar-title')
                self.set_text_entry("")
            else:
                self.__set_default_placeholder()

    def _on_entry_focus_in(self, entry, event):
        """
            Block entry on uri
            @param entry as Gtk.Entry
            @param event as Gdk.Event
        """
        # Needed here too because we don't want to set uri again when
        # window get focus. (don't want to clear user input)
        if self.__lock_focus:
            return True
        self.__entry.get_style_context().remove_class("uribar-title")
        self.__entry.get_style_context().add_class("input")

        # Restore previous user entry
        webview = self.__window.container.current.webview
        if webview in self.__text_entry_history.keys():
            value = self.__text_entry_history[webview]
            if value:
                self.set_text_entry(value)
        else:
            self.set_text_entry(self.__uri)
        self.__action_image2.set_from_icon_name("edit-clear-symbolic",
                                                Gtk.IconSize.MENU)
        parsed = urlparse(self.__uri)
        if parsed.scheme in ["http", "https"]:
            self.__placeholder.set_opacity(0)
        else:
            self.__set_default_placeholder()

    def _on_entry_focus_out(self, entry, event):
        """
            Show title
            @param entry as Gtk.Entry
            @param event as Gdk.Event (do not use)
        """
        if self.__lock_focus:
            return True
        self.__placeholder.set_opacity(0.8)
        self.__entry.get_style_context().add_class("uribar-title")
        self.__entry.get_style_context().remove_class("input")
        self.set_text_entry("")
        view = self.__window.container.current
        bookmark_id = El().bookmarks.get_id(view.webview.get_uri())
        if bookmark_id is not None:
            icon_name = "starred-symbolic"
        else:
            icon_name = "non-starred-symbolic"
        self.__action_image2.set_from_icon_name(icon_name,
                                                Gtk.IconSize.MENU)

    def _on_button_press_event(self, entry, event):
        """
            Show popover if hidden
            @param entry as Gtk.Entry
            @param event as Gdk.Event
        """
        if event.type == Gdk.EventType.BUTTON_PRESS:
            if not self.__popover.is_visible():
                self._on_entry_focus_in(entry, event)
                self.__lock_focus = True
                self.__popover.show()
        elif event.type == Gdk.EventType._2BUTTON_PRESS:
            text_len = len(self.__entry.get_text())
            self.__entry.select_region(0, text_len)
            return True

    def _on_key_press_event(self, entry, event):
        """
            Forward to popover history listbox if needed
            @param entry as Gtk.Entry
            @param event as Gdk.Event
        """
        forwarded = self.__popover.forward_event(event)
        if forwarded:
            self.__entry.get_style_context().remove_class('input')
            return True
        else:
            self.__entry.get_style_context().add_class('input')
            if event.keyval in [Gdk.KEY_Return,
                                Gdk.KEY_KP_Enter,
                                Gdk.KEY_Escape]:
                GLib.idle_add(self.close_popover)

    def _on_readable_indicator_press(self, eventbox, event):
        """
            Reload current view/Stop loading
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        self.__window.container.current.switch_read_mode()
        self.set_reading()
        return True

    def _on_popup_indicator_press(self, eventbox, event):
        """
            Reload current view/Stop loading
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        for popup in self.__window.container.current.webview.popups:
            self.__window.container.popup_webview(popup)
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
            self.__window.container.current.webview.reload()
        else:
            self.__window.container.current.webview.stop_loading()
        return True

    def _on_action2_press(self, eventbox, event):
        """
            Add/Remove page to/from bookmarks
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        view = self.__window.container.current
        if self.__action_image2.get_icon_name()[0] == "edit-clear-symbolic":
            self.__entry.delete_text(0, -1)
        else:
            bookmark_id = El().bookmarks.get_id(view.webview.get_uri())
            if bookmark_id is None:
                uri = view.webview.get_uri()
                if not uri or uri == "about:blank":
                    return
                title = view.webview.get_title()
                if not title:
                    title = uri
                self.__action_image2.set_from_icon_name("starred-symbolic",
                                                        Gtk.IconSize.MENU)
                bookmark_id = El().bookmarks.add(title,
                                                 uri, None, [])

            widget = EditBookmarkWidget(bookmark_id, False)
            widget.show()
            popover = Gtk.Popover.new()
            popover.set_relative_to(eventbox)
            popover.connect("closed", self.__on_popover_closed)
            popover.connect("closed",
                            lambda x: self._on_entry_focus_out(
                                                       self.__entry, None))
            popover.add(widget)
            popover.set_size_request(self.__window.get_size()[0]/2.5, -1)
            self.__lock_focus = True
            popover.show()
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

    def _on_activate(self, entry):
        """
            Go to url or search for words
            @param entry as Gtk.Entry
        """
        uri = entry.get_text()
        parsed = urlparse(uri)
        is_uri = parsed.scheme in ["about", "http",
                                   "https", "file", "populars"]
        if not is_uri and\
                El().search.is_search(uri):
            uri = El().search.get_search_uri(uri)
        self.__window.container.load_uri(uri)
        self.__window.container.current.webview.grab_focus()

    def _on_icon_grid_size_allocate(self, grid, allocation):
        """
            Update margins
            @param grid as Gtk.Grid
            @param allocation as Gtk.Allocation
        """
        # Injecting css on size allocation may make GTK3 segfaults
        # We prevent only update css if width change
        if allocation.width == self.__icon_grid_width:
            return
        self.__icon_grid_width = allocation.width
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
        # Let GTK finish current resizing before injecting css
        self.__css_provider.load_from_data(css.encode("utf-8"))

#######################
# PRIVATE             #
#######################
    def __set_default_placeholder(self):
        """
            Show search placeholder
        """
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
        if parsed.scheme == "https" and self.__secure_content:
            self.__entry.set_icon_from_icon_name(
                                        Gtk.EntryIconPosition.PRIMARY,
                                        "channel-secure-symbolic")
        else:
            self.set_insecure_content()

    def __search_keywords_thread(self, value):
        """
            Run __search_keywords() in a thread
            @param value a str
        """
        self.__keywords_timeout = None
        self.__thread = Thread(target=self.__search_keywords,
                               args=(value,))
        self.__thread.daemon = True
        self.__thread.start()

    def __search_keywords(self, value):
        """
            Search for keywords for value
            @param value as str
        """
        self.__keywords_cancellable.reset()
        keywords = El().search.get_keywords(value, self.__keywords_cancellable)
        for words in keywords:
            if words:
                GLib.idle_add(self.__popover.add_keywords,
                              words.replace('"', ''))

    def __on_popover_closed(self, popover):
        """
            Destroy popover
            @param popover as Gtk.popover
        """
        self.__lock_focus = False
        uri = self.__window.container.current.webview.get_uri()
        self.__entry.delete_selection()
        if uri is not None:
            self.set_uri(uri)
        if isinstance(popover, EditBookmarkWidget):
            view = self.__window.container.current
            bookmark_id = El().bookmarks.get_id(view.webview.get_uri())
            if bookmark_id is None:
                self.__action_image2.set_from_icon_name("non-starred-symbolic",
                                                        Gtk.IconSize.MENU)

    def __on_entry_changed(self, entry):
        """
            Update popover search if needed
            @param entry as Gtk.Entry
        """
        value = entry.get_text()
        webview = self.__window.container.current.webview
        self.__text_entry_history[webview] = self.__entry.get_text()
        self.__keywords_cancellable.cancel()
        parsed = urlparse(value)
        network = Gio.NetworkMonitor.get_default().get_network_available()
        is_uri = parsed.scheme in ["about, http", "file", "https", "populars"]
        if is_uri:
            self.__popover.set_search_text(parsed.netloc + parsed.path)
        else:
            self.__popover.set_search_text(value)

        parsed = urlparse(self.__uri)
        if value:
            self.__placeholder.set_opacity(0)
            # We are doing a search, show popover
            if not is_uri and not self.__popover.is_visible():
                self.__lock_focus = True
                self.__popover.show()
        elif parsed.scheme in ["populars", "about"]:
            self.__set_default_placeholder()
        if self.__keywords_timeout is not None:
            GLib.source_remove(self.__keywords_timeout)
            self.__keywords_timeout = None
        if not is_uri and network:
            self.__keywords_timeout = GLib.timeout_add(
                                                 500,
                                                 self.__search_keywords_thread,
                                                 value)
        self.__entry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY,
                                             "system-search-symbolic")
        self.__entry.set_icon_tooltip_text(Gtk.EntryIconPosition.PRIMARY,
                                           "")
