"""
01_draw_battery_structure.py
============================

Draws the product structure of a BEV traction battery: every component that
makes up the product, labelled with the component code the workbook uses.

    ./.venv/bin/python 00_parameters.py            # first, always
    ./.venv/bin/python 01_draw_battery_structure.py

Writes the PNG named by `drawing.output_file_name` to the project root.

EVERY SETTING LIVES IN `src/params_schema.py` -- which sizes are in scope, the
drawing geometry, the component glosses and colours. Nothing is hardcoded here.

Everything else is READ FROM THE WORKBOOK: which components exist, which branch
they sit on, their kg/kWh range and which levels of detail resolve them. If the
workbook changes, the drawing changes with it.

The structure is identical across all five BEV sizes -- verified, not assumed
(see `_check_structure_is_shared`). Only the values differ, which is why each
box carries a RANGE across the sizes and chemistries rather than a single number.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib
matplotlib.use("Agg")  # never opens a window -- always writes to file
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402
import pandas as pd  # noqa: E402

from src.params_schema import ParameterError, Params, current  # noqa: E402
from src.sodium_composition import (ACTIVE_COMPONENTS, ANODE, CATHODE,  # noqa: E402
                                    ELECTROLYTE, REMAINDER)

INK = "#1c1c1c"
MUTED = "#5c5c5c"
EDGE = "#8a8a8a"

# One line per chemistry built here, under each box. The box is as tall as its
# title, gloss, c-p and e-c lines (10.1) plus one 1.35 line per chemistry: 12.8
# for two, which this used to be fixed at, and 15.5 for the four there are now.
# Left at 12.8 when the two sodium cells arrived, the diagram showed neither of
# them anywhere and went on saying no composition exists for sodium.
def box_height(variants: int) -> float:
    return 10.1 + 1.35 * variants


# The one component the workbook does not have: the cell mass the sodium cells'
# electrochemistry does not explain.
UNITEMISED_COLOUR = "#e4eef5"
BUILT = "#1f5f8b"


def load_bev_rows(params: Params) -> pd.DataFrame:
    """The BEV sheets in scope, concatenated, with the sheet kept as a column."""
    path = params.composition_path(PROJECT_ROOT)
    if not path.exists():
        raise SystemExit(
            f"Input workbook not found: {path}\n"
            "Nothing under data/ is tracked in git -- copy the workbook in from iCloud.")

    frames = []
    for sheet_name in params.sheet_names():
        # keep_default_na=False: 'Layer 4' holds a literal 'n/a' on every row
        # that is not at element level. Under pandas' defaults that becomes NaN
        # and the levels of detail stop being distinguishable.
        frame = pd.read_excel(path, sheet_name=sheet_name,
                              keep_default_na=False, na_values=[""])
        frames.append(frame.assign(sheet=sheet_name))
    return pd.concat(frames, ignore_index=True)


def _check_structure_is_shared(rows: pd.DataFrame, params: Params) -> None:
    """The drawing shows ONE structure for every size in scope. Prove that."""
    component_rows = rows[rows.parameterCode == params.scope.component_parameter_code]
    per_sheet = {
        sheet: set(map(tuple, group[["Layer 1", "Layer 2"]].drop_duplicates().values))
        for sheet, group in component_rows.groupby("sheet")
    }
    first, *rest = per_sheet.values()
    if any(other != first for other in rest):
        raise SystemExit(
            "The BEV sheets in scope do NOT share one component structure any "
            "more. One drawing can no longer stand for all of them -- rework this "
            "script rather than drawing a structure true of only some sizes.")


def build_components(rows: pd.DataFrame, params: Params) -> tuple[list[dict], list[dict]]:
    """Everything each box needs, derived from the workbook."""
    _check_structure_is_shared(rows, params)
    scope, drawing = params.scope, params.drawing

    component_rows = rows[rows.parameterCode == scope.component_parameter_code]
    element_rows = rows[rows.parameterCode == scope.element_parameter_code]
    material_rows = rows[rows.parameterCode == scope.material_parameter_code]

    cell_side: list[dict] = []
    pack_side: list[dict] = []
    for (is_pack, name), group in component_rows.groupby(
        [component_rows["Layer 1"].eq(scope.pack_level_key), "Layer 2"]
    ):
        elements = sorted(set(element_rows.loc[element_rows["Layer 2"] == name, "Layer 4"]))
        role = "pack" if is_pack else drawing.component_role.get(name, "cell_body")
        entry = {
            "name": name,
            "gloss": drawing.component_gloss.get(name, ""),
            "low": group["Value"].min(),
            "high": group["Value"].max(),
            "elements": elements,
            "material_level_only": not elements and bool((material_rows["Layer 2"] == name).any()),
            "colour": drawing.role_colours.get(role, drawing.role_colours["cell_body"]),
        }
        (pack_side if is_pack else cell_side).append(entry)

    missing_gloss = [c["name"] for c in cell_side + pack_side if not c["gloss"]]
    if missing_gloss:
        print(f"NOTE: no gloss for {missing_gloss} -- drawn as bare codes. Add them "
              f"to drawing.component_gloss in src/params_schema.py.")

    def in_order(entries: list[dict], order: tuple[str, ...]) -> list[dict]:
        ranked = {name: i for i, name in enumerate(order)}
        # An unranked component sorts to the end rather than disappearing: a new
        # component in the workbook must show up, not vanish from the drawing.
        return sorted(entries, key=lambda e: (ranked.get(e["name"], len(order)), e["name"]))

    return (in_order(cell_side, drawing.cell_component_order),
            in_order(pack_side, drawing.pack_component_order))


def variant_notes(params, components: list[str]) -> dict[str, list[tuple[str, str]]]:
    """
    What each chemistry built here does to each component, read from
    export.unknown_chemistry_template and export.literature_chemistry_template
    rather than restated here. If a template changes, this diagram changes with
    it instead of quietly going stale.

    Four statuses: IN (claimed from the base chemistry, with what was changed),
    ABSENT, NOT KNOWN (the two with no composition), and BUILT (a sodium cell's
    cathode, anode and electrolyte, made from literature and drawn).
    """
    notes: dict[str, list[tuple[str, str]]] = {}
    short = {"Na_ion": "Na-ion", "solid_state": "solid-state",
             "Na_ion_layered": "Na-ion layered",
             "Na_ion_prussian_white": "Na-ion Prussian white"}
    IN, OUT, GAP = "#1b6b3a", "#8a8f96", "#b03030"
    literature = params.export.literature_chemistry_template
    templates = {**params.export.unknown_chemistry_template, **literature}
    for chemistry, template in templates.items():
        label = short.get(chemistry, chemistry)
        built = chemistry in literature
        removed = set(template["remove_components"])
        claimed = set(template["claim_masses_for"])
        swaps = template["element_swaps"]
        scales = template.get("mass_scale", {})
        for component in components:
            if component == REMAINDER:
                notes.setdefault(component, []).append(
                    (f"{label}: built (drawn)", BUILT) if built
                    else (f"{label}: absent", OUT))
            elif component in removed:
                notes.setdefault(component, []).append(
                    (f"{label}: absent", OUT))
            elif built and component in ACTIVE_COMPONENTS:
                notes.setdefault(component, []).append(
                    (f"{label}: built, {built_elements(params, chemistry, component)}",
                     BUILT))
            elif component in claimed:
                detail = []
                for old_element, new_element in swaps.get(component, {}).items():
                    detail.append(f"{new_element}\u2190{old_element}")
                for element, factor in scales.get(component, {}).items():
                    detail.append(f"x{factor:g}")
                suffix = f" ({', '.join(detail)})" if detail else ""
                notes.setdefault(component, []).append(
                    (f"{label}: in{suffix}", IN))
            else:
                notes.setdefault(component, []).append(
                    (f"{label}: NOT KNOWN", GAP))
    return notes


def built_elements(params, chemistry: str, component: str) -> str:
    """The elements a sodium cell's active component is itemised into."""
    if component == CATHODE:
        return " ".join(params.technology.sodium_cathode[chemistry]["formula"])
    if component == ANODE:
        return "C"
    salt = " ".join(params.technology.sodium_cell["salt_formula"])
    return f"{salt} (salt only)"


