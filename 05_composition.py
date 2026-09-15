"""
05_composition.py
=================

The whole composition step, in one file: the segment-year files, the
consolidated files in the workbook's own schema, the per-draw arrays, and every
figure that draws them.

    ./.venv/bin/python 00_parameters.py     # first, always
    ./.venv/bin/python 05_composition.py

WHY ONE FILE. This was four scripts. They built the SAME Monte Carlo twice --
once for the segment-year files, once for the consolidated ones -- and passed
results between themselves through the filesystem, one of them reaching into
another with spec_from_file_location on a literal filename, a reference no
linter can check and one that broke silently when the scripts were renumbered.
The model is now built once and everything downstream reads it in memory.

WHAT IT WRITES

  data/composition/            one file per chemistry, per SEGMENT and year,
                               plus element_draws/ at the capacity anchors
  data/consolidated/           one file per chemistry in the input workbook's
                               own schema, per capacity ANCHOR and year, with
                               its draw arrays beside it -- the deliverable
  figures/                     composition over time per chemistry, one figure
                               per critical raw material, and the distributions

⚠️ NOMINAL, NOT USEABLE. The workbook's kg/kWh is per nominal kWh. Useable runs
about 5% lower and would understate every mass by that much.

⚠️ 'element' DOES NOT SUM TO 'component'. batteryCellCasing and
batteryCellSeparator have no element rows in the workbook -- about 8% of pack
mass. Both levels are written so the gap is visible rather than inferred.

⚠️ SODIUM-ION AND SOLID-STATE have no composition in the workbook. Only their
PACKAGING is claimed; the cathode, anode and electrolyte are written as
unknownBatteryMaterial. What may be claimed about them, and why, is in
`export.unknown_chemistry_template`.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from typing import NamedTuple

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.composition import (CompositionError, CompositionModel,  # noqa: E402
                             approximate_mode)
from src.params_schema import ParameterError, current  # noqa: E402

LAST_OBSERVED_YEAR = 2026

# What the cathode, anode and electrolyte of an unknown chemistry are called.
# A named material, not a blank: a reader scanning the element column sees that
# something belongs there and is not yet known, which an empty cell does not say.
# The consolidated workbook uses 'undefinedElements' for the same idea.
UNKNOWN_MATERIAL = "unknownBatteryMaterial"


_IMPROVEMENT_DRAWS: np.ndarray | None = None


def improvement_draws(params) -> np.ndarray:
    """
    One drawn 2070 improvement per Monte Carlo draw, shape (n_draws,).

    ⚠️ DRAWN ONCE AND CACHED. This is a single uncertainty about the
    technology, not an independent error per component: the same draw has to
    mean the same improvement everywhere, or summing rows would cancel it and
    the total would come out falsely certain. Same reasoning as the workbook's
    own factor_draws.
    """
    global _IMPROVEMENT_DRAWS
    if _IMPROVEMENT_DRAWS is not None:
        return _IMPROVEMENT_DRAWS
    band = params.technology.mass_improvement_2070
    mc = params.monte_carlo
    rng = np.random.default_rng(mc.random_seed + 1)      # +1: not the workbook's stream
    _IMPROVEMENT_DRAWS = rng.triangular(
        float(band["min"]), float(band["mode"]), float(band["max"]), size=mc.n_draws)
    return _IMPROVEMENT_DRAWS


def improvement_share(params, year: float) -> float:
    """How far along the improvement a year is: 0 at the start, 1 at the end."""
    tech = params.technology
    first, last = float(tech.improvement_from_year), float(tech.improvement_to_year)
    return float(np.clip((float(year) - first) / (last - first), 0.0, 1.0))


def improvement_factor(params, year: float) -> float:
    """Central mass multiplier for a year -- the mode of the distribution."""
    return 1.0 - improvement_share(params, year) * float(
        params.technology.mass_improvement_2070["mode"])


def improvement_factor_draws(params, year: float) -> np.ndarray | None:
    """Per-draw mass multiplier for a year, or None when the MC is off."""
    if not params.monte_carlo.enabled:
        return None
    return 1.0 - improvement_share(params, year) * improvement_draws(params)


def scale_element_masses(rows: pd.DataFrame, by_component: dict, mass_columns) -> None:
    """
    Multiply one element's mass inside one component, IN PLACE, and carry the
    change up to that component's own rows.

    The component and material rows have no element, so an element-keyed factor
    misses them entirely -- which is how currentCollectorAnode once read 29.7 kg
    at component level against 14.2 kg summed over its elements. They take the
    mass-weighted factor of the element rows beneath them instead.
    """
    element_level = rows.level == "element"
    for component, by_element in by_component.items():
        at_component = rows.component == component
        parts = rows.loc[at_component & element_level]
        if parts.empty:
            continue
        weighted = {}
        for key, group in parts.groupby(["segment", "year"], dropna=False):
            total = pd.to_numeric(group.mass_kg, errors="coerce").sum()
            if not total:
                continue
            moved = sum(pd.to_numeric(
                group.loc[group.element == element, "mass_kg"], errors="coerce").sum()
                for element in by_element)
            scaled = sum(pd.to_numeric(
                group.loc[group.element == element, "mass_kg"], errors="coerce").sum()
                * factor for element, factor in by_element.items())
            weighted[key] = (scaled + (total - moved)) / total

        for element, factor in by_element.items():
            target = at_component & (rows.element == element)
            for column in mass_columns:
                rows.loc[target, column] = pd.to_numeric(
                    rows.loc[target, column], errors="coerce") * factor

        if weighted:
            whole = at_component & ~element_level
            factors = pd.MultiIndex.from_frame(
                rows.loc[whole, ["segment", "year"]]).map(weighted).to_numpy()
            for column in mass_columns:
                rows.loc[whole, column] = pd.to_numeric(
                    rows.loc[whole, column], errors="coerce") * factors


def split_module_enclosure(rows: pd.DataFrame, params) -> pd.DataFrame:
    """
    Re-split the module enclosure's element rows, leaving its total alone.

    The workbook files the whole enclosure as iron. Module housings and coolant
    manifolds are part aluminium, so the mass is redistributed across the
    elements in `technology.module_enclosure_split`. The component's own mass
    does not move -- only its makeup, which is the part the stock-and-flow
    model consumes.
    """
    split = params.technology.module_enclosure_split
    component = "batteryPackModuleEnclosuresAndCoolantManifolds"
    mass_columns = [c for c in rows.columns
                    if c.startswith("mass_") or c == "kg_per_kwh"]
    source = rows[(rows.component == component) & (rows.level == "element")]
    if source.empty or not split:
        return rows

    keep = rows.drop(index=source.index)
    pieces = []
    for element, share in split.items():
        piece = source.copy()
        # Every element row of the component is pooled and re-divided, so the
        # split holds whatever the workbook happened to file it under.
        for column in mass_columns:
            piece[column] = pd.to_numeric(piece[column], errors="coerce") * float(share)
        piece["element"] = element
        pieces.append(piece)
    out = pd.concat([keep] + pieces, ignore_index=True)
    return out.groupby(
        [c for c in out.columns if c not in mass_columns],
        dropna=False, as_index=False, sort=False)[mass_columns].sum()


def cell_mass_ratio(params, chemistry: str) -> float:
    """
    Cell mass of this chemistry against the reference, at any capacity.

    Capacity cancels: cells = kWh / (Wh/kg), so the ratio is just the inverse
    ratio of the two cell energy densities. Both are taken in the base year, so
    the structure ratio is a property of the chemistry and does not drift as
    the cells improve -- the improvement already shrinks the whole pack through
    the improvement already shrinks the whole pack, and applying it twice
    would double-count it.
    """
    tech = params.technology
    reference = tech.structure_reference_chemistry
    densities = tech.chemistry_energy_density
    if chemistry not in densities or reference not in densities:
        return 1.0
    here = float(densities[chemistry]["wh_per_kg"][0])
    there = float(densities[reference]["wh_per_kg"][0])
    if not here:
        return 1.0
    return there / here


def scale_structure(rows: pd.DataFrame, params, chemistry: str) -> pd.DataFrame:
    """
    Scale the pack IRON by the mass of cells it carries. Aluminium is untouched.

    The frame and the module box hold the cells up; a lighter cell stack needs
    less of them. The heat exchanger does not follow weight -- the heat to be
    moved is set by the capacity -- so its aluminium is deliberately excluded,
    including the aluminium half of the module enclosure.
    """
    tech = params.technology
    if not tech.structure_scales_with_cell_mass:
        return rows
    factor = cell_mass_ratio(params, chemistry)
    if factor == 1.0:
        return rows
    mass_columns = [c for c in rows.columns
                    if c.startswith("mass_") or c == "kg_per_kwh"]
    scale_element_masses(
        rows, {component: {"Fe": factor} for component in tech.structure_iron_components},
        mass_columns)
    return rows


def with_pack_voltages(rows: pd.DataFrame, params) -> pd.DataFrame:
    """
    One copy of every row per pack voltage, tagged in `voltage_v`.

    The same power at double the voltage is half the current, so the conductors
    sized by current carry half the copper. Nothing else in the pack knows the
    voltage: the frame, the heat exchanger and the cell materials are untouched.
    """
    tech = params.technology
    mass_columns = [c for c in rows.columns
                    if c.startswith("mass_") or c == "kg_per_kwh"]
    out = []
    for voltage in tech.pack_voltages_v:
        factor = float(tech.copper_scale_by_voltage[voltage])
        copy = rows.copy()
        if factor != 1.0:
            scale_element_masses(
                copy,
                {component: {"Cu": factor}
                 for component in tech.voltage_scaled_copper_components},
                mass_columns)
        copy["voltage_v"] = voltage
        out.append(copy)
    return pd.concat(out, ignore_index=True)


# The consolidated files carry the WORKBOOK's column names, not the internal
# ones. Mapping rather than a second implementation: the pack rules bypassed
# this output entirely until 2026-09-10, so solid-state's frame read 88.5 kg
# here against 52 kg in the segment-year files -- the same drift that had hit
# the figures earlier the same day.
WORKBOOK_MASS_COLUMNS = {
    "Value": "mass_kg", "min_value": "mass_min", "max_value": "mass_max",
    "meanValue": "mass_mean", "medianValue": "mass_median",
    "modeValue": "mass_mode", "STD": "mass_std",
    "p025": "mass_p2.5", "p975": "mass_p97.5",
}


def apply_pack_rules_to_workbook(frame: pd.DataFrame, params, chemistry: str
                                 ) -> pd.DataFrame:
    """
    `apply_pack_rules` on workbook-shaped rows, via a renamed view.

    Layer 2 is the component, Layer 4 the element, and the level comes from the
    parameterCode. `additionalSpecification` stands in for the segment, which is
    what the weighting groups on -- these rows are per capacity anchor, not per
    segment, and each anchor must be weighted on its own.
    """
    scope = params.scope
    level_of = {getattr(scope, attribute): level
                for level, attribute in LEVEL_CODES.items()}
    present = {old: new for old, new in WORKBOOK_MASS_COLUMNS.items()
               if old in frame.columns}

    work = frame.rename(columns={"Layer 2": "component", "Layer 4": "element",
                                 **present})
    work["level"] = work["parameterCode"].map(level_of)
    work["segment"] = work["additionalSpecification"]
    work["year"] = 0                       # one anchor, one group; the real year
                                           # is applied after, per year
    work = apply_pack_rules(work, params, chemistry)

    back = {new: old for old, new in present.items()}
    work = work.drop(columns=["level", "segment", "year"])
    return work.rename(columns={"component": "Layer 2", "element": "Layer 4",
                                **back})


def build_rows(model: CompositionModel, params, capacities: pd.DataFrame,
               chemistry: str) -> pd.DataFrame:
    """Every row of one chemistry's file."""
    export = params.export
    frames = []
    for entry in capacities.itertuples():
        for level in export.export_levels:
            # THE CELLS IMPROVE, SO THE MASS FALLS -- AND BY HOW MUCH IS NOT
            # KNOWN. The workbook's composition is true in
            # technology.improvement_from_year; in any later year the same kWh
            # needs less cell, and less pack hardware around a smaller stack.
            #
            # The improvement is passed as DRAWS, not as a scalar, so the band
            # widens with it instead of merely sliding down: by 2070 the mass
            # is 70% to 85% of the base year, most likely 80%. Handed to
            # weights_at so it multiplies the draws BEFORE any percentile is
            # taken -- scaling a percentile afterwards would keep the band the
            # width it had with the improvement treated as certain.
            table = model.weights_at(
                entry.capacity_kwh_nominal, chemistry=chemistry, level=level,
                year_factor=improvement_factor(params, float(entry.year)),
                year_factor_draws=improvement_factor_draws(params, float(entry.year)))
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
        keep += [c for c in rows.columns
                 if (c.startswith("mass_") and c != "mass_kg") or c == "mass_mean"]
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


