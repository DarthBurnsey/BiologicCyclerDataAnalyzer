"""Workstation entrypoint for scheduled daily reporting."""

import argparse
import asyncio
import logging
from datetime import datetime, timezone

from app.database import async_session
from app.services.reporting import generate_daily_report, next_report_time

logger = logging.getLogger("cellscope.reporter")


async def run_loop(run_once: bool) -> None:
    while True:
        async with async_session() as session:
            report = await generate_daily_report(session)
            await session.commit()
        logger.info(
            "report run id=%s date=%s status=%s",
            report.id,
            report.report_date,
            report.delivery_status.value,
        )
        if run_once:
            return

        target = next_report_time(datetime.now(timezone.utc))
        sleep_seconds = max((target - datetime.now(timezone.utc)).total_seconds(), 60)
        await asyncio.sleep(sleep_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the CellScope daily report scheduler.")
    parser.add_argument("--once", action="store_true", help="Generate one report and exit.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(run_loop(run_once=args.once))


if __name__ == "__main__":
    main()
