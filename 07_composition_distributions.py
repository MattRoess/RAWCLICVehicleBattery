"""
07_composition_distributions.py
===============================

How much of a material a battery holds, and how sure we are -- compared across
chemistries, which is the comparison that carries information.

    ./.venv/bin/python 00_parameters.py                    # first, always
    ./.venv/bin/python 07_composition_distributions.py

ONE FULL-SIZE FIGURE PER MATERIAL, plus one for the whole pack. Each shows every
chemistry's distribution of that quantity, overlaid, in absolute kg on a linear
axis, at one capacity anchor.

WHAT THE EARLIER VERSION GOT WRONG, and why this is not that. It drew one
ridgeline per chemistry with an element per row, on an axis relative to each
element's own mode. Every element in this model shares ONE Monte Carlo factor
per series, so every one of those curves was the same +/-7.8% triangle: nine
curves carrying a single fact, with the only thing that actually differed --
the magnitude -- divided out. Comparing chemistries at the same quantity keeps
the magnitude, and the differences between chemistries are real.

  solid line   the mode, the statistic the 200,000 draws were bought for
  dotted       the 2.5 and 97.5 percentiles of that chemistry
  filled       the distribution, scaled to its own peak so a narrow one and a
               wide one are both visible -- the HEIGHT carries no meaning, the
               position and width carry all of it

A chemistry that does not contain the material at all is absent, not drawn at
zero. Sodium and solid-state appear only where the packaging holds the material:
their cathode, anode and electrolyte are unknownBatteryMaterial, so they are on
the copper and aluminium figures and not on lithium or nickel.
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

UNKNOWN_COMPOSITION = ("Na_ion", "solid_state")


def density(values: np.ndarray, grid: np.ndarray, bins: int = 200) -> np.ndarray:
    """
    A histogram on a shared grid, scaled to its own peak.

    Deliberately not a kernel density estimate: a KDE picks a bandwidth, and a
    bandwidth is a claim about smoothness nobody here has made. This is the same
    histogram the mode comes from.
    """
    counts, edges = np.histogram(values, bins=bins, density=True)
    centres = 0.5 * (edges[:-1] + edges[1:])
    if counts.max() > 0:
        counts = counts / counts.max()
    return np.interp(grid, centres, counts, left=0.0, right=0.0)


def collect(model: CompositionModel, params, capacity: float, element: str | None
            ) -> dict[str, np.ndarray]:
    """Every chemistry's draws for one element, or for the whole pack."""
    out: dict[str, np.ndarray] = {}
    known = sorted(set(model._series.keys["chemistry"])
                   - {params.scope.pack_level_key})
    for chemistry in known:
        try:
            elements, masses = model.element_draws_at(capacity, chemistry=chemistry)
        except CompositionError:
            continue
        if element is None:
            row = masses.sum(axis=0)
        else:
            if element not in elements:
                continue
            row = masses[elements.index(element)]
        if row.max() <= row.min():
            continue                       # a fixed zero is not a distribution
        out[chemistry] = row
    return out


def draw(series: dict[str, np.ndarray], title: str, xlabel: str, params):
    """Every chemistry's distribution of one quantity, overlaid, in kg."""
    if not series:
        return None
    low = min(np.percentile(v, 0.2) for v in series.values())
    high = max(np.percentile(v, 99.8) for v in series.values())
    pad = 0.06 * (high - low)
    grid = np.linspace(low - pad, high + pad, 500)

    figure, axes = plt.subplots(figsize=(13.5, 8))
    order = sorted(series, key=lambda c: series[c].mean())
    for chemistry in order:
        row = series[chemistry]
        colour = params.scenarios.workbook_chemistry_colours[chemistry]
        curve = density(row, grid)
        style = "--" if chemistry in UNKNOWN_COMPOSITION else "-"
        axes.fill_between(grid, 0, curve, color=colour, alpha=0.22, linewidth=0)
        axes.plot(grid, curve, color=colour, linewidth=2.0, linestyle=style,
                  label=chemistry)
        mode = float(approximate_mode(row[None, :])[0])
        axes.plot([mode, mode], [0, 1.02], color=colour, linewidth=1.4, alpha=0.9)
        for edge in np.percentile(row, [2.5, 97.5]):
            axes.plot([edge, edge], [0, 0.30], color=colour, linewidth=1.0,
                      linestyle=":", alpha=0.9)

    axes.set_xlabel(xlabel, fontsize=11)
    axes.set_ylabel("relative frequency (each scaled to its own peak)", fontsize=10.5)
    axes.set_title(title, fontsize=12.5)
    axes.set_ylim(0, 1.16)
    axes.grid(True, axis="x", linestyle="--", alpha=0.3)
    axes.set_axisbelow(True)
    for side in ("top", "right", "left"):
        axes.spines[side].set_visible(False)
    axes.set_yticks([])
    axes.legend(frameon=False, fontsize=10, ncol=3, loc="upper center",
                bbox_to_anchor=(0.5, -0.10))
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
        print(f"export.distribution_figure_capacity_kwh is {capacity}, not one of "
              f"the anchors {anchors}; the per-draw arrays exist only at anchors.",
              file=sys.stderr)
        return 2

    draws = params.monte_carlo.n_draws
    print(f"{draws:,} draws at {capacity:.0f} kWh\n")
    written = 0

    figure = draw(collect(model, params, capacity, None),
                  f"Whole battery mass at {capacity:.0f} kWh — every chemistry\n"
                  f"{draws:,} draws; solid line the mode, dotted the 2.5 and 97.5 "
                  "percentiles",
                  "battery mass in one car [kg]", params)
    if figure is not None:
        path = params.output_path(PROJECT_ROOT,
                                  f"distribution_total_{capacity:.0f}kWh.png")
        figure.savefig(path, dpi=params.drawing.output_dpi, bbox_inches="tight",
                       facecolor="white")
        plt.close(figure)
        print(f"  {'whole pack':12s} -> {path.name}")
        written += 1

    for element in params.export.crm_elements:
        series = collect(model, params, capacity, element)
        figure = draw(series,
                      f"{element} at {capacity:.0f} kWh — every chemistry that "
                      f"contains it\n{draws:,} draws; solid line the mode, dotted "
                      "the 2.5 and 97.5 percentiles",
                      f"{element} in one car [kg]", params)
        if figure is None:
            print(f"  {element:12s} no chemistry claims it -- skipped")
            continue
        path = params.output_path(PROJECT_ROOT,
                                  f"distribution_{element}_{capacity:.0f}kWh.png")
        figure.savefig(path, dpi=params.drawing.output_dpi, bbox_inches="tight",
                       facecolor="white")
        plt.close(figure)
        print(f"  {element:12s} -> {path.name}   ({len(series)} chemistries)")
        written += 1

    print(f"\nSaved {written} figures to {params.paths.output_dir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
