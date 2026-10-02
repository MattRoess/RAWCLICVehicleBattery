"""
src/sodium_composition.py
=========================

THE CELL OF A SODIUM-ION BATTERY, BUILT BOTTOM-UP AND DRAWN.

Sodium-ion had its packaging claimed from LFP and its cathode, anode and
electrolyte left as `unknownBatteryMaterial`, because no source existed
(`export.unknown_chemistry_template`). One arrived on 2026-10-02:
documentation/Sodium_Ion_Battery_CATL_Investigation.md and its addendum.

IT DOES NOT GIVE A BILL OF MATERIALS, and nothing here pretends it does. The
report says in terms that no audited whole-cell mass breakdown is public. What
it gives are the ingredients of an electrochemical mass balance -- cathode
capacity and voltage, hard-carbon capacity, the electrolyte class -- and this
module turns those into masses, each one a DISTRIBUTION.

THE MODEL, per battery of E Wh nominal, every symbol below a draw:

    cell        = E / D                           D   cell energy density, Wh/kg
    cathode     = E / (c * (Vc - Va))             c   cathode capacity, mAh/g (== Ah/kg)
                                                  Vc  cathode voltage vs Na, Va anode potential
    anode       = (E / (Vc - Va)) / qa * NP       qa  hard-carbon capacity, NP the N/P ratio
    electrolyte = e * (E / 1000)                  e   kg per kWh
    remainder   = cell - cathode - anode - electrolyte - packaging

THE REMAINDER IS A ROW, NOT A GAP AND NOT A GUESS. With the packaging already
claimed from the base chemistry, the cell at the stated energy density is
heavier than its electrochemistry explains: 65 kg of 400 at 80 kWh and 200 Wh/kg.
Neither document says where that mass is, so it is carried as its own component,
`batteryCellUnitemised`, instead of being poured into the cathode and anode --
which is what a split of the whole cell by lithium proportions did, and put the
cathode 27% too heavy. A reader sees it, sized, rather than inferring it.

EVERYTHING IS DRAWN ONCE PER MONTE CARLO DRAW AND SHARED across capacities,
years and rows: one uncertainty about one technology, not an independent error
per row, which would cancel in any sum and leave a total falsely certain.

DRAWS WITH A NEGATIVE REMAINDER ARE CONDITIONED OUT. A cell cannot be lighter
than its parts, so a draw whose density and electrochemistry contradict each
other is physically impossible. It is redrawn (the sodium inputs only) until
every anchor is consistent. Packaging, the improvement and the trust factor stay
where they are: they are shared with the rest of the pack, and moving them would
decouple a draw's sodium cell from its own frame. The remainder is NOT clipped.

NOTHING IN THIS FILE TOUCHES A FILE. The settings are `technology.sodium_cell`
and `technology.sodium_cathode`; `05_composition.py` feeds the result to both of
its output paths, so the CSV and the persisted arrays cannot disagree.
"""

from __future__ import annotations

import zlib
from typing import NamedTuple

import numpy as np

CATHODE = "cathodeActiveMaterial"
ANODE = "anodeActiveMaterial"
ELECTROLYTE = "batteryCellElectrolyte"
ACTIVE_COMPONENTS = (CATHODE, ANODE, ELECTROLYTE)

# The mass the cell carries that no source itemises. A component of its own.
REMAINDER = "batteryCellUnitemised"

# Standard atomic weights, g/mol. Physical constants, not settings.
ATOMIC_MASS = {
    "H": 1.008, "C": 12.011, "N": 14.007, "O": 15.999, "F": 18.998,
    "Na": 22.990, "Al": 26.982, "P": 30.974, "Ti": 47.867, "V": 50.942,
    "Mn": 54.938, "Fe": 55.845, "Ni": 58.693, "Cu": 63.546, "Li": 6.94,
}

_MAX_REDRAWS = 200

# The most draws that may be redrawn for a negative remainder before the settings
# are judged to contradict themselves. A DESIGN BOUND, not a measurement: past it
# the conditioning, rather than the stated distributions, would be what the
# inputs mean. Measured on the settings of 2026-10-02: 9.6% for the layered oxide
# and 18.3% for Prussian white, nearly all of it at the 25 kWh anchor, where the
# packaging inherited from LFP is 0.84 kg/kWh against 0.50 at 80.
MAX_REDRAWN_SHARE = 0.30


class SodiumCompositionError(ValueError):
    """Raised when the sodium cell model cannot be built or contradicts itself."""


