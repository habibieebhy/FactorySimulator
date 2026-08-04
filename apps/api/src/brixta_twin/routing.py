from __future__ import annotations

from collections import deque

from .blending import direct_production_fractions, preview_blend
from .models import (
    Blend,
    Machine,
    Route,
    RouteAnalysis,
    RouteGraphAnalysis,
    RouteRecommendationSet,
)
from .storage import Repository


ROUTE_DESCRIPTIONS = {
    "integrated": "Quarry/raw feed is crushed and ground, converted to clinker in a kiln, then ground and packed as cement.",
    "grinding_only": "Purchased or transferred clinker and additions are proportioned, finish-ground and packed; no clinker kiln is modelled.",
    "integrated_lc3": "An integrated clinker line is combined with a separate clay-calcination path before finish grinding and packing.",
    "clinker_only": "Raw feed is converted to clinker; finish grinding and cement dispatch are outside this route.",
    "custom": "A user-versioned machine graph; suitability depends on graph validity and the stages actually present.",
}


def required_stages(blend: Blend, route_kind: str | None = None) -> set[str]:
    if blend.blend_class == "raw_material_stockpile":
        return {"crushing"}
    if blend.blend_class == "raw_meal" and route_kind == "clinker_only":
        return {"crushing", "raw_grinding", "thermal_transformation"}
    if blend.blend_class == "raw_meal":
        return {"crushing", "raw_grinding"}
    if blend.blend_class == "clinker_blend":
        return {"thermal_transformation"}
    if blend.blend_class == "finished_cement":
        return {"cement_grinding", "packing_dispatch"}
    if blend.blend_class == "premix":
        return {"cement_grinding"}
    return set()


def stage_throughput_factor(
    machine: Machine,
    blend: Blend,
    route_stages: set[str],
    fractions_by_type: dict[str, float],
    raw_meal_to_clinker_yield: float,
    route_kind: str | None = None,
) -> float:
    if blend.blend_class == "raw_meal" and route_kind == "clinker_only":
        if machine.process_stage in {"crushing", "raw_grinding"}:
            return 1.0 / max(raw_meal_to_clinker_yield, 1e-9)
        if machine.process_stage == "thermal_transformation":
            return 1.0
        return 0.0
    if blend.blend_class != "finished_cement":
        return 1.0 if machine.process_stage in required_stages(blend, route_kind) else 0.0
    clinker_fraction = fractions_by_type.get("clinker", 0.0)
    calcined_clay_fraction = fractions_by_type.get("calcined_clay", 0.0)
    if "thermal_transformation" in route_stages:
        if machine.process_stage in {"crushing", "raw_grinding"}:
            return clinker_fraction / raw_meal_to_clinker_yield if clinker_fraction else 0.0
        if machine.process_stage == "thermal_transformation":
            return clinker_fraction
    if machine.process_stage == "clay_calcination":
        return calcined_clay_fraction
    return 1.0


