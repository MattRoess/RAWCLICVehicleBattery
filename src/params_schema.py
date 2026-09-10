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
    #
    # This is the ONLY place figures are written. It was data/processed until
    # figures were also being copied to figures/ by hand, which meant two homes
    # and one of them going stale the moment a script ran.
    # SAFE TO CHANGE: yes.
    output_dir: str = "figures"


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
    box_gap_y: float = 2.8

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

    # How many draws. The BANDS settle by a few thousand -- measured, the mean and
    # the 2.5/97.5 percentiles move only about 0.1% between 20,000 and 200,000.
    # The MODE does not: it is a histogram peak, and it tightens from 1.57% worst
    # case at 20,000 draws to 0.44% at 200,000 (checked against the triangular's
    # known mode of 1.0). That, and matching RAWCLICVehicleElectronics' own
    # N_SIMULATIONS = 200,000, is why this is 200,000.
    # Costs 5 min 15 s for a full 06 run -- timed, not estimated -- and 318 MB per
    # draw array. The draws are sampled once per model and reused, so the cost is
    # far below draws x capacities.
    # SAFE TO CHANGE: yes. 2,000 is a working figure while editing, 20,000 for a
    # figure, 200,000 for the composition files that leave this project.
    n_draws: int = 200_000

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

    # WHEN A SEGMENT HAS TOO FEW MODELS TO FIT A CURVE, fall back rather than
    # dropping it -- all twelve segments must appear in the exported files, even
    # ones the market barely populates.
    #   'segment_median'  the median capacity of that segment's own models. Real
    #                     data, just thin. JA has two (Hyundai INSTER, 42 and 49
    #                     kWh nominal), so its median is 45.5.
    #   'reference_map'   reference_battery_size_map. Last resort, for a segment
    #                     with no models at all. Note the map says 25 kWh for JA
    #                     against those cars' 45.5, so it is the worse source
    #                     wherever real models exist.
    # Every exported row carries capacity_source saying which was used.
    # SAFE TO CHANGE: yes.
    capacity_fallback: str = "segment_median"

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


    # HOW THE CATHODE MATERIAL IS GROUPED. The file states 11 different values;
    # these are the groups they are collapsed into.
    #   NMC_middle  NMC532, NMC622
    #   NMC_high    NMC712, NMC721, NMC811, and plain 'NMC'/'NCM'
    # Plain 'NMC' carries no grade and is 57% of the 2026 models, so where it
    # goes decides most of the split. It goes to NMC_high by instruction --
    # which is the right guess for recent years, where 100 of 116 graded NMC
    # models are 811, and the wrong one for 2018-2021, where 622 dominated.
    # Treat NMC_high before about 2022 as "NMC of unknown grade", not as high-Ni.
    # SAFE TO CHANGE: yes.
    chemistry_groups: dict[str, tuple[str, ...]] = field(default_factory=lambda: {
        "LFP": ("LFP",),
        "NCA": ("NCA",),
        "NMC_middle": ("NMC532", "NMC622"),
        "NMC_high": ("NMC712", "NMC721", "NMC811", "NMC", "NCM"),
    })

    # NOT COVERED BY THE GROUPS ABOVE, and deliberately left out rather than
    # forced into one: 'NMC333' (5 models, all before 2019 -- graded, so not
    # "ungraded", but neither 532/622 nor 712/721/811) and 'LFP & NMC' (6
    # models, either-or per variant). Together 11 of 1,244 models. They are
    # reported on every run instead of disappearing quietly.
    # SAFE TO CHANGE: yes -- add them to a group above if you decide where they
    # belong; this list only silences the report.
    chemistry_values_left_out: tuple[str, ...] = ("NMC333", "LFP & NMC")

    # A segment-and-chemistry combination needs at least this many distinct
    # models before it is tabulated or drawn. Below it, a median is one
    # manufacturer's product plan rather than a market.
    # SAFE TO CHANGE: yes.
    min_models_per_chemistry_cell: int = 5

    # Colour per chemistry group, used across every chemistry figure.
    # SAFE TO CHANGE: yes -- presentation only.
    chemistry_colours: dict[str, str] = field(default_factory=lambda: {
        "LFP": "#2f8f5b",
        "NCA": "#b07aa1",
        "NMC_middle": "#e08214",
        "NMC_high": "#1f5f8b",
    })

    # Capacity by segment AND chemistry, in paths.output_dir. '{basis}' is
    # filled with 'nominal' or 'useable', so the two cannot overwrite each other
    # or be mistaken for one another later.
    # SAFE TO CHANGE: yes. Keep '{basis}' and the .png suffix.
    capacity_by_chemistry_file_name: str = "bev_capacity_by_segment_and_chemistry_{basis}.png"

    # SAFE TO CHANGE: yes.
    capacity_by_chemistry_figure_size_in: tuple[float, float] = (17.0, 8.5)


