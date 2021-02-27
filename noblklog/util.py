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

from abc import ABC,abstractmethod
from asyncio import get_running_loop
from functools import partial
from selectors import DefaultSelector,EVENT_WRITE

class AsyncEmitMixin(ABC):
    def __init__(self, write_fd, write_func):
        self._write_fd = write_fd
        self._write_func = write_func

    @abstractmethod
    def prepareMessage(self, record):
        pass

    def emit(self, record):
        try:
            msg = self.prepareMessage(record)
            try:
                loop = get_running_loop()
            except RuntimeError:
                write_sync(self._write_fd, self._write_func, msg)
            else:
                write_async(loop, self._write_fd, self._write_func, msg)
        except:
            self.handleError(record)

def _writer(fut, func, data):
    # Someone might have decided to cancel the Future. Take that as a
    # sign to stop trying to send data.
    if fut.done():
        return

    try:
        n = func(data)

    # We were told EAGAIN, so just return and let the event loop decide
    # when to try again.
    except (BlockingIOError, InterruptedError):
        return

    # Something horrible has happend.
    except Exception as exc:
        fut.set_exception(exc)
        return

    # At this point we are either done...
    if n == len(data):
        fut.set_result(None)

    # ...or at least have written some part of the data.
    else:
        del data[:n]

def try_write(func, data):
    # Take shot at writing the data. Small amounts will fit into the
    # kernel buffer right away and thus we might get away without
    # the overhead of an event loop.
    try:
        n = func(data)
    except (BlockingIOError, InterruptedError):
        n = 0

    if n == len(data):
        return

    return bytearray(memoryview(data)[n:])

def write_async(loop, fd, func, data):
    if data := try_write(func, data):
        # Use a Future to communicate completion of the writers job and
        # allow removing it from the loop.
        fut = loop.create_future()
        fut.add_done_callback(partial(loop.remove_writer, fd))

        # Let the event loop decide when to continue.
        loop.add_writer(fd, _writer, fut, func, data)

selector = DefaultSelector()

def write_sync(fd, func, data):
    if data := try_write(func, data):
        selector.register(fd, EVENT_WRITE)

        try:
            while data:
                selector.select()

                try:
                    n = func(data)
                except (BlockingIOError, InterruptedError):
                    continue

                if n == len(data):
                    break
                else:
                    del data[:n]

        finally:
            selector.unregister(fd)
