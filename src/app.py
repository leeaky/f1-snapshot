"""Flask routes for the F1 race snapshot site.

Thin by design: every route delegates data work to data.py and chart
generation to plots.py, and just assembles template context.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime

import fastf1
from flask import Flask, abort, jsonify, render_template

from . import plots
from .data import MIN_YEAR, REPO_ROOT, format_laptime, load_race, pick_two_fastest

# Windows consoles default to a legacy codepage that mangles the em dashes
# used in a few log/exception messages (and in FastF1's own logging).
# UTF-8 output is best-effort — never worth failing a request over.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# templates/ and static/ live at the repo root, as siblings of src/, not
# nested inside the src package — Flask's default (relative to this
# package) would miss them.
app = Flask(
    __name__,
    template_folder=str(REPO_ROOT / "templates"),
    static_folder=str(REPO_ROOT / "static"),
)


def _current_year() -> int:
    return datetime.now().year


def _selectable_years() -> list[int]:
    return list(range(_current_year(), MIN_YEAR - 1, -1))


@app.route("/")
def index():
    return render_template("index.html", years=_selectable_years())


@app.route("/api/events/<int:year>")
def api_events(year: int):
    if year < MIN_YEAR:
        abort(404)
    try:
        schedule = fastf1.get_event_schedule(year, include_testing=False)
    except Exception:
        logger.exception("Failed to fetch event schedule for %s", year)
        return jsonify({"error": "couldn't load the schedule"}), 502

    today = datetime.now().date()
    schedule = schedule[schedule["RoundNumber"] >= 1]
    schedule = schedule[schedule["EventDate"].dt.date <= today]
    schedule = schedule.sort_values("RoundNumber")

    events = [
        {
            "round": int(row.RoundNumber),
            "name": row.EventName,
            "location": row.Location,
        }
        for row in schedule.itertuples()
    ]
    return jsonify(events)


@app.route("/race/<int:year>/<int:round_number>")
def race(year: int, round_number: int):
    if year < MIN_YEAR:
        abort(404)

    try:
        session = load_race(year, round_number)
        image_paths = plots.get_or_create_plots(session, year, round_number)
        two_fastest = pick_two_fastest(session)
        winner = session.results.iloc[0]
        full_name = winner.get("FullName")
        winner_name = (
            full_name if isinstance(full_name, str) and full_name else winner["Abbreviation"]
        )
    except Exception:
        logger.exception(
            "Failed to build race snapshot for %s round %s", year, round_number
        )
        return (
            render_template("error.html", year=year, round_number=round_number),
            500,
        )

    context = {
        "years": _selectable_years(),
        "year": year,
        "round_number": round_number,
        "event_name": session.event["EventName"],
        "location": session.event["Location"],
        "date": session.event["EventDate"].strftime("%d %B %Y"),
        "winner_name": winner_name,
        "fastest": [
            {"abbr": lap["Driver"], "time": format_laptime(lap["LapTime"])}
            for lap in two_fastest
        ],
        "images": {name: f"/static/plots/{p.name}" for name, p in image_paths.items()},
    }
    return render_template("race.html", **context)


if __name__ == "__main__":
    app.run(debug=True)
