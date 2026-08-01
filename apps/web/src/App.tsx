import { useEffect, useMemo, useState } from "react";
import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";

import { API, req } from "./api";
import { BlendWorkspace } from "./BlendWorkspace";
import { CostBookWorkspace } from "./CostBookWorkspace";
import { LibraryManager } from "./LibraryManager";
import { RouteWorkspace } from "./RouteWorkspace";
import type { Blend, CostBook, Machine, Material, Result, Route } from "./types";

function number(value: number | null, unit: string, digits = 1): string {
  return value === null ? "N/A" : `${value.toFixed(digits)}${unit}`;
}

function money(value: number | null): string {
  return value === null ? "N/A" : `₹${value.toFixed(0)}/t`;
}

function pretty(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (match) => match.toUpperCase());
}

function ProcessNode({ data }: NodeProps) {
  const typed = data as {
    label: string;
    stage: string;
    actual: number;
    capacity: number;
    load: number;
    energy: number;
    active: boolean;
    warning: boolean;
  };
  return (
    <div className={`pnode ${typed.active ? "active" : ""} ${typed.warning ? "warning" : ""}`}>
      <Handle type="target" position={Position.Left} />
      <small>{typed.stage}</small>
      <strong>{typed.label}</strong>
      <span>{typed.actual.toFixed(1)} / {typed.capacity.toFixed(1)} t/h stage</span>
      <span>{typed.load.toFixed(1)}% load · {typed.energy.toFixed(1)} kWh/t cement</span>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

const nodeTypes = { process: ProcessNode };

export function App() {
  const [view, setView] = useState("console");
  const [materials, setMaterials] = useState<Material[]>([]);
  const [blends, setBlends] = useState<Blend[]>([]);
  const [machines, setMachines] = useState<Machine[]>([]);
  const [routes, setRoutes] = useState<Route[]>([]);
  const [costBooks, setCostBooks] = useState<CostBook[]>([]);
  const [runs, setRuns] = useState<Result[]>([]);
  const [blendId, setBlendId] = useState("");
  const [routeId, setRouteId] = useState("");
  const [costBookId, setCostBookId] = useState("");
  const [target, setTarget] = useState(100);
  const [duration, setDuration] = useState(24);
  const [electricityTariff, setElectricityTariff] = useState(8.5);
  const [thermalTariff, setThermalTariff] = useState(900);
  const [rawMealYield, setRawMealYield] = useState(0.65);
  const [result, setResult] = useState<Result | null>(null);
  const [visible, setVisible] = useState(0);
  const [error, setError] = useState("");

  async function load() {
    const [loadedMaterials, loadedBlends, loadedMachines, loadedRoutes, loadedCostBooks, loadedRuns] = await Promise.all([
      req<Material[]>("/api/materials"),
      req<Blend[]>("/api/blends"),
      req<Machine[]>("/api/machines"),
      req<Route[]>("/api/routes"),
      req<CostBook[]>("/api/cost-books"),
      req<Result[]>("/api/runs"),
    ]);
    setMaterials(loadedMaterials);
    setBlends(loadedBlends);
    setMachines(loadedMachines);
    setRoutes(loadedRoutes);
    setCostBooks(loadedCostBooks);
    setRuns(loadedRuns);
    setBlendId((current) => current || loadedBlends.find((blend) => blend.blend_id === "blend_reference_ppc")?.blend_id || loadedBlends[0]?.blend_id || "");
    setRouteId((current) => current || loadedRoutes.find((route) => route.route_id === "route_integrated_baseline_v03")?.route_id || loadedRoutes[0]?.route_id || "");
    setCostBookId((current) => current || loadedCostBooks[0]?.cost_book_id || "");
  }

  useEffect(() => {
    void load().catch((caught) => setError(String(caught)));
  }, []);

  useEffect(() => {
    if (result && visible < result.events.length) {
      const timer = window.setTimeout(() => setVisible((current) => current + 1), 70);
      return () => window.clearTimeout(timer);
    }
  }, [result, visible]);

  const route = routes.find((item) => item.route_id === routeId);
  const machineMap = useMemo(() => new Map(machines.map((machine) => [machine.machine_id, machine])), [machines]);
  const metricMap = useMemo(() => new Map(result?.machine_metrics.map((metric) => [metric.machine_id, metric]) ?? []), [result]);
  const active = new Set(result?.events.slice(0, visible).map((event) => event.component) ?? []);
  const nodes: Node[] = (route?.nodes ?? []).map((node) => {
    const machine = machineMap.get(node.machine_id);
    const metric = metricMap.get(node.machine_id);
    return {
      id: node.node_id,
      type: "process",
      position: { x: node.position_x, y: node.position_y },
      draggable: false,
      data: {
        label: node.label,
        stage: machine?.process_stage ?? "unknown",
        actual: metric?.actual_throughput_tph ?? 0,
        capacity: metric?.effective_capacity_tph ?? (machine ? machine.rated_capacity_tph * machine.availability : 0),
        load: metric?.load_percent ?? 0,
        energy: metric?.electricity_kwh_t_cement ?? 0,
        active: active.has(node.machine_id),
        warning: result?.bottleneck_machine_id === node.machine_id,
      },
    };
  });
  const edges: Edge[] = (route?.edges ?? []).map((edge) => ({ id: edge.edge_id, source: edge.source, target: edge.target, animated: Boolean(result) }));

  async function run() {
    setError("");
    setVisible(0);
    const nextResult = await req<Result>("/api/runs", {
      method: "POST",
      body: JSON.stringify({
        blend_id: blendId,
        route_id: routeId,
        cost_book_id: costBookId || null,
        target_output_tph: target,
        duration_hours: duration,
        electricity_inr_kwh: electricityTariff,
        thermal_fuel_inr_mkcal: thermalTariff,
        raw_meal_to_clinker_yield: rawMealYield,
      }),
    });
    setResult(nextResult);
    setRuns((current) => [nextResult, ...current]);
  }

  function openRun(runResult: Result) {
    setResult(runResult);
    setVisible(runResult.events.length);
    setBlendId(runResult.request.blend_id);
    setRouteId(runResult.request.route_id);
    setCostBookId(runResult.request.cost_book_id ?? "");
    setTarget(runResult.request.target_output_tph);
    setDuration(runResult.request.duration_hours);
    setElectricityTariff(runResult.request.electricity_inr_kwh);
    setThermalTariff(runResult.request.thermal_fuel_inr_mkcal);
    setRawMealYield(runResult.request.raw_meal_to_clinker_yield);
    setView("console");
  }

  return (
    <main>
      <header>
        <b>BRIXTA CEMENT TWIN LAB</b>
        <span>{result?.run_id ?? "NO ACTIVE RUN"}</span>
        <nav>
          {["console", "blend", "machine", "route", "costs", "runs", "library"].map((item) => (
            <button className={view === item ? "selected" : ""} onClick={() => setView(item)} key={item}>{item.toUpperCase()}</button>
          ))}
        </nav>
      </header>

      {view === "console" && (
        <>
          <section className="config">
            <label>BLEND<select value={blendId} onChange={(event) => setBlendId(event.target.value)}>{blends.map((blend) => <option value={blend.blend_id} key={blend.blend_id}>{blend.name} · {pretty(blend.blend_class)}</option>)}</select></label>
            <label>ROUTE<select value={routeId} onChange={(event) => setRouteId(event.target.value)}>{routes.map((item) => <option value={item.route_id} key={item.route_id}>{item.name} · {pretty(item.route_kind)}</option>)}</select></label>
            <label>COST BOOK<select value={costBookId} onChange={(event) => { const id = event.target.value; setCostBookId(id); const book = costBooks.find((item) => item.cost_book_id === id); if (book?.electricity_inr_kwh !== null && book?.electricity_inr_kwh !== undefined) setElectricityTariff(book.electricity_inr_kwh); if (book?.thermal_fuel_inr_mkcal !== null && book?.thermal_fuel_inr_mkcal !== undefined) setThermalTariff(book.thermal_fuel_inr_mkcal); }}><option value="">No cost book — legacy fallback</option>{costBooks.map((item) => <option value={item.cost_book_id} key={item.cost_book_id}>{item.name} · v{item.version}</option>)}</select></label>
            <label>TARGET T/H CEMENT<input type="number" min="0.1" value={target} onChange={(event) => setTarget(Number(event.target.value))} /></label>
            <button className="run" disabled={!blendId || !routeId} onClick={() => void run().catch((caught) => setError(String(caught)))}>RUN SIMULATION</button>
          </section>
          <details className="basis-panel">
            <summary>RUN BASIS / TARIFFS / MASS-CONVERSION ASSUMPTIONS</summary>
            <div className="basis-grid">
              <label>DURATION HOURS<input type="number" min="0.1" value={duration} onChange={(event) => setDuration(Number(event.target.value))} /></label>
              <label>ELECTRICITY ₹/KWH<input type="number" min="0" step="0.1" value={electricityTariff} onChange={(event) => setElectricityTariff(Number(event.target.value))} /></label>
              <label>THERMAL FUEL ₹/MILLION KCAL<input type="number" min="0" value={thermalTariff} onChange={(event) => setThermalTariff(Number(event.target.value))} /></label>
              <label>RAW MEAL → CLINKER YIELD<input type="number" min="0.3" max="1" step="0.01" value={rawMealYield} onChange={(event) => setRawMealYield(Number(event.target.value))} /></label>
            </div>
          </details>
          {error && <div className="err">{error}</div>}
          {result && <ResultSummary result={result} />}
          <section className="workspace">
            <div className="topology">
              <div className="title">PROCESS TOPOLOGY / MATERIAL FLOW</div>
              <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView proOptions={{ hideAttribution: true }}>
                <Background gap={28} />
                <Controls />
              </ReactFlow>
            </div>
            <div className="logs">
              <div className="title">EVENT STREAM / CALCULATION TRACE</div>
              {(result?.events ?? []).slice(0, visible).map((event) => (
                <div className={`log ${event.level}`} key={event.sequence}>
                  <span>{event.elapsed_seconds.toFixed(2)}</span><span>{event.level}</span><span>{event.component}</span><span>{event.message}</span>
                </div>
              ))}
              {!result && <div className="empty-state">Run a scenario to populate the trace.</div>}
            </div>
          </section>
          {result && <RunReport result={result} />}
        </>
      )}

      {view === "blend" && <BlendWorkspace materials={materials} blends={blends} onMaterialCreated={(material) => setMaterials((current) => [...current, material])} onBlendCreated={(blend) => { setBlends((current) => [...current, blend]); setBlendId(blend.blend_id); setView("console"); }} />}
      {view === "machine" && <MachineGuide done={(machine) => { setMachines((current) => [...current, machine]); setView("route"); }} />}
      {view === "route" && <RouteWorkspace machines={machines} routes={routes} done={(newRoute) => { setRoutes((current) => [...current, newRoute]); setRouteId(newRoute.route_id); setView("console"); }} />}
      {view === "costs" && <CostBookWorkspace materials={materials} costBooks={costBooks} done={(costBook) => { setCostBooks((current) => [...current, costBook]); setCostBookId(costBook.cost_book_id); setView("console"); }} />}
      {view === "runs" && <RunLibrary runs={runs} openRun={openRun} />}
      {view === "library" && <LibraryManager materials={materials} blends={blends} machines={machines} routes={routes} costBooks={costBooks} refresh={load} />}
    </main>
  );
}

function ResultSummary({ result }: { result: Result }) {
  const metrics = [
    ["TARGET OUTPUT", number(result.request.target_output_tph, " t/h")],
    ["ACHIEVED OUTPUT", number(result.achievable_output_tph, " t/h")],
    ["BOTTLENECK", result.bottleneck_machine_name ?? "Unknown"],
    ["ELECTRICITY", number(result.electricity_kwh_t, " kWh/t")],
    ["THERMAL", number(result.thermal_kcal_kg, " kcal/kg")],
    ["DIRECT MODEL COST", money(result.direct_model_cost_inr_t)],
    ["PLANT CASH COST", money(result.cost_breakdown?.plant_cash_cost_inr_t ?? null)],
    ["FULL COST", money(result.cost_breakdown?.full_cost_inr_t ?? null)],
    ["MATERIAL CO₂", number(result.estimated_co2_kg_t, " kg/t", 0)],
    ["RUN OUTPUT", number(result.total_output_tonnes, " t", 0)],
  ];
  return (
    <section className="result-summary" aria-label="Simulation result summary">
      {metrics.map(([label, value]) => <div key={label}><small>{label}</small><strong>{value}</strong></div>)}
    </section>
  );
}

function RunReport({ result }: { result: Result }) {
  return (
    <section className="run-report">
      <div className="report-heading">
        <div><strong>AUDITABLE RUN REPORT</strong><span>{new Date(result.created_at).toLocaleString()} · model {result.calculation_version}</span><span>{result.blend_snapshot ? `${result.blend_snapshot.name} · ${result.blend_snapshot.blend_id} · v${result.blend_snapshot.version}` : result.request.blend_id}</span><span>{result.route_snapshot ? `${result.route_snapshot.name} · ${result.route_snapshot.route_id} · v${result.route_snapshot.version}` : result.request.route_id}</span><span>{result.cost_book_snapshot ? `${result.cost_book_snapshot.name} · ${result.cost_book_snapshot.cost_book_id} · v${result.cost_book_snapshot.version}` : "No versioned cost book"}</span></div>
        <div className="inline-actions"><a className="export" href={`${API}/api/runs/${result.run_id}/export.csv`}>EXPORT CSV</a><a className="export" href={`${API}/api/runs/${result.run_id}/export.json`}>EXPORT JSON</a></div>
      </div>

      <details open>
        <summary>VALIDATION / {result.validation.filter((item) => item.severity !== "info").length} WARNINGS</summary>
        <div className="validation-list">
          {result.validation.map((item, index) => <div className={`validation ${item.severity}`} key={`${item.code}-${index}`}><code>{item.severity.toUpperCase()} · {item.code}</code><span>{item.message}</span></div>)}
        </div>
      </details>

      <div className="report-grid">
        <details open><summary>WEIGHTED CHEMISTRY / MASS %</summary><div className="chemistry-grid">{Object.entries(result.chemistry).map(([oxide, value]) => <div key={oxide}><small>{oxide.toUpperCase()}</small><strong>{value.toFixed(3)}%</strong></div>)}</div><div className="moduli"><span>LSF {result.lsf === null ? "N/A — raw meal only" : result.lsf.toFixed(2)}</span><span>SM {result.silica_modulus?.toFixed(3) ?? "N/A"}</span><span>AM {result.alumina_modulus?.toFixed(3) ?? "N/A"}</span></div></details>
        <details open><summary>COST / INCLUDED AND EXCLUDED</summary>{result.cost_breakdown && <div className="key-values"><span>Materials</span><strong>{money(result.cost_breakdown.materials_inr_t)}</strong><span>Electricity</span><strong>{money(result.cost_breakdown.electricity_inr_t)}</strong><span>Thermal fuel</span><strong>{money(result.cost_breakdown.thermal_inr_t)}</strong><span>Direct model total</span><strong>{money(result.cost_breakdown.direct_model_cost_inr_t)}</strong><span>Packing</span><strong>{money(result.cost_breakdown.packing_inr_t)}</strong><span>Labour</span><strong>{money(result.cost_breakdown.labour_inr_t)}</strong><span>Maintenance</span><strong>{money(result.cost_breakdown.maintenance_inr_t)}</strong><span>Other variable</span><strong>{money(result.cost_breakdown.other_variable_inr_t)}</strong><span>Plant cash cost</span><strong>{money(result.cost_breakdown.plant_cash_cost_inr_t)}</strong><span>Factory overhead</span><strong>{money(result.cost_breakdown.factory_overhead_inr_t)}</strong><span>Outbound logistics</span><strong>{money(result.cost_breakdown.outbound_logistics_inr_t)}</strong><span>Full cost estimate</span><strong>{money(result.cost_breakdown.full_cost_inr_t)}</strong></div>}<p className="note">Cost book: {result.cost_breakdown?.cost_book_name ?? "none"}. Excludes: {result.cost_breakdown?.excluded_costs.join(", ")}</p></details>
        <details open><summary>ENERGY / RUN TOTALS</summary>{result.energy_breakdown && <div className="key-values"><span>Electricity intensity</span><strong>{number(result.energy_breakdown.electricity_kwh_t, " kWh/t")}</strong><span>Thermal intensity</span><strong>{number(result.energy_breakdown.thermal_kcal_kg, " kcal/kg")}</strong><span>Total electricity</span><strong>{number(result.energy_breakdown.total_electricity_mwh, " MWh")}</strong><span>Total thermal energy</span><strong>{number(result.energy_breakdown.total_thermal_gcal, " Gcal")}</strong></div>}</details>
        <details open><summary>CARBON / MATERIAL SCOPE</summary>{result.carbon_breakdown && <div className="key-values"><span>Material CO₂ intensity</span><strong>{number(result.carbon_breakdown.materials_kg_co2_t, " kg/t", 1)}</strong><span>Run material output</span><strong>{number(result.carbon_breakdown.total_materials_tonnes, " t", 1)}</strong><span>Total material CO₂</span><strong>{result.carbon_breakdown.total_materials_kg_co2 === null ? "N/A" : number(result.carbon_breakdown.total_materials_kg_co2 / 1000, " t CO₂", 1)}</strong></div>}<p className="note">Excludes: {result.carbon_breakdown?.exclusions.join(", ")}</p></details>
      </div>

      <details open><summary>MACHINE CAPACITY AND ENERGY BREAKDOWN</summary><div className="table-responsive"><table><thead><tr><th>Machine / immutable version</th><th>Stage</th><th>Actual stage t/h</th><th>Effective stage cap.</th><th>Cement-eq. cap.</th><th>Load</th><th>kWh/t cement</th><th>kcal/kg cement</th></tr></thead><tbody>{result.machine_metrics.map((item) => { const snapshot = result.machine_snapshots.find((machine) => machine.machine_id === item.machine_id); return <tr key={item.node_id}><td>{item.machine_name} · {item.machine_id} · v{snapshot?.version ?? "?"}</td><td>{pretty(item.process_stage)}</td><td>{item.actual_throughput_tph.toFixed(2)}</td><td>{item.effective_capacity_tph.toFixed(2)}</td><td>{item.cement_equivalent_capacity_tph?.toFixed(2) ?? "N/A"}</td><td>{item.load_percent.toFixed(1)}%</td><td>{item.electricity_kwh_t_cement.toFixed(2)}</td><td>{item.thermal_kcal_kg_cement.toFixed(2)}</td></tr>; })}</tbody></table></div></details>

      <details><summary>MATERIAL MASS / COST / CARBON BREAKDOWN</summary><div className="table-responsive"><table><thead><tr><th>Material / immutable version</th><th>Mass %</th><th>t/h</th><th>t/run</th><th>Applied ₹/t material</th><th>₹/t cement</th><th>Cost basis</th><th>kg CO₂/t cement</th><th>Evidence</th></tr></thead><tbody>{result.material_metrics.map((item) => { const snapshot = result.material_snapshots.find((material) => material.material_id === item.material_id); return <tr key={item.material_id}><td>{item.material_name} · {item.material_id} · v{snapshot?.version ?? "?"}</td><td>{item.percentage.toFixed(3)}</td><td>{item.tonnes_per_hour.toFixed(2)}</td><td>{item.tonnes_per_run.toFixed(1)}</td><td>{item.applied_unit_cost_inr_t?.toFixed(0) ?? "N/A"}</td><td>{item.cost_inr_t_cement?.toFixed(0) ?? "N/A"}</td><td>{item.cost_basis}</td><td>{item.co2_kg_t_cement?.toFixed(1) ?? "N/A"}</td><td>{item.evidence_class}</td></tr>; })}</tbody></table></div></details>

      <div className="report-grid">
        <details><summary>ASSUMPTION REGISTER</summary><div className="audit-list">{result.assumptions.map((item) => <p key={item.key}><code>{item.key}</code><strong>{item.value}</strong><span>{item.basis}</span></p>)}</div></details>
        <details><summary>EVIDENCE REFERENCES</summary><div className="audit-list">{result.evidence_references.map((item, index) => <p key={`${item.source_title}-${index}`}><code>{item.evidence_class}</code><strong>{item.source_title}</strong><span>{item.page ? `Page/table ${item.page}` : "No page locator"}</span></p>)}</div></details>
      </div>
    </section>
  );
}

function RunLibrary({ runs, openRun }: { runs: Result[]; openRun: (run: Result) => void }) {
  const [selected, setSelected] = useState<string[]>([]);
  const compared = runs.filter((run) => selected.includes(run.run_id));
  function toggle(runId: string) {
    setSelected((current) => current.includes(runId) ? current.filter((item) => item !== runId) : current.length >= 6 ? current : [...current, runId]);
  }
  return (
    <section className="library run-library">
      <div className="title">IMMUTABLE RUN LIBRARY / {runs.length} AUDIT RECORDS</div>
      {runs.length === 0 && <div className="empty-state">No saved runs yet. Every completed simulation will appear here.</div>}
      {runs.map((run) => <div className="run-row" key={run.run_id}><input aria-label={`Compare ${run.run_id}`} type="checkbox" checked={selected.includes(run.run_id)} onChange={() => toggle(run.run_id)} /><code>{run.run_id}</code><span>{run.blend_snapshot?.name ?? run.request.blend_id}<small>{run.route_snapshot?.name ?? run.request.route_id} · {new Date(run.created_at).toLocaleString()}</small></span><span>{run.achievable_output_tph.toFixed(1)} t/h<small>{money(run.direct_model_cost_inr_t)} · {number(run.estimated_co2_kg_t, " kg CO₂/t", 0)}</small></span><button onClick={() => openRun(run)}>OPEN</button></div>)}
      {compared.length > 0 && <div className="comparison"><div className="title">SIDE-BY-SIDE COMPARISON / {compared.length} RUNS</div><div className="table-responsive"><table><thead><tr><th>Run</th><th>Blend</th><th>Route</th><th>Output t/h</th><th>Bottleneck</th><th>kWh/t</th><th>kcal/kg</th><th>Direct ₹/t</th><th>CO₂ kg/t</th><th>Warnings</th></tr></thead><tbody>{compared.map((run) => <tr key={run.run_id}><td>{run.run_id.slice(-8)}</td><td>{run.blend_snapshot?.name ?? run.request.blend_id}</td><td>{run.route_snapshot?.name ?? run.request.route_id}</td><td>{run.achievable_output_tph.toFixed(1)}</td><td>{run.bottleneck_machine_name ?? "Unknown"}</td><td>{run.electricity_kwh_t.toFixed(1)}</td><td>{run.thermal_kcal_kg.toFixed(1)}</td><td>{run.direct_model_cost_inr_t?.toFixed(0) ?? "N/A"}</td><td>{run.estimated_co2_kg_t?.toFixed(0) ?? "N/A"}</td><td>{run.warnings.length}</td></tr>)}</tbody></table></div></div>}
    </section>
  );
}

function MachineGuide({ done }: { done: (machine: Machine) => void }) {
  const [kind, setKind] = useState("standard");
  const [name, setName] = useState("New Process Machine");
  const [stage, setStage] = useState("cement_grinding");
  const [capacity, setCapacity] = useState(100);
  const [minimum, setMinimum] = useState(40);
  const [availability, setAvailability] = useState(0.9);
  const [energy, setEnergy] = useState(20);
  const [heat, setHeat] = useState(0);
  const [capex, setCapex] = useState(0);
  const [trl, setTrl] = useState(5);
  const [source, setSource] = useState("Unverified machine input — replace with vendor source");

  async function save() {
    const base = { machine_kind: kind, name, process_stage: stage, rated_capacity_tph: capacity, minimum_stable_tph: minimum, availability, specific_electricity_kwh_t: energy, specific_heat_kcal_kg: heat, capex_inr_crore: capex, technology_readiness_level: trl, evidence: [{ evidence_class: "unverified", source_title: source }] };
    const payload = kind === "thermal" ? { ...base, maximum_temperature_c: stage === "clay_calcination" ? 850 : 1450, residence_time_minutes: 30, conversion_fraction: 0.95, product_state: stage === "clay_calcination" ? "calcined_clay" : "clinker" } : { ...base, input_material: "solid", output_material: "solid" };
    done(await req<Machine>("/api/machines", { method: "POST", body: JSON.stringify(payload) }));
  }

  return <section className="guide"><h2>GUIDE / NEW MACHINE</h2><div className="form-grid two"><label>TYPE<select value={kind} onChange={(event) => setKind(event.target.value)}><option value="standard">Standard</option><option value="thermal">Thermal transformation</option></select></label><label>NAME<input value={name} onChange={(event) => setName(event.target.value)} /></label><label>STAGE<select value={stage} onChange={(event) => setStage(event.target.value)}><option value="crushing">Crushing</option><option value="raw_grinding">Raw grinding</option><option value="thermal_transformation">Clinker thermal transformation</option><option value="clay_calcination">Clay calcination</option><option value="cement_grinding">Cement grinding</option><option value="packing_dispatch">Packing</option></select></label><label>RATED CAPACITY T/H<input type="number" value={capacity} onChange={(event) => setCapacity(Number(event.target.value))} /></label><label>MINIMUM STABLE T/H<input type="number" value={minimum} onChange={(event) => setMinimum(Number(event.target.value))} /></label><label>AVAILABILITY 0–1<input type="number" min="0.01" max="1" step="0.01" value={availability} onChange={(event) => setAvailability(Number(event.target.value))} /></label><label>ELECTRICITY KWH/T STAGE<input type="number" value={energy} onChange={(event) => setEnergy(Number(event.target.value))} /></label><label>THERMAL KCAL/KG STAGE<input type="number" value={heat} onChange={(event) => setHeat(Number(event.target.value))} /></label><label>CAPEX ₹ CRORE<input type="number" value={capex} onChange={(event) => setCapex(Number(event.target.value))} /></label><label>TRL 1–9<input type="number" min="1" max="9" value={trl} onChange={(event) => setTrl(Number(event.target.value))} /></label></div><label>EVIDENCE / VENDOR SOURCE<input value={source} onChange={(event) => setSource(event.target.value)} /></label><pre>{trl >= 8 ? "PASS  Commercial maturity threshold" : "WARN  TRL below 8\nBLOCK Investor base case; R&D scenario only"}</pre><button className="run" disabled={minimum > capacity} onClick={() => void save()}>CREATE IMMUTABLE MACHINE VERSION</button></section>;
}
