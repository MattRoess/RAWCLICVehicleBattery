"""
08_composition_distributions.py
===============================

The Monte Carlo distributions themselves, not a summary of them.

    ./.venv/bin/python 00_parameters.py                    # first, always
    ./.venv/bin/python 08_composition_distributions.py

Writes one FULL-SIZE figure per chemistry to paths.output_dir. One chemistry per
figure on purpose: a 9x14 grid of thumbnails is unreadable, and the shape of a
distribution is the whole point here.

WHAT EACH FIGURE SHOWS. A ridgeline: one filled density per element, drawn from
the 200,000 draws at one capacity anchor, each normalised to its own peak so
that elements three orders of magnitude apart in mass can share an axis and
still be compared by SHAPE.

  solid line    the mode -- the most likely value, and the statistic the 200,000
                draws were actually bought for. Against the triangular factor's
                known mode it is recovered to 0.44% at 200,000 draws and only
                1.57% at 20,000
  dotted lines  the 2.5 and 97.5 percentiles
  x axis        mass relative to that element's own mode, so a wide distribution
                and a narrow one are told apart at a glance

WHY RELATIVE AND NOT ABSOLUTE. A pack holds ~120 kg of iron and ~0.2 kg of
lithium. On a shared absolute axis the lithium is a vertical line at zero. What
matters here is not how much there is -- the other figures say that -- but how
UNCERTAIN each one is, and that only shows up relative to its own value.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from src.composition import CompositionError, CompositionModel, approximate_mode  # noqa: E402
from src.params_schema import ParameterError, current  # noqa: E402



def density(values: np.ndarray, grid: np.ndarray, bins: int = 240) -> np.ndarray:
    """
    A histogram, smoothed just enough to read as a curve.

    Deliberately NOT a kernel density estimate: a KDE picks a bandwidth, and a
    bandwidth is a claim about smoothness that nobody here has made. This is the
    histogram the mode already comes from, interpolated onto a common grid.
    """
    counts, edges = np.histogram(values, bins=bins, density=True)
    centres = 0.5 * (edges[:-1] + edges[1:])
    if counts.max() > 0:
        counts = counts / counts.max()
    return np.interp(grid, centres, counts, left=0.0, right=0.0)


def draw_chemistry(model: CompositionModel, chemistry: str, capacity: float,
                   params):
    """One chemistry's element distributions, stacked as a ridgeline."""
    elements, masses = model.element_draws_at(capacity, chemistry=chemistry)
    live = [(element, row) for element, row in zip(elements, masses)
            if row.max() > row.min()]
    if not live:
        return None
    live.sort(key=lambda pair: pair[1].mean(), reverse=True)

    colour = params.scenarios.workbook_chemistry_colours[chemistry]
    height = max(6.5, 1.05 * len(live) + 2.2)
    figure, axes = plt.subplots(figsize=(13, height))
    grid = np.linspace(0.80, 1.20, 400)
    step = 1.0

    for index, (element, row) in enumerate(live):
        mode = float(approximate_mode(row[None, :])[0])
        if mode <= 0:
            continue
        relative = row / mode
        curve = density(relative, grid)
        base = index * step
        axes.fill_between(grid, base, base + curve * 0.92, color=colour,
                          alpha=0.55, linewidth=0)
        axes.plot(grid, base + curve * 0.92, color=colour, linewidth=1.3)
        axes.plot([1.0, 1.0], [base, base + 0.92], color="0.15", linewidth=1.6)
        low, high = np.percentile(relative, [2.5, 97.5])
        for edge in (low, high):
            axes.plot([edge, edge], [base, base + 0.55], color="0.35",
                      linewidth=0.9, linestyle=":")
        axes.text(0.795, base + 0.30, element, ha="right", va="center",
                  fontsize=11.5, fontweight="bold")
        axes.text(1.205, base + 0.30,
                  f"{mode:8.2f} kg   ±{100 * (high - low) / 2:4.1f}%",
                  ha="left", va="center", fontsize=9.5, color="0.35",
                  family="monospace")

    axes.set_xlim(0.74, 1.30)
    axes.set_ylim(-0.35, len(live) * step + 0.5)
    axes.set_yticks([])
    axes.set_xticks([0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15])
    axes.set_xlabel("mass relative to that element's own mode", fontsize=11)
    axes.set_title(
        f"{chemistry} — element mass distributions at {capacity:.0f} kWh\n"
        f"{params.monte_carlo.n_draws:,} draws; solid line the mode, dotted the "
        "2.5 and 97.5 percentiles; each curve scaled to its own peak",
        fontsize=12.5)
    for side in ("top", "right", "left"):
        axes.spines[side].set_visible(False)
    axes.grid(True, axis="x", linestyle="--", alpha=0.28)
    axes.set_axisbelow(True)
    figure.tight_layout()
    return figure


def main(argv: list[str] | None = None) -> int:
    try:
        params = current()
    except ParameterError as error:
        print(f"parameters: {error}", file=sys.stderr)
        return 2

    model = CompositionModel(params)
    capacity = params.export.distribution_figure_capacity_kwh
    anchors = [float(c) for c in model._series.capacities]
    if capacity not in anchors:
        print(f"export.distribution_figure_capacity_kwh is {capacity}, which is "
              f"not one of the workbook's anchors {anchors}. The per-draw arrays "
              "exist only at anchors.", file=sys.stderr)
        return 2

    known = sorted(set(model._series.keys["chemistry"])
                   - {params.scope.pack_level_key})
    print(f"{params.monte_carlo.n_draws:,} draws at {capacity:.0f} kWh")
    written = 0
    for chemistry in known:
        try:
            figure = draw_chemistry(model, chemistry, capacity, params)
        except CompositionError as error:
            print(f"  {chemistry}: {error}")
            continue
        if figure is None:
            print(f"  {chemistry}: no element varies -- skipped")
            continue
        path = params.output_path(PROJECT_ROOT,
                                  f"distribution_{chemistry}_{capacity:.0f}kWh.png")
        figure.savefig(path, dpi=params.drawing.output_dpi, bbox_inches="tight",
                       facecolor="white")
        plt.close(figure)
        print(f"  {chemistry:20s} -> {path.name}")
        written += 1
    print(f"\nSaved {written} figures to {params.paths.output_dir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
