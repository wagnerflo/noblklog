# Copyright 2021 Florian Wagner <florian@wagner-flo.net>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from logging import Handler
from logging.handlers import SysLogHandler
from socket import socket,AF_UNIX,SOCK_DGRAM
from .util import AsyncEmitMixin

class AsyncSysLogHandler(AsyncEmitMixin, SysLogHandler):
    def __init__(self, ident='', facility=SysLogHandler.LOG_USER):
        self._ident = ident
        self._facility = facility

        self.socket = socket(AF_UNIX, SOCK_DGRAM)
        self.socket.setblocking(False)
        self.socket.connect('/dev/log')

        Handler.__init__(self)
        AsyncEmitMixin.__init__(
            self, self.socket.fileno(), self.socket.send
        )

    def prepareMessage(self, record):
        return (
            '<' +
            str(
                self.encodePriority(
                    self._facility, self.mapPriority(record.levelname)
                )
            )+
            '>' +
            self.format(record) +
            self._ident +
            '\000'
        ).encode()
