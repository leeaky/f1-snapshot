# f1-snapshot — context

A personal website for understanding a historical F1 race at a glance: pick a track + year,
see the track map, speed traces of the two fastest race laps, tyre strategy, and position
changes — one page per race, built from FastF1 data.

## Decisions

- **Stack**: Flask (server-rendered), matplotlib for all charts, rendered to static PNGs.
  Chosen over Streamlit for full design control; chosen over a static site generator so any
  FastF1-supported race can be selected on demand, not just a pre-built list.
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
- **First-load performance**: FastF1 downloads ~50-100MB per race on first fetch (1-3 min),
  then caches to disk (`cache/`, gitignored) and is near-instant. `src/precache.py` is a CLI to
  bulk-warm the cache + pre-generate plot images for chosen seasons ahead of time. Uncached
  races still work live via the Flask route, just slower on that first request.

## Environment

- Only Python available on this machine is 3.14 (via the `py` launcher) — no pinned lower
  version to fall back to. If any dependency lacks a 3.14 wheel on Windows, that's the first
  thing to check.

See the approved plan for full architecture:
`C:\Users\alex\.claude\plans\https-github-com-theoehrly-fast-f1-https-glimmering-ladybug.md`