_UNKNOWN_SCALE_DRAWS: dict[str, np.ndarray] = {}


def unknown_scale_draws(params, chemistry: str) -> np.ndarray | None:
    """
    How much the inherited packaging is trusted, as draws -- shape (n_draws,).

    ⚠️ DRAWN ONCE PER CHEMISTRY AND CACHED, exactly like `improvement_draws`.
    It is one doubt about one inheritance -- "we took LFP's casing" is not "we
    know the casing" -- not an independent error per row. Drawn per row it would
    cancel in any sum and a pack total would come out falsely certain.
    """
    band = params.technology.unknown_chemistry_mass_scale.get(chemistry)
    if band is None or not params.monte_carlo.enabled:
        return None
    if chemistry in _UNKNOWN_SCALE_DRAWS:
        return _UNKNOWN_SCALE_DRAWS[chemistry]
    mc = params.monte_carlo
    # +2: neither the workbook's stream (+0) nor the improvement's (+1).
    seed = mc.random_seed + 2 + (abs(hash(chemistry)) % 1000)
    rng = np.random.default_rng(seed)
    _UNKNOWN_SCALE_DRAWS[chemistry] = rng.triangular(
        float(band["min"]), float(band["mode"]), float(band["max"]), size=mc.n_draws)
    return _UNKNOWN_SCALE_DRAWS[chemistry]