@dataclass
class ScenarioParams:
    """
    Cathode-chemistry mix to 2070, as three scenarios.

    ⚠️ THE SHARE NUMBERS BELOW ARE A DRAFT JUDGEMENT, NOT A RESULT. Nothing
    derives them from data -- the data ends in 2026. They are written here to be
    argued with and corrected, and every figure built from them says so.

    Shares are given at ANCHOR YEARS and interpolated between; before the first
    anchor and after the last they are held flat. Each segment group's shares
    are normalised to 1, so a set that does not add up is corrected rather than
    silently scaled.

    THE CHINA ASSUMPTION IS BUILT INTO THE ANCHORS, not modelled separately.
    Chinese-built BEVs are expected to approach half the EU market within a
    decade, which is what carries LFP and later sodium into the mainstream
    segments this fast. If that share stalls, every LFP and Na trajectory here
    is too fast, and the NMC ones too slow.
    """

    # Segment groups the scenarios are written against. The whole chemistry
    # story is a size story -- cheap small cars take the cheap chemistry first
    # -- so shares are set per group rather than per segment.
    # SAFE TO CHANGE: yes, but every segment must appear in exactly one group.
    segment_groups: dict[str, tuple[str, ...]] = field(default_factory=lambda: {
        "small": ("A", "B", "JA", "JB"),
        "medium": ("C", "D", "JC", "JD"),
        "large": ("E", "F", "JE", "JF"),
    })

    # The years the shares are pinned at. Between them the mix is interpolated.
    # SAFE TO CHANGE: yes -- add anchors where a scenario needs a turn.
    anchor_years: tuple[int, ...] = (2025, 2035, 2050, 2070)

    # ⚠️ CHEMISTRIES WITH NO COMPOSITION DATA. The workbook has LFP, LMFP, LMO,
    # NCA and three NMC grades -- and nothing for sodium-ion or solid-state.
    # They are NOT variants of what is there: sodium replaces the copper anode
    # collector with aluminium, and bipolar solid-state deletes the separator,
    # the liquid electrolyte and the per-cell terminals outright. So a scenario
    # can state their SHARE, but no material mass can be computed for them until
    # a composition is supplied. Every output marks the gap rather than
    # substituting a lookalike.
    # SAFE TO CHANGE: remove a name once its composition exists.
    chemistries_without_composition: tuple[str, ...] = ("Na_ion", "solid_state")

    # SCENARIO 1 -- "LFP volume, NMC premium", kept as a specific case.
    # Today's structure extrapolated: LFP and LMFP take the volume segments, NMC
    # high-Ni holds the long-range premium, nothing new arrives. Useful as the
    # no-surprises reference, not as a forecast: 45 years with no new chemistry
    # has no precedent.
    # SAFE TO CHANGE: yes -- these are shares in %, per anchor year.
    scenario_1: dict[str, dict[str, tuple[float, ...]]] = field(default_factory=lambda: {
        "small":  {"LFP": (70, 65, 60, 60), "LMFP": (18, 25, 33, 35), "NMC_high": (12, 10, 7, 5)},
        "medium": {"LFP": (50, 45, 42, 40), "LMFP": (22, 32, 42, 45), "NMC_high": (28, 23, 16, 15)},
        "large":  {"LFP": (8, 10, 10, 10), "LMFP": (17, 25, 32, 35), "NMC_high": (75, 65, 58, 55)},
    })

    # SCENARIO 2 -- sodium enters, NMC becomes a NICHE rather than disappearing.
    # Reframed deliberately: eliminating NMC by 2035 is the least defensible
    # clause anyone proposed here, since Korean and European cell capacity is
    # committed to it and long-range premium demand does not vanish. Shrinking
    # it to a few per cent keeps the material story -- sodium's aluminium anode
    # collector removing better than half the pack's copper -- without resting
    # on a clause likely to be wrong.
    # SAFE TO CHANGE: yes.
    scenario_2: dict[str, dict[str, tuple[float, ...]]] = field(default_factory=lambda: {
        "small":  {"Na_ion": (2, 40, 60, 68), "LFP": (68, 40, 25, 20),
                   "LMFP": (18, 15, 12, 10), "NMC_high": (12, 5, 3, 2)},
        "medium": {"Na_ion": (0, 12, 20, 24), "LFP": (50, 48, 42, 38),
                   "LMFP": (22, 32, 34, 35), "NMC_high": (28, 8, 4, 3)},
        "large":  {"Na_ion": (0, 3, 8, 10), "LFP": (8, 18, 24, 25),
                   "LMFP": (17, 49, 58, 57), "NMC_high": (75, 30, 10, 8)},
    })

    # SCENARIO 3 -- scenario 2, with bipolar solid-state arriving LATER than
    # first proposed. 2035 for mass-market bipolar solid-state is the optimistic
    # end of every roadmap worth trusting, so it enters from 2040 and takes the
    # large segments first, where the energy density is worth the cost.
    # SAFE TO CHANGE: yes.
    scenario_3: dict[str, dict[str, tuple[float, ...]]] = field(default_factory=lambda: {
        "small":  {"solid_state": (0, 0, 15, 35), "Na_ion": (2, 40, 52, 45),
                   "LFP": (68, 40, 20, 12), "LMFP": (18, 15, 11, 7), "NMC_high": (12, 5, 2, 1)},
        "medium": {"solid_state": (0, 0, 28, 50), "Na_ion": (0, 12, 15, 14),
                   "LFP": (50, 48, 30, 18), "LMFP": (22, 32, 25, 17), "NMC_high": (28, 8, 2, 1)},
        "large":  {"solid_state": (0, 2, 45, 70), "Na_ion": (0, 3, 5, 5),
                   "LFP": (8, 18, 12, 6), "LMFP": (17, 49, 33, 17), "NMC_high": (75, 28, 5, 2)},
    })

    # Plain-language label and a likelihood, carried onto every figure so a
    # scenario is never read as a forecast. The probabilities are a judgement
    # about the distinguishing clause of each, and scenarios 2 and 3 are NOT
    # independent -- 3 is 2 plus a later step.
    # SAFE TO CHANGE: yes.
    scenario_labels: dict[str, str] = field(default_factory=lambda: {
        "scenario_1": "S1 · LFP volume, NMC premium, nothing new — reference case (~10% to hold to 2070)",
        "scenario_2": "S2 · sodium enters, NMC shrinks to a niche (~55%)",
        "scenario_3": "S3 · S2 plus bipolar solid-state from 2040 (~40% by 2050)",
    })

    # Colour per chemistry across the scenario figures. LFP/NCA/NMC match the
    # ev_details colours so the observed and projected figures read together.
    # SAFE TO CHANGE: yes -- presentation only.
    # One colour per WORKBOOK CHEMISTRY, for the composition figures (07, 08).
    # NOTE the name: ev_details.chemistry_colours is a DIFFERENT map, keyed by
    # market chemistry (LFP, NCA, NMC_middle, NMC_high) for figure 04. These are
    # keyed by the workbook's own Layer 1 names.
    # Separate from scenario_colours below, which colours the seven SCENARIO
    # chemistries: those group battLiMFP with battLiMO, and battLiNMC_midNi with
    # battLiNMC_lowNi, so reusing them drew two pairs of lines in one colour and
    # made them impossible to tell apart.
    # SAFE TO CHANGE: yes. Every chemistry in the workbook needs an entry.
    workbook_chemistry_colours: dict[str, str] = field(default_factory=lambda: {
        "battLiFP_subsub": "#2f8f5b",     # LFP, green
        "battLiMFP_subsub": "#7fbf7b",    # LMFP, lighter green
        "battLiMO_subsub": "#1b7837",     # LMO, darker green
        "battLiNCA_subsub": "#b07aa1",    # NCA, mauve
        "battLiNMC_highNi": "#1f5f8b",    # blue
        "battLiNMC_midNi": "#e08214",     # orange
        "battLiNMC_lowNi": "#8c3d04",     # darker brown-orange
        "Na_ion": "#d9a441",              # sand
        "solid_state": "#6a51a3",         # violet
    })

    scenario_colours: dict[str, str] = field(default_factory=lambda: {
        "LFP": "#2f8f5b", "LMFP": "#7fbf7b", "NMC_high": "#1f5f8b",
        "NMC_middle": "#e08214", "NCA": "#b07aa1",
        "Na_ion": "#d9a441", "solid_state": "#6a51a3",
    })

    # SAFE TO CHANGE: yes. Keep the .png suffix.
    scenario_file_name: str = "chemistry_scenarios_to_2070.png"
    scenario_figure_size_in: tuple[float, float] = (16.0, 9.0)



