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

from gi.repository import Gdk, GLib

import unicodedata
import string
import cairo
from random import choice
from base64 import b64encode

from eolie.define import El, ArtSize


def is_gnome():
    """
        Return True if desktop is Gnome
    """
    return GLib.getenv("XDG_CURRENT_DESKTOP") == "GNOME"


def resize_favicon(favicon):
    """
        Resize surface to match favicon size
        @param favicon as cairo.surface
        @return cairo.surface
    """
    if favicon is None:
        return None
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                 ArtSize.FAVICON,
                                 ArtSize.FAVICON)
    factor = ArtSize.FAVICON / favicon.get_width()
    context = cairo.Context(surface)
    context.scale(factor, factor)
    context.set_source_surface(favicon, 0, 0)
    context.paint()
    del favicon
    return surface


def get_random_string(size):
    """
        Get a rand string at size
        @param size as int
        return str
    """
    s = ''.join(choice(string.printable) for c in range(size))
    return b64encode(s.encode("utf-8"))[:size].decode("utf-8")


def get_current_monitor_model(window):
    """
        Return monitor model as string
        @param window as Gtk.Window
        @return str
    """
    screen = Gdk.Screen.get_default()
    display = screen.get_display()
    monitor = display.get_monitor_at_window(window.get_window())
    width_mm = monitor.get_width_mm()
    height_mm = monitor.get_height_mm()
    geometry = monitor.get_geometry()
    return "%sx%s/%sx%s" % (width_mm, height_mm,
                            geometry.width, geometry.height)


def noaccents(string):
        """
            Return string without accents
            @param string as str
            @return str
        """
        nfkd_form = unicodedata.normalize('NFKD', string)
        return u"".join([c for c in nfkd_form if not unicodedata.combining(c)])


def get_ftp_cmd():
    """
        Try to guess best ftp app
        @return app cmd as str
    """
    for app in ["filezilla", "nautilus", "thunar", "nemo", "true"]:
        cmd = GLib.find_program_in_path(app)
        if cmd is not None:
            return cmd


def debug(str):
    """
        Print debug
        @param debug as str
    """
    if El().debug is True:
        print(str)