class Inputs(NamedTuple):
    """One draw of every uncertain input, each shape (n_draws,)."""
    density: np.ndarray            # D,  Wh/kg of cell
    anode_capacity: np.ndarray     # qa, mAh/g
    np_ratio: np.ndarray           # NP
    anode_potential: np.ndarray    # Va, V vs Na
    electrolyte_per_kwh: np.ndarray  # e,  kg/kWh
    salt_fraction: np.ndarray      # share of the electrolyte that is salt
    capacity: np.ndarray           # c,  cathode mAh/g
    voltage: np.ndarray            # Vc, cathode V vs Na
    position: np.ndarray           # where the cathode formula sits between its two ends


class Masses(NamedTuple):
    """Base-year masses in kg, each (n_draws,)."""
    cathode: np.ndarray
    anode: np.ndarray
    electrolyte: np.ndarray
    remainder: np.ndarray
    cell: np.ndarray
    elements: dict            # component -> element -> kg


def is_sodium_cell(params, chemistry: str) -> bool:
    """Whether this chemistry's cell is built here rather than left unknown."""
    return chemistry in params.technology.sodium_cathode


def _band(values, name: str) -> tuple[float, float, float]:
    try:
        low, mode, high = (float(v) for v in values)
    except (TypeError, ValueError):
        raise SodiumCompositionError(
            f"{name} must be (min, mode, max), not {values!r}.") from None
    if not low <= mode <= high:
        raise SodiumCompositionError(
            f"{name} must satisfy min <= mode <= max: {low}, {mode}, {high}.")
    return low, mode, high


def _draw(rng: np.random.Generator, values, name: str, n: int) -> np.ndarray:
    low, mode, high = _band(values, name)
    if low == high:                      # a number, not a distribution
        return np.full(n, low)
    return rng.triangular(low, mode, high, n)


def draw_inputs(params, chemistry: str, n: int, rng: np.random.Generator) -> Inputs:
    """Every input drawn from its own triangular, in a fixed order."""
    cell = params.technology.sodium_cell
    cathode = params.technology.sodium_cathode[chemistry]
    return Inputs(
        density=_draw(rng, cell["energy_density_wh_per_kg"], "energy_density_wh_per_kg", n),
        anode_capacity=_draw(rng, cell["anode_capacity_mah_per_g"], "anode_capacity_mah_per_g", n),
        np_ratio=_draw(rng, cell["np_ratio"], "np_ratio", n),
        anode_potential=_draw(rng, cell["anode_potential_v"], "anode_potential_v", n),
        electrolyte_per_kwh=_draw(rng, cell["electrolyte_kg_per_kwh"], "electrolyte_kg_per_kwh", n),
        salt_fraction=_draw(rng, cell["salt_mass_fraction"], "salt_mass_fraction", n),
        capacity=_draw(rng, cathode["capacity_mah_per_g"], f"{chemistry} capacity_mah_per_g", n),
        voltage=_draw(rng, cathode["voltage_v"], f"{chemistry} voltage_v", n),
        position=_draw(rng, cathode["formula_position"], f"{chemistry} formula_position", n))


def mode_inputs(params, chemistry: str) -> Inputs:
    """Every input at its mode: the deterministic central case, shape (1,)."""
    cell = params.technology.sodium_cell
    cathode = params.technology.sodium_cathode[chemistry]

    def at_mode(values, name):
        return np.array([_band(values, name)[1]])
    return Inputs(
        density=at_mode(cell["energy_density_wh_per_kg"], "energy_density_wh_per_kg"),
        anode_capacity=at_mode(cell["anode_capacity_mah_per_g"], "anode_capacity_mah_per_g"),
        np_ratio=at_mode(cell["np_ratio"], "np_ratio"),
        anode_potential=at_mode(cell["anode_potential_v"], "anode_potential_v"),
        electrolyte_per_kwh=at_mode(cell["electrolyte_kg_per_kwh"], "electrolyte_kg_per_kwh"),
        salt_fraction=at_mode(cell["salt_mass_fraction"], "salt_mass_fraction"),
        capacity=at_mode(cathode["capacity_mah_per_g"], "capacity_mah_per_g"),
        voltage=at_mode(cathode["voltage_v"], "voltage_v"),
        position=at_mode(cathode["formula_position"], "formula_position"))


def _fractions(formula: dict, position: np.ndarray) -> dict[str, np.ndarray]:
    """Mass fraction of each element of the cathode, for a formula sitting at `position`."""
    counts = {element: ends[0] + (ends[1] - ends[0]) * position
              for element, ends in formula.items()}
    weight = sum(ATOMIC_MASS[element] * n for element, n in counts.items())
    return {element: ATOMIC_MASS[element] * n / weight for element, n in counts.items()}