@dataclass
class ExportParams:
    """
    The composition files handed to the stock-and-flow model.

    ONE FILE PER CHEMISTRY, one row per component/material/element, for ONE CAR
    of a given segment in a given year. No chemistry mixing happens here: the
    scenario shares are applied downstream, where the fleet numbers are. That
    split is deliberate -- this project knows what a battery is made of, the
    stock-and-flow model knows how many there are, and mixing the two here would
    bake a scenario into a file that ought to outlive it.
    """

    # Where the files go, relative to the project root. Untracked like the rest
    # of data/.
    # SAFE TO CHANGE: yes.
    composition_output_dir: str = "data/composition"

    # Every fifth year, as agreed -- the full annual grid would be five times
    # the rows for an interpolation that is smooth between them anyway.
    # SAFE TO CHANGE: yes.
    first_export_year: int = 2020
    last_export_year: int = 2070
    export_year_step: int = 5

    # ⚠️ WHAT HAPPENS TO CAPACITY AFTER THE DATA ENDS. The fitted capacity per
    # segment runs to 2026 and no further; everything beyond is an assumption,
    # and this is where it is made.
    #   'hold'   the 2026 fitted capacity, unchanged, to 2070
    #   'trend'  continues the 2016-2026 gradient linearly
    # 'hold' is the default because it is the assumption that adds least: pack
    # capacity has been flattening in most segments since 2023, and continuing a
    # decade of growth for another forty-four years would put C-segment cars at
    # well over 100 kWh with nothing supporting it.
    # SAFE TO CHANGE: yes -- 'trend' is there to bound the other side.
    capacity_projection: str = "hold"

    # ⚠️ WHERE THE CHEMISTRY COST SAVING GOES. NMC -> LFP -> sodium each cut the
    # pack cost, and that saving can be taken as a cheaper car or as a bigger
    # battery. This is the switch, and it is an ASSUMPTION about buyer and maker
    # behaviour, not a fitted trend.
    #   'saturate'  all of it goes to price; capacity follows capacity_projection
    #   'grow_low'  part of it goes to capacity, +5% per decade in A-D
    #   'grow_high' more of it goes to capacity, +10% per decade in A-D
    # 'saturate' is the default because it is what the record shows. Across 717
    # A-D models with a German list price, an LFP car at the SAME capacity and
    # segment is 17.7% +/- 1.4 pp cheaper, while at the same PRICE and segment it
    # carries just 2.0% +/- 1.8 pp more kWh -- statistically nothing. Through
    # 2026 the saving went essentially all to price and none to capacity. The
    # grow_* scenarios assume that split changes; nothing measured says it will.
    # SAFE TO CHANGE: yes -- that is the point of the switch.
    capacity_scenario: str = "saturate"

    # Growth per decade under each grow_* scenario, applied to the PROJECTED
    # years only (after each segment's last fitted year), compounding.
    # SAFE TO CHANGE: yes.
    capacity_growth_per_decade: dict[str, float] = field(default_factory=lambda: {
        "grow_low": 0.05,
        "grow_high": 0.10,
    })

    # ⚠️ ONLY THESE SEGMENTS GROW. A-D and their J counterparts are the
    # price-competitive end, where a cheaper chemistry can plausibly be spent on
    # capacity. E, F, JE and JF are left flat: they are not price-constrained
    # (segment F runs at 1256 EUR/kWh against 625-790 in A-C), they stay on
    # NMC/NCA in every scenario, and their median capacity has been flat at
    # ~91 kWh since 2022. Growing them too would be an assumption with the
    # measured evidence against it.
    # SAFE TO CHANGE: yes.
    capacity_growth_segments: tuple[str, ...] = (
        "A", "B", "C", "D", "JA", "JB", "JC", "JD")

    # Cap on the projected capacity, kWh, whatever the projection or a range
    # target says. A trend continued to 2070 has to stop somewhere, and an
    # unbounded one silently leaves the range the composition model will answer
    # for. Raised from 150 to 200 because a 1000 km range target needs 159 kWh
    # in F and 194 in JF, and a cap of 150 was quietly clipping seven of the
    # eleven segments -- which made the mass saving look bigger than the
    # assumption actually gives. Any clipping is now reported.
    # SAFE TO CHANGE: yes, but keep it at or below interpolation.max_capacity_kwh.
    max_projected_capacity_kwh: float = 200.0

    # Levels written. Each becomes its own set of rows, tagged in a 'level'
    # column, so one file answers at whichever detail the caller needs.
    # ⚠️ 'element' does NOT add up to 'component': batteryCellCasing and
    # batteryCellSeparator have no element rows in the workbook, about 8% of
    # pack mass. The files carry both levels precisely so that gap is visible
    # rather than inferred.
    # SAFE TO CHANGE: yes.
    # The critical raw materials, for the CRM figures in 07. Copper is not on
    # the EU CRM list itself but is on the strategic list and is the number the
    # sodium and 800V questions turn on, so it belongs here.
    # SAFE TO CHANGE: yes, to any element the workbook resolves.
    # Carbon is deliberately NOT here: graphite is on the EU list, but it is the
    # anode's bulk material rather than a scarcity question in this model.
    crm_elements: tuple[str, ...] = ("Li", "Co", "Ni", "Mn", "Cu", "Si")

    # Which segment the over-time figures (07) draw. One segment, because these
    # are full-size single-element figures rather than a grid nobody can read.
    # SAFE TO CHANGE: yes, to any segment the composition files contain.
    over_time_figure_segment: str = "JC"

    # Which capacity anchor the distribution figures (08) draw, in kWh. Must be
    # one of the workbook's own anchors -- the per-draw arrays exist only there.
    # SAFE TO CHANGE: yes, to another anchor.
    distribution_figure_capacity_kwh: float = 80.0

    # Where 09 writes the consolidated per-chemistry files, in the input
    # workbook's own schema. Separate from composition_output_dir so the
    # segment-year files and these cannot be confused for each other.
    # SAFE TO CHANGE: yes.
    consolidated_output_dir: str = "data/consolidated"

    # The year the energy-density trajectories are measured AT. Masses in every
    # other year are scaled by density(this year) / density(that year), so this
    # is the year in which the workbook's composition is taken to be true.
    # SAFE TO CHANGE: yes, but it shifts every year's mass, not just one.
    density_base_year: int = 2025

    export_levels: tuple[str, ...] = ("component", "material", "element")

    # Include the Monte Carlo percentile columns.
    # SAFE TO CHANGE: yes -- dropping them makes the files smaller, not better.
    include_uncertainty: bool = True

    # 'csv' or 'xlsx'. CSV by default: these are handed to another model, and a
    # csv is diffable, streamable and cannot carry a stale cached formula.
    # SAFE TO CHANGE: yes.
    export_format: str = "csv"

    # ⚠️ WHAT A COMPONENT IS MADE OF, WHERE THE WORKBOOK DOES NOT SAY.
    #
    # The workbook resolves batteryCellCasing at 'm-c' only, and with no Layer 3
    # column it never names the material -- so the casing is one of the
    # components that vanishes entirely at element level (100% of its own mass,
    # ~0.08 kg/kWh). Stating the materials here puts the name back on rows that
    # otherwise carry none.
    #
    # A share of None means: the material IS present, the SPLIT is not known.
    # Those rows are written with the material named and the mass left empty,
    # marked 'material_known_split_unknown'. Give real fractions -- they must sum
    # to 1 -- and the component's mass is divided among them instead, which is
    # what the casing now does: 40% aluminium, 60% plastics, supplied 2026-09-08.
    #
    # NOTE that 'plastics' is a material, not an element: it will never appear at
    # element level. Resolving the casing at element level needs the polymer
    # broken into C/H/O, which nobody here has done, so the element-level gap for
    # this component stays open even once the split is filled in.
    # SAFE TO CHANGE: yes -- this is exactly the parameter to edit when the
    # aluminium-to-plastics ratio is known.
    component_material_overrides: dict[str, dict] = field(default_factory=lambda: {
        "batteryCellCasing": {"Al": 0.40, "plastics": 0.60},
    })

    # WRITE A FILE FOR THE CHEMISTRIES WITH NO COMPOSITION TOO -- sodium-ion and
    # bipolar solid-state -- with every mass left EMPTY and marked unknown,
    # rather than leaving them out. A missing file is easy to overlook
    # downstream; a file full of blanks with a status column is not, and the
    # stock-and-flow model can carry the chemistry through and see the gap
    # arrive rather than silently dropping that share of the fleet.
    # SAFE TO CHANGE: yes.
    write_unknown_chemistries: bool = True

    # ⚠️ THE ROW SKELETON FOR THOSE CHEMISTRIES IS A STRUCTURAL ASSUMPTION, and
    # the ONLY thing asserted about them. No mass, no kg/kWh, no uncertainty is
    # written -- those columns are empty and `composition_status` says why.
    #
    #   based_on            whose component list is borrowed, and nothing else
    #   remove_components   components that chemistry does not have
    #   element_swaps       PER COMPONENT: {component: {from: to}}. Scoped on
    #                       purpose. A blanket Cu -> Al swap would also turn the
    #                       pack cables aluminium, which is wrong -- the cables
    #                       stay copper whatever the cell chemistry is. Copper
    #                       against aluminium is exactly what differs between
    #                       these battery types, and only on the collector.
    #   assert_elements_for  the ONLY components whose element list is claimed.
    #                       Everywhere else the element is written 'unknown',
    #                       because borrowing a component list is not the same
    #                       as knowing what the cathode is made of -- and a row
    #                       saying 'Fe' for a sodium cathode would be a claim
    #                       nobody made, empty mass or not.
    #   note                what a reader has to know before using the row
    #
    # Sodium-ion: aluminium replaces copper as the anode current collector,
    # because sodium does not alloy with aluminium at low potential. That single
    # swap is roughly 0.4 kg Cu/kWh, 55-59% of the pack's copper, and it is the
    # main reason to model sodium at all.
    #
    # Bipolar solid-state: the separator and the liquid electrolyte cease to
    # exist, and stacking cells in series inside the pack removes the per-cell
    # terminals. The anode is lithium or sodium metal rather than graphite --
    # which of the two is undecided, so the anode element is left unknown rather
    # than picked.
    # SAFE TO CHANGE: yes, and it should be, as soon as real data exists -- at
    # which point these chemistries belong in the workbook instead.
    unknown_chemistry_template: dict[str, dict] = field(default_factory=lambda: {
        "Na_ion": {
            "based_on": "battLiFP_subsub",
            "remove_components": (),
            "element_swaps": {"currentCollectorAnode": {"Cu": "Al"},
                              "batteryPackCellTerminals": {"Cu": "Al"}},
            # The pack hardware is chemistry-independent, and the current
            # collectors are the whole point of the sodium case. The cathode,
            # anode and electrolyte are not claimed.
            "assert_elements_for": ("currentCollectorAnode", "currentCollectorCathode",
                                    "batteryCellCasing", "batteryCellSeparator",
                                    "batteryPackCellTerminals",
                                    "batteryPackCables", "batteryPackSupportFrame",
                                    "batteryPackThermalConductor",
                                    "batteryPackModuleEnclosuresAndCoolantManifolds"),
            # The packaging is what can be claimed. Everything here keeps the base
            # chemistry's mass; the cathode, anode and electrolyte stay empty. At
            # 75 kWh that fills 46.7% of the pack and leaves 53.3% open.
                        # EVERYTHING THAT IS NOT THE CHEMISTRY. The can, the separator, the
            # terminals, the collectors and the four pack components. A sodium
            # cell sits in the same steel or aluminium can as a lithium one, in
            # the same format, behind the same porous separator -- nothing about
            # sodium changes those. The workbook files casing and separator under
            # the chemistry's own Layer 1 rather than under battPackXEV, which is
            # bookkeeping, not a statement that they differ.
            #
            # Only the cathode, the anode and the electrolyte are left unclaimed,
            # because only those actually depend on the chemistry.
            #
            # NOTE casing and separator have no element rows anywhere in the
            # workbook, so they add mass at component and material level and
            # nothing at element level -- the same 8% gap every chemistry has.
            "claim_masses_for": ("batteryCellCasing", "batteryCellSeparator",
                                 "batteryPackCellTerminals",
                                 "currentCollectorAnode", "currentCollectorCathode",
                                 "batteryPackCables", "batteryPackSupportFrame",
                                 "batteryPackThermalConductor",
                                 "batteryPackModuleEnclosuresAndCoolantManifolds"),
            # Relabelling copper foil as aluminium without changing its mass would
            # be wrong twice over. Aluminium is 2.70 g/cm3 against copper's 8.96,
            # but it also conducts at only 37.7 MS/m against 59.6, so matching the
            # resistance needs 1.58x the cross-section. Both together:
            #     (59.6 / 37.7) x (2.70 / 8.96) = 0.4764
            # LFP's 27.56 kg of copper becomes 13.13 kg of aluminium -- a 14.43 kg
            # saving, only 2.9% of a 495 kg pack. The mass is not the point. The
            # copper is: that collector is 27.56 of the 45.07 kg of copper in the
            # whole pack, 61%, so a sodium pack carries 17.50 kg -- cables and
            # terminals only.
            # ASSUMPTION, NOT MEASUREMENT: equal conductance. A real cell trades
            # resistance against mass differently, and a move to 800V lowers the
            # current, which relaxes this and pushes the mass back toward the
            # 8.31 kg that pure density scaling would give.
            #
            # Keyed by component AND element, and applied while the row still says
            # copper: the terminals are part aluminium already, and that aluminium
            # must not be scaled by a copper-to-aluminium factor.
            "mass_scale": {"currentCollectorAnode": {"Cu": 0.4764},
                           "batteryPackCellTerminals": {"Cu": 0.4764}},
            "note": ("packaging assumed from LFP -- casing, separator, terminals, "
                     "collectors and pack hardware carry LFP's masses; Al replaces Cu "
                     "as the anode current collector, its mass scaled by 0.4764 for "
                     "equal conductance (density AND conductivity, an assumption); "
                     "cathode, anode and electrolyte are NOT known"),
        },
        "solid_state": {
            "based_on": "battLiNMC_highNi",
            # BIPOLAR MEANS ONE PACKAGE FOR THE WHOLE BATTERY, NOT ONE PER CELL.
            # The cells are stacked directly against each other, so there is no
            # per-cell can and no module enclosure -- only the outer pack. That
            # removes 5.12 kg of cell casing and 33.10 kg of module enclosures and
            # coolant manifolds at 75 kWh, on top of the separator, the liquid
            # electrolyte and the per-cell terminals a bipolar stack also does
            # without.
            "remove_components": ("batteryCellSeparator", "batteryCellElectrolyte",
                                  "batteryPackCellTerminals", "batteryCellCasing",
                                  "batteryPackModuleEnclosuresAndCoolantManifolds"),
            "element_swaps": {},
            # The collectors ARE claimed, at NMC_highNi's aluminium cathode side and
            # COPPER anode side, because the copper is the number that is wanted: if
            # a solid-state cell keeps its copper substrate that is 21.46 kg per car
            # of a critical raw material, and a model that leaves it blank cannot say
            # so either way. It is a claim about an undecided design -- a
            # lithium-metal anode normally keeps the copper, a sodium-metal one would
            # not -- so it is stated here rather than buried.
            "assert_elements_for": ("currentCollectorAnode", "currentCollectorCathode",
                                    "batteryCellCasing",
                                    "batteryPackCables", "batteryPackSupportFrame",
                                    "batteryPackThermalConductor",
                                    "batteryPackModuleEnclosuresAndCoolantManifolds"),
            # Packaging only. At 75 kWh this fills 57.5% of the pack -- higher than
            # sodium's 46.7%, because bipolar construction has already removed the
            # separator, the electrolyte and the per-cell terminals.
                        # The chemistry-independent pack components that survive bipolar
            # construction -- there is NO cell packaging: no casing, no
            # separator, no per-cell terminals, no module enclosures -- plus the
            # current collectors, halved for the shared bipolar plate.
            "claim_masses_for": ("currentCollectorAnode", "currentCollectorCathode",
                                 "batteryPackCables", "batteryPackSupportFrame",
                                 "batteryPackThermalConductor"),
            # ONE CLAD Al-Cu PLATE, reported as its two faces. A bipolar cell has
            # no separate anode and cathode collector: it has a single plate,
            # copper on the face towards the anode and aluminium on the face
            # towards the cathode. The workbook has no name for such a plate and
            # none is invented here, so it is carried as the two collector rows
            # -- but they are two faces of one object, not two foils.
            #
            # THE FACTOR IS A COUNT, not a thickness. A stack of N layers needs
            # N+1 plates where a monopolar pack needs 2N foils: 0.55 at ten
            # layers, 0.525 at twenty, 0.505 at a hundred. 0.5 is the many-layer
            # limit, which is where a real bipolar stack sits.
            #
            # ⚠️ WHAT THIS DOES NOT KNOW is the clad plate's THICKNESS. The count
            # alone justifies 0.5; if the laminate is as thin as one of the foils
            # it replaces rather than as thick as both, the copper halves again.
            "mass_scale": {"currentCollectorAnode": {"Cu": 0.5},
                           "currentCollectorCathode": {"Al": 0.5}},
            "note": ("bipolar: no cell packaging at all -- no separator, no liquid "
                     "electrolyte, no per-cell "
                     "terminals, no cell casing, no module enclosures. The two "
                     "collector rows are the two faces of ONE clad Al-Cu bipolar "
                     "plate, counted at one plate per layer instead of two foils; "
                     "its thickness is not known, so the copper is an upper bound. "
                     "Anode is Li or Na metal, not graphite, so anode and cathode "
                     "are NOT known"),
        },
    })


