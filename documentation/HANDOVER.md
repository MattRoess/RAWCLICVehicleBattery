# Handover — RAWCLICVehicleBattery

Written 2026-09-10, last revised **2026-10-02**. The Monday it was written for
has passed; this is the current state.

**Sodium-ion changed on 2026-10-02: it is now two cells built from literature,
`Na_ion_layered` and `Na_ion_prussian_white`, and the old packaging-only `Na_ion`
is gone from this repository's composition. Read §7 for everything about sodium.
§0 still governs how to work.**

State verified against the repository and against runs made on the date of each
revision, not remembered. For how each chemistry develops over time, read
[`CHEMISTRY_OVER_TIME.md`](CHEMISTRY_OVER_TIME.md). For the methods and the reasoning, read
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
- **No dead code, and no flag that switches code off.** A `write_segment_files:
  bool` was written for exactly this and rejected on sight. When something is
  cut it may move to its own runnable file as a holding place, but that is a
  waiting room, not a home: `06_segment_capacity.py` sat there until 2026-09-14
  and was then deleted, because the question it answered is now answered
  per draw in RAWCLICStockAndFlow's `src/battery_capacity.py`.
- **"Ready to run" means every output was checked, not the convenient ones.**
  `05` was called ready when only the segment-year files and the figures had
  been verified; the consolidated files — the actual deliverable — had never
  been looked at and were missing every rule decided that day. That cost a
  full rerun.

The afternoon of 2026-09-10 cost several reruns, and every one traces to the
same thing: he had already said what he wanted and it was not acted on. He
said the composition is per capacity in the morning; the whole segment
apparatus kept running until the evening.

**2026-10-02, three more, and he found each one, not a test.**

- **The product-structure diagram was not updated.** `01` reads
  `unknown_chemistry_template`, which does not contain the two new cells, so it
  went on saying "NOT KNOWN" and "no composition exists" for sodium and drew
  neither chemistry nor the new component. It was known while editing, was
  answered by one line that only stopped the cells being called workbook
  chemistries, and the report said exactly that and nothing about the gap. **When
  a chemistry is added, grep every reader of `unknown_chemistry_template` and
  `chemistries_without_composition` and list each as done or not done in the
  report. A summary that is true of what was changed and silent about what was
  not is a failure.**
- **A proof at one capacity understated a rejection rate twenty-fold.**
  Negative-remainder draws were 0.5% of the layered cell at 80 kWh and 9.6% across
  the five anchors, almost all of it at 25 kWh. Check every anchor, not the
  convenient one.
- **"The workbook" meant two things in one session**: the WP3 lithium workbook in
  `data/raw/`, and a new spreadsheet about sodium. See the glossary in §7.

**The same afternoon, six more, and again he found them.**

- **`Na_ion` was kept, unasked, "as a safeguard".** He had said two chemistries,
  and had to say "Na_ion is gone" before it went. It is out of the settings, `05`,
  the figures and the templates; every other output was byte-identical.
- **`02` and `04` enumerate chemistries too, and were missed the same way.** `02`
  drew neither sodium cell -- an earlier audit judged it unaffected without
  opening it. `04`'s footnote still said sodium has no composition after `Na_ion`
  left `chemistries_without_composition`, and its coverage line had quietly moved;
  that was found only by running `01`-`04` and comparing with the baseline, which
  is the check that should have come first. **A change to a setting is not
  finished until every script has been run and every figure that moved has been
  looked at.**
- **The product-structure diagram explained itself in the project's own jargon**:
  "the workbook", `c-p`, `e-c`, "Layer 1", "built here". His words: "Who the hell
  knows what the workbook is now?" **A figure's wording is plain or it is wrong.**
  It was rebuilt from scratch (§7) and carries its whole explanation in two short
  lines.
- **A report that said what was changed and not what was left out**, once more.
  Every report on this work now lists each consumer as done or not done.
- **`01` was made to depend on `05`, and then to run Monte Carlo.** He ran it and
  it stopped with "run 05 first". His words: "1 has to run before 5", "1 to 5 is it
  such hard to get. Build up step by step", "01 is NO MC", "just draw a figure",
  "01 is draw battery structure and nothing else", and "I do not want that code
  copies run in two different code". The detour moved code out of `05` and edited it
  in six places for a figure that needed none of it; it was undone, and `05` was
  checked byte-identical to before. **Take the smallest step that works, prove it,
  then take the next -- and a figure at step 1 never reads step 5.**
