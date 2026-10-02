"""
src/unknown_chemistries.py
==========================

THE CHEMISTRIES THAT ARE NOT IN THE WORKBOOK, as draws: the two that have no
composition at all (solid-state) and the two sodium cells built from literature.

Moved out of 05_composition.py on 2026-10-02 because a second script, 02, has to
draw the sodium cells too, and scripts do not import each other in this project --
that pattern broke silently when they were renumbered. The functions are unchanged;
05 imports them under the same names, and the byte-for-byte comparison of its output
before and after the move is the proof.

Nothing here writes a file.
"""

from __future__ import annotations

import zlib

import numpy as np
import pandas as pd

from src import sodium_composition as sodium
from src.composition import MODULE_ENCLOSURE, CompositionError, CompositionModel


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
    # crc32, NOT hash(): Python randomises string hashes per process, so a seed
    # built from hash() changed between runs -- measured 19, 697 and 922 for one
    # name in three processes -- and the packaging-trust draws with it. The same
    # settings gave different files. Fixed 2026-10-02; the draws of solid_state are
    # therefore different from every run before this date, and from now on
    # identical from one run to the next.
    seed = mc.random_seed + 2 + (zlib.crc32(chemistry.encode()) % 1000)
    rng = np.random.default_rng(seed)
    _UNKNOWN_SCALE_DRAWS[chemistry] = rng.triangular(
        float(band["min"]), float(band["mode"]), float(band["max"]), size=mc.n_draws)
    return _UNKNOWN_SCALE_DRAWS[chemistry]


def unknown_template(params, chemistry: str) -> dict:
    """
    The template of a chemistry that is not in the workbook: one of the two with
    no composition, or one of the sodium cells built from literature. Both carry
    the same keys, so everything that claims packaging reads them alike.
    """
    export = params.export
    if chemistry in export.unknown_chemistry_template:
        return export.unknown_chemistry_template[chemistry]
    return export.literature_chemistry_template[chemistry]


_SODIUM_CACHE: dict = {}
_SODIUM_VERIFIED: set = set()


def lithium_cathode_range(model: CompositionModel, params,
                          capacity: float = 80.0) -> tuple[float, float]:
    """
    The lowest and highest cathode energy per gram among the workbook's
    chemistries, MEASURED NOW from the workbook rather than written down: the
    anchor the sodium cathode is checked against, so it follows the workbook if
    the workbook changes.
    """
    key = ("lithium range", float(capacity))
    if key not in _SODIUM_CACHE:
        per_gram = []
        for chemistry in sorted(set(model._series.keys.chemistry)
                                - {params.scope.pack_level_key}):
            table = model.weights_at(capacity, chemistry=chemistry, level="component")
            mass = float(table.loc[table.component == sodium.CATHODE, "mass_kg"].sum())
            if mass > 0:
                per_gram.append(capacity / mass)        # kWh / kg == Wh / g
        _SODIUM_CACHE[key] = (min(per_gram), max(per_gram))
    return _SODIUM_CACHE[key]


def sodium_packaging(model: CompositionModel, params, chemistry: str,
                     capacity: float) -> np.ndarray:
    """
    What the claimed casing, separator and collectors weigh in each draw, kg.

    Taken from the SAME packaging draws the arrays carry -- template factors,
    conductance scaling and trust factor included -- so the remainder is the
    cell minus exactly what is already counted.
    """
    key = ("packaging", chemistry, round(float(capacity), 6))
    if key in _SODIUM_CACHE:
        return _SODIUM_CACHE[key]
    keys, draws = unknown_packaging_draws(model, params, chemistry, capacity)
    named = params.technology.sodium_cell["packaging_components"]
    rows = ((keys.code == params.scope.component_parameter_code)
            & keys.component.isin(named)).to_numpy()
    if int(rows.sum()) != len(named):
        raise sodium.SodiumCompositionError(
            f"{chemistry}: expected one component-level row for each of {named}, "
            f"found {int(rows.sum())}.")
    total = draws[rows].sum(axis=0)
    # Kept for the anchors only: the conditioning reads them, and 05 asks for them
    # again. A curve visits capacities nobody asks for twice, and 200,000 draws at
    # a hundred of them is gigabytes of nothing.
    if any(abs(float(capacity) - float(anchor)) < 1e-9
           for anchor in model._series.capacities):
        _SODIUM_CACHE[key] = total
    return total


