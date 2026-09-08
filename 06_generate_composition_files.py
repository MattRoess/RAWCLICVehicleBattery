"""
06_generate_composition_files.py
================================

Writes the composition files the stock-and-flow model reads: **one file per
chemistry**, one row per component / material / element, for **one car** of a
given segment in a given year.

    ./.venv/bin/python 00_parameters.py                # first, always
    ./.venv/bin/python 06_generate_composition_files.py

NO CHEMISTRY MIXING HAPPENS HERE, by design. The scenario shares are applied
downstream, where the fleet numbers live. This project knows what a battery is
made of; the stock-and-flow model knows how many there are. Baking a scenario
into these files would tie them to an assumption they ought to outlive -- and
the same file then serves all three scenarios, and any later one.

WHAT EACH ROW IS
----------------
One car. `mass_kg` is the material in a single battery of that segment, year and
chemistry -- multiply by vehicle counts downstream, never by a share here.

WHERE THE CAPACITY COMES FROM
-----------------------------
The fitted nominal capacity for that segment and year (`03`), which is real data
to 2026. **Beyond 2026 it is an assumption**, set by `export.capacity_projection`
-- 'hold' keeps the 2026 figure, 'trend' continues the gradient. Every row
carries `capacity_is_projected` so a downstream user cannot mistake one for the
other.

⚠️ NOMINAL, NOT USEABLE. The workbook's kg/kWh is per nominal kWh. Useable runs
about 5% lower and would understate every mass by that much.

⚠️ 'element' DOES NOT SUM TO 'component'. batteryCellCasing and
batteryCellSeparator have no element rows in the workbook -- about 8% of pack
mass. Both levels are written so the gap is visible rather than inferred.

⚠️ SODIUM-ION AND SOLID-STATE ARE NOT WRITTEN. They have no composition in the
workbook and are not variants of anything that does. The run reports them as
missing instead of substituting a lookalike.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.composition import CompositionError, CompositionModel  # noqa: E402
from src.ev_details import EVDetails, EVDetailsError  # noqa: E402
from src.params_schema import ParameterError, current  # noqa: E402

LAST_OBSERVED_YEAR = 2026


def segment_capacities(params, ev: EVDetails, segments: list[str]) -> pd.DataFrame:
    """Nominal capacity per segment per export year, marked observed or projected."""
    export = params.export
    years = params.export_years()
    rows = []

    for segment in segments:
        try:
            curve = ev.curve(segment)
        except EVDetailsError:
            print(f"[export] segment {segment}: no models at all -- skipped.")
            continue

        fitted = pd.Series(curve.central, index=curve.years.astype(int)).dropna()
        if fitted.empty:
            print(f"[export] segment {segment}: too few models to fit a capacity "
                  f"-- skipped (this is why JA is absent).")
            continue

        last_year = int(fitted.index.max())
        last_value = float(fitted.loc[last_year])
        # Gradient of the final decade, used only by 'trend'.
        window = fitted.loc[fitted.index >= last_year - 10]
        gradient = (0.0 if len(window) < 2 else
                    float(np.polyfit(window.index.astype(float), window.to_numpy(), 1)[0]))

        for year in years:
            if year in fitted.index:
                capacity, projected = float(fitted.loc[year]), False
            elif year < fitted.index.min():
                # Before the fit starts, hold the earliest fitted year rather
                # than running a gradient backwards into four data points.
                capacity, projected = float(fitted.iloc[0]), True
            else:
                capacity = (last_value if export.capacity_projection == "hold"
                            else last_value + gradient * (year - last_year))
                projected = True
            capacity = float(np.clip(capacity, params.interpolation.min_capacity_kwh,
                                     export.max_projected_capacity_kwh))
            rows.append({"segment": segment, "year": year,
                         "capacity_kwh_nominal": round(capacity, 2),
                         "capacity_is_projected": projected})
    return pd.DataFrame(rows)


def build_rows(model: CompositionModel, params, capacities: pd.DataFrame,
               chemistry: str) -> pd.DataFrame:
    """Every row of one chemistry's file."""
    export = params.export
    frames = []
    for entry in capacities.itertuples():
        for level in export.export_levels:
            table = model.weights_at(entry.capacity_kwh_nominal, chemistry=chemistry,
                                     level=level)
            table.insert(0, "level", level)
            table.insert(0, "year", entry.year)
            table.insert(0, "segment", entry.segment)
            table["capacity_is_projected"] = entry.capacity_is_projected
            frames.append(table)

    rows = pd.concat(frames, ignore_index=True)
    rows = rows.rename(columns={"capacity_kwh": "capacity_kwh_nominal",
                                "chemistry": "layer1"})
    keep = ["segment", "year", "level", "layer1", "branch", "component", "element",
            "capacity_kwh_nominal", "capacity_is_projected", "mass_kg", "kg_per_kwh",
            "extrapolated"]
    if export.include_uncertainty:
        keep += [c for c in rows.columns if c.startswith("mass_p") or c == "mass_mean"]
    rows["chemistry"] = chemistry
    return rows[["chemistry"] + [c for c in keep if c in rows.columns]]


