"""
04_chemistry_scenarios.py
=========================

The three cathode-chemistry scenarios to 2070.

    ./.venv/bin/python 00_parameters.py         # first, always
    ./.venv/bin/python 04_chemistry_scenarios.py

Writes `chemistry_scenarios_to_2070.png` to paths.output_dir and prints the mix
at each anchor year, plus how much of each scenario can be costed in materials
at all.

⚠️ EVERYTHING AFTER 2026 IS AN ASSUMPTION. The observed data ends there. The
shares are a written-down judgement in `scenarios.*`, meant to be argued with.

The stack is ordered so that every chemistry WITH a composition in the workbook
sits at the bottom and those without sit on top. The line between them is
therefore the share of the market whose material content can actually be
computed -- it falls to a fifth in scenario 3 by 2070, and that is the single
most important thing this figure has to say.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from src.params_schema import ParameterError, current  # noqa: E402
from src.scenarios import SCENARIO_NAMES, ChemistryScenarios, ScenarioError  # noqa: E402

INK = "#1c1c1c"
MUTED = "#5c5c5c"
LAST_OBSERVED_YEAR = 2026


def draw(scenarios: ChemistryScenarios, *, returning: bool = False):
    """One 3x3 grid: scenarios down, segment groups across.

    `returning=False` draws the mix being SOLD; `returning=True` the mix
    ARRIVING at the recycler, which is the same scenario seen through the
    vehicle lifetime and the second-life diversion.
    """
    settings = scenarios.settings
    groups = list(settings.segment_groups)
    missing = list(settings.chemistries_without_composition)

    fig, axes = plt.subplots(len(SCENARIO_NAMES), len(groups),
                             figsize=settings.scenario_figure_size_in,
                             sharex=True, sharey=True)
    axes = np.atleast_2d(axes)

    for row, scenario in enumerate(SCENARIO_NAMES):
        frame = (scenarios.returning_shares(scenario) if returning
                 else scenarios.shares(scenario))
        for column, group in enumerate(groups):
            ax = axes[row, column]
            here = frame[frame.segment_group == group]
            wide = here.pivot_table(index="year", columns="chemistry", values="share").fillna(0.0)

            # Composition-backed chemistries first, the rest on top, so the
            # boundary between them IS the coverage line.
            with_composition = [c for c in wide.columns if c not in missing]
            without = [c for c in wide.columns if c in missing]
            ordered = with_composition + without
            colours = [settings.scenario_colours[c] for c in ordered]

            ax.stackplot(wide.index, *[wide[c] * 100 for c in ordered],
                         labels=ordered, colors=colours, alpha=0.9, linewidth=0)
            if without:
                covered = wide[with_composition].sum(axis=1) * 100
                ax.plot(wide.index, covered, color="#111111", linewidth=1.6, zorder=5)

            if not returning:
                ax.axvline(LAST_OBSERVED_YEAR, color="#8a3b3b", linewidth=1.0,
                           linestyle="--", zorder=6)
            if row == 0:
                ax.set_title(group, fontsize=10, loc="left", color=INK)
            if column == 0:
                ax.set_ylabel("share arriving for recycling [%]" if returning
                              else "share of new batteries [%]", fontsize=8)
            if row == len(SCENARIO_NAMES) - 1:
                ax.set_xlabel("year", fontsize=8)
            ax.set_ylim(0, 100)
            ax.set_xlim(wide.index.min(), wide.index.max())
            ax.grid(True, linestyle="--", alpha=0.25)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)

        axes[row, 0].text(0.012, 0.06, scenarios.label(scenario), transform=axes[row, 0].transAxes,
                          fontsize=8, color=INK, va="bottom",
                          bbox=dict(facecolor="white", edgecolor="none", alpha=0.75, pad=2))

    handles, labels = [], []
    for ax in axes.ravel():
        for handle, label in zip(*ax.get_legend_handles_labels()):
            if label not in labels:
                handles.append(handle)
                labels.append(label)
    line = plt.Line2D([], [], color="#111111", linewidth=1.6)
    fig.legend(handles + [line], labels + ["composition available below this line"],
               loc="lower center", ncol=7, frameon=False, fontsize=8.5,
               bbox_to_anchor=(0.5, 0.028))

    second_life = scenarios.params.second_life
    if returning:
        diverted = ", ".join(f"{name} {share:.0%}"
                             for name, share in second_life.second_life_share.items()
                             if share > 0)
        fig.suptitle(
            "Cathode chemistry ARRIVING FOR RECYCLING to 2070 — the same three scenarios\n"
            f"{second_life.vehicle_lifetime_years}-year vehicle life, plus "
            f"{second_life.second_life_extra_years_min}–{second_life.second_life_extra_years_max} "
            "more years for the packs that go to second life first",
            fontsize=12, ha="left", x=0.006, y=0.995)
        fig.text(0.006, 0.005,
                 f"Diverted to second life, and therefore returning later: {diverted}. Not all of any "
                 "chemistry — second_life.second_life_share is the parameter, and it is a genuine unknown "
                 "worth varying.\n"
                 "Compare with the sales figure: in 2045 the large segments return 57% NMC_high under S2 "
                 "while only 17% is being sold. What comes back is what was bought fifteen years ago, and "
                 "an LFP-heavy scenario is also the one whose material comes back latest.\n"
                 "Assumes constant annual sales volume — only shares exist here. Real volumes come from the "
                 "stock-and-flow model, and growth means the true return mix is somewhat more modern than this.",
                 fontsize=7.5, color="#8a3b3b")
    else:
        fig.suptitle(
            "Cathode chemistry of new BEV batteries to 2070 — three scenarios\n"
            "everything right of the dashed line is ASSUMPTION, not data: the observed record ends in 2026",
            fontsize=12, ha="left", x=0.006, y=0.995)
        fig.text(0.006, 0.005,
                 "Sodium-ion and bipolar solid-state have NO composition in the workbook and are not variants of "
                 "anything that does — sodium swaps the copper anode collector for aluminium, bipolar solid-state "
                 "deletes the separator, the electrolyte and the per-cell terminals. Above the black line, no "
                 "material mass can be computed.\n"
                 "These are shares of what is SOLD. With a ~15-year vehicle life, what returns for recycling in "
                 "2050 is roughly what was sold in 2035 — the scenarios barely separate on recovered material "
                 "before about 2045.",
                 fontsize=7.5, color="#8a3b3b")
    fig.tight_layout(rect=[0, 0.075, 1, 0.94])
    return fig


def main(argv: list[str] | None = None) -> int:
    try:
        params = current()
    except ParameterError as error:
        print(f"src/params_schema.py is NOT valid:\n  {error}", file=sys.stderr)
        return 1

    try:
        scenarios = ChemistryScenarios(params)
        anchors = list(params.scenarios.anchor_years)

        for name in SCENARIO_NAMES:
            frame = scenarios.shares(name)
            table = (frame[frame.year.isin(anchors)]
                     .pivot_table(index=["segment_group", "year"], columns="chemistry",
                                  values="share") * 100)
            print(f"\n=== {scenarios.label(name)}")
            print(table.round(0).fillna(0).astype(int).to_string())

        coverage = scenarios.composition_coverage()
        print("\n=== SHARE OF THE MARKET WITH A COMPOSITION IN THE WORKBOOK [%]")
        print((coverage[coverage.year.isin(anchors)]
               .pivot_table(index=["scenario", "year"], columns="segment_group",
                            values="share_with_composition") * 100).round(0).astype(int).to_string())
        print("\n  Below 100 means material mass cannot be computed for that part of the "
              "market.\n  Missing compositions: "
              f"{', '.join(params.scenarios.chemistries_without_composition)}")

        print("\n=== WHAT ARRIVES AT THE RECYCLER, vs what is being sold that year")
        print(f"  {params.second_life.vehicle_lifetime_years}-year vehicle life; "
              f"{params.second_life.second_life_extra_years_min}–"
              f"{params.second_life.second_life_extra_years_max} more years for the "
              "second-life fraction")
        for name in SCENARIO_NAMES:
            returning = scenarios.returning_shares(name)
            table = (returning[returning.year.isin([2045, 2055, 2070])]
                     .pivot_table(index=["segment_group", "year"], columns="chemistry",
                                  values="share") * 100)
            print(f"\n-- {name}, arriving [%]")
            print(table.round(0).fillna(0).astype(int).to_string())

        figures = {params.scenarios.scenario_file_name: draw(scenarios),
                   params.second_life.returning_mix_file_name: draw(scenarios, returning=True)}
    except ScenarioError as error:
        print(f"{error}", file=sys.stderr)
        return 1

    for file_name, figure in figures.items():
        path = params.output_path(PROJECT_ROOT, file_name)
        figure.savefig(path, dpi=params.drawing.output_dpi, bbox_inches="tight",
                       facecolor="white")
        print(f"\nSaved {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
