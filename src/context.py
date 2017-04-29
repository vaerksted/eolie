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

from gi.repository import GLib, Gio

from urllib.parse import urlparse
from gettext import gettext as _

from eolie.define import El


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
        locales = GLib.get_language_names()
        context.set_spell_checking_enabled(True)
        if locales:
            user_locale = locales[0]
            default_locale = "en_GB.UTF-8"
            context.set_spell_checking_languages([user_locale, default_locale])
        context.register_uri_scheme("populars", self.__on_populars_scheme)
        context.register_uri_scheme("internal", self.__on_internal_scheme)
        context.register_uri_scheme("accept", self.__on_accept_scheme)
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
        items = []
        # First from bookmarks
        for (bookmark_id, title, uri) in El().bookmarks.get_populars(20):
            items.append((title, uri))
        # Then from history
        more = 30 - len(items)
        if more > 0:
            uris = [item[1] for item in items]
            for (title, uri) in El().history.search("", more):
                if uri not in uris:
                    items.append((title, uri))
        start = Gio.File.new_for_uri("resource:///org/gnome/Eolie/start.html")
        end = Gio.File.new_for_uri("resource:///org/gnome/Eolie/end.html")
        (status, start_content, tag) = start.load_contents(None)
        (status, end_content, tag) = end.load_contents(None)
        # Update start
        html_start = start_content.decode("utf-8")
        html_start = html_start.replace("@TITLE@", _("Popular pages"))
        for (title, uri) in items:
            path = El().art.get_path(uri, "start")
            f = Gio.File.new_for_path(path)
            if not f.query_exists():
                continue
            html_start += '<a class="child" title="%s" href="%s">' % (title,
                                                                      uri)
            html_start += '<img src="file://%s"></img>' % path
            html_start += '<div class="caption">%s</div></a>' % title
        html = html_start.encode("utf-8") + end_content
        stream = Gio.MemoryInputStream.new_from_data(html)
        request.finish(stream, -1, "text/html")

    def __on_internal_scheme(self, request):
        """
            Load an internal resource
            @param request as WebKit2.URISchemeRequest
        """
        # We use internal:/ because resource:/ is already used by WebKit2
        uri = request.get_uri().replace("internal:/", "resource:/")
        f = Gio.File.new_for_uri(uri)
        request.finish(f.read(), -1, "image/svg+xml")

    def __on_accept_scheme(self, request):
        """
            Accept certificate for uri
            @param request as WebKit2.URISchemeRequest
        """
        view = request.get_web_view()
        if view.bad_tls is None:
            return
        parsed = urlparse(request.get_uri())
        self.__context.allow_tls_certificate_for_host(view.bad_tls,
                                                      parsed.netloc)
        view.load_uri("https://" + parsed.netloc + parsed.path)

    def __on_download_started(self, context, download):
        """
            A new download started, handle signals
            @param context as WebKit2.WebContext
            @param download as WebKit2.Download
        """
        El().download_manager.add(download)
        # Notify user about download
        window = El().active_window
        if window is not None:
            window.toolbar.end.show_download(download)
