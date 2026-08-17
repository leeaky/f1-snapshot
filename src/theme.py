"""Shared 'cinematic dark' visual theme for all matplotlib charts.

Applied once via apply() before any chart is generated, so every plot in
plots.py inherits the same palette and rcParams instead of restyling itself.
"""

from __future__ import annotations

import colorsys
import math

import matplotlib as mpl
from matplotlib.colors import LinearSegmentedColormap

import fastf1.plotting

# Palette
BG = "#0d0d0f"
BG_CARD = "#141416"
RED = "#e8383a"
AMBER = "#f5a623"
TEAL = "#2dd4bf"
TEXT = "#f5f5f0"
TEXT_MUTED = "#8a8a90"
GRID = "#2a2a2e"

FONT_FAMILY = ["Arial", "Segoe UI", "DejaVu Sans", "sans-serif"]

_applied = False


def apply() -> None:
    """Configure FastF1's color-lookup tables and matplotlib rcParams.

    Idempotent — safe to call once at import time and again per-request.
    """
    global _applied
    if _applied:
        return

    # Required before fastf1.plotting.get_team_color / get_compound_color /
    # get_driver_style will return colors. 'fastf1' is FastF1's own scheme,
    # tuned so same-team cars stay visually distinguishable.
    fastf1.plotting.setup_mpl(mpl_timedelta_support=True, color_scheme="fastf1")

    mpl.rcParams.update(
        {
            "figure.facecolor": BG,
            "axes.facecolor": BG,
            "savefig.facecolor": BG,
            "axes.edgecolor": GRID,
            "axes.labelcolor": TEXT,
            "axes.grid": True,
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "text.color": TEXT,
            "xtick.color": TEXT_MUTED,
            "ytick.color": TEXT_MUTED,
            "font.family": "sans-serif",
            "font.sans-serif": FONT_FAMILY,
            "font.size": 11,
            "legend.frameon": False,
            "legend.labelcolor": TEXT,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    _applied = True


def speed_colormap() -> LinearSegmentedColormap:
    """Red (slow) -> amber -> grey (fast).

    Deliberately not a rainbow/jet scale — those aren't perceptually ordered,
    which makes them read speed *categories* rather than a smooth gradient.
    Red-for-slow matches the common motorsport-telemetry convention (braking
    zones read hot). The fast end fades to a neutral grey rather than a
    bright accent color — most of a lap is spent at high speed, so a bright
    color there would dominate the whole track line instead of just drawing
    the eye to the notable (slow/braking) sections.
    """
    return LinearSegmentedColormap.from_list("f1snapshot_speed", [RED, AMBER, TEXT_MUTED])


def _luma(r: float, g: float, b: float) -> float:
    """Perceived brightness (ITU-R BT.601 luma), 0-1."""
    return 0.299 * r + 0.587 * g + 0.114 * b


def ensure_visible(hex_color: str, min_luma: float = 0.4) -> str:
    """Lighten a color if it's too dark to read against the BG canvas.

    FastF1's team-color scheme includes hues — saturated blue especially —
    that are perceptually much darker than their HSL lightness suggests:
    blue contributes only ~11% to perceived brightness vs. ~59% for green,
    so a "medium lightness" blue can still read as near-black on screen.
    Thresholds on perceived luma instead of raw HSL lightness, and nudges
    lightness up in HSL space (preserving hue/saturation) until the color
    actually reads as lit against a near-black chart.
    """
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) / 255 for i in (0, 2, 4))
    if _luma(r, g, b) >= min_luma:
        return f"#{hex_color}"

    h, l, s = colorsys.rgb_to_hls(r, g, b)
    for _ in range(50):
        l = min(l + 0.02, 0.92)
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        if _luma(r, g, b) >= min_luma or l >= 0.92:
            break
    return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))


def _redmean_distance(hex_a: str, hex_b: str) -> float:
    """Low-cost perceptual color distance (the 'redmean' approximation)."""
    a, b = hex_a.lstrip("#"), hex_b.lstrip("#")
    r1, g1, b1 = (int(a[i : i + 2], 16) for i in (0, 2, 4))
    r2, g2, b2 = (int(b[i : i + 2], 16) for i in (0, 2, 4))
    rmean = (r1 + r2) / 2
    dr, dg, db = r1 - r2, g1 - g2, b1 - b2
    return math.sqrt((2 + rmean / 256) * dr**2 + 4 * dg**2 + (2 + (255 - rmean) / 256) * db**2)


def distinguish(hex_color: str, used_colors: list[str], min_distance: float = 90.0, floor_luma: float = 0.22) -> str:
    """Darken a color until it's visually distinct from already-used ones.

    FastF1's per-team palette repeats similar hues across a 20-driver grid
    (Ferrari red vs. Alfa Romeo/Kick Sauber red, for one) — indistinguishable
    once ensure_visible() has brightened both off a near-black floor. Steps
    lightness down (preserving hue, so team identity stays recognizable)
    until far enough from every color already claimed on this chart, or
    until floor_luma would be crossed. Call once per team, not per driver —
    teammates should keep sharing an identical color.
    """
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) / 255 for i in (0, 2, 4))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    current = f"#{hex_color}"

    for _ in range(14):
        if all(_redmean_distance(current, used) >= min_distance for used in used_colors):
            return current
        l = max(l - 0.04, 0.0)
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        current = "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))
        if _luma(r, g, b) <= floor_luma:
            return current

    return current
