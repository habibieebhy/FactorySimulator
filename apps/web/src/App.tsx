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
import { AccuracyWorkspace } from "./AccuracyWorkspace";
import { BlendWorkspace } from "./BlendWorkspace";
import { CostBookWorkspace } from "./CostBookWorkspace";
import { LibraryManager } from "./LibraryManager";
import { RouteWorkspace } from "./RouteWorkspace";
import type { Blend, CostBook, Machine, Material, QualityMeasurements, Result, Route, RouteRecommendationSet } from "./types";

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
    outputProduct: string;
    active: boolean;
    warning: boolean;
  };
  return (
    <div className={`pnode ${typed.active ? "active" : ""} ${typed.warning ? "warning" : ""}`}>
      <Handle type="target" position={Position.Left} />
      <small>{typed.stage}</small>
      <strong>{typed.label}</strong>
      <span>{typed.actual.toFixed(1)} / {typed.capacity.toFixed(1)} t/h stage</span>
      <span>{typed.load.toFixed(1)}% load · {typed.energy.toFixed(1)} kWh/t {typed.outputProduct}</span>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

const nodeTypes = { process: ProcessNode };

export function App() {
  const [view, setView] = useState("console");
  const [materials, setMaterials] = useState<Material[]>([]);
  const [archivedMaterials, setArchivedMaterials] = useState<Material[]>([]);
  const [blends, setBlends] = useState<Blend[]>([]);
  const [archivedBlends, setArchivedBlends] = useState<Blend[]>([]);
  const [machines, setMachines] = useState<Machine[]>([]);
  const [archivedMachines, setArchivedMachines] = useState<Machine[]>([]);
  const [routes, setRoutes] = useState<Route[]>([]);
  const [archivedRoutes, setArchivedRoutes] = useState<Route[]>([]);
  const [costBooks, setCostBooks] = useState<CostBook[]>([]);
  const [archivedCostBooks, setArchivedCostBooks] = useState<CostBook[]>([]);
  const [runs, setRuns] = useState<Result[]>([]);
  const [blendId, setBlendId] = useState("");
  const [routeId, setRouteId] = useState("");
  const [costBookId, setCostBookId] = useState("");
  const [target, setTarget] = useState(100);
  const [duration, setDuration] = useState(24);
  const [electricityTariff, setElectricityTariff] = useState(8.5);
  const [thermalTariff, setThermalTariff] = useState(900);
  const [rawMealYield, setRawMealYield] = useState(0.65);
  const [autoMassConversion, setAutoMassConversion] = useState(true);
  const [chemistryScenario, setChemistryScenario] = useState<"low" | "typical" | "high">("typical");
  const [targetBlaine, setTargetBlaine] = useState(320);
  const [fuelMaterialId, setFuelMaterialId] = useState("");
  const [fuelRate, setFuelRate] = useState("");
  const [kilnMoisture, setKilnMoisture] = useState("");
  const [kilnOxygen, setKilnOxygen] = useState("");
  const [kilnTemperature, setKilnTemperature] = useState("");
  const [freeLime, setFreeLime] = useState("");
  const [quality, setQuality] = useState<Record<keyof QualityMeasurements, string>>({ blaine_m2_kg: "", initial_setting_minutes: "", final_setting_minutes: "", le_chatelier_mm: "", autoclave_expansion_percent: "", strength_3d_mpa: "", strength_7d_mpa: "", strength_28d_mpa: "" });
  const [routeAdvice, setRouteAdvice] = useState<RouteRecommendationSet | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [visible, setVisible] = useState(0);
  const [error, setError] = useState("");

  async function load() {
    const [loadedMaterials, loadedBlends, loadedMachines, loadedRoutes, loadedCostBooks, loadedRuns] = await Promise.all([
      req<Material[]>("/api/materials?include_archived=true"),
      req<Blend[]>("/api/blends?include_archived=true"),
      req<Machine[]>("/api/machines?include_archived=true"),
      req<Route[]>("/api/routes?include_archived=true"),
      req<CostBook[]>("/api/cost-books?include_archived=true"),
      req<Result[]>("/api/runs"),
    ]);
    const activeMaterials = loadedMaterials.filter((item) => !item.archived);
    const activeBlends = loadedBlends.filter((item) => !item.archived);
    const activeMachines = loadedMachines.filter((item) => !item.archived);
    const activeRoutes = loadedRoutes.filter((item) => !item.archived);
    const activeCostBooks = loadedCostBooks.filter((item) => !item.archived);
    setMaterials(activeMaterials);
    setArchivedMaterials(loadedMaterials.filter((item) => item.archived));
    setBlends(activeBlends);
    setArchivedBlends(loadedBlends.filter((item) => item.archived));
    setMachines(activeMachines);
    setArchivedMachines(loadedMachines.filter((item) => item.archived));
    setRoutes(activeRoutes);
    setArchivedRoutes(loadedRoutes.filter((item) => item.archived));
    setCostBooks(activeCostBooks);
    setArchivedCostBooks(loadedCostBooks.filter((item) => item.archived));
    setRuns(loadedRuns);
    setBlendId((current) => activeBlends.some((blend) => blend.blend_id === current) ? current : activeBlends.find((blend) => blend.blend_id === "blend_reference_ppc")?.blend_id || activeBlends[0]?.blend_id || "");
    setRouteId((current) => activeRoutes.some((route) => route.route_id === current) ? current : activeRoutes.find((route) => route.route_id === "route_integrated_baseline_v03")?.route_id || activeRoutes[0]?.route_id || "");
    setCostBookId((current) => activeCostBooks.some((book) => book.cost_book_id === current) ? current : activeCostBooks[0]?.cost_book_id || "");
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

  useEffect(() => {
    if (!blendId) { setRouteAdvice(null); return; }
    const timer = window.setTimeout(() => {
      req<RouteRecommendationSet>(`/api/route-recommendations?blend_id=${encodeURIComponent(blendId)}&target_output_tph=${target}&selected_route_id=${encodeURIComponent(routeId)}`)
        .then(setRouteAdvice)
        .catch(() => setRouteAdvice(null));
    }, 160);
    return () => window.clearTimeout(timer);
  }, [blendId, routeId, target, routes]);

  const route = routes.find((item) => item.route_id === routeId);
  const selectedBlend = blends.find((item) => item.blend_id === blendId);
  const selectedCostBook = costBooks.find((item) => item.cost_book_id === costBookId);
  const effectiveElectricityTariff = selectedCostBook?.electricity_inr_kwh ?? electricityTariff;
  const effectiveThermalTariff = selectedCostBook?.thermal_fuel_inr_mkcal ?? thermalTariff;
  const selectedOutputProduct = route?.route_kind === "clinker_only"
    ? "CLINKER"
    : selectedBlend?.blend_class === "raw_meal"
      ? "RAW MEAL"
      : selectedBlend?.blend_class === "raw_material_stockpile"
        ? "RAW MATERIAL"
        : selectedBlend?.blend_class === "premix"
          ? "PREMIX"
          : "CEMENT";
  const machineMap = useMemo(() => new Map(machines.map((machine) => [machine.machine_id, machine])), [machines]);
  const routeHasCementGrinding = (route?.nodes ?? []).some(
    (node) => machineMap.get(node.machine_id)?.process_stage === "cement_grinding",
  );
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
        energy: metric?.electricity_kwh_t_output ?? 0,
        outputProduct: (result?.output_product ?? selectedOutputProduct).toLowerCase(),
        active: active.has(node.machine_id),
        warning: result?.bottleneck_machine_id === node.machine_id,
      },
    };
  });
  const edges: Edge[] = (route?.edges ?? []).map((edge) => ({ id: edge.edge_id, source: edge.source, target: edge.target, animated: Boolean(result) }));

  const optionalNumber = (value: string) => value.trim() === "" ? null : Number(value);
  function runPayload() {
    return {
      blend_id: blendId, route_id: routeId, cost_book_id: costBookId || null,
      target_output_tph: target, duration_hours: duration,
      electricity_inr_kwh: effectiveElectricityTariff, thermal_fuel_inr_mkcal: effectiveThermalTariff,
      raw_meal_to_clinker_yield: rawMealYield, auto_mass_conversion: autoMassConversion,
      chemistry_scenario: chemistryScenario,
      target_blaine_m2_kg: routeHasCementGrinding ? targetBlaine || null : null,
      fuel_material_id: fuelMaterialId || null, fuel_rate_kg_t_clinker: optionalNumber(fuelRate),
      kiln_feed_moisture_percent: optionalNumber(kilnMoisture), kiln_oxygen_percent: optionalNumber(kilnOxygen),
      kiln_temperature_c: optionalNumber(kilnTemperature), clinker_free_lime_percent: optionalNumber(freeLime),
      quality_measurements: Object.fromEntries(Object.entries(quality).map(([key, value]) => [key, optionalNumber(value)])),
    };
  }

  async function run() {
    setError("");
    setVisible(0);
    const nextResult = await req<Result>("/api/runs", {
      method: "POST",
      body: JSON.stringify(runPayload()),
    });
    setResult(nextResult);
    setRuns((current) => [nextResult, ...current]);
  }

  async function runVariability() {
    setError(""); setVisible(0);
    const results = await req<Result[]>("/api/runs/variability", { method: "POST", body: JSON.stringify(runPayload()) });
    const typical = results.find((item) => item.chemistry_scenario === "typical") ?? results[0] ?? null;
    setResult(typical); setVisible(typical?.events.length ?? 0); setRuns((current) => [...results, ...current]);
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
    setAutoMassConversion(runResult.request.auto_mass_conversion);
    setChemistryScenario(runResult.request.chemistry_scenario);
    setTargetBlaine(runResult.request.target_blaine_m2_kg ?? 320);
    setFuelMaterialId(runResult.request.fuel_material_id ?? "");
    setFuelRate(runResult.request.fuel_rate_kg_t_clinker?.toString() ?? "");
    setKilnMoisture(runResult.request.kiln_feed_moisture_percent?.toString() ?? "");
    setKilnOxygen(runResult.request.kiln_oxygen_percent?.toString() ?? "");
    setKilnTemperature(runResult.request.kiln_temperature_c?.toString() ?? "");
    setFreeLime(runResult.request.clinker_free_lime_percent?.toString() ?? "");
    const measured = runResult.request.quality_measurements ?? {};
    setQuality((current) => Object.fromEntries(Object.keys(current).map((key) => [key, measured[key as keyof QualityMeasurements]?.toString() ?? ""])) as Record<keyof QualityMeasurements, string>);
    setView("console");
  }

  return (
    <main>
      <header>
        <b>BRIXTA CEMENT TWIN LAB</b>
        <span>{result?.run_id ?? "NO ACTIVE RUN"}</span>
        <nav>
          {["console", "blend", "machine", "route", "accuracy", "costs", "runs", "library"].map((item) => (
            <button className={view === item ? "selected" : ""} onClick={() => setView(item)} key={item}>{item.toUpperCase()}</button>
          ))}
        </nav>
      </header>

      {view === "console" && (
        <>
          <section className="config">
            <label>BLEND<select value={blendId} onChange={(event) => setBlendId(event.target.value)}>{blends.map((blend) => <option value={blend.blend_id} key={blend.blend_id}>{blend.name} · {pretty(blend.blend_class)}</option>)}</select></label>
            <label>ROUTE<select value={routeId} onChange={(event) => setRouteId(event.target.value)}>{routes.map((item) => <option value={item.route_id} key={item.route_id}>{item.name} · {pretty(item.route_kind)}</option>)}</select></label>
            <label>COST BOOK<select value={costBookId} onChange={(event) => setCostBookId(event.target.value)}><option value="">No cost book — use run tariffs</option>{costBooks.map((item) => <option value={item.cost_book_id} key={item.cost_book_id}>{item.name} · v{item.version}</option>)}</select></label>
            <label>TARGET T/H {selectedOutputProduct}<input type="number" min="0.1" value={target} onChange={(event) => setTarget(Number(event.target.value))} /></label>
            <button className="run" disabled={!blendId || !routeId} onClick={() => void run().catch((caught) => setError(String(caught)))}>RUN SIMULATION</button>
            <button disabled={!blendId || !routeId} onClick={() => void runVariability().catch((caught) => setError(String(caught)))}>RUN LOW / TYPICAL / HIGH</button>
          </section>
          {routeAdvice?.selected && <section className={`route-explainer ${routeAdvice.selected.compatible ? "compatible" : "incompatible"}`}><div><strong>SELECTED ROUTE · {routeAdvice.selected.route_name}</strong><span>{routeAdvice.selected.description}</span><code>{routeAdvice.selected.flow_summary}</code></div><div><strong>{routeAdvice.selected.compatibility_score.toFixed(0)}/100 · {routeAdvice.selected.predicted_output_tph?.toFixed(1) ?? "N/A"} t/h</strong><span>{routeAdvice.selected.compatible ? "Compatible screening route" : `Missing: ${routeAdvice.selected.missing_stages.map(pretty).join(", ") || "usable capacity"}`}</span><span>Bottleneck: {routeAdvice.selected.bottleneck_machine_name ?? "N/A"}</span></div></section>}
          {routeAdvice && <details className="route-shortlist"><summary>NEAREST ALTERNATIVE ROUTES TO TRY / RANKED FOR THIS BLEND AND TARGET</summary><div className="recommendation-grid">{routeAdvice.recommendations.filter((advice) => advice.route_id !== routeId).slice(0, 5).map((advice, index) => <div key={advice.route_id}><strong>#{index + 1} · {advice.route_name}</strong><span>{advice.compatibility_score.toFixed(0)}/100 · {advice.predicted_output_tph?.toFixed(1) ?? "N/A"} t/h · {advice.bottleneck_machine_name ?? "no bottleneck"}</span><span>{advice.reasons.join(" · ")}</span><button onClick={() => setRouteId(advice.route_id)}>TRY THIS ROUTE</button></div>)}</div></details>}
          <details className="basis-panel">
            <summary>RUN BASIS / TARIFFS / MASS-CONVERSION ASSUMPTIONS</summary>
            <div className="basis-grid">
              <label>DURATION HOURS<input type="number" min="0.1" value={duration} onChange={(event) => setDuration(Number(event.target.value))} /></label>
              <label>ELECTRICITY ₹/KWH {selectedCostBook?.electricity_inr_kwh !== null && selectedCostBook?.electricity_inr_kwh !== undefined ? "· COST BOOK" : "· RUN INPUT"}<input type="number" min="0" step="0.1" value={effectiveElectricityTariff} disabled={selectedCostBook?.electricity_inr_kwh !== null && selectedCostBook?.electricity_inr_kwh !== undefined} onChange={(event) => setElectricityTariff(Number(event.target.value))} /></label>
              <label>THERMAL FUEL ₹/MILLION KCAL {selectedCostBook?.thermal_fuel_inr_mkcal !== null && selectedCostBook?.thermal_fuel_inr_mkcal !== undefined ? "· COST BOOK" : "· RUN INPUT"}<input type="number" min="0" value={effectiveThermalTariff} disabled={selectedCostBook?.thermal_fuel_inr_mkcal !== null && selectedCostBook?.thermal_fuel_inr_mkcal !== undefined} onChange={(event) => setThermalTariff(Number(event.target.value))} /></label>
              <label>RAW MEAL → CLINKER YIELD<input type="number" min="0.3" max="1" step="0.01" value={rawMealYield} onChange={(event) => setRawMealYield(Number(event.target.value))} /></label>
              <label>CHEMISTRY SCENARIO<select value={chemistryScenario} onChange={(event) => setChemistryScenario(event.target.value as "low" | "typical" | "high")}><option value="low">Low profile</option><option value="typical">Typical</option><option value="high">High profile</option></select></label>
              <label>TARGET BLAINE M²/KG {routeHasCementGrinding ? "" : "· NOT APPLICABLE"}<input type="number" min="1" value={targetBlaine} disabled={!routeHasCementGrinding} onChange={(event) => setTargetBlaine(Number(event.target.value))} /></label>
              <label className="check-line"><input type="checkbox" checked={autoMassConversion} onChange={(event) => setAutoMassConversion(event.target.checked)} /> AUTO YIELD FROM RAW-MEAL LOI</label>
            </div>
            {!routeHasCementGrinding && <p className="note">Target Blaine is disabled and sent as null because this route has no cement-grinding stage.</p>}
            {selectedCostBook && <p className="note">Selected cost-book tariffs are authoritative and locked above. A blank tariff in the cost book falls back to the editable run input. Deselect the cost book to use run tariffs for both fields.</p>}
          </details>
          <details className="basis-panel"><summary>KILN / FUEL-ASH OPERATING ENVELOPE</summary><div className="basis-grid"><label>FUEL MATERIAL<select value={fuelMaterialId} onChange={(event) => setFuelMaterialId(event.target.value)}><option value="">No fuel-ash model</option>{materials.filter((item) => ["fuel", "alternative_fuel"].includes(item.functional_role)).map((item) => <option value={item.material_id} key={item.material_id}>{item.name}</option>)}</select></label><label>FUEL RATE KG/T CLINKER<input type="number" value={fuelRate} onChange={(event) => setFuelRate(event.target.value)} /></label><label>KILN FEED MOISTURE %<input type="number" value={kilnMoisture} onChange={(event) => setKilnMoisture(event.target.value)} /></label><label>KILN O₂ %<input type="number" value={kilnOxygen} onChange={(event) => setKilnOxygen(event.target.value)} /></label><label>KILN TEMPERATURE °C<input type="number" value={kilnTemperature} onChange={(event) => setKilnTemperature(event.target.value)} /></label><label>MEASURED FREE LIME %<input type="number" value={freeLime} onChange={(event) => setFreeLime(event.target.value)} /></label></div></details>
          <details className="basis-panel"><summary>OPC 43 MEASURED PRODUCTION GATE</summary><p className="note">Leave untested values blank. The gate will remain REVIEW; it never predicts strength from oxide chemistry.</p><div className="basis-grid">{Object.entries(quality).map(([key, value]) => <label key={key}>{pretty(key)}<input type="number" value={value} onChange={(event) => setQuality((current) => ({ ...current, [key]: event.target.value }))} /></label>)}</div></details>
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
      {view === "accuracy" && <AccuracyWorkspace materials={materials} runs={runs} blendCreated={(blend) => { setBlends((current) => [...current, blend]); setBlendId(blend.blend_id); setView("console"); }} />}
      {view === "costs" && <CostBookWorkspace materials={materials} costBooks={costBooks} done={(costBook) => { setCostBooks((current) => [...current, costBook]); setCostBookId(costBook.cost_book_id); setView("console"); }} />}
      {view === "runs" && <RunLibrary runs={runs} openRun={openRun} />}
      {view === "library" && <LibraryManager materials={materials} archivedMaterials={archivedMaterials} blends={blends} archivedBlends={archivedBlends} machines={machines} archivedMachines={archivedMachines} routes={routes} archivedRoutes={archivedRoutes} costBooks={costBooks} archivedCostBooks={archivedCostBooks} refresh={load} />}
    </main>
  );
}

function ResultSummary({ result }: { result: Result }) {
  const valid = result.run_status === "completed";
  const product = result.output_product.toUpperCase();
  const metrics = [
    [`TARGET ${product}`, number(result.request.target_output_tph, " t/h")],
    [`ACHIEVED ${product}`, valid ? number(result.achievable_output_tph, " t/h") : "BLOCKED"],
    ["BOTTLENECK", result.bottleneck_machine_name ?? "Unknown"],
    ["ELECTRICITY", valid ? number(result.electricity_kwh_t, " kWh/t") : "N/A — BLOCKED"],
    ["THERMAL", valid ? number(result.thermal_kcal_kg, " kcal/kg") : "N/A — BLOCKED"],
    ["DIRECT MODEL COST", valid ? money(result.direct_model_cost_inr_t) : "N/A — BLOCKED"],
    ["PLANT CASH COST", valid ? money(result.cost_breakdown?.plant_cash_cost_inr_t ?? null) : "N/A — BLOCKED"],
    ["FULL COST", valid ? money(result.cost_breakdown?.full_cost_inr_t ?? null) : "N/A — BLOCKED"],
    ["MATERIAL CO₂", valid ? number(result.estimated_co2_kg_t, " kg/t", 0) : "N/A — BLOCKED"],
    ["RUN OUTPUT", valid ? number(result.total_output_tonnes, " t", 0) : "0 t — BLOCKED"],
    ["MATERIAL INPUT", valid ? number(result.total_material_input_tonnes, " t", 0) : "0 t — BLOCKED"],
  ];
  return (
    <>
      {!valid && <div className="err">RUN BLOCKED — resolve every BLOCK validation before treating output, energy or cost as a production result.</div>}
      <section className="result-summary" aria-label="Simulation result summary">
        {metrics.map(([label, value]) => <div key={label}><small>{label}</small><strong>{value}</strong></div>)}
      </section>
    </>
  );
}

function RunReport({ result }: { result: Result }) {
  const valid = result.run_status === "completed";
  const clinkerOutput = result.output_product === "clinker";
  const clinkerAllocationApplied = result.cost_breakdown?.operating_cost_basis.startsWith("clinker-only") ?? false;
  const clinkerOperatingCost = (value: number | null): string => {
    if (clinkerOutput && !clinkerAllocationApplied) return "N/A — RERUN FOR CLINKER ALLOCATION";
    return money(value);
  };
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
        <details open><summary>WEIGHTED CHEMISTRY / MASS %</summary><div className="chemistry-grid">{Object.entries(result.chemistry).map(([oxide, value]) => <div key={oxide}><small>{oxide.toUpperCase()}</small><strong>{value === null ? "UNKNOWN" : `${value.toFixed(3)}%`}</strong></div>)}</div><div className="moduli"><span>LSF {result.lsf === null ? "N/A — raw meal only or chemistry incomplete" : result.lsf.toFixed(2)}</span><span>SM {result.silica_modulus?.toFixed(3) ?? "N/A"}</span><span>AM {result.alumina_modulus?.toFixed(3) ?? "N/A"}</span></div></details>
        <details open><summary>COST / INCLUDED AND EXCLUDED</summary>{!valid ? <p className="note">N/A — this run is BLOCKED. Resolve the blocking validation and rerun before using cost results.</p> : result.cost_breakdown && <div className="key-values"><span>Materials</span><strong>{money(result.cost_breakdown.materials_inr_t)}</strong><span>Electricity</span><strong>{money(result.cost_breakdown.electricity_inr_t)}</strong><span>Thermal fuel</span><strong>{money(result.cost_breakdown.thermal_inr_t)}</strong><span>Applied electricity tariff</span><strong>{result.applied_electricity_inr_kwh === null ? "N/A — legacy run" : `₹${result.applied_electricity_inr_kwh.toFixed(2)}/kWh · ${result.electricity_tariff_source}`}</strong><span>Applied thermal tariff</span><strong>{result.applied_thermal_fuel_inr_mkcal === null ? "N/A — legacy run" : `₹${result.applied_thermal_fuel_inr_mkcal.toFixed(2)}/million kcal · ${result.thermal_tariff_source}`}</strong><span>Direct model total</span><strong>{money(result.cost_breakdown.direct_model_cost_inr_t)}</strong><span>Packing</span><strong>{clinkerOutput ? "EXCLUDED — NO CEMENT PACKING" : money(result.cost_breakdown.packing_inr_t)}</strong><span>{clinkerOutput ? "Clinker-stage labour" : "Labour"}</span><strong>{clinkerOperatingCost(result.cost_breakdown.labour_inr_t)}</strong><span>{clinkerOutput ? "Clinker-stage maintenance" : "Maintenance"}</span><strong>{clinkerOperatingCost(result.cost_breakdown.maintenance_inr_t)}</strong><span>{clinkerOutput ? "Clinker-stage other variable" : "Other variable"}</span><strong>{clinkerOperatingCost(result.cost_breakdown.other_variable_inr_t)}</strong><span>Plant cash cost</span><strong>{clinkerOperatingCost(result.cost_breakdown.plant_cash_cost_inr_t)}</strong><span>{clinkerOutput ? "Clinker-stage factory overhead" : "Factory overhead"}</span><strong>{clinkerOperatingCost(result.cost_breakdown.factory_overhead_inr_t)}</strong><span>Outbound logistics</span><strong>{clinkerOutput ? "EXCLUDED — FINISHED-CEMENT LOGISTICS" : money(result.cost_breakdown.outbound_logistics_inr_t)}</strong><span>Full cost estimate</span><strong>{clinkerOperatingCost(result.cost_breakdown.full_cost_inr_t)}</strong></div>}{valid && result.cost_breakdown && <p className="note">Cost book: {result.cost_breakdown.cost_book_name ?? "none"}. Basis: {result.cost_breakdown.operating_cost_basis}.<br />Included: {result.cost_breakdown.included_costs.join(", ") || "direct model only"}.<br />Excluded: {result.cost_breakdown.excluded_costs.join(", ")}</p>}</details>
        <details open><summary>ENERGY / RUN TOTALS</summary>{!valid ? <p className="note">N/A — this run is BLOCKED. Stored design intensities are not published as achieved production energy.</p> : result.energy_breakdown && <div className="key-values"><span>Electricity intensity</span><strong>{number(result.energy_breakdown.electricity_kwh_t, ` kWh/t ${result.output_product}`)}</strong><span>Thermal intensity</span><strong>{number(result.energy_breakdown.thermal_kcal_kg, ` kcal/kg ${result.output_product}`)}</strong><span>Total electricity</span><strong>{number(result.energy_breakdown.total_electricity_mwh, " MWh")}</strong><span>Total thermal energy</span><strong>{number(result.energy_breakdown.total_thermal_gcal, " Gcal")}</strong></div>}</details>
        <details open><summary>CARBON / MATERIAL SCOPE</summary>{!valid ? <p className="note">N/A — this run is BLOCKED. No achieved-production carbon headline is published.</p> : result.carbon_breakdown && <div className="key-values"><span>Material CO₂ intensity</span><strong>{number(result.carbon_breakdown.materials_kg_co2_t, ` kg/t ${result.output_product}`, 1)}</strong><span>Total material input</span><strong>{number(result.carbon_breakdown.total_materials_tonnes, " t", 1)}</strong><span>Total material CO₂</span><strong>{result.carbon_breakdown.total_materials_kg_co2 === null ? "N/A" : number(result.carbon_breakdown.total_materials_kg_co2 / 1000, " t CO₂", 1)}</strong></div>}{valid && <p className="note">Excludes: {result.carbon_breakdown?.exclusions.join(", ")}</p>}</details>
        <details open><summary>ROUTE / WHY THIS PATH</summary>{result.route_analysis ? <><div className="key-values"><span>Route kind</span><strong>{pretty(result.route_analysis.route_kind)}</strong><span>Compatibility</span><strong>{result.route_analysis.compatibility_score.toFixed(0)}/100</strong><span>Predicted route capacity</span><strong>{number(result.route_analysis.predicted_output_tph, " t/h")}</strong><span>Route bottleneck</span><strong>{result.route_analysis.bottleneck_machine_name ?? "N/A"}</strong></div><p className="note">{result.route_analysis.description}<br />{result.route_analysis.flow_summary}<br />{result.route_analysis.reasons.join(" · ")}</p></> : <p className="note">Legacy run: route analysis was not stored by this calculation version.</p>}</details>
        <details open><summary>PRODUCTION QUALITY GATE</summary>{result.quality_gate ? <><div className="key-values"><span>Gate</span><strong>{result.quality_gate.standard}</strong><span>Status</span><strong>{result.quality_gate.status.toUpperCase()}</strong>{result.quality_gate.checks.flatMap((check) => [<span key={`${check.metric}-label`}>{pretty(check.metric)} · {check.requirement}</span>, <strong key={`${check.metric}-value`}>{check.measured === null ? "NOT TESTED" : `${check.measured} · ${check.status.toUpperCase()}`}</strong>])}</div><p className="note">{result.quality_gate.note}</p></> : <p className="note">This recipe is not being screened as an OPC 43 finished-cement candidate.</p>}</details>
        <details><summary>UNCERTAINTY / PROCESS CORRECTIONS</summary><div className="key-values"><span>Chemistry scenario</span><strong>{pretty(result.chemistry_scenario)}</strong><span>LOI-derived raw-meal yield</span><strong>{result.derived_raw_meal_to_clinker_yield?.toFixed(4) ?? "N/A"}</strong><span>Grinding capacity factor</span><strong>{result.grinding_capacity_factor.toFixed(4)}</strong><span>Grinding energy factor</span><strong>{result.grinding_energy_factor.toFixed(4)}</strong><span>Fuel ash addition</span><strong>{result.fuel_ash_contribution_kg_t_clinker === null ? "N/A" : `${result.fuel_ash_contribution_kg_t_clinker.toFixed(2)} kg/t clinker`}</strong></div></details>
      </div>

      <details open><summary>MACHINE CAPACITY AND ENERGY BREAKDOWN</summary><div className="table-responsive"><table><thead><tr><th>Machine / immutable version</th><th>Stage</th><th>Target-required t/h</th><th>Target load</th><th>Achieved stage t/h</th><th>Achieved load</th><th>Effective stage cap.</th><th>{pretty(result.output_product)}-eq. cap.</th><th>kWh/t {result.output_product}</th><th>kcal/kg {result.output_product}</th></tr></thead><tbody>{result.machine_metrics.map((item) => { const snapshot = result.machine_snapshots.find((machine) => machine.machine_id === item.machine_id); return <tr key={item.node_id}><td>{item.machine_name} · {item.machine_id} · v{snapshot?.version ?? "?"}</td><td>{pretty(item.process_stage)}</td><td>{item.target_throughput_tph.toFixed(2)}</td><td>{item.target_load_percent.toFixed(1)}%</td><td>{item.actual_throughput_tph.toFixed(2)}</td><td>{item.load_percent.toFixed(1)}%</td><td>{item.effective_capacity_tph.toFixed(2)}</td><td>{item.output_equivalent_capacity_tph?.toFixed(2) ?? "N/A"}</td><td>{result.run_status === "blocked" ? "N/A" : item.electricity_kwh_t_output.toFixed(2)}</td><td>{result.run_status === "blocked" ? "N/A" : item.thermal_kcal_kg_output.toFixed(2)}</td></tr>; })}</tbody></table></div></details>

      <details><summary>MATERIAL MASS / COST / CARBON BREAKDOWN</summary><div className="table-responsive"><table><thead><tr><th>Material / immutable version</th><th>Input mass %</th><th>t input/t {result.output_product}</th><th>t/h input</th><th>t/run input</th><th>Applied ₹/t material</th><th>₹/t {result.output_product}</th><th>Cost basis</th><th>kg CO₂/t {result.output_product}</th><th>Evidence</th></tr></thead><tbody>{result.material_metrics.map((item) => { const snapshot = result.material_snapshots.find((material) => material.material_id === item.material_id); return <tr key={item.material_id}><td>{item.material_name} · {item.material_id} · v{snapshot?.version ?? "?"}</td><td>{item.percentage.toFixed(3)}</td><td>{item.tonnes_per_t_output?.toFixed(4) ?? "N/A — legacy"}</td><td>{item.tonnes_per_hour.toFixed(2)}</td><td>{item.tonnes_per_run.toFixed(1)}</td><td>{item.applied_unit_cost_inr_t?.toFixed(0) ?? "N/A"}</td><td>{valid ? item.cost_inr_t_output?.toFixed(0) ?? "N/A" : "N/A"}</td><td>{item.cost_basis}</td><td>{valid ? item.co2_kg_t_output?.toFixed(1) ?? "N/A" : "N/A"}</td><td>{item.evidence_class}</td></tr>; })}</tbody></table></div></details>

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
      {runs.map((run) => <div className="run-row" key={run.run_id}><input aria-label={`Compare ${run.run_id}`} type="checkbox" checked={selected.includes(run.run_id)} onChange={() => toggle(run.run_id)} /><code>{run.run_id}</code><span>{run.blend_snapshot?.name ?? run.request.blend_id}<small>{run.route_snapshot?.name ?? run.request.route_id} · {new Date(run.created_at).toLocaleString()}</small></span><span>{run.run_status === "blocked" ? "BLOCKED" : `${run.achievable_output_tph.toFixed(1)} t/h ${run.output_product}`}<small>{run.run_status === "blocked" ? "No valid production result" : `${money(run.direct_model_cost_inr_t)} · ${number(run.estimated_co2_kg_t, " kg CO₂/t", 0)}`}</small></span><button onClick={() => openRun(run)}>OPEN</button></div>)}
      {compared.length > 0 && <div className="comparison"><div className="title">SIDE-BY-SIDE COMPARISON / {compared.length} RUNS</div><div className="table-responsive"><table><thead><tr><th>Run</th><th>Status</th><th>Blend</th><th>Route</th><th>Output t/h</th><th>Bottleneck</th><th>kWh/t</th><th>kcal/kg</th><th>Direct ₹/t</th><th>CO₂ kg/t</th><th>Warnings</th></tr></thead><tbody>{compared.map((run) => <tr key={run.run_id}><td>{run.run_id.slice(-8)}</td><td>{run.run_status.toUpperCase()}</td><td>{run.blend_snapshot?.name ?? run.request.blend_id}</td><td>{run.route_snapshot?.name ?? run.request.route_id}</td><td>{run.run_status === "blocked" ? "N/A" : run.achievable_output_tph.toFixed(1)}</td><td>{run.bottleneck_machine_name ?? "Unknown"}</td><td>{run.run_status === "blocked" ? "N/A" : run.electricity_kwh_t.toFixed(1)}</td><td>{run.run_status === "blocked" ? "N/A" : run.thermal_kcal_kg.toFixed(1)}</td><td>{run.run_status === "blocked" ? "N/A" : run.direct_model_cost_inr_t?.toFixed(0) ?? "N/A"}</td><td>{run.run_status === "blocked" ? "N/A" : run.estimated_co2_kg_t?.toFixed(0) ?? "N/A"}</td><td>{run.warnings.length}</td></tr>)}</tbody></table></div></div>}
    </section>
  );
}

function MachineGuide({ done }: { done: (machine: Machine) => void }) {
  const [kind, setKind] = useState("standard");
  const [name, setName] = useState("New Process Machine");
  const [stage, setStage] = useState("cement_grinding");
  const [capacity, setCapacity] = useState(100);
  const [minimum, setMinimum] = useState(40);
  const [maximumStable, setMaximumStable] = useState(90);
  const [availability, setAvailability] = useState(0.9);
  const [energy, setEnergy] = useState(20);
  const [heat, setHeat] = useState(0);
  const [capex, setCapex] = useState(0);
  const [trl, setTrl] = useState(5);
  const [designBlaine, setDesignBlaine] = useState("");
  const [maxMoisture, setMaxMoisture] = useState("");
  const [minimumTemperature, setMinimumTemperature] = useState("");
  const [maximumTemperature, setMaximumTemperature] = useState("");
  const [minimumOxygen, setMinimumOxygen] = useState("");
  const [maximumOxygen, setMaximumOxygen] = useState("");
  const [maximumFreeLime, setMaximumFreeLime] = useState("");
  const [source, setSource] = useState("Unverified machine input — replace with vendor source");

  async function save() {
    const optional = (value: string) => value === "" ? null : Number(value);
    const base = {
      machine_kind: kind, name, process_stage: stage,
      rated_capacity_tph: capacity, minimum_stable_tph: minimum,
      maximum_stable_tph: maximumStable, availability,
      specific_electricity_kwh_t: energy, specific_heat_kcal_kg: heat,
      capex_inr_crore: capex, technology_readiness_level: trl,
      design_blaine_m2_kg: optional(designBlaine),
      maximum_feed_moisture_percent: optional(maxMoisture),
      minimum_temperature_c: optional(minimumTemperature),
      maximum_temperature_c: optional(maximumTemperature),
      minimum_oxygen_percent: optional(minimumOxygen),
      maximum_oxygen_percent: optional(maximumOxygen),
      maximum_free_lime_percent: optional(maximumFreeLime),
      evidence: [{ evidence_class: "unverified", source_title: source }],
    };
    const payload = kind === "thermal"
      ? { ...base, residence_time_minutes: 30, conversion_fraction: 0.95, product_state: stage === "clay_calcination" ? "calcined_clay" : "clinker" }
      : { ...base, input_material: "solid", output_material: "solid" };
    done(await req<Machine>("/api/machines", { method: "POST", body: JSON.stringify(payload) }));
  }

  const isKiln = stage === "thermal_transformation" || stage === "clay_calcination";
  const invalidEnvelope = minimum > maximumStable || maximumStable > capacity || (
    minimumOxygen !== "" && maximumOxygen !== "" && Number(minimumOxygen) > Number(maximumOxygen)
  );
  return <section className="guide"><h2>GUIDE / NEW MACHINE</h2><div className="form-grid two">
    <label>TYPE<select value={kind} onChange={(event) => setKind(event.target.value)}><option value="standard">Standard</option><option value="thermal">Thermal transformation</option></select></label>
    <label>NAME<input value={name} onChange={(event) => setName(event.target.value)} /></label>
    <label>STAGE<select value={stage} onChange={(event) => { const value = event.target.value; setStage(value); if (value === "cement_grinding" && designBlaine === "") setDesignBlaine("320"); }}><option value="crushing">Crushing</option><option value="raw_grinding">Raw grinding</option><option value="thermal_transformation">Clinker thermal transformation</option><option value="clay_calcination">Clay calcination</option><option value="cement_grinding">Cement grinding</option><option value="packing_dispatch">Packing</option></select></label>
    <label>RATED CAPACITY T/H<input type="number" value={capacity} onChange={(event) => setCapacity(Number(event.target.value))} /></label>
    <label>MINIMUM STABLE T/H<input type="number" value={minimum} onChange={(event) => setMinimum(Number(event.target.value))} /></label>
    <label>MAXIMUM STABLE T/H<input type="number" value={maximumStable} onChange={(event) => setMaximumStable(Number(event.target.value))} /></label>
    <label>AVAILABILITY 0–1<input type="number" min="0.01" max="1" step="0.01" value={availability} onChange={(event) => setAvailability(Number(event.target.value))} /></label>
    <label>ELECTRICITY KWH/T STAGE<input type="number" value={energy} onChange={(event) => setEnergy(Number(event.target.value))} /></label>
    <label>THERMAL KCAL/KG STAGE<input type="number" value={heat} onChange={(event) => setHeat(Number(event.target.value))} /></label>
    <label>CAPEX ₹ CRORE<input type="number" value={capex} onChange={(event) => setCapex(Number(event.target.value))} /></label>
    <label>TRL 1–9<input type="number" min="1" max="9" value={trl} onChange={(event) => setTrl(Number(event.target.value))} /></label>
    <label>DESIGN BLAINE M²/KG<input type="number" value={designBlaine} onChange={(event) => setDesignBlaine(event.target.value)} placeholder="Grinding machines only" /></label>
    <label>MAXIMUM FEED MOISTURE %<input type="number" value={maxMoisture} onChange={(event) => setMaxMoisture(event.target.value)} /></label>
    {isKiln && <><label>MINIMUM TEMPERATURE °C<input type="number" value={minimumTemperature} onChange={(event) => setMinimumTemperature(event.target.value)} /></label><label>MAXIMUM TEMPERATURE °C<input type="number" value={maximumTemperature} onChange={(event) => setMaximumTemperature(event.target.value)} /></label><label>OXYGEN MINIMUM %<input type="number" value={minimumOxygen} onChange={(event) => setMinimumOxygen(event.target.value)} /></label><label>OXYGEN MAXIMUM %<input type="number" value={maximumOxygen} onChange={(event) => setMaximumOxygen(event.target.value)} /></label><label>MAXIMUM FREE LIME %<input type="number" value={maximumFreeLime} onChange={(event) => setMaximumFreeLime(event.target.value)} /></label></>}
  </div><label>EVIDENCE / VENDOR SOURCE<input value={source} onChange={(event) => setSource(event.target.value)} /></label><pre>{invalidEnvelope ? "BLOCK Invalid operating envelope" : trl >= 8 ? "PASS  Commercial maturity threshold\nINFO  Stored operating limits are enforced during every run" : "WARN  TRL below 8\nBLOCK Investor base case; R&D scenario only"}</pre><button className="run" disabled={invalidEnvelope} onClick={() => void save()}>CREATE IMMUTABLE MACHINE VERSION</button></section>;
}
