import { useEffect, useMemo, useState } from "react";

import { req } from "./api";
import type {
  Blend,
  BlendComponent,
  BlendPreview,
  Chemistry,
  Material,
} from "./types";

const blendClasses = [
  ["finished_cement", "Finished cement"],
  ["raw_meal", "Raw meal"],
  ["raw_material_stockpile", "Raw-material stockpile"],
  ["fuel_blend", "Fuel blend"],
  ["clinker_blend", "Clinker blend"],
  ["premix", "Reusable premix"],
] as const;

const materialTypes = [
  "limestone",
  "clinker",
  "fly_ash",
  "gypsum",
  "calcined_clay",
  "ggbs",
  "slag",
  "silica_fume",
  "natural_pozzolan",
  "rice_husk_ash",
  "metakaolin",
  "cement_kiln_dust",
  "grinding_aid",
  "clay",
  "shale",
  "silica_corrective",
  "iron_corrective",
  "bauxite",
  "laterite",
  "sand",
  "coal",
  "petcoke",
  "biomass",
  "rdf",
  "alternative_fuel",
  "custom",
];

const functionalRoles = [
  "raw_kiln_feed",
  "corrective",
  "clinker",
  "cement_addition",
  "set_regulator",
  "process_additive",
  "fuel",
  "alternative_fuel",
  "fuel_ash",
  "recycled_process_material",
];

type DraftPart = {
  rowId: string;
  component_type: "material" | "blend";
  reference_id: string;
  percentage: number;
};

