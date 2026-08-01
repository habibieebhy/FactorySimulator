import { useEffect, useState } from "react";

import { req } from "./api";
import type { Machine, Route } from "./types";

type DraftNode = { node_id: string; machine_id: string };

function draftId(): string {
  return `node_${Date.now()}_${Math.random().toString(16).slice(2, 8)}`;
}

function pretty(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (match) => match.toUpperCase());
}

export function RouteWorkspace({
  machines,
  routes,
  done,
}: {
  machines: Machine[];
  routes: Route[];
  done: (route: Route) => void;
}) {
  const [baseId, setBaseId] = useState("new");
  const [name, setName] = useState("New Process Route");
  const [kind, setKind] = useState("custom");
  const [nodes, setNodes] = useState<DraftNode[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    const base = routes.find((route) => route.route_id === baseId);
    if (base) {
      setName(`${base.name} — New Version`);
      setKind(base.route_kind);
      setNodes(base.nodes.map((node) => ({ node_id: node.node_id, machine_id: node.machine_id })));
    } else {
      setName("New Process Route");
      setKind("custom");
      setNodes([]);
    }
  }, [baseId, routes]);

  function move(index: number, direction: -1 | 1) {
    setNodes((current) => {
      const destination = index + direction;
      if (destination < 0 || destination >= current.length) return current;
      const copy = [...current];
      [copy[index], copy[destination]] = [copy[destination], copy[index]];
      return copy;
    });
  }

  function addNode() {
    if (!machines.length) return;
    setNodes((current) => [...current, { node_id: draftId(), machine_id: machines[0].machine_id }]);
  }

  async function save() {
    setError("");
    const routeNodes = nodes.map((node, index) => {
      const machine = machines.find((item) => item.machine_id === node.machine_id);
      return {
        node_id: node.node_id,
        machine_id: node.machine_id,
        label: machine?.name ?? "Unknown machine",
        position_x: index * 240,
        position_y: machine?.process_stage === "clay_calcination" ? 220 : 80,
      };
    });
    const edges = routeNodes.slice(1).map((node, index) => ({
      edge_id: `edge_${Date.now()}_${index + 1}`,
      source: routeNodes[index].node_id,
      target: node.node_id,
      stream_type: "material",
    }));
    try {
      const endpoint = baseId === "new" ? "/api/routes" : `/api/routes/${baseId}/versions`;
      done(await req<Route>(endpoint, {
        method: "POST",
        body: JSON.stringify({ name, route_kind: kind, nodes: routeNodes, edges }),
      }));
    } catch (caught) {
      setError(String(caught));
    }
  }

  return (
    <section className="guide wide-guide">
      <h2>GUIDE / ROUTE COMPOSER AND VERSION EDITOR</h2>
      <div className="form-grid two">
        <label>START FROM<select value={baseId} onChange={(event) => setBaseId(event.target.value)}><option value="new">Blank route</option>{routes.map((route) => <option value={route.route_id} key={route.route_id}>{route.name} · {pretty(route.route_kind)} · v{route.version}</option>)}</select></label>
        <label>ROUTE NAME<input value={name} onChange={(event) => setName(event.target.value)} /></label>
        <label>ROUTE KIND<select value={kind} onChange={(event) => setKind(event.target.value)}><option value="integrated">Integrated</option><option value="grinding_only">Grinding only</option><option value="integrated_lc3">Integrated LC3</option><option value="clinker_only">Clinker only</option><option value="custom">Custom</option></select></label>
      </div>
      <div className="section-heading"><span>ORDERED PROCESS NODES</span><span>{nodes.length} MACHINES</span></div>
      {nodes.map((node, index) => {
        const machine = machines.find((item) => item.machine_id === node.machine_id);
        return <div className="route-node-row" key={node.node_id}><code>{index + 1}</code><select value={node.machine_id} onChange={(event) => setNodes((current) => current.map((item, rowIndex) => rowIndex === index ? { ...item, machine_id: event.target.value } : item))}>{machines.map((item) => <option value={item.machine_id} key={item.machine_id}>{item.name} · {pretty(item.process_stage)} · {item.rated_capacity_tph} t/h · v{item.version}</option>)}</select><span>{machine ? `${machine.specific_electricity_kwh_t} kWh/t stage · ${machine.specific_heat_kcal_kg} kcal/kg stage` : "Unknown"}</span><button className="icon-button" disabled={index === 0} onClick={() => move(index, -1)}>UP</button><button className="icon-button" disabled={index === nodes.length - 1} onClick={() => move(index, 1)}>DOWN</button><button className="icon-button danger" onClick={() => setNodes((current) => current.filter((_, rowIndex) => rowIndex !== index))}>REMOVE</button></div>;
      })}
      <button onClick={addNode} disabled={!machines.length}>+ ADD MACHINE STAGE</button>
      <pre className="validation-log">INFO  Machines execute in the displayed order; material edges are rebuilt automatically.{"\n"}INFO  Editing creates a new immutable route version. Existing runs retain the old route snapshot.{"\n"}{nodes.length ? "PASS  Route contains at least one machine" : "FAIL  Add at least one machine"}</pre>
      {error && <div className="err">{error}</div>}
      <button className="run primary-action" disabled={!name.trim() || nodes.length === 0} onClick={() => void save()}>{baseId === "new" ? "CREATE IMMUTABLE ROUTE" : "CREATE NEW ROUTE VERSION"}</button>
    </section>
  );
}
