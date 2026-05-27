#!/usr/bin/env python3
"""
MotoGP Data Ingestion CLI.
Usage: python -m backend.ingestion.cli [--year 2026]
"""
import asyncio
import argparse
from backend.ingestion.ingest_motogp import ingest_season


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2026, help="Season year")
    args = parser.parse_args()
    await ingest_season(args.year)


if __name__ == "__main__":
    asyncio.run(main())
