"""
The structure figure: every chemistry that has a composition, side by side, with the
parts of its battery and the chemical elements each part is made of.

NAMES ONLY. There is no weight, no range and no Monte Carlo in it, so
01_draw_battery_structure.py needs nothing from the later steps. The parts and
elements come from `CompositionWithCells.structure`, which reads them off the
composition data -- and, for the two sodium cells, off their settings.

The figure's wording, order and size are all settings (`drawing.*`). Nothing about
the chemistries or the parts is written in this file.
"""

from __future__ import annotations

from dataclasses import dataclass

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.colors import to_rgb
from matplotlib.figure import Figure
from matplotlib.patches import FancyBboxPatch, Rectangle

from src.unknown_chemistries import CompositionWithCells

INK = "#1c1c1c"
MUTED = "#5c5c5c"
RULE = "#d4d4d4"

# Geometry, in inches. The figure is drawn on a canvas where one unit is one inch,
# so these are real sizes, and the height is whatever the rows add up to.
MARGIN = 0.45
LABEL_WIDTH = 3.35        # the column of row names
GROUP_GAP = 0.30          # between the lithium and the sodium columns
COLUMN_GAP = 0.07
CELL_PAD = 0.10
CHIP_HEIGHT = 0.86        # the coloured box with a chemistry's name
ROW_TOP = 0.10
ROW_BOTTOM = 0.12
LINE_MAIN = 0.16          # down to the first baseline of a row
LINE_ELEMENT = 0.17
LINE_GLOSS = 0.13

# Type sizes, in points.
SIZE_TITLE, SIZE_LEGEND = 20, 10.5
SIZE_CHIP, SIZE_CHIP_VARIANT, SIZE_CHIP_MATERIAL = 13, 10, 7.5
SIZE_ELEMENT, SIZE_NO_SPLIT = 10.5, 8.5
SIZE_LABEL, SIZE_GLOSS, SIZE_BAND = 10.5, 8, 9.5


class OverviewError(Exception):
    """The figure cannot be drawn."""


@dataclass(frozen=True)
class Column:
    chemistry: str
    short: str
    material: str
    colour: str
    group: int
    parts: dict             # part -> the elements it is made of
    x: float = 0.0


class _Ruler:
    """Measures text in inches, so a line is broken to fit the box it sits in."""

    def __init__(self, figure: Figure) -> None:
        self.figure = figure
        self.renderer = figure.canvas.get_renderer()

    def width(self, text: str, size: float, weight: str = "normal") -> float:
        probe = self.figure.text(0, 0, text, fontsize=size, fontweight=weight)
        inches = probe.get_window_extent(self.renderer).width / self.figure.dpi
        probe.remove()
        return inches

    def wrap(self, items: list[str], size: float, limit: float, sep: str) -> list[str]:
        """Pack items into lines no wider than `limit`, never splitting an item."""
        lines, current = [], ""
        for item in items:
            trial = item if not current else current + sep + item
            if current and self.width(trial, size) > limit:
                lines.append(current)
                current = item
            else:
                current = trial
        if current:
            lines.append(current)
        return lines


def _text_colour(background: str) -> str:
    red, green, blue = to_rgb(background)
    return INK if 0.2126 * red + 0.7152 * green + 0.0722 * blue > 0.55 else "white"