@dataclass
class TechnologyParams:
    """
    Where a future chemistry's CAPACITY comes from, once energy density stops
    being the binding constraint.

    THE ARGUMENT. Today a battery is as big as the pack you can afford to carry.
    If solid-state reaches 500 Wh/kg, that stops being true: there is no point
    carrying range nobody drives, so capacity saturates at whatever gives a
    sensible range and every further gain in density is taken as LESS MASS.
    Material per car then falls.

    ⚠️ THE ARITHMETIC DOES NOT SUPPORT BOTH HALVES OF THAT AT ONCE, and the
    numbers are the workbook's and the vehicle table's, not a guess. Today's
    real range is 220-667 km by segment (median ~490) at 118-215 Wh/kg pack. At
    500 Wh/kg PACK:

        range target 1000 km  ->  pack mass 0.65-1.07x today (mean ~0.79)
        range target 1500 km  ->  pack mass 0.97-1.61x today -- HEAVIER
        pack mass 2/3 of today -> range 620-1030 km (mean ~850)

    So a third off the material corresponds to about 850 km, not to 1000-1500.
    Chasing 1500 km spends the whole density gain and then some: going from
    ~490 km to 1500 km is a factor 3 in capacity, while 200 -> 500 Wh/kg is a
    factor 2.5 in density.

    The saturation range is therefore the input here and the mass reduction is
    an OUTPUT. Setting both would be over-determined, and the one that has a
    physical argument behind it -- nobody drives 1500 km without stopping -- is
    the range.
    """

    # Whether a chemistry's capacity is set by a range target rather than by
    # continuing its segment's historical capacity.
    # SAFE TO CHANGE: yes. Off means every chemistry keeps the segment capacity
    # from 03, which is the conservative assumption.
    apply_range_saturation: bool = True

    # The range a car is built for once density stops binding, in km, on the
    # real-world consumption in EV_details.csv.
    #
    # SETTLED AT 600 km, and the reason is charging speed rather than range.
    # A cap only bites if it sits below where the market would otherwise go, and
    # today's median real range is already ~490 km -- so 1200 km would not have
    # restrained anything, it would have mandated a 2.4x increase and produced
    # 233 kWh packs, 65% larger than anything in the vehicle table. At 350 kW a
    # 600 km car refills in about fifteen minutes, which is why real ranges have
    # plateaued at 400-600 km instead of climbing: it is cheaper to charge
    # faster than to carry more. Fast charging substitutes for capacity, and
    # that substitution is what makes the material saving real.
    #
    # At 600 km and 500 Wh/kg the pack is 0.48x today's mass -- the density gain
    # is taken as material rather than as range. Compare 1200 km, which gives
    # 0.96x: no saving at all.
    #
    # The pairs, on the fleet mean:
    #
    #     range    500 Wh/kg   600      700      800
    #      600 km    0.48      0.40     0.34     0.30
    #      800 km    0.64      0.53     0.46     0.40
    #     1000 km    0.80      0.66     0.57     0.50
    #     1200 km    0.96      0.80     0.68     0.60
    #     1500 km    1.19      1.00     0.85     0.75
    #
    # Rule of thumb: mass vs today = 0.40 x (range km / pack Wh/kg).
    # SAFE TO CHANGE: yes -- this is THE lever, and the mass saving follows it.
    range_saturation_km: float = 600.0

    # ⚠️ ENERGY DENSITY, AS A TRAJECTORY AND WITH ITS BASIS STATED.
    #
    # Two things were being conflated before and both mattered.
    #
    # FIRST, CELL OR PACK. Solid-state figures in the press are CELL figures.
    # Today's packing ratio in this workbook is 0.59 (NMC high-Ni) to 0.69 (LFP)
    # -- a 356 Wh/kg cell gives a 211 Wh/kg pack. Bipolar stacking should do
    # better, having no per-cell terminals and less module hardware, so 0.80 is
    # assumed below. At that ratio a 400 Wh/kg CELL is a 320 Wh/kg pack, and the
    # difference decides the answer: at a 600 km target, 320 pack is 0.75x
    # today's mass while 500 pack is 0.48x.
    #
    # SECOND, IT IS NOT ONE NUMBER. The first solid-state cells are around
    # 400 Wh/kg and 500-600 follows; a chemistry entering in 2040 and still
    # being built in 2070 does not have one density for thirty years. Values are
    # given at anchor years and interpolated, held flat outside them.
    #
    #     cell Wh/kg   ->  pack at 0.85  ->  mass vs today at 600 km
    #        400              340              0.71x
    #        500              425              0.56x
    #        600              510              0.47x
    #
    # SAFE TO CHANGE: yes. Say which basis you are using -- it is the single
    # easiest thing to get wrong here.
    # WHERE THE WORKBOOK'S OWN ENERGY DENSITY IS NOT BELIEVED, in Wh/kg at CELL
    # level. The composition is rescaled so the cell's kg/kWh matches -- see
    # CompositionModel._apply_density_override. Empty means take the workbook.
    #
    # battLiMFP: the workbook implies 336 Wh/kg, which makes LMFP LIGHTER per kWh
    # than NMC mid-Ni -- 2.947 against 3.179 kg/kWh at the 80 kWh sheet. It cannot
    # be: LMFP is LFP with manganese substituted in, and its advantage is a higher
    # voltage plateau, not a nickel-cobalt cathode. The workbook has it 1.44x
    # better than LFP. Two further signs it is a rescaled LFP rather than a
    # measurement: the ratio to LFP is near-uniform across every component
    # (anode 0.68, cathode 0.71, separator 0.62, collectors 0.58), where a real
    # cathode change would land mostly on the cathode; and every row is
    # count_value = 1, DQS = 2, so it carries no more evidence than the rest.
    # Pinned 2026-09-10 at 270, between LFP's 233 and NMC low-Ni's 285, which
    # restores the physical ordering. It raises LMFP material demand ~24%.
    # SAFE TO CHANGE: yes, and it should change if WP3 revises the workbook.
    cell_density_override_wh_per_kg: dict[str, float] = field(default_factory=lambda: {
        "battLiMFP_subsub": 270.0,
    })

    # WHERE AN ELEMENT'S SHARE OF ITS COMPONENT IS NOT BELIEVED, as a fraction
    # of that component's mass: chemistry -> component -> element -> share.
    #
    # battLiMFP's lithium is 3.45% of its cathode where every other chemistry
    # lands on its own stoichiometry -- LFP 4.59% against 4.40% for LiFePO4, the
    # three NMCs 7.29-7.37% against 7.19%, NCA 7.40%. LMFP cannot be the
    # exception: LiMnxFe1-xPO4 carries the same lithium per formula unit as
    # LiFePO4, and manganese (54.94) and iron (55.85) weigh almost the same, so
    # its share must be LFP's. 3.45% is 22% short.
    #
    # This is the SECOND defect in battLiMFP, after its energy density, from the
    # same count_value = 1, DQS = 2 source. Both are corrected here rather than
    # in the workbook, so a WP3 revision can simply remove them.
    # SAFE TO CHANGE: yes. Element rows do not have to sum to their component --
    # the workbook resolves only part of most components at element level -- so
    # setting one share does not disturb the others.
    element_share_of_component_override: dict[str, dict[str, dict[str, float]]] = field(
        default_factory=lambda: {
            "battLiMFP_subsub": {"cathodeActiveMaterial": {"Li": 0.0440}},
        })

    chemistry_energy_density: dict[str, dict] = field(default_factory=lambda: {
        # 400 Wh/kg is where solid-state cells ARE, not where they arrive in 2040.
        # The old trajectory started at 400 in 2040 and so built in a decade of no
        # progress, and held flat from 2060. Revised 2026-09-10: today's 400
        # doubling to 800 by 2070, on a straight line.
        # This also brings the chemistry forward by ten years -- it now affects
        # results from 2030, as soon as the scenarios put it on the road.
        "solid_state": {
            "basis": "cell",
            "years": (2030, 2040, 2050, 2060, 2070),
            "wh_per_kg": (400.0, 500.0, 600.0, 700.0, 800.0),
        },
        # THE SEVEN LITHIUM CHEMISTRIES. Until 2026-09-10 they had no trajectory
        # at all, so their kg/kWh was frozen forever and a 2070 NMC pack held
        # exactly the materials of a 2030 one. They never improved because the
        # model never let them.
        #
        # Today's values are MEASURED from the workbook -- cell mass at 75 kWh
        # gives the cell's Wh/kg directly, and battLiMFP is post-override at 270.
        # Matthias supplied 330 for NMC and 235 for LFP; the measured 339 and 233
        # are within 3%, and the measured ones are used so that the trajectory and
        # the composition cannot contradict each other. A trajectory saying 330
        # against a composition implying 339 would make the implied pack mass
        # disagree with the sum of its own parts.
        #
        # +30% by 2050, supplied, then FLAT to 2070. Flat is a claim, and the
        # reason is a ceiling: +30% puts NMC at 440 Wh/kg cell, and liquid
        # electrolyte with a graphite or silicon anode runs out near 400-450.
        # Going further needs a lithium-metal anode, which is not this chemistry
        # any more -- it is solid_state, tracked separately. After 2050 the gains
        # come from SWITCHING chemistry, not from improving the old one.
        "battLiFP_subsub":   {"basis": "cell", "years": (2025, 2050, 2070),
                              "wh_per_kg": (233.0, 303.0, 303.0)},
        "battLiMO_subsub":   {"basis": "cell", "years": (2025, 2050, 2070),
                              "wh_per_kg": (231.0, 300.0, 300.0)},
        "battLiMFP_subsub":  {"basis": "cell", "years": (2025, 2050, 2070),
                              "wh_per_kg": (270.0, 351.0, 351.0)},
        "battLiNMC_lowNi":   {"basis": "cell", "years": (2025, 2050, 2070),
                              "wh_per_kg": (285.0, 371.0, 371.0)},
        "battLiNCA_subsub":  {"basis": "cell", "years": (2025, 2050, 2070),
                              "wh_per_kg": (306.0, 398.0, 398.0)},
        "battLiNMC_midNi":   {"basis": "cell", "years": (2025, 2050, 2070),
                              "wh_per_kg": (311.0, 404.0, 404.0)},
        "battLiNMC_highNi":  {"basis": "cell", "years": (2025, 2050, 2070),
                              "wh_per_kg": (339.0, 441.0, 441.0)},

        # Sodium improves too, and treating it as static was wrong: without a
        # trajectory it had no pack mass, so its unknown active material could
        # carry no number at all while solid-state's could.
        # Supplied 2026-09-10, at CELL level.
        # Held flat after 2050 -- np.interp does not extrapolate, so 2060 and
        # 2070 stay at 220. That is an assumption of stagnation, not a forecast;
        # add later years here if that is wrong.
        "Na_ion": {
            "basis": "cell",
            "years": (2030, 2040, 2050),
            "wh_per_kg": (160.0, 200.0, 220.0),
        },
    })

    # Cell-to-pack packing ratio, used only when 'basis' above is 'cell'.
    # Today's workbook chemistries sit at 0.59-0.69; bipolar solid-state beats
    # that, needing no per-cell terminals and less module hardware. 0.85 was
    # supplied 2026-09-08 and is no longer a guess -- it is the highest of the
    # plausible range, so it is the optimistic end of this assumption.
    # SAFE TO CHANGE: yes, and it is not a detail: 0.70 instead of 0.85 moves a
    # 600 Wh/kg cell from a 510 to a 420 Wh/kg pack, and the mass at 600 km from
    # 0.47x to 0.57x of today.
    cell_to_pack_ratio: dict[str, float] = field(default_factory=lambda: {
        "solid_state": 0.85,
        # The seven lithium chemistries, MEASURED from the workbook at 75 kWh --
        # cell mass over pack mass. battLiMFP is 0.616 rather than the 0.563 it
        # showed before its density override, because pinning the cell heavier
        # raises the cell's share of a pack whose hardware did not change.
        # Each is an approximation: the real ratio rises with capacity, because
        # the pack hardware does not scale with the cells.
        "battLiFP_subsub": 0.650,
        "battLiMFP_subsub": 0.616,
        "battLiMO_subsub": 0.652,
        "battLiNCA_subsub": 0.585,
        "battLiNMC_highNi": 0.561,
        "battLiNMC_lowNi": 0.603,
        "battLiNMC_midNi": 0.582,

        # MEASURED, not chosen: this is LFP's own ratio in the workbook, which is
        # where sodium's packaging comes from. Sodium is a conventional format
        # with a normal casing, so it has no reason to beat LFP.
        # It is an approximation, because the real ratio moves with capacity --
        # LFP is 0.567 at 45 kWh, 0.650 at 75 and 0.687 at 100, since the pack
        # hardware does not scale with the cells. 0.650 is the middle of the
        # range this project exports.
        # SAFE TO CHANGE: yes, and worth about 25% of pack mass at the extremes.
        "Na_ion": 0.650,
    })

    # Real-world consumption per segment, Wh/km, used to turn a range target
    # into a capacity. Left empty, it is taken from EV_details.csv -- the median
    # of models introduced from 2022 on, which is 132 Wh/km for A rising to 194
    # for JF. Fill it to override.
    # SAFE TO CHANGE: yes. Note these are MILD-weather figures; the cold-weather
    # column is about 35% higher, and a car built for 1000 km in January is a
    # third bigger again.
    segment_consumption_wh_per_km: dict[str, float] = field(default_factory=dict)

    # Models introduced from this year on are used for the consumption median.
    # SAFE TO CHANGE: yes.
    consumption_from_year: int = 2022

    # The chemistry whose pack mass today is the comparison for "material
    # reduced by a third".
    # SAFE TO CHANGE: yes.
    reference_chemistry: str = "battLiNMC_highNi"


