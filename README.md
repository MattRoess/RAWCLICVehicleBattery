# RAWCLICVehicleBattery

What car batteries are made of: `BATT_consolidated_composition.xlsx`, consolidated
from the underlying sources, in kg of material per kWh of battery capacity.

It is the battery counterpart to `RAWCLICVehicleComposition` (whole car) and
`RAWCLICVehicleElectronics` (BEV electronics), and it feeds
`RAWCLICStockAndFlow/code/04_04_batteries.py`.

---

## Running it

```bash
./.venv/bin/python 00_parameters.py             # always first
./.venv/bin/python 99_check_environment.py      # smoke test
./.venv/bin/python 01_draw_battery_structure.py # the product-structure drawing
```

| script | what it does |
|---|---|
| `00_parameters.py` | Turns `src/params_schema.py` into `params.xlsx`, **and validates it**. `--check` validates and prints without writing. |
| `99_check_environment.py` | Checks the interpreter, the pinned packages and the workbook, and prints the workbook's real structure. Writes nothing. |
| `01_draw_battery_structure.py` | Draws every component of the BEV battery, labelled with the workbook's own `Layer 2` codes. Writes `battery_product_structure.png`. |

## Changing what it does

Every value lives in `src/params_schema.py` -- which sizes are in scope, which
`parameterCode` means what, the drawing geometry, the component glosses and
colours. Nothing is hardcoded in the scripts.

1. Edit only what is to the **right** of the `=`. Renaming a parameter breaks the code.
2. Keep the **type** -- a number stays a number, text stays quoted.
3. Keep the punctuation inside `{ }` and `( )`. A missing comma is the commonest breakage.

Then always:

```bash
./.venv/bin/python 00_parameters.py
```

That regenerates the register *and* validates the edit, so a mistake surfaces in
a second rather than as a wrong drawing. `params.xlsx` is an output: editing it
changes nothing, because nothing reads it. It is untracked, like every other
`.xlsx` here -- regenerate it rather than looking for it in a fresh clone.

The drawing writes **PNG only**.

### In Positron

Open this folder as the workspace. `.vscode/settings.json` already points the
interpreter at `.venv`, activates it in every terminal, and runs scripts from the
project root, so relative paths to the workbook resolve the same way whether the
code runs from the console, a script or a notebook cell.

### Rebuilding the environment from scratch

```bash
~/.pyenv/versions/3.14.4/bin/python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

Python 3.14.4, matching `RAWCLICStockAndFlow`. Versions are pinned in
`requirements.txt`; `ipykernel` is there because Positron needs it to start a
Python console.

---

## What is in the workbook

Seven sheets, one per battery type and size --
`BATTinELV_BEV_{25,45,60,80,100}kWh`, `BATTinELV_HEV_1kWh`,
`BATTinELV_PHEV_20kWh` -- 1,395 rows in total. Every value is in **kg/kWh**, and
every row carries `min_value` / `max_value`, a `DQS` data-quality score and
`count_value`, the number of sources it was consolidated from.

The columns that carry the structure:

| column | meaning |
|---|---|
| `additionalSpecification` | battery type and size; repeats the sheet name |
| `Layer 1` | cell chemistry (`battLiNMC_midNi`, `battLiFP_subsub`, ...) or `battPackXEV` for the pack-level parts shared by all chemistries |
| `Layer 2` | component (`cathodeActiveMaterial`, `batteryCellCasing`, `batteryPackSupportFrame`, ...) |
| `Layer 4` | chemical element -- filled **only** on `e-c` rows, literal `n/a` elsewhere |
| `parameterCode` | which level of detail the row is at |

`parameterCode` is the one to get right:

- **`c-p`** -- component per product: one row per component, its whole mass.
- **`m-c`** -- material per component.
- **`e-c`** -- element per component: the `Layer 4` breakdown (Li, Ni, Co, Cu, Al, ...).

Two things to know before using `m-c`. It covers only 21 rows per sheet, against
118 for `e-c` -- the cell casing, electrolyte and separator, and nothing at all
for `battPackXEV`. And with no `Layer 3` column in this workbook, an `m-c` row
does not name its material; it is identified by its component alone.

Reading note, and the reason `00_check_environment.py` passes
`keep_default_na=False`: the workbook writes a literal `n/a` in `Layer 4`. Under
pandas' defaults that becomes `NaN`, and the three levels of detail stop being
distinguishable from each other.
