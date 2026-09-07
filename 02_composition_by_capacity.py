"""
02_composition_by_capacity.py
=============================

The battery composition at any capacity: interpolated between the workbook's
five BEV sizes and extrapolated beyond them, with a Monte Carlo band.

    ./.venv/bin/python 00_parameters.py                 # first, always
    ./.venv/bin/python 02_composition_by_capacity.py
    ./.venv/bin/python 02_composition_by_capacity.py --capacity 150 --level element

Writes two PNGs to the project root:

  battery_mass_by_capacity.png        one panel per component: mass against
                                      capacity, anchors, curve, band
  battery_total_mass_by_capacity.png  whole-battery mass by chemistry, and what
                                      the extrapolation implies for Wh/kg

and prints the composition table at the requested capacity.

The interpolation itself lives in `src/composition.py`; every setting lives in
`src/params_schema.py`. This file only asks and draws.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from src.composition import CompositionError, CompositionModel  # noqa: E402
from src.params_schema import ParameterError, current  # noqa: E402

INK = "#1c1c1c"
MUTED = "#5c5c5c"
CURVE = "#2f6f9f"
BAND = "#8fbcd9"
ANCHOR = "#1c1c1c"
EXTRAP = "#f2e7e3"


def _style(ax) -> None:
    ax.grid(True, linestyle="--", alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def _mark_extrapolation(ax, last_anchor: float, upper: float) -> None:
    """Shade where the answer stops being interpolation and starts being a line."""
    if upper <= last_anchor:
        return
    ax.axvspan(last_anchor, upper, color=EXTRAP, zorder=0)
    ax.axvline(last_anchor, color="#b98c7d", linewidth=0.9, linestyle="--", zorder=1)


def draw_component_panels(model: CompositionModel, capacities: np.ndarray):
    params = model.params
    figure_params, mc = params.capacity_figure, params.monte_carlo
    chemistry = figure_params.components_figure_chemistry

    curves = model.component_curves(capacities, chemistry=chemistry)
    keys, central, lower, upper = (curves["keys"], curves["central"],
                                   curves["lower"], curves["upper"])
    anchor_x, anchor_y = curves["anchor_capacities"], curves["anchor_mass"]
    last_anchor = float(anchor_x[-1])

    n_panels = len(keys)
    columns = 4
    rows = int(np.ceil(n_panels / columns))
    fig, axes = plt.subplots(rows, columns, figsize=figure_params.components_figure_size_in,
                             sharex=True)
    axes = np.atleast_1d(axes).ravel()

    for index in range(n_panels):
        ax = axes[index]
        _mark_extrapolation(ax, last_anchor, capacities[-1])
        if mc.enabled:
            ax.fill_between(capacities, lower[index], upper[index],
                            color=BAND, alpha=0.45, linewidth=0)
        ax.plot(capacities, central[index], color=CURVE, linewidth=1.8)
        ax.plot(anchor_x, anchor_y[index], "o", color=ANCHOR, markersize=4.5,
                zorder=3, label="workbook")
        branch = "pack" if keys.loc[index, "chemistry"] == params.scope.pack_level_key else "cell"
        ax.set_title(f"{keys.loc[index, 'component']}", fontsize=8.5, loc="left", color=INK)
        ax.text(0.015, 0.90, branch, transform=ax.transAxes, fontsize=7,
                color=MUTED, va="top")
        ax.set_ylim(bottom=0)
        _style(ax)

    for ax in axes[n_panels:]:
        ax.axis("off")
    for ax in axes[max(0, n_panels - columns):n_panels]:
        ax.set_xlabel("battery capacity [kWh]", fontsize=8)
    for row in range(rows):
        axes[row * columns].set_ylabel("mass [kg]", fontsize=8)

    band_text = (f"shaded band = Monte Carlo p{mc.lower_percentile:g}–p{mc.upper_percentile:g}, "
                 f"{mc.n_draws:,} draws, {mc.distribution}"
                 if mc.enabled else "Monte Carlo disabled")
    fig.suptitle(
        f"Battery component mass against capacity — {chemistry}\n"
        f"dots = the workbook's five BEV sizes · line = {params.interpolation.interpolation_method} "
        f"interpolation · shaded area past {last_anchor:g} kWh = linear extrapolation · {band_text}",
        fontsize=11, ha="left", x=0.008, y=0.995)
    fig.text(0.008, 0.005,
             "The workbook's min/max is a flat ±10% of the value on every row, whatever "
             "the source count — so the band is that convention carried through the "
             "arithmetic, not evidence about how well these numbers are known.",
             fontsize=7.5, color="#8a3b3b")
    fig.tight_layout(rect=[0, 0.02, 1, 0.94])
    return fig


def draw_totals(model: CompositionModel, capacities: np.ndarray):
    params = model.params
    figure_params, mc = params.capacity_figure, params.monte_carlo
    chemistries = sorted(set(model._series.keys["chemistry"]) - {params.scope.pack_level_key})
    highlighted = figure_params.components_figure_chemistry
    last_anchor = float(model._series.capacities[-1])

    fig, (ax_mass, ax_density) = plt.subplots(
        1, 2, figsize=figure_params.totals_figure_size_in)

    colours = plt.get_cmap("tab10")
    for index, chemistry in enumerate(chemistries):
        curve = model.total_mass_curve(capacities, chemistry=chemistry)
        is_highlighted = chemistry == highlighted
        ax_mass.plot(curve.capacity_kwh, curve.mass_kg, color=colours(index % 10),
                     linewidth=2.2 if is_highlighted else 1.2,
                     alpha=1.0 if is_highlighted else 0.75, label=chemistry)
        ax_density.plot(curve.capacity_kwh, curve.capacity_kwh * 1000 / curve.mass_kg,
                        color=colours(index % 10),
                        linewidth=2.2 if is_highlighted else 1.2,
                        alpha=1.0 if is_highlighted else 0.75)
        if is_highlighted and mc.enabled:
            ax_mass.fill_between(curve.capacity_kwh,
                                 curve[f"mass_p{mc.lower_percentile:g}"],
                                 curve[f"mass_p{mc.upper_percentile:g}"],
                                 color=colours(index % 10), alpha=0.2, linewidth=0)

    for ax in (ax_mass, ax_density):
        _mark_extrapolation(ax, last_anchor, capacities[-1])
        ax.set_xlabel("battery capacity [kWh]", fontsize=9)
        _style(ax)

    ax_mass.set_ylabel("whole-battery mass [kg]", fontsize=9)
    ax_mass.set_title("Total mass", fontsize=10, loc="left")
    ax_mass.set_ylim(bottom=0)
    ax_mass.legend(fontsize=7, frameon=False, loc="upper left")

    ax_density.set_ylabel("specific energy [Wh/kg]", fontsize=9)
    ax_density.set_title("What that implies for energy density", fontsize=10, loc="left")

    fig.suptitle(
        f"Whole-battery mass against capacity, by chemistry — band shown for {highlighted}\n"
        f"shaded area past {last_anchor:g} kWh is extrapolated, not data",
        fontsize=11, ha="left", x=0.008, y=0.99)
    fig.text(0.008, 0.005,
             "Read the right-hand panel as a sanity check on the left one: a straight-line "
             "extrapolation of mass means energy density keeps improving with size, which is "
             "an assumption the workbook never made.",
             fontsize=7.5, color="#8a3b3b")
    fig.tight_layout(rect=[0, 0.04, 1, 0.90])
    return fig


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Composition at any battery capacity.")
    parser.add_argument("--capacity", type=float, default=150.0,
                        help="capacity in kWh to print the table for (default: 150)")
    parser.add_argument("--chemistry", default=None,
                        help="cell chemistry (default: capacity_figure.components_figure_chemistry)")
    parser.add_argument("--level", default="component", choices=["component", "material", "element"],
                        help="level of detail for the printed table (default: component)")
    parser.add_argument("--no-figures", action="store_true", help="print the table only")
    args = parser.parse_args(argv)

    try:
        params = current()
    except ParameterError as error:
        print(f"src/params_schema.py is NOT valid:\n  {error}", file=sys.stderr)
        return 1

    try:
        model = CompositionModel(params, project_root=PROJECT_ROOT)
        chemistry = args.chemistry or params.capacity_figure.components_figure_chemistry

        table = model.weights_at(args.capacity, chemistry=chemistry, level=args.level,
                                 aggregate_elements=args.level == "element")
    except CompositionError as error:
        print(f"{error}", file=sys.stderr)
        return 1

    label = "element" if args.level == "element" else "component"
    print(f"\n{chemistry} at {args.capacity:g} kWh, {args.level} level"
          f"{'  [EXTRAPOLATED]' if bool(table['extrapolated'].iloc[0]) else ''}")
    columns = [c for c in (label, "branch", "mass_kg", *[c for c in table.columns
                                                         if c.startswith("mass_p")], "kg_per_kwh")
               if c in table.columns]
    print(table[columns].round(3).to_string(index=False))
    print(f"{'TOTAL':<46} {table['mass_kg'].sum():10.2f} kg")

    if args.level == "element":
        components = model.weights_at(args.capacity, chemistry=chemistry, level="component")
        gap = components["mass_kg"].sum() - table["mass_kg"].sum()
        print(f"\nNOTE: the elements account for {table['mass_kg'].sum():.1f} kg of the "
              f"{components['mass_kg'].sum():.1f} kg the components come to -- {gap:.1f} kg "
              f"({gap / components['mass_kg'].sum():.0%}) is missing because "
              "batteryCellCasing and batteryCellSeparator have no element rows in the "
              "workbook at all.")

    if args.no_figures:
        return 0

    figure_params = params.capacity_figure
    capacities = np.linspace(figure_params.plot_min_kwh, figure_params.plot_max_kwh,
                             figure_params.plot_points)

    for figure, name in ((draw_component_panels(model, capacities), figure_params.components_file_name),
                         (draw_totals(model, capacities), figure_params.totals_file_name)):
        path = params.output_path(PROJECT_ROOT, name)
        figure.savefig(path, dpi=params.drawing.output_dpi, bbox_inches="tight", facecolor="white")
        print(f"Saved {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
