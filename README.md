# BRIXTA Cement Twin Lab

## Complete Operating Catalogue, Research Manual and Validation Guide

**Product version covered:** V0.4  
**Document edition:** 1.0 - 2 August 2026  
**Primary purpose:** controlled cement recipe, process-route and equipment scenario screening  
**Audience:** founders, plant engineers, cement technologists, research partners, laboratory teams and investment reviewers
**This is how you start it in VScode:**
python -m uvicorn brixta_twin.app:app --reload --port 8100
vite: npm run dev INSIDE THE web/
---

## Read this first

BRIXTA Cement Twin Lab is a deterministic engineering scenario and audit engine. It combines an immutable material library, versioned blend recipes, versioned machines, versioned process routes, versioned cost books and a fixed calculation engine. Each completed simulation is stored as an immutable experiment.

It is designed to answer:

- What material composition did we test?
- Which exact machine and route versions were used?
- What throughput can that route screen as achievable?
- Which machine becomes the bottleneck?
- What weighted oxide chemistry is produced by the recipe?
- What electricity and thermal-energy intensity is implied?
- What material, energy, plant-cash and full-cost scenario is implied?
- What material-scope CO2 estimate is implied?
- Which values were measured, sourced, assumed, missing or unverified?
- How does one controlled candidate compare with a baseline?

It does **not** yet prove compressive strength, setting time, durability, workability, mineral phases, kiln stability, product-standard compliance, market acceptance or project bankability. Those require laboratory, pilot, plant, commercial and regulatory evidence.

> The simulator ranks and documents hypotheses. Physical testing decides whether a hypothesis is real.

---

## 1. The simulator in one picture

Every experiment is the combination of six controlled objects:

```text
Materials -> Blend -> Machines -> Route -> Cost Book -> Run Basis
                                                   |
                                                   v
                                    Immutable simulation result
                                                   |
                                                   v
                              Compare, review, validate and export
```

### The prime rule

For useful research, change **one layer at a time**:

1. Keep route, machines, cost book and throughput fixed; change only the blend.
2. Keep blend, cost book and throughput fixed; change only one machine or route.
3. Keep blend and route fixed; change only the cost-book scenario.
4. Keep everything else fixed; change only the target throughput or raw-meal yield.

If several layers change together, the result may improve, but you will not know which change caused it.

---

## 2. What is calculated and what is not

| Area | V0.4 result | Interpretation |
| --- | --- | --- |
| Blend composition | Yes | Direct and recursively flattened base-material percentages |
| Weighted oxides | Yes | Linear mass-weighted screening chemistry |
| LSF, SM and AM | Raw-meal blends only | Kiln-feed control ratios, not finished-cement quality scores |
| Throughput | Yes | Steady-state screening based on effective machine capacities and material-flow factors |
| Bottleneck | Yes | Machine with the lowest cement-equivalent capacity |
| Electricity | Yes | Sum of route-stage specific electricity after mass-flow conversion |
| Thermal energy | Yes | Sum of route-stage specific heat after mass-flow conversion |
| Material cost | Yes, when complete | Route-aware purchased or internal-feed cost from the selected cost book |
| Plant-cash/full cost | Yes, when complete | Only when all required cost-book fields are populated |
| Material CO2 | Yes, when complete | Weighted material-record factors; scope limitations apply |
| Compressive strength | No | Requires a calibrated empirical or mechanistic model and physical tests |
| Setting time/durability | No | Requires laboratory data and a separate validated model |
| Dynamic kiln behaviour | No | No transient temperatures, pressures, gas balance or process-control dynamics |
| CAPEX returns | No | Machine CAPEX can be recorded, but V0.4 does not calculate IRR, NPV or payback |
| Cement-standard compliance | No | Standards and accredited testing remain external gates |

---

## 3. Screen map

### CONSOLE

Runs one selected blend through one selected route and cost book. It displays the process topology, event log, top-level KPIs, warnings, machine breakdown, material breakdown, assumptions and evidence references.

### BLEND

Contains two workspaces:

- **Blend Composer:** creates an immutable recipe from any number of materials and/or existing immutable blends.
- **New Material:** creates a versioned material record with chemistry, location, processing state, commercial values, CO2 factor, evidence and data gaps.

### MACHINE

Creates immutable machine versions with stage, capacity, stable load, availability, energy intensity, heat intensity, CAPEX, technology-readiness level and evidence.

### ROUTE

Creates a new immutable route or a new version copied from an existing route. Machines are added, removed and reordered.

### COSTS

Creates immutable commercial scenarios. It stores tariffs, operating costs and both purchased-delivered and internally produced feed costs for each active material.

### RUNS

