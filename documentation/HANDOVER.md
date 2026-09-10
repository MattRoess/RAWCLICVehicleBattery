# Handover — RAWCLICVehicleBattery

Written 2026-09-10, superseding the 09-09 version. State verified against the repository and against runs made
today, not remembered.

For the methods and the reasoning, read [`METHODOLOGY.md`](METHODOLOGY.md). This
file is only what you need to carry on.

**Read §1 before trusting the previous handover.** Several of its claims were
wrong, and that is the most useful thing this document has to say.

---

## 1. The previous handover was wrong about the blocker

It said `RAWCLICStockAndFlow/code/04_04_batteries.py` was blocked for three
reasons. All three were checked against the actual files on 2026-09-09 and none
of them held:

| its claim | what is actually true |
|---|---|
| `parameterCode = "e-m"` does not exist in the workbook | it exists — **3,289 rows**, the largest of the three codes |
| no sheet `BATT_EV_consolidated_inputForRM`, no `Layer 3` column | both exist, in sheet 1 of 4 |
| `BATTKey_xEV_shares_final.xlsx` is not on disk | it is, in `Empa/RAWCLIC/_vehicles/dataStockFlow/` |

The mistake was comparing that script against **this** project's
`BATT_consolidated_composition.xlsx`. It does not read that file. It reads
`250318_WP3_MS23_consolidatedComposition_BATT_EV_v7_editable.xlsx`, an older WP3
workbook with a different shape. Both inputs have since been copied into
`RAWCLICStockAndFlow/data/raw/` and the loader runs.

The lesson generalises: **verify a handover's claims before repeating them**,
including this one's.

Two things settled while looking, worth keeping:

- The undocumented `÷1000` in `04_04` is a **kg→tonne** conversion, not the
  g→kg its comment guesses. Every workbook row is `kg/kWh` and `amount` is in
  millions of vehicles, so the output is tonnes and that file's `"Mass [kg]"`
  axis label is wrong by 1000×.
- `04_03` and `04_04` hardcode their scenario lists while `04_01` uses
  `active_scenario_names()`. Since `scenarios_to_run = ("BAU",)`, both demand
  trackers that were deliberately never generated. **That work is Matthias's own
  — do not take it up unless he asks.**

---

## 2. Picking up on another Mac

The project lives in iCloud Drive, so the whole folder syncs, `data/` and
`figures/` included. Neither is in git.

```bash
cd "/Users/rm/Documents/GitHub/RAWCLICVehicleBattery"   # == the iCloud path
git pull
ls data/raw/                                            # the .xlsx and the .csv
./.venv/bin/python 00_parameters.py
```

1. **iCloud may not have downloaded the files.** A placeholder looks like a file
   but is not one. Force a download in Finder before blaming the code.
2. **`.venv` is not in git.** Rebuild if it fails to start:
   ```bash
   rm -rf .venv
   ~/.pyenv/versions/3.14.4/bin/python3 -m venv .venv
   ./.venv/bin/pip install -r requirements.txt
   ```
3. **`params.xlsx`, `data/composition/` and `figures/` are generated.** Rerun;
   nothing is lost.

> **A warning paid for in lost time.** iCloud syncs `.venv` — 386 MB of
> `site-packages`, pandas' own compiled test bytecode included — one small file
> at a time. While that runs, **every git command touching the index or the
> object store hangs indefinitely** in any repo under `Documents/`. It looks
> like a broken repository and is not. Wait for `brctl status` to go quiet.
>
> Do **not** try to fix this by renaming `.venv` to `.venv.nosync`. That was
> tried today, it does stop the sync, and it was reverted on instruction: it
> leaves conflict folders behind and iCloud can propagate the exclusion to the
> other Mac as a deletion. Leave the venvs alone.

---

## 3. Where things stand

Repository: <https://github.com/MattRoess/RAWCLICVehicleBattery>. Branch
**`composition-distributions`**, ahead of `main` and **pushed**. For what is on
it, `git log --oneline main..HEAD` — a count written here goes stale the next
time anyone commits, as it already did once.

All seven scripts run. `03` takes **5 min 15 s** at 200,000 draws — timed.

