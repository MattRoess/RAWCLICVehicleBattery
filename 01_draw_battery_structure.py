"""
01_draw_battery_structure.py
============================

Draws what is inside a battery pack, for every chemistry that has a composition:
its parts, and the chemical elements each part is made of.

    ./.venv/bin/python 00_parameters.py            # first, always
    ./.venv/bin/python 01_draw_battery_structure.py

Writes the PNG named by `drawing.output_file_name` to `paths.output_dir`.

STRUCTURE ONLY: names, with no weights, no ranges and no Monte Carlo, and nothing
from the later steps. The lithium chemistries' parts and elements are read from the
composition data in `data/raw`; the two sodium cells' from their settings.

EVERY SETTING LIVES IN `src/params_schema.py`. The drawing itself is
`src/overview_figure.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.composition import CompositionError, CompositionModel  # noqa: E402
from src.overview_figure import OverviewError, draw_overview  # noqa: E402
from src.params_schema import ParameterError, current  # noqa: E402


def main() -> int:
    try:
        params = current()
    except ParameterError as error:
        print(f"src/params_schema.py is NOT valid:\n  {error}", file=sys.stderr)
        return 1
    try:
        model = CompositionModel(params, project_root=PROJECT_ROOT)
        name = draw_overview(params, PROJECT_ROOT, model)
    except (CompositionError, OverviewError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"Saved {params.output_path(PROJECT_ROOT, name)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