Stores immutable experiments. Previous runs can be reopened, compared and exported to CSV or JSON.

### LIBRARY

Manages active materials, blends, machines, routes and cost books. Records can be archived, restored where supported, or permanently deleted only when unreferenced.

---

## 4. Installation and startup

### Requirements

- Python 3.11 or later
- Node.js 20 or later
- npm

### First installation

```bash
cd ~/brixta-cement-twin
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e "./apps/api[dev]"
cd apps/web
npm install
```

The editable Python installation points at the local `apps/api` directory. It does not need to clone another repository.

### Start the API

```bash
cd ~/brixta-cement-twin
source .venv/bin/activate
python -m uvicorn brixta_twin.app:app --reload --port 8100
```

### Start the frontend in a second Terminal

```bash
cd ~/brixta-cement-twin/apps/web
npm run dev
```

Open:

- Interface: `http://127.0.0.1:5173`
- API documentation: `http://127.0.0.1:8100/docs`

Use `python -m uvicorn`, not a bare `uvicorn` command. This ensures the server uses the active virtual environment.

---

## 5. The correct first experiment

Start with a reproducible reference before inventing anything.

1. Open `CONSOLE`.
2. Select `Reference PPC 64/31/5`.
3. Select `Integrated Plant Baseline v0.3`.
4. Select a cost book. The starter cost book is screening-only.
5. Set target output to `100 t/h cement`.
6. Open `RUN BASIS`.
7. Set duration to `24 hours`.
8. Review electricity tariff, thermal-fuel tariff and raw-meal-to-clinker yield.
9. Press `RUN SIMULATION`.
10. Read warnings before reading the headline cost.
11. Save the run as the baseline in `RUNS`.

Expected behaviour with the starter integrated route:

- The kiln is likely to constrain output below the 100 t/h target.
- Electricity and heat are calculated from installed machine stages.
- Integrated-route material cost may be `N/A` until an internal clinker-feed/raw-material cost is entered in a new cost-book version.
- LSF is `N/A` because PPC is finished cement, not raw meal.
- Physical-validation and assumed-data warnings remain until real evidence replaces starter values.

---

## 6. Creating and managing materials

### 6.1 Create a material

Go to `BLEND -> NEW MATERIAL`.

Fill these fields:

| Field | What it means | Good practice |
| --- | --- | --- |
| Name | Human-readable material identity | Include source and state, such as `Plant A Fly Ash - August 2026` |
| Material type | Functional category | Use stable names such as clinker, fly_ash, gypsum, limestone, calcined_clay or ggbs |
| Location/source | Mine, supplier, plant or sample origin | Use a precise, repeatable location |
| Processing state | As-received, dried, ground, calcined, mine average, etc. | Never mix two physical states in one record |
| Applicable blend classes | Where the material is valid | Raw-meal limestone is not automatically a finished-cement addition |
| Chemistry | Oxide mass percentages | Prefer a dated XRF/COA and record sample variability |
| Delivered cost | Purchased material delivered to the selected plant | Include date, freight basis and taxes consistently |
| Material CO2 | Embodied factor for the defined scope | State whether transport and processing are included |
| Evidence class | Measured, official document, vendor, literature, assumed, etc. | Use the strongest honest classification |
| Source URI | Original source or internal record | Keep a stable reference |
| Page/table | Exact locator | Avoid evidence with no page or table |
| Notes | Scope, moisture, test method and caveats | Record anything needed to reproduce the value |
| Data gaps | Unknown or unreported properties | Explicitly name every unknown field |

Press `CREATE VERSIONED MATERIAL`.

### 6.2 Chemistry rules

The current chemistry object contains:

```text
CaO, SiO2, Al2O3, Fe2O3, MgO, SO3, Na2O, K2O and LOI
```

Important rules:

- Use mass percentages on a clearly stated basis.
- Do not mix dry-basis and as-received values without conversion.
- Do not treat `0` as identical to `unknown`.
- If the interface requires a numerical placeholder, record the oxide in `data gaps` and treat every dependent result as provisional.
- A single average hides quarry or supplier variability. Create separate records for benches, dates, suppliers or confidence bounds.
- Create a new material version when chemistry, cost basis, processing state or evidence changes materially.

### 6.3 How new materials reach the COSTS page

An existing cost book is an immutable historical snapshot. A new material does not rewrite it.

After creating a material:

1. Open `COSTS`.
2. Start from the latest cost book.
3. Create a **new cost-book version**.
4. The new active material appears in the pricing table.
5. Enter the relevant purchased and/or internal-feed cost.
6. Save the new immutable cost book.

### 6.4 Archive versus delete

Use `LIBRARY -> MATERIAL LIBRARY`.

