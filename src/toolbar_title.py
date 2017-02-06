# Copyright (c) 2014-2016 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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
from eolie.utils import strip_uri
from eolie.popover_uri import UriPopover


class ToolbarTitle(Gtk.Bin):
    """
        Title toolbar
    """

    def __init__(self):
        """
            Init toolbar
        """
        Gtk.Bin.__init__(self)
        self.__uri = ""
        self.__lock = False
        self.__in_notify = False
        self.__signal_id = None
        self.__keywords_timeout = None
        self.__keywords_cancellable = Gio.Cancellable.new()
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/ToolbarTitle.ui")
        builder.connect_signals(self)
        self.__entry = builder.get_object("entry")
        self.__popover = UriPopover()
        self.__action_image = builder.get_object("action_image")
        self.add(builder.get_object('widget'))
        # Some on the fly css styling
        context = self.__entry.get_style_context()
        self.__css_provider = Gtk.CssProvider()
        context.add_provider_for_screen(Gdk.Screen.get_default(),
                                        self.__css_provider,
                                        Gtk.STYLE_PROVIDER_PRIORITY_USER)
        self.__progress = builder.get_object("progress")
        self.__bookmark_image = builder.get_object("bookmark_image")

    def set_width(self, width):
        """
            Set Gtk.Scale progress width
            @param width as int
        """
        self.set_property("width_request", width)

    def show_uri(self, uri):
        """
            Just show uri in titlebar
        """
        self.__entry.set_placeholder_text(uri)

    def set_uri(self, uri):
        """
            Update entry
            @param text as str
        """
        if uri is not None:
            self.__entry.set_icon_tooltip_text(Gtk.EntryIconPosition.PRIMARY,
                                               "")
            if uri.startswith("https://"):
                self.__entry.set_icon_from_icon_name(
                                            Gtk.EntryIconPosition.PRIMARY,
                                            'channel-secure-symbolic')
            else:
                self.__entry.set_icon_from_icon_name(
                                            Gtk.EntryIconPosition.PRIMARY,
                                            None)
            # Some uri update may not change title
            if strip_uri(uri) != strip_uri(self.__uri):
                if not self.__popover.is_visible():
                    self.__entry.set_text(uri)
                self.__entry.set_placeholder_text("")
            self.__entry.get_style_context().remove_class('uribar-title')
            self.__uri = uri
            bookmark_id = El().bookmarks.get_id(uri)
            if bookmark_id is not None:
                icon_name = "starred-symbolic"
            else:
                icon_name = "non-starred-symbolic"
            self.__bookmark_image.set_from_icon_name(icon_name,
                                                     Gtk.IconSize.MENU)

    def set_insecure_content(self):
        """
            Mark uri as insecure
        """
        if not self.__uri.startswith("https://") or\
                self.__entry.get_icon_name(Gtk.EntryIconPosition.PRIMARY) ==\
                'channel-insecure-symbolic':
            return
        self.__entry.set_icon_tooltip_text(
                                      Gtk.EntryIconPosition.PRIMARY,
                                      _("This page contains insecure content"))
        self.__entry.set_icon_from_icon_name(
                                        Gtk.EntryIconPosition.PRIMARY,
                                        'channel-insecure-symbolic')

    def set_title(self, title):
        """
            Show title instead of uri
        """
        if title is not None:
            self.__entry.set_placeholder_text(title)
            if not self.__lock and\
                    not self.__in_notify and\
                    not self.__popover.is_visible():
                self.__entry.set_text("")
                self.__entry.get_style_context().add_class('uribar-title')

    def hide_popover(self):
        """
            hide popover if needed
        """
        self.__lock = False
        self.__in_notify = False
        if self.__popover.is_visible():
            self.__popover.hide()
            self.__keywords_cancellable.cancel()
            self.__keywords_cancellable.reset()
            El().active_window.set_focus(None)

    def focus_entry(self):
        """
            Focus entry
        """
        self.get_toplevel().set_focus(self.__entry)

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
        popover.show()

    def on_load_changed(self, view, event):
        """
            Update action image
            @param view as WebView
            @param event as WebKit2.LoadEvent
        """
        if view.is_loading():
            self.__action_image.set_from_icon_name('process-stop-symbolic',
                                                   Gtk.IconSize.MENU)
        else:
            self.__action_image.set_from_icon_name('view-refresh-symbolic',
                                                   Gtk.IconSize.MENU)

    @property
    def progress(self):
        """
            Get progress bar
            @return Gtk.ProgressBar
        """
        return self.__progress

    @property
    def focus_in(self):
        """
            Return True if title bar has focus
            @return bool
        """
        return self.__popover.is_visible()

