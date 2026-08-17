"""CLI to bulk-warm the FastF1 cache and pre-generate chart images.

FastF1 downloads ~50-100MB per race on first fetch (1-3 minutes); after
that it's served from cache/ near-instantly. Run this ahead of time for
whichever seasons you care about so the site never makes you wait.

Usage:
    python -m src.precache 2023                # every race that season
    python -m src.precache 2023 --rounds 10 12  # just these rounds
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime

import fastf1

from . import plots
from .data import MIN_YEAR, load_race

# Windows consoles default to a legacy codepage that mangles the em dashes
# used in log messages below (and in FastF1's own logging). UTF-8 output is
# best-effort — never worth failing a precache run over a log encoding.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def _rounds_for_season(year: int) -> list[int]:
    """Every conventional, already-run round number for a season."""
    schedule = fastf1.get_event_schedule(year, include_testing=False)
    schedule = schedule[schedule["RoundNumber"] >= 1]
    today = datetime.now().date()
    schedule = schedule[schedule["EventDate"].dt.date <= today]
    return sorted(int(r) for r in schedule["RoundNumber"])


def precache_race(year: int, round_number: int) -> bool:
    """Warm the cache and generate charts for one race. Returns success."""
    try:
        session = load_race(year, round_number)
        plots.get_or_create_plots(session, year, round_number)
    except Exception:
        logger.exception("Failed to precache %s round %s", year, round_number)
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("year", type=int, help=f"season to precache ({MIN_YEAR}-present)")
    parser.add_argument(
        "--rounds",
        type=int,
        nargs="+",
        default=None,
        help="specific round numbers (default: every already-run round that season)",
    )
    args = parser.parse_args(argv)

    if args.year < MIN_YEAR:
        parser.error(f"year must be {MIN_YEAR} or later (FastF1 telemetry isn't reliable before that)")

    rounds = args.rounds or _rounds_for_season(args.year)
    if not rounds:
        logger.warning("No rounds found for %s — nothing to do", args.year)
        return 0

    logger.info("Precaching %s round(s) for %s: %s", len(rounds), args.year, rounds)
    failures = []
    for i, round_number in enumerate(rounds, start=1):
        logger.info("[%d/%d] %s round %s", i, len(rounds), args.year, round_number)
        if not precache_race(args.year, round_number):
            failures.append(round_number)

    if failures:
        logger.warning("Done, but %d round(s) failed: %s", len(failures), failures)
        return 1

    logger.info("Done — %d round(s) precached successfully.", len(rounds))
    return 0


if __name__ == "__main__":
    sys.exit(main())
