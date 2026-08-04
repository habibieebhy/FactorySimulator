# BRIXTA 0.8.0 — PPC-to-LC3 Retrofit Designer

## Product boundary

This release is the first bounded vertical slice of the proposed factory-wide formulation and optimisation platform. It does not attempt to model every cement-factory operation yet. It proves the architecture on one commercially useful question:

> Given an existing PPC blend and plant route, what LC3 formulations and retrofit pathways are technically plausible, what assets are missing, which candidates are Pareto-efficient, how robust are they to chemistry/dosage variation, and how can the selected model be delivered as an editable Excel workbook?

## What was added

### 1. Multi-level formulation chain

Each candidate contains a linked formulation chain covering:

- quarry / stockpile basis;
- raw meal;
- kiln feed;
- clinker constituent;
- finished LC3 cement;
- thermal-fuel duty;
- electrical-energy duty.

The chain preserves the difference between a material, a nested blend, a process transformation and a finished-cement component.

### 2. Staged deterministic solver

The solver does not enumerate the complete combinatorial space. It uses:

1. percentage-bound and sum-to-100 feasibility pruning;
2. clay-to-limestone ratio screening;
3. multiple engineering seed formulations;
4. bounded pairwise coordinate descent at progressively finer step sizes;
5. objective profiles for cost, CO2, output, energy and robustness;
6. local neighbourhood exploration around each optimum;
7. Pareto dominance filtering;
8. low / typical / high chemistry and dosage stress testing.

No AI model is used.

### 3. Retrofit asset diagnosis

The designer checks the selected plant route and reports required or recommended assets, including:

- clay calcination line for onsite raw-clay activation;
- calcined-clay storage and extraction;
- independent clay / limestone / gypsum dosing;
- missing cement-grinding capacity.

Reference capacity, CAPEX and energy figures are explicitly labelled as replaceable screening assumptions.

### 4. Candidate persistence

A selected candidate can be saved as an immutable `finished_cement` LC3 blend. Existing material and nested-blend IDs are preserved.

### 5. Excel engineering compiler

The selected candidate exports as a formula-driven `.xlsx` workbook containing:

- model control;
- assumption register;
- editable material/formulation table;
- multi-level formulation chain;
- Pareto shortlist;
- mass balance;
- energy and capacity;
- cost and CO2;
- robustness stress tests;
- data-to-replace register;
- calculation trace;
- dashboard.

Blue cells are plant-editable. Yellow cells are BRIXTA reference assumptions. Grey cells are formulas.

## API endpoints

```text
POST /api/retrofit/ppc-to-lc3/design
GET  /api/retrofit-studies
GET  /api/retrofit-studies/{study_id}
GET  /api/retrofit-studies/{study_id}/export.xlsx
POST /api/retrofit-studies/{study_id}/candidates/{candidate_id}/save-blend
```

## Frontend location

```text
RETROFIT → PPC → LC3 RETROFIT DESIGNER
```

## Deliberate limitations

This release is a screening and engineering-design model. It does not yet provide:

- standards certification;
- exact strength prediction;
- detailed sulfate-balance optimisation;
- plant-calibrated clay reactivity;
- dynamic silo/inventory simulation;
- detailed CAPEX estimation;
- full factory-wide scheduling;
- automatic equipment sizing beyond the reference clay-calciner gap;
- a macro-enabled Excel optimiser.

The next kernel should generalise the formulation-chain and equipment-gap concepts into typed process streams, equipment ports, inventories, equation definitions and time-dependent factory simulation.