#######################
# PROTECTED           #
#######################
    def _on_map(self, grid):
        """
            Update entry padding
        """
        border = self.__entry.get_style_context().get_border(
                                                  Gtk.StateFlags.NORMAL).bottom
        margin_start = self.__entry.get_style_context().get_margin(
                                                  Gtk.StateFlags.NORMAL).left
        margin_end = self.__entry.get_style_context().get_margin(
                                                  Gtk.StateFlags.NORMAL).right
        margin_bottom = self.__entry.get_style_context().get_margin(
                                                  Gtk.StateFlags.NORMAL).bottom
        css = ".progressbar { margin-bottom: %spx;\
               margin-left: %spx;\
               margin-right: %spx; }" % (margin_bottom,
                                         margin_start + border,
                                         margin_end + border)
        # 5 is grid margin (see ui file)
        width = grid.get_allocated_width()
        css += ".uribar { padding-right: %spx; }" % (width + 5)
        self.__css_provider.load_from_data(css.encode("utf-8"))

    def _on_enter_notify(self, eventbox, event):
        """
            Show uri
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        self.__in_notify = True
        current_text = self.__entry.get_text()
        if current_text == "":
            self.__entry.set_text(self.__uri)
            self.__entry.get_style_context().remove_class('uribar-title')

    def _on_leave_notify(self, eventbox, event):
        """
            Show uri
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        allocation = eventbox.get_allocation()
        if event.x <= 0 or\
           event.x >= allocation.width or\
           event.y <= 0 or\
           event.y >= allocation.height:
            self.__in_notify = False
            if self.__entry.get_placeholder_text() and\
                    self.__entry.get_text() and\
                    not self.__lock:
                self.__entry.set_text("")
                self.__entry.get_style_context().add_class('uribar-title')

    def _on_entry_focus_in(self, entry, event):
        """
            Block entry on uri
            @param entry as Gtk.Entry
            @param event as Gdk.Event
        """
        self.__lock = True
        self.__entry.set_text(self.__uri)
        self.__entry.get_style_context().remove_class('uribar-title')
        self.__entry.get_style_context().add_class('input')
        self.__popover.set_relative_to(self)
        self.__popover.show()
        self.__signal_id = self.__entry.connect('changed',
                                                self.__on_entry_changed)

    def _on_entry_focus_out(self, entry, event):
        """
            Show title
            @param entry as Gtk.Entry
            @param event as Gdk.Event
        """
        self.__lock = False
        if self.__signal_id is not None:
            self.__entry.disconnect(self.__signal_id)
            self.__signal_id = None
        if self.__entry.get_placeholder_text():
            self.__entry.set_text("")
            self.__entry.get_style_context().add_class('uribar-title')
        self.__entry.get_style_context().remove_class('input')

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

    def _on_action_press(self, eventbox, event):
        """
            Reload current view
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        if self.__action_image.get_icon_name()[0] == 'view-refresh-symbolic':
            El().active_window.container.current.reload()
        else:
            El().active_window.container.current.stop_loading()

    def _on_bookmark_press(self, eventbox, event):
        """
            Add/Remove page to/from bookmarks
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        view = El().active_window.container.current
        from eolie.widget_edit_bookmark import EditBookmarkWidget
        if self.__bookmark_image.get_icon_name()[0] == "starred-symbolic":
            self.__bookmark_image.set_from_icon_name("non-starred-symbolic",
                                                     Gtk.IconSize.MENU)
            bookmark_id = El().bookmarks.get_id(view.get_uri())
            El().bookmarks.remove(bookmark_id)
        else:
            self.__bookmark_image.set_from_icon_name("starred-symbolic",
                                                     Gtk.IconSize.MENU)
            bookmark_id = El().bookmarks.add(view.get_title(),
                                             view.get_uri(), [])
            widget = EditBookmarkWidget(bookmark_id, False)
            widget.show()
            popover = Gtk.Popover.new()
            size = El().active_window.get_size()
            popover.set_size_request(size[0]*0.3, size[1]*0.5)
            popover.set_relative_to(eventbox)
            popover.add(widget)
            popover.show()

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
        if El().search.is_search(uri):
            uri = El().search.get_search_uri(uri)
        El().active_window.container.load_uri(uri)

#######################
# PRIVATE             #
#######################
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

    def __on_entry_changed(self, entry):
        """
            Update popover search if needed
        """
        value = entry.get_text()
        if value == self.__uri:
            self.__popover.set_search_text("")
        else:
            self.__popover.set_search_text(value)
        if self.__keywords_timeout is not None:
            GLib.source_remove(self.__keywords_timeout)
        parsed = urlparse(value)
        if not parsed.scheme.startswith("http") and\
                Gio.NetworkMonitor.get_default().get_network_available():
            self.__keywords_timeout = GLib.timeout_add(
                                                 500,
                                                 self.__search_keywords_thread,
                                                 value)
