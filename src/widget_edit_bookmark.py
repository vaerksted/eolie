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

from gi.repository import Gtk, GLib

from locale import strcoll
from time import time
from gettext import gettext as _

from eolie.define import El


class TagWidget(Gtk.FlowBoxChild):
    """
        Tag widget with some visual effects
    """

    def __init__(self):
        """
            Init widget
        """
        Gtk.FlowBoxChild.__init__(self)
        self.__active = False
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/TagWidget.ui")
        builder.connect_signals(self)
        self.__label = builder.get_object("label")
        self.__close_button = builder.get_object("close_button")
        self.set_property("halign", Gtk.Align.START)
        self.set_property("valign", Gtk.Align.START)
        self.add(builder.get_object("widget"))

    def set_label(self, label):
        """
            Set label
            @param label as str
        """
        self.__label.set_text(label)
        self.__label.set_tooltip_text(label)

    @property
    def label(self):
        """
            Get label
            @return str
        """
        return self.__label.get_text()

    @property
    def removable(self):
        """
            True if removable
            @return bool
        """
        return self.__close_button.is_visible()

    def set_removable(self, removable):
        """
            Make tag removable
            @param removable as bool
        """
        if removable:
            self.__close_button.show()
        else:
            self.__close_button.hide()

    def set_active(self, active):
        """
            Mark tag as active
            @param active as bool
        """
        self.__active = active
        if active:
            self.__label.get_style_context().add_class("tag-set")
        else:
            self.__label.get_style_context().remove_class("tag-set")
        self.__label.get_style_context().remove_class("tag-hover")

