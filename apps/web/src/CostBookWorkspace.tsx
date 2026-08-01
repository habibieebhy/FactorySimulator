import { useEffect, useState } from "react";

import { req } from "./api";
import type { CostBook, Material } from "./types";

type CostDraft = { purchased: string; internal: string };

function optionalNumber(value: string): number | null {
  return value.trim() === "" ? null : Number(value);
}

export function CostBookWorkspace({
  materials,
  costBooks,
  done,
}: {
  materials: Material[];
  costBooks: CostBook[];
  done: (costBook: CostBook) => void;
}) {
  const [baseId, setBaseId] = useState("new");
  const [name, setName] = useState("New Plant Cost Book");
  const [effectiveDate, setEffectiveDate] = useState("");
  const [electricity, setElectricity] = useState("8.5");
  const [thermal, setThermal] = useState("900");
  const [packing, setPacking] = useState("");
  const [labour, setLabour] = useState("");
  const [maintenance, setMaintenance] = useState("");
  const [otherVariable, setOtherVariable] = useState("");
  const [factoryOverhead, setFactoryOverhead] = useState("");
  const [outbound, setOutbound] = useState("");
  const [notes, setNotes] = useState("Replace every assumption with a quotation, invoice or plant record.");
  const [costs, setCosts] = useState<Record<string, CostDraft>>({});
  const [error, setError] = useState("");

  useEffect(() => {
    const base = costBooks.find((item) => item.cost_book_id === baseId);
    const entryMap = new Map(base?.material_costs.map((entry) => [entry.material_id, entry]));
    setName(base ? `${base.name} — New Version` : "New Plant Cost Book");
    setEffectiveDate(base?.effective_date ?? "");
    setElectricity(base?.electricity_inr_kwh?.toString() ?? "8.5");
    setThermal(base?.thermal_fuel_inr_mkcal?.toString() ?? "900");
    setPacking(base?.packing_inr_t?.toString() ?? "");
    setLabour(base?.labour_inr_t?.toString() ?? "");
    setMaintenance(base?.maintenance_inr_t?.toString() ?? "");
    setOtherVariable(base?.other_variable_inr_t?.toString() ?? "");
    setFactoryOverhead(base?.factory_overhead_inr_t?.toString() ?? "");
    setOutbound(base?.outbound_logistics_inr_t?.toString() ?? "");
    setNotes(base?.notes ?? "Replace every assumption with a quotation, invoice or plant record.");
    setCosts(Object.fromEntries(materials.map((material) => {
      const entry = entryMap.get(material.material_id);
      return [material.material_id, {
        purchased: entry?.purchased_delivered_cost_inr_t?.toString() ?? material.cost_inr_per_t?.toString() ?? "",
        internal: entry?.internal_feed_cost_inr_t?.toString() ?? "",
      }];
    })));
  }, [baseId, costBooks, materials]);

  function updateCost(materialId: string, field: keyof CostDraft, value: string) {
    setCosts((current) => ({
      ...current,
      [materialId]: { ...(current[materialId] ?? { purchased: "", internal: "" }), [field]: value },
    }));
  }

  async function save() {
    setError("");
    const payload = {
      name,
      effective_date: effectiveDate || null,
      currency: "INR",
      electricity_inr_kwh: optionalNumber(electricity),
      thermal_fuel_inr_mkcal: optionalNumber(thermal),
      packing_inr_t: optionalNumber(packing),
      labour_inr_t: optionalNumber(labour),
      maintenance_inr_t: optionalNumber(maintenance),
      other_variable_inr_t: optionalNumber(otherVariable),
      factory_overhead_inr_t: optionalNumber(factoryOverhead),
      outbound_logistics_inr_t: optionalNumber(outbound),
      material_costs: materials.map((material) => ({
        material_id: material.material_id,
        purchased_delivered_cost_inr_t: optionalNumber(costs[material.material_id]?.purchased ?? ""),
        internal_feed_cost_inr_t: optionalNumber(costs[material.material_id]?.internal ?? ""),
        evidence_class: "user_input",
        note: "User-entered scenario value; attach source evidence before investment use",
      })),
      evidence: [{ evidence_class: "user_input", source_title: "User-maintained cost book" }],
      notes: notes || null,
    };
    try {
      const endpoint = baseId === "new" ? "/api/cost-books" : `/api/cost-books/${baseId}/versions`;
      done(await req<CostBook>(endpoint, { method: "POST", body: JSON.stringify(payload) }));
    } catch (caught) {
      setError(String(caught));
    }
  }

  return (
    <section className="guide wide-guide">
      <h2>GUIDE / VERSIONED COST BOOK</h2>
      <div className="form-grid two">
        <label>START FROM<select value={baseId} onChange={(event) => setBaseId(event.target.value)}><option value="new">Blank cost book</option>{costBooks.map((item) => <option value={item.cost_book_id} key={item.cost_book_id}>{item.name} · v{item.version}</option>)}</select></label>
        <label>COST BOOK NAME<input value={name} onChange={(event) => setName(event.target.value)} /></label>
        <label>EFFECTIVE DATE<input type="date" value={effectiveDate} onChange={(event) => setEffectiveDate(event.target.value)} /></label>
        <label>NOTES<input value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
      </div>
      <div className="section-heading"><span>ENERGY AND OPERATING COSTS</span><span>BLANK = UNKNOWN, NOT ZERO</span></div>
      <div className="cost-input-grid">
        <label>ELECTRICITY ₹/KWH<input type="number" min="0" step="0.01" value={electricity} onChange={(event) => setElectricity(event.target.value)} /></label>
        <label>THERMAL FUEL ₹/MILLION KCAL<input type="number" min="0" step="0.01" value={thermal} onChange={(event) => setThermal(event.target.value)} /></label>
        <label>PACKING ₹/T CEMENT<input type="number" min="0" step="0.01" value={packing} onChange={(event) => setPacking(event.target.value)} /></label>
        <label>LABOUR ₹/T CEMENT<input type="number" min="0" step="0.01" value={labour} onChange={(event) => setLabour(event.target.value)} /></label>
        <label>MAINTENANCE ₹/T CEMENT<input type="number" min="0" step="0.01" value={maintenance} onChange={(event) => setMaintenance(event.target.value)} /></label>
        <label>OTHER VARIABLE ₹/T<input type="number" min="0" step="0.01" value={otherVariable} onChange={(event) => setOtherVariable(event.target.value)} /></label>
        <label>FACTORY OVERHEAD ₹/T<input type="number" min="0" step="0.01" value={factoryOverhead} onChange={(event) => setFactoryOverhead(event.target.value)} /></label>
        <label>OUTBOUND LOGISTICS ₹/T<input type="number" min="0" step="0.01" value={outbound} onChange={(event) => setOutbound(event.target.value)} /></label>
      </div>
      <div className="section-heading"><span>ROUTE-AWARE MATERIAL PRICES</span><span>INTERNAL FEED EXCLUDES PROCESS ENERGY</span></div>
      <div className="table-responsive">
        <table className="editable-table">
          <thead><tr><th>Material</th><th>Type</th><th>Purchased delivered ₹/t</th><th>Internal feed/raw-material ₹/t product</th></tr></thead>
          <tbody>{materials.map((material) => <tr key={material.material_id}><td>{material.name}<small>{material.material_id} · v{material.version}</small></td><td>{material.material_type}</td><td><input type="number" min="0" step="0.01" value={costs[material.material_id]?.purchased ?? ""} onChange={(event) => updateCost(material.material_id, "purchased", event.target.value)} /></td><td><input type="number" min="0" step="0.01" value={costs[material.material_id]?.internal ?? ""} onChange={(event) => updateCost(material.material_id, "internal", event.target.value)} /></td></tr>)}</tbody>
        </table>
      </div>
      <pre className="validation-log">INFO  Grinding routes use purchased delivered clinker/calcined-clay prices.{"\n"}INFO  Integrated routes use internal feed costs and add kiln/calciner energy separately.{"\n"}WARN  Missing applicable prices make the calculated cost N/A instead of silently assuming zero.</pre>
      {error && <div className="err">{error}</div>}
      <button className="run primary-action" disabled={!name.trim()} onClick={() => void save()}>{baseId === "new" ? "CREATE IMMUTABLE COST BOOK" : "CREATE NEW COST BOOK VERSION"}</button>
    </section>
  );
}