- **Chemistries nobody uses in an EV were drawn and calculated without asking.** `01`,
  `02` and `05` took "every chemistry in the lithium data", LMO and NCA included. His
  words: "NO LMO, NO NCA", "Use the chemistries, which we calculate the composition",
  "All figure have to reflect what we do", "02 figures are shit ... It shows
  chemistries, which we exclude". There is now one list, `scope.chemistries`, and
  everything follows it (§7). **Which chemistries go in a figure is his decision,
  asked before they are drawn.**

---

## 1. Picking up on the office Mac

The project lives in iCloud Drive, so the whole folder syncs, `data/` and
`figures/` included. Neither is in git.

```bash
cd "/Users/rm/Documents/GitHub/RAWCLICVehicleBattery"   # == the iCloud path
git pull                                                # branch main
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
./.venv/bin/python 00_parameters.py                 # always first, validates 125 settings
./.venv/bin/python 99_check_environment.py
./.venv/bin/python 01_draw_battery_structure.py
./.venv/bin/python 02_composition_by_capacity.py
./.venv/bin/python 03_capacity_by_chemistry.py
./.venv/bin/python 04_chemistry_scenarios.py
./.venv/bin/python 05_composition.py                # THE DELIVERABLE, and every figure
```

**`05_composition.py` is the one that matters.** It writes the consolidated
files, the per-draw arrays and all 19 figures.

`01`-`04` take seconds each and none reads another's output, so their order does
not matter. `01` is names only -- the parts of each chemistry and the elements each
is made of, with no weights and no Monte Carlo -- and needs nothing from any later
step. `99` is read-only and says to run it after `00`. Measured 2026-10-02 in a
sandbox, in the order 00, 01, 02, 03, 04, 05, 99 from an empty folder: all exit 0;
`01` 1 s, `02` 4 s, `03` 12 s, `04` 1 s, `05` 27 s at 2,000 draws. **`05` at 200,000 draws has not been run since the sodium cells
arrived**; they add statistics for every anchor and year, so expect it to take
longer than before, by an amount nobody has measured.

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

Then `importlib.import_module('05_composition').main([])`. Verified 2026-10-02,
after the chemistry list (§7): exit 0, 8 consolidated CSVs (499 files with their
draw arrays), 19 figures. For `01`-`04` the same idea needs only
`paths.output_dir` pointed somewhere else.
The result no longer depends on `PYTHONHASHSEED` (§7).

---

## 3. Where things stand

Repository: <https://github.com/MattRoess/RAWCLICVehicleBattery>. **Work is on
`main` now** — `composition-distributions` was merged and the branch still
exists but is behind. For what has landed: `git log --oneline` — anything
written here goes stale.

The run of commits that built the current state, newest first:

| commit | what |
|---|---|
| `4991f5c` | handover and README: Na_ion is gone, 01 is names only and runs first |
| `35e0abd` | remove Na_ion, draw the sodium cells in 02, rebuild 01 as a names-only structure figure |
| `d0a0432` | the product structure shows the two sodium cells and the unitemised component |
| `f928a1d` | drop the LMFP lithium override: the workbook is fixed at source |
| `8b34020` | **two sodium-ion cells built from literature**, every input drawn; the hash seed fixed |
| `bc2a0a9` | the sodium research the cells are built from |
| `3218cda` | stop pointing at the deleted `06_segment_capacity.py` |
| `6fbfb60` | write the element inside the component, stop clipping a residual |
| `9041c2a` | export draws for the two chemistries with no composition of their own |
| `5584baf` | **delete `06_segment_capacity.py`** and the eleven parameters only it read |
| `3785f40` | write the component level beside the elements, and guard both |
| `bec5ca0` | draw the packaging trust for sodium and solid-state |
| `8a7fa98` | `CHEMISTRY_OVER_TIME.md` |
| `b1fda81` | carry the improvement's uncertainty into the CSV statistics |
| `445510d` | put the persisted draws through the pack rules, and write them in kg |
| `a5dd51c` | the distribution figures have a year |
| `38a0575` | the consolidated files get the pack rules; 200 kWh for LMFP only |
| `534e5a0` | composition at held capacity; improvement drawn, not asserted; structure follows weight; 400/800 V |
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