def draw_box(ax, x, y, width, height, entry: dict) -> None:
    ax.add_patch(FancyBboxPatch(
        (x, y), width, height, boxstyle="round,pad=0,rounding_size=0.6",
        facecolor=entry["colour"], edgecolor=EDGE, linewidth=0.8,
    ))
    ax.text(x + 0.7, y + height - 1.5, entry["name"], fontsize=8.2, fontweight="bold",
            family="DejaVu Sans Mono", color=INK, va="top")
    if entry["gloss"]:
        # 2.3 below the title, not 1.4: at 8.2pt over 7.2pt the old gap put the
        # descenders of one into the ascenders of the other.
        ax.text(x + 0.7, y + height - 3.3, entry["gloss"], fontsize=7.2,
                style="italic", color=MUTED, va="top")
    variants = entry.get("variants", [])
    # The chemistry lines get their own band at the bottom, under a rule. They
    # used to be right-aligned at y+1.0 and y+2.15 -- exactly where e-c and c-p
    # already sat -- so on any box with a long element list they overprinted it.
    band = 1.35 * len(variants) + 0.9 if variants else 0.0
    floor = y + band

    ax.text(x + 0.7, floor + 2.3,
            entry.get("c_p_text") or f"c-p  {entry['low']:.2f}–{entry['high']:.2f} kg/kWh",
            fontsize=7.0, color=INK, va="bottom", family="DejaVu Sans Mono")
    detail = (entry.get("e_c_text")
              or (f"e-c  {', '.join(entry['elements'])}" if entry["elements"]
                  else "m-c only — no element split"))
    ax.text(x + 0.7, floor + 0.85, detail, fontsize=7.0,
            color=INK if entry["elements"] else MUTED,
            va="bottom", family="DejaVu Sans Mono")

    if variants:
        ax.plot([x + 0.7, x + width - 0.7], [floor + 0.3, floor + 0.3],
                color=EDGE, linewidth=0.6)
        for offset, (note, colour) in enumerate(reversed(variants)):
            ax.text(x + 0.7, y + 0.65 + offset * 1.35, note, fontsize=6.6,
                    color=colour, va="bottom", family="DejaVu Sans Mono")


