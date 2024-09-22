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
from asyncio import get_running_loop,CancelledError,Event
from collections import deque
from selectors import DefaultSelector,EVENT_WRITE

selector = DefaultSelector()
workers = {}

class Worker:
    def __init__(self, loop, write_fd, write_func, maxlen=None):
        workers[write_fd] = self
        self._loop = loop
        self._fd = write_fd
        self._func = write_func
        self._users = set()
        self._maxlen = maxlen
        self._queue = deque((), maxlen)
        self._event = Event()
        self._consumer = loop.create_task(self._consume())

    @property
    def is_empty(self):
        return not self._queue

    def append(self, user, data):
        if self._maxlen is None or len(self._queue) < self._maxlen:
            self._users.add(self)
            self._queue.append(data)
            self._event.set()

    def user_closing(self, user, cb):
        # Remove user from the list. If no users are left afterwards,
        # close this worker down.
        self._users.discard(user)

        if not self._users and not self._consumer.cancelled():
            self._consumer.add_done_callback(cb)
            self._consumer.cancel()

    async def _consume(self):
        try:
            while await self._event.wait():
                self._event.clear()
                await self._start_writer()

        except CancelledError:
            await self._start_writer()
            del workers[self._fd]

    def _start_writer(self):
        fut = self._loop.create_future()
        fut.add_done_callback(
            lambda fut: self._loop.remove_writer(self._fd)
        )
        self._loop.add_writer(self._fd, self._writer, fut)
        return fut

    def _writer(self, fut):
        try:
            # Start or continue sending data. The left side of the queue
            # represents our current message.
            data = self._queue[0]
            n = self._func(data)

        # We were told EAGAIN, so just return and let the event loop
        # decide when to try again.
        except (BlockingIOError, InterruptedError) as exc:
            return

        # The queue is empty. We're done here.
        except IndexError:
            fut.set_result(None)
            return

        # Something horrible has happend.
        except Exception as exc:
            fut.set_exception(exc)
            return

        # We might have not written all of the message right away...
        if n != len(data):
            del data[:n]

        # ...or someone thinks it might be a good idea to stop sending
        # any more messages
        elif fut.done():
            return

        # ...or we might have more messages left in the queue
        elif len(self._queue) > 1:
            self._queue.popleft()

        # ...or possibly are really done for now.
        else:
            self._queue.clear()
            fut.set_result(None)

class AsyncEmitMixin(ABC):
    def __init__(self, write_fd, write_func, max_queued=None):
        self._aem_fd = write_fd
        self._aem_func = write_func
        self._max_queued = max_queued

    @abstractmethod
    def prepareMessage(self, record):
        pass

    def emit(self, record):
        try:
            worker = workers.get(self._aem_fd)
            data = self.prepareMessage(record)

            # If the queue is empty try writing right away. Small
            # messages might complete immediately and thus allow the
            # overhead of queue and consumer task to be avoided.
            if not worker or worker.is_empty:
                try:
                    n = self._aem_func(data)
                except (BlockingIOError, InterruptedError):
                    n = 0

                if n == len(data):
                    return

                data = memoryview(data)[n:]

            # Copy data into a bytearray to make sure we have a mutable
            # buffer for piecewise writing.
            data = bytearray(data)

            if not worker:
                try:
                    # Starting here we can't postpone creating queue and
                    # consumer any longer.
                    worker = Worker(
                        get_running_loop(), self._aem_fd, self._aem_func,
                        self._max_queued
                    )

                except RuntimeError:
                    # We know of no running consumer and also have been
                    # called from outside a loop: No other way than to
                    # write synchronously.
                    return self._write_sync(data)

            worker.append(self, data)

        except:
            self.handleError(record)

    def _write_sync(self, data):
        selector.register(self._aem_fd, EVENT_WRITE)

        try:
            while data:
                selector.select()
                try:
                    del data[:self._aem_func(data)]
                except (BlockingIOError, InterruptedError):
                    continue
        finally:
            selector.unregister(self._aem_fd)

    def close(self):
        if (worker := workers.get(self._aem_fd)) is not None:
            worker.user_closing(self, super().close)
        else:
            super().close()