| gone from `05` | where it went |
|---|---|
| `segment_capacities`, `capacity_growth_factor` | `06_segment_capacity.py`, then **deleted 2026-09-14** |
| `range_saturated_capacities`, `segment_consumption`, `pack_density` | same |
| the segment-year export loop, `capacity_by_segment_year.csv` | same |
| `density_factor` | **deleted** — zero callers once the mass scaling moved to the drawn improvement |
| the figures' read-back of `composition_*.csv` from disk | **deleted** — they build their own rows now |

**`06_segment_capacity.py` is gone as of 2026-09-14, and so are the eleven
parameters only it read** — `capacity_projection`, `capacity_scenario`,
`capacity_growth_per_decade`, `capacity_growth_segments`,
`max_projected_capacity_kwh`, `export_format`, `range_saturation_km`,
`apply_range_saturation`, `segment_consumption_wh_per_km`,
`consumption_from_year` and `capacity_fallback`. 119 parameters remain.

It was kept runnable in case the segment path was revived. It was not: the
question "what capacity does a segment carry" is now answered per draw in
RAWCLICStockAndFlow's `src/battery_capacity.py`, as a five-level discrete
mixture measured from EV_details.csv with a drawn growth rate and plateau year.
That is a better answer than the fit, and it lives in the project that knows the
fleet.

**As of 2026-09-16 `04_04` carries the modelling for it**, so nothing in this
project needs to answer a capacity question at all. `05`'s run header said as
late as `3218cda` that the segment work "lives in `06_segment_capacity.py`" —
a printed line naming a deleted file, which sends whoever reads the run output
looking for something that is not there. It now names `04_04` instead. **If you
find another reference to `06`, it is stale; there are none left in the code.**

> **Its two defects are why it was never the deliverable, and they are the
> reason not to revive it from history without rewriting it.** The capacity
> curve was fitted over seven observed years and projected over forty-four; and
> the range target fired for two chemistries and not the other seven, with no
> year in the line that set it, so sodium and solid-state held one capacity for
> all fifty years. Recoverable from `be418ad` and its successors if ever needed.

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

### One LMFP correction stands, and the other is gone

**Cell density is pinned at 270 Wh/kg** (the workbook implies 336, which would
make LMFP lighter per kWh than NMC mid-Ni). It overrides the source and lives in
a parameter, so a WP3 revision removes it. Correcting the density **rescales the
cell**, because kg/kWh is one over Wh/kg. Ordering restored: LFP 233, LMFP 270,
NMC low 285, NMC mid 311, NMC high 339.

**The lithium override is removed (2026-10-02, `f928a1d`).** It pinned LMFP's
cathode lithium at 4.40% because the workbook's 3.45% was 22% short. The diagnosis
was one element too narrow -- oxygen and phosphorus were short by the same factor
-- and the workbook's five LMFP cathode rows were corrected at the source on
2026-09-17, so lithium arrives at 4.408% on its own. Measured with and without it
at 80 kWh: 6.284 against 6.273 kg of lithium, and the cathode's elements summing
to 100.000% against 99.992% of the component. Small, which is why nothing failed;
but this section said both corrections stood for two weeks after one had not.

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
   confirmed.** The two sodium cells built from literature take the same ramp, for
   the structure scaling only; their cell mass is drawn (§7).

**Both moved to `06_segment_capacity.py`, and went with it when that file was
deleted on 2026-09-14. Recorded because the reasoning still matters:**

4. **Sodium and solid-state capacity was a constant 86.4 kWh in segment C for
   every year 2020–2070.** `range_saturated_capacities()` fired on
   `if unknown and ...`, so it applied to those two chemistries and to no others,
   and the line that set it had **no year in it**:
   ```python
   saturated = wh_per_km * 600 / 1000      # wh_per_km: one median, no year
   ```
   Segment C's own cars were 50.6 kWh in 2020 and 64.0 in 2025. It also means
   those two chemistries are **deaf to `export.capacity_scenario`**: under
   `saturate` sodium is 31% above the lithium capacity and under `grow_high` 14%
   below — the sign flips. A fix was written and **reverted on instruction**. The
   open question was: range saturation **off for all nine, or on for all nine**.
   It must never again apply to a subset.
