"""FastF1 session loading and data-selection helpers.

All four visuals for a race snapshot are built from a single Race session
load, so this module centers on load_race() plus the one non-trivial
selection rule the app needs: which two drivers' laps go into the speed
trace comparison.
"""

from __future__ import annotations

import json
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


def _fastest_laps_by_driver(session: fastf1.core.Session) -> list[fastf1.core.Lap]:
    """Every driver's personal-best lap this session, fastest first."""
    candidates: list[fastf1.core.Lap] = []
    for drv in session.drivers:
        lap = session.laps.pick_drivers(drv).pick_fastest()
        if lap is None or pd.isna(lap["LapTime"]):
            continue
        candidates.append(lap)
    candidates.sort(key=lambda lap: lap["LapTime"])
    return candidates


def pick_two_fastest(session: fastf1.core.Session) -> list[fastf1.core.Lap]:
    """Return the two drivers with the quickest individual race laps.

    Quickest first. This is each driver's personal-best lap, compared across
    drivers — not simply the two quickest rows, which could both belong to
    the same driver if they set their two fastest laps back to back.

    Deliberately telemetry-agnostic: this is the *factual* fastest lap of
    the race, used for the page header/metadata, and should stay accurate
    even for a driver whose telemetry can't be plotted. See
    pick_fastest_with_telemetry() for the chart-plotting equivalent.
    """
    candidates = _fastest_laps_by_driver(session)

    if len(candidates) < 2:
        raise ValueError(
            f"only {len(candidates)} driver(s) with a valid lap time in "
            f"{session.event['EventName']} {session.event.year} — need 2"
        )

    logger.info(
        "Two fastest: %s (%s) and %s (%s)",
        candidates[0]["Driver"],
        format_laptime(candidates[0]["LapTime"]),
        candidates[1]["Driver"],
        format_laptime(candidates[1]["LapTime"]),
    )
    return candidates[:2]


def pick_fastest_with_telemetry(
    session: fastf1.core.Session, telemetry: dict, count: int
) -> list[fastf1.core.Lap]:
    """The `count` fastest laps among drivers who actually have this
    telemetry stream — skipping any who don't, in favor of the
    next-fastest driver who does.

    `telemetry` is session.car_data or session.pos_data: FastF1 fetches
    car (speed/throttle) and position (X/Y) data as independent streams,
    and either can be missing for a driver entirely (not just incomplete)
    on older data especially. A fast-but-unplottable lap is useless to a
    chart that needs to actually draw the telemetry, unlike
    pick_two_fastest()'s factual "what really was the fastest lap" — so
    this is the one to use for chart data, not for reporting a time.

    May return fewer than `count` laps if not enough drivers have this
    telemetry; callers already treat that as "can't build this chart" via
    the same fallback path as any other plotting failure.
    """
    candidates = [
        lap for lap in _fastest_laps_by_driver(session)
        if lap["DriverNumber"] in telemetry
    ]
    return candidates[:count]


def build_meta(session: fastf1.core.Session, two_fastest: list[fastf1.core.Lap]) -> dict:
    """Assemble the small, JSON-serializable summary shown in the page header.

    Kept separate from the live Session object specifically so it can be
    cached to disk (see save_meta/load_meta) — reading this back is what
    lets a re-visited race skip a full FastF1 load entirely, not just skip
    re-drawing the charts.
    """
    winner = session.results.iloc[0]
    full_name = winner.get("FullName")
    winner_name = (
        full_name if isinstance(full_name, str) and full_name else winner["Abbreviation"]
    )
    return {
        "event_name": session.event["EventName"],
        "location": session.event["Location"],
        "date": session.event["EventDate"].strftime("%d %B %Y"),
        "winner_name": winner_name,
        "fastest": [
            {"abbr": lap["Driver"], "time": format_laptime(lap["LapTime"])}
            for lap in two_fastest
        ],
    }


def _meta_path(year: int, round_number: int) -> Path:
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    return PLOTS_DIR / f"{year}_{round_number:02d}_meta.json"


def save_meta(year: int, round_number: int, meta: dict) -> None:
    _meta_path(year, round_number).write_text(json.dumps(meta, indent=2), encoding="utf-8")


def load_meta(year: int, round_number: int) -> dict | None:
    """Cached meta for this race, or None if it hasn't been built yet.

    A corrupt cache file is treated the same as a missing one (log and
    recompute) rather than raised — the same self-healing-cache reasoning
    as a missing image file, not an error worth failing the page over.
    """
    path = _meta_path(year, round_number)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.warning("Corrupt meta cache at %s, ignoring", path)
        return None


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
