# How the chemistries develop over time

What changes, year by year, in a battery of a given capacity — and what does
not. Written so the behaviour can be understood without reading the code.

*Written 2026-09-14. Every number here was computed from the parameters and the
outputs, not remembered.*

---

## 1. The one-paragraph answer

Hold the capacity fixed and only **one thing** moves with the year: the same kWh
needs less material as the cell improves. That improvement is **not a number**,
it is a drawn distribution, and it is the reason the uncertainty band widens the
further out you look. Everything else — which chemistry, what the pack is made
of, how the structure is sized — is a property of the chemistry, not of the year.

---

## 2. What moves with the year, and what does not

| | moves with the year? |
|---|---|
| Mass of every component and element | **yes** — through the improvement |
| Width of the uncertainty band | **yes** — it grows; see §4 |
| Which chemistry a car carries | yes, but **not here** — that is the scenario mix, §7 |
| Cell chemistry's composition (what an NMC cathode is made of) | no |
| Structure-to-cell ratio | no — a property of the chemistry, §5 |
| Thermal conductor, cables | no — sized by capacity, §6 |
| Capacity itself | **not in this project** — a fleet question, §8 |

---

## 3. The improvement: one distribution, drawn once

`technology.mass_improvement_2070` = **triangular, min 0.15 / mode 0.20 /
max 0.30**, ramping linearly from zero in 2020 (`improvement_from_year`) to full
effect in 2070 (`improvement_to_year`).

Read it as: *by 2070 the same kWh needs about 20% less material, and might need
as little as 15% less or as much as 30% less.*

Three properties matter and each was a deliberate choice:

**It is drawn once per Monte Carlo draw and shared by every component, element
and year.** This is one uncertainty about the technology, not an independent
error per row. Drawn per row it would cancel in any sum and a whole-pack total
would come out falsely certain.

**It multiplies the draws, before any percentile is taken.** Applied to a
finished percentile instead it would slide the band without widening it — which
is exactly what the consolidated files did until 2026-09-14, showing a flat
15.5% band in every year while the draws behind them widened to 22.1%.

**It is asymmetric, and that is the spec.** Mode-to-max is 0.10 against 0.05
from min-to-mode: the improvement can beat expectations by twice as much as it
can disappoint. So the band around a future mass is skewed, and the mass can
come out lower more easily than higher.

### The consequence: `Value` and `meanValue` are not the same number

`Value` is the central estimate and takes the improvement's **mode**.
`meanValue` is the **mean of the draws**. A skewed triangular has mean ≠ mode,
so the two diverge as the year advances. Measured on `battLiNMC_midNi`,
80 kWh, 400 V, total pack:

| year | `Value` | `meanValue` | gap |
|---|---|---|---|
| 2020 | 371.61 kg | 371.61 kg | 0.00% |
| 2045 | 334.45 kg | 331.38 kg | +0.93% |
| 2070 | 297.29 kg | 291.14 kg | +2.11% |

Both are correct; they are different statistics of the same distribution.
Collapsing them would hide the skew.

---

## 4. Why the band widens — and why that is intentional

The further into the future, the less is known about how much better cells will
get, so the spread around the answer grows. The composition's own uncertainty is
fixed; the improvement's is not, and it accumulates with the year.

Measured on nickel, `battLiNMC_midNi` 80 kWh 400 V — the p2.5–p97.5 width as a
percentage of the central:

| year | band |
|---|---|
| 2020 | 15.5% |
| 2035 | 15.8% |
| 2050 | 17.4% |
| 2070 | **22.1%** |

Every chemistry behaves the same way — 15.5% → 22.1% by 2070 in all seven
workbook chemistries, and in sodium and solid-state too.

At 2020 the improvement is zero by construction, so the band is the workbook's
own composition uncertainty alone. Everything above 15.5% is the technology
uncertainty being carried, not composition noise.

> **What the band still does not carry.** Uncertainty about the *projection
> itself*. In kilograms it narrows before it widens, because the composition
> band shrinks with the falling mass while the improvement's own spread barely
> outruns it. A 2070 pack is therefore drawn as almost as well known as a 2020
> one, which it is not. Raised 2026-09-10, not decided.

---

## 5. Cell density, and why the structure follows the cells

### The densities

`technology.chemistry_energy_density`, **cell level**, Wh/kg:

