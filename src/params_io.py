"""
src/params_io.py
================

Writes `params.xlsx` from the values in `src/params_schema.py`.

One direction only: code -> spreadsheet. The spreadsheet is a readable register
of what is set, never a source of values, so editing it changes nothing. Change
`src/params_schema.py` and run `00_parameters.py`.

Kept apart from `params_schema.py` so the schema stays free of I/O, and out of
`00_parameters.py`, whose leading digits make it unimportable.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from src.params_schema import Params, flatten

PARAMS_FILE = "params.xlsx"
SHEET = "parameters"


def save(params: Params, path: str = PARAMS_FILE) -> pd.DataFrame:
    """Write the register: one row per parameter, name/description/key/value."""
    frame = pd.DataFrame(flatten(params), columns=["name", "description", "key", "value"])
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name=SHEET, index=False)
        _widen(writer.sheets[SHEET], frame)
    return frame


def _widen(sheet: Any, frame: pd.DataFrame) -> None:
    """Column widths, so the file is readable the moment it is opened."""
    for index, width in enumerate((26, 96, 32, 46), start=1):
        sheet.column_dimensions[chr(64 + index)].width = width
    sheet.freeze_panes = "A2"
