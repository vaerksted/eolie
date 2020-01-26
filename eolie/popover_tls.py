# Copyright (c) 2017-2020 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from gettext import gettext as _
from datetime import datetime

from eolie.define import MARGIN


class TLSPopover(Gtk.Popover):
    """
        Show TLS information
    """

    def __init__(self, window):
        """
            Init popover
            @param window as Window
        """
        Gtk.Popover.__init__(self)
        self.get_style_context().add_class("dark")
        self.set_modal(False)
        window.register(self)
        grid = Gtk.Grid.new()
        grid.show()
        grid.set_row_spacing(MARGIN)
        grid.set_orientation(Gtk.Orientation.VERTICAL)
        title_label = Gtk.Label.new()
        title_label.show()
        title_label.get_style_context().add_class("bold")
        title_label.get_style_context().add_class("dim-label")
        cert_label = Gtk.Label.new()
        cert_label.show()
        cert_label.set_property("halign", Gtk.Align.START)
        grid.add(title_label)
        grid.add(cert_label)
        grid.get_style_context().add_class("padding")
        webview = window.container.webview
        try:
            from OpenSSL import crypto
            (valid, tls, error) = webview.get_tls_info()
            if valid:
                text = ""
                title_label.set_text(_("Connexion is secure"))
                cert_pem = tls.get_property("certificate-pem")
                cert = crypto.load_certificate(crypto.FILETYPE_PEM, cert_pem)
                subject = cert.get_subject()
                if subject.CN is not None:
                    text += _("<b>Website identity:</b> %s\n\n") %\
                        GLib.markup_escape_text(subject.CN)
                end_bytes = cert.get_notAfter()
                end = datetime.strptime(end_bytes.decode("utf-8"),
                                        "%Y%m%d%H%M%SZ")
                text += _("<b>Expires on:</b> %s\n\n") % end
                cert_pem = tls.get_issuer().get_property("certificate-pem")
                cert = crypto.load_certificate(crypto.FILETYPE_PEM, cert_pem)
                subject = cert.get_subject()
                if subject.O is not None:
                    text += _("<b>Verified by:</b> %s\n\n") %\
                        GLib.markup_escape_text(subject.O)
                cert_label.set_markup(text)
            else:
                title_label.set_text(_("Connexion is unsecure"))
        except Exception as e:
            title_label.set_text(str(e))
        self.add(grid)