# ======================================================================
#  END OF SETTINGS.  Below here is plumbing.
# ======================================================================

@dataclass
class Params:
    """Every setting, in one object."""

    SECTIONS = ("paths", "scope", "drawing", "interpolation", "monte_carlo", "capacity_figure",
                "ev_details", "scenarios",
                "technology", "export")

    paths: PathParams = field(default_factory=PathParams)
    scope: ScopeParams = field(default_factory=ScopeParams)
    drawing: DrawingParams = field(default_factory=DrawingParams)
    interpolation: InterpolationParams = field(default_factory=InterpolationParams)
    monte_carlo: MonteCarloParams = field(default_factory=MonteCarloParams)
    capacity_figure: CapacityFigureParams = field(default_factory=CapacityFigureParams)
    ev_details: EVDetailsParams = field(default_factory=EVDetailsParams)
    scenarios: ScenarioParams = field(default_factory=ScenarioParams)
    technology: TechnologyParams = field(default_factory=TechnologyParams)
    export: ExportParams = field(default_factory=ExportParams)

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

    def composition_output_path(self, project_root, file_name: str) -> "Path":
        """Where an exported composition file goes, folder created if needed."""
        from pathlib import Path
        directory = Path(project_root) / self.export.composition_output_dir
        directory.mkdir(parents=True, exist_ok=True)
        return directory / file_name

    def export_years(self) -> list[int]:
        return list(range(self.export.first_export_year,
                          self.export.last_export_year + 1,
                          self.export.export_year_step))

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
        if ev.capacity_fallback not in ("segment_median", "reference_map"):
            raise ParameterError(
                f"ev_details.capacity_fallback must be 'segment_median' or "
                f"'reference_map': {ev.capacity_fallback!r}")
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
        if not ev.chemistry_groups:
            raise ParameterError("ev_details.chemistry_groups is empty.")
        seen: dict[str, str] = {}
        for group, values in ev.chemistry_groups.items():
            for value in values:
                if value in seen:
                    raise ParameterError(
                        f"cathode value {value!r} is in two chemistry groups, "
                        f"{seen[value]!r} and {group!r} -- a model would be counted twice.")
                seen[value] = group
        clash = sorted(set(ev.chemistry_values_left_out) & set(seen))
        if clash:
            raise ParameterError(
                f"{clash} are both grouped and listed in chemistry_values_left_out. "
                "Being left out is the opposite of being grouped -- pick one.")
        without_colour = sorted(set(ev.chemistry_groups) - set(ev.chemistry_colours))
        if without_colour:
            raise ParameterError(
                f"no ev_details.chemistry_colours entry for {without_colour}.")
        if ev.min_models_per_chemistry_cell < 1:
            raise ParameterError(
                "ev_details.min_models_per_chemistry_cell must be at least 1: "
                f"{ev.min_models_per_chemistry_cell}")
        sc = self.scenarios
        grouped_segments = [seg for group in sc.segment_groups.values() for seg in group]
        if len(grouped_segments) != len(set(grouped_segments)):
            raise ParameterError(
                "a segment appears in more than one scenarios.segment_groups entry -- "
                "its share would be counted twice.")
        if len(sc.anchor_years) < 2:
            raise ParameterError(
                f"scenarios.anchor_years needs at least two years: {sc.anchor_years}")
        if list(sc.anchor_years) != sorted(sc.anchor_years):
            raise ParameterError(
                f"scenarios.anchor_years must ascend: {sc.anchor_years}")
        for name in ("scenario_1", "scenario_2", "scenario_3"):
            definition = getattr(sc, name)
            if name not in sc.scenario_labels:
                raise ParameterError(f"no scenarios.scenario_labels entry for {name!r}.")
            missing_groups = sorted(set(sc.segment_groups) - set(definition))
            if missing_groups:
                raise ParameterError(
                    f"scenarios.{name} has no shares for segment group(s) "
                    f"{missing_groups}.")
            for group, chemistries in definition.items():
                if group not in sc.segment_groups:
                    raise ParameterError(
                        f"scenarios.{name} sets shares for {group!r}, which is not a "
                        f"segment group ({sorted(sc.segment_groups)}).")
                for chemistry, shares in chemistries.items():
                    if chemistry not in sc.scenario_colours:
                        raise ParameterError(
                            f"no scenarios.scenario_colours entry for {chemistry!r} "
                            f"(used in {name}.{group}).")
                    if len(shares) != len(sc.anchor_years):
                        raise ParameterError(
                            f"scenarios.{name}.{group}.{chemistry} has {len(shares)} "
                            f"shares but there are {len(sc.anchor_years)} anchor years.")
                    if any(share < 0 for share in shares):
                        raise ParameterError(
                            f"negative share in scenarios.{name}.{group}.{chemistry}: "
                            f"{shares}")
                totals = [sum(shares[i] for shares in chemistries.values())
                          for i in range(len(sc.anchor_years))]
                far_off = [(year, total) for year, total in zip(sc.anchor_years, totals)
                           if abs(total - 100) > 5]
                if far_off:
                    raise ParameterError(
                        f"scenarios.{name}.{group} shares are meant to be percentages "
                        f"of that group's market and are far from 100 at {far_off}. "
                        "Small drift is normalised away; this is too big to be a "
                        "rounding slip.")

        tech = self.technology
        if tech.range_saturation_km <= 0:
            raise ParameterError(
                f"technology.range_saturation_km must be positive: "
                f"{tech.range_saturation_km}")
        for chemistry, entry in tech.chemistry_energy_density.items():
            # Either naming is allowed: the SCENARIO chemistries (Na_ion,
            # solid_state) and the WORKBOOK ones (battLiFP_subsub, ...). Both are
            # real chemistries with real trajectories; this check exists to catch
            # a typo, not to insist on one vocabulary.
            if (chemistry not in sc.scenario_colours
                    and chemistry not in sc.workbook_chemistry_colours):
                raise ParameterError(
                    f"technology.chemistry_energy_density names {chemistry!r}, which "
                    "is neither a scenario chemistry nor a workbook chemistry.")
            missing = sorted({"basis", "years", "wh_per_kg"} - set(entry))
            if missing:
                raise ParameterError(
                    f"technology.chemistry_energy_density[{chemistry!r}] is missing "
                    f"{missing}.")
            if entry["basis"] not in ("cell", "pack"):
                raise ParameterError(
                    f"technology.chemistry_energy_density[{chemistry!r}]['basis'] must "
                    f"be 'cell' or 'pack': {entry['basis']!r}. Getting this wrong is "
                    "worth about 25% of the pack mass.")
            if len(entry["years"]) != len(entry["wh_per_kg"]):
                raise ParameterError(
                    f"technology.chemistry_energy_density[{chemistry!r}] has "
                    f"{len(entry['years'])} years and {len(entry['wh_per_kg'])} "
                    "densities.")
            if list(entry["years"]) != sorted(entry["years"]):
                raise ParameterError(
                    f"technology.chemistry_energy_density[{chemistry!r}]['years'] must "
                    f"ascend: {entry['years']}")
            if any(value <= 0 for value in entry["wh_per_kg"]):
                raise ParameterError(
                    f"technology.chemistry_energy_density[{chemistry!r}] densities must "
                    f"be positive: {entry['wh_per_kg']}")
            if entry["basis"] == "cell" and chemistry not in tech.cell_to_pack_ratio:
                raise ParameterError(
                    f"technology.chemistry_energy_density[{chemistry!r}] is on the CELL "
                    "basis but has no technology.cell_to_pack_ratio entry, so it cannot "
                    "be turned into a pack figure.")
        bad_ratio = {name: value for name, value in tech.cell_to_pack_ratio.items()
                     if not 0 < value <= 1}
        if bad_ratio:
            raise ParameterError(
                f"technology.cell_to_pack_ratio values must be in (0, 1]: {bad_ratio}")
        bad_consumption = {name: value
                           for name, value in tech.segment_consumption_wh_per_km.items()
                           if value <= 0}
        if bad_consumption:
            raise ParameterError(
                f"technology.segment_consumption_wh_per_km values must be positive "
                f"Wh/km: {bad_consumption}")

        ex = self.export
        if ex.export_year_step < 1:
            raise ParameterError(
                f"export.export_year_step must be at least 1: {ex.export_year_step}")
        if ex.first_export_year > ex.last_export_year:
            raise ParameterError(
                f"export.first_export_year ({ex.first_export_year}) is after "
                f"last_export_year ({ex.last_export_year}).")
        if ex.capacity_projection not in ("hold", "trend"):
            raise ParameterError(
                f"export.capacity_projection must be 'hold' or 'trend': "
                f"{ex.capacity_projection!r}")
        grow_names = tuple(ex.capacity_growth_per_decade)
        if ex.capacity_scenario not in ("saturate",) + grow_names:
            raise ParameterError(
                "export.capacity_scenario must be 'saturate' or one of "
                f"{grow_names}: {ex.capacity_scenario!r}")
        for name, rate in ex.capacity_growth_per_decade.items():
            if not name.startswith("grow"):
                raise ParameterError(
                    "export.capacity_growth_per_decade keys must start with 'grow' "
                    f"so no scenario can be confused with 'saturate': {name!r}")
            if not 0.0 <= float(rate) < 1.0:
                raise ParameterError(
                    f"export.capacity_growth_per_decade[{name!r}] must be in [0, 1): "
                    f"{rate!r}")
        if ex.capacity_scenario != "saturate" and not ex.capacity_growth_segments:
            raise ParameterError(
                f"export.capacity_scenario is {ex.capacity_scenario!r} but "
                "export.capacity_growth_segments is empty -- nothing would grow.")
        if ex.max_projected_capacity_kwh > self.interpolation.max_capacity_kwh:
            raise ParameterError(
                f"export.max_projected_capacity_kwh ({ex.max_projected_capacity_kwh}) "
                f"is above interpolation.max_capacity_kwh "
                f"({self.interpolation.max_capacity_kwh}), so the export would ask the "
                "composition model for a capacity it refuses to answer for.")
        unknown_levels = sorted(set(ex.export_levels) - {"component", "material", "element"})
        if unknown_levels:
            raise ParameterError(
                f"export.export_levels may only contain 'component', 'material' and "
                f"'element': {unknown_levels}")
        if not ex.export_levels:
            raise ParameterError("export.export_levels is empty -- nothing to write.")
        for component, materials in ex.component_material_overrides.items():
            if not materials:
                raise ParameterError(
                    f"export.component_material_overrides[{component!r}] is empty.")
            shares = [share for share in materials.values() if share is not None]
            if shares and len(shares) != len(materials):
                raise ParameterError(
                    f"export.component_material_overrides[{component!r}] mixes known "
                    f"and unknown shares: {materials}. Either every material has a "
                    "fraction or none does -- a half-known split would be written as "
                    "though the missing part did not exist.")
            if shares and abs(sum(shares) - 1.0) > 1e-6:
                raise ParameterError(
                    f"export.component_material_overrides[{component!r}] shares must "
                    f"sum to 1, not {sum(shares)}: {materials}")
            if any(share is not None and not 0 <= share <= 1 for share in materials.values()):
                raise ParameterError(
                    f"export.component_material_overrides[{component!r}] shares must be "
                    f"fractions in [0, 1]: {materials}")

        for chemistry, template in ex.unknown_chemistry_template.items():
            if chemistry not in sc.chemistries_without_composition:
                raise ParameterError(
                    f"export.unknown_chemistry_template has an entry for {chemistry!r}, "
                    "which is NOT in scenarios.chemistries_without_composition. If it "
                    "now has a real composition, delete the template rather than "
                    "leaving a skeleton that will quietly override it.")
            missing_keys = sorted({"based_on", "remove_components", "element_swaps",
                                   "assert_elements_for", "claim_masses_for",
                                   "mass_scale", "note"} - set(template))
            if missing_keys:
                raise ParameterError(
                    f"export.unknown_chemistry_template[{chemistry!r}] is missing "
                    f"{missing_keys}.")
        if ex.write_unknown_chemistries:
            untemplated = sorted(set(sc.chemistries_without_composition)
                                 - set(ex.unknown_chemistry_template))
            if untemplated:
                raise ParameterError(
                    f"{untemplated} have no composition and no "
                    "export.unknown_chemistry_template entry, so no file could be "
                    "written for them at all -- add a template or set "
                    "export.write_unknown_chemistries = False.")
        if ex.export_format not in ("csv", "xlsx"):
            raise ParameterError(
                f"export.export_format must be 'csv' or 'xlsx': {ex.export_format!r}")

        if not sc.scenario_file_name.endswith(".png"):
            raise ParameterError(
                f"scenarios.scenario_file_name must end in '.png': {sc.scenario_file_name!r}")

        if "{basis}" not in ev.capacity_by_chemistry_file_name:
            raise ParameterError(
                "ev_details.capacity_by_chemistry_file_name must contain '{basis}': "
                f"{ev.capacity_by_chemistry_file_name!r}")
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