def draw(cell_side: list[dict], pack_side: list[dict], params: Params) -> plt.Figure:
    drawing = params.drawing
    sizes = ", ".join(str(kwh) for kwh in params.scope.bev_capacities_kwh)
    n_variants = (len(params.export.unknown_chemistry_template)
                  + len(params.export.literature_chemistry_template))
    box_h = box_height(n_variants)
    # Where the top edge of the first row of boxes sits. The rows HANG from it, so
    # a taller box grows downward instead of into the header above.
    grid_top = 61.2
    n_workbook = sum(1 for entry in cell_side if entry["name"] != REMAINDER)

    fig, ax = plt.subplots(figsize=(drawing.figure_width_in, drawing.figure_height_in * 1.22))
    ax.set_xlim(0, 100)
    ax.set_ylim(-26, 100)
    ax.axis("off")

    ax.text(0, 98.2, "BEV traction battery — product structure",
            fontsize=17, fontweight="bold", color=INK, va="top")
    ax.text(0, 94.6,
            "Every component making up the product, labelled with the workbook's own "
            f"Layer 2 code. Source: {params.scope.composition_file_name}",
            fontsize=9.5, color=MUTED, va="top")
    ax.text(0, 91.8,
            f"Scope: the BEV sizes — BATTinELV_BEV_{{{sizes}}}kWh. All of them share "
            "one structure; only the values differ, so each box shows a range.",
            fontsize=9.5, color=MUTED, va="top")

    # The product node.
    ax.add_patch(FancyBboxPatch((28, 82), 44, 6, boxstyle="round,pad=0,rounding_size=0.6",
                                facecolor="#2f3b46", edgecolor="none"))
    ax.text(50, 85.9, "BEV traction battery pack", fontsize=12, fontweight="bold",
            color="white", ha="center", va="center")
    ax.text(50, 83.4, "additionalSpecification = BATTinELV_BEV_<size>kWh",
            fontsize=8, color="#c9d3dc", ha="center", va="center",
            family="DejaVu Sans Mono")

    # Branch lines from the product node down onto each group's centre.
    ax.plot([50, 50], [82, 79], color=EDGE, linewidth=1.0)
    ax.plot([24.4, 73.7], [79, 79], color=EDGE, linewidth=1.0)
    for branch_x in (24.4, 73.7):
        ax.plot([branch_x, branch_x], [79, 77], color=EDGE, linewidth=1.0)

    # ---- left branch: the cell, one set per chemistry --------------------
    ax.text(0, 76, "CELLS — one set per chemistry", fontsize=11,
            fontweight="bold", color=INK, va="top")
    # Two short lines, not one long one: at x=0 a single line ran under the
    # PACK heading at x=56 and the two overprinted.
    # All NINE Layer 1 values, not the seven in the workbook: Na_ion and
    # solid_state are Layer 1 in the files this project writes, and leaving them
    # off here said the opposite.
    workbook_chemistries = sorted(
        set(params.scenarios.workbook_chemistry_colours)
        - set(params.export.unknown_chemistry_template)
        - set(params.export.literature_chemistry_template))
    ax.text(0, 73.2,
            "Layer 1, in the workbook:  " + " · ".join(workbook_chemistries[:4]) + "\n"
            "                           " + " · ".join(workbook_chemistries[4:]),
            fontsize=7.6, color=MUTED, va="top", family="DejaVu Sans Mono",
            linespacing=1.5)
    ax.text(0, 68.4,
            "Layer 1, built here:       "
            + " · ".join(params.export.unknown_chemistry_template)
            + "\n                           "
            + " · ".join(params.export.literature_chemistry_template),
            fontsize=7.6, color="#6a4b8a", va="top", family="DejaVu Sans Mono",
            linespacing=1.5)
    ax.text(0, 64.9, f"{n_workbook} components per workbook chemistry; the sodium cells "
                     "built from literature add a ninth. The last four lines of every box "
                     "are the four chemistries built here:\n"
                     "green in · grey absent · red not known · blue built from literature.",
            fontsize=8, color=MUTED, va="top")

    for index, entry in enumerate(cell_side):
        column, row = index % 2, index // 2
        draw_box(ax,
                 column * (drawing.box_width + drawing.box_gap_x),
                 grid_top - box_h - row * (box_h + drawing.box_gap_y),
                 drawing.box_width, box_h, entry)

    # ---- right branch: the pack, shared by every chemistry ---------------
    ax.text(56, 76, "PACK — shared by every chemistry", fontsize=11,
            fontweight="bold", color=INK, va="top")
    ax.text(56, 73.2, f"Layer 1 = {params.scope.pack_level_key}", fontsize=8,
            color=MUTED, va="top", family="DejaVu Sans Mono")
    ax.text(56, 70.8, "One set per pack, independent of the cell chemistry inside it.",
            fontsize=8, color=MUTED, va="top")

    for index, entry in enumerate(pack_side):
        draw_box(ax, 56, grid_top - box_h - index * (box_h + drawing.box_gap_y),
                 drawing.box_width + 12, box_h, entry)

    # ---- the chemistries the workbook does not contain -------------------
    # Below the last row of cell boxes, wherever that now is: the rows hang from
    # grid_top, so the bottom is computed. It used to be written down (-1.5), which
    # is only right for exactly eight boxes of exactly two variant lines.
    rows_of_cells = -(-len(cell_side) // 2)
    last_bottom = grid_top - box_h - (rows_of_cells - 1) * (box_h + drawing.box_gap_y)
    ax.text(0, last_bottom - 3.7, "NOT IN THE WORKBOOK — built from a base chemistry",
            fontsize=11, fontweight="bold", color="#6a4b8a", va="top")
    cursor = last_bottom - 3.7 - 3.0

    ax.text(0, cursor, "NO COMPOSITION AT ALL", fontsize=8.6, fontweight="bold",
            color="#6a4b8a", va="top")
    cursor -= 2.5
    for chemistry, template in params.export.unknown_chemistry_template.items():
        ax.text(0, cursor, f"{chemistry:22s} base {template['based_on']}",
                fontsize=7.6, color=INK, va="top", family="DejaVu Sans Mono")
        cursor -= 2.4
    ax.text(0, cursor,
            "Only their PACKAGING is claimed. Cathode, anode and electrolyte are "
            "unknownBatteryMaterial: no composition exists for either chemistry.\n"
            "Na_ion is still written, unchanged, until 04_04 reads the two sodium "
            "cells below instead.",
            fontsize=8, color="#6a4b8a", va="top")
    cursor -= 5.2

    ax.text(0, cursor, "BUILT FROM LITERATURE — a scenario, not a bill of materials",
            fontsize=8.6, fontweight="bold", color=BUILT, va="top")
    cursor -= 2.5
    for chemistry, template in params.export.literature_chemistry_template.items():
        ax.text(0, cursor,
                f"{chemistry:22s} base {template['based_on']}   cathode: "
                f"{built_elements(params, chemistry, CATHODE)}",
                fontsize=7.6, color=INK, va="top", family="DejaVu Sans Mono")
        cursor -= 2.4
    ax.text(0, cursor,
            "Packaging claimed as above. Cathode, anode and electrolyte are an "
            "electrochemical mass balance on published capacities and voltages, every\n"
            "input drawn once per Monte Carlo draw; no whole-cell breakdown of a "
            "commercial sodium-ion cell is public. The mass the balance does not\n"
            "explain is batteryCellUnitemised, a component the workbook does not have.",
            fontsize=8, color=BUILT, va="top")
    cursor -= 6.4

    # ---- reading the box -------------------------------------------------
    ax.text(0, cursor, "Reading a box", fontsize=9.5, fontweight="bold",
            color=INK, va="top")
    ax.text(0, cursor - 2.2,
            "c-p  = the component's whole mass per kWh, low–high across the sizes and seven chemistries.\n"
            "e-c  = the elements the component resolves into.  m-c = material level, where no element split exists.\n"
            "blue = a sodium cell built from literature: drawn in 05_composition, not read from the workbook, and not in the range above.",
            fontsize=8, color=MUTED, va="top", family="DejaVu Sans Mono")
    ax.text(0, cursor - 8.9,
            "Note: batteryPackCellTerminals is named for the pack but sits under the cell chemistry "
            "in the workbook, so it is drawn on the cell side.\n"
            "batteryCellCasing and batteryCellSeparator carry no element breakdown at all, and "
            "batteryCellElectrolyte itemises only its lithium — 99% of it. About 13% of cell mass "
            "has no element rows, the electrolyte being the largest part of that.\n"
            "The sodium cells built from literature itemise the salt's Na, P and F in the electrolyte; "
            "its solvent, and batteryCellUnitemised, have no element rows either.",
            fontsize=8, color="#8a3b3b", va="top")

    # The figure is as tall as what is drawn in it. The limits used to be fixed at
    # -26..100 for exactly the old layout, which cut off anything below.
    y_low = cursor - 17.0
    ax.set_ylim(y_low, 100)
    fig.set_size_inches(drawing.figure_width_in,
                        drawing.figure_height_in * 1.22 * (100 - y_low) / 126)
    fig.tight_layout()
    return fig


def main() -> int:
    try:
        params = current()
    except ParameterError as error:
        print(f"src/params_schema.py is NOT valid:\n  {error}", file=sys.stderr)
        return 1

    cell_side, pack_side = build_components(load_bev_rows(params), params)
    if params.export.literature_chemistry_template:
        cell_side.append({
            "name": REMAINDER, "gloss": "mass the electrochemistry does not explain",
            "low": float("nan"), "high": float("nan"), "elements": [],
            "material_level_only": False, "colour": UNITEMISED_COLOUR,
            "c_p_text": "c-p  not in the workbook; drawn per draw",
            "e_c_text": "no element split",
        })
    notes = variant_notes(params, [e["name"] for e in cell_side + pack_side])
    for entry in cell_side + pack_side:
        entry["variants"] = notes.get(entry["name"], [])
    print(f"cell-level components ({len(cell_side)}): {[c['name'] for c in cell_side]}")
    print(f"pack-level components ({len(pack_side)}): {[c['name'] for c in pack_side]}")

    figure = draw(cell_side, pack_side, params)
    path = params.output_path(PROJECT_ROOT, params.drawing.output_file_name)
    figure.savefig(path, dpi=params.drawing.output_dpi, bbox_inches="tight", facecolor="white")
    print(f"Saved {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
