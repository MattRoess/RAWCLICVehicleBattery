# Handover — RAWCLICVehicleBattery

Written 2026-09-10, superseding the earlier 09-10 version. For resuming on the
**office Mac on Monday 2026-09-14**.

State verified against the repository and against runs made today, not
remembered. For the methods and the reasoning, read
[`METHODOLOGY.md`](METHODOLOGY.md).

**Read §0 first.** It is how to work on this project, and it cost the most to
learn.

---

## 0. How to work on this, and what went wrong today

Three separate times today a narrow instruction was read as authorisation for a
broad change, and the work had to be reverted. The pattern was always the same:
Matthias points at **one** thing, the assistant comes back with a **bigger**
thing. Sodium's capacity became a proposal to change the range-saturation gate,
which became an argument to replace the whole fitted-curve basis, which became
an unasked rewrite of `segment_capacities`.

The rules that follow are his, stated repeatedly, and they are not negotiable:

- **Ask before every change. Propose and wait.** "Implement it" answers *whether*,
  not *which* — if two options were on the table and he has not named one, the
  choice is still his.
- **He runs the long jobs.** "I always told you that long reruns are up to me."
  Never run the pipeline against `data/` or `figures/` unasked. Test in a
  sandbox — see §2.
- **Do not widen the scope.** If he narrows, narrow with him. An adjacent defect
  you notice is a thing to *report*, not to fix.
- **Never claim an unmeasured number.** A claim that a rerun changes nothing must
  be verified before it is made, not after. That specific mistake was made today.
- **He decides what is useful.** Not the assistant.
- **No dead code, and no flag that switches code off.** When something is cut,
  it moves to its own runnable file — `06_segment_capacity.py` is the pattern.
  A `write_segment_files: bool` was written for exactly this and rejected on
  sight.
- **"Ready to run" means every output was checked, not the convenient ones.**
  `05` was called ready when only the segment-year files and the figures had
  been verified; the consolidated files — the actual deliverable — had never
  been looked at and were missing every rule decided that day. That cost a
  full rerun.

The afternoon of 2026-09-10 cost several reruns, and every one traces to the
same thing: he had already said what he wanted and it was not acted on. He
said the composition is per capacity in the morning; the whole segment
apparatus kept running until the evening.

---

## 1. Picking up on the office Mac

The project lives in iCloud Drive, so the whole folder syncs, `data/` and
`figures/` included. Neither is in git.

```bash
cd "/Users/rm/Documents/GitHub/RAWCLICVehicleBattery"   # == the iCloud path
git pull                                                # branch composition-distributions
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
3. **`params.xlsx`, `data/composition/`, `data/consolidated/` and `figures/` are
   generated.** Rerun; nothing is lost.

> **A warning paid for in lost time.** iCloud syncs `.venv` — 386 MB of
> `site-packages` — one small file at a time. While that runs, **every git
> command touching the index or the object store hangs indefinitely** in any repo
> under `Documents/`. It looks like a broken repository and is not. Wait for
> `brctl status` to go quiet.
>
> Do **not** rename `.venv` to `.venv.nosync`. It was tried, it does stop the
> sync, and it was reverted on instruction: it leaves conflict folders behind and
> iCloud can propagate the exclusion to the other Mac as a deletion. **Leave the
> venvs alone.**

---

## 2. Running it

```bash
./.venv/bin/python 00_parameters.py                 # always first, validates 128 settings
./.venv/bin/python 99_check_environment.py
./.venv/bin/python 01_draw_battery_structure.py
./.venv/bin/python 02_composition_by_capacity.py
./.venv/bin/python 03_capacity_by_chemistry.py
./.venv/bin/python 04_chemistry_scenarios.py
./.venv/bin/python 05_composition.py                # THE DELIVERABLE, and every figure
./.venv/bin/python 06_segment_capacity.py           # the cut segment work; not needed
```

**`05_composition.py` is the one that matters.** It writes the consolidated
files, the per-draw arrays and all 18 figures.

**`06_segment_capacity.py` is not part of the deliverable and does not need to
run.** See §3, "what 05 stopped doing".

**Its runtime at 200,000 draws has not been timed.** The last measured figure
(5 min 15 s) was for the pre-merge `03` and does not carry over — `05` now does
strictly more work. Do not quote a number until someone times it.

### Testing without touching `data/`

Never smoke-test against the real output directories. The harness used today is
in the session scratchpad and is three lines of principle:

```python
import src.params_schema as ps
_real = ps.current
def patched():
    p = _real()
    p.monte_carlo.n_draws = 2000                     # shape, not precision
    p.export.composition_output_dir  = OUT + "/composition"
    p.export.consolidated_output_dir = OUT + "/consolidated"
    p.paths.output_dir               = OUT + "/figures"
    return p
