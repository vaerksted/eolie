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

from gi.repository import GLib, Gio, Gtk, WebKit2

from urllib.parse import urlparse
from gettext import gettext as _
from datetime import datetime

from eolie.define import App, COOKIES_PATH, EOLIE_DATA_PATH


class Context:
    """
        Handle context signals
    """

    def __init__(self, context):
        """
            Init context
            @param context as WebKit2.WebContext
        """
        self.__context = context
        if not context.is_ephemeral():
            context.set_cache_model(WebKit2.CacheModel.WEB_BROWSER)
            context.set_favicon_database_directory(App().favicons_path)
            cookie_manager = context.get_cookie_manager()
            cookie_manager.set_accept_policy(
                App().settings.get_enum("cookie-storage"))
            path = COOKIES_PATH % (EOLIE_DATA_PATH, "default")
            cookie_manager.set_persistent_storage(
                path,
                WebKit2.CookiePersistentStorage.SQLITE)
        context.set_web_extensions_directory(App().extension_dir)
        context.set_process_model(
            WebKit2.ProcessModel.MULTIPLE_SECONDARY_PROCESSES)
        context.set_spell_checking_enabled(
            App().settings.get_value("enable-spell-check"))
        context.register_uri_scheme("populars", self.__on_populars_scheme)
        context.register_uri_scheme("internal", self.__on_internal_scheme)
        context.register_uri_scheme("accept", self.__on_accept_scheme)
        context.register_uri_scheme("file", self.__on_file_scheme)
        context.get_security_manager().register_uri_scheme_as_local("populars")
        # We allow DownloadPopover to connect before default context
        context.connect_after("download-started", self.__on_download_started)

