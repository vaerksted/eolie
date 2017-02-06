# Copyright (c) 2014-2016 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

import unicodedata
from urllib.parse import urlparse

from eolie.define import El


def noaccents(string):
        """
            Return string without accents
            @param string as str
            @return str
        """
        nfkd_form = unicodedata.normalize('NFKD', string)
        return u"".join([c for c in nfkd_form if not unicodedata.combining(c)])


def debug(str):
    """
        Print debug
        @param debug as str
    """
    if El().debug is True:
        print(str)


def strip_uri(uri, prefix=True):
    """
        Clean up uri
        @param uri as str
        @param prefix as bool
        @return str
    """
    parsed = urlparse(uri)
    if prefix:
        new_uri = "%s://%s%s" % (parsed.scheme, parsed.netloc, parsed.path)
    else:
        new_uri = "%s%s" % (parsed.netloc, parsed.path)
    return new_uri.rstrip('/')