- **ARCHIVE:** recommended for an obsolete, superseded or temporarily hidden record. It disappears from new experiments while historical runs remain reproducible.
- **DELETE:** permanent and allowed only when no blend, cost book or run depends on the material.

If deletion is blocked, archive the record. A referenced material must never be removed from experiment history.

### 6.5 Recommended material naming pattern

```text
<Material> - <Source/Location> - <State> - <Month/Year>
```

Examples:

```text
Limestone - Lumshnong Bench 531-540 - Crushed - Aug 2026
Fly Ash - Supplier X - Dry Classified - Aug 2026
Calcined Clay - Pilot Lot 03 - 800 C - Aug 2026
Clinker - Existing Kiln Line 1 - Weekly Composite - Aug 2026
```

---

## 7. Cost books and trustworthy costing

### 7.1 Why cost books are separate

A material's chemistry may remain stable while price, freight, tariff and operating cost change every month. Cost books version the commercial scenario without rewriting the engineering record.

### 7.2 Fields

| Cost-book input | Unit | Meaning |
| --- | --- | --- |
| Electricity | INR/kWh | Applicable plant electricity tariff |
| Thermal fuel | INR/million kcal | Fuel cost normalized by usable calorific energy |
| Packing | INR/t cement | Bag and packing-related cost |
| Labour | INR/t cement | Defined plant labour allocation |
| Maintenance | INR/t cement | Defined maintenance allocation |
| Other variable | INR/t cement | Other variable manufacturing OPEX |
| Factory overhead | INR/t cement | Fixed/allocated factory overhead for the scenario |
| Outbound logistics | INR/t cement | Dispatch-to-market logistics included in the scenario |

Blank means unknown. Blank must never silently become zero.

### 7.3 Purchased delivered versus internal feed

These columns have different meanings:

| Column | Use it when | Example |
| --- | --- | --- |
| Purchased delivered INR/t | The selected route buys the processed material | A grinding unit buys clinker |
| Internal feed/raw-material INR/t product | The selected route produces that material and process energy is calculated separately | An integrated route produces clinker in its kiln |

For an integrated kiln route:

```text
clinker contribution = clinker fraction x internal clinker-feed cost
                     + kiln electricity
                     + kiln thermal energy
```

For a grinding-only route:

```text
clinker contribution = clinker fraction x purchased delivered clinker price
```

Do not put a full purchased-clinker price in the internal-feed column. That would risk counting clinker-production energy twice.

### 7.4 Cost tiers

```text
Direct model cost
  = route-appropriate materials + electricity + thermal fuel

Plant cash cost
  = direct model cost + packing + labour + maintenance + other variable OPEX

Full cost estimate
  = plant cash cost + factory overhead + outbound logistics
```

Still outside V0.4 unless added in a separate financial model:

- depreciation;
- finance and interest;
- taxes;
- working capital;
- construction CAPEX;
- sales and corporate overhead;
- dealer margin and market realization;
- WHRS/export credits;
- carbon-credit revenue.

### 7.5 Commercial evidence checklist

For every cost-book version, record:

- effective date;
- supplier quotation or invoice date;
- freight and delivery basis;
- moisture or quality adjustment;
- taxes included/excluded;
- tariff source;
- fuel grade and net calorific value;
- allocation basis for labour and overhead;
- person responsible for review.

---

## 8. Creating blends

### 8.1 Blend classes

| Class | Intended use |
| --- | --- |
| Raw material stockpile | Quarry bench and preblending scenarios |
| Raw meal | Kiln-feed chemistry; LSF, SM and AM apply |
| Fuel blend | Coal, petcoke, biomass, RDF and alternative fuels |
| Clinker blend | Internal and/or purchased clinker combinations |
| Finished cement | Clinker, SCMs, gypsum, limestone and additions |
| Premix | Reusable intermediate composition |

### 8.2 Compose a recipe

Go to `BLEND -> BLEND COMPOSER`.

1. Give the recipe a unique name.
2. Select its blend class.
3. Record family, research objective and standard/review note.
4. Add any number of material rows.
5. Add an existing immutable blend when a reusable premix is needed.
6. Set direct percentages.
7. Ensure the direct total is exactly 100%.
8. Review the flattened base-material composition.
9. Review screening chemistry and warnings.
10. Press `CREATE IMMUTABLE BLEND VERSION`.

The engine rejects:

- totals outside 100% tolerance;
- duplicate direct references;
- unknown material/blend references;
- circular blend references.

### 8.3 Nested blends

Nested blends are useful for premixes:

