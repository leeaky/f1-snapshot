"""Flask routes for the F1 race snapshot site.

Thin by design: every route delegates data work to data.py and chart
generation to plots.py, and just assembles template context.

Cache-only, deliberately: this used to fall back to a live FastF1 load for
a race that hadn't synced yet, which was the one thing that ever came close
to Render's free-tier memory limit. Now that the site deploys as a static
build (see build_site.py) with no live server behind it at all, there's
nowhere for that fallback to run even if it stayed — a race that hasn't
synced yet just isn't a page until the next weekly sync picks it up. This
module still doubles as the local dev server (`flask --app src.app run`),
so it's worth keeping fast and simple: every route here is exactly what
build_site.py drives directly to produce the static output, not two
separate implementations of "what does a race page look like."
"""

from __future__ import annotations

import logging
import sys

from flask import Flask, abort, jsonify, render_template, url_for

from . import plots
from .data import MIN_YEAR, REPO_ROOT, load_meta

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


def _selectable_years() -> list[int]:
    """Years with at least one synced race, newest first.

    Only ever what's actually cached — with no live fallback, a year with
    nothing synced yet would otherwise be pickable but dead-end on an empty
    event list.
    """
    years = {year for year, _ in plots.cached_races() if year >= MIN_YEAR}
    return sorted(years, reverse=True)


@app.errorhandler(404)
def not_found(_e):
    return render_template("error.html"), 404


@app.route("/")
def index():
    return render_template("index.html", years=_selectable_years())


@app.route("/api/events/<int:year>.json")
def api_events(year: int):
    rounds = [r for y, r in plots.cached_races() if y == year]
    events = []
    for round_number in sorted(rounds):
        meta = load_meta(year, round_number)
        events.append({
            "round": round_number,
            "name": meta["event_name"],
            "location": meta["location"],
        })
    return jsonify(events)


@app.route("/race/<int:year>/<int:round_number>/")
def race(year: int, round_number: int):
    image_paths = plots.existing_plot_paths(year, round_number)
    meta = load_meta(year, round_number) if image_paths is not None else None
    if image_paths is None or meta is None:
        abort(404)

    context = {
        "years": _selectable_years(),
        "year": year,
        "round_number": round_number,
        **meta,
        "images": {
            name: url_for("static", filename=f"plots/{p.name}")
            for name, p in image_paths.items()
        },
    }
    return render_template("race.html", **context)


if __name__ == "__main__":
    app.run(debug=True)
