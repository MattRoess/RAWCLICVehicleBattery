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

    def label(self, scenario: str) -> str:
        return self.settings.scenario_labels.get(scenario, scenario)
