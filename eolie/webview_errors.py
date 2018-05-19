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

from gi.repository import GLib, Gio

from gettext import gettext as _

from eolie.define import App


class WebViewErrors:
    """
        Implement WebView erros, should be inherited by a WebView
    """

    def __init__(self):
        """
            Init errors
        """
        self.__bad_tls = None  # Keep invalid TLS certificate
        self.__error = False
        self.connect("load-failed", self.__on_load_failed)
        self.connect("load-failed-with-tls-errors", self.__on_load_failed_tls)
        self.connect("web-process-crashed", self.__on_web_process_crashed)

    def reset_bad_tls(self):
        """
            Reset invalid certificate
        """
        self.__bad_tls = None

    def discard_error(self):
        """
            Discard current error status
        """
        self.__error = False

    @property
    def error(self):
        """
            Is webview in error
            @return bool
        """
        return self.__error

    @property
    def bad_tls(self):
        """
            Get invalid certificate
            @return Gio.TlsCertificate
        """
        return self.__bad_tls

#######################
# PROTECTED           #
#######################
    def _show_phishing_error(self, uri):
        """
            Show a warning about phishing
            @param uri as str
        """
        self.stop_loading()
        self.__error = True
        f = Gio.File.new_for_uri("resource:///org/gnome/Eolie/error.css")
        (status, css_content, tag) = f.load_contents(None)
        css = css_content.decode("utf-8")
        # Hide reload button
        css = css.replace("@button@", "display: none")
        f = Gio.File.new_for_uri("resource:///org/gnome/Eolie/error.html")
        (status, content, tag) = f.load_contents(None)
        html = content.decode("utf-8")
        title = _("This page is dangerous")
        detail = _("Eolie will not display this page")
        icon = "dialog-warning-symbolic"
        html = html % (title,
                       css,
                       uri,
                       "internal://%s" % icon,
                       title,
                       _("%s is a phishing page") % uri,
                       detail,
                       "",
                       "")
        self.load_alternate_html(html, uri)

#######################
# PRIVATE             #
#######################
    def __check_for_network(self, uri):
        """
            Load uri when network is available
        """
        if Gio.NetworkMonitor.get_default().get_network_available():
            self.load_uri(uri)
        else:
            return True

    def __on_load_failed(self, view, event, uri, error):
        """
            Show error page
            @param view as WebKit2.WebView
            @param event as WebKit2.LoadEvent
            @param uri as str
            @param error as GLib.Error
        """
        # Ignore HTTP errors
        if error.code > 101:
            return False
        self.__error = True
        network_available = Gio.NetworkMonitor.get_default(
        ).get_network_available()
        f = Gio.File.new_for_uri("resource:///org/gnome/Eolie/error.css")
        (status, css_content, tag) = f.load_contents(None)
        css = css_content.decode("utf-8")
        # Hide reload button if network is down
        if network_available:
            css = css.replace("@button@", "")
        else:
            css = css.replace("@button@", "display: none")
        f = Gio.File.new_for_uri("resource:///org/gnome/Eolie/error.html")
        (status, content, tag) = f.load_contents(None)
        html = content.decode("utf-8")
        if network_available:
            title = _("Failed to load this web page")
            detail = _("It may be temporarily inaccessible or moved"
                       " to a new address.<br/>"
                       "You may wish to verify that your internet"
                       " connection is working correctly.")
            icon = "dialog-information-symbolic"
        else:
            title = _("Network not available")
            detail = _("Check your network connection")
            icon = "network-offline-symbolic"
        html = html % (title,
                       css,
                       uri,
                       "internal://%s" % icon,
                       title,
                       "<b>%s</b> %s" % (uri, error.message),
                       detail,
                       "suggested-action",
                       _("Retry"))
        self.load_alternate_html(html, uri)
        if not network_available:
            GLib.timeout_add(1000, self.__check_for_network, uri)
        return True

    def __on_load_failed_tls(self, view, uri, certificate, errors):
        """
            Show TLS error page
            @param view as WebKit2.WebView
            @param certificate as Gio.TlsCertificate
            @parma errors as Gio.TlsCertificateFlags
        """
        self.__error = True
        self.__bad_tls = certificate
        accept_uri = uri.replace("https://", "accept://")
        if App().websettings.get_accept_tls(uri):
            self.load_uri(accept_uri)
        else:
            f = Gio.File.new_for_uri("resource:///org/gnome/Eolie/error.css")
            (status, css_content, tag) = f.load_contents(None)
            css = css_content.decode("utf-8")
            f = Gio.File.new_for_uri("resource:///org/gnome/Eolie/error.html")
            (status, content, tag) = f.load_contents(None)
            html = content.decode("utf-8")
            if errors == Gio.TlsCertificateFlags.BAD_IDENTITY:
                error = _("The certificate does not match this website")
            elif errors == Gio.TlsCertificateFlags.EXPIRED:
                error = _("The certificate has expired")
            elif errors == Gio.TlsCertificateFlags.UNKNOWN_CA:
                error = _("The signing certificate authority is unknown")
            elif errors == Gio.TlsCertificateFlags.GENERIC_ERROR:
                error = _("The certificate contains errors")
            elif errors == Gio.TlsCertificateFlags.REVOKED:
                error = _("The certificate has been revoked")
            elif errors == Gio.TlsCertificateFlags.INSECURE:
                error = _("The certificate is signed using"
                          " a weak signature algorithm")
            elif errors == Gio.TlsCertificateFlags.NOT_ACTIVATED:
                error = _(
                    "The certificate activation time is still in the future")
            else:
                error = _("The identity of this website has not been verified")
            html = html % (_("Connection is not secure"),
                           css,
                           accept_uri,
                           "internal://dialog-warning-symbolic",
                           _("Connection is not secure"),
                           error,
                           _("This does not look like the real %s.<br/>"
                             "Attackers might be trying to steal or alter"
                             " info going to or coming from this site"
                             " (for example, private messages, credit card"
                             " information, or passwords).") % uri,
                           "destructive-action",
                           _("Accept Risk and Proceed"))
            self.load_alternate_html(html, uri)
        return True

    def __on_web_process_crashed(self, webview):
        """
            We just crashed :-(
            @param webview as WebKit2.WebView
        """
        self.__error = True
        f = Gio.File.new_for_uri("resource:///org/gnome/Eolie/error.css")
        (status, css_content, tag) = f.load_contents(None)
        css = css_content.decode("utf-8")
        f = Gio.File.new_for_uri("resource:///org/gnome/Eolie/error.html")
        (status, content, tag) = f.load_contents(None)
        html = content.decode("utf-8")
        html = html % (_("WebKit web engine crashed"),
                       css,
                       "https://bugs.webkit.org/"
                       "enter_bug.cgi?product=WebKit')",
                       "internal://help-faq-symbolic",
                       _("WebKit web engine crashed"),
                       "",
                       _("The webpage was terminated unexpectedly."
                         " To continue, reload or go to another page.<br/><br/>"
                         "If the problem persists, you can report a bug :)<br/>"
                         "Use <b>'WebKit GTK+'</b> as component.<br/>"
                         "Set <b>[GTK]</b> as subject prefix."),
                       "suggested-action",
                       _("Report a bug now"))
        self.load_html(html, webview.uri)
        return True
