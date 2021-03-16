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

log.info('Here comes that magic we promised!')

async def main():
    log.info('Even more magic!')

asyncio.run(main())
