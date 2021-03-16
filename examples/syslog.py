import asyncio
import json
import logging
import logging.config
import pathlib

logging.config.dictConfig(
    json.load(
        pathlib.Path(__file__).with_suffix('.json').open()
    )
)
log = logging.getLogger(None)

log.info('Here comes that magic we promised!')

async def main():
    log.info('Even more magic!')

asyncio.run(main())
