import { useEffect, useMemo, useState } from "react";

import { API, req } from "./api";
import type {
  EngineeringCase,
  EngineeringLearningResult,
  EngineeringPrediction,
} from "./engineeringTypes";
import type {
  Blend,
  CostBook,
  Material,
  RetrofitCandidate,
  RetrofitStudyResult,
  Route,
} from "./types";

type Props = {
  materials: Material[];
  blends: Blend[];
  routes: Route[];
  costBooks: CostBook[];
  onBlendCreated: (blend: Blend) => void;
};

type Stage = 1 | 2 | 3 | 4 | 5 | 6;

type Actuals = {
  actual_output_tph: string;
  actual_electricity_kwh_t: string;
  actual_thermal_kcal_kg: string;
  actual_variable_cost_inr_t: string;
  actual_material_co2_kg_t: string;
  actual_free_lime_percent: string;
  actual_strength_3d_mpa: string;
  actual_strength_28d_mpa: string;
  xrf_comparison: string;
  xrd_comparison: string;
  coal_observation: string;
  power_observation: string;
  thermal_observation: string;
  comments: string;
  root_cause: string;
  decision: "proceed" | "hold" | "reject";
  engineer_signoff: string;
  quality_head_signoff: string;
  plant_head_signoff: string;
};

const STAGES: Array<{ id: Stage; label: string; subtitle: string }> = [
  { id: 1, label: "1 · INPUTS", subtitle: "Materials, route, plant and constraints" },
  { id: 2, label: "2 · SIMULATION", subtitle: "Pareto candidates, balances and risk" },
  { id: 3, label: "3 · RECOMMEND", subtitle: "Explainable engineering actions" },
  { id: 4, label: "4 · WORKBOOK", subtitle: "Auditable plant-calibration package" },
  { id: 5, label: "5 · PILOT", subtitle: "Controlled production and sampling" },
  { id: 6, label: "6 · LEARNING", subtitle: "Actuals, error and recalibration" },
];

function pretty(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (match) => match.toUpperCase());
}

function formatValue(number: number | null, suffix: string, digits = 1): string {
  return number === null ? "N/A" : `${number.toFixed(digits)}${suffix}`;
}

function rolePercent(candidate: RetrofitCandidate, role: string): number {
  return candidate.components.find((item) => item.role === role)?.percentage ?? 0;
}

function predictionValue(item: EngineeringPrediction): string {
  if (item.prediction === null) return "N/A";
  if (typeof item.prediction === "number") {
    return `${item.prediction.toFixed(item.unit?.includes("%") ? 1 : 2)}${item.unit ? ` ${item.unit}` : ""}`;
  }
  return `${item.prediction}${item.unit ? ` ${item.unit}` : ""}`;
}

function optionalNumber(value: string): number | null {
  return value.trim() === "" ? null : Number(value);
}

