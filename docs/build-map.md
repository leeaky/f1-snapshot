# f1-snapshots — Build Map

**Status:** building

**Sources (the authority for this map):**
- **Brief** = the owner's build-chat brief, 2026-10-31 (problem found by the chief of staff). Cited as "Brief §x".
- **Run log** = GitHub Actions run 40742119543, "Sync race data", 2026-10-31. Cited as "Run log".
- **FastF1 #978** = https://github.com/theOehrly/Fast-F1/issues/978 (maintainer, 2026-10-18: F1 now requires an F1 TV Access subscription for the timing archive). Cited as "FastF1 #978".
- **Source-conflict rule (owner, 2026-10-31):** the owner's decision in this chat wins over the Brief's original goal.

## Goal and use case

Original goal (Brief): every finished race syncs on its own, and a failed race shows as a failure, not a green tick.

Changed by the owner on 2026-10-31, after learning F1's race data now needs a paid F1 TV subscription: "if fastf1 becomes a paid service, it is time to retire this project" → chose **freeze**. The site stays live with every race already synced (2018 to the 2026 Dutch GP, round 12), stops trying to sync new races, and tells visitors where coverage ends. Nothing runs on a schedule that can fail quietly behind a green tick.

Confirmed by the owner on 2026-10-31.

## Big picture

Two moving parts today: a weekly GitHub job that fetches new races and saves their charts, and a second job that publishes those charts as the website whenever `main` changes. Freezing means switching off the first and leaving the second alone, then changing the words on the site and in the docs that still promise weekly updates.

**Stages are the order things get built, not how the finished tool runs.**

| # | Stage | Depends on |
|---|---|---|
| 1 | Sync stops | — |
| 2 | Site says it's frozen | 1 |
| 3 | Loose ends | 2 |

## Stages