def sodium_inputs(model: CompositionModel, params, chemistry: str) -> sodium.Inputs:
    """
    The sodium cell's inputs, drawn ONCE per chemistry and shared by every
    capacity, year and row, conditioned so no anchor has a negative remainder.
    """
    key = ("inputs", chemistry)
    if key not in _SODIUM_CACHE:
        anchors = [float(c) for c in model._series.capacities]
        packaging = {a: sodium_packaging(model, params, chemistry, a) for a in anchors}
        inputs, report = sodium.conditioned_inputs(
            params, chemistry, params.monte_carlo.n_draws, packaging)
        worst = max(report["shift"].items(), key=lambda item: abs(item[1]))
        print(f"    [{chemistry}] sodium cell drawn: {100 * report['redrawn']:.2f}% of "
              f"draws redrawn for a negative remainder across {len(anchors)} anchors; "
              f"conditioning moved {worst[0]} by {100 * worst[1]:+.2f}% at most")
        _SODIUM_CACHE[key] = inputs
    return _SODIUM_CACHE[key]


def sodium_masses(model: CompositionModel, params, chemistry: str,
                  capacity: float, strict: bool = True) -> sodium.Masses:
    """
    The cell of one battery at `capacity`, base year, checked the first time it
    is made at that capacity. Both output paths call this and nothing else, so
    they cannot disagree about what the cell weighs.
    """
    masses = sodium.masses_at(params, chemistry, sodium_inputs(model, params, chemistry),
                              capacity, sodium_packaging(model, params, chemistry, capacity))
    marker = (chemistry, round(float(capacity), 6))
    if strict and marker not in _SODIUM_VERIFIED:
        sodium.verify(params, chemistry, masses, capacity,
                      sodium_packaging(model, params, chemistry, capacity),
                      lithium_cathode_range(model, params))
        _SODIUM_VERIFIED.add(marker)
    return masses


def sodium_wholes(masses: sodium.Masses) -> dict:
    """The four components the sodium cell owns, by name."""
    return {sodium.CATHODE: masses.cathode, sodium.ANODE: masses.anode,
            sodium.ELECTROLYTE: masses.electrolyte, sodium.REMAINDER: masses.remainder}


