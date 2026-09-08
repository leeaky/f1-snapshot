"""Audit FastF1 race telemetry for the position-stream corruption first seen
in the 2026 Hungarian GP.

Symptom (see src/data.py `_telemetry_is_sane`): F1's live-timing position feed
freezes on the last-known coordinate for long stretches, then teleports the car
to catch up, while the speed channel quantises. The merged X/Y path then
disagrees wildly with the lap's own Distance channel: p99 of
(xy_jump / distance_delta) runs ~170-400 for a corrupt session vs ~17 on clean
data. This is upstream data: FastF1 fetches the correct, canonical endpoint and
parses it without error; there is no alternative telemetry source and no "v2"
of a session's archive.

Usage
-----
    python scripts/audit_telemetry.py
        Audit every race the project has processed (one row per
        static/plots/*_meta.json). Cache-first: fully-cached races cost no
        network. Exits 1 if any race is corrupt (usable as a pre-deploy gate).

    python scripts/audit_telemetry.py --year 2026
        Restrict the sweep to one season.

    python scripts/audit_telemetry.py 2026 11
        Verbose per-driver breakdown for a single race.

    python scripts/audit_telemetry.py 2026 11 --renew
        Force a fresh re-download of that one race, bypassing every cache
        layer, then re-check. Use this to find out whether F1 has since
        re-published corrected data for a race previously flagged corrupt.

Does a fix get picked up automatically? No. Three cache layers pin the bad
data, and `--renew` only busts them for the race you name:
  1. FastF1's parsed cache/<year>/<event>/<session>/*.ff1pkl  (never revalidated)
  2. FastF1's HTTP cache  cache/fastf1_http_cache.sqlite
  3. this project's own  static/plots/<year>_<round>_*  (ensure_race_cached
     skips FastF1 entirely when these exist)
When `--renew` shows a race has become clean, this script prints the exact
purge + regenerate commands for it.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import fastf1  # noqa: E402

import data  # noqa: E402  (src/ is on the path; enables the shared cache on import)


def _iter_processed_races() -> list[tuple[int, int]]:
    """(year, round) for every race with a saved meta file, sorted.

    Mirrors plots.cached_races() but without the "all four PNGs present"
    gate: a race whose charts were skipped for corrupt telemetry still has
    a meta file and is exactly what we want to keep auditing.
    """
    races = []
    for meta_path in data.PLOTS_DIR.glob("*_meta.json"):
        year_str, round_str = meta_path.stem.split("_")[:2]
        races.append((int(year_str), int(round_str)))
    return sorted(races)


def _lap_ratio_p99(lap: fastf1.core.Lap) -> float | None:
    """p99 of per-sample (xy_jump / distance_delta) for a lap's telemetry,
    or None if the lap has no usable telemetry. Same computation as
    data._telemetry_is_sane, surfaced as a number for reporting.
    """
    try:
        tel = lap.get_telemetry()
    except Exception:  # noqa: BLE001 - unusable telemetry, treat as "no data"
        return None
    if len(tel) < 2:
        return None
    xy = tel.loc[:, ("X", "Y")].to_numpy()
    xy_jump = np.linalg.norm(np.diff(xy, axis=0), axis=1)
    dist_delta = np.abs(np.diff(tel["Distance"].to_numpy()))
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(dist_delta > 0.01, xy_jump / dist_delta, 0.0)
    return float(np.percentile(ratio, 99))


class RaceReport:
    def __init__(self, year: int, round_number: int):
        self.year = year
        self.round_number = round_number
        self.event_name = f"{year} round {round_number}"
        self.error: str | None = None
        self.rows: list[tuple[str, float | None]] = []  # (abbr, p99 or None)

    @property
    def with_tel(self) -> list[tuple[str, float]]:
        return [(a, p) for a, p in self.rows if p is not None]

    @property
    def corrupt(self) -> list[tuple[str, float]]:
        thr = data.MAX_PLAUSIBLE_JUMP_RATIO
        return [(a, p) for a, p in self.with_tel if p >= thr]

    @property
    def verdict(self) -> str:
        """One of:
        ERROR         - session wouldn't load
        no telemetry  - loaded, but no driver's fastest lap has usable telemetry
        CORRUPT       - session-wide: most drivers fail the self-consistency
                        check (Hungary 2026 = 21/22). A blocker; exits 1.
        degraded      - a few isolated laps fail (Miami 2026 = 1/22, HAD). The
                        app's next-fastest-driver fallback covers this; not a
                        blocker; exits 0.
        ok            - every lap with telemetry is self-consistent
        """
        if self.error:
            return "ERROR"
        if not self.with_tel:
            return "no telemetry"
        if not self.corrupt:
            return "ok"
        # session-wide if a third or more of the field is affected
        if len(self.corrupt) >= max(3, len(self.with_tel) / 3):
            return "CORRUPT"
        return "degraded"

    def one_line(self) -> str:
        if self.error:
            return f"{self.year} r{self.round_number:>2}  {self.event_name:<26}  ERROR: {self.error}"
        n_bad, n_tot = len(self.corrupt), len(self.with_tel)
        p99s = [p for _, p in self.with_tel]
        med = np.median(p99s) if p99s else float("nan")
        mx = max(p99s) if p99s else float("nan")
        flag = {"CORRUPT": "  <-- CORRUPT", "degraded": "  (isolated)"}.get(self.verdict, "")
        return (
            f"{self.year} r{self.round_number:>2}  {self.event_name:<26}  "
            f"bad {n_bad:>2}/{n_tot:<2}  p99 med {med:6.1f} max {mx:7.1f}  "
            f"{self.verdict}{flag}"
        )


def audit_race(year: int, round_number: int) -> RaceReport:
    report = RaceReport(year, round_number)
    try:
        session = data.load_race(year, round_number)
    except Exception as exc:  # noqa: BLE001 - report, don't abort the sweep
        report.error = f"{type(exc).__name__}: {str(exc)[:80]}"
        return report

    report.event_name = f"{session.event['EventName']}"
    for drv in session.drivers:
        lap = session.laps.pick_drivers(drv).pick_fastest()
        if lap is None or pd.isna(lap["LapTime"]):
            report.rows.append((session.get_driver(drv)["Abbreviation"], None))
            continue
        p99 = _lap_ratio_p99(lap)
        report.rows.append((session.get_driver(drv)["Abbreviation"], p99))
    return report


def _print_verbose(report: RaceReport) -> None:
    thr = data.MAX_PLAUSIBLE_JUMP_RATIO
    print("\n" + "=" * 60)
    print(f"{report.event_name} {report.year}  (round {report.round_number})")
    print(f"corruption threshold (p99 xy_jump/dist): {thr}")
    print("=" * 60)
    print(f"{'drv':>5}  {'p99 ratio':>12}   verdict")
    print("-" * 60)
    for abbr, p99 in report.rows:
        if p99 is None:
            print(f"{abbr:>5}  {'--':>12}   no telemetry")
        else:
            print(f"{abbr:>5}  {p99:12.1f}   {'CORRUPT' if p99 >= thr else 'ok'}")
    print("-" * 60)
    print(report.one_line())


def _print_renew_followup(report: RaceReport) -> None:
    """After a --renew that came back clean for a race we know was corrupt:
    the fresh data is now in the FastF1 cache, but the project's generated
    page still shows the old (skipped/garbled) charts. Tell the user how to
    rebuild just this race.
    """
    if report.verdict != "ok":
        return
    y, r = report.year, report.round_number
    stale = sorted(data.PLOTS_DIR.glob(f"{y}_{r:02d}_*"))
    print("\n" + "=" * 60)
    print(f"{report.event_name} {y} now PASSES on freshly downloaded data.")
    print("The FastF1 cache is already updated. To rebuild this race's page:")
    print("=" * 60)
    if stale:
        print("  # drop the stale generated artefacts")
        for p in stale:
            print(f"  rm {p.relative_to(REPO_ROOT).as_posix()}")
    print("  # regenerate charts + meta from the fresh telemetry")
    print(f"  python -m src.precache {y} --rounds {r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("year", nargs="?", type=int, help="single race: season")
    parser.add_argument("round", nargs="?", type=int, help="single race: round number")
    parser.add_argument(
        "--year", dest="season", type=int, default=None,
        help="sweep mode: restrict to this season",
    )
    parser.add_argument(
        "--renew", action="store_true",
        help="single race only: bypass every cache layer and re-download",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="per-driver breakdown",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s"
    )
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    single = args.year is not None and args.round is not None

    if args.renew and not single:
        parser.error("--renew needs an explicit race, e.g. `audit_telemetry.py 2026 11 --renew`")
    if args.renew:
        print(f">>> --renew: bypassing HTTP + parsed cache for {args.year} r{args.round}\n")
        fastf1.Cache.enable_cache(str(data.CACHE_DIR), force_renew=True)

    if single:
        report = audit_race(args.year, args.round)
        _print_verbose(report) if (args.verbose or args.renew) else print(report.one_line())
        if args.renew:
            _print_renew_followup(report)
        return 1 if report.verdict in ("CORRUPT", "degraded", "ERROR") else 0

    races = _iter_processed_races()
    if args.season is not None:
        races = [(y, r) for y, r in races if y == args.season]
    if not races:
        print("No processed races found (static/plots/*_meta.json). Run precache first.")
        return 0

    print(f"Auditing {len(races)} race(s)  (threshold p99 >= {data.MAX_PLAUSIBLE_JUMP_RATIO})\n")
    reports = [audit_race(y, r) for y, r in races]
    print()
    by_verdict: dict[str, list[RaceReport]] = {}
    for rep in reports:
        print(rep.one_line())
        by_verdict.setdefault(rep.verdict, []).append(rep)

    corrupt = by_verdict.get("CORRUPT", [])
    errored = by_verdict.get("ERROR", [])
    degraded = by_verdict.get("degraded", [])

    print("\n" + "-" * 60)
    print(
        f"{len(reports)} audited | {len(corrupt)} corrupt | "
        f"{len(degraded)} degraded | {len(errored)} errored"
    )
    for rep in corrupt + degraded:
        drivers = ", ".join(a for a, _ in rep.corrupt)
        print(f"  {rep.verdict.upper():8} {rep.year} r{rep.round_number} {rep.event_name}: "
              f"{len(rep.corrupt)}/{len(rep.with_tel)} drivers ({drivers})")
        print(f"           re-check for an upstream fix: "
              f"python scripts/audit_telemetry.py {rep.year} {rep.round_number} --renew")

    # Exit non-zero only for session-wide corruption or load errors; an
    # isolated bad lap ("degraded") is covered by the app's fallback and
    # shouldn't fail a deploy gate.
    return 1 if (corrupt or errored) else 0


if __name__ == "__main__":
    sys.exit(main())
