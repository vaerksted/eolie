# Copyright (c) 2017-2018 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from gi.repository import Gdk, GLib, Gio

import unicodedata
import string
import cairo
from urllib.parse import urlparse
from random import choice
from base64 import b64encode

from eolie.logger import Logger
from eolie.define import App, ArtSize, LoadingType


def set_proxy_from_gnome():
    """
        Set proxy settings from GNOME
    """
    try:
        proxy = Gio.Settings.new("org.gnome.system.proxy")
        mode = proxy.get_value("mode").get_string()
        if mode == "manual":
            socks = Gio.Settings.new("org.gnome.system.proxy.socks")
            h = socks.get_value("host").get_string()
            p = socks.get_value("port").get_int32()
            # Set socks proxy
            if h != "" and p != 0:
                import socket
                import socks
                socks.set_default_proxy(socks.SOCKS4, h, p)
                socket.socket = socks.socksocket
            else:
                http = Gio.Settings.new("org.gnome.system.proxy.http")
                https = Gio.Settings.new("org.gnome.system.proxy.https")
                h = http.get_value("host").get_string()
                p = http.get_value("port").get_int32()
                hs = https.get_value("host").get_string()
                ps = https.get_value("port").get_int32()
                if h != "" and p != 0:
                    GLib.setenv("http_proxy", "http://%s:%s" % (h, p), True)
                if hs != "" and ps != 0:
                    GLib.setenv("https_proxy", "http://%s:%s" % (hs, ps), True)
    except Exception as e:
        Logger.error("set_proxy_from_gnome(): %s", e)


def name_from_profile_id(id):
    """
        Get profile name from id
        @param id as str
        @return str
    """
    if id in App().profiles.keys() and id != "default":
        return "%s: " % App().profiles[id]
    else:
        return ""


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
    elif index < 10:
        return LoadingType.BACKGROUND
    else:
        return LoadingType.OFFLOAD


def is_unity():
    """
        Return True if desktop is Gnome
    """
    return GLib.getenv("XDG_CURRENT_DESKTOP") == "ubuntu:GNOME"


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


def get_char_surface(char):
    """
        Draw a char with a random color
        @param char as str
        @return cairo surface
    """
    colors = [[0.102, 0.737, 0.612],                 # Turquoise
              [0.204, 0.596, 0.859],                 # Peterriver
              [0.608, 0.349, 0.714],                 # Amethyst
              [0.204, 0.286, 0.369],                 # Wetasphalt
              [0.086, 0.627, 0.522],                 # Greensea
              [0.153, 0.682, 0.376],                 # Nephritis
              [0.161, 0.502, 0.725],                 # Belizehole
              [0.557, 0.267, 0.678],                 # Wisteria
              [0.173, 0.243, 0.314],                 # Midnightblue
              [0.827, 0.329, 0.0],                   # Pumpkin
              [0.753, 0.224, 0.169],                 # Pomegranate
              [0.498, 0.549, 0.553]                  # Asbestos
              ]
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                 ArtSize.FAVICON,
                                 ArtSize.FAVICON)
    context = cairo.Context(surface)
    color = choice(colors)
    context.set_source_rgb(color[0], color[1], color[2])
    context.select_font_face("Sans", cairo.FONT_SLANT_NORMAL,
                             cairo.FONT_WEIGHT_BOLD)
    context.set_font_size(ArtSize.FAVICON)
    (xbearing, ybearing,
     width, height,
     xadvance, yadvance) = context.text_extents(char)
    context.move_to(ArtSize.FAVICON / 2 - (xadvance + xbearing) / 2,
                    ArtSize.FAVICON / 2 - ybearing - height / 2)
    context.show_text(char)
    context.stroke()
    return surface


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