def draw(params, columns: list[Column], missing: list[str]) -> Figure:
    drawing = params.drawing
    width = drawing.figure_width_in
    figure = Figure(figsize=(width, 12.0), dpi=100)
    FigureCanvasAgg(figure)
    ruler = _Ruler(figure)
    axes = figure.add_axes([0, 0, 1, 1])
    axes.set_xlim(0, width)
    axes.axis("off")

    # ---- the columns
    groups = len(drawing.overview_groups)
    left, right = MARGIN + LABEL_WIDTH, width - MARGIN
    column_width = (right - left - GROUP_GAP * (groups - 1)) / len(columns)
    box = column_width - COLUMN_GAP
    inner = box - 2 * CELL_PAD
    placed, x, previous = [], left, 0
    for column in columns:
        if column.group != previous:
            x += GROUP_GAP
            previous = column.group
        placed.append(Column(column.chemistry, column.short, column.material, column.colour,
                             column.group, column.parts, x))
        x += column_width
    columns = placed

    # ---- what every row needs, worked out before anything is drawn
    rows = list(drawing.cell_component_order) + list(drawing.pack_component_order)
    unplaced = sorted({part for column in columns for part in column.parts} - set(rows))
    if unplaced:
        raise OverviewError(
            f"the composition has parts the figure has no row for: {unplaced}. Add them to "
            "drawing.cell_component_order or drawing.pack_component_order, with a label "
            "and a gloss -- otherwise the figure silently leaves them out.")
    gloss_lines = {code: ruler.wrap(drawing.component_gloss[code].split(), SIZE_GLOSS,
                                    LABEL_WIDTH - 0.3, " ") for code in rows}
    box_lines = {}
    for index, column in enumerate(columns):
        for code in rows:
            elements = column.parts.get(code)
            box_lines[(index, code)] = (
                ruler.wrap(list(elements), SIZE_ELEMENT, inner, " · ") if elements else [])
    height = {}
    for code in rows:
        label = ROW_TOP + LINE_MAIN + len(gloss_lines[code]) * LINE_GLOSS + 0.10
        content = max(ROW_TOP + LINE_MAIN + max(len(lines) - 1, 0) * LINE_ELEMENT + ROW_BOTTOM
                      for (index, owner), lines in box_lines.items() if owner == code)
        height[code] = max(label, content)

    # ---- the title and what it means
    y = MARGIN + 0.36
    axes.text(MARGIN, y, drawing.overview_title, fontsize=SIZE_TITLE, fontweight="bold",
              color=INK, va="baseline")
    y += 0.12
    for line in drawing.overview_legend:
        y += 0.235
        axes.text(MARGIN, y, line, fontsize=SIZE_LEGEND, color=INK, va="baseline")
    y += 0.33

    # ---- the groups, then each chemistry's coloured box
    how_lines = []
    for number, (_title, how, _members) in enumerate(drawing.overview_groups):
        mine = [column for column in columns if column.group == number]
        how_lines.append(ruler.wrap(how.split(), SIZE_LEGEND, mine[-1].x + box - mine[0].x, " "))
    rule = y + 0.17 + max(len(lines) for lines in how_lines) * 0.19 + 0.11
    for number, (title, _how, _members) in enumerate(drawing.overview_groups):
        mine = [column for column in columns if column.group == number]
        x0, x1 = mine[0].x, mine[-1].x + box
        axes.text(x0, y + 0.17, title, fontsize=11.5, fontweight="bold", color=INK, va="baseline")
        for k, line in enumerate(how_lines[number]):
            axes.text(x0, y + 0.17 + (k + 1) * 0.19, line, fontsize=SIZE_LEGEND, color=MUTED,
                      va="baseline")
        axes.plot([x0, x1], [rule, rule], color=INK, linewidth=1.5, solid_capstyle="butt")
    y = rule + 0.10
    chip_top = y
    for column in columns:
        axes.add_patch(FancyBboxPatch(
            (column.x, chip_top), box, CHIP_HEIGHT,
            boxstyle="round,pad=0,rounding_size=0.06", facecolor=column.colour,
            edgecolor="none", zorder=1))
        ink = _text_colour(column.colour)
        name, _, variant = column.short.partition(", ")
        centre, cursor = column.x + box / 2, chip_top + 0.29
        axes.text(centre, cursor, name, fontsize=SIZE_CHIP, fontweight="bold", color=ink,
                  ha="center", va="baseline", zorder=3)
        if variant:
            cursor += 0.2
            axes.text(centre, cursor, variant, fontsize=SIZE_CHIP_VARIANT, color=ink,
                      ha="center", va="baseline", zorder=3)
        cursor += 0.07
        for line in ruler.wrap(column.material.split(), SIZE_CHIP_MATERIAL, inner, " "):
            cursor += 0.12
            axes.text(centre, cursor, line, fontsize=SIZE_CHIP_MATERIAL, color=ink, alpha=0.9,
                      ha="center", va="baseline", zorder=3)
    y += CHIP_HEIGHT + 0.10
    body_top = y

    # ---- the rows
    def band(title: str) -> None:
        nonlocal y
        y += 0.14
        axes.text(MARGIN, y + 0.16, title, fontsize=SIZE_BAND, fontweight="bold", color=MUTED,
                  va="baseline")
        y += 0.24
        axes.plot([MARGIN, right], [y, y], color=INK, linewidth=0.8, solid_capstyle="butt")

    def part_row(code: str) -> None:
        nonlocal y
        top = y
        baseline = top + ROW_TOP + LINE_MAIN
        axes.text(MARGIN + 0.02, baseline, drawing.component_labels[code], fontsize=SIZE_LABEL,
                  fontweight="bold", color=INK, va="baseline")
        for k, line in enumerate(gloss_lines[code]):
            axes.text(MARGIN + 0.02, baseline + 0.015 + (k + 1) * LINE_GLOSS, line,
                      fontsize=SIZE_GLOSS, color=MUTED, va="baseline")
        for index, column in enumerate(columns):
            elements = column.parts.get(code)
            x0 = column.x + CELL_PAD
            if elements is None:
                axes.text(x0, baseline, "–", fontsize=SIZE_ELEMENT, color=MUTED, va="baseline")
            elif not elements:
                axes.text(x0, baseline, drawing.overview_no_split, fontsize=SIZE_NO_SPLIT,
                          color=MUTED, style="italic", va="baseline")
            else:
                for k, line in enumerate(box_lines[(index, code)]):
                    axes.text(x0, baseline + k * LINE_ELEMENT, line, fontsize=SIZE_ELEMENT,
                              color=INK, va="baseline")
        y += height[code]
        axes.plot([MARGIN, right], [y, y], color=RULE, linewidth=0.6, solid_capstyle="butt")

    headings = drawing.overview_headings
    band(headings["cells_band"])
    for code in drawing.cell_component_order:
        part_row(code)
    band(headings["pack_band"])
    for code in drawing.pack_component_order:
        part_row(code)
    body_bottom = y

    for column in columns:
        axes.add_patch(Rectangle((column.x, body_top), box, body_bottom - body_top,
                                 facecolor=column.colour, edgecolor="none", alpha=0.07, zorder=0))

    if missing:
        y += 0.30
        axes.text(MARGIN, y, drawing.overview_footnote.format(
            missing=", ".join(name.replace("_", "-") for name in missing)),
            fontsize=SIZE_LEGEND - 1, color=MUTED, va="baseline")
    total_height = y + MARGIN
    figure.set_size_inches(width, total_height)
    axes.set_ylim(total_height, 0)
    return figure


def draw_overview(params, project_root, model) -> str:
    """Draw the figure from the composition `model` and return the name of the file written."""
    drawing = params.drawing
    colours = params.scenarios.workbook_chemistry_colours
    cells = CompositionWithCells(model)
    columns = []
    for number, (_title, _how, members) in enumerate(drawing.overview_groups):
        for key, short, material in members:
            columns.append(Column(key, short, material, colours[key], number,
                                  cells.structure(key)))
    figure = draw(params, columns, list(params.scenarios.chemistries_without_composition))
    path = params.output_path(project_root, drawing.output_file_name)
    figure.savefig(path, dpi=drawing.output_dpi, facecolor="white")
    return path.name
