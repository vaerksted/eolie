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

from eolie.define import App


class WebViewStateStruct:
    def __init__(self):
        self.uri = ""
        self.title = ""
        self.atime = 0
        self.is_ephemeral = False
        self.session = None


class WebViewState:
    """
        Web view state allowing to restore a webview from disk
    """

    def new_from_state(state, window):
        """
            New webview from state
            @param state as WebViewStateStruct
            @param window as Window
        """
        from eolie.webview import WebView
        if state.is_ephemeral:
            webview = WebView.new_ephemeral(window)
        else:
            webview = WebView.new(window)
        webview.set_uri(state.uri)
        webview.set_title(state.title)
        webview.set_atime(state.atime)
        # TODO session
        return webview

    def __init__(self):
        """
            Init state
        """
        pass

    @property
    def state(self):
        """
            Get state
            @return WebViewStateStruct
        """
        if App().settings.get_value("remember-session"):
            state = WebViewStateStruct()
            state.uri = self.uri
            state.title = self.title
            state.atime = self.atime
            state.is_ephemeral = self.is_ephemeral
            state.session = self.get_session_state().serialize().get_data()
            return state
        else:
            return None
