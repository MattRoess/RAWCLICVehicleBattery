# Vehicle battery composition — what this project does, and what to trust in it

**RAWCLICVehicleBattery** turns two data files into the battery-composition
inputs for the RAWCLIC stock-and-flow model: what a battery is made of, for any
capacity, any of nine chemistries, any vehicle segment, any year to 2070.

This document is the whole story in one place — the data, the methods, the
decisions and their reasons, and every known gap. It is written to be read by
someone who did not build it.

*Written 2026-09-08. Every number in it was computed from the files described
here, not remembered.*

---

## 1. In one page

| | |
|---|---|
| **Inputs** | `BATT_consolidated_composition.xlsx` (what a battery is made of, per kWh) and `EV_details.csv` (1,326 real BEV variants: segment, capacity, chemistry, years on sale) |
| **Outputs** | Nine CSV files — one per chemistry — giving the material content of **one car's battery** for all **12 segments**, by year and level of detail, with Monte Carlo percentiles on every value |
| **Who splits the fleet** | Not this project. The chemistry mix is applied downstream in the stock-and-flow model, where the vehicle counts are |
| **Horizon** | 2020–2070, every fifth year |
| **The biggest caveat** | Two of the nine chemistries — sodium-ion and solid-state — have **no composition data at all**. Their files are written with every mass empty and marked `unknown` |

Run it:

```bash
./.venv/bin/python 00_parameters.py                 # always first — regenerates and validates settings
./.venv/bin/python 99_check_environment.py          # smoke test
./.venv/bin/python 01_draw_battery_structure.py     # what a battery is made of
./.venv/bin/python 02_composition_by_capacity.py    # how much, at any capacity
./.venv/bin/python 03_capacity_by_segment_over_time.py
./.venv/bin/python 04_capacity_by_chemistry.py
./.venv/bin/python 05_chemistry_scenarios.py
./.venv/bin/python 06_generate_composition_files.py # the deliverable
```

Every setting lives in `src/params_schema.py` — 104 parameters, each with a
comment saying what it does and whether it is safe to change. `00_parameters.py`
regenerates `params.xlsx` from it **and validates it**, so a bad edit surfaces in
a second rather than as a wrong answer.

---

## 2. The two input files

### 2.1 The composition workbook

`data/raw/BATT_consolidated_composition.xlsx` — 7 sheets, 1,395 rows, everything
in **kg per kWh**.

Five BEV sizes are in scope: 25, 45, 60, 80 and 100 kWh. The HEV (1 kWh) and
PHEV (20 kWh) sheets exist and are deliberately not used.

A battery is **twelve components on two branches**:

| branch | components |
|---|---|
| **Cell** — one set per chemistry | `cathodeActiveMaterial`, `anodeActiveMaterial`, `currentCollectorCathode`, `currentCollectorAnode`, `batteryCellElectrolyte`, `batteryCellSeparator`, `batteryCellCasing`, `batteryPackCellTerminals` |
| **Pack** — the same whatever chemistry is inside | `batteryPackSupportFrame`, `batteryPackThermalConductor`, `batteryPackModuleEnclosuresAndCoolantManifolds`, `batteryPackCables` |

Seven cell chemistries: LFP, LMFP, LMO, NCA, and NMC in low-, mid- and high-nickel.

Three levels of detail, in the `parameterCode` column:

- **`c-p`** — the component's whole mass. Complete: all twelve components.
- **`m-c`** — material level. Only three components: casing, separator, electrolyte.
- **`e-c`** — element level. Ten of twelve components; the `Layer 4` breakdown into Li, Ni, Co, Cu, Al, Fe, Mn, C, O, P, S, Si, V.

**Two quirks that will trip up anyone reading the file directly:**

1. `batteryPackCellTerminals` is *named* for the pack but sits under the **cell
   chemistry** in `Layer 1`, so it scales with the chemistry mix, not the pack.
   Anything that splits the two branches by the component's name gets this wrong.
   Split on `Layer 1` instead.
2. The file writes a literal `n/a` in `Layer 4`. Read with pandas' defaults that
   becomes `NaN`, and the three levels of detail stop being distinguishable. Every
   loader here passes `keep_default_na=False`.

