"""
00_parameters.py
================

Regenerates `params.xlsx` from the values in `src/params_schema.py`.

    ./.venv/bin/python 00_parameters.py            # regenerate it
    ./.venv/bin/python 00_parameters.py --check    # validate, write nothing

**To change a parameter, edit `src/params_schema.py`**, then run this to
refresh the register. The spreadsheet is an output: editing it changes nothing,
because nothing reads it.

Run this first, before the other scripts -- it is what tells you a setting is
wrong in a second rather than halfway through a run.

This file is intentionally thin. Every parameter, its value and its
documentation live in `src/params_schema.py`; the writing lives in
`src/params_io.py`.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.params_io import PARAMS_FILE, save  # noqa: E402
from src.params_schema import ParameterError, current, flatten  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate params.xlsx from src/params_schema.py.")
    parser.add_argument("--check", action="store_true",
                        help="validate the values and print them, writing nothing")
    parser.add_argument("-p", "--path", default=PARAMS_FILE,
                        help=f"register to write (default: {PARAMS_FILE})")
    args = parser.parse_args(argv)

    try:
        params = current()
    except ParameterError as error:
        print(f"src/params_schema.py is NOT valid:\n  {error}", file=sys.stderr)
        return 1

    rows = flatten(params)

    if args.check:
        print("src/params_schema.py is valid. Values in force:")
        for _, _, key, value in rows:
            print(f"  {key:<34} {value}")
        print("\nSheets in scope:")
        for sheet_name in params.sheet_names():
            print(f"  {sheet_name}")
        return 0

    path = PROJECT_ROOT / args.path
    save(params, str(path))
    print(f"{path}: regenerated ({len(rows)} parameters)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