```text
LC3 mineral premix = 66.6667% calcined clay + 33.3333% limestone
Finished cement    = 50% clinker + 45% premix + 5% gypsum
Flattened result   = 50% clinker + 30% calcined clay + 15% limestone + 5% gypsum
```

The parent blend stores the exact child-blend version. Updating the child later does not rewrite the old parent or its runs.

### 8.4 Seeded reference recipes

These are starting patterns, not proof of standard compliance:

| Recipe | Composition by mass | Intended use |
| --- | --- | --- |
| Reference OPC 95/5 | 95 clinker, 5 gypsum | High-clinker reference |
| Reference PPC 64/31/5 | 64 clinker, 31 fly ash, 5 gypsum | PPC baseline |
| Reference PSC 38/57/5 | 38 clinker, 57 GGBFS, 5 gypsum | Slag-rich reference |
| Reference Composite 45/25/25/5 | 45 clinker, 25 fly ash, 25 GGBFS, 5 gypsum | Multi-SCM reference |
| Plant-Trial Composite 30.5/47/18/4.5 | 30.5 clinker, 47 GGBFS, 18 fly ash, 4.5 gypsum | Captured plant-trial pattern |
| Reference LC3-50 50/30/15/5 | 50 clinker, 30 calcined clay, 15 limestone, 5 gypsum | LC3 research reference |

### 8.5 Recommended controlled candidate ladder

Run known references first. Then change one ingredient in small steps.

| Candidate family | Example composition | Research question |
| --- | --- | --- |
| PPC baseline | 64 clinker, 31 fly ash, 5 gypsum | Reference position |
| PPC step 1 | 60 clinker, 35 fly ash, 5 gypsum | Effect of 4-point clinker reduction |
| PPC step 2 | 55 clinker, 40 fly ash, 5 gypsum | More aggressive substitution; physical validation essential |
| Composite A | 50 clinker, 20 fly ash, 25 GGBFS, 5 gypsum | Balanced clinker reduction |
| Composite B | 45 clinker, 30 fly ash, 20 GGBFS, 5 gypsum | Shift SCM balance toward fly ash |
| LC3 conservative | 55 clinker, 27 calcined clay, 13 limestone, 5 gypsum | Lower-risk step toward LC3-50 |
| LC3 reference | 50 clinker, 30 calcined clay, 15 limestone, 5 gypsum | Literature reference |
| LC3 aggressive R&D | 45 clinker, 33 calcined clay, 17 limestone, 5 gypsum | Research-only boundary exploration |

Never interpret a lower simulated cost or CO2 value as proof that the cement will pass strength, setting, soundness or durability requirements.

---

## 9. Creating machines

Go to `MACHINE`.

| Field | Meaning | Validation recommendation |
| --- | --- | --- |
| Type | Standard or thermal machine | Thermal machines expose heat/transformation fields |
| Name | Exact equipment/version identity | Include vendor/model or plant tag |
| Stage | Crushing, raw grinding, thermal transformation, clay calcination, cement grinding, packing/dispatch, etc. | Stage controls route mass-flow conversion |
| Rated capacity | Nameplate or guaranteed t/h for that machine's physical stream | State material and test conditions |
| Minimum stable capacity | Lowest sustainable throughput | Use vendor/plant evidence |
| Availability | Fraction from 0 to 1 | Prefer historical availability, not aspiration |
| Electricity | kWh/t of that machine's stage flow | Do not enter plant-wide electricity here |
| Thermal energy | kcal/kg of that stage flow | Mainly thermal transformation/calcination |
| CAPEX | INR crore | Store vendor scenario; V0.4 does not calculate returns |
| TRL | Technology readiness 1-9 | Keep investor base case at TRL 8-9 unless explicitly disclosed |
| Evidence | Vendor, measured, literature or assumed source | Attach exact source information |

### Effective capacity

```text
effective stage capacity = rated capacity x availability
```

A machine with 100 t/h nameplate and 90% availability contributes 90 t/h effective stage capacity before stream conversion.

### Machine-version discipline

Create a new version when any of these change:

- capacity guarantee;
- specific electricity/heat;
- availability;
- operating range;
- vendor/model;
- CAPEX quotation;
- technology-readiness status;
- supporting evidence.

---

## 10. Creating and editing routes

Go to `ROUTE`.

### Route kinds

| Route kind | Typical stages | Cost behaviour |
| --- | --- | --- |
| Integrated | Crusher -> raw mill -> kiln -> cement mill -> packer | Uses internal clinker-feed cost plus kiln energy |
| Grinding only | Cement mill -> packer | Uses purchased delivered clinker price; no kiln thermal energy |
| Integrated LC3 | Integrated clinker line plus clay calciner feeding cement grinding | Uses internal clinker and calcined-clay feed plus process energy |
| Clinker only | Raw preparation and kiln route | Intended for clinker-production screening |
| Custom | User-defined ordered machines | Behaviour is inferred from installed machine stages |

