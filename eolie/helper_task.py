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

import gi
gi.require_version("Soup", "2.4")
from gi.repository import GLib, Soup

from threading import Thread


class TaskHelper:
    """
        Simple helper for running a task in background
    """

    def __init__(self, user_agent=None):
        """
            Init helper
            @param user_agent as str
        """
        self.__signals = {}
        self.__headers = []
        self.__user_agent = user_agent

    def add_header(self, name, value):
        """
            Add header
            @param name as str
            @param value as str
        """
        self.__headers.append((name, value))

    def run(self, command, *args, **kwd):
        """
            run command with params and return to callback
            @param command as function
            @param *args as command arguments
            @param **kwd as { "callback": (function, *args) }
        """
        thread = Thread(target=self.__run,
                        args=(command, kwd, *args))
        thread.daemon = True
        thread.start()

    def load_uri_content(self, uri, cancellable, callback, *args):
        """
            Load uri with libsoup (better performance than Gio)
            @param uri as str
            @param cancellable as Gio.Cancellable
            @param callback as a function
            @callback (uri as str, status as bool, content as bytes, args)
        """
        try:
            session = Soup.Session.new()
            session.set_property("accept-language-auto", True)
            if self.__user_agent is not None:
                print(self.__user_agent)
                session.set_property("user-agent", self.__user_agent)
            request = session.request(uri)
            request.send_async(cancellable,
                               self.__on_request_send_async,
                               callback,
                               cancellable,
                               uri,
                               *args)
        except Exception as e:
            print("HelperTask::load_uri_content():",  e)
            callback(None, False, b"", *args)

#######################
# PRIVATE             #
#######################
    def __run(self, command, kwd, *args):
        """
            Pass command result to callback
            @param command as function
            @param *args as command arguments
            @param kwd as { "callback": (function, *args) }
        """
        try:
            result = command(*args)
            if "callback" in kwd.keys():
                (callback, *callback_args) = kwd["callback"]
                if callback is not None:
                    GLib.idle_add(callback, result, *callback_args)
        except Exception as e:
            print("TaskHelper::__run():", e, command, kwd)

    def __on_read_bytes_async(self, stream, result, content,
                              cancellable, callback, uri, *args):
        """
            Read data from stream, when finished, pass to callback
            @param stream as Gio.InputStream
            @param result as Gio.AsyncResult
            @param cancellable as Gio.Cancellable
            @param content as bytes
            @param callback as function
            @param uri as str
        """
        try:
            content_result = stream.read_bytes_finish(result)
            content_bytes = content_result.get_data()
            if content_bytes:
                content += content_bytes
                stream.read_bytes_async(4096, GLib.PRIORITY_LOW,
                                        cancellable,
                                        self.__on_read_bytes_async,
                                        content, cancellable, callback,
                                        uri, *args)
            else:
                callback(uri, True, bytes(content), *args)
        except Exception as e:
            print("TaskHelper::__on_read_bytes_async():", e)
            callback(None, False, b"", *args)

    def __on_request_send_async(self, source, result, callback,
                                cancellable, uri, *args):
        """
            Get stream and start reading from it
            @param source as Soup.Session
            @param result as Gio.AsyncResult
            @param cancellable as Gio.Cancellable
            @param callback as a function
            @param uri as str
        """
        try:
            stream = source.send_finish(result)
            # We use a bytearray here as seems that bytes += is really slow
            stream.read_bytes_async(4096, GLib.PRIORITY_LOW,
                                    cancellable, self.__on_read_bytes_async,
                                    bytearray(0), cancellable, callback, uri,
                                    *args)
        except Exception as e:
            print("TaskHelper::__on_soup_msg_finished():",  e)
            callback(None, False, b"", *args)