### 2.2 The vehicle table

`data/raw/EV_details.csv` — the EV-database scrape: 1,326 model variants,
144 columns. Incomplete and still growing. This project uses five of those
columns: segment, nominal capacity, useable capacity, cathode material and
availability dates.

Availability is free text per country — United Kingdom, Netherlands and Germany
for every model — in exactly **six patterns** across all 3,948 entries:
`MON YYYY - MON YYYY` (1,846), `Since MON YYYY` (1,544), `Not Available` (501),
`Expected MON YYYY` (47), `Not available to order` (5), `MON YYYY` (5). The
parser knows those six and **raises on a seventh** rather than guessing.

Segments use the same A–F and JA–JF codes as the stock-and-flow model, plus
`G`, `I` and `N - Passenger Van`, which that model has no size for.

---

## 3. Composition at any capacity

The workbook gives five sizes. `src/composition.py` gives every capacity from 10
to 200 kWh.

### 3.1 It interpolates mass, not kg/kWh — and this is the important choice

kg/kWh is the wrong thing to interpolate. A part whose mass does not depend on
capacity — `currentCollectorAnode` on high-nickel NMC is 21.4 kg at 25 kWh and
21.8 kg at 100 kWh — has an *intensity* that falls from 0.86 to 0.22 kg/kWh
purely because the denominator grew. Interpolating that hyperbola mixes
fixed-mass parts up with the ones that genuinely scale.

So the intensity is multiplied up to kilograms, interpolated there, and divided
back out. In kilograms the three real behaviours stay distinct:

| behaviour | example | 25 → 100 kWh |
|---|---|---|
| strictly proportional | `cathodeActiveMaterial` | 1.5617 kg/kWh at every size |
| fixed mass | `currentCollectorAnode` (high-Ni) | 21.4 → 21.8 kg |
| in between | `batteryPackSupportFrame` | 64 → 95 kg |

100 of the workbook's 199 series are strictly proportional; the other 99 have a
fixed-mass component.

**Verified**: feeding the model one of the five anchor capacities returns the
workbook's own numbers to 3×10⁻¹⁴ kg.

### 3.2 Between the anchors: shape-preserving. Beyond them: a straight line

Between 25 and 100 kWh the curve is a PCHIP interpolation — monotone where the
data is, and unable to overshoot into a bump the anchors do not support.

**Beyond 100 kWh it is always linear**, whatever the interpolation setting says.
A cubic continued past its last knot diverges; at 150 kWh, half again beyond the
largest sheet, that is how a figure ends up with a negative cathode. Linear is
not a claim that the trend continues — it is the least the data can be made to say.

Every extrapolated row is flagged (`extrapolated` column) and the figures shade
the region. **Read the extrapolation as a straight line's opinion, not as data.**

A sanity check worth doing: a straight line in mass means specific energy keeps
improving with size — 199 Wh/kg at 100 kWh, 219 at 150, 232 at 200 (pack level).
That is an assumption the workbook never made.

### 3.3 The ±10% band is a convention, not a measurement

**Every non-zero row of the workbook has `min_value = 0.9 × Value` and
`max_value = 1.1 × Value`** — all 805 of them, whether the value was consolidated
from 1 source or from 21, with `DQS = 2` throughout.

So the spread is a flat ±10% rule, not an observed range. The Monte Carlo
(20,000 draws, triangular, seeded) propagates it faithfully — which means **the
band is that convention carried through the arithmetic, and not evidence about
how well any of these numbers is known.** A narrow band here means the rule was
narrow.

Two mechanics worth knowing:

- **One draw per series, shared across capacities.** A component's error does not
  change between 60 and 61 kWh. Drawing each anchor independently would put kinks
  in a smooth curve and shrink the band by averaging errors that are the same
  error. The code *checks* the workbook's band really is proportional and raises
  if it ever stops being.
- **Series are drawn independently of each other**, so the whole-pack band
  (±3.4%) is narrower than any single component's ±10%. If component errors are
  in fact correlated, that total band is too tight.