export function RetrofitWorkspace({ materials, blends, routes, costBooks, onBlendCreated }: Props) {
  const ppcBlends = useMemo(
    () => blends
      .filter((item) => item.blend_class === "finished_cement")
      .sort((left, right) => Number(!left.family.toLowerCase().includes("ppc")) - Number(!right.family.toLowerCase().includes("ppc"))),
    [blends],
  );

  const [stage, setStage] = useState<Stage>(1);
  const [baselineBlendId, setBaselineBlendId] = useState("");
  const [routeId, setRouteId] = useState("");
  const [costBookId, setCostBookId] = useState("");
  const [targetOutput, setTargetOutput] = useState(100);
  const [supplyMode, setSupplyMode] = useState<"purchased_calcined_clay" | "onsite_calcination">("purchased_calcined_clay");
  const [calcinedClayId, setCalcinedClayId] = useState("");
  const [limestoneId, setLimestoneId] = useState("");
  const [gypsumId, setGypsumId] = useState("");
  const [rawClayId, setRawClayId] = useState("");
  const [clinkerMin, setClinkerMin] = useState(45);
  const [clinkerMax, setClinkerMax] = useState(60);
  const [clayMin, setClayMin] = useState(20);
  const [clayMax, setClayMax] = useState(35);
  const [limestoneMin, setLimestoneMin] = useState(10);
  const [limestoneMax, setLimestoneMax] = useState(20);
  const [gypsumMin, setGypsumMin] = useState(3);
  const [gypsumMax, setGypsumMax] = useState(7);
  const [clayLimestoneRatioMin, setClayLimestoneRatioMin] = useState(1.5);
  const [clayLimestoneRatioMax, setClayLimestoneRatioMax] = useState(2.5);
  const [targetCandidates, setTargetCandidates] = useState(10);
  const [costWeight, setCostWeight] = useState(1);
  const [co2Weight, setCo2Weight] = useState(1);
  const [outputWeight, setOutputWeight] = useState(1);
  const [energyWeight, setEnergyWeight] = useState(0.7);
  const [robustnessWeight, setRobustnessWeight] = useState(1);
  const [complexityWeight, setComplexityWeight] = useState(0.8);
  const [clinkerFactorWeight, setClinkerFactorWeight] = useState(0.6);

  const [projectName, setProjectName] = useState("PPC-to-LC3 Engineering Decision");
  const [plantName, setPlantName] = useState("Reference plant");
  const [engineer, setEngineer] = useState("BRIXTA Engineering");
  const [revision, setRevision] = useState("R0");
  const [bisConstraints, setBisConstraints] = useState("Applicable BIS/product clauses to be confirmed");
  const [customerConstraints, setCustomerConstraints] = useState("");
  const [pilotQuantity, setPilotQuantity] = useState(500);
  const [pilotRateFraction, setPilotRateFraction] = useState(0.6);
  const [monitoringHours, setMonitoringHours] = useState(72);
  const [projectNotes, setProjectNotes] = useState("");

  const [study, setStudy] = useState<RetrofitStudyResult | null>(null);
  const [selectedCandidateId, setSelectedCandidateId] = useState("");
  const [engineeringCase, setEngineeringCase] = useState<EngineeringCase | null>(null);
  const [learning, setLearning] = useState<EngineeringLearningResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [caseLoading, setCaseLoading] = useState(false);
  const [learningLoading, setLearningLoading] = useState(false);
  const [error, setError] = useState("");

  const [actuals, setActuals] = useState<Actuals>({
    actual_output_tph: "",
    actual_electricity_kwh_t: "",
    actual_thermal_kcal_kg: "",
    actual_variable_cost_inr_t: "",
    actual_material_co2_kg_t: "",
    actual_free_lime_percent: "",
    actual_strength_3d_mpa: "",
    actual_strength_28d_mpa: "",
    xrf_comparison: "",
    xrd_comparison: "",
    coal_observation: "",
    power_observation: "",
    thermal_observation: "",
    comments: "",
    root_cause: "",
    decision: "hold",
    engineer_signoff: "",
    quality_head_signoff: "",
    plant_head_signoff: "",
  });

  useEffect(() => {
    if (!baselineBlendId) setBaselineBlendId(ppcBlends[0]?.blend_id ?? "");
    if (!routeId) setRouteId(routes.find((item) => item.route_kind === "integrated")?.route_id ?? routes[0]?.route_id ?? "");
    if (!costBookId) setCostBookId(costBooks[0]?.cost_book_id ?? "");
    if (!calcinedClayId) setCalcinedClayId(materials.find((item) => item.material_type === "calcined_clay")?.material_id ?? "");
    if (!limestoneId) setLimestoneId(materials.find((item) => item.material_type === "limestone" && item.functional_role === "cement_addition")?.material_id ?? materials.find((item) => item.material_type === "limestone")?.material_id ?? "");
    if (!gypsumId) setGypsumId(materials.find((item) => item.functional_role === "set_regulator")?.material_id ?? "");
    if (!rawClayId) setRawClayId(materials.find((item) => ["clay", "shale", "bauxite", "laterite"].includes(item.material_type))?.material_id ?? "");
  }, [baselineBlendId, routeId, costBookId, calcinedClayId, limestoneId, gypsumId, rawClayId, ppcBlends, routes, costBooks, materials]);

  const selectedCandidate = study?.candidates.find((item) => item.candidate_id === selectedCandidateId)
    ?? study?.candidates[0]
    ?? null;

  const stageAvailable = (target: Stage): boolean => {
    if (target === 1) return true;
    if (target === 2) return Boolean(study);
    if (target >= 3) return Boolean(engineeringCase);
    return false;
  };

  async function design() {
    setError("");
    setLoading(true);
    setEngineeringCase(null);
    setLearning(null);
    try {
      const payload = {
        existing_ppc_blend_id: baselineBlendId,
        route_id: routeId,
        cost_book_id: costBookId || null,
        target_output_tph: targetOutput,
        calcined_clay_source: { component_type: "material", reference_id: calcinedClayId },
        limestone_source: { component_type: "material", reference_id: limestoneId },
        gypsum_source: { component_type: "material", reference_id: gypsumId },
        clay_supply_mode: supplyMode,
        raw_clay_material_id: supplyMode === "onsite_calcination" ? rawClayId : null,
        clinker_bounds: { minimum_percent: clinkerMin, maximum_percent: clinkerMax },
        calcined_clay_bounds: { minimum_percent: clayMin, maximum_percent: clayMax },
        limestone_bounds: { minimum_percent: limestoneMin, maximum_percent: limestoneMax },
        gypsum_bounds: { minimum_percent: gypsumMin, maximum_percent: gypsumMax },
        clay_to_limestone_ratio_min: clayLimestoneRatioMin,
        clay_to_limestone_ratio_max: clayLimestoneRatioMax,
        objective_weights: {
          cost: costWeight,
          co2: co2Weight,
          output: outputWeight,
          electricity: energyWeight,
          thermal: energyWeight,
          robustness: robustnessWeight,
          retrofit_complexity: complexityWeight,
          clinker_factor: clinkerFactorWeight,
        },
        target_candidates: targetCandidates,
      };
      const nextStudy = await req<RetrofitStudyResult>("/api/retrofit/ppc-to-lc3/design", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setStudy(nextStudy);
      setSelectedCandidateId(nextStudy.selected_candidate_id ?? nextStudy.candidates[0]?.candidate_id ?? "");
      setStage(2);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setLoading(false);
    }
  }

  async function generateEngineeringCase() {
    if (!study || !selectedCandidate) return;
    setCaseLoading(true);
    setError("");
    try {
      const nextCase = await req<EngineeringCase>("/api/engineering/cases", {
        method: "POST",
        body: JSON.stringify({
          study_id: study.study_id,
          candidate_id: selectedCandidate.candidate_id,
          project: {
            project_name: projectName,
            plant_name: plantName,
            engineer,
            product_target: "LC3",
            revision,
            bis_constraints: bisConstraints.split("\n").map((item) => item.trim()).filter(Boolean),
            customer_constraints: customerConstraints.split("\n").map((item) => item.trim()).filter(Boolean),
            pilot_quantity_t: pilotQuantity,
            pilot_rate_fraction: pilotRateFraction,
            monitoring_hours: monitoringHours,
            notes: projectNotes || null,
          },
        }),
      });
      setEngineeringCase(nextCase);
      setStage(3);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setCaseLoading(false);
    }
  }

  async function saveCandidate() {
    if (!study || !selectedCandidate) return;
    setSaving(true);
    setError("");
    try {
      const blend = await req<Blend>(
        `/api/retrofit-studies/${study.study_id}/candidates/${selectedCandidate.candidate_id}/save-blend`,
        {
          method: "POST",
          body: JSON.stringify({
            name: `${selectedCandidate.name} · ${study.baseline.blend_name} retrofit`,
            applicable_standard: "LC3 reference screening; laboratory and compliance validation required",
          }),
        },
      );
      onBlendCreated(blend);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setSaving(false);
    }
  }

  async function importActuals() {
    if (!engineeringCase) return;
    setLearningLoading(true);
    setError("");
    try {
      const nextLearning = await req<EngineeringLearningResult>(
        `/api/engineering/cases/${engineeringCase.case_id}/validation`,
        {
          method: "POST",
          body: JSON.stringify({
            actual_output_tph: optionalNumber(actuals.actual_output_tph),
            actual_electricity_kwh_t: optionalNumber(actuals.actual_electricity_kwh_t),
            actual_thermal_kcal_kg: optionalNumber(actuals.actual_thermal_kcal_kg),
            actual_variable_cost_inr_t: optionalNumber(actuals.actual_variable_cost_inr_t),
            actual_material_co2_kg_t: optionalNumber(actuals.actual_material_co2_kg_t),
            actual_free_lime_percent: optionalNumber(actuals.actual_free_lime_percent),
            actual_strength_3d_mpa: optionalNumber(actuals.actual_strength_3d_mpa),
            actual_strength_28d_mpa: optionalNumber(actuals.actual_strength_28d_mpa),
            xrf_comparison: actuals.xrf_comparison || null,
            xrd_comparison: actuals.xrd_comparison || null,
            coal_observation: actuals.coal_observation || null,
            power_observation: actuals.power_observation || null,
            thermal_observation: actuals.thermal_observation || null,
            comments: actuals.comments || null,
            root_cause: actuals.root_cause || null,
            decision: actuals.decision,
            engineer_signoff: actuals.engineer_signoff || null,
            quality_head_signoff: actuals.quality_head_signoff || null,
            plant_head_signoff: actuals.plant_head_signoff || null,
          }),
        },
      );
      setLearning(nextLearning);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setLearningLoading(false);
    }
  }

  function updateActual<K extends keyof Actuals>(key: K, value: Actuals[K]) {
    setActuals((current) => ({ ...current, [key]: value }));
  }

  return (
    <section className="guide retrofit-workspace engineering-workflow">
      <h2>BRIXTA ENGINEERING DECISION SYSTEM</h2>
      <p className="note">
        A traceable workflow from engineering assumptions to simulation, recommendation, workbook, pilot production and model learning.
        Every result carries a prediction, confidence, reason and required validation.
      </p>

      <div className="engineering-stage-rail">
        {STAGES.map((item) => (
          <button
            type="button"
            key={item.id}
            className={`${stage === item.id ? "selected" : ""} ${stageAvailable(item.id) ? "" : "locked"}`}
            disabled={!stageAvailable(item.id)}
            onClick={() => setStage(item.id)}
          >
            <strong>{item.label}</strong>
            <span>{item.subtitle}</span>
          </button>
        ))}
      </div>

      {error && <div className="err">{error}</div>}

      {stage === 1 && (
        <>
          <h3>STAGE 1 · ENGINEERING INPUTS</h3>
          <div className="form-grid two">
            <label>PROJECT NAME<input value={projectName} onChange={(event) => setProjectName(event.target.value)} /></label>
            <label>PLANT<input value={plantName} onChange={(event) => setPlantName(event.target.value)} /></label>
            <label>ENGINEER<input value={engineer} onChange={(event) => setEngineer(event.target.value)} /></label>
            <label>REVISION<input value={revision} onChange={(event) => setRevision(event.target.value)} /></label>
            <label>EXISTING PPC BLEND
              <select value={baselineBlendId} onChange={(event) => setBaselineBlendId(event.target.value)}>
                {ppcBlends.map((item) => <option key={item.blend_id} value={item.blend_id}>{item.name}</option>)}
              </select>
            </label>
            <label>EXISTING PLANT ROUTE
              <select value={routeId} onChange={(event) => setRouteId(event.target.value)}>
                {routes.map((item) => <option key={item.route_id} value={item.route_id}>{item.name} · {pretty(item.route_kind)}</option>)}
              </select>
            </label>
            <label>COST BOOK
              <select value={costBookId} onChange={(event) => setCostBookId(event.target.value)}>
                <option value="">Reference tariffs and material placeholders</option>
                {costBooks.map((item) => <option key={item.cost_book_id} value={item.cost_book_id}>{item.name} · v{item.version}</option>)}
              </select>
            </label>
            <label>TARGET LC3 OUTPUT T/H<input type="number" min="0.1" value={targetOutput} onChange={(event) => setTargetOutput(Number(event.target.value))} /></label>
            <label>CLAY SUPPLY PATHWAY
              <select value={supplyMode} onChange={(event) => setSupplyMode(event.target.value as typeof supplyMode)}>
                <option value="purchased_calcined_clay">Purchase calcined clay</option>
                <option value="onsite_calcination">Calcine raw clay onsite</option>
              </select>
            </label>
            {supplyMode === "onsite_calcination" && <label>RAW KAOLINITIC / CLAY SOURCE
              <select value={rawClayId} onChange={(event) => setRawClayId(event.target.value)}>
                {materials.filter((item) => ["clay", "shale", "bauxite", "laterite"].includes(item.material_type) || item.functional_role === "raw_kiln_feed").map((item) => <option key={item.material_id} value={item.material_id}>{item.name}</option>)}
              </select>
            </label>}
            <label>CALCINED-CLAY PRODUCT / PROXY
              <select value={calcinedClayId} onChange={(event) => setCalcinedClayId(event.target.value)}>
                {materials.filter((item) => ["calcined_clay", "metakaolin"].includes(item.material_type)).map((item) => <option key={item.material_id} value={item.material_id}>{item.name}</option>)}
              </select>
            </label>
            <label>CEMENT-GRADE LIMESTONE
              <select value={limestoneId} onChange={(event) => setLimestoneId(event.target.value)}>
                {materials.filter((item) => item.material_type === "limestone").map((item) => <option key={item.material_id} value={item.material_id}>{item.name}</option>)}
              </select>
            </label>
            <label>GYPSUM / SET REGULATOR
              <select value={gypsumId} onChange={(event) => setGypsumId(event.target.value)}>
                {materials.filter((item) => item.functional_role === "set_regulator" || item.material_type === "gypsum").map((item) => <option key={item.material_id} value={item.material_id}>{item.name}</option>)}
              </select>
            </label>
            <label>SHORTLIST SIZE<input type="number" min="3" max="25" value={targetCandidates} onChange={(event) => setTargetCandidates(Number(event.target.value))} /></label>
          </div>

          <h3>FORMULATION BOUNDS</h3>
          <div className="form-grid two">
            <label>CLINKER MIN / MAX<div className="inline-inputs"><input type="number" value={clinkerMin} onChange={(event) => setClinkerMin(Number(event.target.value))} /><input type="number" value={clinkerMax} onChange={(event) => setClinkerMax(Number(event.target.value))} /></div></label>
            <label>CALCINED CLAY MIN / MAX<div className="inline-inputs"><input type="number" value={clayMin} onChange={(event) => setClayMin(Number(event.target.value))} /><input type="number" value={clayMax} onChange={(event) => setClayMax(Number(event.target.value))} /></div></label>
            <label>LIMESTONE MIN / MAX<div className="inline-inputs"><input type="number" value={limestoneMin} onChange={(event) => setLimestoneMin(Number(event.target.value))} /><input type="number" value={limestoneMax} onChange={(event) => setLimestoneMax(Number(event.target.value))} /></div></label>
            <label>GYPSUM MIN / MAX<div className="inline-inputs"><input type="number" value={gypsumMin} onChange={(event) => setGypsumMin(Number(event.target.value))} /><input type="number" value={gypsumMax} onChange={(event) => setGypsumMax(Number(event.target.value))} /></div></label>
            <label>CLAY : LIMESTONE RATIO MIN / MAX<div className="inline-inputs"><input type="number" step="0.1" value={clayLimestoneRatioMin} onChange={(event) => setClayLimestoneRatioMin(Number(event.target.value))} /><input type="number" step="0.1" value={clayLimestoneRatioMax} onChange={(event) => setClayLimestoneRatioMax(Number(event.target.value))} /></div></label>
          </div>

          <details className="basis-panel"><summary>ADVANCED OBJECTIVE WEIGHTS</summary>
            <p className="note">Higher values make the deterministic solver penalise that dimension more strongly.</p>
            <div className="form-grid two">
              <label>COST WEIGHT<input type="number" min="0" step="0.1" value={costWeight} onChange={(event) => setCostWeight(Number(event.target.value))} /></label>
              <label>CO₂ WEIGHT<input type="number" min="0" step="0.1" value={co2Weight} onChange={(event) => setCo2Weight(Number(event.target.value))} /></label>
              <label>OUTPUT / SHORTFALL WEIGHT<input type="number" min="0" step="0.1" value={outputWeight} onChange={(event) => setOutputWeight(Number(event.target.value))} /></label>
              <label>ENERGY WEIGHT<input type="number" min="0" step="0.1" value={energyWeight} onChange={(event) => setEnergyWeight(Number(event.target.value))} /></label>
              <label>ROBUSTNESS WEIGHT<input type="number" min="0" step="0.1" value={robustnessWeight} onChange={(event) => setRobustnessWeight(Number(event.target.value))} /></label>
              <label>RETROFIT COMPLEXITY WEIGHT<input type="number" min="0" step="0.1" value={complexityWeight} onChange={(event) => setComplexityWeight(Number(event.target.value))} /></label>
              <label>CLINKER-FACTOR WEIGHT<input type="number" min="0" step="0.1" value={clinkerFactorWeight} onChange={(event) => setClinkerFactorWeight(Number(event.target.value))} /></label>
            </div>
          </details>

          <details className="basis-panel"><summary>PROJECT, BIS AND PILOT CONSTRAINTS</summary>
            <div className="form-grid two">
              <label>BIS / PRODUCT CONSTRAINTS<textarea rows={4} value={bisConstraints} onChange={(event) => setBisConstraints(event.target.value)} /></label>
              <label>CUSTOMER CONSTRAINTS<textarea rows={4} value={customerConstraints} onChange={(event) => setCustomerConstraints(event.target.value)} /></label>
              <label>PILOT QUANTITY T<input type="number" min="1" value={pilotQuantity} onChange={(event) => setPilotQuantity(Number(event.target.value))} /></label>
              <label>PILOT RATE FRACTION<input type="number" min="0.1" max="1" step="0.05" value={pilotRateFraction} onChange={(event) => setPilotRateFraction(Number(event.target.value))} /></label>
              <label>MONITORING HOURS<input type="number" min="1" value={monitoringHours} onChange={(event) => setMonitoringHours(Number(event.target.value))} /></label>
              <label>ENGINEERING NOTES<textarea rows={4} value={projectNotes} onChange={(event) => setProjectNotes(event.target.value)} /></label>
            </div>
          </details>

          <button className="run" disabled={loading || !baselineBlendId || !routeId || !calcinedClayId || !limestoneId || !gypsumId || (supplyMode === "onsite_calcination" && !rawClayId)} onClick={() => void design()}>
            {loading ? "SOLVING ENGINEERING SCENARIOS…" : "RUN STAGE 2 · ENGINEERING SIMULATION"}
          </button>
        </>
      )}

      {stage === 2 && study && (
        <>
          <h3>STAGE 2 · ENGINEERING SIMULATION</h3>
          <section className="route-explainer compatible">
            <div>
              <strong>BASELINE · {study.baseline.blend_name}</strong>
              <span>{study.baseline.route_name}</span>
              <span>{formatValue(study.baseline.predicted_output_tph, " t/h")}</span>
            </div>
            <div>
              <strong>DETERMINISTIC SOLVER · {study.candidates.length} SHORTLISTED</strong>
              <span>{study.algorithm}</span>
              <span>Calculation model {study.calculation_version}</span>
            </div>
          </section>

          <h3>PARETO / OPTIMISED CANDIDATES</h3>
          <div className="recommendation-grid">
            {study.candidates.map((candidate) => (
              <button
                type="button"
                key={candidate.candidate_id}
                className={selectedCandidate?.candidate_id === candidate.candidate_id ? "selected" : ""}
                onClick={() => setSelectedCandidateId(candidate.candidate_id)}
              >
                <strong>#{candidate.rank} · {candidate.name}{candidate.pareto_efficient ? " · PARETO" : ""}</strong>
                <span>{rolePercent(candidate, "clinker").toFixed(1)}% clinker · {rolePercent(candidate, "calcined_clay").toFixed(1)}% clay · {rolePercent(candidate, "limestone").toFixed(1)}% limestone · {rolePercent(candidate, "gypsum").toFixed(1)}% gypsum</span>
                <span>{formatValue(candidate.predicted_output_tph, " t/h")} · {formatValue(candidate.electricity_kwh_t, " kWh/t")} · {formatValue(candidate.thermal_kcal_kg, " kcal/kg", 0)}</span>
                <span>{formatValue(candidate.total_variable_cost_inr_t, " INR/t", 0)} · {formatValue(candidate.material_co2_kg_t, " kg CO₂/t", 0)}</span>
                <span>Robustness {candidate.robustness_score.toFixed(0)}/100 · complexity {candidate.retrofit_complexity_score.toFixed(0)}/100</span>
              </button>
            ))}
          </div>

          {selectedCandidate && (
            <>
              <section className="summary-grid">
                <div><small>OUTPUT</small><strong>{formatValue(selectedCandidate.predicted_output_tph, " t/h")}</strong><span>{formatValue(selectedCandidate.output_delta_vs_ppc_tph, " t/h vs PPC")}</span></div>
                <div><small>BOTTLENECK</small><strong>{selectedCandidate.bottleneck_machine_name ?? "N/A"}</strong></div>
                <div><small>VARIABLE COST</small><strong>{formatValue(selectedCandidate.total_variable_cost_inr_t, " INR/t", 0)}</strong><span>{formatValue(selectedCandidate.material_cost_delta_vs_ppc_inr_t, " INR/t material delta", 0)}</span></div>
                <div><small>MATERIAL CO₂</small><strong>{formatValue(selectedCandidate.material_co2_kg_t, " kg/t", 0)}</strong><span>{formatValue(selectedCandidate.material_co2_delta_vs_ppc_kg_t, " kg/t vs PPC", 0)}</span></div>
                <div><small>ROBUSTNESS</small><strong>{selectedCandidate.robustness_score.toFixed(0)}/100</strong></div>
                <div><small>DETERMINISTIC SCORE</small><strong>{selectedCandidate.deterministic_score.toFixed(1)}</strong></div>
              </section>

              <h3>MULTI-LEVEL FORMULATION CHAIN</h3>
              <div className="recommendation-grid">
                {selectedCandidate.formulation_chain.map((formulationStage) => <div key={formulationStage.level}>
                  <strong>{pretty(formulationStage.level)} · {formulationStage.name}</strong>
                  <span>{formulationStage.purpose}</span>
                  <span>Inputs: {formulationStage.inputs.join(" · ") || "N/A"}</span>
                  <span>Outputs: {formulationStage.outputs.join(" · ") || "N/A"}</span>
                </div>)}
              </div>

              <h3>ROBUSTNESS STRESS TEST</h3>
              <table><thead><tr><th>Scenario</th><th>Formulation</th><th>Output</th><th>Electricity</th><th>Thermal</th><th>Cost</th><th>Chemistry</th></tr></thead><tbody>
                {selectedCandidate.stress_tests.map((item) => <tr key={item.scenario}><td>{pretty(item.scenario)}</td><td>{item.clinker_percent}/{item.calcined_clay_percent}/{item.limestone_percent}/{item.gypsum_percent}</td><td>{formatValue(item.predicted_output_tph, " t/h")}</td><td>{formatValue(item.electricity_kwh_t, " kWh/t")}</td><td>{formatValue(item.thermal_kcal_kg, " kcal/kg", 0)}</td><td>{formatValue(item.total_variable_cost_inr_t, " INR/t", 0)}</td><td>{item.chemistry_complete ? "Complete" : `Missing ${item.unknown_chemistry_fields.join(", ")}`}</td></tr>)}
              </tbody></table>

              <button className="run" disabled={caseLoading} onClick={() => void generateEngineeringCase()}>
                {caseLoading ? "GENERATING AUDITABLE RECOMMENDATIONS…" : "RUN STAGE 3 · GENERATE ENGINEERING RECOMMENDATION"}
              </button>
            </>
          )}
        </>
      )}

      {stage === 3 && engineeringCase && (
        <>
          <h3>STAGE 3 · ENGINEERING RECOMMENDATION</h3>
          <section className={`engineering-decision-banner risk-${engineeringCase.risk_rating}`}>
            <div><small>CASE</small><strong>{engineeringCase.case_id}</strong><span>{engineeringCase.project.project_name} · {engineeringCase.project.revision}</span></div>
            <div><small>CONFIDENCE</small><strong>{engineeringCase.confidence_percent.toFixed(1)}%</strong><span>{engineeringCase.confidence_band.toUpperCase()}</span></div>
            <div><small>RISK</small><strong>{engineeringCase.risk_rating.toUpperCase()}</strong><span>{engineeringCase.calibration_sample_count} plant calibration record(s)</span></div>
          </section>
          <div className="engineering-executive">{engineeringCase.executive_summary}</div>

          <h3>PREDICTION · CONFIDENCE · REASON · REQUIRED VALIDATION</h3>
          <div className="engineering-prediction-grid">
            {engineeringCase.predictions.map((item) => (
              <article key={item.code} className={`engineering-prediction risk-${item.risk}`}>
                <small>{pretty(item.category)}</small>
                <strong>{item.label}</strong>
                <b>{predictionValue(item)}</b>
                <span>Confidence {item.confidence_percent.toFixed(0)}% · {item.confidence_band.toUpperCase()}</span>
                <p>{item.reason}</p>
                <details><summary>Required validation</summary><ul>{item.required_validation.map((entry) => <li key={entry}>{entry}</li>)}</ul></details>
              </article>
            ))}
          </div>

          <h3>ENGINEERING ACTIONS</h3>
          <div className="engineering-recommendations">
            {engineeringCase.recommendations.map((recommendation) => (
              <article key={recommendation.recommendation_id} className={`engineering-recommendation risk-${recommendation.risk}`}>
                <header><strong>{recommendation.priority} · {recommendation.title}</strong><span>{recommendation.discipline} · confidence {recommendation.confidence_percent.toFixed(0)}%</span></header>
                <table><thead><tr><th>Parameter</th><th>Current</th><th>Recommended</th><th>Change</th><th>Rationale</th></tr></thead><tbody>
                  {recommendation.actions.map((action) => <tr key={`${recommendation.recommendation_id}-${action.parameter}`}><td>{action.parameter}</td><td>{action.current_value ?? "N/A"}</td><td>{action.recommended_value ?? "N/A"} {action.unit ?? ""}</td><td>{action.change ?? "—"}</td><td>{action.rationale}</td></tr>)}
                </tbody></table>
                <p><b>Proceed condition:</b> {recommendation.proceed_condition}</p>
                <details><summary>Reasons and required validation</summary><ul>{recommendation.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul><h4>Validation</h4><ul>{recommendation.required_validation.map((entry) => <li key={entry}>{entry}</li>)}</ul></details>
              </article>
            ))}
          </div>

          <div className="action-row">
            <button onClick={() => setStage(4)}>CONTINUE TO STAGE 4 · WORKBOOK</button>
            <button disabled={saving} onClick={() => void saveCandidate()}>{saving ? "SAVING…" : "SAVE SELECTED LC3 BLEND"}</button>
          </div>
        </>
      )}

      {stage === 4 && engineeringCase && (
        <>
          <h3>STAGE 4 · ENGINEERING WORKBOOK</h3>
          <p className="note">
            The workbook contains cover, project, assumption, missing-data, input, calculation, validation, decision, pilot and learning sheets. Blue cells are plant inputs; yellow cells are BRIXTA assumptions; grey cells are formulas; green cells are recorded actuals.
          </p>
          <section className="summary-grid">
            <div><small>WORKBOOK CASE</small><strong>{engineeringCase.case_id}</strong></div>
            <div><small>REVISION</small><strong>{engineeringCase.project.revision}</strong></div>
            <div><small>MISSING DATA</small><strong>{engineeringCase.missing_data.length}</strong></div>
            <div><small>RECOMMENDATIONS</small><strong>{engineeringCase.recommendations.length}</strong></div>
            <div><small>RISK</small><strong>{engineeringCase.risk_rating.toUpperCase()}</strong></div>
            <div><small>CONFIDENCE</small><strong>{engineeringCase.confidence_percent.toFixed(1)}%</strong></div>
          </section>

          <a className="run button-link" href={`${API}/api/engineering/cases/${engineeringCase.case_id}/export.xlsx`} target="_blank" rel="noreferrer">EXPORT COMPLETE ENGINEERING WORKBOOK</a>

          <h3>DATA THE PLANT MUST REPLACE OR VERIFY</h3>
          <table><thead><tr><th>Category</th><th>Data item</th><th>Why required</th></tr></thead><tbody>
            {engineeringCase.missing_data.map((item) => <tr key={`${item.category}-${item.item}`}><td>{pretty(item.category)}</td><td>{item.item}</td><td>{item.reason}</td></tr>)}
          </tbody></table>

          <button className="run" onClick={() => setStage(5)}>CONTINUE TO STAGE 5 · PILOT BATCH</button>
        </>
      )}

      {stage === 5 && engineeringCase && (
        <>
          <h3>STAGE 5 · PILOT PRODUCTION</h3>
          <section className="summary-grid">
            <div><small>PILOT QUANTITY</small><strong>{engineeringCase.pilot_plan.pilot_quantity_t.toFixed(0)} t</strong></div>
            <div><small>PILOT RATE</small><strong>{formatValue(engineeringCase.pilot_plan.pilot_rate_tph, " t/h")}</strong></div>
            <div><small>SAMPLING ITEMS</small><strong>{engineeringCase.pilot_plan.sampling_plan.length}</strong></div>
            <div><small>LAB TESTS</small><strong>{engineeringCase.pilot_plan.required_lab_tests.length}</strong></div>
            <div><small>GO / NO-GO</small><strong>{engineeringCase.pilot_plan.go_no_go_criteria.length}</strong></div>
            <div><small>MONITORING</small><strong>{monitoringHours} h</strong></div>
          </section>

          <h3>PILOT FORMULATION</h3>
          <table><thead><tr><th>Role</th><th>Material</th><th>Dosage</th></tr></thead><tbody>
            {engineeringCase.pilot_plan.formulation.map((item) => <tr key={String(item.role)}><td>{pretty(String(item.role))}</td><td>{String(item.material)}</td><td>{Number(item.percentage).toFixed(2)}%</td></tr>)}
          </tbody></table>

          <h3>MACHINE, KILN AND MILL SETTINGS</h3>
          <table><thead><tr><th>Area</th><th>Parameter</th><th>Target</th><th>Basis</th><th>Validation</th></tr></thead><tbody>
            {[...engineeringCase.pilot_plan.machine_settings, ...engineeringCase.pilot_plan.kiln_settings, ...engineeringCase.pilot_plan.mill_settings].map((item) => <tr key={`${item.area}-${item.parameter}`}><td>{pretty(item.area)}</td><td>{item.parameter}</td><td>{item.target ?? "N/A"} {item.unit ?? ""}</td><td>{item.basis}</td><td>{item.validation}</td></tr>)}
          </tbody></table>

          <div className="engineering-list-grid">
            <section><h4>SAMPLING PLAN</h4><ol>{engineeringCase.pilot_plan.sampling_plan.map((item) => <li key={item}>{item}</li>)}</ol></section>
            <section><h4>REQUIRED LAB TESTS</h4><ol>{engineeringCase.pilot_plan.required_lab_tests.map((item) => <li key={item}>{item}</li>)}</ol></section>
            <section><h4>GO / NO-GO CRITERIA</h4><ol>{engineeringCase.pilot_plan.go_no_go_criteria.map((item) => <li key={item}>{item}</li>)}</ol></section>
            <section><h4>MONITORING PLAN</h4><ol>{engineeringCase.pilot_plan.monitoring_plan.map((item) => <li key={item}>{item}</li>)}</ol></section>
          </div>

          <button className="run" onClick={() => setStage(6)}>CONTINUE TO STAGE 6 · IMPORT ACTUALS</button>
        </>
      )}

      {stage === 6 && engineeringCase && (
        <>
          <h3>STAGE 6 · LEARNING AND RECALIBRATION</h3>
          <p className="note">Import pilot or plant actuals. BRIXTA compares them with the prediction, calculates error, updates confidence and stores a median plant/product calibration profile for future cases.</p>
          <div className="form-grid two">
            <label>ACTUAL OUTPUT T/H<input value={actuals.actual_output_tph} onChange={(event) => updateActual("actual_output_tph", event.target.value)} /></label>
            <label>ACTUAL ELECTRICITY KWH/T<input value={actuals.actual_electricity_kwh_t} onChange={(event) => updateActual("actual_electricity_kwh_t", event.target.value)} /></label>
            <label>ACTUAL THERMAL KCAL/KG<input value={actuals.actual_thermal_kcal_kg} onChange={(event) => updateActual("actual_thermal_kcal_kg", event.target.value)} /></label>
            <label>ACTUAL VARIABLE COST INR/T<input value={actuals.actual_variable_cost_inr_t} onChange={(event) => updateActual("actual_variable_cost_inr_t", event.target.value)} /></label>
            <label>ACTUAL MATERIAL CO₂ KG/T<input value={actuals.actual_material_co2_kg_t} onChange={(event) => updateActual("actual_material_co2_kg_t", event.target.value)} /></label>
            <label>ACTUAL FREE LIME %<input value={actuals.actual_free_lime_percent} onChange={(event) => updateActual("actual_free_lime_percent", event.target.value)} /></label>
            <label>ACTUAL 3-DAY STRENGTH MPA<input value={actuals.actual_strength_3d_mpa} onChange={(event) => updateActual("actual_strength_3d_mpa", event.target.value)} /></label>
            <label>ACTUAL 28-DAY STRENGTH MPA<input value={actuals.actual_strength_28d_mpa} onChange={(event) => updateActual("actual_strength_28d_mpa", event.target.value)} /></label>
            <label>XRF COMPARISON<textarea rows={3} value={actuals.xrf_comparison} onChange={(event) => updateActual("xrf_comparison", event.target.value)} /></label>
            <label>XRD COMPARISON<textarea rows={3} value={actuals.xrd_comparison} onChange={(event) => updateActual("xrd_comparison", event.target.value)} /></label>
            <label>POWER OBSERVATION<textarea rows={3} value={actuals.power_observation} onChange={(event) => updateActual("power_observation", event.target.value)} /></label>
            <label>COAL / FUEL OBSERVATION<textarea rows={3} value={actuals.coal_observation} onChange={(event) => updateActual("coal_observation", event.target.value)} /></label>
            <label>THERMAL OBSERVATION<textarea rows={3} value={actuals.thermal_observation} onChange={(event) => updateActual("thermal_observation", event.target.value)} /></label>
            <label>ROOT CAUSE<textarea rows={3} value={actuals.root_cause} onChange={(event) => updateActual("root_cause", event.target.value)} /></label>
            <label>COMMENTS<textarea rows={3} value={actuals.comments} onChange={(event) => updateActual("comments", event.target.value)} /></label>
            <label>DECISION<select value={actuals.decision} onChange={(event) => updateActual("decision", event.target.value as Actuals["decision"])}><option value="hold">HOLD</option><option value="proceed">PROCEED</option><option value="reject">REJECT</option></select></label>
            <label>ENGINEER SIGN-OFF<input value={actuals.engineer_signoff} onChange={(event) => updateActual("engineer_signoff", event.target.value)} /></label>
            <label>QUALITY HEAD SIGN-OFF<input value={actuals.quality_head_signoff} onChange={(event) => updateActual("quality_head_signoff", event.target.value)} /></label>
            <label>PLANT HEAD SIGN-OFF<input value={actuals.plant_head_signoff} onChange={(event) => updateActual("plant_head_signoff", event.target.value)} /></label>
          </div>
          <button className="run" disabled={learningLoading} onClick={() => void importActuals()}>{learningLoading ? "CALCULATING PREDICTION ERROR…" : "IMPORT ACTUALS AND RECALIBRATE"}</button>

          {learning && (
            <>
              <section className="summary-grid">
                <div><small>MAPE</small><strong>{learning.mean_absolute_percent_error === null ? "N/A" : `${learning.mean_absolute_percent_error.toFixed(2)}%`}</strong></div>
                <div><small>CONFIDENCE BEFORE</small><strong>{learning.confidence_before_percent.toFixed(1)}%</strong></div>
                <div><small>CONFIDENCE AFTER</small><strong>{learning.confidence_after_percent.toFixed(1)}%</strong></div>
                <div><small>CALIBRATION SAMPLES</small><strong>{learning.calibration_sample_count}</strong></div>
              </section>
              <div className="engineering-executive">{learning.learning_summary}</div>
              <table><thead><tr><th>Metric</th><th>Predicted</th><th>Actual</th><th>Absolute error</th><th>% error</th><th>Correction factor</th></tr></thead><tbody>
                {learning.prediction_errors.map((item) => <tr key={item.metric}><td>{pretty(item.metric)}</td><td>{item.predicted ?? "N/A"}</td><td>{item.actual ?? "N/A"}</td><td>{item.absolute_error?.toFixed(3) ?? "N/A"}</td><td>{item.percent_error?.toFixed(2) ?? "N/A"}</td><td>{item.recalibration_factor?.toFixed(4) ?? "N/A"}</td></tr>)}
              </tbody></table>
              <a className="run button-link" href={`${API}/api/engineering/cases/${engineeringCase.case_id}/export.xlsx`} target="_blank" rel="noreferrer">RE-EXPORT WORKBOOK WITH ACTUALS AND LEARNING</a>
            </>
          )}
        </>
      )}
    </section>
  );
}
