# BRIXTA Cement Twin Lab

A separate, deterministic cement experimentation repository. It combines an industrial
process topology, animated material flows, chronological calculation logs, guided blend
creation, guided machinery creation, machine-swap routes and SQLite persistence.

It does **not** import the BRIXTA crawler or RAG as editable Python packages. Evidence
integration is through reviewed JSON/CSV/API records. LLMs may retrieve evidence; the
Python engine owns calculations.

## Current V1

- Meghalaya/reference material library;
- reference PPC and LC3 candidate;
- weighted oxide chemistry;
- LSF, SM and AM;
- route bottlenecks and effective capacity;
- electricity, thermal energy, cost and CO2 estimates;
- animated React Flow process topology;
- raw simulation event stream;
- guided new-blend workflow;
- guided standard/thermal machine workflow;
- TRL investor-base-case warnings;
- guided machine replacement and immutable route copy;
- FastAPI API and SQLite data store.

Starter values are literature or assumptions. Replace them with laboratory, plant and
vendor evidence before making an investment claim.

## Install

Requirements: Python 3.11+, Node.js 20+, npm.

```bash
cd brixta-cement-twin
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e "./apps/api[dev]"
cd apps/web
npm install
```

This editable install uses the local `apps/api` folder. It does not clone GitHub or
install another BRIXTA repository.

## Start

Terminal 1:

```bash
cd brixta-cement-twin
source .venv/bin/activate
uvicorn brixta_twin.app:app --reload --port 8100
```

Terminal 2:

```bash
cd brixta-cement-twin/apps/web
npm run dev
```

Open `http://127.0.0.1:5173`. API docs are at `http://127.0.0.1:8100/docs`.

## Workflow

1. Run the reference PPC through the baseline route.
2. Open `BLEND`, define a candidate totaling exactly 100%, and save it.
3. Run the candidate through the unchanged route.
4. Open `MACHINE`, define a standard or thermal machine and assign its TRL.
5. Open `ROUTE`, choose a baseline node and pin the new machine into a copied route.
6. Compare output, bottleneck, energy, cost, carbon, warnings and logs.
7. Replace assumptions with measured evidence and validate physically.

## Physics and calculations

```text
oxide_blend = sum(component_fraction * component_oxide)
LSF = CaO / (2.8 SiO2 + 1.18 Al2O3 + 0.65 Fe2O3)
SM = SiO2 / (Al2O3 + Fe2O3)
AM = Al2O3 / Fe2O3
effective_capacity = rated_capacity * availability
route_capacity = minimum(effective_machine_capacities)
```

## Tests

```bash
pytest apps/api/tests -q
cd apps/web
npm run typecheck
npm run build
```

## Next milestones

- typed material ports and drag-to-connect route builder;
- evidence-bundle import and human approval queue;
- sample variability and Monte Carlo simulation;
- laboratory validation ledger;
- model-versus-measurement calibration;
- strength/performance models;
- vendor performance curves;
- CAPEX/OPEX and investor scenario exports.

The interface intentionally looks like SCADA logs plus an engineering process diagram,
not a decorative SaaS dashboard.