### 3.4 ⚠️ Feed it nominal capacity

The workbook's kg/kWh is per **nominal** kWh — the pack's gross, stated figure —
not useable. Useable runs 0.937–0.969 of nominal depending on segment. A useable
figure passed in returns about 5% too little of everything, silently.

### 3.5 ⚠️ Element level does not add up to component level

At element level a 150 kWh NMC battery accounts for **626 kg against 684 kg** at
component level — 8% missing. The attribution is not the obvious one:

| component | lost at element level | why |
|---|---|---|
| `batteryCellElectrolyte` | **99% of its own mass** | only its lithium is itemised |
| `batteryCellCasing` | 100% | no element rows at all — its materials are now known (40% Al, 60% plastics) but `plastics` is not an element, so only the aluminium could ever be resolved here |
| `batteryCellSeparator` | 100% | no element rows at all |
| `anodeActiveMaterial` | −4% | C plus Si *exceed* the component total |

The electrolyte is by far the largest term. About 13% of cell mass overall.
`02_composition_by_capacity.py --level element` computes and prints this
attribution on every run.

**This is the strongest argument for not reading the product at element level
alone.** The output files carry component, material and element levels precisely
so the gap is visible rather than inferred.

---

## 4. What real cars actually carry

### 4.1 Capacity by segment and year

`03_capacity_by_segment_over_time.py` fits capacity against year, per segment,
from the vehicle table. A variant counts in **every year its availability window
covers**, so the series is "what was on sale", not "what launched".

**The curve is not a straight line, deliberately.** Capacity climbs through the
early 2020s and then flattens — C goes 22 → 63 kWh, JC 49 → 72 and levels off
after 2023, E is flat throughout. A line through that gets both ends wrong. What
is fitted is a local linear regression with Gaussian weights (LOESS in all but
name, 2-year bandwidth), on individual variants rather than yearly averages, so a
year with forty models counts for more than one with four. Local *linear* rather
than a local mean, because a mean flattens the trend at the ends of the range —
which is exactly where the recent years are.

**Two bands, and they are different quantities:**

- **Market spread** (p10–p90 of models on sale) — real dispersion. The same car
  sold with several pack sizes: 84 Tesla Model variants from 49 to 98 kWh, 25
  Hyundai IONIQs from 28 to 106. It does **not** shrink as more data arrives, and
  it is much the larger of the two.
- **Curve uncertainty** — how far the fitted line would move on a different
  sample of models. Bootstrapped over **models, never model-years**: a car on sale
  eight years is one observation of the market, not eight.

A segment-year with too few models nearby is left blank rather than drawn. JA
has 2 models and is absent throughout.

### 4.2 ⚠️ The stock-and-flow model's `battery_size_map` disagrees with reality

Fitted **nominal** capacity in 2026 against what that model assumes:

| segment | fitted | map | gap | models |
|---|---|---|---|---|
| A | 29.0 | 25 | +16% | 31 |
| B | 45.9 | 45 | +2% | 68 |
| C | 66.1 | 60 | +10% | 101 |
| D | 81.2 | 80 | +2% | 100 |
| E | 90.9 | 80 | +14% | 81 |
| F | 106.1 | 100 | +6% | 134 |
| JB | 58.4 | 45 | **+30%** | 97 |
| JC | 76.4 | 60 | **+27%** | 266 |
| JD | 87.6 | 80 | +10% | 140 |
| JE | 104.5 | 80 | **+31%** | 61 |
| JF | 105.9 | 100 | +6% | 56 |

Every segment sits above the map. JC is the most populous segment in the file,
assumed at 60 kWh against a fitted 76.

**These are models, not registrations** — an accepted trade-off, since detailed
registration data exists only per year and this is the only source running back
to 2015. A segment with many variants is not a segment with many cars on the
road. **Weighting by sales — using the EEA data the stock-and-flow model already
holds — should come before that map is revised on this evidence.**

### 4.3 Chemistry

The file states a cathode material for 86% of models. It is grouped as:

