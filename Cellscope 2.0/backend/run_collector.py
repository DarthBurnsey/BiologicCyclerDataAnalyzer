"""Workstation entrypoint for polling watched cycler export folders."""

import argparse
import asyncio
import logging

from app.database import async_session
from app.services.live_monitor import poll_all_sources

logger = logging.getLogger("cellscope.collector")


async def run_loop(run_once: bool) -> None:
    while True:
        async with async_session() as session:
            result = await poll_all_sources(session)
            await session.commit()
        logger.info("collector poll result=%s", result)
        if run_once:
            return
        await asyncio.sleep(result["next_poll_seconds"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the CellScope live cycler collector.")
    parser.add_argument("--once", action="store_true", help="Poll sources once and exit.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(run_loop(run_once=args.once))


if __name__ == "__main__":
    main()
