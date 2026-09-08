# Handover — RAWCLICVehicleBattery

Written 2026-09-07. State verified against the repository, not remembered:
every command below was run, and every claim about what does or does not exist
was checked with `git`.

---

## 1. Where things stand

Repository: <https://github.com/MattRoess/RAWCLICVehicleBattery>, public, branch
`main`, tracking `origin/main`.

| commit | what it did | pushed |
|---|---|---|
| `3ee3bba` | Composition at any capacity, with the Monte Carlo | yes |
| `f96951a` | Every setting moved into a parameter file; SVG output dropped | yes |
| `27a2e59` | The product-structure drawing | yes |
| `c513524` | Project set up for Positron | yes |

*Updated 2026-09-08:* the `ev_details` loose end recorded here is **closed** —
`src/ev_details.py` and `03_capacity_by_segment_over_time.py` now exist and run.
See §5.

Nothing under `data/` is tracked, and nothing ever should be. `git ls-files`
returns code and config only.

---

## 2. What runs today

```bash
cd "/Users/rm/Library/Mobile Documents/com~apple~CloudDocs/Documents/GitHub/RAWCLICVehicleBattery"
./.venv/bin/python 00_parameters.py                 # always first — regenerates and VALIDATES
./.venv/bin/python 99_check_environment.py          # smoke test
./.venv/bin/python 01_draw_battery_structure.py     # what a battery is made of
./.venv/bin/python 02_composition_by_capacity.py    # how much of it, at any capacity
```

All four were run and pass. Python 3.14.4 in `.venv`, pinned in
`requirements.txt`. Open the folder in Positron and the interpreter is already
selected (`.vscode/settings.json`).

| file | role |
|---|---|
| `src/params_schema.py` | **the file you edit.** 58 parameters, each with its own comment |
| `src/params_io.py` | writes `params.xlsx` (a report — nothing reads it) |
| `src/composition.py` | the model: composition at any capacity, with uncertainty |
| `data/raw/` | `BATT_consolidated_composition.xlsx`, `EV_details.csv` — supplied separately, never in git |
| `figures/` | every figure, all regenerable — `paths.output_dir` writes here, and only here |

### The public function

```python
from src.composition import CompositionModel
from src.params_schema import current

model = CompositionModel(current())
model.weights_at(150.0, chemistry="battLiNMC_midNi", level="component")
```

Any capacity in 10–200 kWh, any of the seven chemistries, at `component`,
`material` or `element` level. Returns mass in kg, kg/kWh, the Monte Carlo
percentile band, and an `extrapolated` flag. It refuses outside that range
rather than returning a number nobody should trust.

---

## 3. The data

**`BATT_consolidated_composition.xlsx`** — 7 sheets, 1,395 rows, all kg/kWh.
Five BEV sizes (25, 45, 60, 80, 100 kWh) are in scope; the HEV and PHEV sheets
are deliberately not. Twelve components on two branches: eight that exist once
per cell chemistry (7 chemistries), four that belong to the pack
(`Layer 1 = battPackXEV`) and are the same whatever chemistry is inside.
`parameterCode` gives the level: `c-p` component, `m-c` material, `e-c` element.

**`EV_details.csv`** — the EV-database scrape, 1,326 model variants × 144
columns, incomplete and still growing. Profiled but not yet used by any code.
See §5 and §6.

---

## 4. Decisions made, and why

These are the ones that would be expensive to rediscover.

**Interpolation is on MASS, not kg/kWh.** A part whose mass does not depend on
capacity — `currentCollectorAnode` on high-Ni is 21.4 kg at 25 kWh and 21.8 kg
at 100 — has an intensity that falls 0.86 → 0.22 kg/kWh purely because the
denominator grew. Interpolating that hyperbola mixes fixed-mass parts up with
the ones that really scale. Intensity is multiplied up to kilograms,
interpolated there, and divided back out. Verified: the five anchors come back
exactly, to 3×10⁻¹⁴ kg.

**Extrapolation is linear, always.** Whatever `interpolation_method` says. A
cubic continued past its last knot diverges, and at 150 kWh — half again beyond
the largest sheet — that is how a figure ends up with a negative cathode. Every
extrapolated row is flagged and the figures shade the region.