def unknown_packaging_draws(model: CompositionModel, params, chemistry: str,
                            capacity: float) -> tuple[pd.DataFrame, np.ndarray]:
    """
    THE PACKAGING HALF of `unknown_template_draws`: everything the template
    claims, with the cathode, anode and electrolyte at ZERO.

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
    template = unknown_template(params, chemistry)
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


def unknown_template_draws(model: CompositionModel, params, chemistry: str,
                           capacity: float, strict: bool = True
                           ) -> tuple[pd.DataFrame, np.ndarray]:
    """
    (keys, masses) for a chemistry that is not in the workbook, ready for the
    pack rules.

    The two with no composition are the packaging alone. A sodium cell built
    from literature has its cathode, anode and electrolyte replaced by the draws
    of `sodium_masses`, element by element, and the unitemised remainder added as
    a component of its own.
    """
    keys, draws = unknown_packaging_draws(model, params, chemistry, capacity)
    if not sodium.is_sodium_cell(params, chemistry):
        return keys, draws

    masses = sodium_masses(model, params, chemistry, capacity, strict=strict)
    scope = params.scope
    drop = keys.component.isin(sodium.ACTIVE_COMPONENTS).to_numpy()
    keys, draws = keys[~drop].reset_index(drop=True), draws[~drop]
    added_keys, added_draws = [], []
    for component, whole in sodium_wholes(masses).items():
        added_keys.append({"chemistry": chemistry, "component": component,
                           "element": "n/a", "code": scope.component_parameter_code})
        added_draws.append(whole)
        for element, kg in masses.elements.get(component, {}).items():
            added_keys.append({"chemistry": chemistry, "component": component,
                               "element": element, "code": scope.element_parameter_code})
            added_draws.append(kg)
    return (pd.concat([keys, pd.DataFrame(added_keys)], ignore_index=True),
            np.vstack([draws] + [row[None, :] for row in added_draws]))


class CompositionWithCells:
    """
    The workbook's composition model, plus the sodium cells built from literature.

    02 asks the composition model three things: a table at one capacity, a curve
    for every component, and the whole battery's mass against capacity. The workbook
    model answers them for the workbook's chemistries only, so the sodium cells were
    simply missing from every figure 02 draws. This answers the same three for them,
    from their draws and in the same shapes, so the script need not know the
    difference.

    For a sodium cell the central value is the MEDIAN of the draws (the workbook's is
    its own central curve). A draw whose remainder is negative at a capacity is left
    out at that capacity, and `kept` says what share survives; at the anchors that is
    all of them, because they are what the draws were conditioned on. Curves are
    evaluated on `CURVE_POINTS` capacities rather than the workbook's hundred, because
    every capacity is a full set of draws.
    """

    CURVE_POINTS = 26

    def __init__(self, model: CompositionModel):
        self.model = model
        self.params = model.params
        self._series = model._series

    def chemistries(self) -> list[str]:
        scope = self.params.scope
        workbook = sorted(set(self._series.keys["chemistry"]) - {scope.pack_level_key})
        return workbook + sorted(self.params.export.literature_chemistry_template)

    def is_cell(self, chemistry: str) -> bool:
        return sodium.is_sodium_cell(self.params, chemistry)

    def structure(self, chemistry: str) -> dict[str, tuple[str, ...]]:
        """
        What a chemistry's battery is made of, by name only: {part: (elements,)}.

        No masses and no draws -- which parts it has, and which elements each part is
        made of. A part the data does not split into elements has none. A workbook
        chemistry reads this off the workbook. A sodium cell is its base chemistry's
        parts that the template claims, with the template's element swaps, and the
        cell's own cathode, anode and electrolyte in place of the base's, plus the
        remainder -- the same steps `unknown_template_draws` takes on the draws.
        """
        if self.is_cell(chemistry):
            template = unknown_template(self.params, chemistry)
            claimed = set(template["claim_masses_for"]) - set(template["remove_components"])
            parts = {}
            for part, elements in self._workbook_structure(template["based_on"]).items():
                if part in claimed and part not in sodium.ACTIVE_COMPONENTS:
                    swaps = template["element_swaps"].get(part, {})
                    parts[part] = tuple(sorted({swaps.get(e, e) for e in elements}))
            parts.update({part: tuple(sorted(elements)) for part, elements
                          in sodium.elements_of(self.params, chemistry).items()})
            parts[sodium.REMAINDER] = ()
        else:
            parts = self._workbook_structure(chemistry)
        # The pack rules split the enclosure between aluminium and iron.
        split = self.params.technology.module_enclosure_split
        if split and MODULE_ENCLOSURE in parts:
            parts[MODULE_ENCLOSURE] = tuple(sorted(split))
        return parts

    def _workbook_structure(self, chemistry: str) -> dict[str, tuple[str, ...]]:
        scope, table = self.params.scope, self.model.anchors
        known = set(table.chemistry) - {scope.pack_level_key}
        if chemistry not in known:
            raise CompositionError(
                f"unknown chemistry {chemistry!r}. The workbook has: {sorted(known)}")
        present = table[table.chemistry.isin([chemistry, scope.pack_level_key])
                        & (table.mass_kg > 0)]
        parts = set(present.loc[present.code == scope.component_parameter_code, "component"])
        elements = present[present.code == scope.element_parameter_code]
        return {part: tuple(sorted(set(elements.loc[elements.component == part, "element"])))
                for part in sorted(parts)}

    def _pack_components(self) -> set[str]:
        keys, scope = self._series.keys, self.params.scope
        return set(keys.loc[(keys.chemistry == scope.pack_level_key)
                            & (keys.code == scope.component_parameter_code), "component"])

    def _block(self, chemistry: str, capacity: float):
        """(keys, draws, kept) at one capacity, infeasible draws left out."""
        keys, draws = unknown_template_draws(self.model, self.params, chemistry,
                                             float(capacity), strict=False)
        scope = self.params.scope
        remainder = draws[((keys.code == scope.component_parameter_code)
                           & (keys.component == sodium.REMAINDER)).to_numpy()][0]
        feasible = remainder >= 0
        return keys, draws[:, feasible], float(feasible.mean())

    def _coarse(self, capacities) -> np.ndarray:
        targets = np.atleast_1d(np.asarray(capacities, dtype=float))
        if targets.size <= self.CURVE_POINTS:
            return targets
        return np.linspace(targets.min(), targets.max(), self.CURVE_POINTS)

    # ------------------------------------------------ the three questions
    def weights_at(self, capacity_kwh: float, *, chemistry: str, level: str = "component",
                   aggregate_elements: bool = False, **kwargs) -> pd.DataFrame:
        if not self.is_cell(chemistry):
            return self.model.weights_at(capacity_kwh, chemistry=chemistry, level=level,
                                         aggregate_elements=aggregate_elements, **kwargs)
        if level == "material":
            raise CompositionError(
                f"{chemistry} has no material level: it is built from literature and "
                "resolved at component and element level only.")
        scope, mc = self.params.scope, self.params.monte_carlo
        keys, draws, kept = self._block(chemistry, capacity_kwh)
        code = (scope.component_parameter_code if level == "component"
                else scope.element_parameter_code)
        wanted = (keys.code == code).to_numpy()
        subset, block = keys[wanted].reset_index(drop=True), draws[wanted]
        if level == "element" and aggregate_elements:
            grouped = subset.groupby("element").indices
            subset = pd.DataFrame({"element": list(grouped)})
            block = np.vstack([block[positions].sum(axis=0) for positions in grouped.values()])
        pack = self._pack_components()
        out = subset[["element"] if (level == "element" and aggregate_elements)
                     else (["component"] if level == "component"
                           else ["component", "element"])].copy()
        if "component" in out:
            out["branch"] = np.where(out["component"].isin(pack), "pack", "cell")
        out["capacity_kwh"] = float(capacity_kwh)
        out["mass_kg"] = np.median(block, axis=1)
        out[f"mass_p{mc.lower_percentile:g}"] = np.percentile(block, mc.lower_percentile, axis=1)
        out[f"mass_p{mc.upper_percentile:g}"] = np.percentile(block, mc.upper_percentile, axis=1)
        out["mass_mean"] = block.mean(axis=1)
        out["kg_per_kwh"] = out["mass_kg"] / float(capacity_kwh)
        out["extrapolated"] = float(capacity_kwh) > self._series.capacities[-1]
        out["kept"] = kept
        if "component" in out and "element" not in out:
            # cell components first, then the pack's, as the figures draw them
            out = out.sort_values(["branch", "component"], key=lambda column: (
                column.map({"cell": 0, "pack": 1}) if column.name == "branch" else column))
        return out.reset_index(drop=True)

    def component_curves(self, capacities, *, chemistry: str, level: str = "component") -> dict:
        if not self.is_cell(chemistry):
            return self.model.component_curves(capacities, chemistry=chemistry, level=level)
        scope, mc = self.params.scope, self.params.monte_carlo
        targets = self._coarse(capacities)
        pack = self._pack_components()
        names, central, lower, upper = None, [], [], []
        for capacity in targets:
            keys, draws, _ = self._block(chemistry, capacity)
            wanted = (keys.code == scope.component_parameter_code).to_numpy()
            if names is None:
                names = list(keys.component[wanted])
            block = draws[wanted]
            central.append(np.median(block, axis=1))
            lower.append(np.percentile(block, mc.lower_percentile, axis=1))
            upper.append(np.percentile(block, mc.upper_percentile, axis=1))
        # cell components first, then the pack's, each alphabetical
        order = sorted(range(len(names)), key=lambda i: (names[i] in pack, names[i]))
        pick = lambda rows: np.array(rows).T[order]          # (n_components, n_capacities)
        selected = pd.DataFrame({
            "chemistry": [scope.pack_level_key if names[i] in pack else chemistry
                          for i in order],
            "component": [names[i] for i in order]})
        anchors = self._series.capacities
        return {"keys": selected, "capacities": targets, "central": pick(central),
                "lower": pick(lower), "upper": pick(upper),
                "anchor_capacities": anchors,
                "anchor_mass": np.full((len(order), len(anchors)), np.nan)}

    def total_mass_curve(self, capacities, *, chemistry: str) -> pd.DataFrame:
        if not self.is_cell(chemistry):
            return self.model.total_mass_curve(capacities, chemistry=chemistry)
        scope, mc = self.params.scope, self.params.monte_carlo
        rows = []
        for capacity in self._coarse(capacities):
            keys, draws, kept = self._block(chemistry, capacity)
            total = draws[(keys.code == scope.component_parameter_code).to_numpy()].sum(axis=0)
            rows.append({
                "capacity_kwh": float(capacity), "chemistry": chemistry,
                "mass_kg": float(np.median(total)),
                f"mass_p{mc.lower_percentile:g}": float(np.percentile(total, mc.lower_percentile)),
                f"mass_p{mc.upper_percentile:g}": float(np.percentile(total, mc.upper_percentile)),
                "extrapolated": float(capacity) > self._series.capacities[-1],
                "kept": kept})
        return pd.DataFrame(rows)