def unknown_scaled_statistics(model: CompositionModel, params, chemistry: str,
                              capacity: float, year: float) -> pd.DataFrame:
    """
    Statistics for the inherited components, RECOMPUTED FROM DRAWS.

    WHY THIS EXISTS. `build_unknown_rows` makes its numbers by multiplying the
    base chemistry's statistics by deterministic factors, which is exact -- a
    percentile times a constant is that percentile of the scaled variable. The
    packaging-trust factor is NOT a constant, it is a triangular, and a
    percentile times a random number is not a percentile of anything. Applying
    it to the finished statistics would slide the band without widening it: the
    same defect that left the improvement's uncertainty out of these files until
    2026-09-14.

    So the affected rows are rebuilt from the base chemistry's draws, carrying
    the template's deterministic factors, the year's improvement and the trust
    factor, and their statistics are taken from the result.
    """
    template = params.export.unknown_chemistry_template[chemistry]
    scale = unknown_scale_draws(params, chemistry)
    if scale is None:
        return pd.DataFrame()
    in_scope = set(params.technology.unknown_chemistry_scaled_components)

    keys, draws = model.component_element_draws_at(
        capacity, chemistry=template["based_on"], code=None)
    keep = keys.component.isin(in_scope).to_numpy()
    if not keep.any():
        return pd.DataFrame()
    keys = keys[keep].reset_index(drop=True)
    draws = np.asarray(draws, dtype=np.float64)[keep].copy()

    # The template's deterministic factors, keyed on (component, element) as in
    # build_unknown_rows -- the halved collectors, the conductance factor.
    #
    # AND THE COMPONENT AND MATERIAL ROWS TOO, which carry no element to key on.
    # Scaling only what matched left sodium's currentCollectorAnode at 26.7 kg
    # per the component level against 11.9 per the element level: the same part
    # of the same battery disagreeing with itself, which is the defect
    # build_unknown_rows already fixed for the row path. The whole-component
    # rows take the factor their own elements imply, mass-weighted PER DRAW --
    # a collector that is all copper takes the full factor, terminals that are
    # part aluminium already take less.
    element_rows = (keys.code == params.scope.element_parameter_code).to_numpy()
    for component, by_element in template["mass_scale"].items():
        at_component = (keys.component == component).to_numpy()
        elements_here = at_component & element_rows
        if elements_here.any():
            total = draws[elements_here].sum(axis=0)
            scaled_total = np.zeros_like(total)
            for position in np.where(elements_here)[0]:
                factor = float(by_element.get(str(keys.element.iloc[position]), 1.0))
                scaled_total += draws[position] * factor
            with np.errstate(divide="ignore", invalid="ignore"):
                weighted = np.where(total > 0, scaled_total / total, 1.0)
            whole = at_component & ~element_rows
            if whole.any():
                draws[whole] *= weighted[None, :]
        for element, factor in by_element.items():
            target = (at_component & (keys.element == element).to_numpy()
                      & element_rows)
            draws[target] *= float(factor)
    # The swaps rename; they do not scale. Two rows can collapse into one, and
    # they are SUMMED below rather than one being dropped.
    for component, mapping in template["element_swaps"].items():
        target = keys.component == component
        keys.loc[target, "element"] = keys.loc[target, "element"].replace(mapping)

    improvement = improvement_factor_draws(params, float(year))
    if improvement is not None:
        draws *= np.asarray(improvement)[None, :]
    draws *= np.asarray(scale)[None, :]

    grouped = keys.groupby(["code", "component", "element"], dropna=False).indices
    out = []
    mc = params.monte_carlo
    for (code, component, element), positions in grouped.items():
        row = draws[positions].sum(axis=0)
        out.append({
            "code": code, "component": component, "element": element,
            # mass_kg is NOT written here. Value is the central estimate and
            # takes the factor's MODE, exactly as it takes the improvement's;
            # meanValue is the mean of the draws. A skewed triangular makes
            # those different numbers, and the caller multiplies the existing
            # central by the mode rather than having the mean written over it.
            "mass_mean": float(np.mean(row)),
            "mass_median": float(np.median(row)), "mass_std": float(np.std(row)),
            "mass_p2.5": float(np.percentile(row, mc.lower_percentile)),
            "mass_p97.5": float(np.percentile(row, mc.upper_percentile)),
        })
    return pd.DataFrame(out)


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

    # Scale BEFORE the swap, while the row still says which metal it was: the
    # factor is a property of the substitution (copper -> aluminium), so it has
    # to land on the copper rows and not on aluminium that was already there.
    #
    # AND THE COMPONENT ROW TOO. The factor is keyed on (component, element),
    # but a component-level row carries no element -- so scaling only what
    # matched left currentCollectorAnode at 29.7 kg per the component level and
    # 14.2 kg per the element level, the same part of the same battery
    # disagreeing with itself. The component row is scaled by the factor its own
    # elements imply, mass-weighted: a collector that is all copper takes the
    # full factor, terminals that are part aluminium already take less.
    mass_columns = [c for c in rows.columns
                    if c.startswith("mass_") or c == "kg_per_kwh"]
    element_level = rows.level == "element"
    for component, by_element in template["mass_scale"].items():
        at_component = rows.component == component
        parts = rows.loc[at_component & element_level]
        weighted = {}
        for (segment, year), group in parts.groupby(["segment", "year"], dropna=False):
            total = pd.to_numeric(group.mass_kg, errors="coerce").sum()
            if not total:
                continue
            scaled = sum(pd.to_numeric(
                group.loc[group.element == element, "mass_kg"], errors="coerce").sum()
                * factor for element, factor in by_element.items())
            untouched = total - sum(pd.to_numeric(
                group.loc[group.element == element, "mass_kg"], errors="coerce").sum()
                for element in by_element)
            weighted[(segment, year)] = (scaled + untouched) / total

        for element, factor in by_element.items():
            target = at_component & (rows.element == element)
            for column in mass_columns:
                rows.loc[target, column] = pd.to_numeric(
                    rows.loc[target, column], errors="coerce") * factor

        if weighted:
            whole = at_component & ~element_level
            factors = pd.MultiIndex.from_frame(
                rows.loc[whole, ["segment", "year"]]).map(weighted).to_numpy()
            for column in mass_columns:
                rows.loc[whole, column] = pd.to_numeric(
                    rows.loc[whole, column], errors="coerce") * factors

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
    rows.loc[unclaimed, "element"] = UNKNOWN_MATERIAL

    # A swap can collapse two element rows into one -- LFP's terminals are part
    # aluminium and part copper, and for sodium both become aluminium. These now
    # carry masses, so the duplicates are SUMMED. Dropping one, which is what
    # this did while every mass was empty, would silently lose the copper's
    # share: 2.46 kg of aluminium plus 5.38 kg of copper is 5.02 kg of aluminium
    # after scaling, not 2.46.
    group = ["segment", "year", "level", "component", "element"]
    summable = [c for c in mass_columns if c in rows.columns]
    if rows.duplicated(subset=group).any():
        aggregation = {c: "sum" for c in summable}
        aggregation.update({c: "first" for c in rows.columns
                            if c not in summable and c not in group})
        rows = rows.groupby(group, as_index=False, dropna=False).agg(aggregation)

    # ------------------------------------------------------------------
    # The packaging-trust factor, as a DISTRIBUTION. Everything above this
    # point multiplies statistics by constants, which is exact. This factor is
    # a triangular, so the rows it touches have their statistics rebuilt from
    # the draws instead -- see unknown_scaled_statistics for why scaling a
    # percentile by a random number is not a percentile of anything.
    # ------------------------------------------------------------------
    code_to_level = {getattr(params.scope, attribute): level
                     for level, attribute in LEVEL_CODES.items()}
    rebuilt = []
    for (segment, year), group in rows.groupby(["segment", "year"], dropna=False):
        stats = unknown_scaled_statistics(
            model, params, chemistry,
            float(group.capacity_kwh_nominal.iloc[0]), float(year))
        if stats.empty:
            continue
        stats["level"] = stats["code"].map(code_to_level)
        stats["segment"], stats["year"] = segment, year
        rebuilt.append(stats.drop(columns=["code"]))

    if rebuilt:
        replacement = pd.concat(rebuilt, ignore_index=True)
        on = ["segment", "year", "level", "component", "element"]
        replaced = replacement.set_index(on)
        index = pd.MultiIndex.from_frame(rows[on])
        touched = index.isin(replaced.index)
        for column in [c for c in replaced.columns if c in rows.columns]:
            values = index[touched].map(replaced[column])
            rows.loc[touched, column] = np.asarray(values, dtype=float)
        # The central keeps the convention used for every other chemistry: the
        # MODE of the factor, not the mean of the draws.
        mode = float(params.technology.unknown_chemistry_mass_scale[chemistry]["mode"])
        rows.loc[touched, "mass_kg"] = (
            pd.to_numeric(rows.loc[touched, "mass_kg"], errors="coerce") * mode)
        # kg_per_kwh follows the mass it is derived from.
        if "kg_per_kwh" in rows.columns:
            rows.loc[touched, "kg_per_kwh"] = (
                pd.to_numeric(rows.loc[touched, "mass_kg"], errors="coerce")
                / pd.to_numeric(rows.loc[touched, "capacity_kwh_nominal"], errors="coerce"))
        print(f"    [{chemistry}] packaging trust applied to "
              f"{int(touched.sum()):,} rows from draws")

    rows["chemistry"] = chemistry
    rows["layer1"] = chemistry
    rows["note"] = template["note"]

    # The packaging is claimable and the active materials are not, so the two are
    # marked apart rather than the whole file being called one thing. A reader
    # filtering on composition_status gets the claim, not the chemistry's name.
    claimed = set(template["claim_masses_for"])
    is_claimed = rows.component.isin(claimed)
    rows["composition_status"] = np.where(is_claimed, "packaging_from_base", "unknown")

    # NO SCALING. The packaging is the base chemistry's, at its own mass. A
    # sodium pack is built like the LFP pack it is derived from -- same frame,
    # same enclosures, same thermal plate -- so it weighs what that weighs.
    #
    # Two earlier attempts were both wrong. Scaling by the density ratio made
    # sodium's frame 1.55x LFP's, because sodium is less energy dense, giving
    # 343 kg of packaging on a 906 kg pack. Sizing the structure from
    # cell_to_pack_ratio fixed the internal contradiction but left the pack mass
    # itself coming from the density trajectory, which is what made it 906 kg in
    # the first place -- half as heavy again as the LFP pack it is modelled on.

    # Wipe the numbers we are NOT claiming. The cathode, the anode and the
    # electrolyte keep nothing: an empty cell is a reader's cue to go and find
    # the number, where a plausible one borrowed from a lithium chemistry is a
    # claim nobody made.
    for column in mass_columns:
        rows.loc[~is_claimed, column] = pd.NA

    # Put the real capacity back, whatever the base chemistry could answer for.
    rows["capacity_kwh_nominal"] = pd.MultiIndex.from_frame(
        rows[["segment", "year"]]).map(real_capacities)

    # NO REMAINDER. It used to be the base chemistry's pack mass minus the
    # packaging, and called that the active material -- but that pack mass is
    # the base CHEMISTRY's, so the remainder was a claim about how much cathode
    # and anode a sodium cell holds, taken from LFP. Nothing here knows that.
    # Only the four chemistry-independent pack components carry a mass; the rest
    # stays unknownBatteryMaterial with no number attached.

    return rows