#######################
# PRIVATE             #
#######################
    def __on_populars_scheme(self, request):
        """
            Show populars web pages
            @param request as WebKit2.URISchemeRequest
        """
        uri = request.get_uri()
        parsed = urlparse(uri)
        items = []
        start_page = App().settings.get_value("start-page").get_string()
        wanted = App().settings.get_value("max-popular-items").get_int32()
        if start_page == "popular_book":
            reset_function = "reset_bookmark"
            for (item_id, uri, title) in App().bookmarks.get_populars(wanted):
                items.append((title, uri, "", 1))
        else:
            reset_function = "reset_history"
            for (item_id, uri,
                 netloc, title, count) in App().history.get_populars(
                    parsed.netloc,
                    wanted):
                items.append((title, uri, netloc, count))
        start = Gio.File.new_for_uri("resource:///org/gnome/Eolie/start.html")
        end = Gio.File.new_for_uri("resource:///org/gnome/Eolie/end.html")
        (status, start_content, tag) = start.load_contents(None)
        (status, end_content, tag) = end.load_contents(None)
        # Update start
        html_start = start_content.decode("utf-8")
        html_start = html_start.replace("@TITLE@", _("Popular pages"))
        fake = Gtk.Entry.new()
        style_context = fake.get_style_context()
        (found, color) = style_context.lookup_color("theme_selected_bg_color")
        if found:
            color.alpha = 0.2
            html_start = html_start.replace("@BACKGROUND_COLOR@",
                                            color.to_string())
        else:
            html_start = html_start.replace("@BACKGROUND_COLOR@",
                                            "rgba(74,144,217,0.2)")
        idx = 0
        for (title, uri, netloc, count) in items:
            element_id = "element_%s" % idx
            idx += 1
            if count == 1:  # No navigaiftion for one page
                netloc = uri
            if App().settings.get_value("night-mode"):
                path = App().art.get_path(uri, "start_dark")
            else:
                path = App().art.get_path(uri, "start_light")
            if path is None or\
                    not GLib.file_test(path, GLib.FileTest.IS_REGULAR):
                continue
            favicon_path = App().art.get_favicon_path(netloc)
            if favicon_path is not None:
                favicon_uri = "file://%s" % favicon_path
            else:
                favicon_uri = "internal://web-browser-symbolic"
            html_start += '<a class="child color" id="%s"\
                           title="%s" href="%s">\
                           <img src="file://%s"></img>\
                           <footer class="caption color">%s\
                           <img onclick="%s(event, %s, %s)"\
                                class="close_button color">\
                           <img class="favicon" src="%s">\
                           </img></img></footer></a>' % (
                element_id, title, netloc, path,
                title, reset_function,
                "'%s'" % netloc,
                "'%s'" % element_id, favicon_uri)
        html = html_start.encode("utf-8") + end_content
        stream = Gio.MemoryInputStream.new_from_data(html)
        request.finish(stream, -1, "text/html")

    def __on_file_scheme(self, request):
        """
            Show populars web pages
            @param request as WebKit2.URISchemeRequest
        """
        try:
            uri = request.get_uri()
            parent = "/".join(uri.rstrip("/").split("/")[:-1])
            f = Gio.File.new_for_uri(uri)
            info = f.query_info("standard::type",
                                Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS,
                                None)
            if info.get_file_type() == Gio.FileType.DIRECTORY:
                start = Gio.File.new_for_uri(
                    "resource:///org/gnome/Eolie/start_file.html")
                end = Gio.File.new_for_uri(
                    "resource:///org/gnome/Eolie/end_file.html")
                (status, start_content, tag) = start.load_contents(None)
                (status, end_content, tag) = end.load_contents(None)
                html_start = start_content.decode("utf-8")
                html_start = html_start.replace("@PATH@", f.get_path())
                html_start = html_start.replace("@NAME@", _("Name"))
                html_start = html_start.replace("@SIZE@", _("Size"))
                html_start = html_start.replace("@LAST_MODIFICATION@",
                                                _("Last modification"))
                if parent:
                    html_start += '<tr>'\
                                  '<td><a class="dir" href="%s">%s</a></td>'\
                                  '<td></td>'\
                                  '<td></td></tr>' % (
                                      parent, "..")
                try:
                    infos = f.enumerate_children(
                        "standard::name,standard::size,"
                        "standard::type,time::modified",
                        Gio.FileQueryInfoFlags.NONE,
                        None)
                    dirs = {}
                    files = {}
                    for info in infos:
                        name = info.get_name()
                        if f.get_path() == "/":
                            filename = "/%s" % name
                        else:
                            filename = "%s/%s" % (f.get_path(), name)
                        uri = GLib.filename_to_uri(filename)
                        mtime = info.get_attribute_uint64("time::modified")
                        size = round((info.get_size() / 1024), 2)
                        date_str = datetime.fromtimestamp(mtime).strftime(
                            "%Y-%m-%d %H:%M:%S")
                        if info.get_file_type() == Gio.FileType.DIRECTORY:
                            dirs[uri] = (name, size, date_str)
                        else:
                            files[uri] = (name, size, date_str)
                    for uri, (name, size, date_str) in sorted(dirs.items()):
                        html_start += '<tr>'\
                                      '<td><a class="dir" href="%s">'\
                                      '%s</a></td>'\
                                      '<td>%s KB</td>'\
                                      '<td>%s</td></tr>' % (
                                          uri, name, size, date_str)
                    for uri, (name, size, date_str) in sorted(files.items()):
                        html_start += '<tr>'\
                                      '<td><a class="file" href="%s">'\
                                      '%s</a></td>'\
                                      '<td>%s KB</td>'\
                                      '<td>%s</td></tr>' % (
                                          uri, name, size, date_str)
                except Exception as e:
                    infos = []
                    html_start += '<tr>'\
                                  '<td>%s</td>'\
                                  '<td></td>'\
                                  '<td></td></tr>' % e
                html = html_start.encode("utf-8") + end_content
                stream = Gio.MemoryInputStream.new_from_data(html)
                request.finish(stream, -1, "text/html")
            else:
                request.finish(f.read(), -1, None)
        except Exception as e:
            request.get_web_view().emit("load-failed",
                                        WebKit2.LoadEvent.FINISHED,
                                        uri,
                                        GLib.Error(str(e)))

    def __on_internal_scheme(self, request):
        """
            Load an internal resource
            @param request as WebKit2.URISchemeRequest
        """
        # We use internal:// because resource:// is already used by WebKit2
        icon_name = request.get_uri().replace("internal://", "")
        icon_info = Gtk.IconTheme.get_default().lookup_icon(
            icon_name, 22,
            Gtk.IconLookupFlags.FORCE_SVG)
        if icon_info is None:
            return
        filename = icon_info.get_filename()
        if filename.endswith(".png"):
            mime = "image/png"
        else:
            mime = "image/svg+xml"
        f = Gio.File.new_for_path(filename)
        request.finish(f.read(), -1, mime)

    def __on_accept_scheme(self, request):
        """
            Accept certificate for uri
            @param request as WebKit2.URISchemeRequest
        """
        view = request.get_web_view()
        if view.bad_tls is None:
            return
        request_uri = request.get_uri()
        parsed = urlparse(request_uri)
        uri = request_uri.replace("accept://", "https://")
        if not App().websettings.get_accept_tls(uri):
            App().websettings.set("accept_tls", uri, True)
        self.__context.allow_tls_certificate_for_host(
            view.bad_tls,
            # Remove port
            parsed.netloc.split(":")[0])
        view.load_uri(uri)

    def __on_download_started(self, context, download):
        """
            A new download started, handle signals
            @param context as WebKit2.WebContext
            @param download as WebKit2.Download
        """
        App().download_manager.add(download)