**⚠️ The ±10% band is a convention, not a measurement.** Every non-zero row of
the workbook has `min_value = 0.9 × Value` and `max_value = 1.1 × Value` — all
805 of them, whether the value was consolidated from 1 source or from 21, with
`DQS = 2` throughout. The Monte Carlo propagates that faithfully, so the band it
produces is the convention carried through the arithmetic and **not** evidence
about how well any of these numbers is known. A narrow band means the rule was
narrow. `_factor_bounds` in `src/composition.py` checks that proportionality
holds rather than assuming it, and raises if a future workbook carries a real
per-capacity range.

**Series are drawn independently of each other.** So the whole-pack band
(±3.4%) is narrower than any single component's ±10%. If component errors are
in fact correlated, that total band is too tight. No parameter exposes
cross-series correlation yet.

**⚠️ At element level the components do not add up.** A 150 kWh NMC battery
accounts for 626 kg at element level against 684 kg at component level — 8%
missing, silently, unless you look. **The attribution is not what it first
looks like**: `batteryCellElectrolyte` itemises only its lithium and so loses
99% of its own mass, which is the largest single term; `batteryCellCasing` and
`batteryCellSeparator` have no `e-c` rows at all; and `anodeActiveMaterial`'s
elements sum to 4% MORE than the component. About 13% of cell mass, on the
NMC high-Ni 60 kWh sheet. `02_composition_by_capacity.py` prints this
whenever `--level element` is used. This is the strongest argument for not
reading the product at element level alone.

**`batteryPackCellTerminals` is named for the pack but sits under the cell
chemistry** in `Layer 1`, so it scales with the chemistry mix, not with the
pack. Anything splitting the two branches by the component's *name* will get
this one wrong; split on `Layer 1` instead.

---

## 5. `ev_details` — capacity by segment over time

**Closed 2026-09-08.** `src/ev_details.py` parses the CSV and fits the curves;
`03_capacity_by_segment_over_time.py` draws them and prints the table. Only
segment and capacity over time is implemented — the other ~140 columns of the
CSV are untouched and for later.

```bash
./.venv/bin/python 03_capacity_by_segment_over_time.py
```

How it works, and the choices inside it:

- A variant counts in **every year its availability window covers**, so the
  series is "what was on sale", not "what launched".
- The curve is a **local linear regression with Gaussian weights** (LOESS in all
  but name), 2-year bandwidth, fitted to individual variants rather than yearly
  averages — capacity climbs and then flattens, and a straight line through that
  gets both ends wrong. Local *linear*, not a local mean, because a mean
  flattens the trend exactly at the ends of the range where the recent years are.
- **Two different bands, and they are not the same quantity.** The wide one is
  the market spread (p10–p90 of models actually on sale) — real dispersion, the
  same car sold with several pack sizes, and it does not shrink with more data.
  The narrow one is bootstrap uncertainty of the fitted curve, resampled over
  **models, never model-years**: a car on sale eight years is one observation of
  the market, not eight, and resampling years would collapse the band to nothing.
- A segment-year with fewer than `min_effective_models` nearby is left blank
  rather than drawn. That is why **JA is empty** — 2 models.
- `_parse_window` knows the six availability patterns that occur and **raises on
  a seventh** rather than guessing.

### Fitted capacity in 2026 against `battery_size_map`

| segment | fitted | map | gap | models |
|---|---|---|---|---|
| A | 28.1 | 25 | +12% | 31 |
| B | 43.0 | 45 | −4% | 68 |
| C | 62.7 | 60 | +4% | 101 |
| D | 77.6 | 80 | −3% | 100 |
| E | 85.8 | 80 | +7% | 81 |
| F | 100.3 | 100 | +0% | 134 |
| JB | 55.3 | 45 | **+23%** | 97 |
| JC | 72.5 | 60 | **+21%** | 266 |
| JD | 83.4 | 80 | +4% | 140 |
| JE | 99.2 | 80 | **+24%** | 61 |
| JF | 101.4 | 100 | +1% | 56 |

The plain A–F segments are close. The jellybean segments are not: JB, JC and JE
are 21–24% low, and JC is the most populous segment in the file at 266 models.

