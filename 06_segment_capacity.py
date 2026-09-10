"""
06_segment_capacity.py
======================

Battery capacity per car segment, and the composition files keyed on it.

    ./.venv/bin/python 00_parameters.py         # first, always
    ./.venv/bin/python 06_segment_capacity.py

⚠️ THIS IS A FLEET QUESTION, AND THE FLEET IS NOT THIS PROJECT'S SUBJECT.
How big a battery a given segment carries in a given year depends on how many
cars of what size exist and when -- which RAWCLICStockAndFlow knows and this
project does not. `05_composition.py` answers the narrower question it can
actually answer: what is inside a battery of capacity X in year Y at voltage V,
at the workbook's own anchors, with the draws beside it so the consumer can
interpolate.

This file is what was cut out of `05` on 2026-09-10. It is kept, and kept
runnable, because the reasoning in it is worth keeping and the decision may be
revisited -- not because anything downstream needs its output. Nothing in `05`
imports from here; the dependency runs the other way.

WHAT IT PRODUCES
----------------
- `capacity_by_segment_year.csv`, and the same table printed
- `segment_composition_<chemistry>.csv`, one per chemistry, keyed on
  (segment, year) rather than on the capacity anchors. Named apart from `05`'s
  own output so the two can never be mistaken for each other

WHAT IS KNOWN TO BE WRONG WITH IT
---------------------------------
Both defects are why the segment path stopped being the deliverable:

1. **The capacity curve is fitted over seven observed years and projected over
   forty-four.** The per-segment slopes run -2.5 to +2.4 kWh/yr with no
   consistent sign, and the fit disagrees with the measurement it is fitted to:
   segment C measured 62.0 kWh in 2020 and the fit says 50.6, ramping straight
   through six flat years. A fleet median also moves when the MODEL MIX changes,
   not only when batteries change, so its slope is not a technology trend.

2. **The range target fires for two chemistries and not the other seven.**
   `range_saturated_capacities` is applied only where a chemistry has no
   workbook composition, and the line that sets it has no year in it, so sodium
   and solid-state hold ONE capacity for every year 2020-2070 -- 86.4 kWh in
   segment C, against that segment's own 50.6 kWh in 2020. They are also deaf
   to `export.capacity_scenario` as a result. If this path is ever revived, the
   range target must apply to all nine chemistries or to none.
"""

from __future__ import annotations

import importlib
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

# The row builders and the pack rules live in 05 because they are the
# composition, which is that file's subject. Imported rather than duplicated:
# two copies of build_rows drifting apart is exactly the failure this project
# has already had three times. The module name starts with a digit, so it
# cannot be imported with the `import` statement.
_composition = importlib.import_module("05_composition")
apply_pack_rules = _composition.apply_pack_rules
build_rows = _composition.build_rows
build_unknown_rows = _composition.build_unknown_rows
improvement_factor = _composition.improvement_factor

LAST_OBSERVED_YEAR = _composition.LAST_OBSERVED_YEAR


def capacity_growth_factor(params, segment: str, year: float, base_year: float) -> float:
    """
    Multiplier on a PROJECTED capacity under the grow_* scenarios.

    The chemistry cost saving (NMC -> LFP -> sodium) can be taken as a cheaper
    car or as a bigger battery. Through 2026 it went to price: across 717 A-D
    models, at equal capacity and segment an LFP car is 17.7% cheaper, and at
    equal price it carries only 2.0% +/- 1.8 pp more kWh. The grow_* scenarios
    assume part of it turns into capacity instead, and only where price
    competition is the binding constraint -- A-D, not E/F, which run at
    1256 EUR/kWh against 625-790 and are not price-constrained at all.
    Compounded per decade, from the segment's last fitted year.
    """
    export = params.export
    if export.capacity_scenario == "saturate":
        return 1.0
    if segment not in export.capacity_growth_segments:
        return 1.0
    rate = export.capacity_growth_per_decade[export.capacity_scenario]
    decades = max(0.0, (float(year) - float(base_year)) / 10.0)
    return float((1.0 + rate) ** decades)


