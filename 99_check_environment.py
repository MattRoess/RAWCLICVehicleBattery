"""
00_check_environment.py
=======================

Smoke test for a fresh checkout: proves the interpreter, the packages and the
input workbook are all where the rest of this project will expect them.

Run it after `00_parameters.py`, which is what validates the settings:

    ./.venv/bin/python 99_check_environment.py

It reads `BATT_consolidated_composition.xlsx` and prints what is actually in it
-- sheets, row counts, and the distinct values of every key column -- so the
structure comes from the file rather than from memory. It writes nothing.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.params_schema import current  # noqa: E402

PARAMS = current()
COMPOSITION_FILE = PROJECT_ROOT / PARAMS.scope.composition_file_name

# The columns the workbook is expected to have. Checked, not assumed: a renamed
# or dropped column should fail here, loudly, and not halfway through a model run.
EXPECTED_COLUMNS = [
    "additionalSpecification",  # battery type + size, matches the sheet name
    "Layer 1",                  # cell chemistry (battLiNMC_midNi, ...) or battPackXEV
    "Layer 2",                  # component (cathodeActiveMaterial, batteryCellCasing, ...)
    "Layer 4",                  # chemical element -- only filled on 'e-c' rows
    "parameterCode",            # c-p / m-c / e-c: which level of detail the row is at
    "UoM",                      # kg/kWh throughout
    "DQS",                      # data quality score
    "Value", "min_value", "max_value",  # the value and its range
    "count_value",              # how many sources the value is consolidated from
]


def check_packages() -> None:
    print(f"Interpreter : {sys.executable}")
    print(f"Python      : {sys.version.split()[0]}")
    for name in ("pandas", "numpy", "scipy", "openpyxl", "matplotlib", "ipykernel"):
        try:
            module = __import__(name)
        except ImportError as exc:  # noqa: PERF203 -- one message per package is the point
            raise SystemExit(
                f"MISSING PACKAGE: {name} ({exc}). Install the pinned set with:\n"
                f"    ./.venv/bin/pip install -r requirements.txt"
            ) from exc
        print(f"  {name:<11} {getattr(module, '__version__', 'unknown')}")


def load_composition() -> "pandas.DataFrame":  # noqa: F821 -- imported inside, after the check
    import pandas as pd

    if not COMPOSITION_FILE.exists():
        raise SystemExit(
            f"Input workbook not found: {COMPOSITION_FILE}\n"
            "It is not tracked in git (see .gitignore) -- copy it in from iCloud."
        )

    workbook = pd.ExcelFile(COMPOSITION_FILE)
    frames = []
    for sheet_name in workbook.sheet_names:
        # keep_default_na=False: the file writes a literal 'n/a' in 'Layer 4' on
        # every row that is NOT at element level. Left to pandas' defaults that
        # becomes NaN and the three levels of detail stop being distinguishable.
        frame = workbook.parse(sheet_name, keep_default_na=False, na_values=[""])
        missing = [c for c in EXPECTED_COLUMNS if c not in frame.columns]
        if missing:
            raise SystemExit(f"Sheet {sheet_name!r} is missing column(s): {missing}")
        frames.append(frame.assign(sheet=sheet_name))
    return pd.concat(frames, ignore_index=True)


def describe(composition: "pandas.DataFrame") -> None:  # noqa: F821
    print(f"\nWorkbook    : {COMPOSITION_FILE.name}")
    print(f"Rows        : {len(composition):,} across {composition['sheet'].nunique()} sheets")

    print("\nRows per sheet and level of detail (parameterCode):")
    print(composition.pivot_table(
        index="sheet", columns="parameterCode", values="Value",
        aggfunc="count", fill_value=0,
    ).to_string())

    for column in ("Layer 1", "Layer 2", "Layer 4", "parameterCode", "UoM"):
        values = sorted({str(v) for v in composition[column]})
        print(f"\n{column} ({len(values)} distinct): {values}")


def main() -> None:
    check_packages()
    print(f"\nParameters  : src/params_schema.py -- {len(PARAMS.sheet_names())} BEV "
          f"sheet(s) in scope: {', '.join(PARAMS.sheet_names())}")
    describe(load_composition())
    print("\nEnvironment OK.")


if __name__ == "__main__":
    main()