| group | includes |
|---|---|
| LFP | `LFP` |
| NCA | `NCA` |
| NMC_middle | `NMC532`, `NMC622` |
| NMC_high | `NMC712`, `NMC721`, `NMC811`, **and every model stating only `NMC`** |

**⚠️ That last clause decides most of the split** — plain `NMC` with no grade is
57% of 2026 models. Sending it to high-nickel is right for recent years (100 of
116 graded NMC models in 2026 are 811) and wrong for 2018–2021, when 622
dominated. **Before about 2022, read `NMC_high` as "NMC, grade unknown".**

Left out rather than forced into a group: `NMC333` (5 models, all pre-2019 —
graded, so not "ungraded", but neither 532/622 nor 712/721/811) and `LFP & NMC`
(6 models, either-or per variant). With the 174 models stating no cathode at all,
**15% of models appear in no chemistry result**. This is reported on every run.

**LFP runs 15–25% below NMC_high in every segment where both appear** — JC is the
sharpest, 62 against 82 kWh — and LFP went from 0% to 18% of models on sale
between 2020 and 2026. So a single capacity curve per segment is a blend of two
populations with different means and a shifting mix: **some of the flattening
after 2023 is chemistry mix, not technology.**

NCA is finished as a current chemistry: 26 models, only Tesla and Audi, 13.7% of
models in 2019 down to 0.6% in 2026, and only 2 of the 26 still on sale. It
remains relevant on the **outflow** side for a decade, since those 2019–2023 cars
are the ones now entering the ELV stream.

---

## 5. Scenarios to 2070

**⚠️ Everything after 2026 is assumption. The observed record ends there.** The
share numbers are a written-down judgement in `src/params_schema.py`, meant to be
argued with, and both figures say so on their face.

| | what it says | likelihood |
|---|---|---|
| **S1** | LFP volume, NMC_high premium, LMFP growing, nothing new ever arrives | ~10% to hold unchanged to 2070; kept as the no-surprises reference |
| **S2** | sodium enters the small segments, **NMC shrinks to a niche** | ~55% |
| **S3** | S2 plus bipolar solid-state **from 2040**, large segments first | ~40% that solid-state is material by 2050; ~15% at this pace |

S2 was deliberately written as "NMC becomes a niche" rather than "NMC is
eliminated by 2035": Korean and European cell capacity is committed to NMC and
long-range premium demand does not vanish. Shrinking it to a few per cent keeps
the material story — sodium's aluminium anode collector removing more than half
the pack's copper — without resting on the clause most likely to be wrong.

LMFP is in all three. It is **already in the workbook** at 172 Wh/kg pack with no
nickel or cobalt, so it fills the "LFP but denser" role with no new assumption
and no new data.

**The China assumption is built into the anchors**, not modelled separately:
Chinese-built BEVs approaching half the EU market within a decade is what carries
LFP and then sodium into the mainstream this fast. If that share stalls, every
LFP and Na trajectory is too fast and the NMC ones too slow.

### 5.1 Second life, and the outflow lag

This is where the scenarios matter for a recycling model — and where the
intuition inverts.

A return year draws on **two** sales years at once:

```
straight from the car    sold in Y − 15
via second life          sold in Y − 15 − (15 to 20)
```

`second_life.second_life_share` decides how much of each chemistry is diverted —
**not all of it**: LFP 35%, LMFP 30%, Na 25%, NMC 10%, NCA 5%. LFP is highest
because it is what stationary storage wants and what is worth least as scrap. That
parameter is a genuine unknown and the one most worth varying.

The consequence: **in 2045 the large segments return 57% NMC_high under S2 while
only 17% is being sold.** The scenarios barely separate on recovered material
before about 2045, because everything coming back before then is already on the
road. And an LFP-heavy scenario is the one whose material comes back *latest*.

⚠️ The returning mix assumes **constant annual sales volume** — only shares exist
in this project. Real volumes come from the stock-and-flow model, and growth means
the true return mix is somewhat more modern than shown.

---

## 6. The output files

`data/composition/`, CSV, regenerated by `06_generate_composition_files.py` in
about 20 seconds.

**Nine files, one per chemistry. Each row is ONE CAR** — the material in a single
battery of that segment, year and chemistry. Multiply by vehicle counts
downstream; never by a chemistry share here.

