import { useState } from "react";

import { req } from "./api";
import type { Blend, CostBook, Machine, Material, Route } from "./types";

function pretty(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (match) => match.toUpperCase());
}

type EntityKind = "materials" | "blends" | "machines" | "routes" | "cost-books";
type LibraryView = "active" | "archived";
type Notice = { kind: "success" | "error"; text: string } | null;

function archivedWhen(value?: string | null): string {
  return value ? `Archived ${new Date(value).toLocaleString()}` : "Archived";
}

export function LibraryManager({
  materials,
  archivedMaterials,
  blends,
  archivedBlends,
  machines,
  archivedMachines,
  routes,
  archivedRoutes,
  costBooks,
  archivedCostBooks,
  refresh,
}: {
  materials: Material[];
  archivedMaterials: Material[];
  blends: Blend[];
  archivedBlends: Blend[];
  machines: Machine[];
  archivedMachines: Machine[];
  routes: Route[];
  archivedRoutes: Route[];
  costBooks: CostBook[];
  archivedCostBooks: CostBook[];
  refresh: () => Promise<void>;
}) {
  const [view, setView] = useState<LibraryView>("active");
  const [notice, setNotice] = useState<Notice>(null);
  const [busy, setBusy] = useState("");

  const activeCount = materials.length + blends.length + machines.length + routes.length + costBooks.length;
  const archivedCount = archivedMaterials.length + archivedBlends.length + archivedMachines.length + archivedRoutes.length + archivedCostBooks.length;

  async function archive(kind: EntityKind, id: string) {
    setNotice(null);
    setBusy(id);
    try {
      await req(`/api/${kind}/${id}/archive`, { method: "POST" });
      await refresh();
      setNotice({ kind: "success", text: `${id} archived. It is now available under ARCHIVED; historical run snapshots remain intact.` });
    } catch (caught) {
      setNotice({ kind: "error", text: String(caught) });
    } finally {
      setBusy("");
    }
  }

  async function restore(kind: EntityKind, id: string) {
    setNotice(null);
    setBusy(id);
    try {
      await req(`/api/${kind}/${id}/restore`, { method: "POST" });
      await refresh();
      setNotice({ kind: "success", text: `${id} restored. It is active and can be selected in new experiments again.` });
    } catch (caught) {
      setNotice({ kind: "error", text: String(caught) });
    } finally {
      setBusy("");
    }
  }

  async function remove(kind: EntityKind, id: string) {
    if (!window.confirm(`Permanently delete archived record ${id}? This cannot be undone. Referenced records will be blocked automatically.`)) return;
    setNotice(null);
    setBusy(id);
    try {
      await req(`/api/${kind}/${id}`, { method: "DELETE" });
      await refresh();
      setNotice({ kind: "success", text: `${id} permanently deleted because it had no dependencies.` });
    } catch (caught) {
      setNotice({ kind: "error", text: `${String(caught)}\nRestore or retain the record when immutable blends, routes, cost books, or runs depend on it.` });
    } finally {
      setBusy("");
    }
  }

  const actions = (kind: EntityKind, id: string) => view === "active"
    ? <span className="record-actions"><button disabled={Boolean(busy)} onClick={() => void archive(kind, id)}>{busy === id ? "WORKING…" : "ARCHIVE"}</button></span>
    : <span className="record-actions"><button disabled={Boolean(busy)} onClick={() => void restore(kind, id)}>{busy === id ? "WORKING…" : "RESTORE"}</button><button disabled={Boolean(busy)} className="danger" onClick={() => void remove(kind, id)}>DELETE</button></span>;

  const shownMaterials = view === "active" ? materials : archivedMaterials;
  const shownBlends = view === "active" ? blends : archivedBlends;
  const shownMachines = view === "active" ? machines : archivedMachines;
  const shownRoutes = view === "active" ? routes : archivedRoutes;
  const shownCostBooks = view === "active" ? costBooks : archivedCostBooks;
  const stateLabel = view.toUpperCase();

  return (
    <section className="library managed-library">
      <div className="management-note">ACTIVE records can be selected for new experiments. ARCHIVE removes a record from new selectors without damaging history. Open ARCHIVED to restore it or permanently delete it. DELETE remains dependency-safe and cannot remove anything referenced by immutable records.</div>
      <div className="library-mode-tabs" role="tablist" aria-label="Library record state">
        <button className={view === "active" ? "selected" : ""} onClick={() => setView("active")} role="tab" aria-selected={view === "active"}>ACTIVE <strong>{activeCount}</strong></button>
        <button className={view === "archived" ? "selected" : ""} onClick={() => setView("archived")} role="tab" aria-selected={view === "archived"}>ARCHIVED <strong>{archivedCount}</strong></button>
      </div>
      <div className="library-count-grid">
        <span>MATERIALS <strong>{materials.length} / {archivedMaterials.length}</strong></span>
        <span>BLENDS <strong>{blends.length} / {archivedBlends.length}</strong></span>
        <span>MACHINES <strong>{machines.length} / {archivedMachines.length}</strong></span>
        <span>ROUTES <strong>{routes.length} / {archivedRoutes.length}</strong></span>
        <span>COST BOOKS <strong>{costBooks.length} / {archivedCostBooks.length}</strong></span>
      </div>
      <div className="count-legend">COUNTS SHOW ACTIVE / ARCHIVED</div>
      {notice && <div className={notice.kind === "error" ? "err" : "management-success"}>{notice.text}</div>}

      <div className="title">MATERIAL LIBRARY / {shownMaterials.length} {stateLabel} VERSIONED RECORDS</div>
      {shownMaterials.length === 0 && <div className="managed-empty">No {view} materials.</div>}
      {shownMaterials.map((material) => <div className={`managed-row ${view === "archived" ? "archived" : ""}`} key={material.material_id}><code>{material.material_id} · v{material.version}</code><span>{material.name} · {pretty(material.material_type)} · {material.processing_state}</span><span>{view === "archived" ? archivedWhen(material.archived_at) : material.cost_inr_per_t === null ? "Legacy cost N/A" : `Legacy ₹${material.cost_inr_per_t}/t`} · chemistry/evidence version</span>{actions("materials", material.material_id)}</div>)}

      <div className="title">BLEND LIBRARY / {shownBlends.length} {stateLabel} IMMUTABLE RECIPES</div>
      {shownBlends.length === 0 && <div className="managed-empty">No {view} blends.</div>}
      {shownBlends.map((blend) => <div className={`managed-row ${view === "archived" ? "archived" : ""}`} key={blend.blend_id}><code>{blend.blend_id} · v{blend.version}</code><span>{blend.name} · {pretty(blend.blend_class)}</span><span>{view === "archived" ? archivedWhen(blend.archived_at) : `${blend.components.length} direct components · ${blend.status}`}</span>{actions("blends", blend.blend_id)}</div>)}

      <div className="title">MACHINE LIBRARY / {shownMachines.length} {stateLabel} RECORDS</div>
      {shownMachines.length === 0 && <div className="managed-empty">No {view} machines.</div>}
      {shownMachines.map((machine) => <div className={`managed-row ${view === "archived" ? "archived" : ""}`} key={machine.machine_id}><code>{machine.machine_id} · v{machine.version}</code><span>{machine.name} · {pretty(machine.process_stage)}</span><span>{view === "archived" ? archivedWhen(machine.archived_at) : `${machine.rated_capacity_tph} t/h · TRL ${machine.technology_readiness_level}`}</span>{actions("machines", machine.machine_id)}</div>)}

      <div className="title">ROUTE LIBRARY / {shownRoutes.length} {stateLabel} IMMUTABLE TOPOLOGIES</div>
      {shownRoutes.length === 0 && <div className="managed-empty">No {view} routes.</div>}
      {shownRoutes.map((route) => <div className={`managed-row ${view === "archived" ? "archived" : ""}`} key={route.route_id}><code>{route.route_id} · v{route.version}</code><span>{route.name} · {pretty(route.route_kind)}</span><span>{view === "archived" ? archivedWhen(route.archived_at) : `${route.nodes.length} machines · ${route.edges.length} streams`}</span>{actions("routes", route.route_id)}</div>)}

      <div className="title">COST BOOK LIBRARY / {shownCostBooks.length} {stateLabel} COMMERCIAL SCENARIOS</div>
      {shownCostBooks.length === 0 && <div className="managed-empty">No {view} cost books.</div>}
      {shownCostBooks.map((book) => <div className={`managed-row ${view === "archived" ? "archived" : ""}`} key={book.cost_book_id}><code>{book.cost_book_id} · v{book.version}</code><span>{book.name}</span><span>{view === "archived" ? archivedWhen(book.archived_at) : `${book.effective_date || "No effective date"} · ${book.material_costs.length} material prices`}</span>{actions("cost-books", book.cost_book_id)}</div>)}
    </section>
  );
}