5. **The fitted capacity curve.** `segment_capacities()` called
   `ev.curve(segment)`. Matthias's position is unambiguous — *"fitting is shit"* —
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

6. **Active materials for sodium and solid-state.** **Sodium: done 2026-10-02, as
   two cells built from literature (§7) -- a scenario, not a bill of materials.**
   `Na_ion` no longer exists as a chemistry here. **Solid-state is still
   `unknownBatteryMaterial` and still needs a source.**

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
12. **Stock-and-flow stage 04 is Matthias's own, and as of 2026-09-16 `04_04`
    exists with all the modelling.** Capacity per segment per year is answered
    there, per draw. **Nothing about it belongs in this file, and no analysis of
    it should be offered unless he asks.**

---

## 6. Where things are

| | |
|---|---|
| `scope.chemistries` | **the one list of the chemistries we calculate.** 05's files and every figure follow it; the per-chemistry settings are checked against it |
| `src/params_schema.py` | **the file to edit.** 127 settings, each with its own comment; `00_parameters.py` validates every one |
| `src/composition.py` | composition at any capacity, with uncertainty. `weights_at()` takes `year_factor_draws`; `element_draws_at()` returns the draws themselves |
| `src/ev_details.py` | the vehicle table: parsing, smoothing, the fitted curve. **`05` does not import it** — only `03_capacity_by_chemistry.py` does |
| `src/scenarios.py` | the three chemistry-share scenarios |
| `05_composition.py` | **the deliverable.** `apply_pack_rules()`, `fixed_capacity_rows()`, `improvement_factor_draws()`, `build_unknown_rows()` |
| `technology.mass_improvement_2070` | **the improvement, as a distribution** |
| `export.distribution_figure_year` | which year the distribution figures are for |
| `technology.structure_reference_chemistry` | sets the iron level for all nine |
| `technology.pack_voltages_v` / `copper_scale_by_voltage` | 400 V and 800 V |
| `technology.module_enclosure_split` | the 50/50 Al/Fe judgement |
| `export.unknown_chemistry_template` | what may be claimed about the one chemistry with no composition (solid-state), and why |
| `src/sodium_composition.py` | **the sodium cell model and its invariants**, read by both output paths of `05` |
| `src/unknown_chemistries.py` | what `05` and `02` share for every chemistry that is not in the workbook: the packaging claims, the drawn scale, the sodium inputs; and `CompositionWithCells`, which lets `02` draw the sodium cells, and its names-only `structure()`, which `01` draws from |
| `src/overview_figure.py` | the structure figure `01` draws: names only, each chemistry that has a composition against its parts and their elements |
| `drawing.overview_*`, `drawing.component_labels`, `drawing.component_gloss` | the structure figure's size, rows and every word in it |
| `technology.sodium_cell`, `technology.sodium_cathode` | every sodium input, each saying whether it is sourced, measured or assumed |
| `export.literature_chemistry_template` | the packaging claims of the two sodium cells |
| `export.capacity_scenario` | `saturate` / `grow_low` / `grow_high` |
| `technology.cell_density_override_wh_per_kg` | where the workbook's density is not believed — LMFP only |
| `data/raw/` | the two inputs — **not in git**, supplied via iCloud |
| `data/composition/` | `element_draws/` — generated by `05` |
| `data/consolidated/` | **the deliverable** — eight files in the workbook schema (two of them sodium cells built from literature, one solid-state with no composition) plus their draw arrays. **Your real folder also still holds 61 stale files each for `Na_ion`, LMO and NCA**, and `data/composition/element_draws/` 80 for LMO and NCA; `05` no longer writes them and does not clean up (§7, open) |
| `figures/` | 27 figures after `01`-`05` have run (1, 4, 2, 1 and 19) — generated |

**No data file is ever committed.** `data/` and `figures/` are excluded at the
folder, so a new output cannot slip through by having an extension nobody
listed.

