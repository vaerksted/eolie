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

from gi.repository import Gdk, GLib, Gtk, Pango, GdkPixbuf

from math import pi
import unicodedata
import string
import cairo
import sqlite3
from urllib.parse import urlparse
from random import choice
from base64 import b64encode

from eolie.logger import Logger
from eolie.define import ArtSize, LoadingType


def get_safe_netloc(uri):
    """
        Get netloc (scheme if empty)
        @param uri as str
    """
    parsed = urlparse(uri)
    netloc = parsed.netloc
    if not netloc:
        netloc = "%s://" % urlparse(uri).scheme
    return netloc


def remove_www(netloc):
    """
        Remove www from an urllib parse netloc
        @param netloc as str
        @return str
    """
    if netloc:
        split = netloc.split(".")
        if split[0] == "www":
            split.pop(0)
        return ".".join(split)
    else:
        return ""


def wanted_loading_type(index):
    """
        Return window type based on current index
    """
    if index == 0:
        return LoadingType.FOREGROUND
    elif index == 1:
        return LoadingType.BACKGROUND
    else:
        return LoadingType.OFFLOAD


def get_round_surface(image, scale_factor, radius):
    """
        Get rounded surface from pixbuf
        @param image as GdkPixbuf.Pixbuf/cairo.Surface
        @return surface as cairo.Surface
        @param scale_factor as int
        @param radius as int
        @warning not thread safe!
    """
    width = image.get_width()
    height = image.get_height()
    is_pixbuf = isinstance(image, GdkPixbuf.Pixbuf)
    if is_pixbuf:
        width = width // scale_factor
        height = height // scale_factor
        radius = radius // scale_factor
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surface)
    degrees = pi / 180
    ctx.arc(width - radius, radius, radius, -90 * degrees, 0 * degrees)
    ctx.arc(width - radius, height - radius,
            radius, 0 * degrees, 90 * degrees)
    ctx.arc(radius, height - radius, radius, 90 * degrees, 180 * degrees)
    ctx.arc(radius, radius, radius, 180 * degrees, 270 * degrees)
    ctx.close_path()
    ctx.set_line_width(10)
    if is_pixbuf:
        image = Gdk.cairo_surface_create_from_pixbuf(image, scale_factor, None)
    ctx.set_source_surface(image, 0, 0)
    ctx.clip()
    ctx.paint()
    return surface


def is_unity():
    """
        Return True if desktop is Gnome
    """
    return GLib.getenv("XDG_CURRENT_DESKTOP") == "ubuntu:GNOME"


def get_favicon_best_uri(favicons_path, uri):
    """
        Search in WebKit DB for best uri
        @param favicons_path as str
        @param uri as str
        @return str
    """
    favicon_uri = None
    try:
        parsed = urlparse(uri)
        for uri in [parsed.netloc + parsed.path, parsed.netloc]:
            sql = sqlite3.connect(favicons_path, 600.0)
            result = sql.execute("SELECT url\
                                  FROM PageURL\
                                  WHERE url LIKE ?", ("%{}%".format(uri),))
            v = result.fetchone()
            if v is not None:
                favicon_uri = v[0]
                break
    except Exception as e:
        Logger.error("get_favicon_best_uri(): %s", e)
    return favicon_uri


def resize_favicon(favicon):
    """
        Resize surface to match favicon size
        @param favicon as cairo.surface
        @return cairo.surface
    """
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                 ArtSize.FAVICON,
                                 ArtSize.FAVICON)
    factor = ArtSize.FAVICON / favicon.get_width()
    context = cairo.Context(surface)
    context.scale(factor, factor)
    context.set_source_surface(favicon, 0, 0)
    context.paint()
    return surface


# TODO Use Lollypop menu builder
def update_popover_internals(widget):
    """
        Little hack to force Gtk.ModelButton to show image
        @param widget as Gtk.Widget
    """
    if isinstance(widget, Gtk.Image):
        widget.show()
    elif isinstance(widget, Gtk.Label):
        widget.set_ellipsize(Pango.EllipsizeMode.END)
        widget.set_max_width_chars(40)
        widget.set_tooltip_text(widget.get_text())
    elif hasattr(widget, "forall"):
        GLib.idle_add(widget.forall, update_popover_internals)


def get_snapshot(webview, result, callback, *args):
    """
        Set snapshot on main image
        @param webview as WebKit2.WebView
        @param result as Gio.AsyncResult
        @return cairo.Surface
    """
    ART_RATIO = 1.5  # ArtSize.START_WIDTH / ArtSize.START_HEIGHT
    try:
        snapshot = webview.get_snapshot_finish(result)
        # Set start image scale factor
        ratio = snapshot.get_width() / snapshot.get_height()
        if ratio > ART_RATIO:
            factor = ArtSize.START_HEIGHT / snapshot.get_height()
        else:
            factor = ArtSize.START_WIDTH / snapshot.get_width()
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                     ArtSize.START_WIDTH,
                                     ArtSize.START_HEIGHT)
        context = cairo.Context(surface)
        context.scale(factor, factor)
        context.set_source_surface(snapshot, factor, 0)
        context.paint()
        callback(surface, *args)
    except Exception as e:
        Logger.error("get_snapshot(): %s", e)
        callback(None, *args)


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