```
chemistry, segment, year, level, layer1, branch, component, element, material,
capacity_kwh_nominal, capacity_is_projected, mass_kg, kg_per_kwh, extrapolated,
mass_p2.5, mass_p97.5, mass_mean, composition_status, note
```

**All 12 segments** × 11 years (2020–2070, every fifth) × three levels, and
**Monte Carlo percentiles on every computed value** (`mass_p2.5`, `mass_p97.5`,
`mass_mean` — 100% populated wherever a mass exists).

`capacity_source` says where each segment's capacity came from:

| value | meaning |
|---|---|
| `fitted` | the smoothed curve from `03` — 11 segments |
| `segment_median` | too few models to fit; the median of that segment's own cars. **JA only**: two Hyundai INSTER variants at 42 and 49 kWh, median 45.5 |
| `reference_map` | last resort, `battery_size_map`, for a segment with no models at all. Currently unused |

JA is worth a note: `battery_size_map` puts it at 25 kWh, against 45.5 for the
two cars that actually exist in it. The thin real data is the better source.

**No chemistry mixing happens here, by design.** The scenario shares are applied
in the stock-and-flow model, where the fleet numbers are. This project knows what
a battery is made of; that one knows how many there are. Baking a scenario into
these files would tie them to an assumption they should outlive — as written, the
same nine files serve all three scenarios and any later one.

### 6.1 What `composition_status` tells you

| value | meaning |
|---|---|
| `from_workbook` | a real number from the composition workbook |
| `material_known_split_unknown` | the materials are named but the split between them is not — mass empty. **Currently unused**: the only such case, the cell casing, now has its split |
| `unknown` | the chemistry has no composition at all — every mass empty |

### 6.2 ⚠️ Capacity beyond 2026 is projected

The fitted nominal capacity per segment is real data to 2026. Beyond that,
`export.capacity_projection` decides: `hold` (the default) carries the 2026 figure
forward unchanged; `trend` continues the gradient. **Every row carries
`capacity_is_projected`**, so the two cannot be confused. Of a typical file's
4,356 rows, 792 are observed and 3,564 projected.

`hold` is the default because it assumes least: capacity has been flattening in
most segments since 2023, and continuing a decade of growth for another 44 years
would put C-segment cars well over 100 kWh with nothing supporting it.

### 6.3 Range saturation: where a solid-state pack's capacity comes from

Once energy density stops binding, a battery is no longer as big as you can
afford to carry. There is no point carrying range nobody drives, so the pack is
sized for a **range target** and every further gain in density shows up as
**less mass**. `technology.range_saturation_km` is the input; the mass saving is
what falls out of it. Setting both would be over-determined, and the range is
the half with a physical argument behind it.

**The settled assumption is 600 km at 500 Wh/kg pack**, and the reason is
charging speed rather than range. A cap only bites if it sits below where the
market would otherwise go — and today's median real range is already ~490 km.
A 1200 km target would not restrain anything; it would mandate a 2.4× increase
and produce 233 kWh packs, 65% larger than anything in the vehicle table. At
350 kW a 600 km car refills in about fifteen minutes, which is why real ranges
have plateaued at 400–600 km rather than climbing: **it is cheaper to charge
faster than to carry more.** Fast charging substitutes for capacity, and that
substitution is what makes the material saving real.

**⚠️ Energy density is a trajectory, and its basis is CELL.** Two things were
conflated in an earlier version of this document and both mattered:

- **Cell or pack.** Solid-state figures in the press are cell figures. Today's
  packing ratio in this workbook is 0.59 (NMC high-Ni) to 0.69 (LFP) — a 356
  Wh/kg cell gives a 211 Wh/kg pack. Bipolar stacking should do better, having no
  per-cell terminals and less module hardware, so **0.80** is assumed.
- **It is not one number.** The first solid-state cells are around 400 Wh/kg and
  500–600 follows. A chemistry entering in 2040 and still being built in 2070 does
  not have one density for thirty years.

