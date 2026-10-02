# Addendum: Cathode-Level Capacity & Voltage — HiNa vs. Naxtra Layered Oxide

> **Scope:** This addendum addresses whether confirmed cathode specific capacity \[mAh/g\] and average discharge voltage figures are publicly available for HiNa Battery Technology and CATL Naxtra, and the implications for the cell-level material composition model.

---

## 1\. Key Finding: No Confirmed Cathode-Level Figures from Either Company

Neither CATL nor HiNa has published a confirmed **cathode specific capacity \[mAh/g\]** or **average discharge voltage** for their specific cathode formulations. Both companies treat these parameters as proprietary. The only confirmed public data are **cell-level** gravimetric energy densities (Wh/kg). Literature benchmarks from peer-reviewed sources exist for the material families but are not company-verified for their exact compositions.

---

## 2\. Correction to the Main Report

> **Important correction:** HiNa Battery Technology does **not** use a Prussian blue analogue (PBA) cathode in its commercial products.

HiNa's commercial cell chemistry is an **O3-type layered transition metal oxide:**

> **Na\[Cu₀.₂₂Fe₀.₃₀Mn₀.₄₈\]O₂** (Na–Cu–Fe–Mn–O), paired with an anthracite-based hard/soft carbon anode.

The PBA association originates from early academic research papers from the Institute of Physics (IOP), Chinese Academy of Sciences — HiNa's founding institution — and does not reflect their commercial product line.

**CATL's timeline also requires disambiguation:**

* **CATL 1st generation (2021):** Used a **Prussian white (PBA)** cathode — Na₂Fe\[Fe(CN)₆\]-type

* **CATL Naxtra (2025):** Switched to a **layered transition metal oxide** cathode — Na\[Ni–Mn–Cu–Fe\]O₂ type

---

## 3\. Summary Table: Two Cathode Families

| Family | Producer | Cathode Formula | Cell Energy Density (confirmed) | Cathode Capacity mAh/g | Avg. Discharge Voltage | Source Tier |
| --- | --- | --- | --- | --- | --- | --- |
| **PBA (Prussian white)** | CATL 1st gen (2021) | Na₂Fe\[Fe(CN)₆\] type | **160 Wh/kg** | \~150–165 mAh/g _(literature)_ | \~3.3 V _(literature)_ | Cell: Tier 1; mAh/g: Tier 1 (lit.) |
| **Layered oxide — Ni-Mn type** | CATL Naxtra (2025) | Na\[Ni–Mn–Cu–Fe\]O₂ | **175 Wh/kg** | \~140–160 mAh/g _(literature)_ | \~3.3 V _(literature)_ | Cell: Tier 2; mAh/g: Tier 1 (lit.) |
| **Layered oxide — Cu-Fe-Mn type** | HiNa (commercial) | Na\[Cu₀.₂₂Fe₀.₃₀Mn₀.₄₈\]O₂ | **98–167 Wh/kg** | Not published | 2.0–3.95 V (full window) | Cell: Tier 2; mAh/g: N/A |

### Source Reliability Classification