### Create or version a route

1. Choose `Blank route` or an existing route under `START FROM`.
2. Name the new route/version.
3. Select the route kind.
4. Add machine stages.
5. Select exact immutable machine versions.
6. Move stages up/down into process order.
7. Remove unwanted stages.
8. Save the immutable route.

Existing runs retain the old route and machine snapshots.

### Important topology limitation

The current route composer rebuilds material edges automatically in displayed order. It is excellent for serial routes. The seeded LC3 route contains a separate clay-calciner branch, but V0.4 is not yet a full arbitrary-DAG graphical editor. Carefully review any copied/edited branched route because saving it through the linear composer may serialize its edges.

### Recommended route experiments

1. Run the same PPC blend on the integrated baseline and grinding-only route.
2. Run the same LC3 blend on the integrated baseline and integrated-LC3 route.
3. Replace only the bottleneck machine and compare.
4. Increase one machine's capacity without changing its energy intensity; observe whether the bottleneck moves.
5. Change availability using measured downtime data.
6. Test a low-TRL machine only in a clearly labelled R&D route.

---

## 11. Run-basis controls

| Control | Meaning | How to use it |
| --- | --- | --- |
| Target t/h cement | Requested steady-state cement output | Test a ladder such as 60, 70, 80, 90 and 100 t/h |
| Duration hours | Continuous run period for total production/energy | Use 24 h for daily scenarios; adjust for campaign studies |
| Electricity tariff | Fallback when the cost book lacks a value | Prefer a dated cost-book value |
| Thermal-fuel tariff | Fallback when the cost book lacks a value | Normalize to INR/million kcal consistently |
| Raw meal -> clinker yield | Clinker tonnes per tonne raw meal | Default 0.65 is an assumption; calibrate from the plant mass balance |

If the selected cost book contains energy tariffs, those override the run-basis fallback tariffs.

---

## 12. How the simulation works

### 12.1 Flattening and chemistry

```text
flattened fraction = parent fraction x child fraction x deeper-child fractions
weighted oxide = sum(material fraction x material oxide)
```

### 12.2 Raw-meal moduli

For `raw_meal` blends only:

```text
LSF (%) = 100 x CaO / (2.8 SiO2 + 1.18 Al2O3 + 0.65 Fe2O3)
SM      = SiO2 / (Al2O3 + Fe2O3)
AM      = Al2O3 / Fe2O3
```

LSF means Limestone Saturation Factor. It screens whether lime is balanced against silica, alumina and iron for clinker formation. LSF, SM and AM are intentionally withheld for finished cement.

### 12.3 Stream translation

Machine nameplate capacities describe different physical streams. The engine translates them to cement-equivalent capacity.

For finished cement on an integrated route:

```text
clinker flow = cement output x clinker fraction
raw-meal flow = clinker flow / raw-meal-to-clinker yield
calcined-clay flow = cement output x calcined-clay fraction
cement mill and packer flow = cement output
```

For each machine:

```text
effective stage capacity = rated capacity x availability
cement-equivalent capacity = effective stage capacity / stage flow factor
route capacity = minimum cement-equivalent machine capacity
achieved output = minimum(target output, route capacity)
```

### 12.4 Energy

```text
machine electricity per t cement
  = machine kWh/t stage x stage flow factor

route electricity
  = sum(machine electricity per t cement)

machine heat per kg cement
  = machine kcal/kg stage x stage flow factor

route thermal intensity
  = sum(machine heat per kg cement)
```

### 12.5 Carbon

```text
material CO2 per t cement
  = sum(material fraction x material CO2 factor)

total run material CO2
  = material CO2 intensity x total run output
```

This is a material-scope estimate. It does not automatically include every Scope 1, 2 or 3 term, construction CAPEX, downstream concrete use or carbonation.

---

## 13. Reading the CONSOLE result

Read in this order:

### 1. Validation and warnings

Warnings tell you whether data are assumed, missing, low-TRL, below stable load, physically unvalidated or commercially incomplete. Never start with the headline cost.

### 2. Target versus achieved output

- `Target output`: what you requested.
- `Achieved output`: what the route can screen as delivering.
- A lower achieved value means a capacity constraint.

### 3. Bottleneck

The bottleneck is the machine with minimum cement-equivalent capacity. Upgrading a non-bottleneck machine will not necessarily increase route output.

### 4. Energy

- Electricity intensity: kWh/t cement.
- Thermal intensity: kcal/kg cement.
- Run totals: MWh and Gcal over the selected duration.

