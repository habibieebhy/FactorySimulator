from __future__ import annotations

from .blending import preview_blend
from .models import Blend, Machine, Route, RouteAnalysis, RouteRecommendationSet
from .storage import Repository


ROUTE_DESCRIPTIONS = {
    "integrated": "Quarry/raw feed is crushed and ground, converted to clinker in a kiln, then ground and packed as cement.",
    "grinding_only": "Purchased or transferred clinker and additions are proportioned, finish-ground and packed; no clinker kiln is modelled.",
    "integrated_lc3": "An integrated clinker line is combined with a separate clay-calcination path before finish grinding and packing.",
    "clinker_only": "Raw feed is converted to clinker; finish grinding and cement dispatch are outside this route.",
    "custom": "A user-versioned sequence of machines; suitability depends on the stages actually present.",
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
        # Intermediate products stop at their own process boundary.  Extra
        # machines in a full integrated route must not silently constrain or
        # consume energy for a raw-meal, stockpile or premix campaign.
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


def analyse_route(
    repository: Repository,
    blend: Blend,
    route: Route,
    target_output_tph: float,
    raw_meal_to_clinker_yield: float = 0.65,
) -> RouteAnalysis:
    preview = preview_blend(repository, blend, root_id=blend.blend_id)
    machines: list[Machine] = []
    for node in route.nodes:
        machine = repository.get("machines", node.machine_id)
        if isinstance(machine, Machine):
            machines.append(machine)

    stages = {machine.process_stage for machine in machines}
    required = required_stages(blend, route.route_kind)
    missing = required - stages
    extra = stages - required
    fractions: dict[str, float] = {}
    for component in preview.flattened_components:
        fractions[component.material_type] = (
            fractions.get(component.material_type, 0.0) + component.percentage / 100.0
        )

    capacity_candidates: list[tuple[float, Machine]] = []
    low_trl = 0
    for machine in machines:
        if machine.technology_readiness_level < 8:
            low_trl += 1
        factor = stage_throughput_factor(
            machine,
            blend,
            stages,
            fractions,
            raw_meal_to_clinker_yield,
            route.route_kind,
        )
        if factor <= 0:
            continue
        stage_capacity = machine.rated_capacity_tph * machine.availability
        if machine.maximum_stable_tph is not None:
            stage_capacity = min(stage_capacity, machine.maximum_stable_tph)
        capacity_candidates.append((stage_capacity / factor, machine))

    predicted = None
    bottleneck = None
    if capacity_candidates:
        predicted, bottleneck_machine = min(capacity_candidates, key=lambda item: item[0])
        bottleneck = bottleneck_machine.name

    reasons: list[str] = []
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
    if route.route_kind == "integrated" and blend.blend_class == "finished_cement":
        reasons.append("Integrated-route screening uses the stored clinker fraction and raw-meal yield; attach an optimised raw meal before treating this as a calibrated production case")
    if route.route_kind == "grinding_only":
        reasons.append("Clinker and additions are treated as purchased/transferred feed; kiln fuel and clinker production are excluded")

    capacity_penalty = 0.0
    if predicted is None:
        capacity_penalty = 35.0
    elif predicted < target_output_tph:
        capacity_penalty = min(35.0, (target_output_tph - predicted) / target_output_tph * 35.0)
    score = 100.0 - 28.0 * len(missing) - capacity_penalty - 5.0 * low_trl
    if extra:
        score -= min(10.0, len(extra) * 1.5)
    score = max(0.0, min(100.0, score))

    ordered_flow = " → ".join(node.label for node in route.nodes) or "No machines"
    return RouteAnalysis(
        route_id=route.route_id,
        route_name=route.name,
        route_kind=route.route_kind,
        description=ROUTE_DESCRIPTIONS.get(route.route_kind, ROUTE_DESCRIPTIONS["custom"]),
        flow_summary=ordered_flow,
        compatible=not missing and predicted is not None,
        compatibility_score=round(score, 2),
        predicted_output_tph=round(predicted, 3) if predicted is not None else None,
        bottleneck_machine_name=bottleneck,
        required_stages=sorted(required),
        present_stages=sorted(stages),
        missing_stages=sorted(missing),
        extra_stages=sorted(extra),
        reasons=reasons,
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
    analyses.sort(
        key=lambda item: (
            not item.compatible,
            -item.compatibility_score,
            -(item.predicted_output_tph or 0.0),
            item.route_name,
        )
    )
    selected = next((item for item in analyses if item.route_id == selected_route_id), None)
    return RouteRecommendationSet(
        blend_id=blend.blend_id,
        target_output_tph=target_output_tph,
        selected_route_id=selected_route_id,
        selected=selected,
        recommendations=analyses,
    )
