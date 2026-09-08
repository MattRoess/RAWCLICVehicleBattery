"""
src/ev_details.py
=================

Battery capacity against year, per vehicle segment, from the EV-database table.

    from src.ev_details import EVDetails
    ev = EVDetails(current())
    ev.curve("JC")          # the smoothed capacity curve for segment JC

WHAT THE FILE GIVES, AND WHAT HAS TO BE MADE OF IT
---------------------------------------------------
`EV_details.csv` is one row per model VARIANT, not per car: the Tesla Model
range appears 84 times with capacities from 49 to 98 kWh, the Hyundai IONIQ 25
times from 28 to 106. That spread is the market, not an error, and it is the
first of the two uncertainties drawn.

Availability comes as free text per country -- "Since March 2021",
"Oct 2022 - Feb 2026", "Not Available", "Expected June 2026" -- in six patterns
and no others (checked against all 3,948 entries). `_parse_window` reads them
into a first and last year and refuses anything it does not recognise rather
than guessing.

A variant is then counted in EVERY year its availability window covers, so the
series answers "what was on sale that year" rather than "what launched that
year". `count_every_year_on_sale` switches that off.

WHY THE CURVE IS NOT A STRAIGHT LINE
-------------------------------------
Capacity per segment climbs through the early 2020s and then flattens. A
straight line through that either understates the recent years or overstates
the early ones, and extrapolates the wrong slope off the end. What is fitted
instead is a local linear regression with Gaussian weights -- LOESS in all but
name -- run on the individual variants rather than on yearly averages, so a year
with forty models weighs more than a year with four.

THE TWO BANDS ARE NOT THE SAME QUANTITY
----------------------------------------
  market spread   -- the p10-p90 of the models actually on sale that year. Real
                     dispersion. It does not shrink as more data arrives.
  curve band      -- how far the fitted line would move if the market had held a
                     different sample of models. Bootstrapped by resampling
                     MODELS, never model-years: one car on sale for eight years
                     is one observation of the market, not eight, and resampling
                     the years would shrink this band to nothing.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.params_schema import Params

# The six patterns the availability field actually uses. Anything else is
# reported, not guessed at.
_RANGE = re.compile(r"^([A-Z][a-z]{2})\s+((?:19|20)\d{2})\s*-\s*([A-Z][a-z]{2})\s+((?:19|20)\d{2})$")
_SINCE = re.compile(r"^Since\s+([A-Za-z]+)\s+((?:19|20)\d{2})$")
_EXPECTED = re.compile(r"^Expected\s+([A-Za-z]+)\s+((?:19|20)\d{2})$")
_SINGLE = re.compile(r"^([A-Z][a-z]{2})\s+((?:19|20)\d{2})$")
_UNAVAILABLE = ("Not Available", "Not available to order")


class EVDetailsError(ValueError):
    """Raised when the file cannot support what is being asked of it."""


@dataclass
class SegmentCurve:
    """One segment's answer: the curve, both bands, and what it was fitted to."""

    segment: str
    years: np.ndarray            # the grid the curve is drawn on
    central: np.ndarray          # the smoothed capacity, kWh
    spread_low: np.ndarray       # market spread, lower percentile
    spread_high: np.ndarray
    band_low: np.ndarray         # curve uncertainty, bootstrap
    band_high: np.ndarray
    effective_n: np.ndarray      # models within one bandwidth of each year
    points: pd.DataFrame         # the model-years behind it
    n_models: int                # distinct models, not model-years


def _first_number(text) -> float:
    if pd.isna(text):
        return np.nan
    match = re.search(r"[-+]?\d*\.?\d+", str(text).replace(",", ""))
    return float(match.group()) if match else np.nan


def _parse_window(raw: str, *, include_expected: bool) -> tuple[float, float]:
    """One country's availability string -> (first year, last year or NaN)."""
    text = str(raw).strip()
    if text in _UNAVAILABLE:
        return (np.nan, np.nan)
    match = _RANGE.match(text)
    if match:
        return (float(match.group(2)), float(match.group(4)))
    match = _SINCE.match(text)
    if match:
        return (float(match.group(2)), np.nan)          # still on sale
    match = _EXPECTED.match(text)
    if match:
        return (float(match.group(2)), np.nan) if include_expected else (np.nan, np.nan)
    match = _SINGLE.match(text)
    if match:
        return (float(match.group(2)), np.nan)
    raise EVDetailsError(
        f"unrecognised availability string: {text!r}. The parser knows six "
        "patterns and refuses to guess at a seventh -- add it to src/ev_details.py "
        "once you have decided what it means.")


