# RAWCLICVehicleBattery

What car batteries are made of: `BATT_consolidated_composition.xlsx`, consolidated
from the underlying sources, in kg of material per kWh of battery capacity.

It is the battery counterpart to `RAWCLICVehicleComposition` (whole car) and
`RAWCLICVehicleElectronics` (BEV electronics), and it feeds
`RAWCLICStockAndFlow/code/04_04_batteries.py`.

---

## Running it

```bash
./.venv/bin/python 00_parameters.py                # always first
./.venv/bin/python 99_check_environment.py         # smoke test
./.venv/bin/python 01_draw_battery_structure.py    # what a battery is made of
./.venv/bin/python 02_composition_by_capacity.py   # how much, at any capacity
```

| script | what it does |
|---|---|
| `00_parameters.py` | Turns `src/params_schema.py` into `params.xlsx`, **and validates it**. `--check` validates and prints without writing. |
| `99_check_environment.py` | Checks the interpreter, the pinned packages and the workbook, and prints the workbook's real structure. Writes nothing. |
| `01_draw_battery_structure.py` | Draws every component of the BEV battery, labelled with the workbook's own `Layer 2` codes. |
| `02_composition_by_capacity.py` | The composition at **any** capacity, with a Monte Carlo band. Prints a table and writes two figures. |
| `03_capacity_by_segment_over_time.py` | Battery capacity by segment and year from `EV_details.csv`, smoothed, with the market spread and a bootstrap band. One figure per capacity basis. |
| `04_capacity_by_chemistry.py` | The same, split by cathode chemistry — LFP, NCA, NMC_middle, NMC_high — where at least 5 distinct models carry it. Prints the table too. |
| `05_chemistry_scenarios.py` | Three chemistry scenarios to 2070, and the mix arriving for recycling once vehicle life and second life are applied. **Assumption, not data.** |
| `06_generate_composition_files.py` | Writes the composition files for the stock-and-flow model: one file per chemistry, one row per component/material/element, **for one car**. No chemistry mixing — the split happens downstream. |

`02` takes arguments:

```bash
./.venv/bin/python 02_composition_by_capacity.py --capacity 150 --level element --chemistry battLiNMC_highNi
```

`--level` is `component`, `material` or `element`; `--no-figures` prints the
table alone.

## Where the files are

| folder | holds |
|---|---|
| `data/raw/` | `BATT_consolidated_composition.xlsx` and `EV_details.csv` — the inputs, supplied separately |
| `figures/` | every figure, all regenerable — `paths.output_dir` |
| `src/` | `params_schema.py`, `params_io.py`, `composition.py` |

`data/` and `figures/` are both untracked. A fresh clone gets the code only and
needs `data/raw/` supplied from iCloud; the figures come back by re-running the
scripts.

## Composition at any capacity

`src/composition.py` turns the workbook's five BEV sizes into an answer for any
capacity — interpolated between 25 and 100 kWh, extrapolated beyond, at
component, material or element level, for any of the seven chemistries.

```python
from src.composition import CompositionModel
from src.params_schema import current

model = CompositionModel(current())
model.weights_at(150.0, chemistry="battLiNMC_midNi", level="component")
```

**⚠️ Feed it NOMINAL capacity.** The workbook's kg/kWh is per nominal kWh, not
useable. Useable runs about 5% lower, so a useable figure returns about 5% too
little of everything. `ev_details.capacity_basis` defaults to `nominal` for the
same reason.

Three more things are worth knowing before the numbers are used.

**It interpolates mass, not kg/kWh.** A part whose mass does not change with
capacity — `currentCollectorAnode` on high-Ni is 21.4 kg at 25 kWh and 21.8 kg at
100 kWh — has an intensity that falls 0.86 → 0.22 kg/kWh purely because the
denominator grew. Interpolating that hyperbola mixes fixed-mass parts up with
the ones that really do scale. In kilograms the curve means something, so the
intensity is multiplied up, interpolated, and divided back out.

**Everything past 100 kWh is a straight line, and says so.** Extrapolation is
linear whatever `interpolation_method` is set to — a cubic continued past its
last knot diverges, and at 150 kWh that is how a figure ends up with a negative
cathode. The `extrapolated` column marks those rows and the figures shade the
region. Read the right-hand panel of the totals figure as the sanity check: a
straight line in mass implies energy density keeps improving with size, which is
an assumption the workbook never made.

**The ±10% band is a convention, not a measurement.** Every non-zero row of the
workbook has `min_value = 0.9 × Value` and `max_value = 1.1 × Value` — all 805 of
them, whether the value was consolidated from 1 source or 21, with `DQS = 2`
throughout. The Monte Carlo propagates that faithfully, which means the band is
the convention carried through the arithmetic and **not** evidence about how
well any of these numbers is known. A narrow band here means the rule was
narrow.

One consequence worth stating separately: at element level the components do not
add up. An element-level reading of a 150 kWh NMC battery accounts for 626 kg of
the 684 kg the components come to — 8% missing, silently, unless you look. And
it is **not only** the components with no element rows: `batteryCellElectrolyte`
itemises only its lithium, losing 99% of its own mass, which is the largest
single term. `batteryCellCasing` and `batteryCellSeparator` lose all of theirs.
`02_composition_by_capacity.py --level element` prints the attribution per run.

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