def analyse_route_graph(
    route: Route,
    machine_by_node: dict[str, Machine],
    factor_by_node: dict[str, float] | None = None,
) -> RouteGraphAnalysis:
    """Validate and analyse a process route as a directed acyclic graph.

    Kahn's algorithm provides the execution order. A dynamic-programming pass
    then finds the slowest cumulative path using factor/effective-capacity as a
    processing-time proxy. No statistical or AI model is involved.
    """

    factor_by_node = factor_by_node or {}
    warnings: list[str] = []
    node_ids = [node.node_id for node in route.nodes]
    if len(node_ids) != len(set(node_ids)):
        return RouteGraphAnalysis(acyclic=False, warnings=["Route contains duplicate node IDs"])
    node_set = set(node_ids)
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    indegree: dict[str, int] = {node_id: 0 for node_id in node_ids}
    seen_edges: set[tuple[str, str]] = set()
    for edge in route.edges:
        if edge.source not in node_set or edge.target not in node_set:
            warnings.append(f"Edge {edge.edge_id} references an unknown node")
            continue
        if edge.source == edge.target:
            warnings.append(f"Edge {edge.edge_id} is a self-loop")
            indegree[edge.target] += 1
            continue
        pair = (edge.source, edge.target)
        if pair in seen_edges:
            warnings.append(f"Duplicate graph edge {edge.source}→{edge.target} was ignored")
            continue
        seen_edges.add(pair)
        adjacency[edge.source].append(edge.target)
        indegree[edge.target] += 1

    position = {node_id: index for index, node_id in enumerate(node_ids)}
    queue: deque[str] = deque(
        sorted(
            (node for node in node_ids if indegree[node] == 0),
            key=lambda candidate_node_id: position[candidate_node_id],
        )
    )
    topological: list[str] = []
    mutable_indegree = dict(indegree)
    while queue:
        node_id = queue.popleft()
        topological.append(node_id)
        for target in sorted(
            adjacency[node_id],
            key=lambda target_node_id: position[target_node_id],
        ):
            mutable_indegree[target] -= 1
            if mutable_indegree[target] == 0:
                queue.append(target)

    acyclic = len(topological) == len(node_ids) and not any("self-loop" in item for item in warnings)
    if not acyclic:
        warnings.append("Cycle detected: route cannot be executed as a deterministic process DAG")

    source_nodes = [node for node in node_ids if indegree[node] == 0]
    sink_nodes = [node for node in node_ids if not adjacency[node]]
    if len(source_nodes) > 1:
        warnings.append(f"Route has {len(source_nodes)} parallel source branches")
    if len(sink_nodes) > 1:
        warnings.append(f"Route has {len(sink_nodes)} terminal sinks")

    depth: dict[str, int] = {node: 1 for node in node_ids}
    distance: dict[str, float] = {node: 0.0 for node in node_ids}
    predecessor: dict[str, str | None] = {node: None for node in node_ids}
    if acyclic:
        for node_id in topological:
            machine = machine_by_node.get(node_id)
            factor = max(0.0, factor_by_node.get(node_id, 0.0))
            effective = None
            if machine is not None:
                effective = machine.rated_capacity_tph * machine.availability
                if machine.maximum_stable_tph is not None:
                    effective = min(effective, machine.maximum_stable_tph)
            node_weight = factor / effective if effective and factor > 0 else 0.0
            if predecessor[node_id] is None:
                distance[node_id] = max(distance[node_id], node_weight)
            else:
                distance[node_id] += node_weight
            for target in adjacency[node_id]:
                candidate_depth = depth[node_id] + 1
                candidate_distance = distance[node_id]
                if candidate_depth > depth[target]:
                    depth[target] = candidate_depth
                if candidate_distance > distance[target]:
                    distance[target] = candidate_distance
                    predecessor[target] = node_id

    terminal = max(sink_nodes or node_ids, key=lambda node: distance.get(node, 0.0), default=None)
    critical_path: list[str] = []
    cursor = terminal
    while cursor is not None:
        critical_path.append(cursor)
        cursor = predecessor.get(cursor)
    critical_path.reverse()
    labels = {node.node_id: node.label for node in route.nodes}
    return RouteGraphAnalysis(
        acyclic=acyclic,
        topological_order=topological,
        source_nodes=source_nodes,
        sink_nodes=sink_nodes,
        critical_path_node_ids=critical_path,
        critical_path_labels=[labels.get(node, node) for node in critical_path],
        graph_depth=max(depth.values(), default=0),
        critical_path_hours_per_t_output=(round(distance.get(terminal, 0.0), 8) if terminal else None),
        warnings=warnings,
    )