### 5. Cost tiers

Read whether the value is:

- materials only;
- direct model cost;
- plant cash cost;
- full cost estimate;
- `N/A` because a required input is missing.

### 6. Carbon

Read the scope statement beside the value. Compare candidates only when the same boundary and evidence quality are used.

### 7. Machine breakdown

For every machine, inspect:

- actual stage t/h;
- effective stage capacity;
- cement-equivalent capacity;
- load percent;
- kWh/t cement contribution;
- kcal/kg cement contribution.

### 8. Material breakdown

For every base material, inspect:

- flattened mass percentage;
- tonnes/hour;
- tonnes/run;
- applied cost and cost basis;
- INR/t cement contribution;
- kg CO2/t cement contribution;
- evidence class.

### 9. Assumptions and evidence

The assumption register explains calculation version, tariffs, duration, cost book and raw-meal yield. Evidence references show the sources attached to the blend, materials, machines and cost book.

### 10. Event stream

The event stream is the readable calculation trail: load, chemistry, flow, capacity, heat, cost, mass check and result.

---

## 14. RUNS: experiment history and comparison

Each completed run freezes:

- exact blend version;
- exact flattened material versions;
- exact route version;
- exact machine versions;
- exact cost-book version;
- run-basis inputs;
- target and achieved output;
- bottleneck;
- chemistry;
- energy;
- costs and exclusions;
- carbon;
- validation messages;
- assumptions;
- evidence references;
- calculation-engine version;
- timestamp.

Use `RUNS` to:

1. Reopen a historical run.
2. Select a baseline and candidates.
3. Compare up to six runs.
4. Export CSV for spreadsheet analysis.
5. Export JSON for BRIXTA RAG, audit or downstream software.

Never compare two runs without checking that their route, cost-book date, calculation version and evidence boundary are comparable.

---

## 15. Recommended research programme

### Phase A - Reproduce known references

Run the six seeded finished-cement references with one fixed route, cost book and target. Confirm that mass, route and commercial calculations behave consistently.

### Phase B - Local-material substitution

For each candidate:

1. Create separate local material records from measured data.
2. Substitute only one local material into a known reference recipe.
3. Keep percentage, route, cost book and throughput fixed.
4. Compare chemistry, cost, carbon and warnings.
5. Send the most promising candidates to laboratory testing.

### Phase C - Recipe ladder

Change clinker replacement in 3-5 percentage-point increments. Do not jump directly from a known blend to the most aggressive candidate.

### Phase D - Machine and route isolation

Use the same validated blend and cost book. Replace one machine, rerun, and observe capacity, energy and cost. Then test complete route alternatives.

### Phase E - Uncertainty and sensitivity

Create low, base and high versions for:

- quarry chemistry;
- material prices;
- electricity/fuel tariffs;
- availability;
- machine energy intensity;
- raw-meal yield;
- transport cost;
- CO2 factors.

The result should be a range, not a single magical number.

### Phase F - Physical validation

For shortlisted finished-cement recipes, obtain at minimum:

- fineness and particle-size distribution;
- water demand;
- setting time;
- soundness;
- 1, 3, 7, 28, 56 and 90-day strength where relevant;
- heat evolution;
- chloride/sulphate or durability indicators relevant to the target market;
- repeat batches and statistical variability.

### Phase G - Plant calibration

Compare simulator predictions with measured plant data:

```text
error = predicted - measured
relative error (%) = 100 x (predicted - measured) / measured
```

Calibrate capacity, availability, energy and yield parameters only from traceable observations. Keep the original and calibrated model versions.

---

## 16. Evidence ladder

| Level | Evidence | Permitted use |
| --- | --- | --- |
| 0 | Placeholder/assumption | Interface testing and rough scenario screening |
| 1 | Literature/general benchmark | Directional research with explicit caveats |
| 2 | Official project document or supplier certificate | Source-specific screening, still subject to verification |
| 3 | Dated laboratory measurement | Material/recipe evidence for the tested sample |
| 4 | Pilot or controlled plant trial | Scale-up evidence under stated operating conditions |
| 5 | Repeated plant production and commercial records | Strongest basis for operating and investor claims |

The simulator should expose this ladder, not hide it. A result containing assumed data remains a hypothesis even when the arithmetic is exact.

---

## 17. Data still required for high credibility

### Materials and chemistry

- geolocated XRF/XRD results and variability;
- moisture and LOI basis;
- mineralogy, calcite/dolomite and kaolinite content;
- alkalis and sulphates;
- raw meal, kiln feed and clinker chemistry;
- free lime and clinker mineral phases;
- fly-ash/GGBFS/calcined-clay reactivity and quality variation.