---

## 7. Sodium-ion, built from literature (2026-10-02)

Sodium-ion had its packaging claimed from LFP and its cathode, anode and
electrolyte left as `unknownBatteryMaterial`, because no source existed. One
arrived on 2026-10-02 and two cells are now built from it. **They are a
scenario, not a bill of materials**: the report says in terms that no audited
whole-cell breakdown of a commercial sodium-ion cell is public, so nothing here
copies one.

### Words that were used for two things

| | means |
|---|---|
| **the workbook** | the WP3 lithium workbook in `data/raw/` -- the source of the lithium chemistries: seven in it, five calculated (`scope.chemistries`). Nothing else. |
| **the sodium sheet** | `documentation/Sodium_Ion_Battery_Cell_Composition.xlsx`. **Not data, and not used** (below). Ignored by git (`*.xlsx`). |
| **the report** / **the addendum** | `Sodium_Ion_Battery_CATL_Investigation.md` and `Sodium_Ion_Cathode_Capacity_Voltage_Addendum.md`, both in `documentation/` and committed. The report ranks every source by tier. |

### What exists

- **`Na_ion_layered` and `Na_ion_prussian_white`.** Each is one
  `consolidated_<name>.csv` plus 30 draw arrays and 30 name files, like every
  other chemistry. **`Na_ion` is gone**: removed on his instruction ("Na_ion is
  gone, we have now two chemistries") from the settings, `05`, the figures and the
  templates, having been kept unasked as a safeguard. What still carries the name
  is **61 stale files in `data/consolidated/`** from before the removal (under
  Open, below).
- **Packaging is claimed from LFP** (its casing, separator, collectors and pack
  hardware; Al replaces Cu on the anode collector at x0.4764 for equal
  conductance) -- which is what the old `Na_ion` claimed, and all it did.
- **Cathode, anode and electrolyte are an electrochemical mass balance**, in
  `src/sodium_composition.py`, read by both output paths of `05` so the CSV and
  the arrays cannot disagree:

      cell        = E / D                       D  cell energy density
      cathode     = E / (c * (Vc - Va))         c  mAh/g, Vc cathode V vs Na, Va anode potential
      anode       = (E / (Vc - Va)) / qa * NP   qa hard-carbon mAh/g, NP the N/P ratio
      electrolyte = e * kWh                     only the salt's Na, P, F are itemised
      remainder   = cell - cathode - anode - electrolyte - packaging

- **The remainder is a component of its own, `batteryCellUnitemised`**: cell mass
  the electrochemistry does not explain. It exists only for these two cells.
  Pouring it into the cathode and anode instead -- a split of the whole cell by
  lithium proportions -- put the cathode 27% too heavy.
- **Every input is a triangular drawn once per Monte Carlo draw** and shared by
  every capacity, year and row. `technology.sodium_cell` and `sodium_cathode`
  say, input by input, whether it is sourced, measured on the lithium workbook,
  or **assumed**.
- **Elements written:** layered `Al C Cu F Fe Mn Na Ni O P`; Prussian white
  `Al C Cu F Fe N Na P`. The rows carry `composition_status`
  `literature_scenario` and `unitemised_cell_mass`; the consolidated CSV has no
  status column, so there the remainder is recognised by its component name.

### Decided, and by whom

| decision | his words / what it rests on |
|---|---|
| Two full chemistries, separate compositions | "we need two full battery chemistries and compositions". NVP is excluded: research only. |
| **Where they go is 04_04's question, not the composition's** | Prussian white: stationary and AB cars. Layered oxide: CD, AB, perhaps EF. "CD-segment was more a guess, based on the Ni being critical and so expensive." |
| Prussian-white formula: ideal Na2Fe[Fe(CN)6] | "we have nothing else". Sodium drawn 1.5 / 2.0 / 2.0. |
| **200 Wh/kg kept** | "seen in some reports and presentations". The report cites 160 (2021) and 175 (2025); the code's 2020 value is above both. |
| Full Monte Carlo, 200,000 draws | said twice. Not 2,000, not a sensitivity note. |
| Layered nickel per formula unit Tri(2/9, 2/9, 0.33) | floor = HiNa's peer-reviewed post-mortem (Tier 1); **the top is weak** (the sodium sheet, and a lab O3 oxide). A nickel-free layered oxide (the addendum's HiNa) is **not** in this chemistry. |
| Negative-remainder draws conditioned out, not clipped | "1. to 3. seems to be OK" |
| LMFP lithium override dropped; pushed | "Yes, commit the LMFP change and push". The repository is **public**. |
| **`Na_ion` removed** | "Na_ion is gone we have now to chemistries!!" |
| **Sodium in the 04 scenarios is two chemistries, split by segment group** | "In 4 the sodium contribution is split into the two chemistries. AB uses prussin white and might go to 20% layor. CD is 50/50 and EF is only layor". Corrected: "NO increase until 2070 up to 20%" -- layered oxide in small cars rises until 2070, when it reaches 20% |
| **The structure figure shows every chemistry that has a composition, part by part, in plain words -- structure only** | "I want in this figure the chemistries, which we have the composition so one fully understands each of them ... Have the different components of the respective chemistiores." Of the legend: "Who the hell knows what the workbook is now?" Of its scope: "01 is draw battery structure and nothing else", then "yes, structure only". |