On the **nominal** basis — the one that matters for the composition — every
segment sits above the map, and the gaps widen: A +16%, B +2%, C +10%, D +2%,
E +14%, F +6%, JB +30%, JC +27%, JD +10%, JE +31%, JF +6%.

**These are models, not registrations**, and that is a known and accepted
trade-off rather than an oversight: detailed registration data exists only per
year, so this is the only source that runs back to 2015 at all. A segment with
many variants is still not a segment with many cars on the road, so a
sales-weighted version — using the EEA data the stock-and-flow model already
holds — would be the way to turn this into a `battery_size_map` revision.

### Chemistry split (`04_capacity_by_chemistry.py`)

Grouping, set in `ev_details.chemistry_groups`: **LFP**, **NCA**,
**NMC_middle** = NMC532/622, **NMC_high** = NMC712/721/811 *and every model
stating only `NMC` with no grade*.

**⚠️ That last clause decides most of the split** — 57% of 2026 models say only
`NMC`. It is the right guess for recent years (100 of 116 graded NMC models in
2026 are 811) and the wrong one for 2018–2021, when 622 dominated. Before about
2022, read `NMC_high` as "NMC, grade unknown".

Not covered by the rule and deliberately left out rather than forced into a
group: `NMC333` (5 models, all pre-2019 — graded, so not "ungraded", but neither
532/622 nor 712/721/811) and `LFP & NMC` (6 models, either-or per variant). A
further 174 models (14%) state no cathode at all. All three are reported on
every run.

Median nominal kWh, cells with ≥5 distinct models:

| seg | LFP | NCA | NMC_middle | NMC_high |
|---|---|---|---|---|
| A | – | – | – | 26.8 |
| B | 41.0 | – | 50.0 | 51.0 |
| C | 56.2 | – | 50.0 | 63.1 |
| D | 64.0 | 78.8 | – | 82.0 |
| E | – | – | – | 98.0 |
| F | – | 100.0 | – | 105.0 |
| JB | 50.0 | – | 50.0 | 58.3 |
| JC | 62.0 | – | – | 82.0 |
| JD | 75.8 | – | 90.0 | 92.0 |
| JE | 90.6 | – | 95.0 | 105.5 |
| JF | – | 100.0 | – | 110.3 |

**LFP is 15–25% smaller than NMC_high in every segment where both appear**, and
its share of models on sale went 0% → 18% between 2020 and 2026. So the
single-curve segment figure in `03` is a blend of two populations with different
means and a shifting mix — some of the flattening after 2023 is mix, not
technology. That is what this split is for.

On NCA: it **is** in the composition workbook (`battLiNCA_subsub`, a real NCA
cathode signature — Ni 0.709, Co 0.133, Al 0.020 kg/kWh, no Mn). It is finished
as a current chemistry — 26 models, only Tesla and Audi, 13.7% of models in 2019
down to 0.6% in 2026, and only 2 of the 26 still have an open availability
window. It stays relevant on the OUTFLOW side for a decade, since those
2019–2023 cars are the ones now entering the ELV stream. Worth knowing:
`battLiNCA_subsub` shares six of its eight cell-component values exactly with
`battLiMFP_subsub`, so the two are not independent evidence.

### What the profiling established

Run, verified, not yet in any script:

- **Availability parses cleanly.** `availability_json` holds United Kingdom, The
  Netherlands and Germany for all 1,316 models, in six patterns only:
  `MON YYYY - MON YYYY` (1,846), `Since MON YYYY` (1,544), `Not Available`
  (501), `Expected MON YYYY` (47), `Not available to order` (5), `MON YYYY` (5).
  First-availability year spans 2011–2027 and is filled for 99% of rows; 617 of
  1,326 models have no end date, i.e. are still on sale.
- **The segment codes match the stock-and-flow model's exactly** — A–F and
  JA–JF — plus `G`, `I` and `N - Passenger Van`, which have no entry in
  `battery_size_map`.
