import asyncio
import logging
import logging.config
import pathlib

logging.config.fileConfig(
    pathlib.Path(__file__).with_suffix('.ini').open()
)
log = logging.getLogger(None)

log.info('Here comes that magic we promised!')

async def main():
    log.info('Even more magic!')

asyncio.run(main())
