"""
08_consolidated_composition.py
==============================

The deliverable in the workbook's own schema: kg of each material, per chemistry,
per capacity anchor, per year.

    ./.venv/bin/python 00_parameters.py                  # first, always
    ./.venv/bin/python 08_consolidated_composition.py

ONE FILE PER CHEMISTRY, so none of them gets big, into
`export.consolidated_output_dir`. Beside each, the per-draw arrays that the
summary statistics come from -- the distribution next to the value, not instead
of it.

THE SCHEMA IS THE INPUT WORKBOOK'S, EXPANDED. Nothing is invented: every
`Layer 1`, `Layer 2` and `Layer 4` value is the workbook's own, and
`additionalSpecification`, `parameterCode`, `DQS` and `count_value` are carried
through untouched. What is added:

    productionYear     the year, from export_year_step
    capacity_kwh       the anchor, so kg is interpretable
    UoM                'kg' -- the input is kg/kWh, this is a mass
    Value              kg, at that anchor in that year
    min_value/max_value the workbook's own band, in kg
    meanValue, medianValue, modeValue, STD, p025, p975
                       the Monte Carlo, named as RAWCLICVehicleElectronics names
                       them so both sets of files read the same way

WHY THE YEAR CHANGES THE MASS. Each chemistry now has an energy-density
trajectory, and a density improvement IS a mass reduction: the same kWh needs
less cell, and the pack hardware around a smaller cell stack is lighter too. So
every mass is scaled by

    density(base year) / density(that year)

which is 1.00 in 2025 and, for NMC high-Ni, 0.77 by 2050. Uniform across
components, which is an assumption -- cables in particular scale with current
rather than energy, so this understates them slightly in later years.

AT A FIXED ANCHOR THE FRACTIONS DO NOT MOVE, because the scaling is uniform.
That is why one draw array per (chemistry, anchor) serves every year.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.composition import CompositionError, CompositionModel  # noqa: E402
from src.params_schema import ParameterError, current  # noqa: E402

# The input workbook's own column order, then what this script adds.
WORKBOOK_COLUMNS = ["additionalSpecification", "Layer 1", "Layer 2", "Layer 4",
                    "parameterCode", "UoM", "DQS"]
ADDED_COLUMNS = ["productionYear", "capacity_kwh", "Value", "min_value",
                 "max_value", "count_value", "meanValue", "medianValue",
                 "modeValue", "STD", "p025", "p975"]

LEVEL_CODES = {"component": "component_parameter_code",
               "material": "material_parameter_code",
               "element": "element_parameter_code"}



def rows_for(model: CompositionModel, params, chemistry: str, capacity: float
             ) -> pd.DataFrame:
    """Every level at one anchor, in the workbook's shape, in kg, before the year."""
    scope = params.scope
    frames = []
    for level, attribute in LEVEL_CODES.items():
        try:
            table = model.weights_at(capacity, chemistry=chemistry, level=level)
        except CompositionError:
            continue                       # not every level resolves for every chemistry
        band = params.monte_carlo
        frame = pd.DataFrame({
            "additionalSpecification": f"BATTinELV_BEV_{int(capacity)}kWh",
            "Layer 1": table["chemistry"],
            "Layer 2": table["component"],
            "Layer 4": table["element"] if "element" in table else "n/a",
            "parameterCode": getattr(scope, attribute),
            "UoM": "kg",
            "capacity_kwh": float(capacity),
            "Value": table["mass_kg"],
            "min_value": table["mass_kg"] * (1.0 - band.relative_band),
            "max_value": table["mass_kg"] * (1.0 + band.relative_band),
            "meanValue": table["mass_mean"],
            "medianValue": table["mass_median"],
            "modeValue": table["mass_mode"],
            "STD": table["mass_std"],
            "p025": table["mass_p2.5"],
            "p975": table["mass_p97.5"],
        })
        # DQS and count_value are the workbook's own judgement of the row and are
        # carried through rather than recomputed. Joined on the keys the workbook
        # itself uses, at this capacity.
        source = model.anchors
        source = source[source.kwh == float(capacity)]
        keys = ["chemistry", "component", "element", "code"]
        frame = frame.merge(
            source[keys + ["DQS", "count_value"]].drop_duplicates(subset=keys),
            left_on=["Layer 1", "Layer 2", "Layer 4", "parameterCode"],
            right_on=keys, how="left").drop(columns=keys)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def main(argv: list[str] | None = None) -> int:
    try:
        params = current()
    except ParameterError as error:
        print(f"parameters: {error}", file=sys.stderr)
        return 2

    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "generator", PROJECT_ROOT / "05_generate_composition_files.py")
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)

    model = CompositionModel(params)
    anchors = [float(c) for c in model._series.capacities]
    years = params.export_years()
    scaled = ["Value", "min_value", "max_value", "meanValue", "medianValue",
              "modeValue", "STD", "p025", "p975"]

    directory = PROJECT_ROOT / params.export.consolidated_output_dir
    directory.mkdir(parents=True, exist_ok=True)
    known = sorted(set(model._series.keys["chemistry"]) - {params.scope.pack_level_key})
    # Na_ion and solid_state are not IN the workbook, so they are not in
    # model._series -- they are built from a base chemistry by
    # export.unknown_chemistry_template. Leaving them out would have shipped
    # seven files where nine were asked for.
    unknown = sorted(params.export.unknown_chemistry_template)

    print(f"{params.monte_carlo.n_draws:,} draws | anchors {[int(a) for a in anchors]} "
          f"| years {years[0]}-{years[-1]} step {params.export.export_year_step} "
          f"| density base {params.export.density_base_year}")

    for chemistry in known:
        has_trajectory = chemistry in params.technology.chemistry_energy_density
        # generator.density_factor, not a second copy of the arithmetic: 06 and
        # 09 disagreeing about this exact quantity is what made every figure
        # flat after 2025.
        def factor_for(year: float) -> float:
            return generator.density_factor(params, chemistry, year)
        per_year = []
        for capacity in anchors:
            at_anchor = rows_for(model, params, chemistry, capacity)
            elements, draws = model.element_draws_at(capacity, chemistry=chemistry)
            totals = draws.sum(axis=0)
            fractions = np.zeros_like(draws)
            live = totals > 0
            fractions[:, live] = draws[:, live] / totals[live]
            stem = f"{chemistry}_{int(capacity)}kWh"
            np.save(directory / f"{stem}_draws.npy", fractions.T.astype(np.float32))
            (directory / f"{stem}_elements.txt").write_text("\n".join(elements))

            for year in years:
                frame = at_anchor.copy()
                frame["productionYear"] = year
                factor = factor_for(float(year))
                if factor != 1.0:
                    for column in scaled:
                        frame[column] = pd.to_numeric(frame[column],
                                                      errors="coerce") * factor
                per_year.append(frame)

        rows = pd.concat(per_year, ignore_index=True)
        rows = rows[WORKBOOK_COLUMNS + ADDED_COLUMNS]
        path = directory / f"consolidated_{chemistry}.csv"
        rows.to_csv(path, index=False)
        note = "" if has_trajectory else "   (no trajectory -- flat in year)"
        print(f"  {chemistry:20s} {len(rows):>7,} rows -> {path.name}{note}")

    # ---------------------------------------------------------------------
    # The two chemistries with no workbook composition. build_unknown_rows is
    # reused rather than reimplemented: it holds every claim the templates make
    # -- what bipolar removes, the aluminium swap and its conductance factor,
    # the halved collectors, the structure scaling, the remainder. Repeating any
    # of that here is how the two would drift apart.
    #
    # It keys on (segment, year), so each anchor is handed to it as a segment
    # named for its capacity. That is a shim, and the 'segment' it returns is
    # dropped again below.
    # ---------------------------------------------------------------------
    for chemistry in unknown:
        capacities = pd.DataFrame([
            {"segment": f"{int(a)}kWh", "year": y, "capacity_kwh_nominal": a,
             # build_rows carries both through onto every row it makes. An
             # anchor is neither fitted nor projected -- it is the workbook's
             # own capacity -- and saying so is better than leaving them blank.
             "capacity_is_projected": False, "capacity_source": "workbook anchor"}
            for a in anchors for y in years])
        if chemistry in params.technology.chemistry_energy_density:
            capacities["pack_mass_kg_implied"] = [
                row.capacity_kwh_nominal * 1000.0
                / generator.pack_density(params, chemistry, float(row.year))
                for row in capacities.itertuples()]
        built = generator.build_unknown_rows(model, params, capacities, chemistry)

        rows = pd.DataFrame({
            "additionalSpecification": built.segment.map(
                lambda s: f"BATTinELV_BEV_{s}"),
            "Layer 1": built["layer1"],
            "Layer 2": built["component"],
            "Layer 4": built["element"].fillna("n/a"),
            "parameterCode": built["level"].map(
                {level: getattr(params.scope, attribute)
                 for level, attribute in LEVEL_CODES.items()}),
            "UoM": "kg",
            "DQS": pd.NA,                      # nothing was measured, so no score
            "productionYear": built["year"],
            "capacity_kwh": built["capacity_kwh_nominal"],
            "Value": built["mass_kg"],
            "min_value": built.get("mass_p2.5"),
            "max_value": built.get("mass_p97.5"),
            "count_value": pd.NA,
            "meanValue": built.get("mass_mean"),
            "medianValue": built.get("mass_median"),
            "modeValue": built.get("mass_mode"),
            "STD": built.get("mass_std"),
            "p025": built.get("mass_p2.5"),
            "p975": built.get("mass_p97.5"),
        })[WORKBOOK_COLUMNS + ADDED_COLUMNS]
        path = directory / f"consolidated_{chemistry}.csv"
        rows.to_csv(path, index=False)
        filled = int(rows["Value"].notna().sum())
        print(f"  {chemistry:20s} {len(rows):>7,} rows -> {path.name}"
              f"   ({100 * filled / len(rows):.0f}% with a mass)")

    print(f"\nWritten to {params.export.consolidated_output_dir}/, "
          f"one file per chemistry with its draw arrays beside it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