# ---------------------------------------------------------------- constants
# The input workbook's own column order for the consolidated export, then what
# this file adds.
WORKBOOK_COLUMNS = ["additionalSpecification", "Layer 1", "Layer 2", "Layer 4",
                    "parameterCode", "UoM", "DQS"]
ADDED_COLUMNS = ["productionYear", "capacity_kwh", "voltage_v", "Value",
                 "min_value", "max_value", "count_value", "meanValue",
                 "medianValue", "modeValue", "STD", "p025", "p975"]
LEVEL_CODES = {"component": "component_parameter_code",
               "material": "material_parameter_code",
               "element": "element_parameter_code"}

# The two chemistries with no composition in the workbook, drawn dashed.
UNKNOWN_COMPOSITION = ("Na_ion", "solid_state")



def rows_for(model: CompositionModel, params, chemistry: str, capacity: float,
             *, year_factor_draws: np.ndarray | None = None,
             year_factor: float = 1.0) -> pd.DataFrame:
    """
    Every level at one anchor, in the workbook's shape, in kg, FOR ONE YEAR.

    The year's improvement is handed to `weights_at` as DRAWS, so it multiplies
    each draw before any percentile is taken. Scaling the finished statistics by
    a single number instead -- which is what this did until 2026-09-14 -- slides
    the band without widening it: the CSV's p025/p975 stayed 15.5% of the
    central in every year while the draws behind them widened to 22.1% by 2070.
    The improvement's own uncertainty was simply absent from the file.

    `year_factor` is the central's multiplier and is deliberately the MODE of
    the improvement, not the mean of the draws. Value is a central estimate and
    meanValue is a mean; at 2070 they differ by 2.1% because the triangular is
    skewed, and that is the distribution being reported rather than an error.
    """
    scope = params.scope
    frames = []
    for level, attribute in LEVEL_CODES.items():
        try:
            table = model.weights_at(capacity, chemistry=chemistry, level=level,
                                     year_factor_draws=year_factor_draws,
                                     year_factor=year_factor)
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



def apply_pack_rules(rows: pd.DataFrame, params, chemistry: str) -> pd.DataFrame:
    """
    The three pack-level rules, in the one order that is correct.

    Split the enclosure FIRST, so only its iron half is available to scale;
    scale the iron by the cell mass it carries; then expand to the pack
    voltages, which only touches copper. Called by the export AND by the
    figures -- they drifted apart once already, with the files carrying rules
    the figures never saw.
    """
    rows = split_module_enclosure(rows, params)
    rows = scale_structure(rows, params, chemistry)
    return with_pack_voltages(rows, params)


class PackDraws(NamedTuple):
    """One voltage's masses at both levels, in kg, (n_rows, n_draws)."""
    elements: list[str]
    element_masses: np.ndarray
    components: list[str]
    component_masses: np.ndarray


def apply_pack_rules_to_draws(keys: pd.DataFrame, draws: np.ndarray, params,
                              chemistry: str) -> dict[int, PackDraws]:
    """
    The three pack rules, on the DRAWS, in the same order as `apply_pack_rules`.

    Returns {voltage: PackDraws} -- the elements, and the COMPONENTS beside
    them. `keys` must come from `component_element_draws_at(..., code=None)`,
    which carries the component rows as well as the element ones.

    WHY BOTH LEVELS. The elements do not add up to the pack: the cell casing and
    the separator have no element rows at all, and the electrolyte's cover 1% of
    its mass. That is 7-11% of the pack, growing with capacity, and it is the
    part a recycler has to deal with rather than sell. Only the component level
    closes the balance.

    WHY THIS EXISTS. `apply_pack_rules` works on DataFrame rows; the draws are
    an array. Until this function the arrays were written straight out of
    `element_draws_at`, which sums to elements before any rule can be applied --
    so the persisted arrays carried none of the three, and disagreed with the
    consolidated CSVs by 9.9 percentage points on iron and 5.8 on aluminium.
    That was the third drift between these two outputs.

    It is a second implementation of the rules, which is a risk this project has
    already been bitten by. `check_draws_match_workbook()` compares the means
    from here against the CSV path's own numbers on every run, at both levels,
    and raises if they part company.
    """
    tech, scope = params.technology, params.scope
    code = keys["code"].to_numpy()
    at_element = code == scope.element_parameter_code
    at_component = code == scope.component_parameter_code

    masses = np.asarray(draws, dtype=np.float64)
    component_names = [str(c) for c in keys["component"].to_numpy()[at_component]]
    component_masses = masses[at_component].copy()
    component = keys["component"].to_numpy()[at_element]
    element = keys["element"].to_numpy()[at_element]
    masses = masses[at_element].copy()

    def carry_up(before: np.ndarray, after: np.ndarray, touched: set,
                 totals: np.ndarray) -> None:
        """
        Move a component's own row by what the rule did to its elements.

        A factor keyed on an element misses the component row entirely, which is
        how currentCollectorAnode once read 29.7 kg at component level against
        14.2 kg summed over its elements. The component takes the mass-weighted
        factor of the elements beneath it -- PER DRAW, because the weights are
        the draw's own masses and a single average factor would be right for no
        draw in particular.
        """
        for name in touched:
            position = [i for i, c in enumerate(component_names) if c == name]
            here = component == name
            if not position or not here.any():
                continue
            was, now = before[here].sum(axis=0), after[here].sum(axis=0)
            factor = np.divide(now, was, out=np.ones_like(now), where=was > 0)
            totals[position[0]] *= factor

    # 1. Split the module enclosure FIRST, so only its iron half is available to
    #    scale. The component's own total does not move -- only its makeup.
    split = tech.module_enclosure_split
    enclosure = "batteryPackModuleEnclosuresAndCoolantManifolds"
    in_enclosure = component == enclosure
    if split and in_enclosure.any():
        pooled = masses[in_enclosure].sum(axis=0)
        masses = masses[~in_enclosure]
        component = component[~in_enclosure]
        element = element[~in_enclosure]
        for split_element, share in split.items():
            masses = np.vstack([masses, pooled * float(share)])
            component = np.append(component, enclosure)
            element = np.append(element, split_element)

    # 2. Scale the pack IRON by the cell mass it carries. Aluminium untouched --
    #    the heat to be moved is set by the capacity, not by the pack's weight.
    if tech.structure_scales_with_cell_mass:
        factor = cell_mass_ratio(params, chemistry)
        if factor != 1.0:
            iron = np.isin(component, list(tech.structure_iron_components)) & (element == "Fe")
            before = masses.copy()
            masses[iron] *= factor
            carry_up(before, masses, set(tech.structure_iron_components),
                     component_masses)

    # 3. Expand to the pack voltages, which only touches copper.
    out: dict[int, PackDraws] = {}
    for voltage in tech.pack_voltages_v:
        per_voltage = masses.copy()
        per_component = component_masses.copy()
        copper_factor = float(tech.copper_scale_by_voltage[voltage])
        if copper_factor != 1.0:
            copper = (np.isin(component, list(tech.voltage_scaled_copper_components))
                      & (element == "Cu"))
            before = per_voltage.copy()
            per_voltage[copper] *= copper_factor
            carry_up(before, per_voltage, set(tech.voltage_scaled_copper_components),
                     per_component)
        elements = sorted(set(str(e) for e in element))
        stacked = np.vstack([per_voltage[element == e].sum(axis=0) for e in elements])
        order = np.argsort(component_names)
        out[int(voltage)] = PackDraws(
            elements, stacked,
            [component_names[i] for i in order], per_component[order])
    return out