| chemistry | 2020 | 2070 |
|---|---|---|
| `Na_ion` | 200 | 250 |
| `battLiMO_subsub` | 231 | 289 |
| `battLiFP_subsub` | 233 | 291 |
| `battLiMFP_subsub` | 270 | 338 |
| `battLiNMC_lowNi` | 285 | 356 |
| `battLiNCA_subsub` | 306 | 382 |
| `battLiNMC_midNi` | 311 | 389 |
| `battLiNMC_highNi` | 339 | 424 |
| `solid_state` | 400 | 500 |

> **⚠️ The 2070 endpoints are decorative for mass.** Every mass trajectory comes
> from the improvement in §3, not from these numbers. Change a 2070 endpoint and
> no mass will follow it. The **2020** values are real and do work: they set the
> structure ratio below.

### The structure ratio

The workbook gives every chemistry the *same* iron at a given capacity. That put
the same frame and module box around a heavy LFP cell stack and a light
solid-state one — a box weighing nearly as much as its contents in one case and
half as much in the other.

So the pack **iron** is scaled by the mass of cells it carries, against
`technology.structure_reference_chemistry` (LFP). Capacity cancels — cells =
kWh ÷ (Wh/kg) — so the ratio is a property of the chemistry alone:

| chemistry | `cell_mass_ratio` |
|---|---|
| `Na_ion` | **1.165** — heavier cells, more frame |
| `battLiFP_subsub` | 1.000 (the reference) |
| `battLiNMC_midNi` | 0.749 |
| `battLiNMC_highNi` | 0.687 |
| `solid_state` | **0.583** — lighter cells, less frame |

Both base-year densities, so the ratio does not drift as cells improve: the
improvement already shrinks the whole pack, and applying it twice would
double-count it.

**Aluminium is deliberately excluded**, including the aluminium half of the
module enclosure. The heat to be moved is set by the capacity, not by the pack's
weight.

---

## 6. The three pack rules, in the order they must run

Applied to the CSV rows and to the persisted draws through one function each, so
the two cannot disagree.

1. **Split the module enclosure** — `technology.module_enclosure_split`, 50/50
   Fe/Al. The workbook files the whole enclosure as iron; module housings and
   coolant manifolds are part aluminium. The component's total does not move,
   only its makeup. **First**, so only its iron half is available to scale.
2. **Scale the iron** by `cell_mass_ratio` (§5).
3. **Expand to the pack voltages** — 400 V and 800 V in one file, tagged in
   `voltage_v`. Same power at double the voltage is less current and less
   conductor: **copper × 2/3** in the cables and cell terminals. Not a half,
   because a busbar is also sized by handling and minimum crimp gauge. The anode
   current collector is untouched — it is sized by the cell, not the pack bus.

---

## 7. Which chemistry, in which year

**Not decided in this project.** The composition files say what a battery of a
given chemistry and capacity is made of. *How much of each chemistry the fleet
carries* is a scenario, and it is applied downstream in RAWCLICStockAndFlow,
where the vehicle counts are.

The three scenarios are in `src/scenarios.py` and drawn in
`figures/chemistry_scenarios_to_2070.png`. In short: **S1** LFP volume with NMC
premium and nothing new; **S2** sodium enters the small segments and NMC shrinks
to a niche; **S3** S2 plus bipolar solid-state from 2040. LMFP is in all three.

Two things about them that are easy to misread:

- **Everything after 2026 is assumption.** The observed record ends there.
- **They are shares of what is SOLD.** With a ~15-year vehicle life, what returns
  for recycling in 2050 is roughly what was sold in 2035, so the scenarios barely
  separate on recovered material before about 2045.

---

## 8. Capacity does not develop over time here

How big a battery a segment carries in a given year depends on how many cars of
what size exist and when — fleet knowledge this project does not have. `05`
answers only what it can: **what is inside a battery of capacity X in year Y at
voltage V**, at the workbook's own anchors, with the draws beside it so the
consumer interpolates over capacity.

The composition-over-time figures therefore **hold capacity constant**, at 80 kWh
and 200 kWh, so the only thing moving with the year is the cell getting better.
LFP at 80 kWh runs 464 → 372 kg, a straight line.

---

## 9. Sodium and solid-state: what is known and what is not

Both carry **only the casing, the connections and the pack hardware**. The active
materials — cathode, anode, electrolyte — are `unknownBatteryMaterial` and read
zero, because nobody has the split.

A 60 kWh pack as the files have it, 2020, 400 V:

