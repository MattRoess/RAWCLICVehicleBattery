"""
src/composition.py
==================

The battery composition as a function of capacity.

The workbook gives five BEV sizes -- 25, 45, 60, 80 and 100 kWh. This module
turns those five anchors into an answer for ANY capacity: interpolated between
them, extrapolated beyond them, at component, material or element level, for any
cell chemistry, with a Monte Carlo band around it.

    from src.composition import CompositionModel
    model = CompositionModel(params)
    model.weights_at(150.0, chemistry="battLiNMC_midNi", level="component")

⚠️ ELEMENT LEVEL DOES NOT SUM TO COMPONENT LEVEL
--------------------------------------------------
About 13% of cell mass has no element breakdown, and it is NOT only the
components that carry no `e-c` row at all. Worked out from the workbook, for
NMC high-Ni at 60 kWh:

    batteryCellElectrolyte   loses 99% -- only its lithium is itemised
    batteryCellCasing        loses 100% -- no e-c rows
    batteryCellSeparator     loses 100% -- no e-c rows
    anodeActiveMaterial      +4% -- C plus Si slightly EXCEEDS the component total

The electrolyte is the largest term by far, not the casing. Anything reading
this product at element level alone is missing that mass silently, and
`02_composition_by_capacity.py --level element` prints the attribution per run
rather than repeating a remembered figure.

⚠️ WHICH kWh THIS MODEL EXPECTS
--------------------------------
NOMINAL capacity -- the pack's gross, stated figure. The composition workbook's
kg/kWh is per nominal kWh (confirmed 2026-09-08), so a useable figure passed in
here silently returns about 6% too little of everything (median useable/nominal
is 0.944). If a capacity comes from EV_details.csv, it must be
`battery_nominal_capacity`, which is what `ev_details.capacity_basis` defaults to.

WHAT IS INTERPOLATED, AND WHY IT IS MASS
-----------------------------------------
The workbook is in kg/kWh, but kg/kWh is the wrong thing to interpolate. A part
whose mass does not depend on capacity -- currentCollectorAnode on high-Ni is
21.4 kg at 25 kWh and 21.8 kg at 100 kWh -- has an intensity that falls 0.86 ->
0.22 kg/kWh purely because the denominator grew. Interpolating that hyperbola
mixes fixed-mass parts up with the ones that really do scale with capacity.
In kilograms the same part is a flat line and the curve means something. So
kg/kWh is multiplied up to kilograms, the interpolation happens there, and the
intensity is divided back out at the end.

BEYOND THE LAST ANCHOR
----------------------
Extrapolation is linear whatever `interpolation_method` says. A cubic continued
past its last knot diverges; at 150 kWh, half again beyond the largest sheet,
that is how a figure ends up with a negative cathode. Linear is not a claim that
the trend continues -- it is the least the data can be made to say.

Every value above 100 kWh is an extrapolation. The model marks them as such
(`extrapolated` column) rather than letting them pass as data.

THE UNCERTAINTY, AND WHAT IT IS WORTH
-------------------------------------
Every non-zero row of the workbook has min_value = 0.9 x Value and
max_value = 1.1 x Value -- all 805 of them, whether the value was consolidated
from 1 source or from 21, with DQS = 2 throughout. The spread is a flat +/-10%
convention, not an observed range. The Monte Carlo propagates it faithfully,
which means the band it produces is that convention carried through the
arithmetic, and NOT evidence about how well any of these numbers is known.

Because that band is proportional, a draw is one multiplicative factor per
series, shared across capacities (see `monte_carlo.correlate_across_capacities`).
`_factor_bounds` CHECKS that the workbook really is proportional rather than
assuming it, and raises if it ever stops being -- at which point the factor
model no longer fits and this module needs reworking, not patching.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator

from src.params_schema import Params

# Series identity: one curve of mass against capacity.
SERIES_KEYS = ["chemistry", "component", "element", "code"]

LEVELS = ("component", "material", "element")

# The workbook's proportional band has to hold to this tolerance for the
# one-factor-per-series model to be exact.
_PROPORTIONAL_TOLERANCE = 1e-9


class CompositionError(ValueError):
    """Raised when the workbook cannot support what is being asked of it."""


@dataclass
class _Series:
    """Every series' anchors, aligned on one shared capacity axis."""

    keys: pd.DataFrame          # (n_series, 4) the SERIES_KEYS
    capacities: np.ndarray      # (n_anchors,) ascending
    mass: np.ndarray            # (n_series, n_anchors) kilograms
    low_ratio: np.ndarray       # (n_series,) min_value / Value
    high_ratio: np.ndarray      # (n_series,) max_value / Value


