"""
src/scenarios.py
================

Cathode-chemistry mix to 2070, under three scenarios.

    from src.scenarios import ChemistryScenarios
    ChemistryScenarios(current()).shares("scenario_2")

⚠️ THESE ARE ASSUMPTIONS, NOT RESULTS. The observed data ends in 2026; every
year after that is a written-down judgement in `scenarios.*`, interpolated. The
class carries the label and the likelihood so no output can present a scenario
as a forecast.

WHAT IT CAN AND CANNOT TELL YOU
--------------------------------
It gives the SHARE of each chemistry, per segment group, per year. It does not
give material mass for sodium-ion or bipolar solid-state, because the
composition workbook has neither and neither is a variant of what it has:
sodium replaces the copper anode current collector with aluminium, and bipolar
solid-state deletes the separator, the liquid electrolyte and the per-cell
terminals outright. `composition_coverage` reports how much of each scenario-year
can be costed in materials at all, so the gap is visible instead of being filled
with a lookalike chemistry.

THE OUTFLOW LAG, WHICH IS EASY TO FORGET
-----------------------------------------
These are shares of what is SOLD. With a ~15-year vehicle life, what returns for
recycling in 2050 is roughly what was sold in 2035, so the scenarios barely
separate on recovered materials before about 2045 -- everything coming back
before then is already on the road, and it is NMC and NCA. Anyone reading these
curves as recycling input is reading them fifteen years early.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.params_schema import Params

SCENARIO_NAMES = ("scenario_1", "scenario_2", "scenario_3")


class ScenarioError(ValueError):
    """Raised when a scenario cannot be built as written."""


class ChemistryScenarios:
    """The scenario definitions, resolved into yearly shares."""

    def __init__(self, params: Params):
        self.params = params
        self.settings = params.scenarios

    def years(self, last_year: int = 2070) -> np.ndarray:
        first = int(min(self.settings.anchor_years))
        if last_year < max(self.settings.anchor_years):
            last_year = int(max(self.settings.anchor_years))
        return np.arange(first, last_year + 1, dtype=float)

    def shares(self, scenario: str, last_year: int = 2070) -> pd.DataFrame:
        """
        Long frame: scenario, segment_group, chemistry, year, share (0-1).

        Between anchors the share is interpolated linearly; outside them it is
        held flat. Linear on purpose -- these are assumptions, and a smoother
        would invent turns between anchors that nobody chose.
        """
        if scenario not in SCENARIO_NAMES:
            raise ScenarioError(f"unknown scenario {scenario!r}; expected {SCENARIO_NAMES}.")

        definition = getattr(self.settings, scenario)
        anchors = np.asarray(self.settings.anchor_years, dtype=float)
        years = self.years(last_year)
        rows = []

        for group, chemistries in definition.items():
            resolved = {chemistry: np.interp(years, anchors, np.asarray(shares, dtype=float))
                        for chemistry, shares in chemistries.items()}
            total = np.sum(list(resolved.values()), axis=0)
            if np.any(total <= 0):
                raise ScenarioError(
                    f"{scenario}.{group} has all shares at zero in some year -- there "
                    "would be no market to divide.")
            for chemistry, series in resolved.items():
                # Normalise: the anchors are written by hand and validate() only
                # rejects drift beyond 5 points, so small slips are corrected
                # here rather than quietly distorting a share.
                rows.append(pd.DataFrame({
                    "scenario": scenario, "segment_group": group,
                    "chemistry": chemistry, "year": years,
                    "share": series / total,
                }))
        return pd.concat(rows, ignore_index=True)

    def all_shares(self, last_year: int = 2070) -> pd.DataFrame:
        return pd.concat([self.shares(name, last_year) for name in SCENARIO_NAMES],
                         ignore_index=True)

    def composition_coverage(self, last_year: int = 2070) -> pd.DataFrame:
        """
        Per scenario, group and year: what fraction of the market has a
        composition in the workbook at all.

        This is the number that decides whether a material result can be
        computed, and it falls a long way in scenarios 2 and 3. Reporting it is
        the alternative to substituting a lookalike chemistry and hoping.
        """
        missing = set(self.settings.chemistries_without_composition)
        frame = self.all_shares(last_year)
        frame["covered"] = np.where(frame.chemistry.isin(missing), 0.0, frame.share)
        return (frame.groupby(["scenario", "segment_group", "year"])["covered"].sum()
                .rename("share_with_composition").reset_index())

    # ------------------------------------------------------- what comes back
    def returning_shares(self, scenario: str, *, extra_years: int | None = None,
                         last_year: int = 2070) -> pd.DataFrame:
        """
        The chemistry mix ARRIVING AT THE RECYCLER, per year -- not the mix
        being sold.

        Two delays, and they are the whole point:

          straight from the car   sold in Y - lifetime
          via second life         sold in Y - lifetime - extra_years

        so a return year draws on two different sales years at once, weighted by
        `second_life.second_life_share` per chemistry. LFP is diverted most,
        which means an LFP-heavy scenario is also the one whose material comes
        back latest.

        ⚠️ ASSUMES CONSTANT ANNUAL SALES VOLUME. Only shares are available here,
        so a year with twice the sales weighs the same as one with half. Real
        volumes come from the stock-and-flow model, and until they are joined in
        this is the mix of a hypothetical flat market, not of the actual fleet.
        Growth means the recent, later-chemistry years are under-weighted here,
        so the true return mix is a little more modern than this shows.
        """
        settings = self.params.second_life
        if extra_years is None:
            extra_years = int(round((settings.second_life_extra_years_min
                                     + settings.second_life_extra_years_max) / 2))

        sold = self.shares(scenario, last_year)
        lifetime = settings.vehicle_lifetime_years
        rows = []

        for group, group_frame in sold.groupby("segment_group"):
            wide = group_frame.pivot_table(index="year", columns="chemistry",
                                           values="share").fillna(0.0)
            # Sales before the first anchor are held at the first year's mix --
            # the same flat-hold used before the anchors, not an extrapolation.
            def sold_mix(year: float) -> pd.Series:
                if year <= wide.index.min():
                    return wide.iloc[0]
                if year >= wide.index.max():
                    return wide.iloc[-1]
                return wide.loc[year]

            first_return = float(wide.index.min()) + lifetime
            for year in np.arange(first_return, last_year + 1, dtype=float):
                direct = sold_mix(year - lifetime)
                delayed = sold_mix(year - lifetime - extra_years)
                mix = {}
                for chemistry in wide.columns:
                    diverted = (settings.second_life_share.get(chemistry, 0.0)
                                if settings.enabled else 0.0)
                    mix[chemistry] = (direct.get(chemistry, 0.0) * (1 - diverted)
                                      + delayed.get(chemistry, 0.0) * diverted)
                total = sum(mix.values())
                for chemistry, value in mix.items():
                    rows.append({"scenario": scenario, "segment_group": group,
                                 "chemistry": chemistry, "year": year,
                                 "share": value / total if total else 0.0,
                                 "extra_years": extra_years})
        return pd.DataFrame(rows)

    def label(self, scenario: str) -> str:
        return self.settings.scenario_labels.get(scenario, scenario)