```bash
./.venv/bin/python 00_parameters.py                 # always first
./.venv/bin/python 99_check_environment.py
./.venv/bin/python 01_draw_battery_structure.py
./.venv/bin/python 02_composition_by_capacity.py
./.venv/bin/python 03_capacity_by_chemistry.py
./.venv/bin/python 04_chemistry_scenarios.py
./.venv/bin/python 05_composition.py   # THE DELIVERABLE, and every figure
```

**`05_composition.py` is the one to hand on.** It writes `data/consolidated/`, one file per
chemistry in the INPUT WORKBOOK'S OWN SCHEMA, expanded — which is what the rest
of RAWCLIC expects and what the earlier bespoke shape was not:

```
additionalSpecification | Layer 1 | Layer 2 | Layer 4 | parameterCode | UoM | DQS
productionYear | capacity_kwh | Value | min_value | max_value | count_value
meanValue | medianValue | modeValue | STD | p025 | p975
```

Nothing in it is invented: every `Layer 1`, `Layer 2` and `Layer 4` is the
workbook's own, and `DQS`/`count_value` are carried through, not recomputed.
Added are the year, the anchor capacity, kg instead of kg/kWh, and the six
statistics named as `RAWCLICVehicleElectronics` names them. 9 files, 16,005 rows,
with the per-draw arrays beside them — the distribution next to the value.

`03` still writes the segment-year files; they were kept deliberately.

### What changed today

**Every mass now carries its whole distribution, not just a band.** Eleven
columns, matching what `RAWCLICVehicleElectronics` writes: `mass_kg`,
`mass_mode`, `mass_median`, `mass_mean`, `mass_std`, `mass_min`, `mass_max`,
`mass_p2.5`, `mass_p25`, `mass_p75`, `mass_p97.5`. All from the same draw array,
never from the percentiles — the element aggregation sums on draws because a
percentile of a sum is not the sum of percentiles.

**`n_draws` is 200,000**, matching that model's `N_SIMULATIONS`. Measured: the
mean and the 2.5/97.5 percentiles move only ~0.1% between 20,000 and 200,000,
so the bands were already settled. The **mode** is why — it is a histogram peak,
and against the triangular's known mode of 1.0 it tightens from 1.57% worst case
to 0.44%.

**The draws themselves are persisted** as element fractions, at the workbook's
five capacity anchors per chemistry, in `data/composition/element_draws/` —
`float32 (draws × elements) .npy` beside an `elements.txt`, the electronics
layout. 70 files, 328 MB. Stock-and-flow multiplies element data against its own
per-draw vehicle counts, draw against draw, which no percentile supports.

> **The consumer must interpolate, and above 100 kWh extrapolate.** The fitted
> capacities land between anchors (JC 76.3) and past the top one (JE 104.5, F
> 106.1). Checked on `battLiNMC_midNi`: linear interpolation is within **0.51%**
> and linear extrapolation within **0.41%**. **Only that one chemistry was
> checked, and nothing above 106 kWh.** Fractions are strongly capacity-dependent
> — they shift 21–60% relative across 25→100 kWh, because pack hardware does not
> scale with kWh while cell materials do. One array per chemistry would have been
> wrong by up to 60%.

**Sodium and solid-state have packaging masses.** 72.0% and 75.0% of their rows
now carry a mass; the rest is labelled `unknownBatteryMaterial`.
`composition_status` separates `packaging_from_base`, `unknown_remainder` and
`unknown`.

**A trap worth knowing about.** The density trajectory was once applied in `03`
but not in `03`, so the two deliverables disagreed about the same quantity —
nickel fell 23% in one and never moved in the other — and every figure, which
reads `03`, showed a flat line that was simply wrong. They now share
`density_factor()` in `03`. **If you add another consumer, use that helper.**

**What the distributions say, and it is the useful result.** Comparing
chemistries at the same quantity: lithium spans 6.55–9.90 kg across chemistries
against 1.24 kg of uncertainty within one, nickel 27.2–58.5 against 7.2, copper
33.4–46.4 against 4.0. **Which chemistry wins matters 3–4× more than the
composition uncertainty**, which says the effort belongs on the chemistry-share
scenarios rather than on tightening the composition data.

---

## 4. What was decided today, and what it rests on