class CompositionModel:
    """The workbook, read once, answerable at any capacity."""

    def __init__(self, params: Params, project_root=None):
        from pathlib import Path

        self.params = params
        root = Path(project_root) if project_root else Path(__file__).resolve().parent.parent
        self._path = params.composition_path(root)
        self.anchors = self._load()
        self._series = self._build_series()
        self._factors: np.ndarray | None = None

    # ---------------------------------------------------------------- loading
    def _load(self) -> pd.DataFrame:
        if not self._path.exists():
            raise CompositionError(
                f"Input workbook not found: {self._path}\n"
                "Nothing under data/ is tracked in git -- copy the workbook in from iCloud.")

        scope = self.params.scope
        frames = []
        for capacity, sheet_name in zip(scope.bev_capacities_kwh, self.params.sheet_names()):
            # keep_default_na=False: 'Layer 4' holds a literal 'n/a' on every row
            # that is not at element level. Under pandas' defaults that becomes
            # NaN and the levels of detail stop being distinguishable.
            frame = pd.read_excel(self._path, sheet_name=sheet_name,
                                  keep_default_na=False, na_values=[""])
            frames.append(frame.assign(kwh=float(capacity)))

        rows = pd.concat(frames, ignore_index=True).rename(columns={
            "Layer 1": "chemistry", "Layer 2": "component", "Layer 4": "element",
            "parameterCode": "code", "Value": "intensity",
        })
        rows["mass_kg"] = rows["intensity"] * rows["kwh"]
        return rows

    def _build_series(self) -> _Series:
        anchors = np.array(sorted(float(c) for c in self.params.scope.bev_capacities_kwh))
        rows = self.anchors

        pivot = rows.pivot_table(index=SERIES_KEYS, columns="kwh", values="mass_kg")
        missing = pivot.isna()
        if missing.to_numpy().any():
            incomplete = pivot.index[missing.any(axis=1)].tolist()[:5]
            raise CompositionError(
                f"{missing.any(axis=1).sum()} series are not present at every "
                f"capacity, e.g. {incomplete}. A curve cannot be built through a "
                "gap; fix the workbook or narrow scope.bev_capacities_kwh.")
        pivot = pivot[anchors]

        low, high = self._factor_bounds(rows, pivot.index)
        return _Series(
            keys=pivot.index.to_frame(index=False),
            capacities=anchors,
            mass=pivot.to_numpy(dtype=float),
            low_ratio=low,
            high_ratio=high,
        )

    def _factor_bounds(self, rows: pd.DataFrame, index) -> tuple[np.ndarray, np.ndarray]:
        """
        The multiplicative band per series -- CHECKED to be the same at every
        capacity, not assumed.

        The whole one-factor-per-series Monte Carlo rests on min_value and
        max_value being a fixed proportion of Value. That is true of this
        workbook (0.9 and 1.1 everywhere). If a future version carries a real,
        per-capacity range instead, this raises rather than quietly applying a
        model that no longer describes the data.
        """
        mc = self.params.monte_carlo
        if not mc.use_workbook_min_max:
            n = len(index)
            return (np.full(n, 1.0 - mc.relative_band), np.full(n, 1.0 + mc.relative_band))

        usable = rows[rows["intensity"] > 0].copy()
        usable["low_ratio"] = usable["min_value"] / usable["intensity"]
        usable["high_ratio"] = usable["max_value"] / usable["intensity"]
        spread = usable.groupby(SERIES_KEYS)[["low_ratio", "high_ratio"]].agg(["min", "max"])
        drift = float(np.nanmax([
            (spread[("low_ratio", "max")] - spread[("low_ratio", "min")]).max(),
            (spread[("high_ratio", "max")] - spread[("high_ratio", "min")]).max(),
        ]))
        if drift > _PROPORTIONAL_TOLERANCE:
            raise CompositionError(
                f"min_value/max_value are no longer a fixed proportion of Value: they "
                f"vary by up to {drift:.3g} across the capacities of one series. The "
                "Monte Carlo here draws ONE factor per series precisely because that "
                "proportion has always been constant (0.9 and 1.1). It now has to be "
                "reworked to draw per capacity -- not patched to ignore this.")

        # The ratio is constant across capacities (just checked), so either end
        # of the aggregate is the ratio. A series that is zero at every capacity
        # has no ratio at all; its band is zero wide, which is right -- zero
        # times anything is still zero.
        low = spread[("low_ratio", "min")].reindex(index).fillna(1.0).to_numpy(dtype=float)
        high = spread[("high_ratio", "max")].reindex(index).fillna(1.0).to_numpy(dtype=float)
        if low.size != len(index):
            raise CompositionError(
                f"the band could not be resolved one-per-series: {low.size} bounds "
                f"for {len(index)} series. This means SERIES_KEYS no longer "
                "identifies a series uniquely in the workbook.")
        return low, high

    # ---------------------------------------------------- central curve
    def central_mass(self, capacities) -> np.ndarray:
        """Mass in kg, shape (n_series, n_capacities), at any capacities."""
        interp = self.params.interpolation
        targets = np.atleast_1d(np.asarray(capacities, dtype=float))

        below = targets < interp.min_capacity_kwh
        above = targets > interp.max_capacity_kwh
        if below.any() or above.any():
            offending = sorted(set(targets[below].tolist() + targets[above].tolist()))
            raise CompositionError(
                f"capacity {offending} kWh is outside the range this model will "
                f"answer for, [{interp.min_capacity_kwh}, {interp.max_capacity_kwh}] "
                "kWh (interpolation.min/max_capacity_kwh).")

        series = self._series
        x, y = series.capacities, series.mass
        out = np.empty((y.shape[0], targets.size), dtype=float)

        inside = (targets >= x[0]) & (targets <= x[-1])
        if inside.any():
            if interp.interpolation_method == "pchip":
                out[:, inside] = PchipInterpolator(x, y, axis=-1)(targets[inside])
            else:
                out[:, inside] = np.stack(
                    [np.interp(targets[inside], x, row) for row in y])

        # Linear continuation outside the anchors, in both directions.
        for mask, (x_edge, slope) in (
            (targets < x[0], (x[0], self._edge_slope("low"))),
            (targets > x[-1], (x[-1], self._edge_slope("high"))),
        ):
            if not mask.any():
                continue
            base = y[:, 0] if x_edge == x[0] else y[:, -1]
            out[:, mask] = base[:, None] + slope[:, None] * (targets[mask] - x_edge)[None, :]

        if interp.clamp_negative_mass:
            negative = out < 0
            if negative.any():
                affected = series.keys.iloc[np.unique(np.where(negative)[0])]
                print(f"NOTE: linear extrapolation went below zero for "
                      f"{len(affected)} series; clamped to 0. Worst offenders: "
                      f"{affected['component'].unique()[:4].tolist()}")
                out = np.clip(out, 0.0, None)
        return out

    def _edge_slope(self, side: str) -> np.ndarray:
        """kg per kWh continued past the anchors, per series."""
        x, y = self._series.capacities, self._series.mass
        if self.params.interpolation.extrapolation == "fit":
            centred = x - x.mean()
            return (y - y.mean(axis=1, keepdims=True)) @ centred / (centred @ centred)
        if side == "low":
            return (y[:, 1] - y[:, 0]) / (x[1] - x[0])
        return (y[:, -1] - y[:, -2]) / (x[-1] - x[-2])

    # ------------------------------------------------------------ Monte Carlo
    def factor_draws(self) -> np.ndarray:
        """
        One multiplicative factor per series per draw, shape (n_series, n_draws).

        Sampled once and reused: the same draw has to mean the same error
        wherever it is applied, or summing components would cancel errors that
        are in fact the same error.
        """
        if self._factors is not None:
            return self._factors

        mc = self.params.monte_carlo
        low, high = self._series.low_ratio, self._series.high_ratio
        rng = np.random.default_rng(mc.random_seed)
        size = (low.size, mc.n_draws)

        if mc.distribution == "uniform":
            factors = rng.uniform(low[:, None], high[:, None], size=size)
        else:
            # Triangular with the workbook's Value as the mode: the consolidated
            # central estimate stays the most likely outcome.
            mode = np.ones_like(low)
            degenerate = high <= low          # a zero-width band cannot be sampled
            factors = np.empty(size)
            factors[degenerate] = low[degenerate, None]
            live = ~degenerate
            if live.any():
                factors[live] = rng.triangular(
                    low[live, None], mode[live, None], high[live, None],
                    size=(int(live.sum()), mc.n_draws))
        self._factors = factors
        return factors

    def mass_draws_at(self, capacity: float) -> np.ndarray:
        """
        Mass in kg per series per draw at ONE capacity, shape (n_series, n_draws).

        Kept to a single capacity on purpose. Draws at every capacity at once
        would be n_series x n_draws x n_capacities -- gigabytes for a figure --
        and nothing needs them all in memory at the same time.
        """
        central = self.central_mass(capacity)[:, 0]
        if not self.params.monte_carlo.enabled:
            return central[:, None]
        return central[:, None] * self.factor_draws()

    # ------------------------------------------------------------ public API
    def weights_at(self, capacity_kwh: float, *, chemistry: str,
                   level: str = "component", aggregate_elements: bool = False) -> pd.DataFrame:
        """
        What a battery of `capacity_kwh` is made of.

        Parameters
        ----------
        capacity_kwh : NOMINAL capacity in kWh -- the workbook's kg/kWh is per
            nominal kWh, so a useable figure returns ~6% too little of
            everything. Must be inside interpolation.min/max_capacity_kwh;
            above the largest anchor the answer is extrapolated, and the
            `extrapolated` column says so.
        chemistry : a Layer 1 cell chemistry, e.g. 'battLiNMC_midNi'. The
            pack-level components (Layer 1 = battPackXEV) are always included --
            they are part of the product whatever chemistry is inside it.
        level : 'component' (c-p), 'material' (m-c) or 'element' (e-c).
        aggregate_elements : at element level, sum each element across
            components instead of listing it per component.

        Returns
        -------
        One row per component (or per element), with mass_kg, kg_per_kwh, and --
        when the Monte Carlo is on -- the percentile band around the mass.
        """
        if level not in LEVELS:
            raise CompositionError(f"level must be one of {LEVELS}: {level!r}")

        scope, mc = self.params.scope, self.params.monte_carlo
        code = {"component": scope.component_parameter_code,
                "material": scope.material_parameter_code,
                "element": scope.element_parameter_code}[level]

        keys = self._series.keys
        known = set(keys["chemistry"]) - {scope.pack_level_key}
        if chemistry not in known:
            raise CompositionError(
                f"unknown chemistry {chemistry!r}. The workbook has: {sorted(known)}")

        wanted = (keys["code"] == code) & keys["chemistry"].isin([chemistry, scope.pack_level_key])
        if not wanted.any():
            raise CompositionError(
                f"no rows at level {level!r} (parameterCode {code!r}) for chemistry "
                f"{chemistry!r}. Not every component is resolved at every level -- "
                "batteryCellCasing and batteryCellSeparator have no element rows at "
                "all, for instance.")

        draws = self.mass_draws_at(capacity_kwh)[wanted.to_numpy()]
        central = self.central_mass(capacity_kwh)[wanted.to_numpy(), 0]

        out = keys[wanted].reset_index(drop=True).copy()
        out["capacity_kwh"] = float(capacity_kwh)
        out["branch"] = np.where(out["chemistry"] == scope.pack_level_key, "pack", "cell")
        out["mass_kg"] = central

        if level == "element" and aggregate_elements:
            # Summing has to happen on the DRAWS, not on the percentiles: the
            # 97.5th percentile of a sum is not the sum of the 97.5th percentiles.
            grouped = out.groupby("element").indices
            rows = []
            for element, positions in grouped.items():
                summed = draws[positions].sum(axis=0)
                rows.append({"element": element,
                             "capacity_kwh": float(capacity_kwh),
                             "mass_kg": float(central[positions].sum()),
                             "_draws": summed})
            out = pd.DataFrame(rows)
            draws = np.stack([row for row in out.pop("_draws")])

        if mc.enabled:
            out[f"mass_p{mc.lower_percentile:g}"] = np.percentile(draws, mc.lower_percentile, axis=1)
            out[f"mass_p{mc.upper_percentile:g}"] = np.percentile(draws, mc.upper_percentile, axis=1)
            out["mass_mean"] = draws.mean(axis=1)

        out["kg_per_kwh"] = out["mass_kg"] / float(capacity_kwh)
        out["extrapolated"] = float(capacity_kwh) > self._series.capacities[-1]
        return out.reset_index(drop=True)

    def total_mass_curve(self, capacities, *, chemistry: str) -> pd.DataFrame:
        """Whole-battery mass against capacity, with its band, for one chemistry."""
        scope, mc = self.params.scope, self.params.monte_carlo
        keys = self._series.keys
        wanted = ((keys["code"] == scope.component_parameter_code)
                  & keys["chemistry"].isin([chemistry, scope.pack_level_key])).to_numpy()

        # Select the series FIRST, then draw. Multiplying the full 199-series
        # array by 20,000 draws at every one of a few hundred capacities is
        # gigabytes of allocation for twelve rows of answer.
        targets = np.atleast_1d(np.asarray(capacities, dtype=float))
        central_selected = self.central_mass(targets)[wanted]
        factors = self.factor_draws()[wanted] if mc.enabled else None

        rows = []
        for index, capacity in enumerate(targets):
            central = float(central_selected[:, index].sum())
            draws = ((central_selected[:, index][:, None] * factors).sum(axis=0)
                     if mc.enabled else np.array([central]))
            row = {"capacity_kwh": float(capacity), "chemistry": chemistry,
                   "mass_kg": central,
                   "extrapolated": float(capacity) > self._series.capacities[-1]}
            if mc.enabled:
                row[f"mass_p{mc.lower_percentile:g}"] = float(np.percentile(draws, mc.lower_percentile))
                row[f"mass_p{mc.upper_percentile:g}"] = float(np.percentile(draws, mc.upper_percentile))
            rows.append(row)
        return pd.DataFrame(rows)

    def component_curves(self, capacities, *, chemistry: str, level: str = "component") -> dict:
        """Per-component mass curves with bands -- what the small multiples draw."""
        scope, mc = self.params.scope, self.params.monte_carlo
        code = {"component": scope.component_parameter_code,
                "material": scope.material_parameter_code,
                "element": scope.element_parameter_code}[level]
        keys = self._series.keys
        wanted = ((keys["code"] == code)
                  & keys["chemistry"].isin([chemistry, scope.pack_level_key])).to_numpy()
        selected = keys[wanted].reset_index(drop=True)

        targets = np.atleast_1d(np.asarray(capacities, dtype=float))
        central = self.central_mass(targets)[wanted]
        lower = np.empty_like(central)
        upper = np.empty_like(central)
        # Same reason as in total_mass_curve: slice the series, then draw.
        factors = self.factor_draws()[wanted] if mc.enabled else None
        for index in range(targets.size):
            if not mc.enabled:
                lower[:, index] = upper[:, index] = central[:, index]
                continue
            draws = central[:, index][:, None] * factors
            lower[:, index] = np.percentile(draws, mc.lower_percentile, axis=1)
            upper[:, index] = np.percentile(draws, mc.upper_percentile, axis=1)

        anchor_mass = self._series.mass[wanted]
        return {"keys": selected, "capacities": targets, "central": central,
                "lower": lower, "upper": upper,
                "anchor_capacities": self._series.capacities, "anchor_mass": anchor_mass}
