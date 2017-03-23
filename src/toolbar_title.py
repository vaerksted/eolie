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
        self.__lock_focus = False
        self.__signal_id = None
        self.__secure_content = True
        self.__keywords_timeout = None
        self.__icon_grid_width = None
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
        self.__readable = builder.get_object("readable")
        self.__placeholder = builder.get_object("placeholder")
        self.__window.connect("leave-notify-event", self._on_leave_notify)
        self.__signal_id = self.__entry.connect("changed",
                                                self.__on_entry_changed)

    def show_readable_button(self, b):
        """
            Show readable button
            @param b as bool
        """
        if b:
            self.__readable.show()
        else:
            self.__readable.hide()

    def set_width(self, width):
        """
            Set Gtk.Scale progress width
            @param width as int
        """
        self.set_property("width_request", width)

    def set_uri(self, uri):
        """
            Update entry
            @param text as str
        """
        try:
            if self.__signal_id is not None:
                self.__entry.disconnect(self.__signal_id)
            # Do not show this in titlebar
            parsed = urlparse(uri)
            if parsed.scheme == "populars":
                self.__entry.set_text("")
                raise
            elif not uri or uri == self.__entry.get_text():
                raise
            self.__secure_content = True
            if self.__window.container.current.webview.readable[0]:
                self.__readable_image.get_style_context().add_class("selected")
            else:
                self.__readable_image.get_style_context().remove_class(
                                                                    "selected")
            self.__entry.set_icon_tooltip_text(Gtk.EntryIconPosition.PRIMARY,
                                               "")
            self.__entry.set_text(uri)
            self.__placeholder.set_opacity(0)
            self.__entry.get_style_context().remove_class('uribar-title')
            self.__update_secure_content_indicator()
            bookmark_id = El().bookmarks.get_id(uri)
            if bookmark_id is not None:
                icon_name = "starred-symbolic"
            else:
                icon_name = "non-starred-symbolic"
            self.__action_image2.set_from_icon_name(icon_name,
                                                    Gtk.IconSize.MENU)
        except:
            pass
        self.__signal_id = self.__entry.connect("changed",
                                                self.__on_entry_changed)

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

    def set_title(self, title):
        """
            Show title instead of uri
        """
        if title:
            self.__placeholder.set_text(title)
            if not self.__lock_focus and\
                    not self.__popover.is_visible():
                self.__placeholder.set_opacity(0.8)
                self.__entry.get_style_context().add_class('uribar-title')

    def hide_popover(self):
        """
            hide popover if needed
        """
        if self.__popover.is_visible():
            self.__popover.hide()
            self.__keywords_cancellable.cancel()
            self.__keywords_cancellable.reset()
            self.__window.set_focus(None)

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
        popover = PasswordPopover(username, password, uri)
        popover.set_relative_to(self.__entry)
        popover.set_pointing_to(self.__entry.get_icon_area(
                                                Gtk.EntryIconPosition.PRIMARY))
        popover.connect("closed", self.__on_popover_closed)
        popover.show()

    def on_load_changed(self, view, event):
        """
            Update action image
            @param view as WebView
            @param event as WebKit2.LoadEvent
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
    def _on_enter_notify(self, widget, event):
        """
            Show uri
            @param widget as Gtk.Widget
            @param event as Gdk.Event
        """
        if self.__lock_focus:
            return True
        if self.__entry.get_text():
            self.__placeholder.set_opacity(0)
        else:
            self.__placeholder.set_text(_("Search or enter address"))
            self.__placeholder.set_opacity(0.8)
        self.__entry.get_style_context().remove_class('uribar-title')

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
            self.__placeholder.set_opacity(0.8)
            if not self.__entry.get_text():
                self.__placeholder.set_text(_("Search or enter address"))
            elif not self.__lock_focus:
                self.__entry.get_style_context().add_class('uribar-title')

    def _on_entry_focus_in(self, entry, event):
        """
            Block entry on uri
            @param entry as Gtk.Entry
            @param event as Gdk.Event
        """
        if self.__lock_focus:
            return True
        self.__entry.get_style_context().remove_class("uribar-title")
        self.__entry.get_style_context().add_class("input")
        self.__action_image2.set_from_icon_name("edit-clear-symbolic",
                                                Gtk.IconSize.MENU)
        if self.__entry.get_text():
            self.__placeholder.set_opacity(0)
        else:
            self.__placeholder.set_text(_("Search or enter address"))
            self.__placeholder.set_opacity(0.8)
        self.__update_secure_content_indicator()

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
        view = self.__window.container.current
        bookmark_id = El().bookmarks.get_id(view.webview.get_uri())
        if bookmark_id is not None:
            icon_name = "starred-symbolic"
        else:
            icon_name = "non-starred-symbolic"
        self.__action_image2.set_from_icon_name(icon_name,
                                                Gtk.IconSize.MENU)
        self.__update_secure_content_indicator()

    def _on_button_press_event(self, entry, event):
        """
            Show popover if hidden
            @param entry as Gtk.Entry
            @param event as Gdk.Event
        """
        if not self.__popover.is_visible():
            self.__lock_focus = True
            self.__popover.show()

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
                GLib.idle_add(self.hide_popover)

    def _on_readable_press(self, eventbox, event):
        """
            Reload current view/Stop loading
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        self.__window.container.current.webview.switch_read_mode()
        if self.__window.container.current.webview.readable[0]:
            self.__readable_image.get_style_context().add_class("selected")
        else:
            self.__readable_image.get_style_context().remove_class("selected")

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
        from eolie.widget_edit_bookmark import EditBookmarkWidget
        if self.__action_image2.get_icon_name()[0] == "starred-symbolic":
            self.__action_image2.set_from_icon_name("non-starred-symbolic",
                                                    Gtk.IconSize.MENU)
            bookmark_id = El().bookmarks.get_id(view.webview.get_uri())
            El().bookmarks.remove(bookmark_id)
            if El().sync_worker is not None:
                El().sync_worker.sync()
        elif self.__action_image2.get_icon_name()[0] == "non-starred-symbolic":
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
            popover.set_size_request(300, 500)
            popover.set_relative_to(eventbox)
            popover.connect("closed", self.__on_popover_closed)
            popover.connect("closed",
                            lambda x: self._on_entry_focus_out(
                                                           self.__entry, None))
            popover.add(widget)
            self.__lock_focus = True
            popover.show()
        elif self.__action_image2.get_icon_name()[0] == "edit-clear-symbolic":
            self.__entry.delete_text(0, -1)
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
        if parsed.scheme not in ["http", "https", "file", "populars"] and\
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
    def __update_secure_content_indicator(self):
        """
            Update PRIMARY icon
        """
        parsed = urlparse(self.__entry.get_text())
        if parsed.scheme == "https" and self.__secure_content:
            self.__entry.set_icon_from_icon_name(
                                        Gtk.EntryIconPosition.PRIMARY,
                                        'channel-secure-symbolic')
        elif parsed.scheme == "http":
            self.set_insecure_content()
        else:
            self.__entry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY,
                                                 "system-search-symbolic")
            self.__entry.set_icon_tooltip_text(Gtk.EntryIconPosition.PRIMARY,
                                               "")

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
        self.__keywords_cancellable.cancel()
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

    def __on_entry_changed(self, entry):
        """
            Update popover search if needed
        """
        value = entry.get_text()
        parsed = urlparse(value)
        network = Gio.NetworkMonitor.get_default().get_network_available()
        is_uri = parsed.scheme in ["http", "file", "https", "populars"]
        if is_uri:
            self.__popover.set_search_text(parsed.netloc + parsed.path)
        else:
            self.__popover.set_search_text(value)
        if value:
            self.__placeholder.set_opacity(0)
            # We are doing a search, show popover
            if not is_uri and not self.__popover.is_visible():
                self.__lock_focus = True
                self.__popover.show()
        else:
            self.__placeholder.set_text(_("Search or enter address"))
            self.__placeholder.set_opacity(0.8)
        if self.__keywords_timeout is not None:
            GLib.source_remove(self.__keywords_timeout)
            self.__keywords_timeout = None
        if not is_uri and network:
            self.__keywords_timeout = GLib.timeout_add(
                                                 500,
                                                 self.__search_keywords_thread,
                                                 value)
        self.__update_secure_content_indicator()