class EVDetails:
    """The EV-database table, parsed once and smoothable per segment."""

    def __init__(self, params: Params, project_root=None):
        from pathlib import Path

        self.params = params
        root = Path(project_root) if project_root else Path(__file__).resolve().parent.parent
        self._path = params.ev_details_path(root)
        self.models = self._load()
        self.panel = self._expand_to_model_years()

    # ---------------------------------------------------------------- loading
    def _load(self) -> pd.DataFrame:
        ev = self.params.ev_details
        if not self._path.exists():
            raise EVDetailsError(
                f"EV details file not found: {self._path}\n"
                "Nothing under data/ is tracked in git -- copy it in from iCloud.")

        raw = pd.read_csv(self._path, low_memory=False)
        column = ("battery_useable_capacity" if ev.capacity_basis == "useable"
                  else "battery_nominal_capacity")

        frame = pd.DataFrame({
            "car_id": raw["car_id"],
            "name": raw["name"],
            # 'JC - Medium' -> 'JC'. The code before the dash is the segment the
            # stock-and-flow model also uses.
            "segment": raw["miscellaneous_segment"].astype(str).str.split(" - ").str[0],
            "capacity_kwh": raw[column].map(_first_number),
        })

        windows = [self._model_window(value) for value in raw["availability_json"]]
        frame["first_year"] = [start for start, _ in windows]
        frame["last_year"] = [end for _, end in windows]

        usable = frame.dropna(subset=["capacity_kwh", "first_year"]).copy()
        dropped = len(frame) - len(usable)
        if dropped:
            print(f"[ev_details] {dropped} of {len(frame)} rows dropped: no capacity "
                  f"or no availability date for {ev.availability_country}.")
        return usable.reset_index(drop=True)

    def _model_window(self, availability_json) -> tuple[float, float]:
        """One model's window, from the chosen country or across all of them."""
        ev = self.params.ev_details
        if pd.isna(availability_json):
            return (np.nan, np.nan)
        try:
            entries = json.loads(availability_json)
        except (TypeError, ValueError):
            return (np.nan, np.nan)

        windows = []
        for entry in entries:
            country = entry.get("country")
            if ev.availability_country not in ("any", country):
                continue
            start, end = _parse_window(entry.get("value", ""),
                                       include_expected=ev.include_expected)
            if not np.isnan(start):
                windows.append((start, end))
        if not windows:
            return (np.nan, np.nan)

        starts = [start for start, _ in windows]
        ends = [end for _, end in windows]
        # An open window anywhere means still on sale: NaN wins over a date.
        return (min(starts), np.nan if any(np.isnan(ends)) else max(ends))

    def _expand_to_model_years(self) -> pd.DataFrame:
        """One row per model per year it was on sale."""
        ev = self.params.ev_details
        rows = []
        for model in self.models.itertuples():
            start = int(model.first_year)
            if not ev.count_every_year_on_sale:
                years = [start]
            else:
                end = (ev.open_window_end_year if np.isnan(model.last_year)
                       else int(model.last_year))
                years = range(start, min(end, ev.open_window_end_year) + 1)
            for year in years:
                if ev.first_year <= year <= ev.last_year:
                    rows.append((model.car_id, model.name, model.segment,
                                 float(year), model.capacity_kwh))
        panel = pd.DataFrame(rows, columns=["car_id", "name", "segment", "year", "capacity_kwh"])
        if panel.empty:
            raise EVDetailsError(
                "no model-years survived the filters -- check ev_details.first_year, "
                "last_year and availability_country.")
        return panel

    # ------------------------------------------------------------- smoothing
    def _weights(self, years: np.ndarray, grid: np.ndarray) -> np.ndarray:
        """Gaussian weight of every observation at every point of the grid."""
        bandwidth = self.params.ev_details.smoothing_bandwidth_years
        distance = (years[:, None] - grid[None, :]) / bandwidth
        return np.exp(-0.5 * distance ** 2)

    @staticmethod
    def _local_linear(years, values, grid, weights) -> np.ndarray:
        """
        Weighted local LINEAR fit at each grid point, not a weighted mean.

        A local mean flattens a trend at the ends of the range -- exactly where
        the recent years are, and exactly where the answer matters most. The
        linear term removes that bias.
        """
        total = weights.sum(axis=0)
        centred = years[:, None] - grid[None, :]
        weighted_x = (weights * centred).sum(axis=0)
        weighted_xx = (weights * centred ** 2).sum(axis=0)
        weighted_y = (weights * values[:, None]).sum(axis=0)
        weighted_xy = (weights * centred * values[:, None]).sum(axis=0)

        determinant = total * weighted_xx - weighted_x ** 2
        # Where the fit is singular (all points on one year) fall back to the
        # weighted mean rather than dividing by zero.
        safe = np.abs(determinant) > 1e-9
        out = np.divide(weighted_y, total, out=np.full_like(total, np.nan),
                        where=total > 0)
        out[safe] = ((weighted_xx * weighted_y - weighted_x * weighted_xy) / determinant)[safe]
        return out

    @staticmethod
    def _weighted_quantile(values: np.ndarray, weights: np.ndarray, q: float) -> float:
        """Quantile of the models near this year, each weighted by how near."""
        if weights.sum() <= 0:
            return np.nan
        order = np.argsort(values)
        values, weights = values[order], weights[order]
        cumulative = np.cumsum(weights) - 0.5 * weights
        cumulative /= weights.sum()
        return float(np.interp(q / 100.0, cumulative, values))

    def curve(self, segment: str) -> SegmentCurve:
        """The smoothed capacity curve for one segment, with both bands."""
        ev = self.params.ev_details
        points = self.panel[self.panel.segment == segment]
        if points.empty:
            raise EVDetailsError(f"no models in segment {segment!r}.")

        grid = np.arange(ev.first_year, ev.last_year + 1, dtype=float)
        years = points.year.to_numpy(dtype=float)
        values = points.capacity_kwh.to_numpy(dtype=float)
        weights = self._weights(years, grid)

        central = self._local_linear(years, values, grid, weights)
        spread_low = np.array([self._weighted_quantile(values, weights[:, i], ev.spread_lower_percentile)
                               for i in range(grid.size)])
        spread_high = np.array([self._weighted_quantile(values, weights[:, i], ev.spread_upper_percentile)
                                for i in range(grid.size)])

        # Effective sample size: a year held up by two cars should not be drawn
        # as if it were known.
        effective = weights.sum(axis=0)
        thin = effective < ev.min_effective_models
        central[thin] = np.nan
        spread_low[thin] = np.nan
        spread_high[thin] = np.nan

        band_low, band_high = self._bootstrap_band(points, grid, thin)

        return SegmentCurve(
            segment=segment, years=grid, central=central,
            spread_low=spread_low, spread_high=spread_high,
            band_low=band_low, band_high=band_high, effective_n=effective,
            points=points, n_models=int(points.car_id.nunique()),
        )

    def _bootstrap_band(self, points: pd.DataFrame, grid: np.ndarray,
                        thin: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Resample MODELS, refit, and take the percentiles of the refitted curves.

        Models, not model-years: a car on sale for eight years is one draw from
        the market, not eight. Resampling its years instead would make this band
        vanish and dress a thin segment up as a well-known one.
        """
        ev = self.params.ev_details
        rng = np.random.default_rng(ev.bootstrap_seed)

        by_model = {car_id: group for car_id, group in points.groupby("car_id")}
        model_ids = np.array(list(by_model))
        fits = np.empty((ev.bootstrap_draws, grid.size))

        for draw in range(ev.bootstrap_draws):
            chosen = rng.choice(model_ids, size=model_ids.size, replace=True)
            resampled = pd.concat([by_model[car_id] for car_id in chosen], ignore_index=True)
            years = resampled.year.to_numpy(dtype=float)
            values = resampled.capacity_kwh.to_numpy(dtype=float)
            fits[draw] = self._local_linear(years, values, grid, self._weights(years, grid))

        low = np.nanpercentile(fits, ev.curve_band_lower_percentile, axis=0)
        high = np.nanpercentile(fits, ev.curve_band_upper_percentile, axis=0)
        low[thin] = np.nan
        high[thin] = np.nan
        return low, high

    def curves(self, segments) -> dict[str, SegmentCurve]:
        return {segment: self.curve(segment) for segment in segments
                if (self.panel.segment == segment).any()}
