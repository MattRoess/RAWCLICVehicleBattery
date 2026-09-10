"""
04_capacity_by_chemistry.py
===========================

Battery capacity by segment AND cathode chemistry, over time.

    ./.venv/bin/python 00_parameters.py            # first, always
    ./.venv/bin/python 04_capacity_by_chemistry.py

Prints the capacity table per segment and chemistry, and writes one figure per
capacity basis to paths.output_dir.

WHY THIS FIGURE EXISTS SEPARATELY FROM 03
------------------------------------------
`03` draws one curve per segment across all models. But LFP packs run about
20 kWh below NMC on the median and LFP's share of models on sale went 0% to 18%
between 2020 and 2026, so each of those curves is a blend of two populations
with different means and a shifting mix. Part of the flattening after 2023 may
be that mix shift rather than a technology plateau. This figure separates them.

A cell needs `min_models_per_chemistry_cell` DISTINCT MODELS before it is drawn
-- five different cars, not one car counted once per year it was on sale.

⚠️ WHERE PLAIN 'NMC' GOES DECIDES MOST OF THIS. 57% of 2026 models say only
'NMC' with no grade, and by instruction those join NMC_high. That is the right
guess for recent years -- 100 of 116 graded NMC models in 2026 are 811 -- and
the wrong one for 2018-2021, when 622 dominated. Read NMC_high before about 2022
as "NMC of unknown grade", not as high-nickel.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402
import numpy as np  # noqa: E402

from src.ev_details import EVDetails, EVDetailsError  # noqa: E402
from src.params_schema import ParameterError, current  # noqa: E402

INK = "#1c1c1c"
MUTED = "#5c5c5c"
REFERENCE = "#b0533f"


def draw(ev: EVDetails, segments: list[str]):
    params = ev.params
    settings = params.ev_details
    cells = ev.chemistry_cells(segments)
    populated = cells[cells.models >= settings.min_models_per_chemistry_cell]

    columns = 6
    rows = int(np.ceil(len(segments) / columns))
    fig, axes = plt.subplots(rows, columns, figsize=settings.capacity_by_chemistry_figure_size_in,
                             sharex=True, sharey=False)
    axes = np.atleast_1d(axes).ravel()
    drawn_chemistries: list[str] = []

    for index, segment in enumerate(segments):
        ax = axes[index]
        here = populated[populated.segment == segment]
        tops = []

        for chemistry in settings.chemistry_groups:
            if chemistry not in set(here.chemistry):
                continue
            curve = ev.curve(segment, chemistry=chemistry)
            colour = settings.chemistry_colours[chemistry]
            n_models = int(here.loc[here.chemistry == chemistry, "models"].iloc[0])

            ax.scatter(curve.points.year, curve.points.capacity_kwh, s=3.0,
                       color=colour, alpha=0.22, linewidths=0, zorder=1)
            ax.fill_between(curve.years, curve.band_low, curve.band_high,
                            color=colour, alpha=0.22, linewidth=0, zorder=2)
            ax.plot(curve.years, curve.central, color=colour, linewidth=1.9, zorder=3,
                    label=f"{chemistry} ({n_models})")
            if chemistry not in drawn_chemistries:
                drawn_chemistries.append(chemistry)
            for series in (curve.band_high, curve.points.capacity_kwh.to_numpy()):
                finite = series[np.isfinite(series)]
                if finite.size:
                    tops.append(np.nanpercentile(finite, 99))

        reference = settings.reference_battery_size_map.get(segment)
        if reference is not None:
            ax.axhline(reference, color=REFERENCE, linewidth=1.0, linestyle="--", zorder=4)
            tops.append(reference)

        if tops:
            ax.set_ylim(0, max(tops) * 1.15)
        else:
            ax.text(0.5, 0.5, f"no chemistry reaches\n{settings.min_models_per_chemistry_cell} models",
                    transform=ax.transAxes, ha="center", va="center", fontsize=7.5, color=MUTED)

        ax.set_title(segment, fontsize=9, loc="left", color=INK)
        ax.legend(fontsize=6.2, frameon=False, loc="lower right")
        ax.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=4))
        ax.grid(True, linestyle="--", alpha=0.3)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    for ax in axes[len(segments):]:
        ax.axis("off")
    for ax in axes[max(0, len(segments) - columns):len(segments)]:
        ax.set_xlabel("year", fontsize=8)
    for row in range(rows):
        axes[row * columns].set_ylabel(f"{settings.capacity_basis} capacity [kWh]", fontsize=8)

    fig.suptitle(
        f"BEV battery capacity by segment and cathode chemistry, {settings.first_year}–"
        f"{settings.last_year}  ·  {settings.capacity_basis.upper()} capacity\n"
        f"a chemistry is drawn in a segment only where at least "
        f"{settings.min_models_per_chemistry_cell} distinct models carry it  ·  "
        f"band = bootstrap over models  ·  dashed line = stock-flow battery_size_map",
        fontsize=11.5, ha="left", x=0.006, y=0.995)
    fig.text(0.006, 0.005,
             "NMC_high includes every model stating only 'NMC' with no grade — 57% of 2026 models. "
             "That is right for recent years (100 of 116 graded NMC models in 2026 are 811) and wrong for "
             "2018–2021, when 622 dominated: before about 2022, read NMC_high as 'NMC, grade unknown'.\n"
             "14% of models state no cathode at all and appear in no chemistry here. These are models, "
             "not registrations.",
             fontsize=7.5, color="#8a3b3b")
    fig.tight_layout(rect=[0, 0.045, 1, 0.93])
    return fig


def main(argv: list[str] | None = None) -> int:
    try:
        params = current()
    except ParameterError as error:
        print(f"src/params_schema.py is NOT valid:\n  {error}", file=sys.stderr)
        return 1

    segments = (list(params.ev_details.car_segments)
                + list(params.ev_details.jellybean_segments))

    for basis in params.ev_details.capacity_bases_to_plot:
        basis_params = copy.deepcopy(params)
        basis_params.ev_details.capacity_basis = basis
        settings = basis_params.ev_details

        try:
            ev = EVDetails(basis_params, project_root=PROJECT_ROOT)
            figure = draw(ev, segments)
        except EVDetailsError as error:
            print(f"{error}", file=sys.stderr)
            return 1

        counts = (ev.chemistry_cells(segments)
                  .pivot_table(index="segment", columns="chemistry", values="models",
                               fill_value=0)
                  .reindex(segments).fillna(0).astype(int))
        print(f"\n=== {basis.upper()} capacity by segment and chemistry "
              f"(cells with at least {settings.min_models_per_chemistry_cell} models)")
        for statistic in ("median", "mean", "std"):
            table = ev.chemistry_table(segments, statistic).reindex(segments)
            print(f"\n-- {statistic} kWh")
            print(table.round(1).to_string())
        print("\n-- distinct models behind each cell")
        print(counts.to_string())

        path = params.output_path(
            PROJECT_ROOT, settings.capacity_by_chemistry_file_name.format(basis=basis))
        figure.savefig(path, dpi=params.drawing.output_dpi, bbox_inches="tight",
                       facecolor="white")
        print(f"\nSaved {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
