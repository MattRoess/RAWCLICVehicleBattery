"""
src/params_schema.py
====================

**This is the file you edit to change a setting.**

Every value this project uses is written below, with a plain-language comment
above it saying what it does and whether it is safe to change. Change a value,
save the file, and the next run uses it.

Then run:

    ./.venv/bin/python 00_parameters.py

which rewrites `params.xlsx` so the written record matches what is actually
set. That spreadsheet is a report: editing it changes nothing, because nothing
reads it.

Same arrangement as RAWCLICStockAndFlow and RAWCLICRecoveryModel -- parameters
in code, Excel generated.

WHY THIS IS A MODULE AND NOT PART OF 00_parameters.py
-----------------------------------------------------
A file that is run directly is module `__main__`, so a class defined in it is
recorded as `__main__.Params` and cannot be resolved from any other script.
Defining these here, in a module that is only ever imported, keeps them
addressable as `src.params_schema.Params` from every stage.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, fields


class ParameterError(ValueError):
    """Raised when the values below do not make sense together."""


# ======================================================================
#  THE SETTINGS.  Everything you would want to change is in this block.
#  Edit the value to the right of the '=' sign. Nothing else.
# ======================================================================

@dataclass
class PathParams:
    """Where the data comes from and where results are written."""

    # The folder holding the input workbooks, relative to the project root.
    # Nothing under data/ is tracked in git -- no data file goes to GitHub -- so
    # a fresh clone has to be given the workbook separately.
    # SAFE TO CHANGE: yes, if the data is kept somewhere else.
    input_dir: str = "data/raw"

    # Where the figures are written, relative to the project root. Everything
    # here is regenerable by re-running the scripts, and untracked for that
    # reason as much as for the no-data-in-git rule.
    # SAFE TO CHANGE: yes.
    output_dir: str = "data/processed"


@dataclass
class ScopeParams:
    """Which part of the workbook this project reads."""

    # The consolidated composition workbook, inside paths.input_dir.
    # SAFE TO CHANGE: yes, when a newer version of the file arrives.
    composition_file_name: str = "BATT_consolidated_composition.xlsx"

    # The battery sizes in scope, in kWh. Only BEV sizes are here: the workbook
    # also holds BATTinELV_HEV_1kWh and BATTinELV_PHEV_20kWh, and both are
    # deliberately out of scope.
    # SAFE TO CHANGE: yes, but every value must have a matching sheet in the
    # workbook, and adding a size only helps if that sheet actually exists.
    bev_capacities_kwh: tuple[int, ...] = (25, 45, 60, 80, 100)

    # How a capacity becomes a sheet name. `{kwh}` is filled with each value
    # above. This is also the workbook's `additionalSpecification` column.
    # SAFE TO CHANGE: only if the workbook's sheet naming changes.
    sheet_name_template: str = "BATTinELV_BEV_{kwh}kWh"

    # The `Layer 1` value holding the parts shared by every chemistry -- the
    # pack itself. Every other `Layer 1` value is a cell chemistry, which is how
    # the two branches of the drawing are told apart. Note this is decided by
    # `Layer 1`, NOT by the component's name: `batteryPackCellTerminals` is
    # named for the pack but sits under the chemistry.
    # SAFE TO CHANGE: only if the workbook renames that key.
    pack_level_key: str = "battPackXEV"

    # Which level of detail each parameterCode means.
    #   c-p  component per product -- the component's whole mass
    #   e-c  element per component -- the Layer 4 breakdown
    #   m-c  material per component
    # SAFE TO CHANGE: only if the workbook's coding changes.
    component_parameter_code: str = "c-p"

    # The element-level code: the `Layer 4` breakdown into Li, Ni, Co, Cu, Al...
    # Note it does NOT cover every component -- batteryCellCasing and
    # batteryCellSeparator have no element rows at all, so reading this product
    # at element level alone drops them silently.
    # SAFE TO CHANGE: only if the workbook's coding changes.
    element_parameter_code: str = "e-c"

    # The material-level code. Thin in this workbook: casing, separator and
    # electrolyte only, and with no `Layer 3` column an m-c row does not name
    # its material.
    # SAFE TO CHANGE: only if the workbook's coding changes.
    material_parameter_code: str = "m-c"


@dataclass
class DrawingParams:
    """The product-structure drawing: what it is called and how it is laid out."""

    # The figure written by 01_draw_battery_structure.py, in the project root.
    # PNG only, by request. It is regenerable output and is not tracked in git.
    # SAFE TO CHANGE: yes. Keep the .png suffix -- nothing else is written.
    output_file_name: str = "battery_product_structure.png"

    # Resolution of that PNG. 200 gives a figure that stays readable when it is
    # dropped into a slide at full width.
    # SAFE TO CHANGE: yes. Below ~120 the 7pt labels start to break up.
    output_dpi: int = 200

    # Figure size in inches. The drawing is laid out on a fixed 100x100 grid, so
    # these change how large everything is, never where anything sits.
    # SAFE TO CHANGE: yes, keeping roughly this 3:2 shape.
    figure_width_in: float = 15.5

    # Figure height in inches. See figure_width_in.
    # SAFE TO CHANGE: yes, keeping roughly the 3:2 shape.
    figure_height_in: float = 10.5

    # One component box, in grid units, and the gaps between boxes. The left
    # branch puts two boxes side by side, so box_width must stay under half the
    # branch width.
    # SAFE TO CHANGE: yes, in small steps -- the text inside is fixed-size and
    # will overflow a box made much smaller.
    box_width: float = 23.5

    # Height of one component box, in grid units. The four text lines inside are
    # fixed-size, so much below 9 they start to collide.
    # SAFE TO CHANGE: yes, in small steps.
    box_height: float = 9.6

    # Horizontal gap between the two columns of boxes on the cell branch.
    # SAFE TO CHANGE: yes.
    box_gap_x: float = 1.8

    # Vertical gap between rows of boxes.
    # SAFE TO CHANGE: yes.
    box_gap_y: float = 2.4

    # The order the cell-level components are drawn in: assembly order, not
    # alphabetical -- what stores the charge, then what carries it out, then what
    # contains it.
    # SAFE TO CHANGE: yes. A component in the workbook but missing from this
    # list is drawn last rather than dropped, so a new one cannot vanish.
    cell_component_order: tuple[str, ...] = (
        "cathodeActiveMaterial", "anodeActiveMaterial",
        "currentCollectorCathode", "currentCollectorAnode",
        "batteryCellElectrolyte", "batteryCellSeparator",
        "batteryCellCasing", "batteryPackCellTerminals",
    )

    # The same, for the pack-level components: heaviest structure first.
    # SAFE TO CHANGE: yes, same rule as above.
    pack_component_order: tuple[str, ...] = (
        "batteryPackSupportFrame", "batteryPackThermalConductor",
        "batteryPackModuleEnclosuresAndCoolantManifolds", "batteryPackCables",
    )

    # Plain English for each component code. The only content here that cannot
    # be derived from the workbook: a bare code is not a label a reader can use.
    # A component with no entry is drawn as a bare code and reported on the run.
    # SAFE TO CHANGE: yes -- this is wording, it changes nothing computed.
    component_gloss: dict[str, str] = field(default_factory=lambda: {
        "cathodeActiveMaterial": "the cathode itself -- where Ni, Co, Mn, Fe sit",
        "anodeActiveMaterial": "the anode itself -- graphite, silicon-doped in NMC",
        "currentCollectorCathode": "aluminium foil carrying current off the cathode",
        "currentCollectorAnode": "copper foil carrying current off the anode",
        "batteryCellElectrolyte": "the lithium salt solution between the electrodes",
        "batteryCellSeparator": "porous film keeping the electrodes apart",
        "batteryCellCasing": "the can or pouch enclosing one cell",
        "batteryPackCellTerminals": "the cell's own Al/Cu terminals",
        "batteryPackSupportFrame": "the steel frame the modules are mounted in",
        "batteryPackThermalConductor": "aluminium cooling plate",
        "batteryPackModuleEnclosuresAndCoolantManifolds": "module housings and coolant piping",
        "batteryPackCables": "copper wiring between modules",
    })

    # Which role each cell-level component plays, and the fill colour per role.
    # Colour groups the twelve boxes so the eye does not have to read them all.
    # Anything not listed here falls back to the 'cell_body' colour; everything
    # on the pack branch uses 'pack' whatever its role says.
    # SAFE TO CHANGE: yes -- presentation only.
    component_role: dict[str, str] = field(default_factory=lambda: {
        "cathodeActiveMaterial": "electrode",
        "anodeActiveMaterial": "electrode",
        "currentCollectorCathode": "collector",
        "currentCollectorAnode": "collector",
        "batteryCellElectrolyte": "cell_body",
        "batteryCellSeparator": "cell_body",
        "batteryCellCasing": "cell_body",
        "batteryPackCellTerminals": "terminal",
    })

    # SAFE TO CHANGE: yes -- presentation only. Keep them pale: the labels are
    # dark text sitting on top.
    role_colours: dict[str, str] = field(default_factory=lambda: {
        "electrode": "#dbe7f3",
        "collector": "#e3eddc",
        "cell_body": "#f6ecd9",
        "terminal": "#efe1ee",
        "pack": "#e6e4e0",
    })


@dataclass
class InterpolationParams:
    """How a battery size that is not in the workbook is arrived at."""

    # The capacities the drawing and the interpolation are built from, in kWh.
    # These are the workbook's own sheets and are read, never invented.
    # Set in scope.bev_capacities_kwh; repeated here only as a reminder that the
    # anchors ARE the data and everything between and beyond them is inferred.

    # WHAT IS INTERPOLATED: 'mass' interpolates kilograms against capacity and
    # divides afterwards; 'intensity' interpolates kg/kWh directly.
    # 'mass' is the default and the defensible one. In kg/kWh the anchors are
    # hyperbolic -- a fixed-mass part like currentCollectorAnode falls 0.86 ->
    # 0.22 kg/kWh from 25 to 100 kWh purely because the denominator grew -- and
    # interpolating that shape smears fixed-mass parts together with the ones
    # that really do scale. In kilograms the same part is flat at ~21 kg and the
    # curve carries its physical meaning.
    # SAFE TO CHANGE: yes, but 'intensity' is here to test the difference, not
    # to be used for results.
    interpolate_on: str = "mass"

    # BETWEEN THE ANCHORS: 'pchip' is shape-preserving -- monotone where the
    # data is monotone, and it cannot overshoot into a bump the anchors do not
    # support. 'linear' joins them with straight segments.
    # SAFE TO CHANGE: yes. Both are honest; pchip is smoother, linear is the one
    # you can check by hand.
    interpolation_method: str = "pchip"

    # BEYOND THE ANCHORS: extrapolation is always LINEAR, whatever the method
    # above. A cubic continued past its last knot diverges, and at 150 kWh --
    # half again beyond the largest sheet -- that is how a plot ends up with a
    # negative cathode. 'last_segment' continues the slope of the final pair of
    # anchors; 'fit' continues the least-squares slope through all of them.
    # SAFE TO CHANGE: yes. 'last_segment' follows the data's local behaviour,
    # 'fit' is steadier when the last two anchors happen to wobble.
    extrapolation: str = "last_segment"

    # The capacity range the public function will answer for, in kWh. Outside
    # this it refuses rather than returning a number nobody should trust.
    # SAFE TO CHANGE: yes -- but widening it does not make the answer better.
    # Above the largest anchor (100 kWh) every value is an extrapolation, and
    # the further out, the more it is the straight line's opinion and not data.
    min_capacity_kwh: float = 10.0
    max_capacity_kwh: float = 200.0

    # A linear continuation can cross zero: a few series have a slightly
    # negative slope between their last two anchors. Negative mass is never
    # right, so it is clamped, and the clamp is reported rather than hidden.
    # SAFE TO CHANGE: no, not sensibly.
    clamp_negative_mass: bool = True


@dataclass
class MonteCarloParams:
    """The uncertainty around every value, and how it is sampled."""

    # Turn the Monte Carlo off to get the central values alone, fast.
    # SAFE TO CHANGE: yes.
    enabled: bool = True

    # How many draws. The bands settle by a few thousand; more only smooths the
    # tails of a distribution whose width is a flat rule to begin with (below).
    # SAFE TO CHANGE: yes. 2,000 is a working figure, 20,000 for anything shown.
    n_draws: int = 20_000

    # Fixed seed, so the same settings give the same bands and two runs can be
    # compared. Set to None for a different sample every run.
    # SAFE TO CHANGE: yes.
    random_seed: int | None = 20260907

    # The shape sampled between min_value and max_value, with Value as the mode:
    # 'triangular' or 'uniform'. Triangular keeps Value the most likely outcome,
    # which is what a consolidated central estimate is meant to be.
    # SAFE TO CHANGE: yes.
    distribution: str = "triangular"

    # ⚠️ WHAT THE WORKBOOK'S UNCERTAINTY ACTUALLY IS. Every non-zero row in
    # BATT_consolidated_composition.xlsx has min_value = 0.9 x Value and
    # max_value = 1.1 x Value -- all 805 of them, whether the value was
    # consolidated from 1 source or from 21, and DQS is 2 throughout. So the
    # spread is a flat +/-10% convention, NOT an observed range, and the Monte
    # Carlo can only propagate that convention. It cannot tell a well-sourced
    # value from a lone one, and a narrow band here means the rule was narrow,
    # not that the number is well known. Leave True to use the file's own
    # min/max; set False to impose relative_band instead.
    # SAFE TO CHANGE: yes.
    use_workbook_min_max: bool = True

    # The fractional band used when use_workbook_min_max is False -- 0.10 gives
    # the same +/-10% the file states, which makes the two settings easy to
    # compare. Raise it to see what a more honest spread would do to the result.
    # SAFE TO CHANGE: yes.
    relative_band: float = 0.10

    # ONE DRAW PER SERIES, SHARED ACROSS CAPACITIES. A component's error does
    # not change between 60 and 61 kWh, so the same quantile is applied to that
    # series at every anchor. Drawing each anchor independently would put kinks
    # in a curve that is supposed to be smooth, and would shrink the band by
    # averaging errors that are in truth the same error.
    # SAFE TO CHANGE: no, not without a reason to believe the anchors err
    # independently.
    correlate_across_capacities: bool = True

    # The percentiles reported and drawn as the band.
    # SAFE TO CHANGE: yes.
    lower_percentile: float = 2.5
    upper_percentile: float = 97.5


@dataclass
class CapacityFigureParams:
    """The mass-against-capacity figures."""

    # Per-component small multiples: mass in kg against capacity, one panel per
    # component, anchors as dots, the interpolation as a line, the Monte Carlo
    # as a band.
    # SAFE TO CHANGE: yes. Keep the .png suffix.
    components_file_name: str = "battery_mass_by_capacity.png"

    # Total battery mass against capacity, one line per chemistry.
    # SAFE TO CHANGE: yes. Keep the .png suffix.
    totals_file_name: str = "battery_total_mass_by_capacity.png"

    # The chemistry drawn in the per-component figure. The pack-level components
    # are the same whichever is chosen.
    # SAFE TO CHANGE: yes -- any Layer 1 chemistry in the workbook.
    components_figure_chemistry: str = "battLiNMC_midNi"

    # The capacity range plotted, and how many points the curve is drawn with.
    # The range deliberately runs past the largest anchor so the extrapolated
    # part is visible as such rather than hidden inside the data range.
    # SAFE TO CHANGE: yes, within interpolation.min/max_capacity_kwh.
    plot_min_kwh: float = 25.0
    plot_max_kwh: float = 150.0
    plot_points: int = 126

    # Figure size in inches for each of the two figures.
    # SAFE TO CHANGE: yes.
    components_figure_size_in: tuple[float, float] = (16.0, 11.0)
    totals_figure_size_in: tuple[float, float] = (11.0, 7.5)


@dataclass
class EVDetailsParams:
    """The EV-database vehicle table: segment and battery capacity over time."""

    # The scraped vehicle table, inside paths.input_dir. One row per model
    # variant, ~144 columns. Incomplete and still growing.
    # SAFE TO CHANGE: yes, when a newer scrape arrives.
    ev_details_file_name: str = "EV_details.csv"

    # WHICH CAPACITY the curves are fitted to. 'nominal' is the pack's gross,
    # stated figure; 'useable' is what the car will actually deliver. They
    # differ by about 6% (median useable/nominal = 0.944).
    #
    # ⚠️ THE DEFAULT IS 'nominal' BECAUSE THE COMPOSITION WORKBOOK IS PER
    # NOMINAL kWh (confirmed 2026-09-08). Anything joining EV_details.csv to
    # BATT_consolidated_composition.xlsx -- which is every mass this project
    # computes -- has to be on the nominal basis, or every result is ~6% light.
    # 'useable' is still worth plotting, as what the driver gets, but it is not
    # the number to multiply kg/kWh by.
    # SAFE TO CHANGE: yes for a figure; NOT for anything feeding the composition.
    capacity_basis: str = "nominal"

    # Both bases are drawn, as separate figures: 'nominal' is the one the
    # composition arithmetic uses, 'useable' is what the car delivers. Keeping
    # them apart stops the two being read as one series.
    # SAFE TO CHANGE: yes -- any subset of ('nominal', 'useable').
    capacity_bases_to_plot: tuple[str, ...] = ("nominal", "useable")

    # WHICH COUNTRY'S AVAILABILITY DATES. The file carries United Kingdom, The
    # Netherlands and Germany for every model. 'Germany' is the default as the
    # largest of the three European markets; 'any' takes the earliest start and
    # latest end across all three.
    # SAFE TO CHANGE: yes -- 'Germany', 'The Netherlands', 'United Kingdom', 'any'.
    availability_country: str = "Germany"

    # A model counts in a year if its availability window OVERLAPS that year at
    # all, rather than only the year it launched. That makes the series "what
    # was on sale then", which is what a fleet-composition question needs.
    # Set False to count a model only in its introduction year instead.
    # SAFE TO CHANGE: yes, but the two answer different questions.
    count_every_year_on_sale: bool = True

    # 'Expected MON YYYY' rows are announced, not yet on sale (47 of 3,948
    # entries). Including them extends the series into 2026-2027 with models
    # that may not arrive.
    # SAFE TO CHANGE: yes.
    include_expected: bool = True

    # The years plotted. Before 2015 there are too few models for a median to
    # mean anything; the upper end runs past today because the file carries
    # announced models.
    # SAFE TO CHANGE: yes.
    first_year: int = 2015
    last_year: int = 2026

    # A segment-year with fewer models than this is dropped rather than drawn:
    # a median of two cars is a coincidence, not a trend.
    # SAFE TO CHANGE: yes. Below 3 the lines get noisy.
    min_models_per_year: int = 3

    # The segments drawn, in two panels -- the file also carries G, I and
    # 'N - Passenger Van', which have no entry in the stock-and-flow model's
    # battery_size_map and are left out of the comparison for that reason.
    # SAFE TO CHANGE: yes.
    car_segments: tuple[str, ...] = ("A", "B", "C", "D", "E", "F")
    jellybean_segments: tuple[str, ...] = ("JA", "JB", "JC", "JD", "JE", "JF")

    # RAWCLICStockAndFlow's params.materials.battery_size_map, copied here to be
    # compared against what the vehicles actually carry. It is NOT read from
    # that project -- this is a written-down copy, and if the model changes its
    # map this has to be updated by hand.
    # SAFE TO CHANGE: yes, to match whatever the stock-flow model currently sets.
    reference_battery_size_map: dict[str, float] = field(default_factory=lambda: {
        "A": 25.0, "B": 45.0, "C": 60.0, "D": 80.0, "E": 80.0, "F": 100.0,
        "JA": 25.0, "JB": 45.0, "JC": 60.0, "JD": 80.0, "JE": 80.0, "JF": 100.0,
    })

    # A model with an open window ("Since March 2021") is treated as on sale
    # through this year. It is the file's own horizon, not a forecast.
    # SAFE TO CHANGE: yes, but past last_year it has no visible effect.
    open_window_end_year: int = 2026

    # HOW THE CURVE IS SMOOTHED. Not a straight line: capacity per segment rises
    # and then flattens, and a line through that either understates the recent
    # years or overstates the early ones. This is a local linear regression with
    # Gaussian weights -- LOESS in all but name -- fitted to the individual
    # models rather than to yearly averages, so a year with forty variants
    # counts for more than one with four.
    #
    # The bandwidth is the Gaussian's sigma IN YEARS. It sets how much of the
    # neighbouring years each point of the curve can see: small follows the data
    # closely and wanders, large is smooth and flattens real turns.
    # SAFE TO CHANGE: yes. Below ~1.5 the curve starts chasing single models;
    # above ~4 it will smooth away the flattening after 2023.
    smoothing_bandwidth_years: float = 2.0

    # The curve is only drawn where enough models sit within one bandwidth of
    # that year. Without this the fit runs on into years held up by two cars.
    # SAFE TO CHANGE: yes.
    min_effective_models: float = 4.0

    # TWO DIFFERENT UNCERTAINTIES, drawn as two different bands.
    #
    # (1) THE MARKET SPREAD: how far apart the models on sale actually are in a
    # given year -- the same car type sold with several pack sizes. This is real
    # dispersion, not error, and it does not shrink with more data.
    # SAFE TO CHANGE: yes.
    spread_lower_percentile: float = 10.0
    spread_upper_percentile: float = 90.0

    # (2) UNCERTAINTY OF THE CURVE ITSELF: how much the fitted line would move
    # if the market had happened to contain a different sample of models.
    # Bootstrapped by resampling MODELS -- never model-years, which would treat
    # one long-lived car as several independent observations and make the band
    # far too narrow.
    # SAFE TO CHANGE: yes. 400 draws is enough for a band; 2,000 for a figure
    # that is going somewhere.
    bootstrap_draws: int = 400
    curve_band_lower_percentile: float = 2.5
    curve_band_upper_percentile: float = 97.5

    # Fixed seed so the bootstrap band is reproducible. None for a fresh sample.
    # SAFE TO CHANGE: yes.
    bootstrap_seed: int | None = 20260908

    # Draw the individual models behind the bands, so the reader can see how
    # many there are and how scattered.
    # SAFE TO CHANGE: yes -- presentation only.
    show_model_scatter: bool = True

    # The figures, in paths.output_dir. '{basis}' is filled with 'nominal' or
    # 'useable', so the two cannot overwrite each other or be mistaken for one
    # another later.
    # SAFE TO CHANGE: yes. Keep '{basis}' and the .png suffix.
    capacity_over_time_file_name: str = "bev_capacity_by_segment_over_time_{basis}.png"

    # SAFE TO CHANGE: yes.
    capacity_over_time_figure_size_in: tuple[float, float] = (17.0, 8.5)


# ======================================================================
#  END OF SETTINGS.  Below here is plumbing.
# ======================================================================

@dataclass
class Params:
    """Every setting, in one object."""

    SECTIONS = ("paths", "scope", "drawing", "interpolation", "monte_carlo", "capacity_figure",
                "ev_details")

    paths: PathParams = field(default_factory=PathParams)
    scope: ScopeParams = field(default_factory=ScopeParams)
    drawing: DrawingParams = field(default_factory=DrawingParams)
    interpolation: InterpolationParams = field(default_factory=InterpolationParams)
    monte_carlo: MonteCarloParams = field(default_factory=MonteCarloParams)
    capacity_figure: CapacityFigureParams = field(default_factory=CapacityFigureParams)
    ev_details: EVDetailsParams = field(default_factory=EVDetailsParams)

    def sheet_names(self) -> list[str]:
        """The workbook sheets in scope, in the order the capacities are listed."""
        return [self.scope.sheet_name_template.format(kwh=kwh)
                for kwh in self.scope.bev_capacities_kwh]

    def composition_path(self, project_root) -> "Path":
        """The workbook's full path, assembled in one place."""
        from pathlib import Path
        return Path(project_root) / self.paths.input_dir / self.scope.composition_file_name

    def ev_details_path(self, project_root) -> "Path":
        """The EV-database table's full path."""
        from pathlib import Path
        return Path(project_root) / self.paths.input_dir / self.ev_details.ev_details_file_name

    def output_path(self, project_root, file_name: str) -> "Path":
        """Where a figure goes, with the folder created if it is not there yet."""
        from pathlib import Path
        directory = Path(project_root) / self.paths.output_dir
        directory.mkdir(parents=True, exist_ok=True)
        return directory / file_name

    def validate(self) -> None:
        """Every check that can be made without opening the workbook."""
        from pathlib import Path

        scope, drawing = self.scope, self.drawing

        for name in ("input_dir", "output_dir"):
            value = getattr(self.paths, name)
            if not value:
                raise ParameterError(f"paths.{name} is empty.")
            if Path(value).is_absolute():
                raise ParameterError(
                    f"paths.{name} must be relative to the project root, so the "
                    f"project still works when it is cloned elsewhere: {value!r}")

        if not scope.bev_capacities_kwh:
            raise ParameterError("scope.bev_capacities_kwh is empty -- nothing to read.")
        if any(kwh <= 0 for kwh in scope.bev_capacities_kwh):
            raise ParameterError(
                f"scope.bev_capacities_kwh must all be positive: {scope.bev_capacities_kwh}")
        if len(set(scope.bev_capacities_kwh)) != len(scope.bev_capacities_kwh):
            raise ParameterError(
                f"scope.bev_capacities_kwh repeats a value: {scope.bev_capacities_kwh}. "
                "A repeated size would be read, and drawn into the ranges, twice.")
        if "{kwh}" not in scope.sheet_name_template:
            raise ParameterError(
                "scope.sheet_name_template must contain '{kwh}', otherwise every "
                f"capacity resolves to the same sheet: {scope.sheet_name_template!r}")

        codes = (scope.component_parameter_code, scope.element_parameter_code,
                 scope.material_parameter_code)
        if len(set(codes)) != 3:
            raise ParameterError(
                f"the three parameterCode settings must differ from each other: {codes}")

        if not drawing.output_file_name.endswith(".png"):
            raise ParameterError(
                "drawing.output_file_name must end in '.png' -- PNG is the only "
                f"format written: {drawing.output_file_name!r}")
        if drawing.output_dpi <= 0:
            raise ParameterError(f"drawing.output_dpi must be positive: {drawing.output_dpi}")
        for name in ("figure_width_in", "figure_height_in", "box_width",
                     "box_height", "box_gap_x", "box_gap_y"):
            if getattr(drawing, name) <= 0:
                raise ParameterError(f"drawing.{name} must be positive: {getattr(drawing, name)}")

        overlap = set(drawing.cell_component_order) & set(drawing.pack_component_order)
        if overlap:
            raise ParameterError(
                f"a component is ordered on both branches: {sorted(overlap)}. Which "
                "branch it belongs to is decided by the workbook's Layer 1, so an "
                "ordering entry on the wrong branch simply never applies.")

        ordered = set(drawing.cell_component_order) | set(drawing.pack_component_order)
        without_gloss = sorted(ordered - set(drawing.component_gloss))
        if without_gloss:
            raise ParameterError(
                f"no drawing.component_gloss for {without_gloss}. These are known "
                "components, so a missing gloss is an oversight rather than a new "
                "component appearing in the workbook.")

        unknown_role = sorted(set(drawing.component_role.values()) - set(drawing.role_colours))
        if unknown_role:
            raise ParameterError(
                f"drawing.component_role uses role(s) with no colour: {unknown_role}. "
                f"Known roles: {sorted(drawing.role_colours)}")
        if "pack" not in drawing.role_colours:
            raise ParameterError(
                "drawing.role_colours must define 'pack' -- it is the fill for the "
                "whole pack branch.")
        if "cell_body" not in drawing.role_colours:
            raise ParameterError(
                "drawing.role_colours must define 'cell_body' -- it is the fallback "
                "for a cell component with no role.")

        interp, mc, figure = self.interpolation, self.monte_carlo, self.capacity_figure

        if interp.interpolate_on not in ("mass", "intensity"):
            raise ParameterError(
                f"interpolation.interpolate_on must be 'mass' or 'intensity': "
                f"{interp.interpolate_on!r}")
        if interp.interpolation_method not in ("pchip", "linear"):
            raise ParameterError(
                f"interpolation.interpolation_method must be 'pchip' or 'linear': "
                f"{interp.interpolation_method!r}")
        if interp.extrapolation not in ("last_segment", "fit"):
            raise ParameterError(
                f"interpolation.extrapolation must be 'last_segment' or 'fit': "
                f"{interp.extrapolation!r}")
        if interp.min_capacity_kwh <= 0:
            raise ParameterError(
                f"interpolation.min_capacity_kwh must be positive: {interp.min_capacity_kwh}")
        if interp.max_capacity_kwh <= interp.min_capacity_kwh:
            raise ParameterError(
                f"interpolation.max_capacity_kwh ({interp.max_capacity_kwh}) must be "
                f"above min_capacity_kwh ({interp.min_capacity_kwh}).")
        anchors = scope.bev_capacities_kwh
        if anchors and not (interp.min_capacity_kwh <= min(anchors)
                            and interp.max_capacity_kwh >= max(anchors)):
            raise ParameterError(
                f"the allowed capacity range [{interp.min_capacity_kwh}, "
                f"{interp.max_capacity_kwh}] must contain the anchors "
                f"{sorted(anchors)} -- refusing to answer for a size the workbook "
                "actually supplies would be absurd.")
        if interp.interpolation_method == "pchip" and len(anchors) < 2:
            raise ParameterError(
                "interpolation_method 'pchip' needs at least two anchors; "
                f"scope.bev_capacities_kwh has {len(anchors)}.")

        if mc.n_draws < 1:
            raise ParameterError(f"monte_carlo.n_draws must be at least 1: {mc.n_draws}")
        if mc.distribution not in ("triangular", "uniform"):
            raise ParameterError(
                f"monte_carlo.distribution must be 'triangular' or 'uniform': "
                f"{mc.distribution!r}")
        if not 0 <= mc.relative_band < 1:
            raise ParameterError(
                f"monte_carlo.relative_band is a fraction, so it must be in [0, 1): "
                f"{mc.relative_band}")
        if not 0 <= mc.lower_percentile < mc.upper_percentile <= 100:
            raise ParameterError(
                f"monte_carlo percentiles must satisfy 0 <= lower < upper <= 100: "
                f"{mc.lower_percentile}, {mc.upper_percentile}")

        for name in ("components_file_name", "totals_file_name"):
            if not getattr(figure, name).endswith(".png"):
                raise ParameterError(
                    f"capacity_figure.{name} must end in '.png' -- PNG is the only "
                    f"format written: {getattr(figure, name)!r}")
        if figure.plot_min_kwh >= figure.plot_max_kwh:
            raise ParameterError(
                f"capacity_figure.plot_min_kwh ({figure.plot_min_kwh}) must be below "
                f"plot_max_kwh ({figure.plot_max_kwh}).")
        if not (interp.min_capacity_kwh <= figure.plot_min_kwh
                and figure.plot_max_kwh <= interp.max_capacity_kwh):
            raise ParameterError(
                f"the plotted range [{figure.plot_min_kwh}, {figure.plot_max_kwh}] "
                f"leaves the range the function will answer for "
                f"[{interp.min_capacity_kwh}, {interp.max_capacity_kwh}] -- the "
                "figure would have a gap where the function refuses.")
        if figure.plot_points < 2:
            raise ParameterError(
                f"capacity_figure.plot_points must be at least 2: {figure.plot_points}")

        ev = self.ev_details
        if ev.capacity_basis not in ("useable", "nominal"):
            raise ParameterError(
                f"ev_details.capacity_basis must be 'useable' or 'nominal': "
                f"{ev.capacity_basis!r}")
        known_countries = ("Germany", "The Netherlands", "United Kingdom", "any")
        if ev.availability_country not in known_countries:
            raise ParameterError(
                f"ev_details.availability_country must be one of {known_countries}: "
                f"{ev.availability_country!r}")
        if ev.first_year >= ev.last_year:
            raise ParameterError(
                f"ev_details.first_year ({ev.first_year}) must be below last_year "
                f"({ev.last_year}).")
        if ev.min_models_per_year < 1:
            raise ParameterError(
                f"ev_details.min_models_per_year must be at least 1: "
                f"{ev.min_models_per_year}")
        if ev.smoothing_bandwidth_years <= 0:
            raise ParameterError(
                f"ev_details.smoothing_bandwidth_years must be positive: "
                f"{ev.smoothing_bandwidth_years}")
        if ev.bootstrap_draws < 1:
            raise ParameterError(
                f"ev_details.bootstrap_draws must be at least 1: {ev.bootstrap_draws}")
        for low, high, label in (
            (ev.spread_lower_percentile, ev.spread_upper_percentile, "spread"),
            (ev.curve_band_lower_percentile, ev.curve_band_upper_percentile, "curve_band"),
        ):
            if not 0 <= low < high <= 100:
                raise ParameterError(
                    f"ev_details.{label} percentiles must satisfy 0 <= lower < upper "
                    f"<= 100: {low}, {high}")
        if ev.min_effective_models <= 0:
            raise ParameterError(
                f"ev_details.min_effective_models must be positive: "
                f"{ev.min_effective_models}")
        if not ev.capacity_over_time_file_name.endswith(".png"):
            raise ParameterError(
                "ev_details.capacity_over_time_file_name must end in '.png': "
                f"{ev.capacity_over_time_file_name!r}")
        if "{basis}" not in ev.capacity_over_time_file_name:
            raise ParameterError(
                "ev_details.capacity_over_time_file_name must contain '{basis}', "
                "or the nominal and useable figures overwrite each other: "
                f"{ev.capacity_over_time_file_name!r}")
        if not ev.capacity_bases_to_plot:
            raise ParameterError("ev_details.capacity_bases_to_plot is empty.")
        unknown_bases = sorted(set(ev.capacity_bases_to_plot) - {"nominal", "useable"})
        if unknown_bases:
            raise ParameterError(
                f"ev_details.capacity_bases_to_plot may only contain 'nominal' and "
                f"'useable': {unknown_bases}")
        overlapping = set(ev.car_segments) & set(ev.jellybean_segments)
        if overlapping:
            raise ParameterError(
                f"a segment is listed in both ev_details.car_segments and "
                f"jellybean_segments: {sorted(overlapping)}")
        unmapped = sorted((set(ev.car_segments) | set(ev.jellybean_segments))
                          - set(ev.reference_battery_size_map))
        if unmapped:
            raise ParameterError(
                f"no ev_details.reference_battery_size_map entry for {unmapped} -- "
                "the comparison panel would have nothing to compare those against.")


