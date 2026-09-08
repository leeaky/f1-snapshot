# f1-snapshot

## What this is

Personal website: understand a historical F1 race at a glance — track map, the two
fastest laps' speed traces, tyre strategy, position changes. One page per race, any
Grand Prix since 2018. Flask app that pre-renders races to static PNGs; deployed to
GitHub Pages. Live: https://leeaky.github.io/f1-snapshot/

## Stack

Python 3.14 only (via the `py` launcher), `.venv`. Flask, matplotlib (all charts),
FastF1 (all data), pandas / numpy. `requirements.txt`. `gunicorn` is Unix-only — local
always runs `flask run`.

## Commands

- Install: `py -m venv .venv && .venv\Scripts\python -m pip install -r requirements.txt`
- Run locally: `.venv\Scripts\python -m flask --app src.app run --debug` → http://127.0.0.1:5000
- Pre-warm a season: `.venv\Scripts\python -m src.precache <year> [--rounds N N]`
- Build static site: `python -m src.build_site` (outputs `dist/`, which CI deploys)
- Telemetry audit / pre-deploy gate: `python scripts/audit_telemetry.py` (exit 1 if any race is corrupt)
- **No test suite.**

## Layout (`src/`)

`app.py` routes · `data.py` FastF1 loading + telemetry sanity · `plots.py` the four charts +
`ensure_race_cached()` · `precache.py` bulk cache/render CLI · `build_site.py` static export ·
`theme.py` colours.

## Conventions / watch out for

- All four visuals come from the **Race** session only, 2018+. "Two fastest laps" = the two drivers with the quickest individual laps in that race.
- Visual design is fixed: cinematic dark (`#0d0d0f` canvas, `#e8383a` red, `#2dd4bf` teal), broadcast-graphics type.
- FastF1 caches aggressively and does **not** auto-pick-up upstream fixes. A corrupt session (see the 2026 Hungarian GP) stays corrupt until F1 republishes it — `data.py._telemetry_is_sane` (`MAX_PLAUSIBLE_JUMP_RATIO = 50`) rejects bad laps and the UI degrades gracefully. Re-check with `python scripts/audit_telemetry.py <year> <round> --renew`.
- `cache/` (FastF1) and `static/plots/` (generated) are gitignored / data-only.
- CI: `.github/workflows/sync-races.yml` (weekly data sync), `deploy-pages.yml` (deploy on push to `main`).

## Definition of done

- [ ] The affected page renders locally with a real race (and with a data-degraded race if that path was touched)
- [ ] `python scripts/audit_telemetry.py` passes
- [ ] `context.md` decisions list updated if a decision changed
