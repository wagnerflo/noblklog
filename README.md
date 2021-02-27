# noblklog

Keep using the [logging](https://docs.python.org/3/library/logging.html)
you're accustomed to, without having to fear it blocking your
[asyncio](https://docs.python.org/3/library/asyncio.html) event loop.

## Installation

```console
$ pip install noblklog
```

## Usage

```python
import asyncio
import logging
import noblklog

root = logging.getLogger(None)
root.setLevel(logging.INFO)
root.addHandler(noblklog.AsyncStreamHandler())

root.info('It is logging synchronously outside an event loop! Magic!')

async def main():
    root.info('And asynchronously inside an event loop! Even more magic!')

asyncio.run(main())
```