def masses_at(params, chemistry: str, inputs: Inputs, capacity_kwh: float,
              packaging_kg: np.ndarray) -> Masses:
    """
    The cell of one battery of `capacity_kwh` nominal, base year.

    `packaging_kg` is what the base chemistry's casing, separator and collectors
    already weigh in each draw -- the part of the cell that is claimed, and so is
    not the remainder.
    """
    cell_settings = params.technology.sodium_cell
    energy = float(capacity_kwh) * 1000.0
    cell_voltage = inputs.voltage - inputs.anode_potential
    cathode = energy / (inputs.capacity * cell_voltage)
    anode = (energy / cell_voltage) / inputs.anode_capacity * inputs.np_ratio
    electrolyte = inputs.electrolyte_per_kwh * float(capacity_kwh)
    cell = energy / inputs.density
    remainder = cell - cathode - anode - electrolyte - np.asarray(packaging_kg)

    formula = params.technology.sodium_cathode[chemistry]["formula"]
    cathode_elements = {element: cathode * share
                        for element, share in _fractions(formula, inputs.position).items()}
    salt = cell_settings["salt_formula"]
    salt_weight = sum(ATOMIC_MASS[element] * n for element, n in salt.items())
    salt_mass = electrolyte * inputs.salt_fraction
    electrolyte_elements = {element: salt_mass * ATOMIC_MASS[element] * n / salt_weight
                            for element, n in salt.items()}
    return Masses(
        cathode=cathode, anode=anode, electrolyte=electrolyte, remainder=remainder,
        cell=cell,
        elements={CATHODE: cathode_elements, ANODE: {"C": anode},
                  ELECTROLYTE: electrolyte_elements})


def seed_for(params, chemistry: str) -> int:
    """
    A seed that is the same in every process.

    NOT `hash(chemistry)`: Python randomises string hashes per process, so a seed
    built from it changes between runs and the same settings give different
    draws. crc32 is stable.
    """
    return params.monte_carlo.random_seed + 3 + (zlib.crc32(chemistry.encode()) % 1000)


def conditioned_inputs(params, chemistry: str, n: int,
                       packaging_by_capacity: dict[float, np.ndarray]
                       ) -> tuple[Inputs, dict]:
    """
    Inputs for which the remainder is non-negative at EVERY capacity given.

    Returns (inputs, report): the share of the first pass that had to be redrawn,
    and how far conditioning moved the mean of each input. Only the columns that
    failed are redrawn, and only the sodium inputs: the packaging belongs to the
    rest of the pack and keeps its place in the draw.

    THE SAMPLER IS CHECKED BEFORE CONDITIONING, against the distributions as
    stated. After it, the means have moved -- that is what conditioning is -- and
    the move is reported rather than hidden inside a tolerance.
    """
    rng = np.random.default_rng(seed_for(params, chemistry))
    inputs = draw_inputs(params, chemistry, n, rng)
    verify_inputs(params, chemistry, inputs)
    original = Inputs(*(column.copy() for column in inputs))
    first_pass = None
    for _ in range(_MAX_REDRAWS):
        bad = np.zeros(n, dtype=bool)
        for capacity, packaging in packaging_by_capacity.items():
            bad |= masses_at(params, chemistry, inputs, capacity, packaging).remainder < 0
        if first_pass is None:
            first_pass = float(bad.mean())
            if first_pass > MAX_REDRAWN_SHARE:
                raise SodiumCompositionError(
                    f"{chemistry}: {100 * first_pass:.1f}% of draws have a negative "
                    f"remainder at some capacity, past the {100 * MAX_REDRAWN_SHARE:.0f}% "
                    "at which conditioning would be doing more than the stated "
                    "distributions. The cell energy density and the electrochemistry "
                    "contradict the packaging at these settings.")
        if not bad.any():
            shift = {name: float(new.mean() / old.mean() - 1.0)
                     for name, old, new in zip(Inputs._fields, original, inputs)}
            return inputs, {"redrawn": first_pass, "shift": shift}
        fresh = draw_inputs(params, chemistry, int(bad.sum()), rng)
        positions = np.flatnonzero(bad)
        inputs = Inputs(*(old.copy() for old in inputs))
        for column, replacement in zip(inputs, fresh):
            column[positions] = replacement
    raise SodiumCompositionError(
        f"{chemistry}: {int(bad.sum())} of {n:,} draws still have a negative "
        f"remainder after {_MAX_REDRAWS} redraws. The cell energy density and the "
        "electrochemistry cannot be reconciled with the packaging at these settings.")