def current() -> Params:
    """The settings above, validated."""
    params = Params()
    params.validate()
    return params


def describe(section_name: str, field_name: str) -> str:
    """The comment block written above a setting, as one line."""
    return _FIELD_COMMENTS.get((section_name, field_name), "")


def flatten(params: Params) -> list[list]:
    """[name, description, key, value] per setting, in the order written above."""
    rows: list[list] = []
    for section_name in params.SECTIONS:
        section = getattr(params, section_name)
        for f in fields(section):
            value = getattr(section, f.name)
            rows.append([
                f.name,
                describe(type(section).__name__, f.name),
                f"{section_name}.{f.name}",
                json.dumps(value) if isinstance(value, (list, tuple, dict)) else value,
            ])
    return rows


def _collect_field_comments() -> dict[tuple[str, str], str]:
    """
    Read the comment block sitting above each setting, out of this file's own
    source.

    Comments are discarded by Python at import time, so they have to be read
    back from the source to appear in params.xlsx. Doing it this way means the
    explanation a reader sees next to the value is the same text that reaches
    the spreadsheet -- there is no second copy to fall out of date.

    Same approach as RAWCLICRecoveryModel's params_schema.py.
    """
    import ast
    import inspect

    source = inspect.getsource(__import__(__name__, fromlist=["_"]))
    lines = source.splitlines()
    comments: dict[tuple[str, str], str] = {}

    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.ClassDef):
            continue
        for statement in node.body:
            if not (isinstance(statement, ast.AnnAssign)
                    and isinstance(statement.target, ast.Name)):
                continue
            block = []
            index = statement.lineno - 2          # the line above the setting
            while index >= 0 and lines[index].strip().startswith("#"):
                block.insert(0, lines[index].strip().lstrip("#").strip())
                index -= 1
            if block:
                comments[(node.name, statement.target.id)] = " ".join(block)
    return comments


_FIELD_COMMENTS = _collect_field_comments()