def check_draws_match_workbook(model: CompositionModel, params, chemistry: str,
                               capacity: float, tolerance: float = 0.005) -> None:
    """
    The draws and the CSV path must agree, at BOTH levels, or raise.

    Two implementations of the same three rules is the risk this function is
    paid to cover: the arrays have drifted from the workbook three times in this
    project's history -- 9.9 points on iron, 5.8 on aluminium, and a 36 kg frame
    against 88 kg. The docstring above has claimed this check existed since
    then; it did not, until now.
    """
    keys, raw = model.component_element_draws_at(capacity, chemistry=chemistry,
                                                 code=None)
    per_voltage = apply_pack_rules_to_draws(keys, raw, params, chemistry)
    rows = apply_pack_rules_to_workbook(
        rows_for(model, params, chemistry, capacity), params, chemistry)
    scope = params.scope
    for voltage, drawn in per_voltage.items():
        here = rows[rows["voltage_v"] == voltage]
        for code, names, masses, column in (
                (scope.element_parameter_code, drawn.elements,
                 drawn.element_masses, "Layer 4"),
                (scope.component_parameter_code, drawn.components,
                 drawn.component_masses, "Layer 2")):
            book = (here[here["parameterCode"] == code]
                    .groupby(column)["meanValue"].sum())
            for name, values in zip(names, masses):
                expected = float(book.get(name, 0.0))
                got = float(values.mean())
                if expected <= 0 and got <= 0:
                    continue
                off = abs(got - expected) / max(expected, 1e-9)
                if off > tolerance:
                    raise SystemExit(
                        f"{chemistry} {capacity:.0f}kWh {voltage}V {code} {name}: "
                        f"draws mean {got:.4f} kg against the workbook's "
                        f"{expected:.4f} kg, {off:.2%} apart. The two paths "
                        "through the pack rules have drifted.")


def unknown_template_draws(model: CompositionModel, params, chemistry: str,
                           capacity: float) -> tuple[pd.DataFrame, np.ndarray]:
    """
    (keys, masses) for a chemistry with no composition of its own, in the shape
    `component_element_draws_at(code=None)` returns and ready for the pack rules.

    WHY THIS EXISTS. These two chemistries were the only ones with no persisted
    draws, so stage 04_04 downstream could not read them at all and dropped the
    whole car -- the frame, the enclosure, the cables and both collectors along
    with the cathode nobody knows. That threw away roughly half of each pack by
    mass for no reason beyond the export.

    WHAT IT CLAIMS AND WHAT IT DOES NOT. The packaging is the base chemistry's,
    at the base chemistry's mass: a sodium pack is built like the LFP pack it is
    derived from. The active materials are ZERO here, and zero means "this model
    does not describe it" -- the consumer must keep reporting them as a gap, or
    a pack will read as fully known when its cathode is not.

    It is a second path to the same numbers as `build_unknown_rows`, which is a
    risk this project has been bitten by three times.
    `check_unknown_draws_match_workbook()` compares them on every run.
    """
    template = params.export.unknown_chemistry_template[chemistry]
    keys, draws = model.component_element_draws_at(
        capacity, chemistry=template["based_on"], code=None)
    keys = keys.copy()
    draws = np.asarray(draws, dtype=np.float64).copy()

    keep = ~keys.component.isin(template["remove_components"]).to_numpy()
    keys, draws = keys[keep].reset_index(drop=True), draws[keep]

    # The template's deterministic factors, and the component rows with them:
    # a factor keyed on an element misses the row that carries no element, and
    # that is how currentCollectorAnode once read 26.7 kg at component level
    # against 11.9 at element level. The component takes the factor its own
    # elements imply, mass-weighted PER DRAW.
    element_rows = (keys.code == params.scope.element_parameter_code).to_numpy()
    for component, by_element in template["mass_scale"].items():
        at_component = (keys.component == component).to_numpy()
        here = at_component & element_rows
        if not here.any():
            continue
        total = draws[here].sum(axis=0)
        scaled = np.zeros_like(total)
        for position in np.where(here)[0]:
            scaled += draws[position] * float(
                by_element.get(str(keys.element.iloc[position]), 1.0))
        with np.errstate(divide="ignore", invalid="ignore"):
            weighted = np.where(total > 0, scaled / total, 1.0)
        whole = at_component & ~element_rows
        if whole.any():
            draws[whole] *= weighted[None, :]
        for element, factor in by_element.items():
            target = at_component & (keys.element == element).to_numpy() & element_rows
            draws[target] *= float(factor)

    # The swaps rename, they do not scale. Two rows can collapse into one and
    # are summed by the pack rules afterwards, not dropped.
    for component, mapping in template["element_swaps"].items():
        target = keys.component == component
        keys.loc[target, "element"] = keys.loc[target, "element"].replace(mapping)

    # How much the inherited packaging is trusted -- one doubt about one
    # inheritance, drawn once per chemistry, on the components it was inherited
    # for and no others.
    scale = unknown_scale_draws(params, chemistry)
    if scale is not None:
        in_scope = keys.component.isin(
            params.technology.unknown_chemistry_scaled_components).to_numpy()
        draws[in_scope] *= np.asarray(scale)[None, :]

    # What is NOT claimed is zero, and zero here means unknown. The cathode, the
    # anode and the electrolyte keep nothing: a plausible number borrowed from a
    # lithium chemistry is a claim nobody made.
    unclaimed = ~keys.component.isin(template["claim_masses_for"]).to_numpy()
    draws[unclaimed] = 0.0
    return keys, draws


def check_unknown_draws_match_workbook(model: CompositionModel, params,
                                       chemistry: str, capacity: float,
                                       tolerance: float = 0.005) -> None:
    """
    The unknown chemistry's draws and its CSV must agree, or raise.

    Compared at 2020, where the improvement factor is exactly 1 in every draw,
    so the arrays -- which carry no year -- and that year's rows are the same
    quantity.

    ONE CORRECTION IS NEEDED AND IT IS NOT A FUDGE. `build_unknown_rows` writes
    the packaging trust's MODE into the central column, by the same convention
    every other chemistry uses for the improvement. The draws carry the factor
    itself, whose MEAN is (min + mode + max) / 3 -- 1.0667 against a mode of 1.0
    for sodium, 0.8667 against 0.8 for solid-state. So the row is compared
    against the draws divided by mean/mode, on the components the trust applies
    to. Everything else is deterministic on both sides and compared as it is.
    """
    keys, raw = unknown_template_draws(model, params, chemistry, capacity)
    per_voltage = apply_pack_rules_to_draws(keys, raw, params, chemistry)
    rows = apply_pack_rules(
        build_unknown_rows(model, params, pd.DataFrame([{
            "segment": f"{int(capacity)}kWh", "year": 2020,
            "capacity_kwh_nominal": capacity,
            "capacity_is_projected": False, "capacity_source": "workbook anchor"}]),
            chemistry), params, chemistry)

    band = params.technology.unknown_chemistry_mass_scale.get(chemistry)
    drawn_over_central = 1.0
    if band is not None:
        drawn_over_central = ((float(band["min"]) + float(band["mode"])
                               + float(band["max"])) / 3.0) / float(band["mode"])
    in_scope = set(params.technology.unknown_chemistry_scaled_components)

    for voltage, drawn in per_voltage.items():
        here = rows[rows["voltage_v"] == voltage]
        book = (here[here.level == "component"]
                .groupby("component")["mass_kg"].sum())
        for name, values in zip(drawn.components, drawn.component_masses):
            expected = float(book.get(name, 0.0))
            got = float(values.mean())
            if name in in_scope:
                got /= drawn_over_central
            if expected <= 0 and got <= 0:
                continue
            off = abs(got - expected) / max(expected, 1e-9)
            if off > tolerance:
                raise SystemExit(
                    f"{chemistry} {capacity:.0f}kWh {voltage}V {name}: draws give "
                    f"{got:.4f} kg against the workbook's {expected:.4f} kg, "
                    f"{off:.2%} apart. The two paths through the template have "
                    "drifted.")


