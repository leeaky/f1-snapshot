"""The four race-snapshot charts, adapted from FastF1's example gallery and
restyled with the cinematic-dark theme in theme.py:

- plot_track_map        <- gen_modules/examples_gallery/general/plot_annotate_corners
- plot_speed_traces      <- gen_modules/examples_gallery/telemetry/plot_speed_traces
- plot_strategy          <- gen_modules/examples_gallery/results_strategy/plot_strategy
- plot_position_changes  <- gen_modules/examples_gallery/results_strategy/plot_position_changes

get_or_create_plots() is the entry point app.py and precache.py use: it
generates only whatever PNGs are missing for a given race.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")  # must precede any pyplot import; no GUI in a web server

import gc  # noqa: E402
import logging  # noqa: E402
from pathlib import Path  # noqa: E402

import fastf1.plotting  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402
from matplotlib.colors import Normalize  # noqa: E402

from . import theme  # noqa: E402
from .data import (  # noqa: E402
    PLOTS_DIR,
    build_meta,
    finishing_order,
    format_laptime,
    load_meta,
    load_race,
    pick_two_fastest,
    save_meta,
)

logger = logging.getLogger(__name__)

DPI = 200
PLOT_NAMES = ("track_map", "speed_traces", "strategy", "position_changes")
COMPOUND_ORDER = ("SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET")


def _image_path(year: int, round_number: int, name: str) -> Path:
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    return PLOTS_DIR / f"{year}_{round_number:02d}_{name}.png"


def _save(fig: plt.Figure, path: Path) -> None:
    fig.savefig(path, dpi=DPI, facecolor=theme.BG, bbox_inches="tight")
    plt.close(fig)
    logger.info("Wrote %s", path)


def _rotate(xy: np.ndarray, angle: float) -> np.ndarray:
    rot_mat = np.array(
        [[np.cos(angle), np.sin(angle)], [-np.sin(angle), np.cos(angle)]]
    )
    return np.matmul(xy, rot_mat)


def plot_track_map(session, fastest_lap, path: Path) -> None:
    """Track outline colored by speed, with numbered corners, from the fastest lap."""
    circuit_info = session.get_circuit_info()
    tel = fastest_lap.get_telemetry()
    track = tel.loc[:, ("X", "Y")].to_numpy()
    speed = tel["Speed"].to_numpy()
    track_angle = circuit_info.rotation / 180 * np.pi
    rotated_track = _rotate(track, track_angle)

    fig, ax = plt.subplots(figsize=(9, 6.5))

    points = rotated_track.reshape(-1, 1, 2)
    segments = np.concatenate([points[:-1], points[1:]], axis=1)
    segment_speed = (speed[:-1] + speed[1:]) / 2

    line = LineCollection(
        segments,
        cmap=theme.speed_colormap(),
        norm=Normalize(speed.min(), speed.max()),
        capstyle="round",
        joinstyle="round",
    )
    line.set_array(segment_speed)
    line.set_linewidth(3.2)
    ax.add_collection(line)

    cbar = fig.colorbar(line, ax=ax, shrink=0.65, pad=0.03, aspect=25)
    cbar.set_label("Speed (km/h)", color=theme.TEXT_MUTED, size=10)
    cbar.ax.tick_params(color=theme.GRID, labelcolor=theme.TEXT_MUTED, labelsize=9)
    cbar.outline.set_edgecolor(theme.GRID)

    offset_vector = np.array([500.0, 0.0])
    for _, corner in circuit_info.corners.iterrows():
        letter = corner["Letter"] if isinstance(corner["Letter"], str) else ""
        txt = f"{int(corner['Number'])}{letter}"

        offset_angle = corner["Angle"] / 180 * np.pi
        offset_x, offset_y = _rotate(offset_vector, offset_angle)
        text_x, text_y = _rotate(
            np.array([corner["X"] + offset_x, corner["Y"] + offset_y]), track_angle
        )
        track_x, track_y = _rotate(np.array([corner["X"], corner["Y"]]), track_angle)

        ax.plot([track_x, text_x], [track_y, text_y], color=theme.GRID, linewidth=1)
        ax.scatter(text_x, text_y, color=theme.TEAL, s=190, zorder=3)
        ax.text(
            text_x, text_y, txt,
            va="center", ha="center", size=9, color=theme.BG, weight="bold", zorder=4,
        )

    # Title, not a text() placed inside the data area — corner numbers land
    # in different parts of the frame depending on the circuit's shape and
    # rotation, so nowhere inside the axes is reliably empty across tracks.
    ax.set_title(
        f"{fastest_lap['Driver']} — {format_laptime(fastest_lap['LapTime'])}",
        loc="left", color=theme.TEAL, fontsize=13, fontweight="bold", pad=12,
    )

    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_aspect("equal")
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)

    _save(fig, path)


def _unavailable_placeholder(path: Path, message: str, title: str | None = None) -> None:
    """Themed 'this chart isn't available for this race' placeholder.

    Older seasons (2018 especially — F1's first year of this kind of data
    collection) can be missing an entire telemetry stream for specific
    drivers, not just individual samples: position (X/Y) or car data
    (speed/throttle) can each be absent independently, since FastF1 fetches
    them separately. Whichever chart function hits that gap raises before
    it draws anything real; this is what it falls back to instead of
    taking the whole race page down over one chart.
    """
    fig, ax = plt.subplots(figsize=(9, 6.5))
    if title:
        ax.set_title(title, loc="left", color=theme.TEAL, fontsize=13, fontweight="bold", pad=12)
    ax.text(
        0.5, 0.5, message, transform=ax.transAxes, ha="center", va="center",
        color=theme.TEXT_MUTED, fontsize=13, linespacing=1.8,
    )
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    _save(fig, path)


def plot_speed_traces(session, two_fastest_laps, path: Path) -> None:
    """Distance vs speed for the two fastest race laps, red vs teal."""
    colors = (theme.RED, theme.TEAL)
    fig, ax = plt.subplots(figsize=(10, 5))

    for lap, color in zip(two_fastest_laps, colors):
        tel = lap.get_car_data().add_distance()
        label = f"{lap['Driver']} — {format_laptime(lap['LapTime'])}"
        ax.plot(tel["Distance"], tel["Speed"], color=color, linewidth=2.2, label=label)

    ax.set_xlabel("Distance (m)")
    ax.set_ylabel("Speed (km/h)")
    ax.legend(loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.22))

    _save(fig, path)


def _compound_color(compound: str, session) -> str:
    """Real compound color, or a neutral fallback for anomalous data.

    Some races have laps recorded with Compound == "NONE" — e.g. a
    stationary lap during a red flag with no tyre reading (2022 Monaco has
    several, alongside FastF1's own "fixed incorrect tyre stint" warnings
    for that race). FastF1's own color lookup raises ValueError for
    anything outside the real compound set, which would otherwise take the
    whole chart down over a handful of anomalous laps.
    """
    try:
        return fastf1.plotting.get_compound_color(compound, session=session)
    except ValueError:
        return theme.GRID


def plot_strategy(session, path: Path) -> None:
    """Horizontal stacked bars of tyre-compound stints, one row per driver, finishing order."""
    laps = session.laps
    stints = (
        laps[["Driver", "Stint", "Compound", "LapNumber"]]
        .groupby(["Driver", "Stint", "Compound"])
        .count()
        .reset_index()
        .rename(columns={"LapNumber": "StintLength"})
    )

    order = finishing_order(session)
    fig, ax = plt.subplots(figsize=(11, max(4.5, 0.42 * len(order))))

    for driver in order:
        driver_stints = stints.loc[stints["Driver"] == driver]
        previous_stint_end = 0
        for _, row in driver_stints.iterrows():
            compound_color = _compound_color(row["Compound"], session)
            ax.barh(
                y=driver,
                width=row["StintLength"],
                left=previous_stint_end,
                color=compound_color,
                edgecolor=theme.BG,
                linewidth=0.6,
            )
            previous_stint_end += row["StintLength"]

    # Only real compounds belong in the legend — an anomalous "NONE" entry
    # would read as a mystery fifth tyre choice rather than what it is.
    compounds_used = sorted(
        (c for c in stints["Compound"].unique() if c in COMPOUND_ORDER),
        key=COMPOUND_ORDER.index,
    )
    if compounds_used:
        # matplotlib's legend() rejects ncol=0 outright — if a whole race's
        # compound data is unrecognized (not just a stray lap or two, see
        # _compound_color), there's nothing real left to put in a legend.
        # The bars above still render (in the grey fallback), just unlabeled.
        handles = [
            plt.Rectangle((0, 0), 1, 1, color=_compound_color(c, session))
            for c in compounds_used
        ]
        ax.legend(
            handles, compounds_used, loc="upper center", bbox_to_anchor=(0.5, -0.08),
            ncol=len(compounds_used), frameon=False,
        )

    ax.set_xlabel("Lap")
    ax.invert_yaxis()
    ax.tick_params(axis="y", colors=theme.TEXT)
    ax.grid(axis="y", visible=False)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)

    _save(fig, path)


def plot_position_changes(session, path: Path) -> None:
    """Position vs lap for every driver, team-colored, labelled at start and finish."""
    fig, ax = plt.subplots(figsize=(10, 6.2))

    n_drivers = len(session.drivers)
    max_lap = int(session.laps["LapNumber"].max())
    pad = max_lap * 0.06

    # One finalized color per raw team color, not per driver: teammates must
    # keep sharing an identical color (that's how the chart says "same
    # team"), so ensure_visible/distinguish only run once per unique raw
    # color and get reused for the second driver.
    team_colors: dict[str, str] = {}
    used_colors: list[str] = []

    for drv in session.drivers:
        # A driver's last recorded row can carry a NaN Position (how FastF1
        # marks a retirement) — drop those or the line/label for that point
        # silently vanish instead of anchoring to their last valid lap.
        drv_laps = session.laps.pick_drivers(drv).dropna(subset=["Position"])
        if drv_laps.empty:
            continue
        abb = drv_laps["Driver"].iloc[0]
        style = fastf1.plotting.get_driver_style(
            identifier=abb, style=["color", "linestyle"], session=session
        )
        raw_color = style.get("color", theme.TEXT)
        if raw_color not in team_colors:
            color = theme.ensure_visible(raw_color)
            color = theme.distinguish(color, used_colors)
            used_colors.append(color)
            team_colors[raw_color] = color
        color = team_colors[raw_color]
        style["color"] = color

        ax.plot(drv_laps["LapNumber"], drv_laps["Position"], linewidth=1.8, **style)

        first, last = drv_laps.iloc[0], drv_laps.iloc[-1]
        ax.text(
            first["LapNumber"] - max_lap * 0.015, first["Position"], abb,
            va="center", ha="right", size=8.5, color=color,
        )
        ax.text(
            last["LapNumber"] + max_lap * 0.015, last["Position"], abb,
            va="center", ha="left", size=8.5, color=color,
        )

    yticks = [1] + list(range(5, n_drivers + 1, 5))
    ax.set_xlim(1 - pad, max_lap + pad)
    ax.set_ylim([n_drivers + 0.5, 0.5])
    ax.set_yticks(yticks)
    ax.set_xlabel("Lap")
    ax.set_ylabel("Position")

    _save(fig, path)


def _prune_unused_telemetry(session, keep_driver_numbers: set) -> None:
    """Free car/position telemetry for every driver except the ones used.

    FastF1's Session.load() has no way to request telemetry for only
    specific drivers — it's all 20 or nothing — but only 1-2 drivers'
    telemetry is ever actually read across all four charts (the fastest lap
    for the track map, plus one more for the speed-trace comparison).
    Measured locally, the full bulk telemetry load accounts for ~230MB of a
    ~355MB peak for a single race — against Render's free-tier 512MB
    container limit, with Flask/gunicorn overhead on top of that not even
    included in the local measurement. session.car_data / session.pos_data
    are plain dicts keyed by driver number, so once the needed drivers'
    laps have already pulled their telemetry (a fresh DataFrame each call,
    not a view into these dicts), the rest can just be dropped.
    """
    for store in (session.car_data, session.pos_data):
        for drv in list(store.keys()):
            if drv not in keep_driver_numbers:
                del store[drv]
    gc.collect()


def existing_plot_paths(year: int, round_number: int) -> dict[str, Path] | None:
    """All four image paths if every one already exists on disk, else None.

    Deliberately takes no session — the point is to answer "is this race
    fully cached?" *before* deciding whether a live FastF1 load (the
    expensive, memory-heavy path) is needed at all.
    """
    paths = {name: _image_path(year, round_number, name) for name in PLOT_NAMES}
    if all(p.exists() for p in paths.values()):
        return paths
    return None


def get_or_create_plots(session, year: int, round_number: int) -> dict[str, Path]:
    """Ensure all four chart images exist for this race, generating any missing.

    Cheap to call on every request — only regenerates what's actually
    missing on disk, so a fully-cached race costs one Path.exists() per
    chart.
    """
    theme.apply()
    paths = {name: _image_path(year, round_number, name) for name in PLOT_NAMES}
    missing = {name: p for name, p in paths.items() if not p.exists()}

    if not missing:
        return paths

    logger.info(
        "Generating %d missing plot(s) for %s round %s: %s",
        len(missing), year, round_number, list(missing),
    )

    two_fastest = None
    if "track_map" in missing or "speed_traces" in missing:
        two_fastest = pick_two_fastest(session)

    if "track_map" in missing:
        try:
            plot_track_map(session, two_fastest[0], missing["track_map"])
        except Exception:
            # Missing position telemetry for FastF1's own internal reference
            # lap (get_circuit_info() picks it, not configurable) — real,
            # not rare enough to ignore, and shouldn't take the other three
            # charts down with it. A placeholder still satisfies "this race
            # is fully cached" so it isn't retried (and re-failed) on every
            # visit.
            logger.exception(
                "Track map unavailable for %s round %s, using placeholder",
                year, round_number,
            )
            title = f"{two_fastest[0]['Driver']} — {format_laptime(two_fastest[0]['LapTime'])}"
            _unavailable_placeholder(
                missing["track_map"],
                "Track map unavailable for this race\n(no position data recorded)",
                title=title,
            )
    if "speed_traces" in missing:
        try:
            plot_speed_traces(session, two_fastest, missing["speed_traces"])
        except Exception:
            # Same shape of gap as the track map, but in car data (speed/
            # throttle) instead of position — independent telemetry stream,
            # can be missing on its own for a driver.
            logger.exception(
                "Speed traces unavailable for %s round %s, using placeholder",
                year, round_number,
            )
            _unavailable_placeholder(
                missing["speed_traces"],
                "Speed comparison unavailable for this race\n(car telemetry missing for at least one driver)",
            )
    if two_fastest is not None:
        needed = {lap["DriverNumber"] for lap in two_fastest}
        _prune_unused_telemetry(session, needed)
    if "strategy" in missing:
        plot_strategy(session, missing["strategy"])
    if "position_changes" in missing:
        plot_position_changes(session, missing["position_changes"])

    return paths


def ensure_race_cached(year: int, round_number: int) -> tuple[dict, dict[str, Path]]:
    """Ensure both metadata and all four charts exist for this race.

    Cache-first: if everything's already on disk, this is a handful of
    Path.exists()/file reads with no FastF1 involvement at all. Only loads
    the full race session — the expensive, memory-heavy path that's come
    close to Render's free-tier limit — when something's actually missing,
    and whatever that produces gets cached so it's a one-time cost per
    race, not a per-request one. Shared by the web app and precache.py so
    both stay cache-first the same way, rather than two copies of this
    logic drifting apart.
    """
    image_paths = existing_plot_paths(year, round_number)
    meta = load_meta(year, round_number) if image_paths is not None else None
    if image_paths is not None and meta is not None:
        logger.info("Already cached: %s round %s, skipping fetch", year, round_number)
        return meta, image_paths

    session = load_race(year, round_number)
    image_paths = get_or_create_plots(session, year, round_number)
    two_fastest = pick_two_fastest(session)
    meta = build_meta(session, two_fastest)
    save_meta(year, round_number, meta)
    return meta, image_paths
