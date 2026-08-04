import { useEffect, useMemo, useState } from "react";

import { req } from "./api";
import type { Blend, Calibration, ClinkerFamily, Material, RawMixResult, Result } from "./types";

type Constraint = {
  material_id: string;
  minimum_percent: number;
  maximum_percent: number;
};

type BlendComponentPayload = {
  component_type: "material";
  material_id: string;
  blend_id: null;
  percentage: number;
};


type FamilyPreset = {
  label: string;
  lsf: number;
  sm: number;
  am: number;
  c3s: number | null;
  c2s: number | null;
  c3a: number | null;
  c4af: number | null;
};

const FAMILY_PRESETS: Record<ClinkerFamily, FamilyPreset> = {
  moduli_only: { label: "Moduli only / legacy mode", lsf: 95, sm: 2.5, am: 1.5, c3s: null, c2s: null, c3a: null, c4af: null },
  general_purpose: { label: "General-purpose clinker", lsf: 96, sm: 2.4, am: 1.5, c3s: 60, c2s: 20, c3a: 8, c4af: 10 },
  high_early_strength: { label: "High early strength", lsf: 98, sm: 2.3, am: 1.4, c3s: 66, c2s: 14, c3a: 8, c4af: 10 },
  durable_belite: { label: "Durable / belite-rich", lsf: 94.5, sm: 2.45, am: 1.35, c3s: 52, c2s: 29, c3a: 7, c4af: 11 },
  sulfate_resistant: { label: "Sulfate resistant", lsf: 95, sm: 2.5, am: 0.95, c3s: 55, c2s: 25, c3a: 4, c4af: 14 },
  low_carbon_belite: { label: "Lower-carbon belite-rich", lsf: 92.5, sm: 2.45, am: 1.3, c3s: 44, c2s: 37, c3a: 7, c4af: 10 },
  lc3_compatible: { label: "LC3-compatible screening", lsf: 95, sm: 2.35, am: 1.25, c3s: 55, c2s: 25, c3a: 7, c4af: 12 },
  custom: { label: "Custom phase target", lsf: 95, sm: 2.5, am: 1.5, c3s: 60, c2s: 20, c3a: 8, c4af: 10 },
};

function nullable(value: string): number | null {
  return value.trim() === "" ? null : Number(value);
}

function roundSix(value: number): number {
  return Number(value.toFixed(6));
}

/**
 * Convert optimiser suggestions into a blend-safe component list.
 *
 * The optimiser is allowed to return rounded zero-share candidates for
 * screening. Blend persistence is stricter: components must be unique,
 * positive, and total exactly 100%. This function deliberately bridges those
 * two contracts instead of sending the raw solver array to POST /api/blends.
 */
function blendComponentsFrom(result: RawMixResult): BlendComponentPayload[] {
  const aggregated = new Map<string, number>();
  for (const suggestion of result.suggestions) {
    if (!Number.isFinite(suggestion.percentage) || suggestion.percentage <= 0) continue;
    aggregated.set(
      suggestion.material_id,
      (aggregated.get(suggestion.material_id) ?? 0) + suggestion.percentage,
    );
  }

  const positive = [...aggregated.entries()].filter(([, percentage]) => percentage > 0.000001);
  const total = positive.reduce((sum, [, percentage]) => sum + percentage, 0);
  if (!positive.length || total <= 0) return [];

  const normalized = positive.map(([materialId, percentage]) => ({
    component_type: "material" as const,
    material_id: materialId,
    blend_id: null,
    percentage: roundSix((percentage / total) * 100),
  }));

  const largestIndex = normalized.reduce(
    (largest, item, index, items) =>
      item.percentage > items[largest].percentage ? index : largest,
    0,
  );
  const roundedTotal = normalized.reduce((sum, item) => sum + item.percentage, 0);
  normalized[largestIndex] = {
    ...normalized[largestIndex],
    percentage: roundSix(normalized[largestIndex].percentage + (100 - roundedTotal)),
  };
  return normalized.filter((item) => item.percentage > 0);
}