def segment_capacities(params, ev: EVDetails, segments: list[str]) -> pd.DataFrame:
    """Nominal capacity per segment per export year, marked observed or projected."""
    export = params.export
    years = params.export_years()
    rows = []

    for segment in segments:
        fitted = pd.Series(dtype=float)
        try:
            curve = ev.curve(segment)
            fitted = pd.Series(curve.central, index=curve.years.astype(int)).dropna()
        except EVDetailsError:
            pass

        if fitted.empty:
            # Too thin to fit a curve, but the segment still has to be exported:
            # all twelve appear in the stock-and-flow model whatever the EV
            # database knows about them.
            own = ev.models.loc[ev.models.segment == segment, "capacity_kwh"].dropna()
            if params.ev_details.capacity_fallback == "segment_median" and len(own):
                value, source = float(own.median()), "segment_median"
                print(f"[export] segment {segment}: too few models to fit a curve "
                      f"({len(own)}); using their median, {value:.1f} kWh.")
            else:
                value = params.ev_details.reference_battery_size_map.get(segment)
                source = "reference_map"
                if value is None:
                    print(f"[export] segment {segment}: no models and no map entry "
                          "-- skipped.")
                    continue
                print(f"[export] segment {segment}: no usable models; using "
                      f"battery_size_map, {value:g} kWh.")
            for year in years:
                # No fit, so there is no segment-specific last observed year:
                # grow from the year the database itself ends.
                grown = value * capacity_growth_factor(params, segment, year,
                                                       LAST_OBSERVED_YEAR)
                rows.append({"segment": segment, "year": year,
                             "capacity_kwh_nominal": round(float(grown), 2),
                             "capacity_is_projected": True,
                             "capacity_source": source})
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
                capacity *= capacity_growth_factor(params, segment, year, last_year)
                projected = True
            capacity = float(np.clip(capacity, params.interpolation.min_capacity_kwh,
                                     export.max_projected_capacity_kwh))
            rows.append({"segment": segment, "year": year,
                         "capacity_kwh_nominal": round(capacity, 2),
                         "capacity_is_projected": projected,
                         "capacity_source": "fitted"})
    return pd.DataFrame(rows)


def segment_consumption(params, ev: EVDetails) -> pd.Series:
    """Real-world Wh/km per segment: the parameter if set, else the file."""
    tech = params.technology
    if tech.segment_consumption_wh_per_km:
        return pd.Series(tech.segment_consumption_wh_per_km, dtype=float)

    raw = pd.read_csv(params.ev_details_path(PROJECT_ROOT), low_memory=False)
    column = "real-consumption_combined_mild_weather"   # values look like '157 Wh/km'
    if column not in raw.columns:
        raise EVDetailsError(
            f"{column!r} is not in EV_details.csv, so a range target cannot be turned "
            "into a capacity. Set technology.segment_consumption_wh_per_km instead.")
    consumption = raw[["car_id", column]].copy()
    consumption["wh_per_km"] = consumption[column].map(
        lambda value: float(pd.Series([value]).str.extract(r"([\d.]+)")[0].iloc[0])
        if pd.notna(value) else float("nan"))
    merged = ev.models.merge(consumption[["car_id", "wh_per_km"]], on="car_id", how="left")
    recent = merged[merged.first_year >= tech.consumption_from_year]
    return recent.groupby("segment")["wh_per_km"].median().dropna()


def pack_density(params, chemistry: str, year: float) -> float:
    """
    Pack Wh/kg for a chemistry in a given year, from its density trajectory.

    Two conversions in one place: the trajectory may be quoted on a CELL basis,
    in which case it is multiplied by that chemistry's cell-to-pack ratio, and
    it is interpolated between the trajectory's own years.
    """
    entry = params.technology.chemistry_energy_density[chemistry]
    value = float(np.interp(float(year),
                            np.asarray(entry["years"], dtype=float),
                            np.asarray(entry["wh_per_kg"], dtype=float)))
    if entry["basis"] == "cell":
        value *= float(params.technology.cell_to_pack_ratio[chemistry])
    return value


