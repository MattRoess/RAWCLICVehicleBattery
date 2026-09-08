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

⚠️ SODIUM-ION AND SOLID-STATE ARE WRITTEN, AND MARKED. They have no composition
in the workbook, so their files carry the expected ROW SKELETON with every mass
left EMPTY and `composition_status = "unknown"`. Nothing is substituted from a
lookalike chemistry. A file of blanks is harder to overlook downstream than a
missing file, and the stock-and-flow model can carry the chemistry through and
see the gap arrive rather than silently dropping that share of the fleet.

The skeleton itself is a structural assumption, set in
`export.unknown_chemistry_template`, and it is the only thing asserted about
those two: sodium swaps aluminium for copper on the anode current collector;
bipolar solid-state has no separator, no liquid electrolyte and no per-cell
terminals, and an anode of lithium or sodium metal rather than graphite.
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
                rows.append({"segment": segment, "year": year,
                             "capacity_kwh_nominal": round(float(value), 2),
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
                projected = True
            capacity = float(np.clip(capacity, params.interpolation.min_capacity_kwh,
                                     export.max_projected_capacity_kwh))
            rows.append({"segment": segment, "year": year,
                         "capacity_kwh_nominal": round(capacity, 2),
                         "capacity_is_projected": projected,
                         "capacity_source": "fitted"})
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
            table["capacity_source"] = entry.capacity_source
            frames.append(table)

    rows = pd.concat(frames, ignore_index=True)
    rows = rows.rename(columns={"capacity_kwh": "capacity_kwh_nominal",
                                "chemistry": "layer1"})
    keep = ["segment", "year", "level", "layer1", "branch", "component", "element",
            "capacity_kwh_nominal", "capacity_is_projected", "capacity_source",
            "mass_kg", "kg_per_kwh", "extrapolated"]
    if export.include_uncertainty:
        keep += [c for c in rows.columns if c.startswith("mass_p") or c == "mass_mean"]
    rows["chemistry"] = chemistry
    rows["composition_status"] = "from_workbook"
    rows["note"] = ""
    rows["material"] = pd.NA
    keep = keep + ["material", "composition_status", "note"]
    rows = rows[["chemistry"] + [c for c in keep if c in rows.columns]]
    return apply_material_overrides(rows, params)


def apply_material_overrides(rows: pd.DataFrame, params) -> pd.DataFrame:
    """
    Name the materials the workbook leaves unnamed, at material level.

    The workbook resolves batteryCellCasing at 'm-c' with no Layer 3 column, so
    the row has a mass and no material. Where the split is known the mass is
    divided; where only the materials are known the mass is dropped and the row
    marked -- naming a material is not the same as knowing how much of it there
    is, and writing the component's whole mass against one of them would be a
    silent invention.
    """
    overrides = params.export.component_material_overrides
    if not overrides:
        return rows

    material_rows = rows.level == "material"
    keep, expanded = rows[~material_rows], []
    for row in rows[material_rows].to_dict("records"):
        materials = overrides.get(row["component"])
        if not materials:
            expanded.append(row)
            continue
        known_split = all(share is not None for share in materials.values())
        for material, share in materials.items():
            new = dict(row)
            new["material"] = material
            if known_split:
                for column in [c for c in new if c.startswith("mass_") or c == "kg_per_kwh"]:
                    if pd.notna(new[column]):
                        new[column] = new[column] * share
            else:
                for column in [c for c in new if c.startswith("mass_") or c == "kg_per_kwh"]:
                    new[column] = pd.NA
                if new["composition_status"] == "from_workbook":
                    new["composition_status"] = "material_known_split_unknown"
                    new["note"] = (f"{'/'.join(materials)} — the workbook gives this "
                                   "component's mass but never names its materials, and "
                                   "the split between them is not known")
            expanded.append(new)
    return pd.concat([keep, pd.DataFrame(expanded)], ignore_index=True) if expanded else keep


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


def range_saturated_capacities(params, ev: EVDetails, capacities: pd.DataFrame,
                               chemistry: str) -> pd.DataFrame:
    """
    Capacity set by a range target rather than by the segment's history.

    Once energy density stops binding there is no reason to carry range nobody
    drives, so the pack is sized for `technology.range_saturation_km` and the
    remaining density gain shows up as less mass. The capacity is the input; the
    mass saving is what falls out of it.
    """
    tech = params.technology
    consumption = segment_consumption(params, ev)
    density = tech.chemistry_pack_wh_per_kg[chemistry]

    out = capacities.copy()
    wh_per_km = out.segment.map(consumption)
    unknown = sorted(out.loc[wh_per_km.isna(), "segment"].unique())
    if unknown:
        print(f"[export] no consumption figure for {unknown} -- those segments keep "
              "their historical capacity.")
    saturated = wh_per_km * tech.range_saturation_km / 1000.0
    # NOT capped by export.max_projected_capacity_kwh. That ceiling exists to
    # keep a projected capacity inside the composition model's answerable range;
    # this chemistry's composition is never computed, so clipping here would only
    # fail to meet the range target while making the mass saving look better than
    # the assumption gives.
    out["capacity_kwh_nominal"] = saturated.fillna(out.capacity_kwh_nominal).round(2)
    out["capacity_is_projected"] = True
    out["pack_mass_kg_implied"] = (out.capacity_kwh_nominal * 1000.0 / density).round(1)
    out["wh_per_km"] = wh_per_km
    return out


def build_unknown_rows(model: CompositionModel, params, capacities: pd.DataFrame,
                       chemistry: str) -> pd.DataFrame:
    """
    The row skeleton for a chemistry with no composition: right shape, no numbers.

    Every mass column is left empty on purpose. The point is that a downstream
    reader gets a row it cannot mistake for data and cannot silently skip --
    not that it gets a plausible-looking guess.
    """
    template = params.export.unknown_chemistry_template[chemistry]
    base = template["based_on"]
    implied = capacities.set_index(["segment", "year"])["pack_mass_kg_implied"] \
        if "pack_mass_kg_implied" in capacities.columns else None

    # Build the skeleton at a capacity the composition model will answer for.
    # Only the component and element STRUCTURE is taken from it -- every mass is
    # wiped below -- so the base chemistry's answerable range must not constrain
    # a range target for a chemistry whose composition is not computed at all.
    real_capacities = capacities.set_index(["segment", "year"])["capacity_kwh_nominal"]
    capacities = capacities.copy()
    capacities["capacity_kwh_nominal"] = capacities.capacity_kwh_nominal.clip(
        params.interpolation.min_capacity_kwh, params.interpolation.max_capacity_kwh)
    removed = set(template["remove_components"])
    swaps = dict(template["element_swaps"])

    rows = build_rows(model, params, capacities, base)
    rows = rows[~rows.component.isin(removed)].copy()

    for component, mapping in swaps.items():
        # Scoped to one component. A blanket swap would recolour every copper in
        # the pack, cables included, when only the anode collector changes.
        target = rows.component == component
        rows.loc[target, "element"] = rows.loc[target, "element"].replace(mapping)

    # Borrowing a component list is not the same as knowing what the cathode is
    # made of. Outside the components the template is willing to claim, the
    # element is written 'unknown' rather than left showing the base
    # chemistry's -- a row reading 'Fe' for a sodium cathode would be a claim
    # nobody made, empty mass or not.
    asserted = set(template["assert_elements_for"])
    unclaimed = rows.element.notna() & ~rows.component.isin(asserted)
    rows.loc[unclaimed, "element"] = "unknown"

    # A swap can collapse two element rows into one (LFP's Al and Cu terminals
    # both become Al). With no masses to add up, the duplicate is just noise.
    rows = rows.drop_duplicates(
        subset=["segment", "year", "level", "component", "element"]).copy()

    rows["chemistry"] = chemistry
    rows["layer1"] = chemistry
    rows["composition_status"] = "unknown"
    rows["note"] = template["note"]

    # Wipe every number. Capacity and structure survive; nothing quantitative does.
    for column in [c for c in rows.columns
                   if c.startswith("mass_") or c == "kg_per_kwh"]:
        rows[column] = pd.NA

    # Put the real capacity back, whatever the base chemistry could answer for.
    rows["capacity_kwh_nominal"] = pd.MultiIndex.from_frame(
        rows[["segment", "year"]]).map(real_capacities)

    if implied is not None:
        # The WHOLE PACK's mass follows from the assumed energy density and the
        # capacity, so it can be stated even though no component's mass can. It
        # is the same for every row of a segment-year and is not a composition.
        rows["pack_mass_kg_implied"] = pd.MultiIndex.from_frame(
            rows[["segment", "year"]]).map(implied)
        density = params.technology.chemistry_pack_wh_per_kg[chemistry]
        rows["note"] = rows["note"] + (
            f"; pack mass implied by {density:g} Wh/kg at a "
            f"{params.technology.range_saturation_km:g} km range target — a whole-pack "
            "figure, not a composition")
    return rows


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
    missing = list(params.scenarios.chemistries_without_composition)

    print(f"Export years: {params.export_years()}")
    print(f"Segments    : {sorted(capacities.segment.unique())}")
    print(f"Capacity    : fitted to {LAST_OBSERVED_YEAR}, then "
          f"'{export.capacity_projection}', capped at {export.max_projected_capacity_kwh:g} kWh")
    print(f"Chemistries : {len(chemistries)} with composition -- {chemistries}")
    if export.write_unknown_chemistries:
        print(f"              {len(missing)} marked unknown -- {missing}: row skeleton "
              "only, every mass left empty.")
    else:
        print(f"NOT written : {missing} (export.write_unknown_chemistries is off).")

    written = []
    to_write = [(c, False) for c in chemistries]
    if export.write_unknown_chemistries:
        to_write += [(c, True) for c in missing]

    reference_mass = None
    for chemistry, unknown in to_write:
        chemistry_capacities = capacities
        if unknown and params.technology.apply_range_saturation \
                and chemistry in params.technology.chemistry_pack_wh_per_kg:
            chemistry_capacities = range_saturated_capacities(params, ev, capacities,
                                                              chemistry)
            if reference_mass is None:
                reference = params.technology.reference_chemistry
                reference_mass = {
                    entry.segment: model.weights_at(entry.capacity_kwh_nominal,
                                                    chemistry=reference)["mass_kg"].sum()
                    for entry in capacities[capacities.year == capacities.year.max()]
                    .itertuples()}
            latest = chemistry_capacities[
                chemistry_capacities.year == chemistry_capacities.year.max()]
            print(f"\n  {chemistry}: capacity set by a "
                  f"{params.technology.range_saturation_km:g} km range target at "
                  f"{params.technology.chemistry_pack_wh_per_kg[chemistry]:g} Wh/kg pack")
            for entry in latest.itertuples():
                today = reference_mass.get(entry.segment)
                ratio = f"{entry.pack_mass_kg_implied / today:.2f}x" if today else "n/a"
                print(f"      {entry.segment:<3} {entry.wh_per_km:5.0f} Wh/km -> "
                      f"{entry.capacity_kwh_nominal:6.1f} kWh, "
                      f"{entry.pack_mass_kg_implied:6.1f} kg  ({ratio} today's "
                      f"{today:.0f} kg)" if today else "")
        rows = (build_unknown_rows(model, params, chemistry_capacities, chemistry) if unknown
                else build_rows(model, params, chemistry_capacities, chemistry))
        name = f"composition_{chemistry}.{export.export_format}"
        path = params.composition_output_path(PROJECT_ROOT, name)
        if export.export_format == "csv":
            rows.to_csv(path, index=False)
        else:
            rows.to_excel(path, index=False, sheet_name="composition")
        written.append((path, len(rows)))
        flag = "  << UNKNOWN, masses empty" if unknown else ""
        print(f"  {path.name:<44} {len(rows):>7,} rows{flag}")

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