def verify_inputs(params, chemistry: str, inputs: Inputs) -> None:
    """
    Each sampled input has the mean its own distribution says it should.

    Run on the draws BEFORE conditioning: it tests the sampler, and the
    conditioning's own effect is reported separately.
    """
    cell = params.technology.sodium_cell
    cathode = params.technology.sodium_cathode[chemistry]
    stated = {
        "density": cell["energy_density_wh_per_kg"],
        "anode_capacity": cell["anode_capacity_mah_per_g"],
        "np_ratio": cell["np_ratio"], "anode_potential": cell["anode_potential_v"],
        "electrolyte_per_kwh": cell["electrolyte_kg_per_kwh"],
        "salt_fraction": cell["salt_mass_fraction"],
        "capacity": cathode["capacity_mah_per_g"], "voltage": cathode["voltage_v"],
        "position": cathode["formula_position"],
    }
    n = len(inputs.density)
    for name, drawn in zip(Inputs._fields, inputs):
        expected = sum(float(v) for v in stated[name]) / 3.0
        tolerance = 5.0 * drawn.std(ddof=1) / np.sqrt(n) + 0.001 * abs(expected)
        if abs(drawn.mean() - expected) > tolerance:
            raise SodiumCompositionError(
                f"{chemistry}: the drawn {name} has mean {drawn.mean():.5g} where its "
                f"stated distribution {tuple(stated[name])} has {expected:.5g}.")
    low, _, high = _band(cathode["formula_position"], "formula_position")
    if inputs.position.min() < low - 1e-12 or inputs.position.max() > high + 1e-12:
        raise SodiumCompositionError(
            f"{chemistry}: the formula position left its range [{low}, {high}].")


def verify(params, chemistry: str, masses: Masses, capacity_kwh: float,
           packaging_kg: np.ndarray, wh_per_g_range: tuple[float, float]) -> None:
    """
    The invariants of the cell, executable. Raises on the first that fails.

    1. MASS CLOSES in every draw: the parts and the remainder sum to E / D.
       That holds by construction here; it is the guard for whoever changes how
       the remainder is made.
    2. ELEMENTS ADD UP to their component, in every draw.
    3. NO NEGATIVE MASS, the remainder included -- conditioning is what makes
       that true, and this is what notices if it stops being.
    4. THE CATHODE'S ENERGY PER GRAM sits near the lithium chemistries'. The
       range is measured from the workbook on every run and widened by 10%; it
       catches an error of a factor, not a modelling choice.
    """
    packaging = np.asarray(packaging_kg)
    gap = np.max(np.abs(masses.cathode + masses.anode + masses.electrolyte
                        + packaging + masses.remainder - masses.cell) / masses.cell)
    if gap > 1e-9:
        raise SodiumCompositionError(
            f"{chemistry} {capacity_kwh:.0f} kWh: the parts and the remainder miss "
            f"the cell mass by up to {gap:.1e} of it.")
    for component, total in ((CATHODE, masses.cathode), (ANODE, masses.anode)):
        itemised = sum(masses.elements[component].values())
        worst = np.max(np.abs(itemised - total) / total)
        if worst > 1e-9:
            raise SodiumCompositionError(
                f"{chemistry} {capacity_kwh:.0f} kWh: {component}'s elements miss "
                f"its mass by up to {worst:.1e} of it.")
    salt = sum(masses.elements[ELECTROLYTE].values())
    if np.any(salt > masses.electrolyte * (1.0 + 1e-9)):
        raise SodiumCompositionError(
            f"{chemistry} {capacity_kwh:.0f} kWh: the electrolyte's itemised salt "
            "exceeds the electrolyte.")
    for name, values in (("cathode", masses.cathode), ("anode", masses.anode),
                         ("electrolyte", masses.electrolyte),
                         ("remainder", masses.remainder)):
        if values.min() < 0:
            raise SodiumCompositionError(
                f"{chemistry} {capacity_kwh:.0f} kWh: the {name} is negative in "
                f"{int((values < 0).sum()):,} draws (smallest {values.min():.2f} kg).")
    energy_per_gram = float(capacity_kwh) * 1000.0 / masses.cathode / 1000.0
    low, high = 0.9 * wh_per_g_range[0], 1.1 * wh_per_g_range[1]
    median = float(np.median(energy_per_gram))
    if not low <= median <= high:
        raise SodiumCompositionError(
            f"{chemistry} {capacity_kwh:.0f} kWh: the cathode stores a median "
            f"{median:.3f} Wh/g, outside the lithium chemistries' "
            f"[{low:.3f}, {high:.3f}] (their range, widened by 10%).")
