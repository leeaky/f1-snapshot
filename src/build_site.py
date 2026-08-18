"""Renders the site as static files for GitHub Pages.

Drives the exact same Flask view functions app.py uses for local dev, just
called directly (bypassing HTTP) from inside a test_request_context set to
GitHub Pages' project-site prefix. That keeps this to one implementation of
"what does a race page look like" instead of two: every template, url_for()
call, and route stays in sync with local dev by construction.

Usage:
    python -m src.build_site
"""

from __future__ import annotations

import logging
import shutil
import sys

from flask import render_template

from . import plots
from .app import api_events, app, index, race
from .data import REPO_ROOT

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# GitHub Pages serves a project site (as opposed to a user/org site or a
# custom domain) at https://<user>.github.io/<repo>/ — every generated
# link needs that prefix. Change to "" if this ever moves to a custom
# domain or a user/org site serving from the root instead.
SITE_ROOT = "/f1-snapshot"

DIST = REPO_ROOT / "dist"


def build() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    races = plots.cached_races()
    years = sorted({year for year, _ in races})
    logger.info("Building static site: %d cached race(s) across %d year(s)", len(races), len(years))

    with app.test_request_context("/", environ_overrides={"SCRIPT_NAME": SITE_ROOT}):
        (DIST / "index.html").write_text(index(), encoding="utf-8")
        (DIST / "404.html").write_text(render_template("error.html"), encoding="utf-8")

        events_dir = DIST / "api" / "events"
        events_dir.mkdir(parents=True)
        for year in years:
            (events_dir / f"{year}.json").write_bytes(api_events(year).get_data())

        for year, round_number in races:
            out_dir = DIST / "race" / str(year) / str(round_number)
            out_dir.mkdir(parents=True)
            (out_dir / "index.html").write_text(race(year, round_number), encoding="utf-8")

    shutil.copytree(REPO_ROOT / "static", DIST / "static")

    logger.info("Built %d race page(s) + %d event list(s) to %s", len(races), len(years), DIST)


if __name__ == "__main__":
    build()