### Stage 1 — Sync stops
- **What gets built:** the weekly race-fetching job is removed, so nothing runs on a schedule any more.
- **Why:** it can no longer fetch new races without a paid account, and it reports success while failing (Run log; FastF1 #978).
- **Depends on:** nothing
- **Produces:** a repo whose only GitHub job is publishing the site.
- **Terms:** workflow (a script GitHub runs for you, on a schedule or when code changes)
- **Status:** done
- **Tasks:**
  - [x] (a) Remove the weekly sync job.
    Detail: delete `.github/workflows/sync-races.yml` (see Q1). `deploy-pages.yml` untouched. `src/precache.py` stays for local use.
  - [x] (b) Update the project notes so they no longer describe a weekly sync.
    Detail: `CLAUDE.md` (Commands/Conventions CI line), `README.md` "How it works", `context.md` Decisions → new "Frozen 2026-10-31" decision under Sync / caching. Also stale comments in `.gitignore`, `src/app.py`, `src/plots.py`, `deploy-pages.yml` (comment only, no behaviour change).
  - [x] (c) Deploy (owner): merge the PR, then check the Actions tab.
    Detail: look for "Sync race data" gone from the workflow list; "Deploy to GitHub Pages" run on the merge is green.
- **How we know:** after the merge, the Actions tab lists 1 workflow instead of 2, and no run appears on Wednesday 2026-11-04.
- **Issues:** none
- **Verified:** 2026-10-31 — `git rm .github/workflows/sync-races.yml` then listing `.github/workflows`: only `deploy-pages.yml` left (on branch `freeze-site`, not merged)
- **Verified:** 2026-11-01 — owner merged PR #2 (merge commit `5c99b0b`, 2026-10-31 16:13 UTC). `gh workflow list`: only "Deploy to GitHub Pages" active. `gh run list`: "Deploy to GitHub Pages" on `5c99b0b` completed, success. The Wednesday 2026-11-04 check can't fail now that the workflow no longer exists.

### Stage 2 — Site says it's frozen
- **What gets built:** a line on every page saying coverage ends with the 2026 Dutch GP and why; the "page not found" message stops promising weekly updates.
- **Why:** visitors otherwise expect races after round 12 to appear (Brief; owner's freeze decision).
- **Depends on:** Stage 1 (ships in the same PR)
- **Produces:** a live site that is honest about being frozen.
- **Terms:** none
- **Status:** done
- **Tasks:**
  - [x] (a) Add a frozen-coverage line to the site footer.
    Detail: `templates/base.html` footer: "Coverage ends with the 2026 Dutch Grand Prix — F1's timing data now requires a paid F1 TV subscription, so this site is no longer updated."
  - [x] (b) Change the "race not found" message so it no longer says races are added each week.
    Detail: `templates/error.html` line 7.
  - [x] (c) Build the site locally and check the new text appears on a real race page.
    Detail: `python -m src.build_site`, then search `dist/` for the footer line on the 2026 round 12 page; render locally with `flask run` and open it.
  - [x] (d) Deploy (owner): merge the PR (same one as Stage 1), open the live site.
    Detail: the "Deploy to GitHub Pages" run must be green; on https://leeaky.github.io/f1-snapshot/ the footer shows the new line and the 2026 season still lists rounds 1–12.
  - [x] (e) README opening line, the site's search description, and the home page title and headline say where coverage ends.
    Detail: cherry-picked onto `freeze-followup` (PR #2 was merged before these two commits were pushed): `README.md` opening + freeze note moved up; `templates/base.html` meta description; `templates/index.html` `<title>` (owner, 2026-11-01: "Yes, add it"). Built 2026-11-01: `dist/index.html` title reads "F1 Snapshot — relive any race from 2018 to the 2026 Dutch GP". Headline `<h1>` "Relive any race / 2018–2026" (owner, 2026-11-01: "Change headline too"); `flask run` home page at desktop and 375px wide: fits on two lines, no console errors. Owner merges the follow-up PR; live `<meta name="description">` should read "from 2018 to the 2026 Dutch Grand Prix".
- **How we know:** the live site footer shows the coverage line on the home page and the 2026 Dutch GP page, and 2026 still shows 12 races.
- **Issues:** none
- **Verified:** 2026-10-31 — `python -m src.build_site`: built 184 race pages + 9 event lists; footer line found in 186 of 186 HTML files; 12 race pages for 2026. `flask run`: /race/2026/12 shows the footer line, no console errors; /race/2026/13 shows the new "coverage ends" message. Live site not yet checked (needs merge).
- **Verified:** 2026-10-31 — `python scripts/audit_telemetry.py`: exit 1, "184 audited | 0 corrupt | 1 degraded | 109 errored". All 109 errors are `RateLimitExceededError: any API: 500 calls/h` (FastF1's hourly call limit), not bad data; the degraded one is 2019 r5 (1/20 drivers), already known to the audit. Gate not passed.
- **Changed:** 2026-11-01 — owner: "Stop it". The audit gate no longer applies once frozen: it guards newly synced data and `--renew` re-checks, and neither happens without a paid account; this change touches no data or chart code. Re-run stopped unfinished. Owner, 2026-11-01: "Yes, drop it" — audit line removed from CLAUDE.md's Definition of done.
- **Verified:** 2026-11-01 — live site after PR #2: footer line present on https://leeaky.github.io/f1-snapshot/ and /race/2026/12/; the 2026 race list has 12 entries, ending with the Dutch Grand Prix. Live meta description still the old "since 2018" one until task (e) merges.
- **Changed:** 2026-11-01 — owner: "Yes, fix it" (README opening, then meta description) → task (e).
- **Verified:** 2026-11-01 — owner merged PR #3 (merge commit `f0046b0`, includes `296060a`); "Deploy to GitHub Pages" on `f0046b0` completed, success. Live https://leeaky.github.io/f1-snapshot/: title "F1 Snapshot — relive any race from 2018 to the 2026 Dutch GP", headline "Relive any race / 2018–2026", meta description "…from 2018 to the 2026 Dutch Grand Prix…". Owner: "all good".

### Stage 3 — Loose ends
- **What gets built:** the 2018 Italian GP gets a page that says there's no data for it; the FastF1 version is fixed so every machine uses the same one; every "since 2018" wording becomes "2018 to the 2026 Dutch GP"; the decision on F1's terms is written down.
- **Why:** the follow-ups listed at the end of Stage 2. Owner, 2026-11-01: "fix all of the above - put a "no info" page for 2018 italian GP"; on terms: "Will let up until F1 says to take down."
- **Depends on:** Stage 2
- **Produces:** no gap in the 2018 season list, and docs that match the frozen site.
- **Terms:** version pin (telling the installer to use one exact version of a library instead of "this or newer")
- **Status:** done
- **Changed:** 2026-11-01 — added after sign-off at the owner's request.
- **Tasks:**
  - [x] (a) Add a "no data" page for the 2018 Italian GP that still shows the race name, date and winner.
    Detail: `static/plots/2018_14_meta.json` with `"no_data": true` (no images); `plots.cached_races()` includes no-data races; `app.race()` renders new `templates/race_no_data.html`; `scripts/audit_telemetry.py` skips no-data races (nothing to audit).
  - [x] (b) Fix the FastF1 version so the website build always installs the same one.
    Detail: `requirements.txt` `fastf1>=3.4` → `fastf1==3.9.0` (what the last green deploy installed); install into `.venv` and rebuild.
  - [x] (c) Replace the remaining "since 2018" wording and record the terms decision.
    Detail: `CLAUDE.md` lines 7 and 33 (+ a note on no-data races), `context.md` Year range + new decisions "Missing races", "F1 terms", and the pin.
  - [x] (d) Build the site locally and check the 2018 Italian GP page and the 2018 race list.
    Detail: `python -m src.build_site`; `flask run` → /race/2018/14/, 2018 list has 21 races.
  - [x] (e) Deploy (owner): merge the PR, open the live 2018 Italian GP page.
    Detail: "Deploy to GitHub Pages" green; https://leeaky.github.io/f1-snapshot/race/2018/14/ shows the no-data page.
- **How we know:** the live 2018 season lists 21 races instead of 20, and /race/2018/14/ shows the no-data page instead of "page not found".
- **Issues:** none
- **Verified:** 2026-11-01 — `pip install -r requirements.txt`: `.venv` now FastF1 3.9.0. `python -m src.build_site`: exit 0, 185 race pages (was 184); `dist/race/2018/14/index.html` exists; `dist/api/events/2018.json` lists 21 races incl. Italian Grand Prix. `flask run`: /race/2018/14/ shows name, Monza · 02 September 2018, winner Lewis Hamilton, "No charts for this race"; /race/2018/13/ still shows its 4 charts; no console errors. Audit race list: 184 races, 2018 r14 excluded. Search for "since 2018" outside data/docs: no matches.
- **Verified:** 2026-10-31 — owner merged PR #4 (merge commit `61170a3`); "Deploy to GitHub Pages" on `61170a3` completed, success. Live `api/events/2018.json`: 21 races; live /race/2018/14/: status 200, shows "02 September 2018", "Lewis Hamilton", "No charts for this race". Owner's screenshot of the live home page: 2018 dropdown lists 21 races incl. Italian Grand Prix (first showed 20 — the browser's 10-minute cached copy of the old list, `Cache-Control: max-age=600`; not a site bug).

## Blocks

None.

## Open questions

- **Q1 — Delete the sync job, or keep a manual-only version?** Deleting is the simplest freeze. Keeping a manual "run now" button would still fail for any race after round 12 without an account. *Status:* resolved — owner, 2026-10-31: "Delete it". The local command `python -m src.precache` remains if ever needed.

## Code overlay

Owner's stance on existing code (2026-10-31): keep the app as is; change only what the freeze needs.

| Stage | Status | Evidence | Gaps against the map | Proposal |
|---|---|---|---|---|
| 1 Sync stops | extra | `.github/workflows/sync-races.yml` | weekly job still scheduled, swallows failures (line 83) | remove |
| 2 Site says it's frozen | missing | `templates/base.html`, `templates/error.html` | footer silent; error page promises weekly updates | fix |

## Follow-ups (outside this build)

- `requirements.txt` has `fastf1>=3.4` unpinned: CI installed 3.9.0, this PC has 3.8.3.
- 2018 round 14 (Italian GP) has no page; it failed via FastF1's free mirror today.
- FastF1 #978 commenters raised whether publishing charts made from F1 data is within F1's terms; not checked.

## Sign-off

Signed off by the owner on 2026-10-31.
