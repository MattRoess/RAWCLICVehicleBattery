# Handover — RAWCLICVehicleBattery

Written 2026-09-08, to be picked up **on another Mac**. State verified against
the repository, not remembered.

For the methods and the reasoning, read
[`METHODOLOGY.md`](METHODOLOGY.md) — the whole project in one document. This
file is only what you need to carry on.

---

## 1. Picking up on the other Mac — read this first

The project lives in **iCloud Drive**, so the whole folder syncs, `data/` and
`figures/` included. Neither is in git. Three things to check before running
anything:

```bash
cd "/Users/rm/Library/Mobile Documents/com~apple~CloudDocs/Documents/GitHub/RAWCLICVehicleBattery"
git pull                                              # code is on GitHub too
ls data/raw/                                          # must show the .xlsx and the .csv
./.venv/bin/python 00_parameters.py                   # if this runs, the venv survived
```

1. **iCloud may not have downloaded the files.** A placeholder looks like a file
   but is not one. If `data/raw/` looks empty or a read fails, force a download
   in Finder before blaming the code.
2. **`.venv` is not in git and holds absolute paths.** It works on another Mac
   only if the username is also `rm`. If `00_parameters.py` fails to start,
   rebuild it — two minutes:
   ```bash
   rm -rf .venv
   ~/.pyenv/versions/3.14.4/bin/python3 -m venv .venv
   ./.venv/bin/pip install -r requirements.txt
   ```
   That needs **pyenv with Python 3.14.4** on the other machine. Any 3.14.x will
   do at a pinch; `requirements.txt` pins everything else.
3. **`params.xlsx` and everything in `data/composition/` and `figures/` are
   generated.** If they look stale or missing, rerun — nothing is lost.

Everything is committed and pushed. `git status` should be clean and
`main` in sync with `origin/main`.

---

## 2. Where things stand

Repository: <https://github.com/MattRoess/RAWCLICVehicleBattery>, public, `main`.

**All seven scripts run.** Full sequence from cold, about 40 seconds in total:

```bash
./.venv/bin/python 00_parameters.py                 # always first — regenerates AND validates
./.venv/bin/python 99_check_environment.py
./.venv/bin/python 01_draw_battery_structure.py
./.venv/bin/python 02_composition_by_capacity.py
./.venv/bin/python 03_capacity_by_segment_over_time.py
./.venv/bin/python 04_capacity_by_chemistry.py
./.venv/bin/python 05_chemistry_scenarios.py
./.venv/bin/python 06_generate_composition_files.py # the deliverable
```

**The deliverable** is `data/composition/` — nine CSV files, one per chemistry,
one row per component/material/element **for one car**, all 12 segments, 2020 to
2070 every fifth year, Monte Carlo percentiles on every computed value.

No chemistry mixing happens here: the scenario shares are applied downstream in
the stock-and-flow model, where the vehicle counts are.

**Nothing is half-finished.** The last session closed the two parameters that
were outstanding (the casing split and the packing ratio); there is no
work-in-progress to resume.

---

## 3. What was settled, and what it rests on

These were decided over the session and are easy to reopen by accident.

| decision | value | note |
|---|---|---|
| Capacity basis | **nominal** | the workbook's kg/kWh is per nominal kWh; useable is ~5% lower and would understate every mass |
| Range saturation | **600 km** | on the fast-charging argument: at 350 kW a 600 km car refills in ~15 min, which is why real ranges plateaued at 400–600 km. A longer target does not restrain anything — today's median is already ~490 km |
| Solid-state density | **400 Wh/kg cell in 2040 → 500 in 2050 → 600 in 2060** | a trajectory, not a constant, and quoted at CELL level |
| Cell-to-pack ratio | **0.85** | supplied. Today's chemistries are 0.59–0.69; this is the optimistic end |
| Cell casing | **40% Al, 60% plastics** | supplied |
| Second-life diversion | LFP 35%, LMFP 30%, Na 25%, NMC 10%, NCA 5% | a genuine unknown — the parameter most worth varying |
| Scenario S2 | "NMC becomes a niche", not "NMC eliminated by 2035" | the elimination clause was the least defensible thing proposed |
| Segment JA | capacity from its own two cars (45.5 kWh) | `battery_size_map` says 25, which is wrong for the cars that exist |

**The finding that survived every revision**: a one-third material saving and a
1000–1500 km range are mutually exclusive. At 1200 km a third off would need
~717 Wh/kg pack; at 1500 km ~900, beyond any lithium chemistry. Fast charging is
what breaks the deadlock, which is why the target is 600 km.

At 600 km, solid-state packs are **0.69× today's mass in 2040, 0.46× from 2060**
(JC). The saving arrives gradually — an earlier flat-density assumption
overstated the early years by about a third.

---

## 4. Open, and who they are for

1. **Compositions for sodium-ion and bipolar solid-state.** The only real gap.
   Both are written as files with the row skeleton and every mass empty,
   `composition_status = "unknown"`. They are not variants of anything in the
   workbook — the component list itself changes — so nothing can be derived; the
   numbers have to come from literature or from WP3.
2. **The electrolyte's element breakdown.** It itemises only lithium, losing 99%
   of its own mass at element level. This is the largest part of the ~13% of cell
   mass that has no element rows — bigger than the casing and separator together.
3. **Sales weighting.** Every vehicle-table result is by **models, not
   registrations**. Joining to the EEA data the stock-and-flow model already holds
   would turn "share of models" into "share of cars", and is the precondition for
   revising `battery_size_map` on this evidence.
4. **`battery_size_map` is low for every segment** — JB +30%, JC +27%, JE +31% on
   the nominal basis. Changing it is a change to RAWCLICStockAndFlow and it moves
   published results.

### Still blocked in RAWCLICStockAndFlow

`code/04_04_batteries.py` cannot run, for reasons that are not this project's:

- it wants `battery_composition_parameter_code = "e-m"`, which does not exist in
  this workbook (it has `c-p`, `m-c`, `e-c`);
- it expects one sheet named `BATT_EV_consolidated_inputForRM` and a `Layer 3`
  column; this workbook has seven size sheets and no `Layer 3`;
- `BATTKey_xEV_shares_final.xlsx` is not on disk at all. The scenarios in `05`
  now supply chemistry shares to 2070 and could replace it, though by models
  rather than registrations until item 3 is done.

### Outstanding elsewhere

A repository audit on 2026-09-07 found data files in public repos, none from this
work and none cleaned up: `VehicleComposition` (~123 MB including the JRC RMIS
workbooks), `RAWCLICRecoveryModel` (~1.4 MB), `RAWCLICVehicleElectronics` (5
workbooks under `Consolidation/`, outside its `.gitignore`'s `Data/` rule), and
`listing.csv` still in `RAWCLICVehicleComposition`'s history (private repo).
Removing any of them means rewriting history and force-pushing, and
`git filter-repo` is not installed.

---

## 5. Where things are

| | |
|---|---|
| `src/params_schema.py` | **the file to edit.** 111 settings, each with its own comment; `00_parameters.py` validates every one |
| `src/composition.py` | composition at any capacity, with uncertainty |
| `src/ev_details.py` | the vehicle table: parsing, smoothing, bootstrap |
| `src/scenarios.py` | the three scenarios and the returning mix |
| `documentation/METHODOLOGY.md` | the whole project explained, including every known gap |
| `data/raw/` | the two inputs — **not in git**, supplied via iCloud |
| `data/composition/` | the nine output files — generated |
| `figures/` | eight figures — generated |

**No data file is ever committed.** `data/` and `figures/` are excluded at the
folder, so a new output cannot slip through by having an extension nobody listed.