export function AccuracyWorkspace({
  materials,
  runs,
  blendCreated,
}: {
  materials: Material[];
  runs: Result[];
  blendCreated: (blend: Blend) => void;
}) {
  const [mode, setMode] = useState<"rawmix" | "calibration">("rawmix");
  const [constraints, setConstraints] = useState<Constraint[]>([]);
  const [lsf, setLsf] = useState(95);
  const [sm, setSm] = useState(2.5);
  const [am, setAm] = useState(1.5);
  const [family, setFamily] = useState<ClinkerFamily>("general_purpose");
  const [targetC3s, setTargetC3s] = useState<number | null>(60);
  const [targetC2s, setTargetC2s] = useState<number | null>(20);
  const [targetC3a, setTargetC3a] = useState<number | null>(8);
  const [targetC4af, setTargetC4af] = useState<number | null>(10);
  const [scenario, setScenario] = useState("typical");
  const [result, setResult] = useState<RawMixResult | null>(null);
  const [error, setError] = useState("");
  const [savingBlend, setSavingBlend] = useState(false);
  const [blendName, setBlendName] = useState("");
  const [blendFamily, setBlendFamily] = useState("Optimised raw meal");
  const [blendObjective, setBlendObjective] = useState("");
  const [blendStandard, setBlendStandard] = useState(
    "Process-control target — plant validation required",
  );
  const [calibrations, setCalibrations] = useState<Calibration[]>([]);
  const [runId, setRunId] = useState("");
  const [actualOutput, setActualOutput] = useState("");
  const [actualElectricity, setActualElectricity] = useState("");
  const [actualThermal, setActualThermal] = useState("");
  const [actualCost, setActualCost] = useState("");
  const [actualCo2, setActualCo2] = useState("");
  const [source, setSource] = useState("Plant shift report / laboratory campaign");

  const rawMaterials = useMemo(
    () =>
      materials.filter((item) =>
        ["raw_kiln_feed", "corrective", "recycled_process_material"].includes(
          item.functional_role,
        ),
      ),
    [materials],
  );

  const selectedMaterialIds = constraints.map((item) => item.material_id);
  const hasDuplicateMaterials = new Set(selectedMaterialIds).size !== selectedMaterialIds.length;
  const minimumTotal = constraints.reduce((sum, item) => sum + item.minimum_percent, 0);
  const maximumTotal = constraints.reduce((sum, item) => sum + item.maximum_percent, 0);
  const invalidBounds = constraints.some(
    (item) =>
      !Number.isFinite(item.minimum_percent) ||
      !Number.isFinite(item.maximum_percent) ||
      item.minimum_percent < 0 ||
      item.maximum_percent > 100 ||
      item.minimum_percent > item.maximum_percent,
  );
  const canReachHundred = minimumTotal <= 100.000001 && maximumTotal >= 99.999999;
  const constraintsValid =
    constraints.length >= 2 && !hasDuplicateMaterials && !invalidBounds && canReachHundred;
  const nextUnusedMaterial = rawMaterials.find(
    (material) => !selectedMaterialIds.includes(material.material_id),
  );
  const saveComponents = result ? blendComponentsFrom(result) : [];
  const saveDetailsValid =
    blendName.trim().length > 0 &&
    blendFamily.trim().length > 0 &&
    blendObjective.trim().length > 0 &&
    saveComponents.length > 0;

  useEffect(() => {
    if (!constraints.length && rawMaterials.length >= 2) {
      setConstraints(
        rawMaterials.slice(0, 3).map((item, index) => ({
          material_id: item.material_id,
          minimum_percent: index === 0 ? 60 : 0,
          maximum_percent: index === 0 ? 100 : 40,
        })),
      );
    }
  }, [rawMaterials, constraints.length]);

  useEffect(() => {
    setRunId((current) => current || runs[0]?.run_id || "");
    void req<Calibration[]>("/api/calibrations")
      .then(setCalibrations)
      .catch(() => undefined);
  }, [runs]);

  function applyFamily(nextFamily: ClinkerFamily) {
    const preset = FAMILY_PRESETS[nextFamily];
    setFamily(nextFamily);
    setLsf(preset.lsf);
    setSm(preset.sm);
    setAm(preset.am);
    setTargetC3s(preset.c3s);
    setTargetC2s(preset.c2s);
    setTargetC3a(preset.c3a);
    setTargetC4af(preset.c4af);
  }

  async function optimise() {
    setError("");
    setResult(null);
    try {
      const nextResult = await req<RawMixResult>("/api/raw-mix/optimise", {
        method: "POST",
        body: JSON.stringify({
          materials: constraints,
          target_lsf: lsf,
          target_sm: sm,
          target_am: am,
          clinker_family: family,
          target_c3s_percent: targetC3s,
          target_c2s_percent: targetC2s,
          target_c3a_percent: targetC3a,
          target_c4af_percent: targetC4af,
          chemistry_scenario: scenario,
        }),
      });
      setResult(nextResult);
      setBlendName(`${FAMILY_PRESETS[family].label} raw meal / ${scenario}`);
      setBlendFamily(FAMILY_PRESETS[family].label);
      setBlendObjective(
        `Target LSF ${lsf}, SM ${sm}, AM ${am}`
        + (targetC3s === null ? "" : `; potential phases C3S ${targetC3s}, C2S ${targetC2s}, C3A ${targetC3a}, C4AF ${targetC4af}`),
      );
    } catch (caught) {
      setError(String(caught));
    }
  }

  async function saveRawMix() {
    if (!result || !saveDetailsValid) return;
    setSavingBlend(true);
    setError("");
    try {
      const blend = await req<Blend>("/api/blends", {
        method: "POST",
        body: JSON.stringify({
          name: blendName.trim(),
          blend_class: "raw_meal",
          family: blendFamily.trim(),
          objective: blendObjective.trim(),
          applicable_standard: blendStandard.trim() || null,
          components: saveComponents,
          evidence: [],
        }),
      });
      blendCreated(blend);
    } catch (caught) {
      setError(String(caught));
    } finally {
      setSavingBlend(false);
    }
  }

  async function calibrate() {
    setError("");
    try {
      const saved = await req<Calibration>("/api/calibrations", {
        method: "POST",
        body: JSON.stringify({
          run_id: runId,
          actual_output_tph: nullable(actualOutput),
          actual_electricity_kwh_t: nullable(actualElectricity),
          actual_thermal_kcal_kg: nullable(actualThermal),
          actual_direct_cost_inr_t: nullable(actualCost),
          actual_co2_kg_t: nullable(actualCo2),
          source_title: source,
        }),
      });
      setCalibrations((current) => [saved, ...current]);
    } catch (caught) {
      setError(String(caught));
    }
  }

  return (
    <section className="guide wide-guide">
      <div className="subnav">
        <button
          className={mode === "rawmix" ? "selected" : ""}
          onClick={() => setMode("rawmix")}
        >
          RAW-MIX OPTIMISER
        </button>
        <button
          className={mode === "calibration" ? "selected" : ""}
          onClick={() => setMode("calibration")}
        >
          CALIBRATION
        </button>
      </div>

      {mode === "rawmix" ? (
        <div className="composer">
          <h2>GUIDE / CLINKER ENGINEERING OPTIMISER</h2>
          <p className="management-note">
            Choose actual quarry/corrective records and bounds. A deterministic pairwise mass-transfer solver
            minimises moduli error and, when selected, potential Bogue-phase error. The result is a screening
            design—not a substitute for kiln trials, free-lime testing, microscopy, or XRD/Rietveld analysis.
          </p>

          <div className="form-grid two">
            <label>
              CLINKER ENGINEERING OBJECTIVE
              <select value={family} onChange={(event) => applyFamily(event.target.value as ClinkerFamily)}>
                {Object.entries(FAMILY_PRESETS).map(([key, preset]) => (
                  <option value={key} key={key}>{preset.label}</option>
                ))}
              </select>
            </label>
            <label>
              SOLVER
              <input value="Deterministic bounded coordinate descent" disabled />
            </label>
          </div>

          <div className="form-grid four">
            <label>
              TARGET LSF
              <input type="number" value={lsf} onChange={(event) => setLsf(Number(event.target.value))} />
            </label>
            <label>
              TARGET SM
              <input type="number" step="0.01" value={sm} onChange={(event) => setSm(Number(event.target.value))} />
            </label>
            <label>
              TARGET AM
              <input type="number" step="0.01" value={am} onChange={(event) => setAm(Number(event.target.value))} />
            </label>
            <label>
              CHEMISTRY SCENARIO
              <select value={scenario} onChange={(event) => setScenario(event.target.value)}>
                <option value="low">Low profile</option>
                <option value="typical">Typical</option>
                <option value="high">High profile</option>
              </select>
            </label>
          </div>

          <div className="form-grid four">
            <label>
              TARGET C₃S / ALITE %
              <input type="number" step="0.1" disabled={family === "moduli_only"} value={targetC3s ?? ""} onChange={(event) => setTargetC3s(event.target.value === "" ? null : Number(event.target.value))} />
            </label>
            <label>
              TARGET C₂S / BELITE %
              <input type="number" step="0.1" disabled={family === "moduli_only"} value={targetC2s ?? ""} onChange={(event) => setTargetC2s(event.target.value === "" ? null : Number(event.target.value))} />
            </label>
            <label>
              TARGET C₃A %
              <input type="number" step="0.1" disabled={family === "moduli_only"} value={targetC3a ?? ""} onChange={(event) => setTargetC3a(event.target.value === "" ? null : Number(event.target.value))} />
            </label>
            <label>
              TARGET C₄AF / FERRITE %
              <input type="number" step="0.1" disabled={family === "moduli_only"} value={targetC4af ?? ""} onChange={(event) => setTargetC4af(event.target.value === "" ? null : Number(event.target.value))} />
            </label>
          </div>
          <p className="management-note">
            Family presets are editable screening envelopes. Bogue phases are calculated on a loss-free clinker basis and carry substantial model uncertainty.
          </p>

          <div className="section-heading">
            <span>CANDIDATE MATERIAL BOUNDS</span>
            <span>{constraints.length} MATERIALS</span>
          </div>

          {constraints.map((constraint, index) => {
            const selectableMaterials = rawMaterials.filter(
              (material) =>
                material.material_id === constraint.material_id ||
                !constraints.some(
                  (other, otherIndex) =>
                    otherIndex !== index && other.material_id === material.material_id,
                ),
            );
            return (
              <div className="component-row" key={`${constraint.material_id}-${index}`}>
                <span>MATERIAL</span>
                <select
                  value={constraint.material_id}
                  onChange={(event) =>
                    setConstraints((current) =>
                      current.map((item, row) =>
                        row === index ? { ...item, material_id: event.target.value } : item,
                      ),
                    )
                  }
                >
                  {selectableMaterials.map((item) => (
                    <option value={item.material_id} key={item.material_id}>
                      {item.name} · {item.functional_role}
                    </option>
                  ))}
                </select>
                <input
                  aria-label="Minimum percent"
                  type="number"
                  min="0"
                  max="100"
                  value={constraint.minimum_percent}
                  onChange={(event) =>
                    setConstraints((current) =>
                      current.map((item, row) =>
                        row === index
                          ? { ...item, minimum_percent: Number(event.target.value) }
                          : item,
                      ),
                    )
                  }
                />
                <input
                  aria-label="Maximum percent"
                  type="number"
                  min="0"
                  max="100"
                  value={constraint.maximum_percent}
                  onChange={(event) =>
                    setConstraints((current) =>
                      current.map((item, row) =>
                        row === index
                          ? { ...item, maximum_percent: Number(event.target.value) }
                          : item,
                      ),
                    )
                  }
                />
                <button
                  onClick={() =>
                    setConstraints((current) => current.filter((_, row) => row !== index))
                  }
                >
                  REMOVE
                </button>
              </div>
            );
          })}

          {hasDuplicateMaterials && (
            <div className="err">Each candidate material may appear only once.</div>
          )}
          {invalidBounds && (
            <div className="err">Each minimum must be between 0 and its maximum; each maximum must be at most 100.</div>
          )}
          {!invalidBounds && !canReachHundred && (
            <div className="err">
              Bounds cannot produce a 100% raw meal. Current minimum total: {minimumTotal.toFixed(2)}%; maximum total: {maximumTotal.toFixed(2)}%.
            </div>
          )}

          <div className="inline-actions">
            <button
              disabled={!nextUnusedMaterial}
              onClick={() => {
                if (!nextUnusedMaterial) return;
                setConstraints((current) => [
                  ...current,
                  {
                    material_id: nextUnusedMaterial.material_id,
                    minimum_percent: 0,
                    maximum_percent: 30,
                  },
                ]);
              }}
            >
              + ADD MATERIAL
            </button>
            <button className="run" disabled={!constraintsValid} onClick={() => void optimise()}>
              OPTIMISE RAW MIX
            </button>
          </div>

          {result && (
            <div className="route-advice">
              <strong>
                {result.feasible
                  ? "FEASIBLE SCREENING SOLUTION"
                  : "NEAREST SOLUTION — TARGET NOT FULLY REACHED"}
              </strong>
              <span>
                LSF {result.lsf?.toFixed(2) ?? "N/A"} · SM {result.silica_modulus?.toFixed(3) ?? "N/A"} · AM {result.alumina_modulus?.toFixed(3) ?? "N/A"} · yield {result.estimated_clinker_yield?.toFixed(3) ?? "N/A"}
              </span>
              {result.suggestions.map((item, index) => (
                <span key={`${item.material_id}-${index}`}>
                  {item.material_name}: {item.percentage.toFixed(3)}%
                </span>
              ))}
              {result.mineralogy && (
                <>
                  <div className="section-heading">
                    <span>PREDICTED CLINKER MINERALOGY / BOGUE POTENTIAL PHASES</span>
                    <span>{FAMILY_PRESETS[result.clinker_family].label}</span>
                  </div>
                  <div className="chemistry-grid">
                    <div><small>C₃S / ALITE</small><strong>{result.mineralogy.c3s_percent?.toFixed(2) ?? "N/A"}%</strong></div>
                    <div><small>C₂S / BELITE</small><strong>{result.mineralogy.c2s_percent?.toFixed(2) ?? "N/A"}%</strong></div>
                    <div><small>C₃A</small><strong>{result.mineralogy.c3a_percent?.toFixed(2) ?? "N/A"}%</strong></div>
                    <div><small>C₄AF / FERRITE</small><strong>{(result.mineralogy.c4af_percent ?? result.mineralogy.calcium_aluminoferrite_ss_percent)?.toFixed(2) ?? "N/A"}%</strong></div>
                  </div>
                  <span>
                    Potential phase total {result.mineralogy.phase_total_percent?.toFixed(2) ?? "N/A"}% · unallocated {result.mineralogy.unallocated_percent?.toFixed(2) ?? "N/A"}% · A/F {result.mineralogy.alumina_ferric_ratio?.toFixed(3) ?? "N/A"}
                  </span>
                </>
              )}
              {result.behaviour && (
                <div className="key-values">
                  <span>Burnability screening</span><strong>{result.behaviour.burnability_class.toUpperCase()} · {result.behaviour.burnability_score?.toFixed(1) ?? "N/A"}/100</strong>
                  <span>Liquid phase proxy / 1450 °C</span><strong>{result.behaviour.liquid_phase_1450_percent?.toFixed(2) ?? "N/A"}%</strong>
                  <span>Free-lime risk</span><strong>{result.behaviour.free_lime_risk.toUpperCase()}</strong>
                  <span>Expected fuel demand</span><strong>{result.behaviour.expected_fuel_demand.toUpperCase()}</strong>
                  <span>Expected early strength</span><strong>{result.behaviour.expected_early_strength.toUpperCase()}</strong>
                  <span>Expected later strength</span><strong>{result.behaviour.expected_later_strength.toUpperCase()}</strong>
                  <span>Expected sulfate resistance</span><strong>{result.behaviour.expected_sulfate_resistance.toUpperCase()}</strong>
                  <span>Nearest family</span><strong>{result.behaviour.predicted_family ? FAMILY_PRESETS[result.behaviour.predicted_family].label : "N/A"}</strong>
                </div>
              )}
              <details>
                <summary>CALCULATION TRACE / {result.calculation_trace.length} DETERMINISTIC STEPS</summary>
                <div className="audit-list">
                  {result.calculation_trace.map((step) => (
                    <p key={step.sequence}>
                      <code>{step.sequence}. {step.section}</code>
                      <strong>{step.operation}</strong>
                      <span>{step.formula}<br />Inputs: {JSON.stringify(step.inputs)}<br />Result: {String(step.result ?? "N/A")} {step.unit ?? ""}</span>
                    </p>
                  ))}
                </div>
              </details>
              {result.warnings.map((warning) => (
                <span className="warn-text" key={warning}>{warning}</span>
              ))}

              <div className="section-heading">
                <span>SAVE AS IMMUTABLE RAW-MEAL BLEND</span>
                <span>{saveComponents.length} POSITIVE COMPONENTS</span>
              </div>
              <div className="form-grid two">
                <label>
                  BLEND NAME
                  <input value={blendName} onChange={(event) => setBlendName(event.target.value)} />
                </label>
                <label>
                  FAMILY
                  <input value={blendFamily} onChange={(event) => setBlendFamily(event.target.value)} />
                </label>
                <label>
                  OBJECTIVE
                  <input value={blendObjective} onChange={(event) => setBlendObjective(event.target.value)} />
                </label>
                <label>
                  APPLICABLE STANDARD / CONTROL BASIS
                  <input value={blendStandard} onChange={(event) => setBlendStandard(event.target.value)} />
                </label>
              </div>
              <span>
                Zero-share candidates are not stored. Remaining components are merged and normalized to exactly 100.000000% before saving.
              </span>
              <button
                className="run"
                disabled={!saveDetailsValid || savingBlend}
                onClick={() => void saveRawMix()}
              >
                {savingBlend ? "SAVING…" : "SAVE RAW-MEAL BLEND"}
              </button>
            </div>
          )}
        </div>
      ) : (
        <div className="composer">
          <h2>GUIDE / PLANT CALIBRATION WORKSPACE</h2>
          <p className="management-note">
            Enter actual values from the same operating window as a saved run. Error is stored
            immutably; it tells you where the twin needs tuning instead of silently changing the model.
          </p>
          <div className="form-grid two">
            <label>
              SIMULATED RUN
              <select value={runId} onChange={(event) => setRunId(event.target.value)}>
                {runs.map((run) => (
                  <option value={run.run_id} key={run.run_id}>
                    {run.run_id} · {run.blend_snapshot?.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              SOURCE RECORD
              <input value={source} onChange={(event) => setSource(event.target.value)} />
            </label>
            <label>
              ACTUAL OUTPUT T/H
              <input type="number" value={actualOutput} onChange={(event) => setActualOutput(event.target.value)} />
            </label>
            <label>
              ACTUAL KWH/T
              <input type="number" value={actualElectricity} onChange={(event) => setActualElectricity(event.target.value)} />
            </label>
            <label>
              ACTUAL KCAL/KG
              <input type="number" value={actualThermal} onChange={(event) => setActualThermal(event.target.value)} />
            </label>
            <label>
              ACTUAL DIRECT ₹/T
              <input type="number" value={actualCost} onChange={(event) => setActualCost(event.target.value)} />
            </label>
            <label>
              ACTUAL CO₂ KG/T
              <input type="number" value={actualCo2} onChange={(event) => setActualCo2(event.target.value)} />
            </label>
          </div>
          <button className="run" disabled={!runId || !source.trim()} onClick={() => void calibrate()}>
            SAVE CALIBRATION RECORD
          </button>
          <div className="section-heading">
            <span>CALIBRATION HISTORY</span>
            <span>{calibrations.length} RECORDS</span>
          </div>
          {calibrations.map((record) => (
            <div className="calibration-row" key={record.calibration_id}>
              <code>{record.calibration_id} · {record.run_id}</code>
              {record.errors.map((item) => (
                <span key={item.metric}>
                  {item.metric}: {item.percent_error === null ? "N/A" : `${item.percent_error.toFixed(1)}% error`}
                </span>
              ))}
            </div>
          ))}
        </div>
      )}
      {error && <div className="err">{error}</div>}
    </section>
  );
}