def range_saturated_capacities(params, ev: EVDetails, capacities: pd.DataFrame,
                               chemistry: str) -> pd.DataFrame:
    """
    Capacity set by a range target rather than by the segment's history.

    ⚠️ TWO DEFECTS, BOTH KNOWN. It is applied only to the chemistries with no
    workbook composition, which makes those two incomparable with the other
    seven; and `wh_per_km` is a single per-segment median with no year in it,
    so the capacity it returns is the SAME in every year from 2020 to 2070.
    See this module's docstring. Kept as written so the defect is visible
    rather than quietly repaired into something nobody chose.
    """
    tech = params.technology
    consumption = segment_consumption(params, ev)

    out = capacities.copy()
    out["pack_wh_per_kg"] = out.year.map(
        lambda year: pack_density(params, chemistry, year))
    wh_per_km = out.segment.map(consumption)
    unknown = sorted(out.loc[wh_per_km.isna(), "segment"].unique())
    if unknown:
        print(f"[export] no consumption figure for {unknown} -- those segments keep "
              "their historical capacity.")
    saturated = wh_per_km * tech.range_saturation_km / 1000.0
    # NOT capped by export.max_projected_capacity_kwh. That ceiling exists to
    # keep a projected capacity inside the composition model's answerable range;
    # this chemistry's composition is never computed, so clipping here would only
    # fail to meet the range target.
    out["capacity_kwh_nominal"] = saturated.fillna(out.capacity_kwh_nominal).round(2)
    out["capacity_is_projected"] = True
    out["pack_mass_kg_implied"] = (out.capacity_kwh_nominal * 1000.0
                                   / out.pack_wh_per_kg).round(1)
    out["wh_per_km"] = wh_per_km
    return out


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
        ev = EVDetails(params, project_root=PROJECT_ROOT)
        capacities = segment_capacities(params, ev, segments)
    except (CompositionError, EVDetailsError) as error:
        print(f"{error}", file=sys.stderr)
        return 1

    if capacities.empty:
        print("No segment produced a capacity series -- nothing to export.",
              file=sys.stderr)
        return 1

    chemistries = sorted(set(model._series.keys.chemistry) - {params.scope.pack_level_key})
    missing = list(params.scenarios.chemistries_without_composition)

    print(f"Export years: {params.export_years()}")
    print(f"Segments    : {sorted(capacities.segment.unique())}")
    print(f"Capacity    : fitted to {LAST_OBSERVED_YEAR}, then "
          f"'{export.capacity_projection}', capped at "
          f"{export.max_projected_capacity_kwh:g} kWh")
    print(f"Chemistries : {len(chemistries)} with composition -- {chemistries}")

    to_write = [(c, False) for c in chemistries]
    if export.write_unknown_chemistries:
        to_write += [(c, True) for c in missing]

    written = []
    for chemistry, unknown in to_write:
        chemistry_capacities = capacities
        if unknown and params.technology.apply_range_saturation \
                and chemistry in params.technology.chemistry_energy_density:
            chemistry_capacities = range_saturated_capacities(
                params, ev, capacities, chemistry)
            entry = params.technology.chemistry_energy_density[chemistry]
            trajectory = ", ".join(
                f"{year}: {pack_density(params, chemistry, year):.0f}"
                for year in entry["years"])
            print(f"\n  {chemistry}: capacity from a "
                  f"{params.technology.range_saturation_km:g} km range target; "
                  f"density {entry['basis']} basis"
                  + (f" x {params.technology.cell_to_pack_ratio[chemistry]:.2f} packing"
                     if entry["basis"] == "cell" else "")
                  + f" -> pack Wh/kg by year [{trajectory}]")

        rows = (build_unknown_rows(model, params, chemistry_capacities, chemistry)
                if unknown
                else build_rows(model, params, chemistry_capacities, chemistry))
        rows = apply_pack_rules(rows, params, chemistry)
        name = f"segment_composition_{chemistry}.{export.export_format}"
        path = params.composition_output_path(PROJECT_ROOT, name)
        if export.export_format == "csv":
            rows.to_csv(path, index=False)
        else:
            rows.to_excel(path, index=False, sheet_name="composition")
        written.append(path)
        flag = "  << UNKNOWN, masses empty" if unknown else ""
        print(f"  {path.name:<48} {len(rows):>7,} rows{flag}")

    index = capacities.pivot_table(index="segment", columns="year",
                                   values="capacity_kwh_nominal")
    index_path = params.composition_output_path(
        PROJECT_ROOT, f"capacity_by_segment_year.{export.export_format}")
    (capacities.to_csv(index_path, index=False) if export.export_format == "csv"
     else capacities.to_excel(index_path, index=False))
    print(f"\nNominal capacity per car [kWh] (everything beyond "
          f"{LAST_OBSERVED_YEAR} is projected):")
    print(index.round(1).to_string())
    print(f"\nWrote {index_path.name} and {len(written)} segment composition files "
          f"to {export.composition_output_dir}/")
    print("\n⚠️ These are FLEET numbers. RAWCLICStockAndFlow decides the capacity "
          "per segment per year;\n   this file only shows what this project would "
          "have guessed. See the module docstring for\n   the two known defects "
          "before using any of it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
