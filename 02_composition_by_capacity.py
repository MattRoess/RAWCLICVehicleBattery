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
from src.unknown_chemistries import CompositionWithCells  # noqa: E402

INK = "#1c1c1c"
MUTED = "#5c5c5c"
CURVE = "#2f6f9f"
BAND = "#8fbcd9"
ANCHOR = "#1c1c1c"
EXTRAP = "#f2e7e3"
SHEET = "#1f5f8b"


def read_sodium_sheet(params, project_root) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """
    The sodium spreadsheet's component masses as {model component: (capacities, kg)}.

    Empty when the file is not there, so a clone without the spreadsheet (it is
    ignored by git) still draws everything else.
    """
    import re

    import openpyxl

    figure = params.capacity_figure
    path = Path(project_root) / figure.sodium_sheet_file
    if not figure.sodium_sheet_file or not path.exists():
        return {}
    sheet = openpyxl.load_workbook(path, data_only=True)["Scaled Material Composition"]
    header = {column: sheet.cell(3, column).value for column in range(1, sheet.max_column + 1)}
    capacities = {column: float(re.search(r"Mass at ([\d.]+) kWh", str(text)).group(1))
                  for column, text in header.items()
                  if text and re.search(r"Mass at ([\d.]+) kWh", str(text))}
    rows = {str(sheet.cell(row, 1).value): row for row in range(4, sheet.max_row + 1)}
    out = {}
    for component, names in figure.sodium_sheet_components.items():
        missing = [name for name in names if name not in rows]
        if missing:
            print(f"NOTE: the sodium spreadsheet has no row {missing}; {component} is drawn "
                  "without its diamonds.")
            continue
        x = np.array(sorted(capacities.values()))
        y = np.array([sum(float(sheet.cell(rows[name], column).value) for name in names)
                      for column in sorted(capacities, key=capacities.get)])
        out[component] = (x, y)
    return out


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


def draw_component_panels(model: CompositionWithCells, capacities: np.ndarray,
                          chemistry: str, sheet: dict | None = None):
    params = model.params
    figure_params, mc = params.capacity_figure, params.monte_carlo
    is_cell = model.is_cell(chemistry)

    curves = model.component_curves(capacities, chemistry=chemistry)
    keys, central, lower, upper = (curves["keys"], curves["central"],
                                   curves["lower"], curves["upper"])
    anchor_x, anchor_y = curves["anchor_capacities"], curves["anchor_mass"]
    last_anchor = float(anchor_x[-1])
    capacities = curves["capacities"]            # a sodium cell is drawn on a coarser grid

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
        if is_cell:
            # No workbook dots: this chemistry is built from literature. The sodium
            # sheet is what there is to compare against, and it is not what the
            # curve is made from.
            points = (sheet or {}).get(keys.loc[index, "component"])
            if points is not None:
                inside = (points[0] >= capacities[0]) & (points[0] <= capacities[-1])
                ax.plot(points[0][inside], points[1][inside], "D", color=SHEET,
                        markersize=5, zorder=3, label="sodium spreadsheet")
        else:
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
        # sharex hides the numbers on every row but the last, so with a panel count
        # that is not a multiple of four the panels above a short last row were
        # labelled "battery capacity" and carried no numbers. Thirteen components
        # (the sodium cells) is exactly that case.
        ax.tick_params(labelbottom=True)
    for row in range(rows):
        axes[row * columns].set_ylabel("mass [kg]", fontsize=8)

    band_text = (f"shaded band = Monte Carlo p{mc.lower_percentile:g}–p{mc.upper_percentile:g}, "
                 f"{mc.n_draws:,} draws, {mc.distribution}"
                 if mc.enabled else "Monte Carlo disabled")
    if is_cell:
        fig.suptitle(
            f"Battery component mass against capacity — {chemistry}\n"
            f"line = median of the draws · shaded area past {last_anchor:g} kWh = extrapolation · {band_text}\n"
            "diamonds = the cell breakdown in the sodium spreadsheet "
            f"({Path(params.capacity_figure.sodium_sheet_file).name}), for comparison only",
            fontsize=11, ha="left", x=0.008, y=0.995)
        fig.text(0.008, 0.005,
                 "Sodium cells are calculated from published cell figures, not measured. Where line and "
                 "diamonds disagree (casing, separator), the line takes the part from the LFP cell and "
                 "the spreadsheet assumes a share of the cell weight; neither is measured.",
                 fontsize=7.5, color="#8a3b3b")
    else:
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


