"""
07_composition_over_time.py
===========================

How much of each element one BEV carries, 2020 to 2070, by chemistry.

    ./.venv/bin/python 00_parameters.py                    # first, always
    ./.venv/bin/python 06_generate_composition_files.py    # writes what this reads
    ./.venv/bin/python 07_composition_over_time.py

Writes one FULL-SIZE figure per element to paths.output_dir. One element per
figure on purpose: a grid of small panels cannot be read, and the point of these
is to be read.

WHAT EACH FIGURE SHOWS
----------------------
  line        the element's mass in one car of the chosen segment, that year,
              for one chemistry -- the central estimate
  band        the 2.5-97.5 percentile of the Monte Carlo, the same draws every
              other number in this project comes from
  dashed      a chemistry whose composition is NOT known (sodium, solid-state).
              Drawn only where a mass exists at all, which for those two means
              the packaging: the cathode, the anode and the electrolyte are
              unknownBatteryMaterial and contribute nothing to any element line

WHY THE LINES MOVE. Composition per kWh does not change with the year -- the
workbook has no year axis. What changes is the CAPACITY each segment carries,
which grows to 2030 and then saturates at the range target. Sodium and
solid-state move for a second reason: their structure follows their own density
trajectory, so it lightens (solid-state) or does not (sodium) as the cells
improve.
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

# The elements worth a figure of their own: the ones a raw-materials model is
# actually asked about, plus the structural three that dominate the mass.
ELEMENTS = ("Li", "Ni", "Co", "Mn", "Cu", "Al", "Fe", "C")

UNKNOWN_COMPOSITION = ("Na_ion", "solid_state")


def load_composition(params) -> pd.DataFrame:
    """Every chemistry's element rows, from what 06 wrote."""
    directory = PROJECT_ROOT / params.export.composition_output_dir
    files = sorted(directory.glob("composition_*.csv"))
    if not files:
        raise FileNotFoundError(
            f"no composition files in {directory}. Run "
            "06_generate_composition_files.py first -- this script draws what "
            "that one computes, and does not recompute it.")
    frames = []
    for path in files:
        frame = pd.read_csv(path)
        frames.append(frame[frame.level == "element"])
    return pd.concat(frames, ignore_index=True)


def draw_element(rows: pd.DataFrame, element: str, segment: str, params):
    """One element, every chemistry, across the years. Full size, one panel."""
    figure, axes = plt.subplots(figsize=(13, 7.5))
    wanted = rows[(rows.element == element) & (rows.segment == segment)]

    drawn = 0
    for chemistry, group in wanted.groupby("chemistry"):
        series = (group.groupby("year")[["mass_kg", "mass_p2.5", "mass_p97.5"]]
                  .sum(min_count=1).sort_index())
        if series.mass_kg.notna().sum() == 0:
            continue                      # nothing claimed for this one
        colour = params.scenarios.workbook_chemistry_colours[chemistry]
        unknown = chemistry in UNKNOWN_COMPOSITION
        axes.plot(series.index, series.mass_kg, label=chemistry, color=colour,
                  linewidth=2.4, linestyle="--" if unknown else "-",
                  marker="o", markersize=4.5)
        if series["mass_p2.5"].notna().any():
            axes.fill_between(series.index, series["mass_p2.5"],
                              series["mass_p97.5"], color=colour, alpha=0.16,
                              linewidth=0)
        drawn += 1

    if drawn == 0:
        plt.close(figure)
        return None

    axes.set_xlabel("year", fontsize=11)
    axes.set_ylabel(f"{element} in one car [kg]", fontsize=11)
    axes.set_title(
        f"{element} per car, segment {segment}, 2020-2070\n"
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


def main(argv: list[str] | None = None) -> int:
    try:
        params = current()
    except ParameterError as error:
        print(f"parameters: {error}", file=sys.stderr)
        return 2

    rows = load_composition(params)
    segment = params.export.over_time_figure_segment
    if segment not in set(rows.segment.dropna()):
        print(f"segment {segment!r} is not in the composition files: "
              f"{sorted(set(rows.segment.dropna()))}", file=sys.stderr)
        return 2

    print(f"Segment {segment}, years {rows.year.min():.0f}-{rows.year.max():.0f}")
    written = 0
    for element in ELEMENTS:
        figure = draw_element(rows, element, segment, params)
        if figure is None:
            print(f"  {element:3s} nothing claimed by any chemistry -- skipped")
            continue
        path = params.output_path(PROJECT_ROOT,
                                  f"composition_over_time_{element}.png")
        figure.savefig(path, dpi=params.drawing.output_dpi, bbox_inches="tight",
                       facecolor="white")
        plt.close(figure)
        print(f"  {element:3s} -> {path.name}")
        written += 1
    print(f"\nSaved {written} figures to {params.paths.output_dir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
