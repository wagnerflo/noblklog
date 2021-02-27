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

import fcntl
import logging
import os
import stat
import sys

from logging import Handler
from .util import AsyncEmitMixin

class AsyncStreamHandler(AsyncEmitMixin,Handler):
    def __init__(self, stream=None, terminator='\n'):
        self._terminator = terminator.encode()

        fd = (sys.stderr if stream is None else stream).fileno()
        st_mode = os.fstat(fd).st_mode

        if not stat.S_ISCHR(st_mode) and not stat.S_ISFIFO(st_mode):
            raise Exception(
                'AsyncStreamHandler uses non-blocking writes and thus ' +
                'is only supported with character devices, pipes and ' +
                'fifos.'
            )

        # set non-blocking
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

        Handler.__init__(self)
        AsyncEmitMixin.__init__(self, fd, os.fdopen(fd, 'wb', 0).write)

    def prepareMessage(self, record):
        return self.format(record).encode() + self._terminator
