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

import logging  # noqa: E402
from pathlib import Path  # noqa: E402

import fastf1.plotting  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402
from matplotlib.colors import Normalize  # noqa: E402

from . import theme  # noqa: E402
from .data import PLOTS_DIR, finishing_order, format_laptime, pick_two_fastest  # noqa: E402

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
        segments, cmap=theme.speed_colormap(), norm=Normalize(speed.min(), speed.max())
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
            compound_color = fastf1.plotting.get_compound_color(
                row["Compound"], session=session
            )
            ax.barh(
                y=driver,
                width=row["StintLength"],
                left=previous_stint_end,
                color=compound_color,
                edgecolor=theme.BG,
                linewidth=0.6,
            )
            previous_stint_end += row["StintLength"]

    compounds_used = sorted(
        stints["Compound"].unique(),
        key=lambda c: COMPOUND_ORDER.index(c) if c in COMPOUND_ORDER else len(COMPOUND_ORDER),
    )
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=fastf1.plotting.get_compound_color(c, session=session))
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
        plot_track_map(session, two_fastest[0], missing["track_map"])
    if "speed_traces" in missing:
        plot_speed_traces(session, two_fastest, missing["speed_traces"])
    if "strategy" in missing:
        plot_strategy(session, missing["strategy"])
    if "position_changes" in missing:
        plot_position_changes(session, missing["position_changes"])

    return paths