### What to know before reading a number

- **Conditioning is heavy, and it sits at 25 kWh.** About 9.4-9.7% of the layered
  and 18.3-18.8% of the Prussian-white draws are redrawn (measured at 2,000 and
  20,000 draws; it moves a little with the seed). At 80 kWh alone it is 0.5% and
  2.8%: the packaging taken from LFP is **0.84 kg/kWh at 25 kWh against 0.50 at
  80**, so a high density cannot close at small capacities. It moves an input's
  mean by at most about 1.5% and 2.2%. The cap is 30%, **a design bound I chose**.
  The density maximum of 220 is an assumption and is what decides this.
- **The remainder is large and is almost all cell density** (rank correlation
  -0.88 layered, -0.84 Prussian white): about 65 kg of 416 at 80 kWh in the proof,
  71 kg in the written file once every anchor is conditioned. The CSV's
  `Value` for it is every input at its mode, **52.9 kg against a median of 66.9**
  (layered, 80 kWh, 2020). Use the draws.
- **Layered-oxide nickel is 23.2 kg [19.4, 28.7] at 80 kWh in 2020**, the same order
  as a low-Ni NMC pack (27.2 kg) and half a mid-Ni one (43.6). The band is almost
  entirely the prior on the formula.
- **The cathode is about 160-180 kg at 80 kWh, not 203.** The lithium workbook's
  own LFP cathode stores 0.501 Wh/g, the same as the addendum's sodium figure.