### Product performance

- strength-development curves;
- setting, soundness and water demand;
- fineness/PSD and grinding response;
- durability and target-standard testing;
- actual recipes paired with batch test results.

### Plant operations

- feed rates and mass balance;
- kiln temperatures, pressures, O2 and CO;
- fuel rate and calorific value;
- actual kWh/t and kcal/kg;
- mill and packer throughput;
- downtime, alarm and maintenance records;
- WHRS output and electricity import/export.

### Commercial data

- dated delivered quotations;
- internal quarry/raw-material cost;
- fuel and electricity contracts;
- labour, maintenance, packing and overhead allocation;
- outbound logistics by market lane;
- vendor CAPEX/OPEX and performance guarantees.

---

## 18. Investor-use protocol

For a fundraise, do not present one simulator screenshot as proof. Present an evidence chain:

```text
Public/official evidence
-> local measured chemistry
-> known reference reproduction
-> controlled candidate screening
-> laboratory validation
-> pilot or plant trial
-> calibrated operational model
-> commercial quotations and market validation
-> independent expert review
```

### Claims the simulator can support after calibration

- documented comparison of alternative recipes;
- identified route bottleneck under stated assumptions;
- traceable cost and carbon scenario ranges;
- sensitivity to raw-material and energy variables;
- evidence-backed selection of candidates for trials;
- transparent technology and data-risk register.

### Claims it cannot support alone

- guaranteed cement strength or compliance;
- guaranteed plant capacity or availability;
- guaranteed market share or price realization;
- bankable CAPEX/OPEX;
- lender-grade feasibility;
- environmental approvals;
- vendor performance guarantees.

Recommended investor outputs:

1. Baseline versus candidate comparison table.
2. Low/base/high sensitivity range.
3. Evidence-confidence matrix.
4. Laboratory and plant-validation report.
5. Bottleneck and phased-CAPEX plan.
6. Cost bridge from direct model to full commercial cost.
7. Explicit open risks and next validation milestones.

---

## 19. Troubleshooting

| Symptom | Meaning | Action |
| --- | --- | --- |
| Material cost is N/A | At least one used material lacks the route-appropriate cost | Fill purchased or internal-feed value in a new cost-book version |
| New material is absent from an old cost book | Cost books are immutable snapshots | Create a new cost-book version after creating the material |
| Delete is blocked | A blend, cost book or run references the record | Archive it instead |
| LSF is N/A | Selected blend is not `raw_meal` | This is correct; do not use LSF as a finished-cement score |
| Achieved output is below target | A machine's cement-equivalent capacity is lower than target | Inspect bottleneck and machine table |
| Machine is below minimum stable load | Target and flow factor underload the stored machine range | Adjust target/route or validate turndown capability |
| Cost appears too low | Missing operating fields or wrong internal/purchased basis | Inspect cost tiers, exclusions and cost book |
| Integrated route double-counts clinker | Purchased clinker price was incorrectly used as internal feed | Put only internal raw-material/feed cost in the internal column |
| Old run does not change after editing | Runs are immutable | Create a new version and a new run; this is expected |
| Chemistry uses zero for an unknown oxide | Current numerical placeholder may look measured | Add the field to data gaps and do not make claims dependent on it |
| Assumed-data warning persists | Starter values or unverified evidence remain | Replace with measured/source-specific versions |
| Low-TRL warning appears | A machine is below TRL 8 | Keep it in R&D scenarios, not the investor base case |
| Custom branched route looks linear | V0.4 composer rebuilds serial edges | Use seeded route carefully or extend to a typed DAG editor |
| Frontend cannot reach API | Backend is stopped or wrong port | Start API on 8100 and frontend on 5173 |
| Python cannot import `brixta_twin` | Wrong Python/environment or editable install missing | Activate `.venv` and reinstall `./apps/api[dev]` |

---

## 20. Data protection and database operations

The default database is:

```text
data/brixta_twin.sqlite3
```

It belongs to this simulator repository and is separate from the crawler database.

### Safe backup while SQLite is running

```bash
cd ~/brixta-cement-twin
mkdir -p backups
sqlite3 data/brixta_twin.sqlite3 ".backup 'backups/brixta_twin_$(date +%Y%m%d_%H%M%S).sqlite3'"
```

### Simple stopped-service backup

Stop the API, then copy the database:

```bash
cd ~/brixta-cement-twin
mkdir -p backups
cp data/brixta_twin.sqlite3 backups/brixta_twin_manual_backup.sqlite3
```

Do not treat `-wal` or `-shm` files as separate databases. They are SQLite runtime files.

Before an upgrade:

