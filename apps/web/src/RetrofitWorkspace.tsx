import { useEffect, useMemo, useState } from "react";

import { API, req } from "./api";
import { TrustCenter } from "./TrustCenter";
import type {
  EngineeringCase,
  EngineeringCatalog,
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

export type WorkflowSection =
  | "materials"
  | "formulation"
  | "plant"
  | "retrofit"
  | "export";

export type WorkflowTool =
  | "material-editor"
  | "blend-editor"
  | "machine-editor"
  | "route-editor"
  | "cost-editor"
  | "library"
  | "run-library";

export type RetrofitProgress = {
  hasStudy: boolean;
  hasEngineeringCase: boolean;
  selectedCandidateName: string | null;
};

type Props = {
  section: WorkflowSection;
  materials: Material[];
  blends: Blend[];
  routes: Route[];
  costBooks: CostBook[];
  baselineBlendId: string;
  routeId: string;
  costBookId: string;
  targetOutput: number;
  onBaselineBlendChange: (blendId: string) => void;
  onRouteChange: (routeId: string) => void;
  onCostBookChange: (costBookId: string) => void;
  onTargetOutputChange: (targetOutput: number) => void;
  onBlendCreated: (blend: Blend) => void;
  onNavigate: (section: "materials" | "formulation" | "plant" | "retrofit" | "scenarios" | "validation" | "export") => void;
  onOpenTool: (tool: WorkflowTool) => void;
  onProgressChange?: (progress: RetrofitProgress) => void;
};

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
  use_for_calibration: boolean;
  evidence_references: string;
};

const SECTION_COPY: Record<WorkflowSection, { title: string; subtitle: string }> = {
  materials: {
    title: "MATERIALS",
    subtitle: "Choose traceable plant inputs and identify chemistry, cost and evidence gaps before formulation.",
  },
  formulation: {
    title: "FORMULATION",
    subtitle: "Define the existing PPC basis, LC3 dosage envelope and optimisation priorities.",
  },
  plant: {
    title: "PLANT",
    subtitle: "Bind the formulation to the plant route, commercial basis, production target and project constraints.",
  },
  retrofit: {
    title: "ENGINEERING DECISION",
    subtitle: "Submit scenarios to evidence, uncertainty, multidisciplinary review, risk and validation gates.",
  },
  export: {
    title: "EXPORT & PILOT",
    subtitle: "Package the decision, pilot plan, validation sheets and learning loop into the engineering workbook.",
  },
};

function pretty(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (match) => match.toUpperCase());
}