def draw_totals(model: CompositionWithCells, capacities: np.ndarray):
    params = model.params
    figure_params, mc = params.capacity_figure, params.monte_carlo
    chemistries = model.chemistries()
    last_anchor = float(model._series.capacities[-1])

    fig, (ax_mass, ax_density) = plt.subplots(
        1, 2, figsize=figure_params.totals_figure_size_in)

    # EVERY chemistry drawn the same, and every one with its band. One used to be
    # thicker and fully opaque while the rest were thin and faded, which made an
    # arbitrary chemistry look like the answer; and the band was drawn for that
    # one alone, so six of seven showed no uncertainty at all and the density
    # panel showed none whatever. The data was always there for all of them.
    colours = plt.get_cmap("tab10")
    low = f"mass_p{mc.lower_percentile:g}"
    high = f"mass_p{mc.upper_percentile:g}"
    for index, chemistry in enumerate(chemistries):
        curve = model.total_mass_curve(capacities, chemistry=chemistry)
        colour = params.scenarios.workbook_chemistry_colours.get(
            chemistry, colours(index % 10))
        style = "--" if model.is_cell(chemistry) else "-"
        ax_mass.plot(curve.capacity_kwh, curve.mass_kg, color=colour,
                     linewidth=1.1, linestyle=style, label=chemistry)
        ax_density.plot(curve.capacity_kwh, curve.capacity_kwh * 1000 / curve.mass_kg,
                        color=colour, linewidth=1.1, linestyle=style)
        if mc.enabled and low in curve:
            ax_mass.fill_between(curve.capacity_kwh, curve[low], curve[high],
                                 color=colour, alpha=0.13, linewidth=0)
            # Wh/kg is capacity over mass, so the mass band inverts: the HIGH
            # mass gives the LOW specific energy.
            ax_density.fill_between(
                curve.capacity_kwh,
                curve.capacity_kwh * 1000 / curve[high],
                curve.capacity_kwh * 1000 / curve[low],
                color=colour, alpha=0.13, linewidth=0)

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
        "Whole-battery mass against capacity, by chemistry — band is the "
        f"{mc.lower_percentile:g}\u2013{mc.upper_percentile:g} percentile of the Monte Carlo\n"
        f"shaded area past {last_anchor:g} kWh is extrapolated, not data · dashed: sodium cells "
        "built from literature, drawn at their median",
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
        model = CompositionWithCells(CompositionModel(params, project_root=PROJECT_ROOT))
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
        per_component = model.weights_at(args.capacity, chemistry=chemistry, level="element")
        gap = components["mass_kg"].sum() - table["mass_kg"].sum()
        print(f"\nNOTE: the elements account for {table['mass_kg'].sum():.1f} kg of the "
              f"{components['mass_kg'].sum():.1f} kg the components come to -- {gap:.1f} kg "
              f"({gap / components['mass_kg'].sum():.0%}) has no element breakdown.")
        # Worked out from the data rather than asserted: the shortfall is not
        # only the components with no element rows at all.
        by_component = (per_component.groupby("component")["mass_kg"].sum()
                        .reindex(components.set_index("component")["mass_kg"].index)
                        .fillna(0.0))
        shortfall = (components.set_index("component")["mass_kg"] - by_component).sort_values(ascending=False)
        print("      where it goes missing:")
        for name, value in shortfall[shortfall.abs() > 0.05].items():
            share = value / components.set_index("component")["mass_kg"][name]
            print(f"        {name:<26} {value:8.2f} kg ({share:+.0%} of that component)")

    if args.no_figures:
        return 0

    figure_params = params.capacity_figure
    capacities = np.linspace(figure_params.plot_min_kwh, figure_params.plot_max_kwh,
                             figure_params.plot_points)

    sheet = read_sodium_sheet(params, PROJECT_ROOT)
    stem, _, suffix = figure_params.components_file_name.rpartition(".")
    jobs = [(draw_component_panels(model, capacities, figure_params.components_figure_chemistry),
             figure_params.components_file_name)]
    # One component figure for each sodium cell, beside the configured lithium one.
    for cell in sorted(params.export.literature_chemistry_template):
        jobs.append((draw_component_panels(model, capacities, cell, sheet),
                     f"{stem}_{cell}.{suffix}"))
    jobs.append((draw_totals(model, capacities), figure_params.totals_file_name))
    for figure, name in jobs:
        path = params.output_path(PROJECT_ROOT, name)
        figure.savefig(path, dpi=params.drawing.output_dpi, bbox_inches="tight", facecolor="white")
        print(f"Saved {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