1. Stop the API.
2. Back up the database.
3. Back up exported runs.
4. Apply code changes.
5. Start the API and inspect `/api/health`.
6. Run the test suite.

---

## 21. Quality-control checklist before trusting a run

### Identity

- [ ] Material records identify source, date and processing state.
- [ ] Blend percentages total exactly 100%.
- [ ] Exact immutable versions are selected.
- [ ] Route contains the intended machines and order.
- [ ] Cost book has an effective date and evidence.

### Engineering

- [ ] Raw-meal yield is plant-calibrated or clearly assumed.
- [ ] Machine capacities refer to the correct physical streams.
- [ ] Availability comes from evidence or is clearly assumed.
- [ ] Energy intensity is stage-specific, not accidentally plant-wide.
- [ ] Target output and run duration are realistic.

### Commercial

- [ ] Purchased versus internal-feed cost basis is correct.
- [ ] No required material cost is missing.
- [ ] Cost tier and exclusions are stated.
- [ ] Freight, taxes and allocation basis are consistent.
- [ ] Scenario date is appropriate.

### Evidence

- [ ] Warnings are reviewed, not merely counted.
- [ ] Unknown oxide values are declared as gaps.
- [ ] Low-TRL machinery is outside the investor base case.
- [ ] Physical-validation status is clear.
- [ ] Evidence locators are reproducible.

### Comparison

- [ ] Baseline and candidate use comparable boundaries.
- [ ] Only the intended variable changed.
- [ ] Calculation versions match or the difference is disclosed.
- [ ] Low/base/high sensitivity has been run.
- [ ] Candidate has a defined next validation action.

---

## 22. Recommended product roadmap

Priority improvements for the simulator:

1. Nullable chemistry fields so unknown is never represented as zero.
2. Material version editor with side-by-side provenance comparison.
3. Full restore view for archived records.
4. Typed graphical DAG route editor with branches, merges and recycle loops.
5. Separate material-flow, gas-flow and energy-flow edges.
6. Strength, setting and durability models trained only on validated paired data.
7. Monte Carlo uncertainty and sensitivity analysis.
8. Calibration workspace comparing predicted versus measured plant runs.
9. Standards-rule engine linked to accredited test results.
10. Vendor quotation and CAPEX scenario module.
11. NPV/IRR/payback module kept separate from engineering calculations.
12. BRIXTA evidence-bundle import with human approval and provenance.
13. Role-based review, electronic sign-off and audit reporting.

---

## 23. Glossary

| Term | Meaning |
| --- | --- |
| Blend | Versioned mass recipe made from materials and/or other blends |
| Material | Versioned source-specific substance and chemistry record |
| Machine | Versioned process-equipment performance record |
| Route | Ordered process topology using exact machine versions |
| Cost book | Dated immutable commercial-input scenario |
| Run basis | Throughput, duration, tariffs and conversion assumptions |
| Flattening | Resolving nested blends into base-material percentages |
| LSF | Limestone Saturation Factor for raw meal |
| SM | Silica Modulus for raw meal |
| AM | Alumina Modulus for raw meal |
| SCM | Supplementary cementitious material |
| PPC | Portland Pozzolana Cement |
| PSC | Portland Slag Cement |
| LC3 | Limestone Calcined Clay Cement |
| TRL | Technology Readiness Level from 1 to 9 |
| Effective capacity | Rated capacity multiplied by availability |
| Cement-equivalent capacity | Stage capacity translated to finished-cement output basis |
| Bottleneck | Lowest cement-equivalent capacity in the selected route |
| Immutable | Historical record cannot be silently overwritten |
| Evidence class | Declared reliability/source category for an input |

---

## 24. One-page operating sequence

```text
1. Add measured or sourced MATERIALS.
2. Create a dated COST BOOK with route-appropriate costs.
3. Reproduce a known reference BLEND.
4. Select an existing MACHINE ROUTE.
5. Set target, duration and raw-meal yield.
6. RUN the baseline.
7. Read warnings, bottleneck, energy, cost, carbon and evidence.
8. Create one controlled candidate version.
9. RUN with everything else unchanged.
10. Compare in RUNS and export the evidence trail.
11. Validate promising candidates physically.
12. Replace assumptions with measured plant/lab/vendor data.
13. Calibrate predicted versus measured error.
14. Present ranges, evidence and risks - never unsupported certainty.
```

---

## Final operating principle

The value of BRIXTA Cement Twin Lab is not that it makes every answer look precise. Its value is that it makes every assumption, version, dependency, warning and evidence source visible.

Use it to narrow thousands of possibilities into a small number of controlled, testable and economically interesting candidates. Then let laboratory testing, plant trials, commercial evidence and independent engineering review decide what deserves investment.