function rowId(): string {
  return `${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

function pretty(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (match) => match.toUpperCase());
}

function defaultMaterialClasses(materialType: string, functionalRole: string): string[] {
  if (["fuel", "alternative_fuel", "fuel_ash"].includes(functionalRole)) {
    return ["fuel_blend", "premix"];
  }
  if (["raw_kiln_feed", "corrective", "recycled_process_material"].includes(functionalRole)) {
    return ["raw_material_stockpile", "raw_meal", "premix"];
  }
  if (functionalRole === "clinker") {
    return ["clinker_blend", "finished_cement", "premix"];
  }
  if (["cement_addition", "set_regulator", "process_additive"].includes(functionalRole)) {
    return ["finished_cement", "premix"];
  }
  if (["coal", "petcoke", "biomass", "rdf", "alternative_fuel"].includes(materialType)) {
    return ["fuel_blend", "premix"];
  }
  if (materialType === "clinker") {
    return ["clinker_blend", "finished_cement", "premix"];
  }
  if (["limestone", "clay", "shale", "silica_corrective", "iron_corrective", "bauxite", "laterite", "sand"].includes(materialType)) {
    return ["raw_material_stockpile", "raw_meal", "premix"];
  }
  return ["finished_cement", "premix"];
}

function defaultFunctionalRole(materialType: string): string {
  if (materialType === "clinker") return "clinker";
  if (materialType === "gypsum") return "set_regulator";
  if (["coal", "petcoke"].includes(materialType)) return "fuel";
  if (["biomass", "rdf", "alternative_fuel"].includes(materialType)) return "alternative_fuel";
  if (["silica_corrective", "iron_corrective", "bauxite", "laterite", "sand"].includes(materialType)) return "corrective";
  if (["limestone", "clay", "shale"].includes(materialType)) return "raw_kiln_feed";
  if (materialType === "grinding_aid") return "process_additive";
  return "cement_addition";
}

function formatChemistry(value: number | null): string {
  return value === null ? "N/A" : `${value.toFixed(3)}%`;
}

export function BlendWorkspace({
  materials,
  blends,
  onBlendCreated,
  onMaterialCreated,
  initialMode = "blend",
}: {
  materials: Material[];
  blends: Blend[];
  onBlendCreated: (blend: Blend) => void;
  onMaterialCreated: (material: Material) => void;
  initialMode?: "blend" | "material";
}) {
  const [mode, setMode] = useState<"blend" | "material">(initialMode);

  useEffect(() => {
    setMode(initialMode);
  }, [initialMode]);
  return (
    <section className="guide wide-guide">
      <div className="subnav" role="tablist" aria-label="Blend workspace">
        <button className={mode === "blend" ? "selected" : ""} onClick={() => setMode("blend")}>
          BLEND COMPOSER
        </button>
        <button className={mode === "material" ? "selected" : ""} onClick={() => setMode("material")}>
          NEW MATERIAL
        </button>
      </div>
      {mode === "blend" ? (
        <BlendComposer materials={materials} blends={blends} done={onBlendCreated} />
      ) : (
        <MaterialEditor
          done={(material) => {
            onMaterialCreated(material);
            setMode("blend");
          }}
        />
      )}
    </section>
  );
}

function BlendComposer({
  materials,
  blends,
  done,
}: {
  materials: Material[];
  blends: Blend[];
  done: (blend: Blend) => void;
}) {
  const [name, setName] = useState("New Versioned Cement Candidate");
  const [blendClass, setBlendClass] = useState("finished_cement");
  const [family, setFamily] = useState("Custom");
  const [objective, setObjective] = useState("controlled_improvement");
  const [standard, setStandard] = useState("Review required");
  const [parts, setParts] = useState<DraftPart[]>([
    { rowId: rowId(), component_type: "material", reference_id: "", percentage: 64 },
    { rowId: rowId(), component_type: "material", reference_id: "", percentage: 31 },
    { rowId: rowId(), component_type: "material", reference_id: "", percentage: 5 },
  ]);
  const [preview, setPreview] = useState<BlendPreview | null>(null);
  const [previewError, setPreviewError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!materials.length || parts.some((part) => part.reference_id)) return;
    const find = (type: string) => materials.find((material) => material.material_type === type)?.material_id ?? materials[0].material_id;
    setParts((current) => [
      { ...current[0], reference_id: find("clinker") },
      { ...current[1], reference_id: find("fly_ash") },
      { ...current[2], reference_id: find("gypsum") },
    ]);
  }, [materials, parts]);

  const total = parts.reduce((sum, part) => sum + Number(part.percentage || 0), 0);
  const references = parts.map((part) => `${part.component_type}:${part.reference_id}`);
  const duplicates = references.filter((reference, index) => references.indexOf(reference) !== index && !reference.endsWith(":"));
  const structurallyValid =
    Boolean(name.trim()) &&
    parts.length > 0 &&
    parts.every((part) => Boolean(part.reference_id) && part.percentage > 0) &&
    duplicates.length === 0 &&
    Math.abs(total - 100) <= 0.01;

  const components: BlendComponent[] = useMemo(
    () =>
      parts.map((part) => ({
        component_type: part.component_type,
        material_id: part.component_type === "material" ? part.reference_id : null,
        blend_id: part.component_type === "blend" ? part.reference_id : null,
        percentage: part.percentage,
      })),
    [parts],
  );

  const payload = useMemo(
    () => ({
      name,
      blend_class: blendClass,
      family,
      objective,
      applicable_standard: standard || null,
      components,
      evidence: [],
    }),
    [name, blendClass, family, objective, standard, components],
  );

  useEffect(() => {
    setPreview(null);
    setPreviewError("");
    if (!structurallyValid) return;
    let cancelled = false;
    const timer = window.setTimeout(() => {
      req<BlendPreview>("/api/blends/preview", {
        method: "POST",
        body: JSON.stringify(payload),
      })
        .then((value) => {
          if (!cancelled) setPreview(value);
        })
        .catch((error: unknown) => {
          if (!cancelled) setPreviewError(String(error));
        });
    }, 180);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [payload, structurallyValid]);

  function updatePart(index: number, patch: Partial<DraftPart>) {
    setParts((current) => current.map((part, partIndex) => (partIndex === index ? { ...part, ...patch } : part)));
  }

  function addPart(componentType: "material" | "blend") {
    const reference = componentType === "material" ? materials[0]?.material_id ?? "" : blends[0]?.blend_id ?? "";
    setParts((current) => [
      ...current,
      { rowId: rowId(), component_type: componentType, reference_id: reference, percentage: 1 },
    ]);
  }

  function removePart(index: number) {
    setParts((current) => current.filter((_, partIndex) => partIndex !== index));
  }

  function normalise() {
    if (total <= 0) return;
    setParts((current) =>
      current.map((part, index) => ({
        ...part,
        percentage:
          index === current.length - 1
            ? Number((100 - current.slice(0, -1).reduce((sum, item) => sum + (item.percentage / total) * 100, 0)).toFixed(6))
            : Number(((part.percentage / total) * 100).toFixed(6)),
      })),
    );
  }

  async function save() {
    setSaving(true);
    setPreviewError("");
    try {
      const saved = await req<Blend>("/api/blends", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      done(saved);
    } catch (error) {
      setPreviewError(String(error));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="composer">
      <h2>GUIDE / DYNAMIC BLEND COMPOSER</h2>
      <div className="form-grid two">
        <label>
          NAME
          <input value={name} onChange={(event) => setName(event.target.value)} />
        </label>
        <label>
          BLEND CLASS
          <select value={blendClass} onChange={(event) => setBlendClass(event.target.value)}>
            {blendClasses.map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>
        <label>
          FAMILY
          <input value={family} onChange={(event) => setFamily(event.target.value)} placeholder="PPC, LC3, OPC, premix…" />
        </label>
        <label>
          RESEARCH OBJECTIVE
          <input value={objective} onChange={(event) => setObjective(event.target.value)} />
        </label>
      </div>
      <label>
        STANDARD / REVIEW NOTE
        <input value={standard} onChange={(event) => setStandard(event.target.value)} />
      </label>

      <div className="section-heading">
        <span>DIRECT COMPONENTS</span>
        <span>{parts.length} rows · {total.toFixed(3)}%</span>
      </div>
      <div className="component-head">
        <span>KIND</span><span>COMPONENT OR VERSIONED BLEND</span><span>MASS %</span><span />
      </div>
      {parts.map((part, index) => (
        <div className="component-row" key={part.rowId}>
          <select
            value={part.component_type}
            onChange={(event) => {
              const componentType = event.target.value as "material" | "blend";
              updatePart(index, {
                component_type: componentType,
                reference_id: componentType === "material" ? materials[0]?.material_id ?? "" : blends[0]?.blend_id ?? "",
              });
            }}
          >
            <option value="material">Material</option>
            <option value="blend">Existing blend</option>
          </select>
          <select value={part.reference_id} onChange={(event) => updatePart(index, { reference_id: event.target.value })}>
            {part.component_type === "material"
              ? materials.map((material) => (
                  <option key={material.material_id} value={material.material_id}>
                    {material.name} · {pretty(material.material_type)} · {material.evidence[0]?.evidence_class ?? "unverified"}
                  </option>
                ))
              : blends.map((blend) => (
                  <option key={blend.blend_id} value={blend.blend_id}>
                    {blend.name} · {pretty(blend.blend_class)} · v{1}
                  </option>
                ))}
          </select>
          <input
            aria-label={`Component ${index + 1} percentage`}
            type="number"
            min="0.001"
            max="100"
            step="0.001"
            value={part.percentage}
            onChange={(event) => updatePart(index, { percentage: Number(event.target.value) })}
          />
          <button className="icon-button" onClick={() => removePart(index)} disabled={parts.length === 1} aria-label={`Remove component ${index + 1}`}>
            REMOVE
          </button>
        </div>
      ))}
      <div className="inline-actions">
        <button onClick={() => addPart("material")}>+ ADD MATERIAL</button>
        <button onClick={() => addPart("blend")} disabled={!blends.length}>+ ADD EXISTING BLEND</button>
        <button onClick={normalise} disabled={total <= 0}>NORMALISE TO 100%</button>
      </div>

      <pre className="validation-log">
        {Math.abs(total - 100) <= 0.01 ? "PASS" : "FAIL"}  Direct component total = {total.toFixed(3)}%{"\n"}
        {duplicates.length ? "FAIL  Duplicate direct component; merge it into one row" : "PASS  No duplicate direct references"}{"\n"}
        {parts.some((part) => part.component_type === "blend") ? "INFO  Nested blend will be recursively flattened" : "INFO  Direct-material recipe"}{"\n"}
        WARN  Physical validation not attached
      </pre>
      {previewError && <div className="err">{previewError}</div>}

      {preview && (
        <div className="preview-grid">
          <div>
            <div className="section-heading"><span>FLATTENED BASE-MATERIAL COMPOSITION</span><span>{preview.flattened_total_percentage.toFixed(3)}%</span></div>
            <div className="data-table">
              {preview.flattened_components.map((component) => (
                <div className="data-row" key={component.material_id}>
                  <span>{component.material_name}</span>
                  <span>{pretty(component.material_type)}</span>
                  <span>{component.evidence_class}</span>
                  <strong>{component.percentage.toFixed(3)}%</strong>
                </div>
              ))}
            </div>
          </div>
          <div>
            <div className="section-heading"><span>SCREENING CALCULATION</span><span>NOT PHYSICAL VALIDATION</span></div>
            <div className="chemistry-grid">
              {Object.entries(preview.chemistry).map(([oxide, value]) => (
                <div key={oxide}><small>{oxide.toUpperCase()}</small><strong>{formatChemistry(value)}</strong></div>
              ))}
              <div><small>MATERIAL COST</small><strong>{preview.material_cost_inr_t === null ? "N/A" : `₹${preview.material_cost_inr_t.toFixed(0)}/t`}</strong></div>
              <div><small>MATERIAL CO₂</small><strong>{preview.estimated_co2_kg_t === null ? "N/A" : `${preview.estimated_co2_kg_t.toFixed(0)} kg/t`}</strong></div>
            </div>
            {preview.warnings.length > 0 && (
              <pre className="validation-log">{preview.warnings.map((warning) => `WARN  ${warning}`).join("\n")}</pre>
            )}
          </div>
        </div>
      )}
      <button className="run primary-action" disabled={!structurallyValid || !preview || saving} onClick={() => void save()}>
        {saving ? "CREATING…" : "CREATE IMMUTABLE BLEND VERSION"}
      </button>
    </div>
  );
}

const emptyChemistry: Chemistry = { cao: null, sio2: null, al2o3: null, fe2o3: null, mgo: null, so3: null, na2o: null, k2o: null, loi: null };

function ChemistryInputs({ title, value, setValue }: { title: string; value: Chemistry; setValue: (value: Chemistry) => void }) {
  return <><div className="section-heading"><span>{title}</span><span>BLANK = UNKNOWN · 0 = MEASURED ZERO</span></div><div className="oxide-inputs">{(Object.keys(value) as (keyof Chemistry)[]).map((oxide) => <label key={oxide}>{oxide.toUpperCase()}<input type="number" min="0" max="100" step="0.001" value={value[oxide] ?? ""} onChange={(event) => setValue({ ...value, [oxide]: event.target.value === "" ? null : Number(event.target.value) })} /></label>)}</div></>;
}

function MaterialEditor({ done }: { done: (material: Material) => void }) {
  const [name, setName] = useState("New Evidence-Backed Material");
  const [materialType, setMaterialType] = useState("limestone");
  const [functionalRole, setFunctionalRole] = useState("raw_kiln_feed");
  const [customSubtype, setCustomSubtype] = useState("");
  const [location, setLocation] = useState("Meghalaya");
  const [processingState, setProcessingState] = useState("as_received");
  const [cost, setCost] = useState("");
  const [co2, setCo2] = useState("");
  const [moisture, setMoisture] = useState("");
  const [grindability, setGrindability] = useState("");
  const [fuelAsh, setFuelAsh] = useState("");
  const [fuelCv, setFuelCv] = useState("");
  const [chemistry, setChemistry] = useState<Chemistry>({ ...emptyChemistry });
  const [chemistryMin, setChemistryMin] = useState<Chemistry>({ ...emptyChemistry });
  const [chemistryMax, setChemistryMax] = useState<Chemistry>({ ...emptyChemistry });
  const [fuelAshChemistry, setFuelAshChemistry] = useState<Chemistry>({ ...emptyChemistry });
  const [hasRange, setHasRange] = useState(false);
  const [evidenceClass, setEvidenceClass] = useState("measured");
  const [sourceTitle, setSourceTitle] = useState("Laboratory or source record — replace this title");
  const [sourceUri, setSourceUri] = useState("");
  const [page, setPage] = useState("");
  const [notes, setNotes] = useState("");
  const [dataGaps, setDataGaps] = useState("");
  const [error, setError] = useState("");
  const fuelRole = functionalRole === "fuel" || functionalRole === "alternative_fuel";

  async function save() {
    setError("");
    try {
      const saved = await req<Material>("/api/materials", {
        method: "POST",
        body: JSON.stringify({
          name, material_type: materialType === "custom" ? "custom" : materialType,
          functional_role: functionalRole, custom_subtype: customSubtype || null,
          location: location || null, processing_state: processingState,
          applicable_blend_classes: defaultMaterialClasses(materialType, functionalRole), chemistry,
          chemistry_min: hasRange ? chemistryMin : null, chemistry_max: hasRange ? chemistryMax : null,
          moisture_percent: moisture === "" ? null : Number(moisture),
          grindability_factor: grindability === "" ? null : Number(grindability),
          fuel_ash_percent: fuelAsh === "" ? null : Number(fuelAsh),
          fuel_calorific_value_kcal_kg: fuelCv === "" ? null : Number(fuelCv),
          fuel_ash_chemistry: fuelRole && fuelAsh !== "" ? fuelAshChemistry : null,
          cost_inr_per_t: cost === "" ? null : Number(cost), co2_kg_per_t: co2 === "" ? null : Number(co2),
          notes: notes || null, data_gaps: dataGaps.split(",").map((item) => item.trim()).filter(Boolean),
          evidence: [{ evidence_class: evidenceClass, source_title: sourceTitle, source_uri: sourceUri || null, page: page || null, note: notes || null }],
        }),
      });
      done(saved);
    } catch (caught) { setError(String(caught)); }
  }

  return <div className="composer"><h2>GUIDE / NEW MATERIAL RECORD</h2>
    <div className="form-grid two">
      <label>NAME<input value={name} onChange={(event) => setName(event.target.value)} /></label>
      <label>FUNCTIONAL ROLE<select value={functionalRole} onChange={(event) => setFunctionalRole(event.target.value)}>{functionalRoles.map((role) => <option key={role} value={role}>{pretty(role)}</option>)}</select></label>
      <label>CONTROLLED TYPE<select value={materialType} onChange={(event) => { const type = event.target.value; setMaterialType(type); setFunctionalRole(defaultFunctionalRole(type)); }}>{materialTypes.map((type) => <option key={type} value={type}>{pretty(type)}</option>)}</select></label>
      <label>CUSTOM SUBTYPE / TRADE NAME<input value={customSubtype} onChange={(event) => setCustomSubtype(event.target.value)} placeholder="Required context for custom materials" /></label>
      <label>LOCATION / SOURCE<input value={location} onChange={(event) => setLocation(event.target.value)} /></label>
      <label>PROCESSING STATE<input value={processingState} onChange={(event) => setProcessingState(event.target.value)} /></label>
      <label>DELIVERED COST ₹/T<input type="number" min="0" value={cost} onChange={(event) => setCost(event.target.value)} /></label>
      <label>MATERIAL CO₂ KG/T<input type="number" min="0" value={co2} onChange={(event) => setCo2(event.target.value)} /></label>
      <label>MOISTURE %<input type="number" min="0" max="100" value={moisture} onChange={(event) => setMoisture(event.target.value)} /></label>
      <label>GRINDABILITY FACTOR (1 = BASELINE)<input type="number" min="0.01" step="0.01" value={grindability} onChange={(event) => setGrindability(event.target.value)} /></label>
      {fuelRole && <><label>FUEL ASH %<input type="number" min="0" max="100" value={fuelAsh} onChange={(event) => setFuelAsh(event.target.value)} /></label><label>CALORIFIC VALUE KCAL/KG<input type="number" min="0" value={fuelCv} onChange={(event) => setFuelCv(event.target.value)} /></label></>}
    </div>
    <ChemistryInputs title="TYPICAL CHEMISTRY / MASS %" value={chemistry} setValue={setChemistry} />
    <label className="check-line"><input type="checkbox" checked={hasRange} onChange={(event) => setHasRange(event.target.checked)} /> ADD LOW/HIGH COHERENT LAB OR QUARRY PROFILES</label>
    {hasRange && <><ChemistryInputs title="LOW SCENARIO CHEMISTRY" value={chemistryMin} setValue={setChemistryMin} /><ChemistryInputs title="HIGH SCENARIO CHEMISTRY" value={chemistryMax} setValue={setChemistryMax} /></>}
    {fuelRole && fuelAsh !== "" && <ChemistryInputs title="FUEL ASH CHEMISTRY" value={fuelAshChemistry} setValue={setFuelAshChemistry} />}
    <div className="section-heading"><span>EVIDENCE</span><span>PROVENANCE TRAVELS WITH THE MATERIAL</span></div>
    <div className="form-grid two"><label>EVIDENCE CLASS<select value={evidenceClass} onChange={(event) => setEvidenceClass(event.target.value)}><option value="measured">Measured</option><option value="official_project_document">Official project document</option><option value="vendor_data">Vendor data</option><option value="literature">Literature</option><option value="inferred">Inferred</option><option value="assumed">Assumed</option></select></label><label>SOURCE TITLE<input value={sourceTitle} onChange={(event) => setSourceTitle(event.target.value)} /></label><label>SOURCE URI<input value={sourceUri} onChange={(event) => setSourceUri(event.target.value)} /></label><label>PAGE / TABLE<input value={page} onChange={(event) => setPage(event.target.value)} /></label></div>
    <label>NOTES<input value={notes} onChange={(event) => setNotes(event.target.value)} /></label><label>UNREPORTED / UNKNOWN FIELDS<input value={dataGaps} onChange={(event) => setDataGaps(event.target.value)} /></label>
    <pre className="validation-log">INFO  Role controls process behaviour; subtype preserves your own name.{"\n"}INFO  Blank chemistry is unknown and propagates as N/A; zero means a real zero.{"\n"}{evidenceClass === "measured" ? "PASS  Measured evidence selected" : "WARN  Not measured — keep this out of the calibrated base case"}</pre>
    {error && <div className="err">{error}</div>}<button className="run primary-action" disabled={!name.trim() || !sourceTitle.trim() || (materialType === "custom" && !customSubtype.trim())} onClick={() => void save()}>CREATE VERSIONED MATERIAL</button>
  </div>;
}
