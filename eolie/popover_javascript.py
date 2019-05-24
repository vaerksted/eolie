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

from gi.repository import Gtk, GLib, WebKit2

from gettext import gettext as _


class JavaScriptPopover(Gtk.Popover):
    """
        Show JavaScript message
        @warning: will block current execution
    """

    def __init__(self, dialog, window):
        """
            Init popover
            @param dialog as WebKit2.ScriptDialog
            @param window as window
        """
        Gtk.Popover.__init__(self)
        self.set_modal(False)
        window.register(self)
        self.__dialog = dialog
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/PopoverJavaScript.ui")
        builder.connect_signals(self)
        widget = builder.get_object("widget")
        label = builder.get_object("label")
        image = builder.get_object("image")
        self.__entry = builder.get_object("entry")
        ok_button = builder.get_object("ok_button")
        cancel_button = builder.get_object("cancel_button")
        dialog_type = dialog.get_dialog_type()
        # Set icon
        if dialog_type == WebKit2.ScriptDialogType.ALERT:
            image.set_from_icon_name("dialog-warning-symbolic",
                                     Gtk.IconSize.DIALOG)
        elif dialog_type in [WebKit2.ScriptDialogType.CONFIRM,
                             WebKit2.ScriptDialogType.PROMPT,
                             WebKit2.ScriptDialogType.BEFORE_UNLOAD_CONFIRM]:
            image.set_from_icon_name("dialog-question-symbolic",
                                     Gtk.IconSize.DIALOG)
            ok_button.show()
            cancel_button.show()
        if dialog_type == WebKit2.ScriptDialogType.PROMPT:
            self.__entry.set_text(dialog.prompt_get_default_text())
            self.__entry.show()
        if dialog_type == WebKit2.ScriptDialogType.BEFORE_UNLOAD_CONFIRM:
            ok_button.set_label(_("Continue"))
            cancel_button.set_label(_("Cancel"))
        label.set_text(dialog.get_message())
        self.add(widget)
        self.__loop = GLib.MainLoop.new(None, False)
        self.connect("closed", self.__on_closed)

    def popup(self):
        """
            Popup widget and run loop
        """
        Gtk.Popover.popup(self)
        self.__loop.run()

#######################
# PROTECTED           #
#######################
    def _on_ok_button_clicked(self, button):
        """
            Pass ok to js
            @param button as Gtk.Button
        """
        if self.__entry.is_visible():
            self.__dialog.prompt_set_text(self.__entry.get_text())
        else:
            self.__dialog.confirm_set_confirmed(True)
        self.hide()

    def _on_cancel_button_clicked(self, button):
        """
            Pass ok to js
            @param button as Gtk.Button
        """
        if not self.__entry.is_visible():
            self.__dialog.confirm_set_confirmed(False)
        self.hide()

#######################
# PRIVATE             #
#######################
    def __on_closed(self, popover):
        """
            Quit main loop
            @param popover as Gtk.Popover
        """
        self.__loop.quit()