function formatValue(value: number | null, suffix: string, digits = 1): string {
  return value === null ? "N/A" : `${value.toFixed(digits)}${suffix}`;
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

function selectedName<T extends { [key: string]: unknown }>(
  items: T[],
  idField: keyof T,
  nameField: keyof T,
  selectedId: string,
): string {
  const item = items.find((candidate) => String(candidate[idField]) === selectedId);
  return item ? String(item[nameField]) : "Not selected";
}

function WorkflowFooter({
  previous,
  next,
  onNavigate,
}: {
  previous?: { label: string; section: Parameters<Props["onNavigate"]>[0] };
  next?: { label: string; section: Parameters<Props["onNavigate"]>[0]; disabled?: boolean };
  onNavigate: Props["onNavigate"];
}) {
  return (
    <div className="workflow-footer">
      <div>
        {previous && <button type="button" onClick={() => onNavigate(previous.section)}>← {previous.label}</button>}
      </div>
      <div>
        {next && <button className="run" type="button" disabled={next.disabled} onClick={() => onNavigate(next.section)}>{next.label} →</button>}
      </div>
    </div>
  );
}

export function RetrofitWorkspace({
  section,
  materials,
  blends,
  routes,
  costBooks,
  baselineBlendId,
  routeId,
  costBookId,
  targetOutput,
  onBaselineBlendChange,
  onRouteChange,
  onCostBookChange,
  onTargetOutputChange,
  onBlendCreated,
  onNavigate,
  onOpenTool,
  onProgressChange,
}: Props) {
  const ppcBlends = useMemo(
    () => blends
      .filter((item) => item.blend_class === "finished_cement")
      .sort((left, right) => Number(!left.family.toLowerCase().includes("ppc")) - Number(!right.family.toLowerCase().includes("ppc"))),
    [blends],
  );

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

  const [catalog, setCatalog] = useState<EngineeringCatalog | null>(null);
  const [projectName, setProjectName] = useState("Engineering Decision");
  const [plantName, setPlantName] = useState("Reference plant");
  const [engineer, setEngineer] = useState("BRIXTA Engineering");
  const [productDefinitionId, setProductDefinitionId] = useState("lc3");
  const [revision, setRevision] = useState("R0");
  const [qualityStandardIds, setQualityStandardIds] = useState("");
  const [bisConstraints, setBisConstraints] = useState("Applicable BIS/product clauses to be confirmed");
  const [validationResources, setValidationResources] = useState("");
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
    use_for_calibration: false,
    evidence_references: "",
  });

  useEffect(() => {
    void req<EngineeringCatalog>("/api/engineering/catalog")
      .then(setCatalog)
      .catch(() => setCatalog(null));
  }, []);

  useEffect(() => {
    if (!baselineBlendId || !ppcBlends.some((item) => item.blend_id === baselineBlendId)) {
      const preferred = ppcBlends.find((item) => item.family.toLowerCase().includes("ppc")) ?? ppcBlends[0];
      if (preferred) onBaselineBlendChange(preferred.blend_id);
    }
    if (!routeId || !routes.some((item) => item.route_id === routeId)) {
      const preferred = routes.find((item) => item.route_kind === "integrated") ?? routes[0];
      if (preferred) onRouteChange(preferred.route_id);
    }
    if (costBookId && !costBooks.some((item) => item.cost_book_id === costBookId)) {
      onCostBookChange("");
    }
    if (!calcinedClayId) setCalcinedClayId(materials.find((item) => item.material_type === "calcined_clay")?.material_id ?? "");
    if (!limestoneId) setLimestoneId(materials.find((item) => item.material_type === "limestone" && item.functional_role === "cement_addition")?.material_id ?? materials.find((item) => item.material_type === "limestone")?.material_id ?? "");
    if (!gypsumId) setGypsumId(materials.find((item) => item.functional_role === "set_regulator")?.material_id ?? "");
    if (!rawClayId) setRawClayId(materials.find((item) => ["clay", "shale", "bauxite", "laterite"].includes(item.material_type))?.material_id ?? "");
  }, [
    baselineBlendId,
    routeId,
    costBookId,
    calcinedClayId,
    limestoneId,
    gypsumId,
    rawClayId,
    ppcBlends,
    routes,
    costBooks,
    materials,
    onBaselineBlendChange,
    onRouteChange,
    onCostBookChange,
  ]);

  const selectedCandidate = study?.candidates.find((item) => item.candidate_id === selectedCandidateId)
    ?? study?.candidates[0]
    ?? null;
  const selectedProductDefinition = catalog?.product_definitions.find((item) => item.product_id === productDefinitionId) ?? null;

  useEffect(() => {
    onProgressChange?.({
      hasStudy: Boolean(study),
      hasEngineeringCase: Boolean(engineeringCase),
      selectedCandidateName: selectedCandidate?.name ?? null,
    });
  }, [study, engineeringCase, selectedCandidate, onProgressChange]);

  const materialReadiness = [
    { label: "Calcined clay", ready: Boolean(calcinedClayId), count: materials.filter((item) => ["calcined_clay", "metakaolin"].includes(item.material_type)).length },
    { label: "Cement limestone", ready: Boolean(limestoneId), count: materials.filter((item) => item.material_type === "limestone").length },
    { label: "Gypsum / set regulator", ready: Boolean(gypsumId), count: materials.filter((item) => item.functional_role === "set_regulator" || item.material_type === "gypsum").length },
    { label: "Raw clay", ready: supplyMode === "purchased_calcined_clay" || Boolean(rawClayId), count: materials.filter((item) => ["clay", "shale", "bauxite", "laterite"].includes(item.material_type)).length },
  ];

  const readyToDesign = Boolean(
    baselineBlendId
    && routeId
    && calcinedClayId
    && limestoneId
    && gypsumId
    && (supplyMode === "purchased_calcined_clay" || rawClayId),
  );

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
            product_target: selectedProductDefinition?.name ?? "Configured cement product",
            product_definition_id: productDefinitionId || null,
            revision,
            quality_standard_ids: qualityStandardIds.split("\n").map((item) => item.trim()).filter(Boolean),
            bis_constraints: bisConstraints.split("\n").map((item) => item.trim()).filter(Boolean),
            customer_constraints: customerConstraints.split("\n").map((item) => item.trim()).filter(Boolean),
            validation_resources: validationResources.split("\n").map((item) => item.trim()).filter(Boolean),
            pilot_quantity_t: pilotQuantity,
            pilot_rate_fraction: pilotRateFraction,
            monitoring_hours: monitoringHours,
            notes: projectNotes || null,
          },
        }),
      });
      setEngineeringCase(nextCase);
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
            use_for_calibration: actuals.use_for_calibration,
            evidence_references: actuals.evidence_references.split("\n").map((item) => item.trim()).filter(Boolean),
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

  const copy = SECTION_COPY[section];

  return (
    <section className="guide wide-guide retrofit-workspace engineering-workflow">
      <div className="module-heading">
        <div>
          <small>BRIXTA ENGINEERING WORKFLOW</small>
          <h2>{copy.title}</h2>
          <p>{copy.subtitle}</p>
        </div>
        <div className="module-status">
          <span>{study ? "STUDY READY" : "NO STUDY"}</span>
          <strong>{engineeringCase ? `CASE ${engineeringCase.case_id}` : "REFERENCE MODE"}</strong>
        </div>
      </div>

      {error && <div className="err">{error}</div>}

      {section === "materials" && (
        <>
          <section className="workflow-context-panel">
            <div><small>MATERIAL RECORDS</small><strong>{materials.length}</strong><span>Active library inputs</span></div>
            {materialReadiness.map((item) => <div className={item.ready ? "ready" : "missing"} key={item.label}><small>{item.label}</small><strong>{item.ready ? "READY" : "MISSING"}</strong><span>{item.count} compatible record(s)</span></div>)}
          </section>

          <h3>LC3 MATERIAL SOURCES</h3>
          <div className="form-grid two">
            <label>CALCINED-CLAY PRODUCT / PROXY
              <select value={calcinedClayId} onChange={(event) => setCalcinedClayId(event.target.value)}>
                <option value="">Select a calcined-clay record</option>
                {materials.filter((item) => ["calcined_clay", "metakaolin"].includes(item.material_type)).map((item) => <option key={item.material_id} value={item.material_id}>{item.name}</option>)}
              </select>
            </label>
            <label>CEMENT-GRADE LIMESTONE
              <select value={limestoneId} onChange={(event) => setLimestoneId(event.target.value)}>
                <option value="">Select a limestone record</option>
                {materials.filter((item) => item.material_type === "limestone").map((item) => <option key={item.material_id} value={item.material_id}>{item.name}</option>)}
              </select>
            </label>
            <label>GYPSUM / SET REGULATOR
              <select value={gypsumId} onChange={(event) => setGypsumId(event.target.value)}>
                <option value="">Select a gypsum record</option>
                {materials.filter((item) => item.functional_role === "set_regulator" || item.material_type === "gypsum").map((item) => <option key={item.material_id} value={item.material_id}>{item.name}</option>)}
              </select>
            </label>
            <label>RAW KAOLINITIC / CLAY SOURCE
              <select value={rawClayId} onChange={(event) => setRawClayId(event.target.value)}>
                <option value="">Select a raw-clay record</option>
                {materials.filter((item) => ["clay", "shale", "bauxite", "laterite"].includes(item.material_type) || item.functional_role === "raw_kiln_feed").map((item) => <option key={item.material_id} value={item.material_id}>{item.name}</option>)}
              </select>
            </label>
          </div>

          <div className="data-flow-note">
            <strong>DOWNSTREAM DATA FLOW</strong>
            <span>These records supply chemistry, moisture, LOI, material cost and CO₂ to Formulation, Retrofit, Scenarios and Export. Missing fields remain explicit assumptions; they are not silently converted to zero.</span>
          </div>

          <div className="module-tool-row">
            <button type="button" onClick={() => onOpenTool("material-editor")}>OPEN FULL MATERIAL EDITOR</button>
            <button type="button" onClick={() => onOpenTool("library")}>OPEN VERSIONED LIBRARY</button>
          </div>
          <WorkflowFooter next={{ label: "NEXT STEP · FORMULATION", section: "formulation", disabled: materialReadiness.some((item) => !item.ready) }} onNavigate={onNavigate} />
        </>
      )}

      {section === "formulation" && (
        <>
          <section className="workflow-context-panel compact">
            <div><small>BASELINE FORMULATION</small><strong>{selectedName(ppcBlends, "blend_id", "name", baselineBlendId)}</strong><span>Feeds the retrofit baseline</span></div>
            <div><small>LC3 SEARCH SPACE</small><strong>{clinkerMin}–{clinkerMax}% clinker</strong><span>{targetCandidates} candidates requested</span></div>
            <div><small>OBJECTIVE</small><strong>COST · CO₂ · OUTPUT</strong><span>Weighted deterministic ranking</span></div>
          </section>

          <div className="form-grid two">
            <label>EXISTING PPC / FINISHED-CEMENT BLEND
              <select value={baselineBlendId} onChange={(event) => onBaselineBlendChange(event.target.value)}>
                {ppcBlends.map((item) => <option key={item.blend_id} value={item.blend_id}>{item.name} · {item.family}</option>)}
              </select>
            </label>
            <label>SHORTLIST SIZE<input type="number" min="3" max="25" step="1" value={targetCandidates} onChange={(event) => setTargetCandidates(Number(event.target.value))} /></label>
          </div>

          <h3>FORMULATION BOUNDS</h3>
          <div className="form-grid two">
            <label>CLINKER MIN / MAX<div className="inline-inputs"><input type="number" step="0.1" value={clinkerMin} onChange={(event) => setClinkerMin(Number(event.target.value))} /><input type="number" step="0.1" value={clinkerMax} onChange={(event) => setClinkerMax(Number(event.target.value))} /></div></label>
            <label>CALCINED CLAY MIN / MAX<div className="inline-inputs"><input type="number" step="0.1" value={clayMin} onChange={(event) => setClayMin(Number(event.target.value))} /><input type="number" step="0.1" value={clayMax} onChange={(event) => setClayMax(Number(event.target.value))} /></div></label>
            <label>LIMESTONE MIN / MAX<div className="inline-inputs"><input type="number" step="0.1" value={limestoneMin} onChange={(event) => setLimestoneMin(Number(event.target.value))} /><input type="number" step="0.1" value={limestoneMax} onChange={(event) => setLimestoneMax(Number(event.target.value))} /></div></label>
            <label>GYPSUM MIN / MAX<div className="inline-inputs"><input type="number" step="0.1" value={gypsumMin} onChange={(event) => setGypsumMin(Number(event.target.value))} /><input type="number" step="0.1" value={gypsumMax} onChange={(event) => setGypsumMax(Number(event.target.value))} /></div></label>
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

          <div className="module-tool-row">
            <button type="button" onClick={() => onOpenTool("blend-editor")}>OPEN FULL FORMULATION COMPOSER</button>
          </div>
          <WorkflowFooter previous={{ label: "MATERIALS", section: "materials" }} next={{ label: "NEXT STEP · PLANT", section: "plant", disabled: !baselineBlendId }} onNavigate={onNavigate} />
        </>
      )}

      {section === "plant" && (
        <>
          <section className="workflow-context-panel compact">
            <div><small>PLANT ROUTE</small><strong>{selectedName(routes, "route_id", "name", routeId)}</strong><span>Equipment and process topology</span></div>
            <div><small>COMMERCIAL BASIS</small><strong>{selectedName(costBooks, "cost_book_id", "name", costBookId)}</strong><span>{costBookId ? "Versioned cost book" : "Reference placeholders"}</span></div>
            <div><small>PRODUCTION TARGET</small><strong>{targetOutput.toFixed(1)} t/h</strong><span>LC3 design basis</span></div>
          </section>

          <div className="form-grid two">
            <label>PROJECT NAME<input value={projectName} onChange={(event) => setProjectName(event.target.value)} /></label>
            <label>PLANT<input value={plantName} onChange={(event) => setPlantName(event.target.value)} /></label>
            <label>ENGINEER<input value={engineer} onChange={(event) => setEngineer(event.target.value)} /></label>
            <label>REVISION<input value={revision} onChange={(event) => setRevision(event.target.value)} /></label>
            <label>CONFIGURED PRODUCT DEFINITION
              <select value={productDefinitionId} onChange={(event) => setProductDefinitionId(event.target.value)}>
                {(catalog?.product_definitions ?? []).map((item) => <option key={item.product_id} value={item.product_id}>{item.name} · {item.family}</option>)}
              </select>
            </label>
            <label>QUALITY STANDARD IDS / REVISIONS<textarea rows={3} value={qualityStandardIds} onChange={(event) => setQualityStandardIds(event.target.value)} placeholder="One versioned standard or plant specification per line" /></label>
            <label>EXISTING PLANT ROUTE
              <select value={routeId} onChange={(event) => onRouteChange(event.target.value)}>
                {routes.map((item) => <option key={item.route_id} value={item.route_id}>{item.name} · {pretty(item.route_kind)}</option>)}
              </select>
            </label>
            <label>COST BOOK
              <select value={costBookId} onChange={(event) => onCostBookChange(event.target.value)}>
                <option value="">Reference tariffs and material placeholders</option>
                {costBooks.map((item) => <option key={item.cost_book_id} value={item.cost_book_id}>{item.name} · v{item.version}</option>)}
              </select>
            </label>
            <label>TARGET PRODUCT OUTPUT T/H<input type="number" min="0.1" step="0.1" value={targetOutput} onChange={(event) => onTargetOutputChange(Number(event.target.value))} /></label>
            <label>CLAY SUPPLY PATHWAY
              <select value={supplyMode} onChange={(event) => setSupplyMode(event.target.value as typeof supplyMode)}>
                <option value="purchased_calcined_clay">Purchase calcined clay</option>
                <option value="onsite_calcination">Calcine raw clay onsite</option>
              </select>
            </label>
            <label>BIS / PRODUCT CONSTRAINTS<textarea rows={4} value={bisConstraints} onChange={(event) => setBisConstraints(event.target.value)} /></label>
            <label>CUSTOMER CONSTRAINTS<textarea rows={4} value={customerConstraints} onChange={(event) => setCustomerConstraints(event.target.value)} /></label>
            <label>AVAILABLE VALIDATION RESOURCES<textarea rows={4} value={validationResources} onChange={(event) => setValidationResources(event.target.value)} placeholder="Examples: XRF, XRD, free lime, compressive strength, power meter, kiln heat balance" /></label>
            <label>CONFIGURED PRODUCT REQUIREMENTS<textarea rows={4} readOnly value={selectedProductDefinition ? [...selectedProductDefinition.required_process_capabilities, ...selectedProductDefinition.required_validation].join("\n") : "Product catalog unavailable"} /></label>
            <label>PILOT QUANTITY T<input type="number" min="1" step="1" value={pilotQuantity} onChange={(event) => setPilotQuantity(Number(event.target.value))} /></label>
            <label>PILOT RATE FRACTION<input type="number" min="0.1" max="1" step="0.05" value={pilotRateFraction} onChange={(event) => setPilotRateFraction(Number(event.target.value))} /></label>
            <label>MONITORING HOURS<input type="number" min="1" step="1" value={monitoringHours} onChange={(event) => setMonitoringHours(Number(event.target.value))} /></label>
            <label>ENGINEERING NOTES<textarea rows={4} value={projectNotes} onChange={(event) => setProjectNotes(event.target.value)} /></label>
          </div>

          <div className="module-tool-row three">
            <button type="button" onClick={() => onOpenTool("machine-editor")}>EDIT MACHINES</button>
            <button type="button" onClick={() => onOpenTool("route-editor")}>EDIT PROCESS ROUTE</button>
            <button type="button" onClick={() => onOpenTool("cost-editor")}>EDIT COSTS & TARIFFS</button>
          </div>
          <WorkflowFooter previous={{ label: "FORMULATION", section: "formulation" }} next={{ label: "NEXT STEP · ENGINEERING DECISION", section: "retrofit", disabled: !routeId || targetOutput <= 0 || !productDefinitionId }} onNavigate={onNavigate} />
        </>
      )}

      {section === "retrofit" && (
        <>
          <section className="retrofit-readiness">
            <div>
              <small>FORMULATION</small>
              <strong>{selectedName(ppcBlends, "blend_id", "name", baselineBlendId)}</strong>
              <span>Clinker {clinkerMin}–{clinkerMax}% · clay {clayMin}–{clayMax}% · limestone {limestoneMin}–{limestoneMax}%</span>
            </div>
            <div>
              <small>PLANT</small>
              <strong>{selectedName(routes, "route_id", "name", routeId)}</strong>
              <span>{targetOutput.toFixed(1)} t/h target · {pretty(supplyMode)}</span>
            </div>
            <div className={readyToDesign ? "ready" : "missing"}>
              <small>READINESS</small>
              <strong>{readyToDesign ? "READY TO SOLVE" : "INPUTS INCOMPLETE"}</strong>
              <span>{readyToDesign ? "All required references resolved" : "Return to Materials, Formulation or Plant"}</span>
            </div>
          </section>

          <div className="action-row">
            <button className="run" disabled={loading || !readyToDesign} onClick={() => void design()}>
              {loading ? "SOLVING ENGINEERING SCENARIOS…" : study ? "RE-RUN RETROFIT DESIGN" : "RUN RETROFIT DESIGN"}
            </button>
          </div>

          {!study && <div className="empty-workflow-state"><strong>No retrofit study yet.</strong><span>The solver will prune infeasible formulations, rank Pareto candidates, stress-test variability and identify plant asset gaps.</span></div>}

          {study && (
            <>
              <section className="route-explainer compatible">
                <div><strong>BASELINE · {study.baseline.blend_name}</strong><span>{study.baseline.route_name}</span><span>{formatValue(study.baseline.predicted_output_tph, " t/h")}</span></div>
                <div><strong>{study.candidates.length} SHORTLISTED CANDIDATES</strong><span>{study.algorithm}</span><span>Calculation model {study.calculation_version}</span></div>
              </section>

              <h3>PARETO / OPTIMISED CANDIDATES</h3>
              <div className="recommendation-grid">
                {study.candidates.map((candidate) => (
                  <button type="button" key={candidate.candidate_id} className={selectedCandidate?.candidate_id === candidate.candidate_id ? "selected" : ""} onClick={() => setSelectedCandidateId(candidate.candidate_id)}>
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
                    <div><small>SCORE</small><strong>{selectedCandidate.deterministic_score.toFixed(1)}</strong></div>
                  </section>

                  <h3>MISSING / RETROFIT ASSETS</h3>
                  <div className="recommendation-grid">
                    {selectedCandidate.missing_assets.length ? selectedCandidate.missing_assets.map((gap) => <div key={gap.asset_code}><strong>{gap.requirement.toUpperCase()} · {gap.asset_name}</strong><span>{gap.reason}</span><span>{gap.reference_capacity_tph === null ? "Capacity to be engineered" : `${gap.reference_capacity_tph.toFixed(1)} t/h reference capacity`}</span></div>) : <div><strong>NO REQUIRED ASSET GAP FOUND</strong><span>The selected route still requires plant verification.</span></div>}
                  </div>

                  <details open><summary>ROBUSTNESS / SENSITIVITY STRESS TEST</summary>
                    <div className="table-responsive"><table><thead><tr><th>Scenario</th><th>Formulation</th><th>Output</th><th>Electricity</th><th>Thermal</th><th>Cost</th><th>Chemistry</th></tr></thead><tbody>
                      {selectedCandidate.stress_tests.map((item) => <tr key={item.scenario}><td>{pretty(item.scenario)}</td><td>{item.clinker_percent}/{item.calcined_clay_percent}/{item.limestone_percent}/{item.gypsum_percent}</td><td>{formatValue(item.predicted_output_tph, " t/h")}</td><td>{formatValue(item.electricity_kwh_t, " kWh/t")}</td><td>{formatValue(item.thermal_kcal_kg, " kcal/kg", 0)}</td><td>{formatValue(item.total_variable_cost_inr_t, " INR/t", 0)}</td><td>{item.chemistry_complete ? "Complete" : `Missing ${item.unknown_chemistry_fields.join(", ")}`}</td></tr>)}
                    </tbody></table></div>
                  </details>

                  <div className="action-row">
                    <button disabled={saving} onClick={() => void saveCandidate()}>{saving ? "SAVING…" : "SAVE SELECTED LC3 FORMULATION"}</button>
                    <button className="run" disabled={caseLoading} onClick={() => void generateEngineeringCase()}>{caseLoading ? "GENERATING…" : engineeringCase ? "RE-GENERATE ENGINEERING CASE" : "GENERATE ENGINEERING RECOMMENDATION"}</button>
                  </div>
                </>
              )}

              {engineeringCase && (
                <>
                  <div className={`engineering-decision-banner risk-${engineeringCase.risk_rating}`}>
                    <div><small>ENGINEERING DECISION CASE</small><strong>{engineeringCase.status.toUpperCase()}</strong><span>{engineeringCase.executive_summary}</span></div>
                    <div><small>CONFIDENCE</small><strong>{engineeringCase.confidence_percent.toFixed(1)}%</strong><span>{engineeringCase.confidence_band.toUpperCase()}</span></div>
                    <div><small>RISK</small><strong>{engineeringCase.risk_rating.toUpperCase()}</strong><span>{engineeringCase.missing_data.length} missing data item(s)</span></div>
                  </div>

                  <TrustCenter engineeringCase={engineeringCase} />

                  <h3>ENGINEERING RECOMMENDATIONS</h3>
                  <div className="engineering-recommendations">
                    {engineeringCase.recommendations.map((recommendation) => <article className={`engineering-recommendation risk-${recommendation.risk}`} key={recommendation.recommendation_id}>
                      <header><strong>{recommendation.priority} · {recommendation.title}</strong><span>{recommendation.discipline} · {pretty(recommendation.recommendation_authority)} · confidence {recommendation.confidence_percent.toFixed(0)}%</span></header>
                      <p>{recommendation.reasons.join(" · ")}</p>
                      <div className="key-values">{recommendation.actions.map((action) => <><span key={`${recommendation.recommendation_id}-${action.parameter}-label`}>{action.parameter}</span><strong key={`${recommendation.recommendation_id}-${action.parameter}-value`}>{String(action.current_value ?? "N/A")} → {String(action.recommended_value ?? "N/A")} {action.unit ?? ""}</strong></>)}</div>
                      <p><b>Validation:</b> {recommendation.required_validation.join(" · ") || "Plant review"}</p>
                      <p><b>Failure modes:</b> {recommendation.potential_failure_modes.join(" · ") || "Discipline review required"}</p>
                      <p><b>Rollback:</b> {recommendation.rollback_criteria.join(" · ") || "Return to approved baseline"}</p>
                      <p><b>Approvals:</b> {recommendation.approval_requirements.join(" · ") || "Plant approval required"}</p>
                    </article>)}
                  </div>
                </>
              )}
            </>
          )}

          <WorkflowFooter previous={{ label: "PLANT", section: "plant" }} next={{ label: "NEXT STEP · SCENARIOS", section: "scenarios", disabled: !study }} onNavigate={onNavigate} />
        </>
      )}

      {section === "export" && (
        <>
          {!engineeringCase && (
            <div className="empty-workflow-state">
              <strong>No auditable engineering case is available.</strong>
              <span>Return to Retrofit, select a candidate and generate the engineering recommendation before exporting.</span>
              <button className="run" type="button" onClick={() => onNavigate("retrofit")}>RETURN TO RETROFIT</button>
            </div>
          )}

          {engineeringCase && (
            <>
              <div className={`engineering-decision-banner risk-${engineeringCase.risk_rating}`}>
                <div><small>PROJECT</small><strong>{engineeringCase.project.project_name}</strong><span>{engineeringCase.project.plant_name} · revision {engineeringCase.project.revision}</span></div>
                <div><small>CONFIDENCE</small><strong>{engineeringCase.confidence_percent.toFixed(1)}%</strong><span>{engineeringCase.confidence_band.toUpperCase()}</span></div>
                <div><small>DECISION RISK</small><strong>{engineeringCase.risk_rating.toUpperCase()}</strong><span>{engineeringCase.status.toUpperCase()}</span></div>
              </div>

              <div className="export-action-grid">
                <a className="run button-link export-primary" href={`${API}/api/engineering/cases/${engineeringCase.case_id}/package.zip`} target="_blank" rel="noreferrer">EXPORT DIGITAL ENGINEERING PACKAGE</a>
                <a className="button-link" href={`${API}/api/engineering/cases/${engineeringCase.case_id}/export.xlsx`} target="_blank" rel="noreferrer">EXPORT WORKBOOK ONLY</a>
              </div>

              <TrustCenter engineeringCase={engineeringCase} compact />

              <section className="summary-grid">
                <div><small>WORKBOOK CASE</small><strong>{engineeringCase.case_id}</strong></div>
                <div><small>PREDICTIONS</small><strong>{engineeringCase.predictions.length}</strong></div>
                <div><small>RECOMMENDATIONS</small><strong>{engineeringCase.recommendations.length}</strong></div>
                <div><small>MISSING DATA</small><strong>{engineeringCase.missing_data.length}</strong></div>
                <div><small>PILOT QUANTITY</small><strong>{engineeringCase.pilot_plan.pilot_quantity_t.toFixed(0)} t</strong></div>
                <div><small>MONITORING</small><strong>{monitoringHours} h</strong></div>
              </section>

              <details open><summary>PREDICTION / CONFIDENCE / REASON / REQUIRED VALIDATION</summary>
                <div className="engineering-prediction-grid">
                  {engineeringCase.predictions.map((prediction) => <article className={`engineering-prediction risk-${prediction.risk}`} key={prediction.code}><small>{prediction.category} · {prediction.confidence_percent.toFixed(0)}% earned confidence</small><strong>{prediction.label}</strong><b>{predictionValue(prediction)}</b><p><b>Interval:</b> {prediction.prediction_interval?.low === null || prediction.prediction_interval?.high === null ? "Qualitative / not applicable" : `${prediction.prediction_interval?.low} to ${prediction.prediction_interval?.high} ${prediction.unit ?? ""}`}</p><p>{prediction.reason}</p><p><b>Method:</b> {prediction.method}</p><p><b>Critical assumptions:</b> {prediction.critical_assumptions.join(" · ") || "None registered"}</p><p><b>Sensitive variables:</b> {prediction.sensitive_variables.join(" · ") || "Not resolved"}</p><p><b>Unknowns:</b> {prediction.unknown_inputs.join(" · ") || "No declared unknown"}</p><p><b>Validate:</b> {prediction.required_validation.join(" · ") || "Plant review"}</p></article>)}
                </div>
              </details>

              <details open><summary>PILOT PRODUCTION PLAN</summary>
                <section className="summary-grid">
                  <div><small>PILOT QUANTITY</small><strong>{engineeringCase.pilot_plan.pilot_quantity_t.toFixed(0)} t</strong></div>
                  <div><small>PILOT RATE</small><strong>{formatValue(engineeringCase.pilot_plan.pilot_rate_tph, " t/h")}</strong></div>
                  <div><small>SAMPLING ITEMS</small><strong>{engineeringCase.pilot_plan.sampling_plan.length}</strong></div>
                  <div><small>LAB TESTS</small><strong>{engineeringCase.pilot_plan.required_lab_tests.length}</strong></div>
                  <div><small>GO / NO-GO</small><strong>{engineeringCase.pilot_plan.go_no_go_criteria.length}</strong></div>
                  <div><small>MONITORING</small><strong>{monitoringHours} h</strong></div>
                </section>
                <div className="engineering-list-grid">
                  <section><h4>SAMPLING PLAN</h4><ol>{engineeringCase.pilot_plan.sampling_plan.map((item) => <li key={item}>{item}</li>)}</ol></section>
                  <section><h4>REQUIRED LAB TESTS</h4><ol>{engineeringCase.pilot_plan.required_lab_tests.map((item) => <li key={item}>{item}</li>)}</ol></section>
                  <section><h4>GO / NO-GO CRITERIA</h4><ol>{engineeringCase.pilot_plan.go_no_go_criteria.map((item) => <li key={item}>{item}</li>)}</ol></section>
                  <section><h4>MONITORING PLAN</h4><ol>{engineeringCase.pilot_plan.monitoring_plan.map((item) => <li key={item}>{item}</li>)}</ol></section>
                </div>
              </details>

              <details><summary>DATA THE PLANT MUST REPLACE OR VERIFY</summary>
                <div className="table-responsive"><table><thead><tr><th>Category</th><th>Data item</th><th>Why required</th></tr></thead><tbody>{engineeringCase.missing_data.map((item) => <tr key={`${item.category}-${item.item}`}><td>{pretty(item.category)}</td><td>{item.item}</td><td>{item.reason}</td></tr>)}</tbody></table></div>
              </details>

              <details><summary>IMPORT PILOT ACTUALS / LEARNING</summary>
                <p className="note">Import pilot or plant actuals. Records enter the audit trail immediately, but the model recalibrates only when PROCEED is approved, all three sign-offs are present, evidence references are attached and calibration use is explicitly authorised.</p>
                <div className="form-grid two">
                  <label>ACTUAL OUTPUT T/H<input type="number" step="0.1" value={actuals.actual_output_tph} onChange={(event) => updateActual("actual_output_tph", event.target.value)} /></label>
                  <label>ACTUAL ELECTRICITY KWH/T<input type="number" step="0.1" value={actuals.actual_electricity_kwh_t} onChange={(event) => updateActual("actual_electricity_kwh_t", event.target.value)} /></label>
                  <label>ACTUAL THERMAL KCAL/KG<input type="number" step="1" value={actuals.actual_thermal_kcal_kg} onChange={(event) => updateActual("actual_thermal_kcal_kg", event.target.value)} /></label>
                  <label>ACTUAL VARIABLE COST INR/T<input type="number" step="1" value={actuals.actual_variable_cost_inr_t} onChange={(event) => updateActual("actual_variable_cost_inr_t", event.target.value)} /></label>
                  <label>ACTUAL MATERIAL CO₂ KG/T<input type="number" step="1" value={actuals.actual_material_co2_kg_t} onChange={(event) => updateActual("actual_material_co2_kg_t", event.target.value)} /></label>
                  <label>ACTUAL FREE LIME %<input type="number" step="0.01" value={actuals.actual_free_lime_percent} onChange={(event) => updateActual("actual_free_lime_percent", event.target.value)} /></label>
                  <label>ACTUAL 3-DAY STRENGTH MPA<input type="number" step="0.1" value={actuals.actual_strength_3d_mpa} onChange={(event) => updateActual("actual_strength_3d_mpa", event.target.value)} /></label>
                  <label>ACTUAL 28-DAY STRENGTH MPA<input type="number" step="0.1" value={actuals.actual_strength_28d_mpa} onChange={(event) => updateActual("actual_strength_28d_mpa", event.target.value)} /></label>
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
                  <label>EVIDENCE REFERENCES<textarea rows={3} value={actuals.evidence_references} onChange={(event) => updateActual("evidence_references", event.target.value)} placeholder="One lab report, run log, signed form or source reference per line" /></label>
                  <label className="check-line"><input type="checkbox" checked={actuals.use_for_calibration} onChange={(event) => updateActual("use_for_calibration", event.target.checked)} /> AUTHORISE THIS SIGNED RECORD FOR CONTROLLED MODEL CALIBRATION</label>
                </div>
                <button className="run" disabled={learningLoading} onClick={() => void importActuals()}>{learningLoading ? "CALCULATING PREDICTION ERROR…" : "IMPORT ACTUALS AND RECALIBRATE"}</button>

                {learning && <><section className="summary-grid"><div><small>MAPE</small><strong>{learning.mean_absolute_percent_error === null ? "N/A" : `${learning.mean_absolute_percent_error.toFixed(2)}%`}</strong></div><div><small>CALIBRATION ACCEPTED</small><strong>{learning.accepted_for_calibration ? "YES" : "NO"}</strong></div><div><small>CONFIDENCE BEFORE</small><strong>{learning.confidence_before_percent.toFixed(1)}%</strong></div><div><small>CONFIDENCE AFTER</small><strong>{learning.confidence_after_percent.toFixed(1)}%</strong></div><div><small>ACCEPTED SAMPLES</small><strong>{learning.calibration_sample_count}</strong></div></section>{learning.calibration_rejection_reason && <div className="err">{learning.calibration_rejection_reason}</div>}<div className="engineering-executive">{learning.learning_summary}</div><a className="run button-link" href={`${API}/api/engineering/cases/${engineeringCase.case_id}/package.zip`} target="_blank" rel="noreferrer">RE-EXPORT ENGINEERING PACKAGE WITH ACTUALS</a></>}
              </details>
            </>
          )}

          <div className="module-tool-row">
            <button type="button" onClick={() => onOpenTool("run-library")}>OPEN RUN HISTORY</button>
            <button type="button" onClick={() => onOpenTool("library")}>OPEN VERSIONED LIBRARY</button>
          </div>
          <WorkflowFooter previous={{ label: "VALIDATION", section: "validation" }} onNavigate={onNavigate} />
        </>
      )}
    </section>
  );
}