#######################
# PROTECTED           #
#######################
    def _on_close_button_press(self, eventbox, event):
        """
            Remove tag
            @param eventbox as Gtk.EventBox
            @param event as Gtk.Event
        """
        tag_title = self.__label.get_text()
        El().bookmarks.del_tag(tag_title, True)
        self.destroy()

    def _on_enter_notify(self, eventbox, event):
        """
            Update style
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        if self.__close_button.is_visible():
            return
        if self.__active:
            self.__label.get_style_context().remove_class("tag-set")
        self.__label.get_style_context().add_class("tag-hover")

    def _on_leave_notify(self, eventbox, event):
        """
            Update style
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        if self.__close_button.is_visible():
            return
        if self.__active:
            self.__label.get_style_context().add_class("tag-set")
        self.__label.get_style_context().remove_class("tag-hover")

    def _on_close_enter_notify(self, eventbox, event):
        """
            Update style
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        eventbox.set_opacity(1)

    def _on_close_leave_notify(self, eventbox, event):
        """
            Update style
            @param eventbox as Gtk.EventBox
            @param event as Gdk.Event
        """
        eventbox.set_opacity(0.7)


class EditBookmarkWidget(Gtk.Bin):
    """
        Widget allowing to edit a bookmark
    """

    def __init__(self, bookmark_id, back_enabled=True):
        """
            Init widget
            @param bookmark id as int
            @param enable back button as bool
        """
        Gtk.Bin.__init__(self)
        self.__bookmark_id = bookmark_id
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/BookmarkEdit.ui")
        builder.connect_signals(self)
        self.__flowbox = builder.get_object("flowbox")
        self.__flowbox.set_sort_func(self.__sort_tags)
        self.__flowbox.connect("child-activated", self.__on_tag_activated)
        self.__add_tag_button = builder.get_object("add_tag_button")
        self.__remove_tag_button = builder.get_object("remove_tag_button")
        self.__new_tag_entry = builder.get_object("new_tag_entry")
        self.__title_entry = builder.get_object("title_entry")
        self.__uri_entry = builder.get_object("uri_entry")
        self.__title_entry.set_text(El().bookmarks.get_title(bookmark_id))
        self.__uri_entry.set_text(El().bookmarks.get_uri(bookmark_id))
        for (tag_id, title) in El().bookmarks.get_all_tags():
            tag = TagWidget()
            tag.set_label(title)
            if El().bookmarks.has_tag(bookmark_id, title):
                tag.set_active(True)
            tag.show()
            self.__flowbox.add(tag)
        # Some magic here but look ok when removing button
        # May need a better tweak later
        if not back_enabled:
            builder.get_object("back_button").hide()
            self.set_margin_start(20)
            self.set_margin_top(20)
        self.add(builder.get_object("widget"))
        self.connect("unmap", self.__on_unmap)

#######################
# PROTECTED           #
#######################
    def _on_back_clicked(self, button):
        """
            Destroy self
            @param button as Gtk.Button
        """
        self.disconnect_by_func(self.__on_unmap)
        El().bookmarks.set_title(self.__bookmark_id,
                                 self.__title_entry.get_text())
        El().bookmarks.set_uri(self.__bookmark_id,
                               self.__uri_entry.get_text())
        self.get_parent().set_visible_child_name("bookmarks")
        if El().sync_worker is not None:
            mtimes = El().sync_worker.mtimes
            if mtimes["bookmarks"] == 0:
                El().bookmarks.set_mtime(self.__bookmark_id,
                                         round(time(), 2) + 1)
            else:
                El().bookmarks.set_mtime(self.__bookmark_id,
                                         mtimes["bookmarks"] + 1)
            El().bookmarks.clean_tags()
            if El().sync_worker is not None:
                El().sync_worker.sync()
        GLib.timeout_add(1000, self.destroy)

    def _on_del_clicked(self, button):
        """
            Remove item
            @param button as Gtk.Button
        """
        self.disconnect_by_func(self.__on_unmap)
        El().bookmarks.delete(self.__bookmark_id)
        if isinstance(self.get_parent(), Gtk.Popover):
            self.get_parent().hide()
        else:
            self.get_parent().set_visible_child_name("bookmarks")

    def _on_new_tag_changed(self, entry):
        """
            Update button states
            @param entry as Gtk.Entry
        """
        text = entry.get_text()
        sensitive = text != ""
        for child in self.__flowbox.get_children():
            if child.label == text:
                sensitive = False
                break
        self.__add_tag_button.set_sensitive(sensitive)

    def _on_add_tag_clicked(self, button):
        """
            Add new tag
            @param button as Gtk.Button
        """
        tag_title = self.__new_tag_entry.get_text()
        El().bookmarks.add_tag(tag_title, True)
        tag_id = El().bookmarks.get_tag_id(tag_title)
        El().bookmarks.add_tag_to(tag_id, self.__bookmark_id)
        tag = TagWidget()
        tag.set_label(tag_title)
        tag.show()
        self.__flowbox.add(tag)
        button.set_sensitive(False)

    def _on_remove_tags_clicked(self, button):
        """
            Remove tag
            @param button as Gtk.Button
        """
        if button.get_label() == _("Cancel"):
            removable = False
            button.set_label(_("Remove tags"))
        else:
            removable = True
            button.set_label(_("Cancel"))
        for child in self.__flowbox.get_children():
            child.set_removable(removable)

    def _on_flowbox_size_allocate(self, scrolled, allocation):
        """
            Set scrolled size allocation based on viewport allocation
            @param scrolled as Gtk.ScrolledWindow
            @param flowbox allocation as Gtk.Allocation
        """
        height = allocation.height
        if height > 200:
            height = 200
        scrolled.set_size_request(-1, height)

#######################
# PRIVATE             #
#######################
    def __sort_tags(self, child1, child2):
        """
            Sort tags
            @param child1 as TagWidget
            @param child2 as TagWidget
        """
        return strcoll(child1.label, child2.label)

    def __on_unmap(self, widget):
        """
            Save uri and title
            @param widget as Gtk.Widget
        """
        El().bookmarks.set_title(self.__bookmark_id,
                                 self.__title_entry.get_text())
        El().bookmarks.set_uri(self.__bookmark_id,
                               self.__uri_entry.get_text())
        if El().sync_worker is not None:
            mtimes = El().sync_worker.mtimes
            if mtimes["bookmarks"] == 0:
                El().bookmarks.set_mtime(self.__bookmark_id,
                                         round(time(), 2) + 1)
            else:
                El().bookmarks.set_mtime(self.__bookmark_id,
                                         mtimes["bookmarks"] + 1)
            El().bookmarks.clean_tags()
            if El().sync_worker is not None:
                El().sync_worker.sync()

    def __on_tag_activated(self, flowbox, child):
        """
            Add or remove tag
            @param flowbox as Gtk.FlowBox
            @param child as TagWidget
        """
        if child.removable:
            return
        tag_id = El().bookmarks.get_tag_id(child.label)
        if tag_id is None:
            return  # Sync may have deleted tag
        active = not El().bookmarks.has_tag(self.__bookmark_id, child.label)
        if active:
            El().bookmarks.add_tag_to(tag_id, self.__bookmark_id)
        else:
            El().bookmarks.del_tag_from(tag_id, self.__bookmark_id)
        child.set_active(active)
        self.__new_tag_entry.set_text(child.label)

    def __on_tag_edited(self, widget, path, name):
        """
            Rename tag
            @param widget as cell renderer
            @param path as str representation of Gtk.TreePath
            @param name as str
        """
        tag_id = El().bookmarks.get_tag_id(name)
        if tag_id is not None:
            return
        iterator = self.__model.get_iter(path)
        old_name = self.__model.get_value(iterator, 0)
        has_tag = El().bookmarks.has_tag(self.__bookmark_id, old_name)
        self.__model.remove(iterator)
        self.__model.append([name, has_tag])
        # Update mtime for all tagged bookmarks
        if El().sync_worker is not None:
            mtimes = El().sync_worker.mtimes
            if mtimes["bookmarks"] == 0:
                mtime = round(time(), 2)
            else:
                mtime = mtimes["bookmarks"]
            tag_id = El().bookmarks.get_tag_id(old_name)
            if tag_id is None:
                return
            for (bookmark_id, title, uri) in\
                    El().bookmarks.get_bookmarks(tag_id):
                El().bookmarks.set_mtime(bookmark_id, mtime + 1)
        El().bookmarks.rename_tag(old_name, name)