def analyse_route(
    repository: Repository,
    blend: Blend,
    route: Route,
    target_output_tph: float,
    raw_meal_to_clinker_yield: float = 0.65,
) -> RouteAnalysis:
    preview = preview_blend(repository, blend, root_id=blend.blend_id)
    machine_by_node: dict[str, Machine] = {}
    for node in route.nodes:
        machine = repository.get("machines", node.machine_id)
        if isinstance(machine, Machine):
            machine_by_node[node.node_id] = machine

    machines = list(machine_by_node.values())
    stages = {machine.process_stage for machine in machines}
    required = required_stages(blend, route.route_kind)
    missing = required - stages
    extra = stages - required
    fractions: dict[str, float] = {}
    for component in preview.flattened_components:
        fractions[component.material_type] = fractions.get(component.material_type, 0.0) + component.percentage / 100.0
    if blend.blend_class == "finished_cement":
        production_fractions = direct_production_fractions(repository, blend)
        fractions["clinker"] = production_fractions["clinker"]
        fractions["calcined_clay"] = production_fractions["calcined_clay"]
        if route.route_kind in {"integrated", "integrated_lc3"} and production_fractions["clinker"] > 0:
            required.update({"crushing", "raw_grinding", "thermal_transformation"})
        if route.route_kind == "integrated_lc3" and production_fractions["calcined_clay"] > 0:
            required.add("clay_calcination")
        missing = required - stages
        extra = stages - required

    capacity_candidates: list[tuple[float, Machine]] = []
    factor_by_node: dict[str, float] = {}
    low_trl = 0
    weighted_availability_numerator = 0.0
    factor_total = 0.0
    electricity = 0.0
    thermal = 0.0
    trl_values: list[float] = []
    for node_id, machine in machine_by_node.items():
        if machine.technology_readiness_level < 8:
            low_trl += 1
        trl_values.append(float(machine.technology_readiness_level))
        factor = stage_throughput_factor(
            machine,
            blend,
            stages,
            fractions,
            raw_meal_to_clinker_yield,
            route.route_kind,
        )
        factor_by_node[node_id] = factor
        if factor <= 0:
            continue
        stage_capacity = machine.rated_capacity_tph * machine.availability
        if machine.maximum_stable_tph is not None:
            stage_capacity = min(stage_capacity, machine.maximum_stable_tph)
        capacity_candidates.append((stage_capacity / factor, machine))
        electricity += machine.specific_electricity_kwh_t * factor
        thermal += machine.specific_heat_kcal_kg * factor
        weighted_availability_numerator += machine.availability * factor
        factor_total += factor

    graph = analyse_route_graph(route, machine_by_node, factor_by_node)
    predicted = None
    bottleneck = None
    if capacity_candidates:
        predicted, bottleneck_machine = min(capacity_candidates, key=lambda item: item[0])
        bottleneck = bottleneck_machine.name

    reasons: list[str] = []
    if not graph.acyclic:
        reasons.append("Route graph contains a cycle or invalid edge and cannot be executed")
    if missing:
        reasons.append("Missing required stages: " + ", ".join(sorted(missing)))
    else:
        reasons.append("All required production stages are present")
    if predicted is not None:
        if predicted >= target_output_tph:
            reasons.append(f"Estimated capacity meets the {target_output_tph:.1f} t/h target")
        else:
            reasons.append(f"Estimated capacity is {target_output_tph - predicted:.1f} t/h below target")
    else:
        reasons.append("No capacity-bearing machine is available for this recipe")
    if low_trl:
        reasons.append(f"{low_trl} machine(s) are below TRL 8")
    if graph.critical_path_labels:
        reasons.append("DAG critical path: " + " → ".join(graph.critical_path_labels))
    if route.route_kind == "integrated" and blend.blend_class == "finished_cement":
        reasons.append("Integrated-route screening uses the stored clinker fraction and raw-meal yield; attach an optimised raw meal before calibrated use")
    if route.route_kind == "grinding_only":
        reasons.append("Clinker and additions are purchased/transferred feed; kiln fuel and clinker production are excluded")

    capacity_penalty = 35.0 if predicted is None else max(0.0, min(35.0, (target_output_tph - predicted) / target_output_tph * 35.0))
    compatibility_score = 100.0 - 28.0 * len(missing) - capacity_penalty - 5.0 * low_trl
    if extra:
        compatibility_score -= min(10.0, len(extra) * 1.5)
    if not graph.acyclic:
        compatibility_score -= 45.0
    compatibility_score = max(0.0, min(100.0, compatibility_score))

    capacity_ratio = min((predicted or 0.0) / max(target_output_tph, 1e-9), 1.2) / 1.2
    energy_score = max(0.0, 1.0 - min(1.0, electricity / 100.0) * 0.45 - min(1.0, thermal / 1000.0) * 0.55)
    availability = weighted_availability_numerator / factor_total if factor_total else None
    mean_trl = sum(trl_values) / len(trl_values) if trl_values else None
    efficiency_score = (
        35.0 * capacity_ratio
        + 25.0 * energy_score
        + 15.0 * (availability or 0.0)
        + 10.0 * ((mean_trl or 0.0) / 9.0)
        + 15.0 * (1.0 if not missing and graph.acyclic else 0.0)
    )
    efficiency_score = max(0.0, min(100.0, efficiency_score))

    ordered_ids = graph.topological_order if graph.acyclic else [node.node_id for node in route.nodes]
    label_by_id = {node.node_id: node.label for node in route.nodes}
    ordered_flow = " → ".join(label_by_id.get(node_id, node_id) for node_id in ordered_ids) or "No machines"
    return RouteAnalysis(
        route_id=route.route_id,
        route_name=route.name,
        route_kind=route.route_kind,
        description=ROUTE_DESCRIPTIONS.get(route.route_kind, ROUTE_DESCRIPTIONS["custom"]),
        flow_summary=ordered_flow,
        compatible=not missing and predicted is not None and graph.acyclic,
        compatibility_score=round(compatibility_score, 2),
        efficiency_score=round(efficiency_score, 2),
        predicted_output_tph=round(predicted, 3) if predicted is not None else None,
        bottleneck_machine_name=bottleneck,
        electricity_kwh_t_output=round(electricity, 4),
        thermal_kcal_kg_output=round(thermal, 4),
        weighted_availability=round(availability, 4) if availability is not None else None,
        mean_technology_readiness_level=round(mean_trl, 3) if mean_trl is not None else None,
        graph=graph,
        required_stages=sorted(required),
        present_stages=sorted(stages),
        missing_stages=sorted(missing),
        extra_stages=sorted(extra),
        reasons=reasons + graph.warnings,
    )


