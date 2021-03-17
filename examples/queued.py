import asyncio
import logging
import noblklog

h1 = noblklog.AsyncStreamHandler()
h2 = noblklog.AsyncStreamHandler()

l1 = logging.getLogger('l1')
l2 = logging.getLogger('l2')

l1.addHandler(h1)
l2.addHandler(h2)

async def main():
    l1.error('Even more magic!\n' * 2000)
    await asyncio.sleep(.5)
    l2.error('LOL\n' * 20000)
    l1.error('ROFL')
    h1.close()
    h2.close()

asyncio.run(main())
