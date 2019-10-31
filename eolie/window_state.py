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


class WindowStateStruct:
    def __init__(self):
        self.wid = ""
        self.size = []
        self.is_maximized = False
        self.webview_states = []
        self.sort = []


class WindowState:
    """
        Window state allowing to restore a webview from disk
    """

    def new_from_state(state):
        """
            New webview from WindowStateStruct
            @param state as WebState
        """
        from eolie.window import Window
        window = Window(state.size, state.is_maximized)
        window.container.sites_manager.set_initial_sort(state.sort)
        return window

    def __init__(self):
        """
            Init state
        """
        pass

    @property
    def state(self):
        """
            Get state
            @return WindowStateStruct
        """
        state = WindowStateStruct()
        for view in self.container.views:
            webview_state = view.webview.state
            if webview_state is not None:
                state.webview_states.append(webview_state)
        if not state.webview_states:
            return None
        state.size = self.size
        state.is_maximized = self.is_maximized()
        state.sort = self.container.sites_manager.sort
        return state
