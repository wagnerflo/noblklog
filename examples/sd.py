import asyncio
import json
import logging
import logging.config
import pathlib

logging.config.dictConfig(
    json.load(
        pathlib.Path(__file__).with_suffix(".json").open()
    )
)
log = logging.getLogger(None)

async def main():
    log.info("Structured magic!")
    log.info(
        "Structured magic!", extra={
            "sd": {
                "abc@123": {
                    "escape": ']"\\',
                    "key": "value",
                }
            }
        })
    log.info(
        "Structured magic!", extra={
            "sd": {
                "abc@123": {
                    "escape": ']"\\',
                    "key": "value",
                },
                "default@123": {
                    "override": "..."
                }
            }
        })

asyncio.run(main())