- **The documents disagree.** The addendum corrects the report on HiNa's formula
  (no nickel, Tier 2-3, against the report's Tier-1 post-mortem with nickel),
  asserts a Naxtra Ni/Mn/Cu/Fe composition it does not source (the report says
  that ratio would be speculation), and gives Prussian-white capacity as 150-165
  mAh/g against the report's 100-150. **The sodium sheet is not data**: it labels a
  layered oxide "CATL 1st-gen", which the report contradicts; its sodium (3.59% of
  the cell) is half what its own cathode formula needs (7.13%); it has no
  source, basis or status columns.
- **Frame and enclosure iron still scale with the deterministic 200 Wh/kg**, while
  the drawn cell averages about 4% heavier (415.6 against 400 kg at 80 kWh). The
  structure does not follow the drawn density.
- **The hash seed is fixed.** `unknown_scale_draws` seeded with `hash(chemistry)`,
  which Python randomises per process (19, 697, 922 for `Na_ion` in three runs), so
  the same settings gave different packaging-trust draws. It is crc32 now: the
  draws of `Na_ion` and `solid_state` differ from every earlier run and are
  identical from here on (984 of 984 outputs byte-identical under two hash
  seeds). That exposed `check_unknown_draws_match_workbook`, which divided by the
  trust factor's analytic mean; it uses the realised mean now.

### Figures

`composition_over_time_<chemistry>_80kWh.png` for each cell, its total band taken
from the draws (adding percentiles is exact for the workbook's comonotonic
chemistries and wrong for independent inputs). The nickel, manganese, copper and
whole-battery distribution figures carry both cells as dashed lines, with a note
only where one is drawn. **`distribution_elements_<chemistry>_80kWh.png`**: every
element of one cell in a panel of its own, with its band.

**`battery_product_structure.png` is a different figure since 2026-10-02**, built
from scratch, and it is **structure only**: names, no weights, no ranges, no Monte
Carlo. One column per chemistry of `scope.chemistries` that has a composition (five lithium, two sodium),
one row per part, and in each box the chemical elements the data names for that
part ("not broken down" where the data does not split the part, a dash where the
chemistry has no such part). The parts and elements come from
`CompositionWithCells.structure` in `src/unknown_chemistries.py`: for lithium, off
the composition data; for a sodium cell, off its settings (the cathode formula, the
salt formula, hard carbon for the anode) and LFP's packaging with the template's
element swaps; and the enclosure is Al + Fe, as the pack rules make it. **It equals
the parts and elements `05` delivers for all seven** (checked against the
consolidated CSVs, not built from them), and `01` needs nothing from `05` or any
later step. It refuses a part it has no row for, and the settings refuse a start-up
in which a chemistry of `scope.chemistries` that has a composition is left out of
`drawing.overview_groups`, so a new one cannot be forgotten again. Its whole explanation is two short lines in
plain words, on his instruction.

**`02` now draws the two sodium cells** (`CompositionWithCells`, in
`src/unknown_chemistries.py`): a component figure for each cell, and both cells in
the totals figure, dashed. The blue diamonds on the cell figures are the masses in
the sodium sheet, an overlay for comparison -- **my reading of "use the different
reports and data for 02", unconfirmed.** `02` shows the values before the pack
rules, as it does for lithium; `05`'s are after them.

### The chemistries we calculate (2026-10-02)

**`scope.chemistries`** is the one list: `battLiFP_subsub`, `battLiMFP_subsub`,
`battLiNMC_lowNi`, `battLiNMC_midNi`, `battLiNMC_highNi`, the two sodium cells, and
`solid_state`. **LMO and NCA are in the lithium data and are not calculated**: not used
in EVs, his instruction. Solid-state is on the list and keeps all of its handling --
packaging only, no composition, `chemistries_without_composition` -- untouched.

What follows the list: the composition files `05` writes (8 CSVs, not 10), its
figures, `01`'s columns, `02`, and, by settings, `03` (NCA is out of
`ev_details.chemistry_groups` and its colours, and into
`chemistry_values_left_out`, which silences the report, so the NCA models in
`EV_details.csv` -- 28 of the 1,438 rows carry the label -- belong to no panel) and `04`
(NCA has no colour). `CompositionModel.chemistries()` and `Params.cells_in_scope()` /
`packaging_only_in_scope()` are how the code reads it. The settings refuse an entry in
`chemistry_energy_density`, `cell_to_pack_ratio` or `workbook_chemistry_colours` for a
chemistry that is not on the list, a listed chemistry with no energy density or colour,
and a workbook chemistry on the list that the data does not have.

**Nothing numerical changed for the chemistries that stay**: in the sandbox every
consolidated and composition file of the other eight is byte-identical to a run made
before the list existed; the model draws one random stream for all chemistries, so the
list filters what is enumerated, not what is drawn.

**One thing still reads every lithium chemistry in the data, on purpose**:
`lithium_cathode_range` in `src/unknown_chemistries.py` measures the lowest and highest
cathode energy per gram of the lithium chemistries as the reference the sodium
cathode's plausibility check is held against. It is a physical reference, not a list of
what we calculate; narrowing it to the list would tighten that check. `99` also
describes the whole of the data. **Stale in your real folders, not touched: the LMO,
NCA and `Na_ion` files above.**

### Verified, and not

In a sandbox at 2,000 draws, never against `data/` or `figures/`: against the
unmodified code **0 of 427 lithium files and 0 of 280 fraction arrays changed**;
the committed state, exported from the index and run alone, exits 0; **13 of 13**
deliberately broken inputs are refused (the invariants, the sampler, the
validator, and the drift check on both a cell and a packaging component). Those
proofs were run outside the repository -- there is no test suite here to hold
them. **Not verified: any run at 200,000 draws, and its time or memory.**

