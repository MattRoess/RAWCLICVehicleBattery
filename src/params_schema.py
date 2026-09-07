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
class ScopeParams:
    """Which part of the workbook this project reads."""

    # The consolidated composition workbook. It is not tracked in git -- no data
    # file goes to GitHub -- so a fresh clone has to be given it.
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


# ======================================================================
#  END OF SETTINGS.  Below here is plumbing.
# ======================================================================

@dataclass
class Params:
    """Every setting, in one object."""

    SECTIONS = ("scope", "drawing")

    scope: ScopeParams = field(default_factory=ScopeParams)
    drawing: DrawingParams = field(default_factory=DrawingParams)

    def sheet_names(self) -> list[str]:
        """The workbook sheets in scope, in the order the capacities are listed."""
        return [self.scope.sheet_name_template.format(kwh=kwh)
                for kwh in self.scope.bev_capacities_kwh]

    def validate(self) -> None:
        """Every check that can be made without opening the workbook."""
        scope, drawing = self.scope, self.drawing

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