| decision | value | note |
|---|---|---|
| Sodium anode collector and cell terminals | **Al**, mass × **0.4764** | density AND conductivity: (59.6/37.7) × (2.70/8.96). Equal conductance is an **assumption** |
| Sodium pack copper | **12.12 kg**, cables only | was 45.07 kg; the anode collector alone was 27.56 of it |
| Solid-state is bipolar | no cell casing, no module enclosures | one package for the whole battery, not one per cell — **38.2 kg** at 75 kWh, on top of separator, electrolyte and per-cell terminals |
| Solid-state collectors | **halved** | the bipolar plate is shared: cathode collector of one cell, anode collector of the next |
| Solid-state collectors stay **copper** | 21.46 kg at 75 kWh | claimed deliberately, because the copper is the number wanted. **Treat as an upper bound** — a solid-state cell may need no copper substrate at all |
| Solid-state structure | scales by base Wh/kg ÷ solid-state Wh/kg | **the correction that makes it work**, see below |

### Added 2026-09-10

| decision | value | note |
|---|---|---|
| **Every** chemistry now has a density trajectory | — | before today only solid-state had one, so seven of nine never improved: a 2070 NMC pack held exactly a 2030 pack's materials |
| Sodium | **160 / 200 / 220** Wh/kg cell at 2030/2040/2050, flat after | supplied. Cell-to-pack **0.650**, measured as LFP's own, since sodium's packaging comes from LFP |
| Solid-state, revised | **400** in 2030 → **800** in 2070 | 400 is where cells ARE, not where they arrive. The old curve started at 400 in 2040 and so built in a decade of no progress |
| Seven lithium chemistries | today's measured density, **+30% by 2050**, flat after | +30% supplied. Flat is a **ceiling argument**: +30% puts NMC high-Ni at 441 Wh/kg cell and liquid electrolyte with graphite or silicon runs out near 400–450. Past that is a lithium-metal anode, which is `solid_state`, not this chemistry |
| Which lithium densities | **measured**, not the supplied 330/235 | measurement gives 339 and 233, within 3%. Used so the trajectory and the composition cannot contradict each other — a trajectory of 330 against a composition implying 339 makes the implied pack mass disagree with the sum of its own parts |
| **battLiMFP pinned at 270 Wh/kg**, composition rescaled | +24.6% material | see below |
| **battLiMFP lithium corrected to stoichiometry** | 3.45% → **4.40%** of cathode | its SECOND defect, see below |
| The year now moves the mass | Ni in an 80 kWh NMC high-Ni pack: **58.5 kg (2025) → 45.0 (2050)**, −23.1% | the density gain expressed as mass. Uniform across components, which is an assumption: cables scale with current rather than energy and are understated late |

**Two LMFP corrections, the only numbers here that override the source.** Both
are in parameters rather than the workbook, so a WP3 revision removes them.

*Its lithium.* Lithium as a share of cathode active material lands on the
compound's own arithmetic for every chemistry — LFP 4.59% against 4.40% for
LiFePO₄, the three NMCs 7.29–7.37% against 7.19%, NCA 7.40% — except LMFP at
3.45%, 22% short. It cannot be the exception: LiMnₓFe₁₋ₓPO₄ carries the same
lithium per formula unit as LiFePO₄, and manganese (54.94) and iron (55.85)
weigh almost the same. Pinned at 4.40% via
`technology.element_share_of_component_override`.

*Its energy density.* The workbook implies 336 Wh/kg, which makes LMFP *lighter per kWh than
NMC mid-Ni* — 2.947 against 3.179 kg/kWh. It cannot be: LMFP is LFP with
manganese substituted in, and its advantage is a higher voltage plateau, not a
nickel-cobalt cathode. Two further signs it is a rescaled LFP rather than a
measurement: the ratio to LFP is near-uniform across every component (anode 0.68,
cathode 0.71, separator 0.62, collectors 0.58), where a real cathode change would
land on the cathode; and every row is `count_value = 1`, `DQS = 2`.

Pinned at 270, between LFP's 233 and NMC low-Ni's 285. Correcting it means
**rescaling the cell**, because a composition per kWh IS an energy-density claim:
kg/kWh is one over Wh/kg. `Value`, `min_value` and `max_value` scale together —
`_factor_bounds` checks the band is a fixed proportion of the value, so scaling
one alone would have broken every LMFP distribution rather than merely biased it.
Ordering restored: LFP 233, LMFP 270, NMC low 285, NMC mid 311, NMC high 339.
**Revisit if WP3 revises the workbook** — the parameter is
`technology.cell_density_override_wh_per_kg`.