The assumed trajectory, and what it does to a JC pack (94 kWh at a 600 km target,
against today's 399 kg):

| year | cell Wh/kg | pack Wh/kg | pack mass | vs today |
|---|---|---|---|---|
| 2040 | 400 | 320 | 294 kg | 0.74× |
| 2050 | 500 | 400 | 236 kg | 0.59× |
| 2060 | 600 | 480 | 196 kg | 0.49× |
| 2070 | 600 | 480 | 196 kg | 0.49× |

So the saving **arrives gradually**: about a quarter off when solid-state enters,
reaching a half only once cells reach 600 Wh/kg. An earlier version of this
document assumed a flat 500 Wh/kg *pack* — equivalent to a 625 Wh/kg cell from
day one — and overstated the early saving by a third.

Pack mass relative to today at a 600 km target, fleet mean over the twelve
segments, by **pack** Wh/kg:

| pack Wh/kg | **600 km** | 800 km | 1000 km | 1200 km | 1500 km |
|---|---|---|---|---|---|
| 400 | 0.60 | 0.80 | 1.00 | 1.19 | 1.49 |
| 480 *(2060+, from a 600 Wh/kg cell)* | **0.50** | 0.67 | 0.83 | 1.00 | 1.24 |
| 400 *(2050, from a 500 Wh/kg cell)* | 0.60 | 0.80 | 1.00 | 1.19 | 1.49 |
| 320 *(2040, from a 400 Wh/kg cell)* | 0.75 | 1.00 | 1.25 | 1.49 | 1.86 |
| 500 | 0.48 | 0.64 | 0.80 | 0.96 | 1.19 |
| 600 | 0.40 | 0.53 | 0.66 | 0.80 | 1.00 |
| 700 | 0.34 | 0.46 | 0.57 | 0.68 | 0.85 |
| 800 | 0.30 | 0.40 | 0.50 | 0.60 | 0.75 |

**Rule of thumb: mass vs today ≈ 0.40 × (range km ÷ pack Wh/kg).** It reproduces
every cell above, and lets any other pair be checked without rerunning anything.

Under the default, solid-state packs run **79 kWh in A to 116 kWh in JF**. At
first-generation density (2040, 400 Wh/kg cell) that is 165–243 kg, **0.40× to
0.67× today's mass**; by 2060 at 600 Wh/kg cell it is a third lower again. Those capacities sit
inside the range of packs already on sale, which a 1200 km target did not.

Three things this exposes, all of which survived the change of target:

- **The two halves of the original proposal cannot both hold.** A third off the
  material and a 1000–1500 km range are mutually exclusive: at 1200 km, 500 Wh/kg
  gives 0.96× — no saving — and a third off would need ~717 Wh/kg pack. At
  1500 km it would need ~900 Wh/kg, beyond any lithium chemistry.
- **⚠️ The cell-to-pack ratio is not a detail.** At 0.70 rather than 0.85, a
  600 Wh/kg cell gives 420 rather than 510 Wh/kg pack — 0.57× against 0.47× of
  today's mass. The 0.80 assumed here is itself a guess about bipolar packaging.
- **Segment A saves least, always** — 0.64× here, and it is the only segment that
  ever goes *above* 1.0 at longer targets. A small car carrying a long-range pack
  is always a battery out of proportion to itself.

The consumption figures are **mild-weather** medians of models introduced from
2022 (132 Wh/km in A to 194 in JF). The cold-weather column is about 35% higher,
which is equivalent to cutting density by a quarter: a 600 km pack sized for
January is a third bigger.

Those rows carry `pack_mass_kg_implied` — **a whole-pack figure, not a
composition.** No component's mass is stated, because none is known.

### 6.4 ⚠️ Sodium-ion and solid-state have no composition

They are written anyway — with the expected row skeleton, **every mass column
empty**, and `composition_status = "unknown"`. A missing file is easy to overlook
downstream; a file of blanks is not, and the stock-and-flow model can carry the
chemistry through and see the gap arrive rather than silently dropping that share
of the fleet.

**They are not variants of anything in the workbook.** The component list itself
changes:

- **Sodium-ion** replaces the copper anode current collector with **aluminium** —
  sodium does not alloy with aluminium at low potential, which is precisely why it
  is cheaper. That single swap is ~0.4 kg Cu/kWh, **55–59% of the pack's entire
  copper**. The pack *cables* stay copper: the swap is scoped to the collector.
- **Bipolar solid-state** deletes the separator, the liquid electrolyte and the
  per-cell terminals outright, and puts lithium or sodium metal where graphite was.

The skeleton is the only thing asserted about them. Outside the components each
template explicitly claims, the element reads **`unknown`** rather than the base
chemistry's — borrowing a component list is not knowing what the cathode is made
of, and a row reading `Fe` for a sodium cathode would be a claim nobody made,
empty mass or not.

---

## 7. Every known gap, in one list

| gap | size | where |
|---|---|---|
| Sodium-ion has no composition | whole chemistry | §6.3 |
| Bipolar solid-state has no composition | whole chemistry | §6.3 |
| Element level does not sum to component level | ~13% of cell mass, mostly the electrolyte | §3.5 |
| `plastics` in the cell casing has no element breakdown (needs C/H/O) | ~0.05 kg/kWh, the 60% plastics share | §3.5 |
| The ±10% uncertainty is a convention, not a measurement | all of it | §3.3 |
| Capacity beyond 2026 is projected | 82% of exported rows | §6.2 |
| Everything after 2026 in the scenarios is judgement | all of it | §5 |
| 15% of vehicle models appear in no chemistry group | 185 of 1,244 | §4.3 |
| Plain `NMC` (57% of 2026 models) has no stated grade | most of the NMC split | §4.3 |
| Models, not registrations | all vehicle-table results | §4.2 |
| Returning mix assumes constant sales volume | all outflow results | §5.1 |
| Cross-component error correlation not modelled | pack-level band too tight | §3.3 |
| A third off the material and a 1000–1500 km range are mutually exclusive | at 1200 km, 500 Wh/kg saves nothing | §6.3 |
| JA's capacity rests on two cars | 1 of 12 segments | §6 |
| 500 Wh/kg at cell rather than pack level would nearly erase the saving | 0.81–1.34× today instead of 0.61–1.07× | §6.3 |

None of these is hidden in the code. Each is printed at runtime, marked in a
column, or stated on the figure that depends on it.

---

## 8. Open questions

1. **Is the 500 Wh/kg solid-state figure cell or pack?** It decides whether the
   material saving is a quarter or nothing (§6.3).
1. **The cell-to-pack ratio for a bipolar solid-state pack.** 0.80 is assumed
   against today's 0.59–0.69; the plausible range moves the answer by ~20%.
2. **Compositions for sodium-ion and bipolar solid-state** — including which
   components cease to exist, not just new numbers.
3. **Does pack mass really keep rising linearly above 100 kWh?** The straight line
   implies specific energy climbing to 219 Wh/kg at 150 kWh. This is the weakest
   part of the extrapolation.
4. **Should `battery_size_map` be revised?** §4.2 says it is low for every
   segment, but by models rather than registrations. That is a change to the
   stock-and-flow model and it moves published results.
5. **Sales weighting.** Joining the vehicle table to EEA registrations would turn
   every "share of models" result here into a share of cars.

---

## 9. Where things are

| | |
|---|---|
| `src/params_schema.py` | **the file to edit.** 104 settings, each with its own comment |
| `src/composition.py` | composition at any capacity, with uncertainty |
| `src/ev_details.py` | the vehicle table: parsing, smoothing, bootstrap |
| `src/scenarios.py` | the three scenarios and the returning mix |
| `src/params_io.py` | writes `params.xlsx` (a report — nothing reads it) |
| `data/raw/` | the two inputs, supplied separately |
| `data/composition/` | the nine output files |
| `figures/` | all eight figures |

**No data file is ever committed to git.** `data/` and `figures/` are excluded at
the folder, so a new output cannot slip through by having an extension nobody
listed. A fresh clone gets the code only and needs `data/raw/` supplied
separately.

Environment: Python 3.14.4, pinned in `requirements.txt`. Open the folder in
Positron and the interpreter is already selected.