def fixed_capacity_rows(model: CompositionModel, params, chemistry: str,
                        capacity: float, unknown: bool) -> pd.DataFrame:
    """
    Every element at ONE capacity, across the export years.

    The improvement, isolated. Capacity is held, so the only thing that moves
    with the year is the improvement -- the same kWh needing less material as
    the cell gets better. A segment's capacity trajectory is a different
    question and belongs to the stock-and-flow path, not to this figure.

    Built through build_rows / build_unknown_rows rather than a second copy of
    the arithmetic, so the figure and the exported files can never disagree.
    """
    held = pd.DataFrame({
        "segment": f"{capacity:.0f}kWh",
        "year": list(params.export_years()),
        "capacity_kwh_nominal": float(capacity),
        "capacity_is_projected": False,
        "capacity_source": "held_constant",
    })
    builder = build_unknown_rows if unknown else build_rows
    return apply_pack_rules(builder(model, params, held, chemistry), params, chemistry)


def draw_chemistry(rows: pd.DataFrame, chemistry: str, segment: str, params,
                   top_anchor_kwh: float = 100.0):
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
    # 'segment' carries the capacity label for the held-capacity figures. Above
    # the workbook's top anchor every mass is extrapolated and the title has to
    # say so -- 200 kWh is twice the highest capacity the workbook measures.
    held = str(segment).endswith("kWh")
    where = f"at {segment}, held constant" if held else f"segment {segment}"
    beyond = ""
    if held:
        value = float(str(segment)[:-3])
        top = float(top_anchor_kwh)
        if value > top:
            beyond = (f"\n⚠️ EXTRAPOLATED: {value:.0f} kWh is {value / top:.1f}x the "
                      f"workbook's top anchor ({top:.0f} kWh); no measurement supports it")
    axes.set_title(
        f"{chemistry} — every element, {where}, 2020-2070"
        + ("\nPACKAGING ONLY: the cathode, anode and electrolyte are not known "
           "for this chemistry" if unknown else
           f"\ntotal falls {100 * (1 - total.iloc[-1] / total.max()):.0f}% as the "
           "cells improve — same kWh, less material")
        + beyond,
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



def save_figure(figure, params, name: str) -> str:
    path = params.output_path(PROJECT_ROOT, name)
    figure.savefig(path, dpi=params.drawing.output_dpi, bbox_inches="tight",
                   facecolor="white")
    plt.close(figure)
    return path.name



def histogram_density(values: np.ndarray, grid: np.ndarray, bins: int = 200) -> np.ndarray:
    """
    A histogram on a shared grid, scaled to its own peak.

    Deliberately not a kernel density estimate: a KDE picks a bandwidth, and a
    bandwidth is a claim about smoothness nobody here has made. This is the same
    histogram the mode comes from.
    """
    counts, edges = np.histogram(values, bins=bins, density=True)
    centres = 0.5 * (edges[:-1] + edges[1:])
    if counts.max() > 0:
        counts = counts / counts.max()
    return np.interp(grid, centres, counts, left=0.0, right=0.0)



def collect_draws(model: CompositionModel, params, capacity: float, element: str | None
            ) -> dict[str, np.ndarray]:
    """
    Every chemistry's draws for one element, or for the whole pack, IN A YEAR.

    The year is not optional. These draws used to come straight from the
    workbook with nothing applied, which made them the base year by accident
    and labelled nowhere -- a distribution of a mass means nothing without the
    year it belongs to, since the same pack is 20% lighter in 2070 and its
    band is wider. `export.distribution_figure_year` names it, and the
    improvement is applied draw by draw exactly as the composition files apply
    it: element-wise, so the improvement draw and the composition draw that
    meet in one column are the same draw.
    """
    out: dict[str, np.ndarray] = {}
    known = sorted(set(model._series.keys["chemistry"])
                   - {params.scope.pack_level_key})
    year = float(params.export.distribution_figure_year)
    year_draws = improvement_factor_draws(params, year)
    for chemistry in known:
        try:
            elements, masses = model.element_draws_at(capacity, chemistry=chemistry)
        except CompositionError:
            continue
        if year_draws is not None:
            masses = masses * np.asarray(year_draws)[None, :]
        if element is None:
            row = masses.sum(axis=0)
        else:
            if element not in elements:
                continue
            row = masses[elements.index(element)]
        if row.max() <= row.min():
            continue                       # a fixed zero is not a distribution
        out[chemistry] = row
    return out



def shared_pack_draws(model: CompositionModel, params, capacity: float
                      ) -> dict[str, np.ndarray]:
    """
    Per-draw mass of the components every battery has in common.

    These are the ones filed under scope.pack_level_key -- one set per pack,
    identical whatever chemistry is inside it -- so unlike everything else in
    this project there is ONE distribution, not one per chemistry.
    """
    keys, scope = model._series.keys, params.scope
    wanted = ((keys["code"] == scope.component_parameter_code)
              & (keys["chemistry"] == scope.pack_level_key))
    draws = model.mass_draws_at(float(capacity))[wanted.to_numpy()]
    # The same year as every other distribution figure, applied the same way.
    year_draws = improvement_factor_draws(
        params, float(params.export.distribution_figure_year))
    if year_draws is not None:
        draws = draws * np.asarray(year_draws)[None, :]
    subset = keys[wanted].reset_index(drop=True)
    out: dict[str, np.ndarray] = {}
    for component, positions in subset.groupby("component").indices.items():
        row = draws[positions].sum(axis=0)
        if row.max() > row.min():
            out[str(component)] = row
    if out:
        out["ALL SHARED PARTS"] = np.sum(list(out.values()), axis=0)
    return out


def draw_distribution(series: dict[str, np.ndarray], title: str, xlabel: str,
                      params, colours: dict[str, str] | None = None):
    """Several distributions of the same quantity, overlaid, in kg."""
    if not series:
        return None
    low = min(np.percentile(v, 0.2) for v in series.values())
    high = max(np.percentile(v, 99.8) for v in series.values())
    pad = 0.06 * (high - low)
    grid = np.linspace(low - pad, high + pad, 500)

    figure, axes = plt.subplots(figsize=(13.5, 8))
    order = sorted(series, key=lambda c: series[c].mean())
    for chemistry in order:
        row = series[chemistry]
        colour = (colours or params.scenarios.workbook_chemistry_colours)[chemistry]
        curve = histogram_density(row, grid)
        style = "--" if chemistry in UNKNOWN_COMPOSITION else "-"
        axes.fill_between(grid, 0, curve, color=colour, alpha=0.22, linewidth=0)
        axes.plot(grid, curve, color=colour, linewidth=2.0, linestyle=style,
                  label=chemistry)
        mode = float(approximate_mode(row[None, :])[0])
        axes.plot([mode, mode], [0, 1.02], color=colour, linewidth=1.4, alpha=0.9)
        for edge in np.percentile(row, [2.5, 97.5]):
            axes.plot([edge, edge], [0, 0.30], color=colour, linewidth=1.0,
                      linestyle=":", alpha=0.9)

    axes.set_xlabel(xlabel, fontsize=11)
    axes.set_ylabel("relative frequency (each scaled to its own peak)", fontsize=10.5)
    axes.set_title(title, fontsize=12.5)
    axes.set_ylim(0, 1.16)
    axes.grid(True, axis="x", linestyle="--", alpha=0.3)
    axes.set_axisbelow(True)
    for side in ("top", "right", "left"):
        axes.spines[side].set_visible(False)
    axes.set_yticks([])
    axes.legend(frameon=False, fontsize=10, ncol=3, loc="upper center",
                bbox_to_anchor=(0.5, -0.10))
    figure.tight_layout()
    return figure


def main(argv: list[str] | None = None) -> int:
    try:
        params = current()
    except ParameterError as error:
        print(f"src/params_schema.py is NOT valid:\n  {error}", file=sys.stderr)
        return 1

    export = params.export

    try:
        model = CompositionModel(params, project_root=PROJECT_ROOT)
        if params.ev_details.capacity_basis != "nominal":
            print("[export] WARNING: ev_details.capacity_basis is "
                  f"{params.ev_details.capacity_basis!r}, but the workbook's kg/kWh "
                  "is per NOMINAL kWh. Every mass below is on the wrong basis.")
    except CompositionError as error:
        print(f"{error}", file=sys.stderr)
        return 1

    chemistries = sorted(set(model._series.keys.chemistry) - {params.scope.pack_level_key})
    missing = list(params.scenarios.chemistries_without_composition)

    print(f"Export years: {params.export_years()}")
    print("Capacity    : the workbook's own anchors "
          f"{[int(c) for c in model._series.capacities]} kWh. Segment capacity, the "
          "range target and the\n              fitted curve are NOT here -- they are "
          "fleet questions and live in\n              06_segment_capacity.py, which "
          "RAWCLICStockAndFlow supersedes.")
    print(f"Chemistries : {len(chemistries)} with composition -- {chemistries}")
    if export.write_unknown_chemistries:
        print(f"              {len(missing)} marked unknown -- {missing}: packaging "
              "only, active materials left empty.")
    else:
        print(f"NOT written : {missing} (export.write_unknown_chemistries is off).")

    to_write = [(c, False) for c in chemistries]
    if export.write_unknown_chemistries:
        to_write += [(c, True) for c in missing]

    # -----------------------------------------------------------------------
    # Per-draw element FRACTIONS, at the workbook's own capacity anchors.
    #
    # WHY FRACTIONS AND WHY PER DRAW. RAWCLICStockAndFlow multiplies element data
    # against its own per-draw vehicle counts, draw against draw, which no
    # percentile can support. Same reasoning and same layout as
    # RAWCLICVehicleElectronics' `Composition/element_draws/`.
    #
    # WHY THE ANCHORS, AND NOT ONE ARRAY. Unlike the electronics model -- whose
    # composition is frozen at 2025 and genuinely has no second axis -- these
    # fractions move with capacity, because the pack hardware (frame, thermal
    # conductor, cables: Fe, Al, Cu) does not scale with kWh while the cell
    # materials do. Measured across 25 -> 100 kWh they shift by 21% to 60%
    # relative, so a single array per chemistry would be wrong by up to 60%.
    #
    # THE CONSUMER MUST INTERPOLATE, AND WILL SOMETIMES EXTRAPOLATE: the fitted
    # capacities land between anchors (JC 76.3) and above the top one (JE 104.5,
    # F 106.1). Measured on battLiNMC_midNi against the model's own fractions,
    # linear interpolation is within 0.51% and linear extrapolation from the top
    # two anchors within 0.41% -- well inside the 2.5-97.5 band. Checked on that
    # one chemistry and no higher than 106 kWh.
    # -----------------------------------------------------------------------
    draws_dir = params.composition_output_path(PROJECT_ROOT, "element_draws")
    draws_dir.mkdir(parents=True, exist_ok=True)
    anchors = [float(c) for c in model._series.capacities]
    n_written = 0
    for chemistry in chemistries:
        for anchor in anchors:
            # THROUGH THE PACK RULES, like the consolidated masses beside them.
            # Taken straight from element_draws_at these fractions carried none
            # of the three rules and sat 9.9 percentage points off the CSVs on
            # iron. Fractions also MOVE WITH VOLTAGE, because the copper does,
            # so there is one set per voltage -- a single array could only ever
            # have been right for one of the two.
            keys, raw_draws = model.component_element_draws_at(
                anchor, chemistry=chemistry, code=None)
            for voltage, drawn in apply_pack_rules_to_draws(
                    keys, raw_draws, params, chemistry).items():
                stem = f"batt_{chemistry}_{int(anchor)}kWh_{voltage}V"
                for names, masses, level in (
                        (drawn.elements, drawn.element_masses, "elements"),
                        (drawn.components, drawn.component_masses, "components")):
                    totals = masses.sum(axis=0)
                    fractions = np.zeros_like(masses)
                    live = totals > 0
                    fractions[:, live] = masses[:, live] / totals[live]
                    suffix = "" if level == "elements" else "_component"
                    # (draws, rows) float32, the orientation the electronics files use.
                    np.save(draws_dir / f"{stem}{suffix}_fractions.npy",
                            fractions.T.astype(np.float32))
                    (draws_dir / f"{stem}_{level}.txt").write_text("\n".join(names))
                    n_written += 1
    print(f"\nWrote {n_written} per-draw fraction arrays to "
          f"{params.export.composition_output_dir}/element_draws/ "
          f"({len(anchors)} anchors x {len(chemistries)} chemistries x "
          f"{len(params.technology.pack_voltages_v)} voltages)")

    # ------------------------------------------- the consolidated files

    anchors = [float(c) for c in model._series.capacities]
    years = params.export_years()
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

    n_draw_files = 0
    # THE YEAR IS NOT MULTIPLIED OUT. The improvement is one scalar per draw,
    # shared by every component, element and year, so a year's mass draws are
    # the base-year draws times that year's factor. Writing the factor once per
    # year is 11 arrays of (n_draws,) against 11 copies of every mass array.
    #   mass(year) = <stem>_mass_draws.npy * improvement_factor_draws_<year>.npy[:, None]
    for year in years:
        factors = improvement_factor_draws(params, float(year))
        if factors is None:
            break
        np.save(directory / f"improvement_factor_draws_{int(year)}.npy",
                np.asarray(factors, dtype=np.float32))

    for chemistry in known:
        has_trajectory = chemistry in params.technology.chemistry_energy_density
        # improvement_factor, the SAME function the segment-year files use, not
        # a second copy of the arithmetic: these two outputs disagreeing about
        # this exact quantity is what made every figure flat after 2025.
        def factor_for(year: float) -> float:
            return improvement_factor(params, year)
        per_year = []
        for capacity in anchors:
            # MASS draws, in kg, THROUGH THE PACK RULES -- not fractions taken
            # straight off the model. The rules are keyed on (component,
            # element), so they have to be applied before the sum to elements;
            # writing the summed array directly is what left these files 9.9
            # percentage points adrift of the CSVs on iron.
            keys, raw_draws = model.component_element_draws_at(
                capacity, chemistry=chemistry, code=None)
            check_draws_match_workbook(model, params, chemistry, capacity)
            for voltage, drawn in apply_pack_rules_to_draws(
                    keys, raw_draws, params, chemistry).items():
                stem = f"{chemistry}_{int(capacity)}kWh_{voltage}V"
                np.save(directory / f"{stem}_mass_draws.npy",
                        drawn.element_masses.T.astype(np.float32))
                (directory / f"{stem}_elements.txt").write_text(
                    "\n".join(drawn.elements))
                # The component level beside it: the elements do not add up to
                # the pack, and 7-11% of it lives only here.
                np.save(directory / f"{stem}_component_mass_draws.npy",
                        drawn.component_masses.T.astype(np.float32))
                (directory / f"{stem}_components.txt").write_text(
                    "\n".join(drawn.components))
                n_draw_files += 2

            # Built PER YEAR from the draws, not copied and scaled. The
            # improvement has to reach the statistics as a distribution or the
            # band it carries never appears in them.
            for year in years:
                frame = apply_pack_rules_to_workbook(
                    rows_for(model, params, chemistry, capacity,
                             year_factor_draws=improvement_factor_draws(
                                 params, float(year)),
                             year_factor=factor_for(float(year))),
                    params, chemistry)
                frame["productionYear"] = year
                per_year.append(frame)

        rows = pd.concat(per_year, ignore_index=True)
        rows = rows[WORKBOOK_COLUMNS + ADDED_COLUMNS]
        path = directory / f"consolidated_{chemistry}.csv"
        rows.to_csv(path, index=False)
        note = "" if has_trajectory else "   (no trajectory -- flat in year)"
        print(f"  {chemistry:20s} {len(rows):>7,} rows -> {path.name}{note}")

    print(f"  wrote {n_draw_files} per-draw MASS arrays (kg, pack rules applied, "
          f"one per chemistry x capacity x voltage)")

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
    n_unknown_draw_files = 0
    for chemistry in unknown:
        capacities = pd.DataFrame([
            {"segment": f"{int(a)}kWh", "year": y, "capacity_kwh_nominal": a,
             # build_rows carries both through onto every row it makes. An
             # anchor is neither fitted nor projected -- it is the workbook's
             # own capacity -- and saying so is better than leaving them blank.
             "capacity_is_projected": False, "capacity_source": "workbook anchor"}
            for a in anchors for y in years])
        # Through the same pack rules as everything else. Without this the
        # consolidated files for these two chemistries would carry the
        # unsplit enclosure, the unscaled iron and no voltage at all.
        built = apply_pack_rules(
            build_unknown_rows(model, params, capacities, chemistry),
            params, chemistry)

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
            "voltage_v": built["voltage_v"],
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

        # THE DRAWS, like every other chemistry. Without these two sets of
        # arrays a consumer cannot read these chemistries at all and drops the
        # whole car -- the frame, the enclosure, the cables and both collectors
        # along with the cathode nobody knows. Roughly half of each pack by mass
        # was being thrown away for no reason beyond the export.
        #
        # The active materials are ZERO in them, and a consumer must keep
        # reporting these two as a gap on that basis: zero means "not described
        # here", not "none present".
        for capacity in anchors:
            check_unknown_draws_match_workbook(model, params, chemistry, capacity)
            keys, raw_draws = unknown_template_draws(model, params, chemistry,
                                                     capacity)
            for voltage, drawn in apply_pack_rules_to_draws(
                    keys, raw_draws, params, chemistry).items():
                stem = f"{chemistry}_{int(capacity)}kWh_{voltage}V"
                np.save(directory / f"{stem}_mass_draws.npy",
                        drawn.element_masses.T.astype(np.float32))
                (directory / f"{stem}_elements.txt").write_text(
                    "\n".join(drawn.elements))
                np.save(directory / f"{stem}_component_mass_draws.npy",
                        drawn.component_masses.T.astype(np.float32))
                (directory / f"{stem}_components.txt").write_text(
                    "\n".join(drawn.components))
                n_unknown_draw_files += 2
    print(f"  wrote {n_unknown_draw_files} per-draw arrays for the chemistries "
          "with no composition of their own -- packaging only, active materials "
          "zero")
    print(f"\n  consolidated -> {params.export.consolidated_output_dir}/, "
          "one file per chemistry with its draw arrays beside it.")

    # ------------------------------------------------------------- figures
    # Built here, not read back from disk. The figures used to re-read the
    # segment-year files, which tied them to an output that has since moved to
    # 06_segment_capacity.py -- and which had already let them drift from the
    # rules the files carried.
    drawn = 0

    # COMPOSITION OVER TIME, AT A HELD CAPACITY. Not a segment: a segment's
    # capacity moves, and that trend would be drawn on top of the improvement
    # the figure exists to show. One figure per chemistry per capacity.
    top_anchor = float(model.anchors.kwh.max())
    for capacity in params.export.over_time_figure_capacities_kwh:
        # Above the workbook's top anchor, only the chemistries that plausibly
        # reach that size. Everything else would be a figure of an extrapolation
        # of a pack nobody would build.
        large = float(capacity) > params.export.over_time_large_capacity_above_kwh
        eligible = ([(c, u) for c, u in to_write
                     if c in params.export.over_time_large_capacity_chemistries]
                    if large else to_write)
        if not eligible:
            continue
        held_rows = []
        for chemistry, unknown in eligible:
            built = fixed_capacity_rows(model, params, chemistry, float(capacity),
                                         unknown)
            # ONE voltage only. The rows carry both, and stacking both would
            # draw every element twice.
            at_voltage = built.voltage_v == params.export.over_time_figure_voltage_v
            held_rows.append(built[(built.level == "element") & at_voltage])
        held = pd.concat(held_rows, ignore_index=True)
        label = f"{float(capacity):.0f}kWh"
        for chemistry in sorted(held.chemistry.dropna().unique()):
            figure = draw_chemistry(held, chemistry, label, params,
                                    top_anchor_kwh=top_anchor)
            if figure is not None:
                save_figure(figure, params,
                            f"composition_over_time_{chemistry}_{label}.png")
                drawn += 1
        print(f"  composition over time at {label}: capacity held, only the "
              "cell improvement moves"
              + ("" if float(capacity) <= top_anchor else
                 f"  ⚠️ EXTRAPOLATED, {float(capacity) / top_anchor:.1f}x the top "
                 f"anchor ({top_anchor:.0f} kWh)"))


    capacity = params.export.distribution_figure_capacity_kwh

    # The parts every battery shares, which have ONE distribution rather than one
    # per chemistry: frame, thermal conductor, module enclosures, cables. Drawn
    # per component and as their total, so it is visible which one carries the
    # uncertainty.
    shared = shared_pack_draws(model, params, capacity)
    if shared:
        palette = plt.get_cmap("tab10")
        shared_colours = {name: ("#1c1c1c" if name.startswith("ALL")
                                 else palette(i % 10))
                          for i, name in enumerate(shared)}
        figure = draw_distribution(
            shared,
            f"Parts every battery shares, at {capacity:.0f} kWh in "
            f"{params.export.distribution_figure_year} \u2014 identical whatever "
            f"chemistry is inside\n{params.monte_carlo.n_draws:,} draws; "
            "solid line the mode, dotted the 2.5 and 97.5 percentiles",
            "mass in one car [kg]", params, colours=shared_colours)
        if figure is not None:
            save_figure(figure, params,
                        f"distribution_shared_parts_{capacity:.0f}kWh.png")
            drawn += 1

    figure = draw_distribution(
        collect_draws(model, params, capacity, None),
        f"Whole battery mass at {capacity:.0f} kWh in "
        f"{params.export.distribution_figure_year} \u2014 every chemistry\n"
        f"{params.monte_carlo.n_draws:,} draws; solid line the mode, dotted the "
        "2.5 and 97.5 percentiles",
        "battery mass in one car [kg]", params)
    if figure is not None:
        save_figure(figure, params, f"distribution_total_{capacity:.0f}kWh.png")
        drawn += 1
    for element in params.export.crm_elements:
        figure = draw_distribution(
            collect_draws(model, params, capacity, element),
            f"{element} at {capacity:.0f} kWh in "
            f"{params.export.distribution_figure_year} \u2014 every chemistry that "
            f"contains it\n{params.monte_carlo.n_draws:,} draws; solid line the mode, "
            "dotted the 2.5 and 97.5 percentiles",
            f"{element} in one car [kg]", params)
        if figure is not None:
            save_figure(figure, params, f"distribution_{element}_{capacity:.0f}kWh.png")
            drawn += 1
    print(f"\n  figures      -> {drawn} in {params.paths.output_dir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
