# Copyright (c) 2014-2017 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from eolie.define import El


class BookmarkRatingWidget(Gtk.Bin):
    """
        Rate widget
    """

    def __init__(self, bookmark_id):
        """
            Init widget
            @param bookmark_id as int
        """
        Gtk.Bin.__init__(self)
        self.__bookmark_id = bookmark_id
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/BookmarkRatingWidget.ui")
        builder.connect_signals(self)
        self.set_property("valign", Gtk.Align.CENTER)
        self.set_property("halign", Gtk.Align.END)
        self._hearts = []
        self._hearts.append(builder.get_object("heart0"))
        self._hearts.append(builder.get_object("heart1"))
        self._hearts.append(builder.get_object("heart2"))
        self._hearts.append(builder.get_object("heart3"))
        self._hearts.append(builder.get_object("heart4"))
        self._on_leave_notify(None, None)
        self.add(builder.get_object("widget"))

#######################
# PROTECTED           #
#######################
    def _on_enter_notify(self, widget, event):
        """
            On enter notify, change heart opacity
            @param widget as Gtk.EventBox
            @param event as Gdk.Event
        """
        event_heart = widget.get_children()[0]
        # First heart is hidden (used to clear score)
        if event_heart.get_opacity() == 0.0:
            found = True
        else:
            found = False
        for heart in self._hearts:
            if found:
                heart.set_opacity(0.2)
            else:
                heart.set_opacity(0.8)
            if heart == event_heart:
                found = True

    def _on_leave_notify(self, widget, event):
        """
            On leave notify, change heart opacity
            @param widget as Gtk.EventBox (can be None)
            @param event as Gdk.Event (can be None)
        """
        rate = self.__get_rate()
        if rate < 1:
            for i in range(5):
                self._hearts[i].set_opacity(0.2)
        else:
            heart = self.__heart_from_rate(rate)
            # Select wanted heart
            for idx in range(0, heart):
                widget = self._hearts[idx]
                widget.set_opacity(0.8)
            # Unselect others
            for idx in range(heart, 5):
                self._hearts[idx].set_opacity(0.2)

    def _on_button_press(self, widget, event):
        """
            On button press, set album popularity
            @param widget as Gtk.EventBox
            @param event as Gdk.Event
        """
        rate = self.__get_rate()
        max_heart = self.__heart_from_rate(rate)
        event_heart = widget.get_children()[0]
        if event_heart in self._hearts:
            position = self._hearts.index(event_heart)
        else:
            position = -1
        new_rate = position + 1
        if new_rate == 0 or new_rate == max_heart:
            El().bookmarks.set_popularity(self.__bookmark_id, 0)
            self._on_leave_notify(None, None)
        else:
            avg_popularity = El().bookmarks.get_avg_popularity()
            best_popularity = El().bookmarks.get_higher_popularity()
            popularity = int((new_rate * avg_popularity / 5) + 0.5)
            # Special case, if new_rate == 5, try to move bookmark near
            # most popular bookmark
            if new_rate == 5:
                popularity = (popularity + best_popularity) / 2
            El().bookmarks.set_popularity(self.__bookmark_id, popularity)
        return True

#######################
# PRIVATE             #
#######################
    def __get_rate(self):
        """
            Get bookmark rate: popularity related to avarage popularity
        """
        avg_popularity = El().bookmarks.get_avg_popularity()
        popularity = El().bookmarks.get_popularity(self.__bookmark_id)
        return popularity * 5 / avg_popularity + 0.5

    def __heart_from_rate(self, rate):
        """
            Calculate hearts from rate
            @param rate as double
            @return int
        """
        heart = min(5, int(rate))
        return heart