def main(argv: list[str] | None = None) -> int:
    try:
        params = current()
    except ParameterError as error:
        print(f"src/params_schema.py is NOT valid:\n  {error}", file=sys.stderr)
        return 1

    export = params.export
    segments = (list(params.ev_details.car_segments)
                + list(params.ev_details.jellybean_segments))

    try:
        model = CompositionModel(params, project_root=PROJECT_ROOT)
        ev_params = params  # capacity_basis already defaults to nominal
        if ev_params.ev_details.capacity_basis != "nominal":
            print("[export] WARNING: ev_details.capacity_basis is "
                  f"{ev_params.ev_details.capacity_basis!r}, but the workbook's kg/kWh "
                  "is per NOMINAL kWh. Every mass below is on the wrong basis.")
        ev = EVDetails(ev_params, project_root=PROJECT_ROOT)
        capacities = segment_capacities(params, ev, segments)
    except (CompositionError, EVDetailsError) as error:
        print(f"{error}", file=sys.stderr)
        return 1

    if capacities.empty:
        print("No segment produced a capacity series -- nothing to export.", file=sys.stderr)
        return 1

    chemistries = sorted(set(model._series.keys.chemistry) - {params.scope.pack_level_key})
    missing = [c for c in params.scenarios.chemistries_without_composition]

    print(f"Export years: {params.export_years()}")
    print(f"Segments    : {sorted(capacities.segment.unique())}")
    print(f"Capacity    : fitted to {LAST_OBSERVED_YEAR}, then "
          f"'{export.capacity_projection}', capped at {export.max_projected_capacity_kwh:g} kWh")
    print(f"Chemistries : {len(chemistries)} with composition -- {chemistries}")
    print(f"NOT written : {missing} -- no composition in the workbook, and not a "
          "variant of one that has it.")

    written = []
    for chemistry in chemistries:
        rows = build_rows(model, params, capacities, chemistry)
        name = f"composition_{chemistry}.{export.export_format}"
        path = params.composition_output_path(PROJECT_ROOT, name)
        if export.export_format == "csv":
            rows.to_csv(path, index=False)
        else:
            rows.to_excel(path, index=False, sheet_name="composition")
        written.append((path, len(rows)))
        print(f"  {path.name:<44} {len(rows):>7,} rows")

    index = capacities.pivot_table(index="segment", columns="year",
                                   values="capacity_kwh_nominal")
    index_path = params.composition_output_path(PROJECT_ROOT,
                                                f"capacity_by_segment_year.{export.export_format}")
    (capacities.to_csv(index_path, index=False) if export.export_format == "csv"
     else capacities.to_excel(index_path, index=False))
    print(f"\nNominal capacity per car [kWh] (bold years beyond {LAST_OBSERVED_YEAR} are projected):")
    print(index.round(1).to_string())
    print(f"\nAlso wrote {index_path.name}")
    print(f"\n{len(written)} files in {params.export.composition_output_dir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
