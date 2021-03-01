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

class AsyncEmitMixin(ABC):
    def __init__(self, write_fd, write_func):
        self._aem_fd = write_fd
        self._aem_func = write_func
        self._aem_queue = None
        self._aem_event = None
        self._aem_consumer = None
        self._aem_known_loops = set()

    @abstractmethod
    def prepareMessage(self, record):
        pass

    def emit(self, record):
        try:
            msg = self.prepareMessage(record)
            try:
                loop = get_running_loop()
            except RuntimeError:
                loop = None
            self._aem_write(loop, msg)
        except:
            self.handleError(record)

    def _start_writer(self, loop):
        fut = loop.create_future()
        fut.add_done_callback(
            lambda fut: loop.remove_writer(self._aem_fd)
        )
        loop.add_writer(self._aem_fd, self._writer, fut)
        return fut

    def _writer(self, fut):
        try:
            # Start or continue sending data. The left side of the queue
            # represents our current message.
            data = self._aem_queue[0]
            n = self._aem_func(data)

            # We were told EAGAIN, so just return and let the event loop
            # decide when to try again.
        except (BlockingIOError, InterruptedError) as exc:
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
        elif len(self._aem_queue) > 1:
            self._aem_queue.popleft()

        # ...or possibly are really done for now.
        else:
            self._aem_queue.clear()
            fut.set_result(None)

    async def _ame_consume(self, loop):
        try:
            while await self._aem_event.wait():
                self._aem_event.clear()
                await self._start_writer(loop)

        except CancelledError:
            # Look for a new loop to move the consumer to.
            new_loop = self._find_loop()

            # If our collection only yields ourselves then we might as
            # well continue to empty the queue on this loop.
            if new_loop == loop:
                await self._start_writer(loop)
                self._aem_event = None
                self._aem_consumer = None

            # We got lucky. This can only happen in multi threaded
            # enviroments with multiple loops running in different
            # threads and using logging everywhere.
            else:
                await self._start_writer(loop)

    def _find_loop(self):
        # Throw out all loops that are closed.
        self._aem_known_loops.difference_update([
            loop for loop in self._aem_known_loops
            if loop.is_closed()
        ])
        try:
            return next(iter(self._aem_known_loops))
        except StopIteration:
            return None

    def _start_comsumer(self, loop):
        self._aem_event = Event(loop=loop)
        self._aem_consumer = loop.create_task(
            self._ame_consume(loop)
        )

    def _aem_write(self, loop, data):
        # If the queue is empty try writing right away. Small messages
        # might complete immediately and thus allow the overhead of
        # queue and consumer task to be avoided.
        if not self._aem_queue:
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

        if not self._aem_consumer:
            if loop is None:
                # We know of no running consumer and also have been
                # called from outside a loop: No other way than to write
                # synchronously.
                return self._write_sync(data)

            # Starting here we can't postpone creating queue and
            # consumer any longer.
            self._aem_queue = deque()
            self._start_comsumer(loop)

        # Build a small collection of loops for worse times.
        self._aem_known_loops.add(loop)

        # Append to queue and notify consumer.
        self._aem_queue.append(data)
        self._aem_event.set()

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
        parent_close = super().close

        def write_all(fut=None):
            if self._aem_queue is not None:
                for data in self._aem_queue:
                    self._write_sync(data)

            parent_close()

        if self._aem_consumer and not self._aem_consumer.cancelled():
            self._aem_consumer.add_done_callback(write_all)
            self._aem_consumer.cancel()
        else:
            write_all()
