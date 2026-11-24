#!/usr/bin/env python3
"""Wait until a PostgreSQL database accepts SQLAlchemy connections.

Used by Cloud Build (`cloudbuild.yaml`) and CI jobs to replace inline shell blobs.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from sqlalchemy import create_engine


def wait_for_database(url: str, *, retries: int = 30, delay_seconds: float = 1.0) -> None:
    """Poll the database URL until a connection succeeds or retries are exhausted."""
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        engine = create_engine(url)
        try:
            with engine.connect():
                print(f"PostgreSQL is ready! (attempt {attempt}/{retries})")
                return
        except Exception as exc:
            last_error = exc
            print(f"Waiting for database... ({attempt}/{retries}: {exc})")
            time.sleep(delay_seconds)
        finally:
            engine.dispose()

    raise RuntimeError(f"Database did not start in time after {retries} attempts: {last_error}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Wait for PostgreSQL to accept connections.")
    parser.add_argument(
        "--url",
        default=os.environ.get(
            "POWERCORD_DB_URL",
            "postgresql+pg8000://powercord:test_pass@postgres:5432/postgres",
        ),
        help="SQLAlchemy database connection URL.",
    )
    parser.add_argument("--retries", type=int, default=30, help="Maximum connection attempts (default: 30).")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between attempts (default: 1.0).")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        wait_for_database(args.url, retries=args.retries, delay_seconds=args.delay)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