**The finding worth keeping.** The structure scales with the battery it carries,
not with its kWh. Carried over unscaled, NMC's 87 kg frame exceeded the entire
88 kg a 45 kWh 2060 pack is meant to weigh, and **16 of 20 segment-years came out
negative**. Scaled, none do, and the unknown active material lands at **48–61%**
of pack mass against roughly 42% in today's NMC — the right direction for a
chemistry that has shed this much inert structure. A guard raises rather than
writing a negative mass, so it now catches a real contradiction.

**Matthias's rule of thumb checks out, in the middle years only.** "A 150 kWh
solid-state pack uses the materials of a 75 kWh one" needs the density ratio to
be exactly 2. It is 1.79 in 2040 — a 150 kWh pack is then 12% *heavier* than a
75 kWh NMC — passes through 2 around 2050 (the 200/100 case lands at **0.99**),
and reaches 2.68 by 2060.

---

## 5. Open

0. **The figures were rejected and rebuilt.** Settled 2026-09-10. `03` now draws
   all elements in one stacked figure per chemistry, plus one figure per critical
   raw material across every chemistry; `03` draws one figure per material with
   every chemistry's distribution overlaid in absolute kg. Two constraints he
   stated and neither should be undone: **no log scales**, and **no small
   figures** — so no facet grids, one subject per full-size figure.

   Uncertainty on the stacked figure is on the TOTAL only. That is a real limit,
   not laziness: iron is 600× lithium, so on one linear axis a per-element band
   for lithium is thinner than its own line. Per-element bands are on the CRM
   figures. If per-element uncertainty is wanted per chemistry, the only honest
   way on a linear axis is two figures split by magnitude — offered, not taken.

1. **The active materials for sodium and solid-state.** Still the only real gap.
   Cathode, anode and electrolyte are `unknownBatteryMaterial`. **Both** now have
   a density trajectory, so both carry a total as `unknown_remainder` — sodium's
   was empty until today. The split between cathode and anode is not known for
   either. **The numbers have to come from literature or WP3.**
2. **150 and 200 kWh.** The model answers for them (range 10–200 kWh) and the
   density scaling extends cleanly — remainder 64–71%, no negatives. But they are
   50% and 100% past the last anchor and **untested there**, and *nothing asks for
   those capacities*: the 600 km saturation caps every segment near 106 kWh. To
   make them appear, something has to drive them — a large-battery segment, or a
   higher range target. **That decision was not taken.**
3. **Interpolation checked on one chemistry only.** Extend to the other six
   before relying on the fraction arrays.
4. **The electrolyte's element breakdown** itemises only lithium, losing 99% of
   its own mass at element level.
5. **Sales weighting** — every vehicle-table result is by models, not
   registrations.
6. **`battery_size_map` is low for every segment** — JB +23%, JC +21%, JE +24%
   against the fitted values on the useable basis. Changing it moves published
   results in RAWCLICStockAndFlow.

---

## 6. Where things are

| | |
|---|---|
| `src/params_schema.py` | **the file to edit.** 113 settings, each with its own comment; `00_parameters.py` validates every one |
| `src/composition.py` | composition at any capacity, with uncertainty; `element_draws_at()` returns the draws themselves |
| `src/ev_details.py` | the vehicle table: parsing, smoothing, bootstrap |
| `src/scenarios.py` | the three scenarios and the returning mix |
| `05_composition.py` | the deliverable, including `build_unknown_rows` for the two unknown chemistries |
| `export.unknown_chemistry_template` | what may be claimed about sodium and solid-state, and why |
| `data/raw/` | the two inputs — **not in git**, supplied via iCloud |
| `data/composition/` | nine segment-year CSVs plus `element_draws/` — generated |
| `data/consolidated/` | **the deliverable** — nine files in the workbook schema plus their draw arrays, from `03` |
| `technology.chemistry_energy_density` | every chemistry's trajectory, and the reasoning for each |
| `technology.cell_density_override_wh_per_kg` | where the workbook's density is not believed — currently LMFP only |
| `figures/` | nine figures — generated |

**No data file is ever committed.** `data/` and `figures/` are excluded at the
folder, so a new output cannot slip through by having an extension nobody listed.
That includes the 328 MB of `element_draws/`.
