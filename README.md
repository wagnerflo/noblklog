# noblklog

Keep using the [logging](https://docs.python.org/3/library/logging.html)
you're accustomed to, without having to fear it blocking your
[asyncio](https://docs.python.org/3/library/asyncio.html) event loop.

```python
import asyncio
import logging
import noblklog

logging.basicConfig(
    level=logging.INFO,
    handlers=[
        noblklog.AsyncStreamHandler(),
    ],
)
log = logging.getLogger(None)

log.info('It is logging synchronously outside an event loop! Magic!')

async def main():
    log.info('And asynchronously inside an event loop! Even more magic!')

asyncio.run(main())
```

For more details see the [documentation](https://noblklog.readthedocs.io).
