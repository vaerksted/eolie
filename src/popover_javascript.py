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

from gi.repository import Gtk, WebKit2


class JavaScriptPopover(Gtk.Popover):
    """
        Show JavaScript message
    """

    def __init__(self, dialog):
        """
            Init popover
            @param dialog as WebKit2.ScriptDialog
        """
        Gtk.Popover.__init__(self)
        self.__dialog = dialog
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/PopoverJavaScript.ui")
        builder.connect_signals(self)
        widget = builder.get_object("widget")
        label = builder.get_object("label")
        image = builder.get_object("image")
        dialog_type = dialog.get_dialog_type()
        if dialog_type == WebKit2.ScriptDialogType.ALERT:
            image.set_from_icon_name("dialog-warning-symbolic",
                                     Gtk.IconSize.DIALOG)
        elif dialog_type in [WebKit2.ScriptDialogType.CONFIRM,
                             WebKit2.ScriptDialogType.PROMPT,
                             WebKit2.ScriptDialogType.BEFORE_UNLOAD_CONFIRM]:
            image.set_from_icon_name("dialog-question-symbolic",
                                     Gtk.IconSize.DIALOG)
        label.set_text(dialog.get_message())
        self.add(widget)

#######################
# PROTECTED           #
#######################

#######################
# PRIVATE             #
#######################
