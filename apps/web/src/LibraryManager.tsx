import { useState } from "react";

import { req } from "./api";
import type { Blend, CostBook, Machine, Material, Route } from "./types";

function pretty(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (match) => match.toUpperCase());
}

type EntityKind = "materials" | "blends" | "machines" | "routes" | "cost-books";

export function LibraryManager({
  materials,
  blends,
  machines,
  routes,
  costBooks,
  refresh,
}: {
  materials: Material[];
  blends: Blend[];
  machines: Machine[];
  routes: Route[];
  costBooks: CostBook[];
  refresh: () => Promise<void>;
}) {
  const [message, setMessage] = useState("");

  async function archive(kind: EntityKind, id: string) {
    setMessage("");
    try {
      await req(`/api/${kind}/${id}/archive`, { method: "POST" });
      await refresh();
      setMessage(`${id} archived. Historical run snapshots remain intact.`);
    } catch (caught) {
      setMessage(String(caught));
    }
  }

  async function remove(kind: EntityKind, id: string) {
    if (!window.confirm(`Permanently delete ${id}? Referenced records will be blocked automatically.`)) return;
    setMessage("");
    try {
      await req(`/api/${kind}/${id}`, { method: "DELETE" });
      await refresh();
      setMessage(`${id} permanently deleted because it had no dependencies.`);
    } catch (caught) {
      setMessage(`${String(caught)}\nUse ARCHIVE when immutable blends, routes or runs depend on this record.`);
    }
  }

  const actions = (kind: EntityKind, id: string) => <span className="record-actions"><button onClick={() => void archive(kind, id)}>ARCHIVE</button><button className="danger" onClick={() => void remove(kind, id)}>DELETE</button></span>;

  return (
    <section className="library managed-library">
      <div className="management-note">ARCHIVE hides a record from new experiments without damaging history. DELETE only succeeds when nothing references the record. Editing is performed by creating a new immutable version.</div>
      {message && <div className="err">{message}</div>}
      <div className="title">MATERIAL LIBRARY / {materials.length} ACTIVE VERSIONED RECORDS</div>
      {materials.map((material) => <div className="managed-row" key={material.material_id}><code>{material.material_id} · v{material.version}</code><span>{material.name} · {pretty(material.material_type)} · {material.processing_state}</span><span>{material.cost_inr_per_t === null ? "Legacy cost N/A" : `Legacy ₹${material.cost_inr_per_t}/t`} · chemistry/evidence version</span>{actions("materials", material.material_id)}</div>)}
      <div className="title">BLEND LIBRARY / {blends.length} ACTIVE IMMUTABLE RECIPES</div>
      {blends.map((blend) => <div className="managed-row" key={blend.blend_id}><code>{blend.blend_id} · v{blend.version}</code><span>{blend.name} · {pretty(blend.blend_class)}</span><span>{blend.components.length} direct components · {blend.status}</span>{actions("blends", blend.blend_id)}</div>)}
      <div className="title">MACHINE LIBRARY / {machines.length} ACTIVE RECORDS</div>
      {machines.map((machine) => <div className="managed-row" key={machine.machine_id}><code>{machine.machine_id} · v{machine.version}</code><span>{machine.name} · {pretty(machine.process_stage)}</span><span>{machine.rated_capacity_tph} t/h · TRL {machine.technology_readiness_level}</span>{actions("machines", machine.machine_id)}</div>)}
      <div className="title">ROUTE LIBRARY / {routes.length} ACTIVE IMMUTABLE TOPOLOGIES</div>
      {routes.map((route) => <div className="managed-row" key={route.route_id}><code>{route.route_id} · v{route.version}</code><span>{route.name} · {pretty(route.route_kind)}</span><span>{route.nodes.length} machines · {route.edges.length} streams</span>{actions("routes", route.route_id)}</div>)}
      <div className="title">COST BOOK LIBRARY / {costBooks.length} ACTIVE COMMERCIAL SCENARIOS</div>
      {costBooks.map((book) => <div className="managed-row" key={book.cost_book_id}><code>{book.cost_book_id} · v{book.version}</code><span>{book.name}</span><span>{book.effective_date || "No effective date"} · {book.material_costs.length} material prices</span>{actions("cost-books", book.cost_book_id)}</div>)}
    </section>
  );
}
