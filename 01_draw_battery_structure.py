"""
01_draw_battery_structure.py
============================

Draws the product structure of a BEV traction battery: every component that
makes up the product, labelled with the component code the workbook uses.

    ./.venv/bin/python 01_draw_battery_structure.py

Writes `battery_product_structure.svg` and `.png` to the project root.

SCOPE: the five BEV sheets only -- BATTinELV_BEV_{25,45,60,80,100}kWh. The
HEV (1 kWh) and PHEV (20 kWh) sheets are deliberately excluded.

Everything except the plain-English glosses is READ FROM THE WORKBOOK, not
hardcoded: which components exist, which branch they sit on, their kg/kWh range
and which levels of detail resolve them. If the workbook changes, the drawing
changes with it. The glosses are the one thing that cannot be derived, so they
live in COMPONENT_GLOSS below and a component missing from it is reported rather
than silently drawn bare.

The structure is identical across all five BEV sizes -- verified, not assumed
(see `_check_structure_is_shared`). Only the values differ, which is why each
box carries a RANGE across the five sizes and seven chemistries rather than a
single number.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # never opens a window -- always writes to file
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent
COMPOSITION_FILE = PROJECT_ROOT / "BATT_consolidated_composition.xlsx"

BEV_CAPACITIES_KWH = [25, 45, 60, 80, 100]
BEV_SHEETS = [f"BATTinELV_BEV_{kwh}kWh" for kwh in BEV_CAPACITIES_KWH]

# The Layer 1 value that holds the parts shared by every chemistry. Everything
# else in Layer 1 is a cell chemistry.
PACK_LEVEL_KEY = "battPackXEV"

# Plain English for each component code. The only hardcoded content here: it
# cannot be derived from the file, and a bare code is not a label a reader can
# use. A component absent from this dict is drawn without a gloss and reported.
COMPONENT_GLOSS = {
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
}

# Colour by role, so the eye groups the twelve boxes without reading them all.
ROLE_COLOURS = {
    "electrode": "#dbe7f3",
    "collector": "#e3eddc",
    "cell_body": "#f6ecd9",
    "terminal": "#efe1ee",
    "pack": "#e6e4e0",
}
COMPONENT_ROLE = {
    "cathodeActiveMaterial": "electrode",
    "anodeActiveMaterial": "electrode",
    "currentCollectorCathode": "collector",
    "currentCollectorAnode": "collector",
    "batteryCellElectrolyte": "cell_body",
    "batteryCellSeparator": "cell_body",
    "batteryCellCasing": "cell_body",
    "batteryPackCellTerminals": "terminal",
}

INK = "#1c1c1c"
MUTED = "#5c5c5c"
EDGE = "#8a8a8a"


def load_bev_rows() -> pd.DataFrame:
    """The five BEV sheets, concatenated, with the sheet kept as a column."""
    if not COMPOSITION_FILE.exists():
        raise SystemExit(f"Input workbook not found: {COMPOSITION_FILE}")
    frames = []
    for sheet_name in BEV_SHEETS:
        # keep_default_na=False: 'Layer 4' holds a literal 'n/a' on every row
        # that is not at element level. Under pandas' defaults that becomes NaN
        # and the levels of detail stop being distinguishable.
        frame = pd.read_excel(
            COMPOSITION_FILE, sheet_name=sheet_name,
            keep_default_na=False, na_values=[""],
        )
        frames.append(frame.assign(sheet=sheet_name))
    return pd.concat(frames, ignore_index=True)


def _check_structure_is_shared(rows: pd.DataFrame) -> None:
    """The drawing shows ONE structure for all five sizes. Prove that is true."""
    per_sheet = {
        sheet: set(map(tuple, group[["Layer 1", "Layer 2"]].drop_duplicates().values))
        for sheet, group in rows[rows.parameterCode == "c-p"].groupby("sheet")
    }
    first, *rest = per_sheet.values()
    if any(other != first for other in rest):
        raise SystemExit(
            "The five BEV sheets do NOT share one component structure any more. "
            "One drawing can no longer stand for all of them -- rework this script "
            "rather than drawing a structure that is true of only some sizes."
        )


def build_components(rows: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    """Everything each box needs, derived from the workbook."""
    _check_structure_is_shared(rows)

    component_rows = rows[rows.parameterCode == "c-p"]
    element_rows = rows[rows.parameterCode == "e-c"]
    material_rows = rows[rows.parameterCode == "m-c"]

    cell_side: list[dict] = []
    pack_side: list[dict] = []
    for (layer1_is_pack, name), group in component_rows.groupby(
        [component_rows["Layer 1"].eq(PACK_LEVEL_KEY), "Layer 2"]
    ):
        elements = sorted(set(element_rows.loc[element_rows["Layer 2"] == name, "Layer 4"]))
        has_material_level = bool((material_rows["Layer 2"] == name).any())
        entry = {
            "name": name,
            "gloss": COMPONENT_GLOSS.get(name, ""),
            "low": group["Value"].min(),
            "high": group["Value"].max(),
            "elements": elements,
            "material_level_only": not elements and has_material_level,
            "colour": ROLE_COLOURS["pack" if layer1_is_pack else COMPONENT_ROLE.get(name, "cell_body")],
        }
        (pack_side if layer1_is_pack else cell_side).append(entry)

    missing_gloss = [c["name"] for c in cell_side + pack_side if not c["gloss"]]
    if missing_gloss:
        print(f"NOTE: no gloss for {missing_gloss} -- drawn as bare codes. Add them "
              f"to COMPONENT_GLOSS in {Path(__file__).name}.")

    # Draw in assembly order, not alphabetical: the parts that store the charge
    # first, then what carries it out, then what contains it.
    cell_order = [
        "cathodeActiveMaterial", "anodeActiveMaterial",
        "currentCollectorCathode", "currentCollectorAnode",
        "batteryCellElectrolyte", "batteryCellSeparator",
        "batteryCellCasing", "batteryPackCellTerminals",
    ]
    pack_order = [
        "batteryPackSupportFrame", "batteryPackThermalConductor",
        "batteryPackModuleEnclosuresAndCoolantManifolds", "batteryPackCables",
    ]

    def in_order(entries: list[dict], order: list[str]) -> list[dict]:
        ranked = {name: i for i, name in enumerate(order)}
        # An unranked component sorts to the end rather than disappearing: a new
        # component in the workbook must show up in the drawing, not vanish from it.
        return sorted(entries, key=lambda e: (ranked.get(e["name"], len(order)), e["name"]))

    return in_order(cell_side, cell_order), in_order(pack_side, pack_order)


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
            color=MUTED if not entry["elements"] else INK,
            va="bottom", family="DejaVu Sans Mono")


def draw(cell_side: list[dict], pack_side: list[dict]) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(15.5, 10.5))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    ax.text(0, 98.2, "BEV traction battery — product structure",
            fontsize=17, fontweight="bold", color=INK, va="top")
    ax.text(0, 94.6,
            "Every component making up the product, labelled with the workbook's own "
            "Layer 2 code. Source: BATT_consolidated_composition.xlsx",
            fontsize=9.5, color=MUTED, va="top")
    ax.text(0, 91.8,
            "Scope: the five BEV sizes — BATTinELV_BEV_{25, 45, 60, 80, 100}kWh. "
            "All five share one structure; only the values differ, so each box shows a range.",
            fontsize=9.5, color=MUTED, va="top")

    # The product node.
    ax.add_patch(FancyBboxPatch((28, 82), 44, 6, boxstyle="round,pad=0,rounding_size=0.6",
                                facecolor="#2f3b46", edgecolor="none"))
    ax.text(50, 85.9, "BEV traction battery pack", fontsize=12, fontweight="bold",
            color="white", ha="center", va="center")
    ax.text(50, 83.4, "additionalSpecification = BATTinELV_BEV_<size>kWh",
            fontsize=8, color="#c9d3dc", ha="center", va="center",
            family="DejaVu Sans Mono")

    # Branch lines from the product node down to the two group headers, dropped
    # on each group's centre.
    ax.plot([50, 50], [82, 79], color=EDGE, linewidth=1.0)
    ax.plot([24.4, 73.7], [79, 79], color=EDGE, linewidth=1.0)
    for branch_x in (24.4, 73.7):
        ax.plot([branch_x, branch_x], [79, 77], color=EDGE, linewidth=1.0)

    # ---- left branch: the cell, one set per chemistry -------------------
    ax.text(0, 76, "CELLS — one set per chemistry", fontsize=11,
            fontweight="bold", color=INK, va="top")
    ax.text(0, 73.2,
            "Layer 1 = 7 chemistries: battLiFP · battLiMFP · battLiMO · battLiNCA · "
            "battLiNMC_lowNi · battLiNMC_midNi · battLiNMC_highNi",
            fontsize=8, color=MUTED, va="top", family="DejaVu Sans Mono")
    ax.text(0, 70.8, "Each of these eight components exists once per chemistry; "
                     "the chemistry mix decides how much of each is in the fleet.",
            fontsize=8, color=MUTED, va="top")

    box_w, box_h, gap_x, gap_y = 23.5, 9.6, 1.8, 2.4
    for index, entry in enumerate(cell_side):
        column, row = index % 2, index // 2
        draw_box(ax, column * (box_w + gap_x), 57 - row * (box_h + gap_y), box_w, box_h, entry)

    # ---- right branch: the pack, shared by every chemistry ---------------
    ax.text(56, 76, "PACK — shared by every chemistry", fontsize=11,
            fontweight="bold", color=INK, va="top")
    ax.text(56, 73.2, "Layer 1 = battPackXEV", fontsize=8, color=MUTED,
            va="top", family="DejaVu Sans Mono")
    ax.text(56, 70.8, "One set per pack, independent of the cell chemistry inside it.",
            fontsize=8, color=MUTED, va="top")

    for index, entry in enumerate(pack_side):
        draw_box(ax, 56, 57 - index * (box_h + gap_y), box_w + 12, box_h, entry)

    # ---- reading the box ------------------------------------------------
    ax.text(0, 17.5, "Reading a box", fontsize=9.5, fontweight="bold", color=INK, va="top")
    ax.text(0, 15.3,
            "c-p  = the component's whole mass per kWh, low–high across the five sizes and seven chemistries.\n"
            "e-c  = the elements the component resolves into.  m-c = material level, where no element split exists.",
            fontsize=8, color=MUTED, va="top", family="DejaVu Sans Mono")
    ax.text(0, 10.0,
            "Note: batteryPackCellTerminals is named for the pack but sits under the cell chemistry "
            "in the workbook, so it is drawn on the cell side.\n"
            "batteryCellCasing and batteryCellSeparator carry no element breakdown at all — "
            "reading this product at element level silently drops them.",
            fontsize=8, color="#8a3b3b", va="top")

    fig.tight_layout()
    return fig


def main() -> None:
    cell_side, pack_side = build_components(load_bev_rows())
    print(f"cell-level components ({len(cell_side)}): {[c['name'] for c in cell_side]}")
    print(f"pack-level components ({len(pack_side)}): {[c['name'] for c in pack_side]}")

    figure = draw(cell_side, pack_side)
    for suffix in ("svg", "png"):
        path = PROJECT_ROOT / f"battery_product_structure.{suffix}"
        figure.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
        print(f"Saved {path}")


if __name__ == "__main__":
    main()