ps.current = patched
```

Then `importlib.import_module('05_composition').main([])`. Verified today: exit
0, 9 consolidated files, 35 draw arrays, 18 figures. `06` runs the same way and
also exits 0.

---

## 3. Where things stand

Repository: <https://github.com/MattRoess/RAWCLICVehicleBattery>. Branch
**`composition-distributions`**, ahead of `main` and **pushed**. For
what is on it: `git log --oneline main..HEAD` — a count written here goes stale.

Today's commits, newest first:

| commit | what |
|---|---|
| `be418ad` | the segment capacity work moved out of `05` into `06_segment_capacity.py` |
| `38a0575` | the consolidated files finally get the pack rules; 200 kWh for LMFP only; CRM-over-time figures removed |
| `5a32ea8` | this handover |
| `534e5a0` | composition at held capacity; improvement drawn, not asserted; structure follows weight; 400/800 V |
| `892df4e` | capacity scenarios `saturate` / `grow_low` / `grow_high`, A–D only |
| `1f693c9` | sodium/solid-state claims, shared-parts distribution, component `mass_scale` fix |

### What `05` stopped doing, and why

**It was answering a question it cannot answer.** How big a battery a segment
carries in a given year depends on how many cars of what size exist and when.
That is fleet knowledge: RAWCLICStockAndFlow has it, this project does not.
Every run paid for a fitted capacity curve, a 600 km range target and a
per-segment Wh/km median — and every wrong answer they produced was an answer
to a question that was never ours.

`05` now answers only what it can: **what is inside a battery of capacity X in
year Y at voltage V**, at the workbook's own anchors, with the draws beside it
so the consumer interpolates. 287 lines lighter.

Removed outright, not disabled — a switch that turns code off is still code
nobody reads:

| gone from `05` | now in |
|---|---|
| `segment_capacities`, `capacity_growth_factor` | `06_segment_capacity.py` |
| `range_saturated_capacities`, `segment_consumption`, `pack_density` | `06_segment_capacity.py` |
| the segment-year export loop, `capacity_by_segment_year.csv` | `06_segment_capacity.py` |
| the `EVDetails` import | `06` only |
| `density_factor` | **deleted** — zero callers once the mass scaling moved to the drawn improvement |
| the figures' read-back of `composition_*.csv` from disk | **deleted** — they build their own rows now |

`06` writes `segment_composition_<chemistry>.csv`, named apart from `05`'s
output so the two can never be mistaken for each other. It imports the row
builders from `05` rather than copying them: two copies of `build_rows`
drifting apart is the failure this project has already had three times.

> **`06`'s two defects are stated in its own docstring, and they are why it is
> not the deliverable.** The capacity curve is fitted over seven observed years
> and projected over forty-four; and the range target fires for two chemistries
> and not the other seven, with no year in the line that sets it, so sodium and
> solid-state hold one capacity for all fifty years. **If that path is ever
> revived, the range target must apply to all nine chemistries or to none.**

### The composition figures answer a different question now

They used to follow segment JC, whose capacity runs 65 → 76 kWh, so the mass
**rose** to 2025 before falling — a capacity trend drawn on top of the
improvement the figure exists to show. They now **hold capacity constant**, at
80 kWh and 200 kWh, and the only thing moving with the year is the cell getting
better. LFP at 80 kWh: 464 → 372 kg, a straight line.

The segment capacity trajectory belongs to the stock-and-flow path, which
interpolates these files over capacity. `export.over_time_figure_capacities_kwh`
controls which capacities are drawn; `over_time_figure_voltage_v` picks the
voltage (drawing both would stack every element twice).

**200 kWh is twice the workbook's top anchor.** Every mass at it is
extrapolated, and the figure title and the run log both say so.

### The improvement is a distribution, not a number

How much lighter the same kWh gets by 2070 is not known to three figures, so it
is drawn: **triangular, min 15%, mode 20%, max 30%**, interpolated linearly from
zero in 2020. `technology.mass_improvement_2070`.

> **It is drawn ONCE per Monte Carlo draw and shared by every component, element
> and year.** It is one uncertainty about the technology, not an independent
> error per row. Drawn per row it would cancel in any sum and the total would
> come out falsely certain — the same reasoning as the workbook's own
> `factor_draws`.

It is handed to `weights_at()` so it multiplies the **draws**, before any
percentile is taken. Applied to a percentile afterwards it would slide the band
without widening it. Measured on LFP at 80 kWh: the band grows from **15.5%** of
the central in 2020 to **21.6%** in 2070, and the central falls exactly 20.0%.

> **`density_factor()` is gone.** The mass scaling moved to the drawn
> improvement and left it with zero callers. The 2070 endpoints in
> `technology.chemistry_energy_density` are now **decorative for mass** — change
> one and the other will not follow. This is a trap; the docstring says so.

### The distribution figures have a year, and it is a parameter

They had none. `collect_draws()` took the draws straight from the workbook with
nothing applied, so they were the base year by accident and said so in no
title. **`export.distribution_figure_year`** names it, defaulting to 2020 — the
numbers are what they always were and only the label is new. Set it to any
export year and `improvement_factor_draws()` is applied draw by draw, exactly
as the composition files apply it, so both the mass and the band move.

> **The band is asymmetric, and that is correct.** LFP at 80 kWh is
> −36.1 / +36.1 kg in 2020 and **−48.1 / +32.3 kg** in 2070. The triangular
> runs 15 / 20 / 30, so mode-to-max is 0.10 against 0.05 from min-to-mode: the
> improvement can beat expectations by twice as much as it can disappoint, and
> more improvement means a lighter pack. The skew is the spec, not a defect —
> confirmed and kept on 2026-09-10. A symmetric band would need a symmetric
> spec, 12.5 / 20 / 27.5.

> **What the band does NOT yet carry is uncertainty about the projection
> itself.** In kg it narrows before it widens: 72.1 kg in 2020, 69.5 in 2035,
> 80.4 in 2070, because the composition band shrinks with the mass while the
> improvement's own spread (±9.7 pp on a 20% improvement) barely outruns it. A
> 2070 pack is therefore drawn as almost as well known as a 2020 one, which it
> is not. A horizon-growing projection term would fix it; its width was never
> chosen. **Raised 2026-09-10, not decided.**

### The structure follows the weight it carries

The workbook gives every chemistry the **same** iron at a given capacity. That
put 123 kg of frame and module box around 343 kg of LFP cells but also around
200 kg of solid-state cells — a structure-to-cell ratio of 0.52 against **0.88**,
a box weighing nearly as much as its contents.

The iron is now scaled by the cell mass it supports, against the reference. The
ratio is **0.31 for all nine**.

> **`technology.structure_reference_chemistry` sets the level for everyone.** It
> is LFP. Its own iron is unchanged and every other chemistry moves relative to
> it, so a denser reference makes the whole fleet heavier. Using the codebase's
> other `reference_chemistry` (NMC high-Ni) would make every chemistry ~45%
> heavier in iron. **Worth arguing about.**

Aluminium is deliberately **excluded** from the scaling, including the
enclosure's aluminium half: the heat to be moved is set by the capacity, not by
the pack's weight.

### 400 V and 800 V, in one file

A `voltage_v` column, values 400 and 800. Same power at double the voltage is
less current and less conductor: **a third off** the copper in the cables and
the cell terminals — not a half, because a busbar is also sized by handling,
connector geometry and minimum crimp gauge.

The **anode current collector is untouched**: it is sized by the cell, not by
the pack bus.

Two rows rather than two files because the stock-and-flow model already
interpolates these files over capacity; a column it can filter on costs it
nothing.

### A bug found while testing, worth remembering

The figures were bypassing the enclosure split, the structure scaling **and** the
voltage expansion — all three ran in `main` on the export rows only, so the CSVs
and the PNGs would have disagreed. Both paths now go through one
**`apply_pack_rules()`**. *If you add a third consumer, use that function.*

This is the second time these two outputs drifted apart. The first was
`density_factor` applied to the consolidated files but not the segment-year
ones, which had nickel falling 23% in one and never moving in the other.

---

## 4. Decided today, and what it rests on

| decision | value | rests on |
|---|---|---|
| Improvement to 2070 | **15 / 20 / 30 %**, triangular | supplied. Was 25%, revised down |
| Improvement starts | **2020** | supplied. Replaced a steep-then-flat curve that reached its full −23% by 2050 and did nothing after |
| Sodium cell density | **200 Wh/kg** | supplied — "car sodium is already around 200". Replaced 160 |
| Module enclosure | **50/50 Al/Fe** | supplied. The workbook files all of it as iron. Component total unchanged, only its makeup moves |
| Solid-state keeps module enclosures | **34.6 kg at 80 kWh** | they are pack hardware, not cell packaging — the same box the frame bolts into. They had been grouped with the cell packaging by mistake, leaving solid-state the only one of nine without them |
| Solid-state cell packaging | **all gone** — no casing, separator, electrolyte or per-cell terminals | bipolar with many layers |
| Solid-state collectors | **halved** | one clad Al–Cu plate shared between adjacent layers; the many-layer limit of (N+1)/2N |
| Copper at 800 V | **× 2/3** | supplied. A third off, not a half |
| Capacity growth scenarios | `saturate` / `grow_low` +5%/decade / `grow_high` +10%/decade | supplied. **A–D and JA–JD only** |

### The price finding, which is the evidence behind the capacity scenarios

Across **717 A–D models** with a German list price, from `EV_details.csv`:

- at the **same capacity and segment**, an LFP car is **17.7% ± 1.4 pp cheaper**
- at the **same price and segment**, it carries **+2.0% ± 1.8 pp more kWh** —
  statistically nothing

So through 2026 the chemistry cost saving went **essentially all to price and
none to capacity**. That is why `saturate` is the default: it is what the record
shows. The `grow_*` scenarios assume the split changes; nothing measured says it
will, and the parameter comment says so.

Supporting measurements, same source:

- median capacity plateaued at **~82 kWh from 2023**, while fast-charge power
  rose 101 → 180 kW (2020 → 2024) and the C-rate went 1.69 → 2.20 and flattened
- motor count flat at **~1.4** since 2020 (AWD 532 / Rear 402 / Front 392),
  median power flat at **210–220 kW** since 2022
- segment F runs at **1256 €/kWh** against 625–790 in A–C — the large segments
  are not price-constrained, which is why they do not grow

### The two LMFP corrections still stand

Both override the source and both live in parameters, so a WP3 revision removes
them: lithium pinned at **4.40%** of cathode (stoichiometry; the workbook's 3.45%
is 22% short and LMFP cannot be the one exception), and cell density pinned at
**270 Wh/kg** (the workbook implies 336, which would make LMFP lighter per kWh
than NMC mid-Ni). Correcting the density **rescales the cell**, because kg/kWh is
one over Wh/kg. Ordering restored: LFP 233, LMFP 270, NMC low 285, NMC mid 311,
NMC high 339.

---

## 5. Open — nothing below has been decided

**Raised and waiting on Matthias:**

1. **Thermal conductor for sodium and solid-state.** Both have much lower thermal
   demand and should carry less than the 41.8 kg the lithium packs do — *except
   under fast charging*, where the heat is the same whatever the cathode is. Two
   numbers needed: the reduction, and whether fast charging cancels it. **Not
   started.**
2. **Solid-state's density gain was flattened.** It ran 400 → 800 Wh/kg, a
   doubling. It now takes the same 20% as everything else (400 → 500). Bipolar
   with many layers is the argument for keeping it steeper. **Flagged, not
   confirmed.**
3. **Sodium's own curve was overwritten.** The 160 / 200 / 220 Wh/kg at
   2030/2040/2050 is gone, replaced by the 2020→2070 ramp. **Flagged, not
   confirmed.**

**Both moved to `06_segment_capacity.py`, which is no longer the deliverable:**

4. **Sodium and solid-state capacity is a constant 86.4 kWh in segment C for
   every year 2020–2070.** `range_saturated_capacities()` fires on
   `if unknown and ...`, so it applies to those two chemistries and to no others,
   and the line that sets it has **no year in it**:
   ```python
   saturated = wh_per_km * 600 / 1000      # wh_per_km: one median, no year
   ```
   Segment C's own cars were 50.6 kWh in 2020 and 64.0 in 2025. It also means
   those two chemistries are **deaf to `export.capacity_scenario`**: under
   `saturate` sodium is 31% above the lithium capacity and under `grow_high` 14%
   below — the sign flips. A fix was written and **reverted on instruction**. The
   open question was: range saturation **off for all nine, or on for all nine**.
   It must never again apply to a subset.
5. **The fitted capacity curve.** `segment_capacities()` still calls
   `ev.curve(segment)`, in `06`. Matthias's position is unambiguous — *"fitting is shit"* —
   and the evidence supports him: seven observed years against forty-four
   projected, per-segment slopes running **−2.5 to +2.4 kWh/yr** with no
   consistent sign, and the fit disagreeing with its own data (segment C measured
   62.0 kWh in 2020, the fit says 50.6; JC's fit is 5.7 kWh below the 2026
   median). A fleet median also moves when the **model mix** changes, not only
   when batteries change, so its slope is not a technology trend.
   A replacement — measured recent-year median as the anchor,
   `capacity_scenario` carrying everything after — was written and **reverted on
   instruction, twice**. Do not start it again without being asked.

**Still the real gap:**

6. **Active materials for sodium and solid-state.** Cathode, anode and
   electrolyte are `unknownBatteryMaterial`. The split is not known for either.
   **The numbers have to come from literature or WP3.**

**Older, still open:**

7. **Capacity trend from long-history nameplates.** Matthias's own method: a
   trend needs models with a long history, not a cross-section. Ten candidates
   were identified. Two traps found: "Tesla Model" lumps 3/S/X/Y across 84
   variants, and the BMW i3 series shows 21.6 → 115 kWh, which is a data error.
8. **Interpolation checked on one chemistry only** (`battLiNMC_midNi`: within
   0.51% interpolating, 0.41% extrapolating). Extend to the other six before
   relying on the fraction arrays.
9. **The electrolyte's element breakdown** itemises only lithium, losing 99% of
   its own mass at element level.
10. **Sales weighting** — every vehicle-table result is by models, not
    registrations.
11. **`battery_size_map` is low for every segment** — JB +23%, JC +21%, JE +24%.
    Changing it moves published results in RAWCLICStockAndFlow.
12. **Stock-and-flow stage 04 is Matthias's own.** He is starting it fresh.
    **Nothing about it belongs in this file, and no analysis of it should be
    offered unless he asks.**

---

## 6. Where things are

| | |
|---|---|
| `src/params_schema.py` | **the file to edit.** 128 settings, each with its own comment; `00_parameters.py` validates every one |
| `src/composition.py` | composition at any capacity, with uncertainty. `weights_at()` takes `year_factor_draws`; `element_draws_at()` returns the draws themselves |
| `src/ev_details.py` | the vehicle table: parsing, smoothing, the fitted curve. **`05` no longer imports it** — only `06` does |
| `src/scenarios.py` | the three chemistry-share scenarios |
| `05_composition.py` | **the deliverable.** `apply_pack_rules()`, `fixed_capacity_rows()`, `improvement_factor_draws()`, `build_unknown_rows()` |
| `06_segment_capacity.py` | the segment work cut out of `05`. Runnable, not needed, two known defects in its docstring |
| `technology.mass_improvement_2070` | **the improvement, as a distribution** |
| `export.distribution_figure_year` | which year the distribution figures are for |
| `technology.structure_reference_chemistry` | sets the iron level for all nine |
| `technology.pack_voltages_v` / `copper_scale_by_voltage` | 400 V and 800 V |
| `technology.module_enclosure_split` | the 50/50 Al/Fe judgement |
| `export.unknown_chemistry_template` | what may be claimed about sodium and solid-state, and why |
| `export.capacity_scenario` | `saturate` / `grow_low` / `grow_high` |
| `technology.cell_density_override_wh_per_kg` | where the workbook's density is not believed — LMFP only |
| `data/raw/` | the two inputs — **not in git**, supplied via iCloud |
| `data/composition/` | `element_draws/` — generated by `05`. `segment_composition_*.csv` and `capacity_by_segment_year.csv` only if you run `06` |
| `data/consolidated/` | **the deliverable** — nine files in the workbook schema plus their draw arrays |
| `figures/` | 18 figures — generated |

**No data file is ever committed.** `data/` and `figures/` are excluded at the
folder, so a new output cannot slip through by having an extension nobody
listed.
