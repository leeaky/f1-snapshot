"""FastF1 session loading and data-selection helpers.

All four visuals for a race snapshot are built from a single Race session
load, so this module centers on load_race() plus the one non-trivial
selection rule the app needs: which two drivers' laps go into the speed
trace comparison.
"""

from __future__ import annotations

import logging
from pathlib import Path

import fastf1
import pandas as pd

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = REPO_ROOT / "cache"
PLOTS_DIR = REPO_ROOT / "static" / "plots"

CACHE_DIR.mkdir(parents=True, exist_ok=True)
fastf1.Cache.enable_cache(str(CACHE_DIR))

MIN_YEAR = 2018


def load_race(year: int, round_number: int) -> fastf1.core.Session:
    """Load a fully-populated Race session (laps + telemetry + weather).

    Lets fastf1's exception propagate after logging context, per project
    convention: fail loudly rather than returning a partial/None session.
    """
    logger.info("Loading race session: %s round %s", year, round_number)
    try:
        session = fastf1.get_session(year, round_number, "R")
        session.load()
    except Exception:
        logger.exception(
            "Failed to load race session %s round %s", year, round_number
        )
        raise
    logger.info(
        "Loaded %s %s (%s laps)",
        year,
        session.event["EventName"],
        len(session.laps),
    )
    return session


def format_laptime(delta: pd.Timedelta) -> str:
    """Format a lap-time Timedelta as M:SS.mmm, e.g. '1:27.097'."""
    if pd.isna(delta):
        return "—"
    total_seconds = delta.total_seconds()
    minutes = int(total_seconds // 60)
    seconds = total_seconds - minutes * 60
    return f"{minutes}:{seconds:06.3f}"


def pick_two_fastest(session: fastf1.core.Session) -> list[fastf1.core.Lap]:
    """Return the two drivers with the quickest individual race laps.

    Quickest first. This is each driver's personal-best lap, compared across
    drivers — not simply the two quickest rows, which could both belong to
    the same driver if they set their two fastest laps back to back.
    """
    candidates: list[fastf1.core.Lap] = []
    for drv in session.drivers:
        lap = session.laps.pick_drivers(drv).pick_fastest()
        if lap is None or pd.isna(lap["LapTime"]):
            continue
        candidates.append(lap)

    if len(candidates) < 2:
        raise ValueError(
            f"only {len(candidates)} driver(s) with a valid lap time in "
            f"{session.event['EventName']} {session.event.year} — need 2"
        )

    candidates.sort(key=lambda lap: lap["LapTime"])
    logger.info(
        "Two fastest: %s (%s) and %s (%s)",
        candidates[0]["Driver"],
        format_laptime(candidates[0]["LapTime"]),
        candidates[1]["Driver"],
        format_laptime(candidates[1]["LapTime"]),
    )
    return candidates[:2]


def finishing_order(session: fastf1.core.Session) -> list[str]:
    """Driver abbreviations in classified finishing order.

    Falls back to session.drivers order (car-number order) if results
    aren't available for some reason, so callers never have to special-case
    a missing classification.
    """
    try:
        results = session.results.sort_values("Position")
        order = [abbr for abbr in results["Abbreviation"] if isinstance(abbr, str)]
        if order:
            return order
    except Exception:
        logger.warning("No results classification available, falling back to driver order")

    return [session.get_driver(drv)["Abbreviation"] for drv in session.drivers]