- **⚠️ The empirical capacities disagree with `battery_size_map`.** Median
  useable kWh against the map:

  | segment | map | median | n |
  |---|---|---|---|
  | A | 25 | 19.0 | 32 |
  | B | 45 | 41.0 | 79 |
  | C | 60 | 58.0 | 108 |
  | D | 80 | 77.0 | 104 |
  | E | 80 | 86.0 | 86 |
  | F | 100 | 96.5 | 136 |
  | JA | 25 | 42.5 | 2 |
  | JB | 45 | 50.8 | 105 |
  | JC | 60 | 74.2 | 284 |
  | JD | 80 | 83.6 | 146 |
  | JE | 80 | 94.8 | 65 |
  | JF | 100 | 96.0 | 57 |

  `JC` is the big one: 284 models, median 74 kWh against a map value of 60 —
  24% low, in the most populous segment. `JE` is 19% low. These feed straight
  into every battery mass the stock-and-flow model computes.
- **Capacity range**: median 75 kWh useable, 95th percentile 106.5, maximum 141.
  98 models above 100 kWh, only 5 above 120. So extrapolating to 150 kWh covers
  the real fleet rather than inventing a hypothetical one.
- **Useable vs nominal capacity differ by ~6%** (median ratio 0.944). Settled:
  the composition workbook is per **nominal**. Both bases are plotted, as
  separate figures, because they are different quantities — but only nominal
  may be multiplied by kg/kWh.

---

## 5b. Chemistry scenarios to 2070 (`05_chemistry_scenarios.py`)

**⚠️ Everything after 2026 is assumption.** The share numbers in
`scenarios.scenario_1/2/3` are a written-down judgement, not a result, and are
meant to be argued with. Both figures say so on their face.

| scenario | what it says | likelihood |
|---|---|---|
| S1 | LFP volume, NMC_high premium, LMFP growing, nothing new ever arrives | ~10% to hold unchanged to 2070; kept as the no-surprises reference |
| S2 | sodium enters small segments, **NMC shrinks to a niche** rather than disappearing | ~55% |
| S3 | S2 plus bipolar solid-state **from 2040**, large segments first | ~40% that solid-state is material by 2050; ~15% at this pace |

S2 was deliberately reframed from "NMC eliminated by 2035" — the least
defensible clause proposed, since Korean and European cell capacity is committed
to NMC and long-range premium demand does not vanish. Shrinking it to a few per
cent keeps the copper story, which is the point, without resting on a clause
likely to be wrong. LMFP was added to all three: it is **already in the
workbook** at 172 Wh/kg pack with no Ni or Co, so it fills the "LFP but denser"
role with no new assumptions.

The China assumption is built into the anchors, not modelled separately:
Chinese-built BEVs approaching half the EU market within a decade is what
carries LFP and then sodium into the mainstream this fast. If that stalls, every
LFP and Na trajectory here is too fast.

**⚠️ The coverage line is the most important thing on the sales figure.** The
stack is ordered so chemistries WITH a workbook composition sit at the bottom;
the black line is therefore the share whose material content can be computed at
all. It falls to 20–36% by 2070 under S3. Sodium-ion and bipolar solid-state
have no composition and are not variants of anything that does — sodium swaps
the copper anode collector for aluminium (~0.4 kg Cu/kWh, 55–59% of the pack's
copper), bipolar solid-state deletes the separator, the electrolyte and the
per-cell terminals. Those entries have to be supplied before any scenario
produces material mass.

### Second life, and the outflow lag

`06`-style outputs do not exist; the returning mix is the second figure from
`05`. A return year draws on two sales years at once:

    straight from the car   sold in Y − 15
    via second life         sold in Y − 15 − (15 to 20)

with `second_life.second_life_share` deciding how much of each chemistry is
diverted — **not all of it**: LFP 35%, LMFP 30%, Na 25%, NMC 10%, NCA 5%. That
parameter is a genuine unknown and the one most worth varying.

The consequence is the point: **in 2045 the large segments return 57% NMC_high
under S2 while only 17% is being sold.** The scenarios barely separate on
recovered material before about 2045, because everything coming back before then
is already on the road. An LFP-heavy scenario is also the one whose material
comes back latest.

⚠️ The returning mix assumes **constant annual sales volume** — only shares
exist in this project. Real volumes come from the stock-and-flow model, and
growth means the true return mix is somewhat more modern than shown.

