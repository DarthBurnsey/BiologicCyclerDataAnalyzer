#!/usr/bin/env python3
"""Export an ontology reconciliation package for the NMC cathode workbook."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "Cellscope 2.0" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import Base
from app.services.nmc_cathode_workbook import import_nmc_cathode_workbook


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workbook",
        required=True,
        help="Path to the primary NMC cathode formulation workbook.",
    )
    parser.add_argument(
        "--legacy-db",
        default=str(REPO_ROOT / "cellscope.db"),
        help="Path to the legacy CellScope SQLite database.",
    )
    parser.add_argument(
        "--comparison-workbook",
        default=None,
        help="Optional path to the auxiliary comparison workbook with compiled experiment results.",
    )
    parser.add_argument(
        "--export-dir",
        required=True,
        help="Directory where the reconciliation package should be written.",
    )
    parser.add_argument(
        "--persist",
        action="store_true",
        help="Persist the ontology import instead of running preview only.",
    )
    return parser


async def run(args: argparse.Namespace) -> dict:
    temp_db = Path("/tmp/nmc_cathode_reconciliation_runner.db")
    engine = create_async_engine(f"sqlite+aiosqlite:///{temp_db}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        result = await import_nmc_cathode_workbook(
            session,
            workbook_path=args.workbook,
            legacy_db_path=args.legacy_db,
            comparison_workbook_path=args.comparison_workbook,
            export_dir=args.export_dir,
            persist=args.persist,
        )
        if args.persist:
            await session.commit()

    await engine.dispose()
    return result


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    result = asyncio.run(run(args))
    print(json.dumps(
        {
            "persisted": result.get("persisted"),
            "counts": result.get("counts"),
            "review_export": result.get("review_export"),
        },
        indent=2,
        default=str,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
