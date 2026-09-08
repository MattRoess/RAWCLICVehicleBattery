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

INK = "#1c1c1c"
MUTED = "#5c5c5c"
EDGE = "#8a8a8a"


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


def draw_box(ax, x, y, width, height, entry: dict) -> None:
    ax.add_patch(FancyBboxPatch(
        (x, y), width, height, boxstyle="round,pad=0,rounding_size=0.6",
        facecolor=entry["colour"], edgecolor=EDGE, linewidth=0.8,
    ))
    ax.text(x + 0.7, y + height - 1.15, entry["name"], fontsize=8.2, fontweight="bold",
            family="DejaVu Sans Mono", color=INK, va="top")
    if entry["gloss"]:
        ax.text(x + 0.7, y + height - 2.55, entry["gloss"], fontsize=7.2,
                style="italic", color=MUTED, va="top")
    ax.text(x + 0.7, y + 2.5, f"c-p  {entry['low']:.2f}–{entry['high']:.2f} kg/kWh",
            fontsize=7.0, color=INK, va="bottom", family="DejaVu Sans Mono")
    detail = (f"e-c  {', '.join(entry['elements'])}" if entry["elements"]
              else "m-c only — no element split")
    ax.text(x + 0.7, y + 0.9, detail, fontsize=7.0,
            color=INK if entry["elements"] else MUTED,
            va="bottom", family="DejaVu Sans Mono")


def draw(cell_side: list[dict], pack_side: list[dict], params: Params) -> plt.Figure:
    drawing = params.drawing
    sizes = ", ".join(str(kwh) for kwh in params.scope.bev_capacities_kwh)

    fig, ax = plt.subplots(figsize=(drawing.figure_width_in, drawing.figure_height_in))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
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
    ax.text(0, 73.2,
            "Layer 1 = 7 chemistries: battLiFP · battLiMFP · battLiMO · battLiNCA · "
            "battLiNMC_lowNi · battLiNMC_midNi · battLiNMC_highNi",
            fontsize=8, color=MUTED, va="top", family="DejaVu Sans Mono")
    ax.text(0, 70.8, f"Each of these {len(cell_side)} components exists once per "
                     "chemistry; the chemistry mix decides how much of each is in the fleet.",
            fontsize=8, color=MUTED, va="top")

    for index, entry in enumerate(cell_side):
        column, row = index % 2, index // 2
        draw_box(ax,
                 column * (drawing.box_width + drawing.box_gap_x),
                 57 - row * (drawing.box_height + drawing.box_gap_y),
                 drawing.box_width, drawing.box_height, entry)

    # ---- right branch: the pack, shared by every chemistry ---------------
    ax.text(56, 76, "PACK — shared by every chemistry", fontsize=11,
            fontweight="bold", color=INK, va="top")
    ax.text(56, 73.2, f"Layer 1 = {params.scope.pack_level_key}", fontsize=8,
            color=MUTED, va="top", family="DejaVu Sans Mono")
    ax.text(56, 70.8, "One set per pack, independent of the cell chemistry inside it.",
            fontsize=8, color=MUTED, va="top")

    for index, entry in enumerate(pack_side):
        draw_box(ax, 56, 57 - index * (drawing.box_height + drawing.box_gap_y),
                 drawing.box_width + 12, drawing.box_height, entry)

    # ---- reading the box -------------------------------------------------
    ax.text(0, 17.5, "Reading a box", fontsize=9.5, fontweight="bold", color=INK, va="top")
    ax.text(0, 15.3,
            "c-p  = the component's whole mass per kWh, low–high across the sizes and seven chemistries.\n"
            "e-c  = the elements the component resolves into.  m-c = material level, where no element split exists.",
            fontsize=8, color=MUTED, va="top", family="DejaVu Sans Mono")
    ax.text(0, 10.0,
            "Note: batteryPackCellTerminals is named for the pack but sits under the cell chemistry "
            "in the workbook, so it is drawn on the cell side.\n"
            "batteryCellCasing and batteryCellSeparator carry no element breakdown at all, and "
            "batteryCellElectrolyte itemises only its lithium — 99% of it. About 13% of cell mass "
            "has no element rows, the electrolyte being the largest part of that.",
            fontsize=8, color="#8a3b3b", va="top")

    fig.tight_layout()
    return fig


def main() -> int:
    try:
        params = current()
    except ParameterError as error:
        print(f"src/params_schema.py is NOT valid:\n  {error}", file=sys.stderr)
        return 1

    cell_side, pack_side = build_components(load_bev_rows(params), params)
    print(f"cell-level components ({len(cell_side)}): {[c['name'] for c in cell_side]}")
    print(f"pack-level components ({len(pack_side)}): {[c['name'] for c in pack_side]}")

    figure = draw(cell_side, pack_side, params)
    path = params.output_path(PROJECT_ROOT, params.drawing.output_file_name)
    figure.savefig(path, dpi=params.drawing.output_dpi, bbox_inches="tight", facecolor="white")
    print(f"Saved {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