def _dominates(left: RouteAnalysis, right: RouteAnalysis) -> bool:
    left_values = (
        left.compatibility_score,
        left.efficiency_score,
        left.predicted_output_tph or 0.0,
        -(left.electricity_kwh_t_output or 0.0),
        -(left.thermal_kcal_kg_output or 0.0),
    )
    right_values = (
        right.compatibility_score,
        right.efficiency_score,
        right.predicted_output_tph or 0.0,
        -(right.electricity_kwh_t_output or 0.0),
        -(right.thermal_kcal_kg_output or 0.0),
    )
    return all(a >= b - 1e-9 for a, b in zip(left_values, right_values, strict=True)) and any(
        a > b + 1e-9 for a, b in zip(left_values, right_values, strict=True)
    )


def _stage_distance(left: RouteAnalysis, right: RouteAnalysis) -> float:
    left_stages = set(left.present_stages)
    right_stages = set(right.present_stages)
    union = left_stages | right_stages
    return 0.0 if not union else 1.0 - len(left_stages & right_stages) / len(union)


def _distance(left: RouteAnalysis, right: RouteAnalysis, target_output_tph: float) -> float:
    return round(
        0.30 * _stage_distance(left, right)
        + 0.20 * abs((left.predicted_output_tph or 0.0) - (right.predicted_output_tph or 0.0)) / max(target_output_tph, 1.0)
        + 0.15 * abs((left.electricity_kwh_t_output or 0.0) - (right.electricity_kwh_t_output or 0.0)) / 100.0
        + 0.15 * abs((left.thermal_kcal_kg_output or 0.0) - (right.thermal_kcal_kg_output or 0.0)) / 1000.0
        + 0.10 * abs(left.efficiency_score - right.efficiency_score) / 100.0
        + 0.10 * (0.0 if left.route_kind == right.route_kind else 1.0),
        6,
    )


def recommend_routes(
    repository: Repository,
    blend: Blend,
    target_output_tph: float,
    selected_route_id: str | None = None,
) -> RouteRecommendationSet:
    analyses = [
        analyse_route(repository, blend, route, target_output_tph)
        for route in repository.list("routes")
        if isinstance(route, Route) and not route.archived
    ]
    pareto_ids = {
        candidate.route_id
        for candidate in analyses
        if candidate.compatible and not any(
            other.route_id != candidate.route_id and other.compatible and _dominates(other, candidate)
            for other in analyses
        )
    }
    selected_base = next((item for item in analyses if item.route_id == selected_route_id), None)
    enriched: list[RouteAnalysis] = []
    for analysis in analyses:
        updates: dict[str, object] = {"pareto_efficient": analysis.route_id in pareto_ids}
        if selected_base is not None:
            distance = _distance(analysis, selected_base, target_output_tph)
            improves = analysis.route_id != selected_base.route_id and _dominates(analysis, selected_base)
            improvement_reasons: list[str] = []
            if improves:
                if (analysis.predicted_output_tph or 0) > (selected_base.predicted_output_tph or 0):
                    improvement_reasons.append("higher predicted output")
                if (analysis.electricity_kwh_t_output or 0) < (selected_base.electricity_kwh_t_output or 0):
                    improvement_reasons.append("lower specific electricity")
                if (analysis.thermal_kcal_kg_output or 0) < (selected_base.thermal_kcal_kg_output or 0):
                    improvement_reasons.append("lower specific thermal demand")
                if analysis.efficiency_score > selected_base.efficiency_score:
                    improvement_reasons.append("higher deterministic efficiency score")
            updates.update(
                distance_from_selected=distance,
                improves_selected=improves,
                improvement_reasons=improvement_reasons,
            )
        enriched.append(analysis.model_copy(update=updates))

    enriched.sort(
        key=lambda item: (
            not item.compatible,
            not item.improves_selected if selected_base else False,
            not item.pareto_efficient,
            item.distance_from_selected if item.distance_from_selected is not None else 999.0,
            -item.efficiency_score,
            -(item.predicted_output_tph or 0.0),
            item.route_name,
        )
    )
    selected = next((item for item in enriched if item.route_id == selected_route_id), None)
    nearest = next((item.route_id for item in enriched if item.improves_selected), None)
    return RouteRecommendationSet(
        blend_id=blend.blend_id,
        target_output_tph=target_output_tph,
        selected_route_id=selected_route_id,
        selected=selected,
        nearest_more_efficient_route_id=nearest,
        recommendations=enriched,
    )