| Claim | Source | Tier |
| --- | --- | --- |
| CATL 2021 cell energy density 160 Wh/kg | CATL official press release, July 2021 | **Tier 1** |
| CATL Naxtra 175 Wh/kg | CarNewsChina, [BatteryDesign.net](http://BatteryDesign.net) (April 2025) | **Tier 2** |
| HiNa cell energy density 98–167 Wh/kg | Batemo cell datasheet (NaCR26700), [battery-tech.net](http://battery-tech.net) | **Tier 2** |
| PBA cathode \~150–165 mAh/g; \~3.3 V | Peer-reviewed literature (Nature Comms, ACS, Wiley) | **Tier 1 (literature benchmark, not company-confirmed)** |
| Layered oxide 140–160 mAh/g; 3.2–3.5 V | Peer-reviewed literature (general benchmark) | **Tier 1 (literature benchmark, not company-confirmed)** |
| HiNa cathode formula Na\[Cu₀.₂₂Fe₀.₃₀Mn₀.₄₈\]O₂ | [battery-tech.net](http://battery-tech.net), IOP CAS affiliated publications | **Tier 2–3** |

---

## 4\. Implications for the Material Composition Excel Model

The current Excel model assigns a flat **35% cathode active material** mass fraction to all Na-ion chemistries. This is physically only valid when specific energy per gram of cathode is held constant. Since the two families have different specific energies, a shared cathode mass row introduces the following error:

### Estimated Cathode Specific Energy by Family

| Family | Approx. Cathode Capacity | Approx. Avg. Voltage | Cathode Specific Energy | Relative Error if Unified |
| --- | --- | --- | --- | --- |
| PBA (CATL 2021) | \~157 mAh/g | \~3.3 V | **\~0.52 Wh/g** | Baseline |
| Naxtra layered oxide (CATL 2025) | \~150 mAh/g | \~3.3 V | **\~0.50 Wh/g** | \~4% — within measurement uncertainty |
| HiNa Cu–Fe–Mn layered oxide | Not published | avg. \~3.1 V (estimated from window) | **\~0.35–0.42 Wh/g (est.)** | \~20–30% higher cathode mass needed |

### Conclusions for the Model

1. **PBA and Naxtra layered oxide** are close enough in cathode specific energy (\~4% difference) that sharing a single cathode mass row introduces only minor error. Both can reasonably use the midpoint assumption of **\~150 mAh/g at 3.3 V**.

2. **HiNa's Cu–Fe–Mn layered oxide** is more problematic. Its lower cell-level energy density (98–155 Wh/kg vs. CATL's 160–175 Wh/kg) back-calculates to a meaningfully larger cathode mass fraction — estimated **\~40–45%** vs. the 35% used in the unified model — implying a \~14–28% underestimation of cathode mass if the unified row is applied to HiNa.

3. Until HiNa publishes cathode-level electrochemical data, the HiNa row in any composition table should carry an explicit **uncertainty annotation** and should use the cell-back-calculated estimate rather than the literature benchmark.

---

## 5\. Recommended Model Update

To correct the Excel model, the cathode row should be split as follows:

| Cathode Row | Chemistry | Assumed mAh/g | Assumed avg. V | Cathode Wh/g | Cathode mass fraction | Confidence |
| --- | --- | --- | --- | --- | --- | --- |
| PBA / CATL 2021 | Na₂Fe\[Fe(CN)₆\] | 155 mAh/g | 3.3 V | 0.51 Wh/g | \~35% | Medium (lit. benchmark) |
| Naxtra / CATL 2025 | Na\[Ni–Mn–Cu–Fe\]O₂ | 150 mAh/g | 3.3 V | 0.50 Wh/g | \~35% | Medium (lit. benchmark) |
| HiNa Cu–Fe–Mn | Na\[Cu₀.₂₂Fe₀.₃₀Mn₀.₄₈\]O₂ | \~120 mAh/g _(est.)_ | \~3.1 V _(est.)_ | \~0.37 Wh/g | **\~43% _(est.)_** | Low (back-calculated, unconfirmed) |

> **Note:** All mAh/g and voltage figures for specific commercial formulations are unconfirmed by the respective companies. Literature benchmarks for the material family are used as proxies. Cell-level energy density figures are the only confirmed public data points.

---

_Sources consulted: CATL official press releases (Tier 1); CarNewsChina, [BatteryDesign.net](http://BatteryDesign.net), [battery-tech.net](http://battery-tech.net) (Tier 2); Batemo cell datasheets (Tier 2); peer-reviewed Na-ion literature via Nature Communications, ACS Energy Letters, Wiley Small (Tier 1 — as literature benchmarks); Wikipedia sodium-ion battery article (Tier 3)._