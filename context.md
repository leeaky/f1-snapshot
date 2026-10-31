# f1-snapshot — context

A personal website for understanding a historical F1 race at a glance: pick a track + year,
see the track map, speed traces of the two fastest race laps, tyre strategy, and position
changes — one page per race, built from FastF1 data.

## Decisions

- **Stack**: Flask + matplotlib, all charts rendered to static PNGs. Chosen over Streamlit
  for full design control.
- **Hosting**: static site on GitHub Pages (migrated off Render 2026-08-18). `src/build_site.py`
  drives Flask's own view functions to render every synced race to files; `deploy-pages.yml`
  publishes on each push to `main`. Flask (`src/app.py`) is now only the local dev server and
  the single source of "what a race page looks like" that `build_site.py` reuses — production
  has no live server and no request-time FastF1. Render's live-fetch fallback was dropped in
  the same move.
- **Data scope**: all four visuals come from the **Race** session only (not Qualifying), for
  one consistent "race snapshot". "Two fastest laps" = the two drivers with the quickest
  individual laps in that race (not two arbitrarily chosen drivers).
- **Year range**: 2018–present. FastF1 telemetry is unreliable before 2018, so the UI never
  offers earlier years rather than handling a missing-data error state.
- **Visual design**: "cinematic dark" — near-black canvas (`#0d0d0f`), bold red primary
  (`#e8383a`), teal/cyan accent (`#2dd4bf`), condensed broadcast-graphics typography. Chosen
  over an editorial-light and a dashboard-grid direction after a brainstorming pass.
- **Page layout**: single vertical scrolling page, sections full-width in the order track map →
  speed traces → strategy → position changes. Chosen over a 2x2 dashboard grid because the
  strategy and position charts need width to stay legible with ~20 drivers. Naturally mobile
  friendly (already one column).
- **Sync / caching**: FastF1 downloads ~50-100MB per race on first fetch (1-3 min), then
  caches to disk (`cache/`, gitignored). `src/precache.py` pulls any un-synced race and writes
  its PNGs + `_meta.json`; `src/plots.py` `ensure_race_cached()` only touches FastF1 when an
  artefact is missing.
- **Frozen (2026-10-31)**: from ~15 Oct 2026 F1 requires a paid F1 TV subscription for its
  timing archive (FastF1 issue #978). Rather than pay, the site is frozen at the 2026 Dutch GP
  (round 12): the weekly `sync-races.yml` workflow was deleted (it also reported success while
  failing), and the site footer says why coverage ends. `src/precache.py` still works locally
  for older seasons the free FastF1 mirror holds.

## Environment

- Only Python available on this machine is 3.14 (via the `py` launcher) — no pinned lower
  version to fall back to. If any dependency lacks a 3.14 wheel on Windows, that's the first
  thing to check.

See the approved plan for full architecture:
`C:\Users\alex\.claude\plans\https-github-com-theoehrly-fast-f1-https-glimmering-ladybug.md`
