#!/usr/bin/env python
"""Manual entrypoint: python scripts/run_daily.py --date 2026-08-27"""

from __future__ import annotations

import argparse
import logging
from datetime import date

from argus.config import Settings
from argus.pipeline import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Argus Overwatch v4 daily pipeline once.")
    parser.add_argument("--date", type=str, default=None, help="YYYY-MM-DD, defaults to today (UTC)")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--fresh", action="store_true",
        help="ignore checkpoints and recompute everything (default resumes)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    run_date: date | None = date.fromisoformat(args.date) if args.date else None

    settings = Settings()
    index_path = run(settings, run_date=run_date, fresh=args.fresh)
    print(f"Report written: {index_path}")


if __name__ == "__main__":
    main()
