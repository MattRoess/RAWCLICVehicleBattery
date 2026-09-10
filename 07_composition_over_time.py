"""
07_composition_over_time.py
===========================

What one BEV's battery is made of, 2020 to 2070, and what that costs in critical
raw materials.

    ./.venv/bin/python 00_parameters.py                    # first, always
    ./.venv/bin/python 06_generate_composition_files.py    # writes what this reads
    ./.venv/bin/python 07_composition_over_time.py

TWO KINDS OF FIGURE, both full size.

  composition_over_time_<chemistry>.png
      ALL ELEMENTS IN ONE FIGURE, one figure per chemistry. Stacked, so the
      total pack mass and the split between elements are read off the same
      picture: the band is the whole battery, each layer an element.

  crm_over_time_<element>.png
      One critical raw material, every chemistry, with its 2.5-97.5 band. This
      is the comparison the raw-materials question actually asks -- how much
      lithium, cobalt, nickel does a car need, and how much does the answer
      depend on which chemistry wins.

WHY THE LINES FALL. Every chemistry now has an energy-density trajectory, and a
density gain IS a mass reduction: the same kWh needs less cell, and the pack
hardware around a smaller stack is lighter. Lithium chemistries improve 30% by
2050 and then stop, on the argument that liquid electrolyte runs out near
400-450 Wh/kg; solid-state keeps going to 800. Capacity works the other way and
grows to 2030 before the range target saturates it, which is why the early years
rise before the decline sets in.

DASHED means the composition is NOT known -- sodium and solid-state, where only
the packaging is claimed and the cathode, anode and electrolyte are
unknownBatteryMaterial. Those layers are absent from the stack, so a sodium
figure shows less than a whole battery on purpose.
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
import pandas as pd  # noqa: E402

from src.params_schema import ParameterError, current  # noqa: E402

UNKNOWN_COMPOSITION = ("Na_ion", "solid_state")
UNKNOWN_MATERIAL = "unknownBatteryMaterial"


def load_composition(params) -> pd.DataFrame:
    directory = PROJECT_ROOT / params.export.composition_output_dir
    files = sorted(directory.glob("composition_*.csv"))
    if not files:
        raise FileNotFoundError(
            f"no composition files in {directory}. Run "
            "06_generate_composition_files.py first -- this script draws what "
            "that one computes, and does not recompute it.")
    frames = [pd.read_csv(path) for path in files]
    rows = pd.concat(frames, ignore_index=True)
    return rows[rows.level == "element"]


def draw_chemistry(rows: pd.DataFrame, chemistry: str, segment: str, params):
    """Every element of one chemistry, stacked, across the years."""
    wanted = rows[(rows.chemistry == chemistry) & (rows.segment == segment)
                  & (rows.element != UNKNOWN_MATERIAL)]
    if wanted.mass_kg.notna().sum() == 0:
        return None
    table = (wanted.pivot_table(index="year", columns="element", values="mass_kg",
                                aggfunc="sum").fillna(0.0).sort_index())
    table = table.loc[:, table.sum() > 0]
    # Heaviest at the bottom: the stack then reads as a battery, structure first.
    table = table[table.sum().sort_values(ascending=False).index]

    figure, axes = plt.subplots(figsize=(13.5, 8))
    colours = plt.get_cmap("tab20")(np.linspace(0, 1, max(len(table.columns), 2)))
    axes.stackplot(table.index, table.T.values, labels=table.columns,
                   colors=colours, alpha=0.9, edgecolor="white", linewidth=0.6)
    total = table.sum(axis=1)
    axes.plot(total.index, total, color="0.15", linewidth=2.2,
              label=f"total ({total.iloc[0]:.0f} → {total.iloc[-1]:.0f} kg)")
    # THE UNCERTAINTY, on the total. Per-element bands cannot go on this figure:
    # iron is 600x lithium, and on one linear axis lithium's band is invisible.
    # The total's band is summed ON THE DRAWS -- the 97.5th percentile of a sum
    # is not the sum of the 97.5th percentiles -- and the CRM figures carry the
    # per-element bands at a scale where they can actually be read.
    band = (wanted.groupby("year")[["mass_p2.5", "mass_p97.5"]]
            .sum(min_count=1).reindex(total.index))
    if band["mass_p2.5"].notna().any():
        axes.fill_between(total.index, band["mass_p2.5"], band["mass_p97.5"],
                          color="0.15", alpha=0.18, linewidth=0,
                          label="total, 2.5-97.5 percentile")

    unknown = chemistry in UNKNOWN_COMPOSITION
    axes.set_xlabel("year", fontsize=11)
    axes.set_ylabel("mass in one car [kg]", fontsize=11)
    axes.set_title(
        f"{chemistry} — every element, segment {segment}, 2020-2070"
        + ("\nPACKAGING ONLY: the cathode, anode and electrolyte are not known "
           "for this chemistry" if unknown else
           f"\ntotal falls {100 * (1 - total.iloc[-1] / total.max()):.0f}% from its "
           "peak as the cells improve"),
        fontsize=12.5)
    axes.grid(True, linestyle="--", alpha=0.3)
    axes.set_axisbelow(True)
    for side in ("top", "right"):
        axes.spines[side].set_visible(False)
    axes.legend(frameon=False, fontsize=9.5, ncol=2, loc="upper center",
                bbox_to_anchor=(0.5, -0.09))
    axes.set_ylim(bottom=0)
    figure.tight_layout()
    return figure


def draw_crm(rows: pd.DataFrame, element: str, segment: str, params):
    """One critical raw material, every chemistry, with its band."""
    figure, axes = plt.subplots(figsize=(13, 7.5))
    wanted = rows[(rows.element == element) & (rows.segment == segment)]
    drawn = 0
    for chemistry, group in wanted.groupby("chemistry"):
        series = (group.groupby("year")[["mass_kg", "mass_p2.5", "mass_p97.5"]]
                  .sum(min_count=1).sort_index())
        if series.mass_kg.notna().sum() == 0:
            continue
        colour = params.scenarios.workbook_chemistry_colours[chemistry]
        unknown = chemistry in UNKNOWN_COMPOSITION
        axes.plot(series.index, series.mass_kg, label=chemistry, color=colour,
                  linewidth=2.4, linestyle="--" if unknown else "-",
                  marker="o", markersize=4.5)
        if series["mass_p2.5"].notna().any():
            axes.fill_between(series.index, series["mass_p2.5"],
                              series["mass_p97.5"], color=colour, alpha=0.15,
                              linewidth=0)
        drawn += 1
    if drawn == 0:
        plt.close(figure)
        return None

    axes.set_xlabel("year", fontsize=11)
    axes.set_ylabel(f"{element} in one car [kg]", fontsize=11)
    axes.set_title(
        f"{element} per car, segment {segment}, 2020-2070 — every chemistry\n"
        "band is the 2.5-97.5 percentile of the Monte Carlo; dashed chemistries "
        "have only their packaging known",
        fontsize=12.5)
    axes.grid(True, linestyle="--", alpha=0.3)
    axes.set_axisbelow(True)
    for side in ("top", "right"):
        axes.spines[side].set_visible(False)
    axes.legend(frameon=False, fontsize=10, ncol=2)
    axes.set_ylim(bottom=0)
    figure.tight_layout()
    return figure


def save(figure, params, name: str) -> str:
    path = params.output_path(PROJECT_ROOT, name)
    figure.savefig(path, dpi=params.drawing.output_dpi, bbox_inches="tight",
                   facecolor="white")
    plt.close(figure)
    return path.name


def main(argv: list[str] | None = None) -> int:
    try:
        params = current()
    except ParameterError as error:
        print(f"parameters: {error}", file=sys.stderr)
        return 2

    rows = load_composition(params)
    segment = params.export.over_time_figure_segment
    if segment not in set(rows.segment.dropna()):
        print(f"segment {segment!r} is not in the composition files.",
              file=sys.stderr)
        return 2

    print(f"Segment {segment}, {rows.year.min():.0f}-{rows.year.max():.0f}\n")
    print("all elements, one figure per chemistry:")
    written = 0
    for chemistry in sorted(rows.chemistry.dropna().unique()):
        figure = draw_chemistry(rows, chemistry, segment, params)
        if figure is None:
            print(f"  {chemistry:20s} nothing claimed -- skipped")
            continue
        print(f"  {chemistry:20s} -> "
              f"{save(figure, params, f'composition_over_time_{chemistry}.png')}")
        written += 1

    print("\ncritical raw materials, every chemistry:")
    for element in params.export.crm_elements:
        figure = draw_crm(rows, element, segment, params)
        if figure is None:
            print(f"  {element:3s} nothing claimed -- skipped")
            continue
        print(f"  {element:3s} -> {save(figure, params, f'crm_over_time_{element}.png')}")
        written += 1

    print(f"\nSaved {written} figures to {params.paths.output_dir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