| | `Na_ion` | `solid_state` | `battLiFP_subsub` |
|---|---|---|---|
| cathode / anode / electrolyte | **0** | **0** | 119.6 / 59.1 / 32.6 kg |
| `batteryPackSupportFrame` | 98.0 | 49.0 | 84.1 |
| `batteryPackThermalConductor` | 38.2 | 38.2 | 38.2 |
| `batteryPackModuleEnclosures…` | 31.5 | 23.0 | 29.1 |
| `batteryPackCables` | 12.4 | 12.4 | 12.4 |
| `currentCollectorAnode` | 11.9 | 11.3 | 25.0 |
| `batteryCellCasing` | 6.3 | — | 6.3 |
| **total** | **216.5** | **138.6** | **427.4** |

Solid-state has no casing, separator or per-cell terminals at all: bipolar
stacking removes them.

**What they inherit and what they do not.** Their rows are built from a base
chemistry and then transformed — components removed, copper swapped for
aluminium, collectors halved. The pack iron is weight-scaled like everything
else (§5), which is why sodium's frame is *heavier* than LFP's at the same kWh
and solid-state's is lighter.

### How much the inherited packaging is trusted

Their casing, separator, terminals and current collectors are taken from a base
chemistry at the same capacity. Friday 2026-09-10 settled that the packaging is
the base chemistry's **at its own mass** — two attempts to rescale it were worse,
one giving sodium 343 kg of packaging on a 906 kg pack. But *"we took LFP's
number"* is not the same as *"we know the number"*, and that doubt is now in the
file as a distribution rather than absent from it.

`technology.unknown_chemistry_mass_scale`, an asymmetric triangular:

| chemistry | min | mode | max | mean |
|---|---|---|---|---|
| `Na_ion` | 0.9 | **1.0** | 1.3 | 1.067 |
| `solid_state` | 0.7 | **0.8** | 1.1 | 0.867 |

Asymmetric on purpose: a sodium cell stack of the same kWh is bulkier than the
LFP one it is copied from, so the packaging can be a good deal heavier more
easily than it can be lighter.

**Sodium's mode is 1.0, so the central case is exactly Friday's decision** — the
numbers do not move, only the spread around them appears. Solid-state's 0.8 is a
claim that bipolar needs less packaging, with its own spread.

It multiplies the components in
`technology.unknown_chemistry_scaled_components` — casing, separator, terminals
and both collectors — **in addition to** the existing rules. Not the pack iron,
which already carries `cell_mass_ratio`; not the thermal conductor or cables,
for the same reason aluminium is excluded from the structure scaling.

Drawn **once per chemistry per Monte Carlo draw** and shared across every
component, element and year, on its own random stream. One doubt about one
inheritance, not an error per row.

Measured at 60 kWh, 2020, 400 V — the band on what it touches, against what it
does not:

| component | `Na_ion` band | `solid_state` band |
|---|---|---|
| casing, separator, terminals, collectors | **33.6–33.9%** | **40.6–40.9%** |
| frame, enclosures, thermal conductor, cables | 15.5% | 15.5% |

> **The statistics for those rows are rebuilt from the draws, not scaled.** The
> template's own factors — the halved collectors, the conductance factor — are
> constants, and a percentile times a constant is a percentile. This factor is a
> triangular, and a percentile times a random number is not a percentile of
> anything: applying it to finished statistics would slide the band without
> widening it, the same defect fixed for the improvement on 2026-09-14. See
> `unknown_scaled_statistics()`.

> **What is still open.** The active materials. Cathode, anode and electrolyte
> are `unknownBatteryMaterial` with no number attached, for both chemistries.
> That is a gap in the source, not in the model, and the numbers have to come
> from literature or WP3. Neither chemistry has a persisted draw array either,
> so a consumer wanting their distributions reads the statistics.

---

## 10. The two LMFP corrections

Both override the source and both live in parameters, so a WP3 revision removes
them:

- **Lithium pinned at 4.40% of cathode.** Stoichiometry; the workbook's 3.45% is
  22% short, and LMFP cannot be the one exception.
- **Cell density pinned at 270 Wh/kg** (`technology.cell_density_override_wh_per_kg`).
  The workbook implies 336, which would make LMFP lighter per kWh than NMC
  mid-Ni. Correcting the density **rescales the cell**, because kg/kWh is one
  over Wh/kg.

Ordering restored: LFP 233, LMFP 270, NMC low 285, NMC mid 311, NMC high 339.