After `Na_ion` was removed, the structure figure rebuilt and the chemistry list added,
same sandbox: `05` exits 0; against a run made before any of the figure work, **every
file of the five lithium chemistries, the two sodium cells and solid-state is
byte-identical** -- 499 consolidated and 200 composition files now against 621 and 280,
and the 122 and 80 that are gone are exactly LMO's and NCA's. Of `05`'s 21 figures, the
two LMO and NCA composition-over-time figures are gone, six distribution figures changed
(they drew those lines) and 13 are identical. Run in the order 00, 01, 02, 03, 04, 05, 99
from an empty folder, **all exit 0**, and `01` draws first, in about 2 s, with nothing
from `05` there. `structure()` equals the parts and elements in what `05` delivers
**for all seven**. **6 of 6** deliberate tests of `01`'s inputs behaved (a part with no
row, a chemistry left out of the columns, a column for a chemistry that does not exist,
the composition data missing, an empty legend), and **8 of 8** of the list's: an empty
list, a chemistry named twice, an LMO entry left in the cell-to-pack settings, LMO
listed without its settings (refused by the figure's check, and by the coverage check
once the figure's check is satisfied), a chemistry the data does not have (the
settings cannot see the data; the model's `chemistries()` refuses it), and the model's
list coming out as the five lithium chemistries. `04`'s figure
differs from before the sodium work, deliberately (open item 1).

### Open, in the order I would take them

1. **04_04 (his).** The new file names; removing the name from
   `battery_chemistry_active_material_unknown` in RAWCLICStockAndFlow's
   `params_schema.py`; and reading the sodium share as two chemistries (below).
   **`Na_ion` has no composition file any more, so anything reading
   `consolidated_Na_ion.csv` finds only the 61 stale files until they are deleted or
   the reader is changed; `05` never cleans its output folder, and deleting them has
   not been asked.** In this repository the 04 scenarios now give sodium as the two
   chemistries, split by segment group from his words: A, B, JA, JB Prussian white,
   with layered oxide increasing until 2070, when it reaches 20% of the sodium; C, D,
   JC, JD half and half in every year; E, F, JE, JF layered oxide only. The total
   sodium share is unchanged (checked number by number against the old single
   series). **Open: the rise in small cars is a straight line from none in 2025 to 20%
   in 2070 (4.4% in 2035, 11.1% in 2050); that shape is my reading.**
2. **Recovery.** The recovery battery case has coefficients for Ni, Mn, Cu, Fe, C,
   Al, P and O and **none for Na, F or N**; the report has none for sodium-ion
   recycling, so a source is needed. The layered oxide puts nickel, copper and
   manganese back, which contradicts the stock-and-flow design note's
   "sodium-ion carries no critical or strategic raw material" (§3b of
   `DESIGN_chemistries_without_composition.md`) -- true only for Prussian white.
   That note is stage 04's and has not been touched.
3. **Stale in this repository, not fixed:** `README.md` (the `05` row still says
   "nine files" and that sodium-ion and solid-state are written with empty masses;
   only the `01` lines were corrected); `CHEMISTRY_OVER_TIME.md` (about lines
   218 and 293-294: "unknownBatteryMaterial ... for both chemistries");
   `METHODOLOGY.md` §6.4 and the sodium rows of §6.3 and its summary ("no
   composition at all"), its "Nine CSV files" and "104 parameters", and the status vocabulary at about line 385, which does
   not list `literature_scenario` or `unitemised_cell_mass`.
4. **Replace the four assumed inputs with sources**: N/P, the anode potential, the
   electrolyte maximum, and the density maximum of 220.
5. **Run `05` at 200,000 draws and time it.**
6. **The mutation tests are not in the repository.** Add them as a test file if
   wanted.
7. **The composition-over-time stack colours nickel a pale grey, nearly invisible
   against the band.** Not changed.
8. **The 02 figures.** "02 figures are shit" turned out to mean they showed the
   chemistries we exclude; that is fixed by the list. The comparison overlay on the sodium
   ones (the cell breakdown in the sodium spreadsheet) is still only my reading of "use
   the different reports and data for 02", unconfirmed.
