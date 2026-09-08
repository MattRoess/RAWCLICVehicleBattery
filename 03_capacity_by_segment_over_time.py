"""
03_capacity_by_segment_over_time.py
===================================

Battery capacity against year, one panel per vehicle segment, from the
EV-database table.

    ./.venv/bin/python 00_parameters.py                       # first, always
    ./.venv/bin/python 03_capacity_by_segment_over_time.py

Writes `bev_capacity_by_segment_over_time.png` to paths.output_dir and prints
the fitted capacity per segment per year.

The parsing, the smoothing and the bootstrap live in `src/ev_details.py`; every
setting lives in `src/params_schema.py`. This file asks and draws.

WHAT THE THREE LAYERS IN EACH PANEL ARE
----------------------------------------
  dots        every model variant on sale that year -- the Tesla Model range is
              84 of them, from 49 to 98 kWh
  wide band   the market spread, p10-p90 of those models. Real dispersion: the
              same car sold with several pack sizes. It does not shrink with
              more data
  narrow band how far the fitted curve itself would move on a different sample
              of models, bootstrapped over MODELS rather than model-years
  dashed line what RAWCLICStockAndFlow's battery_size_map assumes for that
              segment, for comparison
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
import pandas as pd  # noqa: E402

from src.ev_details import EVDetails, EVDetailsError  # noqa: E402
from src.params_schema import ParameterError, current  # noqa: E402

INK = "#1c1c1c"
MUTED = "#5c5c5c"
CURVE = "#1f5f8b"
SPREAD = "#bcd6e6"
BAND = "#5f9ec4"
SCATTER = "#9aa6ad"
REFERENCE = "#b0533f"


def draw(ev: EVDetails, segments: list[str]):
    params = ev.params
    settings = params.ev_details
    curves = ev.curves(segments)
    if not curves:
        raise EVDetailsError(f"none of the segments {segments} appear in the file.")

    columns = 6
    rows = int(np.ceil(len(curves) / columns))
    fig, axes = plt.subplots(rows, columns, figsize=settings.capacity_over_time_figure_size_in,
                             sharex=True, sharey=False)
    axes = np.atleast_1d(axes).ravel()

    for index, (segment, curve) in enumerate(curves.items()):
        ax = axes[index]

        if settings.show_model_scatter:
            # A little horizontal jitter, so a year with forty models reads as
            # forty rather than as one dark dot.
            rng = np.random.default_rng(1)
            jitter = rng.uniform(-0.22, 0.22, size=len(curve.points))
            ax.scatter(curve.points.year + jitter, curve.points.capacity_kwh,
                       s=3.5, color=SCATTER, alpha=0.35, linewidths=0, zorder=1)

        ax.fill_between(curve.years, curve.spread_low, curve.spread_high,
                        color=SPREAD, alpha=0.55, linewidth=0, zorder=2,
                        label=f"market spread p{settings.spread_lower_percentile:g}–"
                              f"p{settings.spread_upper_percentile:g}")
        ax.fill_between(curve.years, curve.band_low, curve.band_high,
                        color=BAND, alpha=0.45, linewidth=0, zorder=3,
                        label="curve uncertainty (bootstrap)")
        ax.plot(curve.years, curve.central, color=CURVE, linewidth=2.0, zorder=4,
                label="smoothed capacity")

        reference = settings.reference_battery_size_map.get(segment)
        if reference is not None:
            ax.axhline(reference, color=REFERENCE, linewidth=1.1, linestyle="--",
                       zorder=5, label="stock-flow battery_size_map")

        # Set the scale explicitly rather than letting the reference line or a
        # single outlier decide it, and only then place the label -- text put at
        # a data coordinate outside the limits drags the whole layout apart.
        top = np.nanmax(np.concatenate([
            np.atleast_1d(curve.spread_high[np.isfinite(curve.spread_high)]),
            np.atleast_1d(curve.band_high[np.isfinite(curve.band_high)]),
            np.atleast_1d(np.nanpercentile(curve.points.capacity_kwh, 98)),
            np.atleast_1d(reference if reference is not None else np.nan),
        ]))
        ax.set_ylim(0, top * 1.15)
        if reference is not None:
            ax.text(curve.years[0] + 0.2, reference + top * 0.02, f"{reference:g}",
                    fontsize=6.5, color=REFERENCE)

        ax.set_title(f"{segment}   ({curve.n_models} models)", fontsize=9,
                     loc="left", color=INK)
        ax.grid(True, linestyle="--", alpha=0.3)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    for ax in axes[len(curves):]:
        ax.axis("off")
    for ax in axes[max(0, len(curves) - columns):len(curves)]:
        ax.set_xlabel("year", fontsize=8)
    label = (f"{settings.capacity_basis} battery capacity [kWh]")
    for row in range(rows):
        axes[row * columns].set_ylabel(label, fontsize=8)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, frameon=False, fontsize=8.5,
               bbox_to_anchor=(0.5, 0.035))

    fig.suptitle(
        f"BEV battery capacity by segment, {settings.first_year}–{settings.last_year}"
        f"  ·  {settings.capacity_basis} capacity  ·  availability: {settings.availability_country}\n"
        f"curve = local linear regression, Gaussian bandwidth {settings.smoothing_bandwidth_years:g} years, "
        f"fitted to individual model variants  ·  bootstrap {settings.bootstrap_draws:,} draws over models",
        fontsize=11.5, ha="left", x=0.006, y=0.995)
    fig.text(0.006, 0.005,
             "A model counts in every year its availability window covers, so this is what was ON SALE, "
             "not what launched. These are MODELS, not registrations — a segment with many variants is not "
             "the same as a segment with many cars on the road.",
             fontsize=7.5, color="#8a3b3b")
    fig.tight_layout(rect=[0, 0.075, 1, 0.93])
    return fig, curves


def main(argv: list[str] | None = None) -> int:
    try:
        params = current()
    except ParameterError as error:
        print(f"src/params_schema.py is NOT valid:\n  {error}", file=sys.stderr)
        return 1

    settings = params.ev_details
    segments = list(settings.car_segments) + list(settings.jellybean_segments)

    try:
        ev = EVDetails(params, project_root=PROJECT_ROOT)
        figure, curves = draw(ev, segments)
    except EVDetailsError as error:
        print(f"{error}", file=sys.stderr)
        return 1

    table = pd.DataFrame({segment: pd.Series(curve.central, index=curve.years.astype(int))
                          for segment, curve in curves.items()})
    print(f"\nSmoothed {settings.capacity_basis} capacity [kWh] by segment and year")
    print(table.round(1).to_string())

    print("\nLatest year against the stock-and-flow battery_size_map:")
    latest = settings.last_year
    for segment, curve in curves.items():
        fitted = table.loc[latest, segment]
        reference = settings.reference_battery_size_map.get(segment)
        if reference is None or np.isnan(fitted):
            continue
        gap = (fitted - reference) / reference
        print(f"  {segment:<3} fitted {fitted:6.1f}   map {reference:6.1f}   "
              f"{gap:+6.0%}   ({curve.n_models} models)")

    path = params.output_path(PROJECT_ROOT, settings.capacity_over_time_file_name)
    figure.savefig(path, dpi=params.drawing.output_dpi, bbox_inches="tight", facecolor="white")
    print(f"\nSaved {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