## 5c. The composition files (`06_generate_composition_files.py`)

**One file per chemistry, one row per component/material/element, for ONE CAR**
of a given segment and year. Written to `data/composition/` (untracked), CSV.

```bash
./.venv/bin/python 06_generate_composition_files.py     # ~19 s
```

Seven files, ~4,200 rows each, plus `capacity_by_segment_year.csv`. Years 2020
to 2070 every five. Eleven segments — JA is absent because it has 2 models, too
few to fit a capacity.

**No chemistry mixing happens here, deliberately.** The scenario shares are
applied in the stock-and-flow model, where the fleet numbers are. This project
knows what a battery is made of; that one knows how many there are. Baking a
scenario into these files would tie them to an assumption they should outlive,
and as written the same files serve all three scenarios and any later one.

Columns: `chemistry, segment, year, level, layer1, branch, component, element,
capacity_kwh_nominal, capacity_is_projected, mass_kg, kg_per_kwh, extrapolated,
mass_p2.5, mass_p97.5, mass_mean`.

**⚠️ Capacity beyond 2026 is projected**, and every row says so in
`capacity_is_projected`. `export.capacity_projection` is `hold` by default — the
2026 fitted capacity carried forward unchanged — because capacity has been
flattening in most segments since 2023 and continuing a decade of growth for
another forty-four years would put C-segment cars well over 100 kWh with nothing
supporting it. `trend` is there to bound the other side.

**⚠️ Sodium-ion and solid-state are not written**, and the run says so rather
than substituting a lookalike.

## 6. Open questions, and who they are for

1. ~~Which kWh does the workbook mean?~~ **ANSWERED 2026-09-08: nominal.** The
   composition workbook's kg/kWh is per nominal capacity, so `weights_at()` must
   be fed nominal, and `ev_details.capacity_basis` defaults to `nominal` for
   that reason. Useable runs about 5% below nominal (0.937–0.969 by segment);
   feeding a useable figure in understates every mass by that much.
2. **Does mass really keep rising linearly above 100 kWh?** The straight line
   implies specific energy climbing to 219 Wh/kg at 150 kWh and 232 at 200. That
   is the weakest part of the extrapolation. A view on how pack mass actually
   scales belongs in the model rather than in a straight line.
3. **`battery_size_map`** — the table in §5 says it is wrong for several
   segments. Updating it is a change to RAWCLICStockAndFlow, not to this
   project, and it changes published results.

### Blocked in RAWCLICStockAndFlow

`code/04_04_batteries.py` still cannot run, for reasons that are not this
project's to fix:

- It wants `materials.battery_composition_parameter_code = "e-m"`, which **does
  not exist** in this workbook. The file offers `c-p`, `m-c` and `e-c`. Only
  `e-c` is complete; `m-c` covers just casing, separator and electrolyte, and
  with no `Layer 3` column it does not name its material. See §4 on the element
  gap before choosing.
- It expects one sheet named `BATT_EV_consolidated_inputForRM` and a `Layer 3`
  column. This workbook has seven size sheets and no `Layer 3`. A new loader is
  needed.
- `BATTKey_xEV_shares_final.xlsx`, the chemistry market shares, **is not
  anywhere on disk**. `EV_details.csv` carries `battery_cathode_material` and
  could be made to yield those shares by year — but by model count, not by
  registrations, so it would need weighting against the EEA data the
  stock-and-flow model already holds.

### Outstanding elsewhere

A repository audit on 2026-09-07 found data files in public repos, none of them
put there by this work and none yet cleaned up:

- `VehicleComposition` (public): 24 workbooks and a PDF, ~123 MB, including the
  JRC RMIS files.
- `RAWCLICRecoveryModel` (public): 35 csv/xlsx, ~1.4 MB.
- `RAWCLICVehicleElectronics` (public): 5 workbooks under `Consolidation/` — its
  `.gitignore` excludes `Data/`, and these sit outside it.
- `RAWCLICVehicleComposition` (private): `listing.csv` remains in history,
  deleted from the tree in commit `f37d8f3`.

Removing any of them means rewriting history and force-pushing, and
`git filter-repo` is not installed on this machine.
