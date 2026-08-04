from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Iterable

from .blending import preview_blend
from .models import (
    AssumptionRecord,
    Blend,
    BlendComponent,
    Chemistry,
    CostBook,
    FormulationStageResult,
    Material,
    PercentageBounds,
    PpcToLc3RetrofitRequest,
    RetrofitAssetGap,
    RetrofitBaseline,
    RetrofitCandidate,
    RetrofitComponentShare,
    RetrofitObjectiveWeights,
    RetrofitReference,
    RetrofitStressScenario,
    RetrofitStudyResult,
    Route,
    CalculationTraceStep,
    new_id,
    now,
)
from .routing import analyse_route
from .storage import Repository


ROLES = ("clinker", "calcined_clay", "limestone", "gypsum")
REFERENCE_COST_INR_T = {
    "clinker": 2500.0,
    "calcined_clay": 1800.0,
    "limestone": 500.0,
    "gypsum": 1200.0,
}
REFERENCE_CO2_KG_T = {
    "clinker": 850.0,
    "calcined_clay": 250.0,
    "limestone": 30.0,
    "gypsum": 40.0,
}


@dataclass(frozen=True, slots=True)
class _ResolvedSource:
    role: str
    reference: RetrofitReference
    name: str
    component: BlendComponent


@dataclass(frozen=True, slots=True)
class _QuickMetrics:
    vector: tuple[float, float, float, float]
    chemistry: Chemistry
    chemistry_complete: bool
    unknown_fields: tuple[str, ...]
    predicted_output_tph: float | None
    bottleneck: str | None
    route_compatibility_score: float
    route_efficiency_score: float
    electricity_kwh_t: float
    thermal_kcal_kg: float
    material_cost_inr_t: float
    energy_cost_inr_t: float
    total_variable_cost_inr_t: float
    material_co2_kg_t: float
    missing_assets: tuple[RetrofitAssetGap, ...]
    retrofit_complexity_score: float
    warnings: tuple[str, ...]


class PpcToLc3Designer:
    """Deterministic PPC-to-LC3 retrofit designer.

    The solver intentionally does not enumerate the full combination space.
    It first prunes infeasible percentage vectors, then runs bounded pairwise
    coordinate descent from several engineering seeds and objective profiles,
    and finally applies Pareto filtering and robustness stress tests.
    """

    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def design(self, request: PpcToLc3RetrofitRequest) -> RetrofitStudyResult:
        ppc = self._require("blends", request.existing_ppc_blend_id, Blend)
        route = self._require("routes", request.route_id, Route)
        if ppc.blend_class != "finished_cement":
            raise ValueError("PPC-to-LC3 design requires a finished-cement baseline blend")

        sources = self._resolve_sources(ppc, request)
        bounds = (
            request.clinker_bounds,
            request.calcined_clay_bounds,
            request.limestone_bounds,
            request.gypsum_bounds,
        )
        cost_book = (
            self._require("cost_books", request.cost_book_id, CostBook)
            if request.cost_book_id
            else None
        )

        baseline = self._baseline(ppc, route, request, cost_book)
        quick_cache: dict[tuple[float, float, float, float], _QuickMetrics] = {}

        def quick(vector: tuple[float, float, float, float]) -> _QuickMetrics:
            key = tuple(round(value, 4) for value in vector)
            if key not in quick_cache:
                quick_cache[key] = self._quick_evaluate(
                    key, sources, route, request, cost_book
                )
            return quick_cache[key]

        seeds = self._engineering_seeds(bounds)
        profiles = self._objective_profiles(request.objective_weights)
        vectors: set[tuple[float, float, float, float]] = set(seeds)
        for seed, weights in zip(seeds * 2, profiles, strict=False):
            optimum = self._coordinate_descent(seed, bounds, weights, request, quick)
            vectors.add(optimum)
            vectors.update(self._local_neighbours(optimum, bounds, step=1.0))

        # Always include the familiar LC3-50 reference anchor if it fits.
        reference_anchor = self._project_to_bounds((50.0, 30.0, 15.0, 5.0), bounds)
        vectors.add(reference_anchor)
        vectors = {
            vector
            for vector in vectors
            if self._clay_limestone_ratio_is_valid(vector, request)
        }
        if not vectors:
            raise ValueError(
                "No LC3 candidate satisfies the clay-to-limestone ratio and percentage bounds"
            )

        full_candidates = [
            self._full_candidate(vector, sources, route, request, cost_book, quick(vector))
            for vector in sorted(vectors)
        ]
        full_candidates = self._deduplicate_candidates(full_candidates)
        for candidate in full_candidates:
            candidate.output_delta_vs_ppc_tph = (
                candidate.predicted_output_tph - baseline.predicted_output_tph
                if candidate.predicted_output_tph is not None
                and baseline.predicted_output_tph is not None
                else None
            )
            candidate.electricity_delta_vs_ppc_kwh_t = (
                candidate.electricity_kwh_t - baseline.electricity_kwh_t
                if candidate.electricity_kwh_t is not None
                and baseline.electricity_kwh_t is not None
                else None
            )
            candidate.thermal_delta_vs_ppc_kcal_kg = (
                candidate.thermal_kcal_kg - baseline.thermal_kcal_kg
                if candidate.thermal_kcal_kg is not None
                and baseline.thermal_kcal_kg is not None
                else None
            )
            candidate.material_cost_delta_vs_ppc_inr_t = (
                candidate.material_cost_inr_t - baseline.material_cost_inr_t
                if candidate.material_cost_inr_t is not None
                and baseline.material_cost_inr_t is not None
                else None
            )
            candidate.material_co2_delta_vs_ppc_kg_t = (
                candidate.material_co2_kg_t - baseline.material_co2_kg_t
                if candidate.material_co2_kg_t is not None
                and baseline.material_co2_kg_t is not None
                else None
            )
        self._mark_pareto(full_candidates)
        full_candidates.sort(
            key=lambda item: (
                not item.pareto_efficient,
                -item.deterministic_score,
                item.total_variable_cost_inr_t if item.total_variable_cost_inr_t is not None else 1e12,
                item.clinker_factor_percent,
            )
        )
        selected = full_candidates[0] if full_candidates else None
        for index, candidate in enumerate(full_candidates, 1):
            candidate.rank = index

        assumptions = self._assumptions(request, cost_book)
        data_to_replace = self._data_to_replace(sources, route, cost_book, request)
        warnings: list[str] = []
        if not any(item.pareto_efficient for item in full_candidates):
            warnings.append("No Pareto-efficient candidate survived deterministic feasibility screening")
        if request.clay_supply_mode == "onsite_calcination":
            warnings.append(
                "Onsite-calcination results use a reference clay-calciner model until plant/vendor data replace it"
            )

        study = RetrofitStudyResult(
            study_id=new_id("retrofit"),
            created_at=now(),
            request=request,
            baseline=baseline,
            selected_candidate_id=selected.candidate_id if selected else None,
            candidates=full_candidates[: request.target_candidates],
            assumptions=assumptions,
            data_to_replace=data_to_replace,
            warnings=warnings,
        )
        self.repository.save("retrofit_studies", study)
        return study

    def _require(self, table: str, entity_id: str | None, model: type):
        if not entity_id:
            raise ValueError(f"Missing {table[:-1]} reference")
        item = self.repository.get(table, entity_id)
        if not isinstance(item, model):
            raise ValueError(f"Unknown {table[:-1]} {entity_id}")
        return item

    def _resolve_reference(self, role: str, reference: RetrofitReference) -> _ResolvedSource:
        if reference.component_type == "material":
            material = self._require("materials", reference.reference_id, Material)
            return _ResolvedSource(
                role=role,
                reference=reference,
                name=material.name,
                component=BlendComponent(material_id=material.material_id, percentage=25),
            )
        blend = self._require("blends", reference.reference_id, Blend)
        return _ResolvedSource(
            role=role,
            reference=reference,
            name=blend.name,
            component=BlendComponent(
                component_type="blend", blend_id=blend.blend_id, percentage=25
            ),
        )

    def _resolve_sources(
        self, ppc: Blend, request: PpcToLc3RetrofitRequest
    ) -> dict[str, _ResolvedSource]:
        inferred: dict[str, RetrofitReference] = {}
        for component in ppc.components:
            if component.component_type == "material":
                material = self.repository.get("materials", component.material_id or "")
                if not isinstance(material, Material):
                    continue
                if material.functional_role == "clinker" and "clinker" not in inferred:
                    inferred["clinker"] = RetrofitReference(
                        component_type="material", reference_id=material.material_id
                    )
                if material.functional_role == "set_regulator" and "gypsum" not in inferred:
                    inferred["gypsum"] = RetrofitReference(
                        component_type="material", reference_id=material.material_id
                    )
            else:
                child = self.repository.get("blends", component.blend_id or "")
                if isinstance(child, Blend) and child.blend_class in {"clinker_blend", "raw_meal"}:
                    inferred.setdefault(
                        "clinker",
                        RetrofitReference(component_type="blend", reference_id=child.blend_id),
                    )

        def first_material(predicate) -> RetrofitReference | None:
            for item in self.repository.list("materials"):
                if isinstance(item, Material) and not item.archived and predicate(item):
                    return RetrofitReference(component_type="material", reference_id=item.material_id)
            return None

        references = {
            "clinker": request.clinker_source or inferred.get("clinker") or first_material(
                lambda item: item.functional_role == "clinker" or item.material_type == "clinker"
            ),
            "calcined_clay": request.calcined_clay_source or first_material(
                lambda item: item.material_type in {"calcined_clay", "metakaolin"}
            ),
            "limestone": request.limestone_source or first_material(
                lambda item: item.material_type == "limestone"
                and item.functional_role == "cement_addition"
            ) or first_material(lambda item: item.material_type == "limestone"),
            "gypsum": request.gypsum_source or inferred.get("gypsum") or first_material(
                lambda item: item.functional_role == "set_regulator"
                or item.material_type == "gypsum"
            ),
        }
        missing = [role for role, value in references.items() if value is None]
        if missing:
            raise ValueError(
                "Cannot construct LC3 formulation; missing source for " + ", ".join(missing)
            )
        return {
            role: self._resolve_reference(role, reference)
            for role, reference in references.items()
            if reference is not None
        }

    def _bounds_tuple(
        self, request: PpcToLc3RetrofitRequest
    ) -> tuple[PercentageBounds, PercentageBounds, PercentageBounds, PercentageBounds]:
        return (
            request.clinker_bounds,
            request.calcined_clay_bounds,
            request.limestone_bounds,
            request.gypsum_bounds,
        )

    def _project_to_bounds(
        self,
        vector: tuple[float, float, float, float],
        bounds: tuple[PercentageBounds, PercentageBounds, PercentageBounds, PercentageBounds],
    ) -> tuple[float, float, float, float]:
        values = [
            min(max(value, bound.minimum_percent), bound.maximum_percent)
            for value, bound in zip(vector, bounds, strict=True)
        ]
        difference = 100.0 - sum(values)
        if difference > 0:
            for index, bound in sorted(
                enumerate(bounds),
                key=lambda item: item[1].maximum_percent - values[item[0]],
                reverse=True,
            ):
                addition = min(difference, bound.maximum_percent - values[index])
                values[index] += addition
                difference -= addition
                if difference <= 1e-9:
                    break
        elif difference < 0:
            remaining = -difference
            for index, bound in sorted(
                enumerate(bounds),
                key=lambda item: values[item[0]] - item[1].minimum_percent,
                reverse=True,
            ):
                reduction = min(remaining, values[index] - bound.minimum_percent)
                values[index] -= reduction
                remaining -= reduction
                if remaining <= 1e-9:
                    break
        if abs(sum(values) - 100.0) > 1e-6:
            raise ValueError("LC3 percentage bounds do not admit a 100% formulation")
        rounded = [round(value, 4) for value in values]
        rounded[-1] = round(rounded[-1] + 100.0 - sum(rounded), 4)
        return tuple(rounded)  # type: ignore[return-value]

    def _engineering_seeds(
        self,
        bounds: tuple[PercentageBounds, PercentageBounds, PercentageBounds, PercentageBounds],
    ) -> list[tuple[float, float, float, float]]:
        midpoint = tuple((item.minimum_percent + item.maximum_percent) / 2 for item in bounds)
        low_clinker = (
            bounds[0].minimum_percent,
            bounds[1].maximum_percent,
            bounds[2].maximum_percent,
            (bounds[3].minimum_percent + bounds[3].maximum_percent) / 2,
        )
        high_output = (
            bounds[0].maximum_percent,
            bounds[1].minimum_percent,
            (bounds[2].minimum_percent + bounds[2].maximum_percent) / 2,
            (bounds[3].minimum_percent + bounds[3].maximum_percent) / 2,
        )
        high_clay = (
            (bounds[0].minimum_percent + bounds[0].maximum_percent) / 2,
            bounds[1].maximum_percent,
            bounds[2].minimum_percent,
            bounds[3].minimum_percent,
        )
        anchors = [midpoint, low_clinker, high_output, high_clay, (50, 30, 15, 5)]
        unique: list[tuple[float, float, float, float]] = []
        for item in anchors:
            projected = self._project_to_bounds(item, bounds)
            if projected not in unique:
                unique.append(projected)
        return unique

    def _objective_profiles(
        self, requested: RetrofitObjectiveWeights
    ) -> list[RetrofitObjectiveWeights]:
        return [
            requested,
            RetrofitObjectiveWeights(cost=3, co2=0.5, output=1, electricity=1, thermal=0.7, robustness=0.8, retrofit_complexity=1, clinker_factor=0.5),
            RetrofitObjectiveWeights(cost=0.5, co2=3, output=1, electricity=0.7, thermal=1, robustness=1, retrofit_complexity=0.8, clinker_factor=2),
            RetrofitObjectiveWeights(cost=0.5, co2=0.5, output=4, electricity=0.5, thermal=0.5, robustness=1, retrofit_complexity=0.5, clinker_factor=0.2),
            RetrofitObjectiveWeights(cost=0.8, co2=0.8, output=1, electricity=2, thermal=2, robustness=1, retrofit_complexity=0.8, clinker_factor=0.5),
            RetrofitObjectiveWeights(cost=0.5, co2=0.5, output=1, electricity=0.5, thermal=0.5, robustness=4, retrofit_complexity=1, clinker_factor=0.5),
        ]

    def _coordinate_descent(
        self,
        seed: tuple[float, float, float, float],
        bounds: tuple[PercentageBounds, PercentageBounds, PercentageBounds, PercentageBounds],
        weights: RetrofitObjectiveWeights,
        request: PpcToLc3RetrofitRequest,
        evaluator,
    ) -> tuple[float, float, float, float]:
        current = seed
        current_value = self._scalar_objective(evaluator(current), weights, request)
        for step in (5.0, 2.0, 1.0, 0.5):
            for _ in range(20):
                best = current
                best_value = current_value
                for receiver in range(4):
                    for donor in range(4):
                        if receiver == donor:
                            continue
                        trial = list(current)
                        trial[receiver] += step
                        trial[donor] -= step
                        if trial[receiver] > bounds[receiver].maximum_percent + 1e-9:
                            continue
                        if trial[donor] < bounds[donor].minimum_percent - 1e-9:
                            continue
                        candidate = tuple(round(value, 4) for value in trial)
                        value = self._scalar_objective(evaluator(candidate), weights, request)
                        if value < best_value - 1e-10:
                            best = candidate  # type: ignore[assignment]
                            best_value = value
                if best == current:
                    break
                current, current_value = best, best_value
        return current

    def _local_neighbours(
        self,
        vector: tuple[float, float, float, float],
        bounds: tuple[PercentageBounds, PercentageBounds, PercentageBounds, PercentageBounds],
        step: float,
    ) -> set[tuple[float, float, float, float]]:
        neighbours: set[tuple[float, float, float, float]] = set()
        for receiver in range(4):
            for donor in range(4):
                if receiver == donor:
                    continue
                trial = list(vector)
                trial[receiver] += step
                trial[donor] -= step
                if (
                    trial[receiver] <= bounds[receiver].maximum_percent + 1e-9
                    and trial[donor] >= bounds[donor].minimum_percent - 1e-9
                ):
                    neighbours.add(tuple(round(value, 4) for value in trial))
        return neighbours

    def _temporary_blend(
        self,
        vector: tuple[float, float, float, float],
        sources: dict[str, _ResolvedSource],
        name: str = "LC3 retrofit candidate",
    ) -> Blend:
        components: list[BlendComponent] = []
        for role, percentage in zip(ROLES, vector, strict=True):
            source = sources[role]
            payload = source.component.model_copy(update={"percentage": percentage})
            components.append(payload)
        return Blend(
            blend_id=f"temporary_{abs(hash(vector))}",
            created_at=now(),
            name=name,
            blend_class="finished_cement",
            family="LC3",
            objective="PPC-to-LC3 deterministic retrofit design",
            applicable_standard="Reference LC3 screening; plant validation required",
            components=components,
        )

    def _route_stages(self, route: Route) -> tuple[set[str], list[str]]:
        stages: set[str] = set()
        names: list[str] = []
        for node in route.nodes:
            machine = self.repository.get("machines", node.machine_id)
            if hasattr(machine, "process_stage"):
                stages.add(str(getattr(machine, "process_stage")))
                names.append(str(getattr(machine, "name", node.label)).lower())
        return stages, names

    def _asset_gaps(
        self, route: Route, request: PpcToLc3RetrofitRequest
    ) -> tuple[RetrofitAssetGap, ...]:
        stages, names = self._route_stages(route)
        gaps: list[RetrofitAssetGap] = []
        if request.clay_supply_mode == "onsite_calcination" and "clay_calcination" not in stages:
            gaps.append(
                RetrofitAssetGap(
                    asset_code="CLAY_CALCINER",
                    asset_name="Clay calcination line",
                    requirement="required",
                    reason="Raw kaolinitic clay must be thermally activated before cement blending",
                    reference_capacity_tph=request.reference_clay_calciner_capacity_tph,
                    reference_capex_inr_crore=35.0,
                )
            )
        if not any("clay" in name and "silo" in name for name in names):
            gaps.append(
                RetrofitAssetGap(
                    asset_code="CALCINED_CLAY_STORAGE",
                    asset_name="Calcined-clay storage and extraction",
                    requirement="recommended",
                    reason="Independent storage prevents moisture pickup and enables controlled LC3 campaigns",
                    reference_capacity_tph=None,
                    reference_capex_inr_crore=8.0,
                )
            )
        if not any("dose" in name or "feeder" in name for name in names):
            gaps.append(
                RetrofitAssetGap(
                    asset_code="LC3_DOSING",
                    asset_name="Independent clay/limestone/gypsum dosing",
                    requirement="recommended",
                    reason="LC3 formulation requires controlled component proportions before finish grinding",
                    reference_capex_inr_crore=4.0,
                )
            )
        if "cement_grinding" not in stages:
            gaps.append(
                RetrofitAssetGap(
                    asset_code="CEMENT_GRINDING",
                    asset_name="Cement grinding line",
                    requirement="required",
                    reason="The selected route has no finish-grinding stage",
                )
            )
        return tuple(gaps)

    def _reference_cost(
        self,
        role: str,
        material: Material,
        cost_book: CostBook | None,
        production_stream: str,
    ) -> tuple[float, str]:
        if cost_book is not None:
            entry = next(
                (item for item in cost_book.material_costs if item.material_id == material.material_id),
                None,
            )
            if entry is not None:
                if production_stream in {"clinker", "clinker_raw_feed"} and entry.internal_feed_cost_inr_t is not None:
                    return entry.internal_feed_cost_inr_t, "cost-book internal feed"
                if entry.purchased_delivered_cost_inr_t is not None:
                    return entry.purchased_delivered_cost_inr_t, "cost-book purchased delivered"
        if material.cost_inr_per_t is not None:
            return material.cost_inr_per_t, "material record"
        return REFERENCE_COST_INR_T[role], "BRIXTA reference placeholder"

    def _material_cost_co2(
        self,
        blend: Blend,
        cost_book: CostBook | None,
        role_by_root: dict[str | None, str],
    ) -> tuple[float, float, list[str]]:
        preview = preview_blend(self.repository, blend, root_id=blend.blend_id)
        cost = 0.0
        co2 = 0.0
        warnings: list[str] = []
        for item in preview.flattened_components:
            material = self._require("materials", item.material_id, Material)
            role = role_by_root.get(item.root_component_id, "limestone")
            unit_cost, cost_basis = self._reference_cost(
                role, material, cost_book, item.production_stream
            )
            unit_co2 = material.co2_kg_per_t
            if unit_co2 is None:
                unit_co2 = REFERENCE_CO2_KG_T[role]
                warnings.append(
                    f"{material.name}: material CO2 missing; {unit_co2:.0f} kg/t reference placeholder used"
                )
            if cost_basis == "BRIXTA reference placeholder":
                warnings.append(
                    f"{material.name}: cost missing; ₹{unit_cost:.0f}/t reference placeholder used"
                )
            fraction = item.percentage / 100.0
            cost += unit_cost * fraction
            co2 += unit_co2 * fraction
        return cost, co2, warnings

    def _quick_evaluate(
        self,
        vector: tuple[float, float, float, float],
        sources: dict[str, _ResolvedSource],
        route: Route,
        request: PpcToLc3RetrofitRequest,
        cost_book: CostBook | None,
    ) -> _QuickMetrics:
        if abs(sum(vector) - 100.0) > 1e-5:
            raise ValueError("Candidate formulation does not total 100%")
        blend = self._temporary_blend(vector, sources)
        preview = preview_blend(self.repository, blend, root_id=blend.blend_id)
        analysis = analyse_route(
            self.repository, blend, route, request.target_output_tph
        )
        gaps = self._asset_gaps(route, request)
        predicted = analysis.predicted_output_tph
        electricity = float(analysis.electricity_kwh_t_output or 0.0)
        thermal = float(analysis.thermal_kcal_kg_output or 0.0)
        clay_fraction = vector[1] / 100.0
        if request.clay_supply_mode == "onsite_calcination":
            stages, _ = self._route_stages(route)
            if "clay_calcination" not in stages and clay_fraction > 0:
                virtual_capacity = request.reference_clay_calciner_capacity_tph / clay_fraction
                predicted = min(predicted, virtual_capacity) if predicted is not None else virtual_capacity
                electricity += clay_fraction * request.reference_clay_calciner_electricity_kwh_t
                thermal += clay_fraction * request.reference_clay_calciner_thermal_kcal_kg

        role_by_root = {
            sources[role].reference.reference_id: role for role in ROLES
        }
        material_cost, material_co2, data_warnings = self._material_cost_co2(
            blend, cost_book, role_by_root
        )
        electricity_tariff = (
            cost_book.electricity_inr_kwh
            if cost_book and cost_book.electricity_inr_kwh is not None
            else 8.5
        )
        thermal_tariff = (
            cost_book.thermal_fuel_inr_mkcal
            if cost_book and cost_book.thermal_fuel_inr_mkcal is not None
            else 900.0
        )
        energy_cost = electricity * electricity_tariff + thermal * thermal_tariff / 1000.0
        complexity = min(
            100.0,
            sum(28 if item.requirement == "required" else 12 for item in gaps),
        )
        return _QuickMetrics(
            vector=vector,
            chemistry=preview.chemistry,
            chemistry_complete=preview.chemistry_complete,
            unknown_fields=tuple(preview.unknown_chemistry_fields),
            predicted_output_tph=predicted,
            bottleneck=analysis.bottleneck_machine_name,
            route_compatibility_score=analysis.compatibility_score,
            route_efficiency_score=analysis.efficiency_score,
            electricity_kwh_t=electricity,
            thermal_kcal_kg=thermal,
            material_cost_inr_t=material_cost,
            energy_cost_inr_t=energy_cost,
            total_variable_cost_inr_t=material_cost + energy_cost,
            material_co2_kg_t=material_co2,
            missing_assets=gaps,
            retrofit_complexity_score=complexity,
            warnings=tuple(preview.warnings + data_warnings + analysis.reasons),
        )

    def _clay_limestone_ratio_is_valid(
        self,
        vector: tuple[float, float, float, float],
        request: PpcToLc3RetrofitRequest,
    ) -> bool:
        limestone = vector[2]
        if limestone <= 0:
            return False
        ratio = vector[1] / limestone
        return (
            request.clay_to_limestone_ratio_min - 1e-9
            <= ratio
            <= request.clay_to_limestone_ratio_max + 1e-9
        )

    def _scalar_objective(
        self,
        metrics: _QuickMetrics,
        weights: RetrofitObjectiveWeights,
        request: PpcToLc3RetrofitRequest,
    ) -> float:
        predicted = metrics.predicted_output_tph or 0.0
        shortfall = max(0.0, request.target_output_tph - predicted) / request.target_output_tph
        unknown_penalty = len(metrics.unknown_fields) / 9.0
        vector = metrics.vector
        ratio_penalty = 0.0
        if vector[2] <= 0:
            ratio_penalty = 10.0
        else:
            ratio = vector[1] / vector[2]
            ratio_penalty = (
                max(0.0, request.clay_to_limestone_ratio_min - ratio)
                + max(0.0, ratio - request.clay_to_limestone_ratio_max)
            ) * 20.0
        reactivity_penalty = max(0.0, 0.60 - request.calcined_clay_reactivity_index) * 2.0
        kaolinite_penalty = max(0.0, 40.0 - request.clay_kaolinite_percent) / 40.0
        robustness_proxy = min(
            1.0,
            unknown_penalty
            + metrics.retrofit_complexity_score / 200.0
            + reactivity_penalty
            + kaolinite_penalty,
        )
        return (
            weights.cost * metrics.total_variable_cost_inr_t / 5000.0
            + weights.co2 * metrics.material_co2_kg_t / 1000.0
            + weights.output * shortfall * 4.0
            + weights.electricity * metrics.electricity_kwh_t / 100.0
            + weights.thermal * metrics.thermal_kcal_kg / 1000.0
            + weights.robustness * robustness_proxy
            + weights.retrofit_complexity * metrics.retrofit_complexity_score / 100.0
            + weights.clinker_factor * vector[0] / 100.0
            + ratio_penalty
        )

    def _stress_vectors(
        self,
        vector: tuple[float, float, float, float],
        bounds: tuple[PercentageBounds, PercentageBounds, PercentageBounds, PercentageBounds],
    ) -> list[tuple[str, str, tuple[float, float, float, float]]]:
        results: list[tuple[str, str, tuple[float, float, float, float]]] = [
            ("low_chemistry", "low", vector),
            ("typical", "typical", vector),
            ("high_chemistry", "high", vector),
        ]
        for label, delta in (("clay_minus_2pct", -2.0), ("clay_plus_2pct", 2.0)):
            trial = list(vector)
            trial[1] += delta
            trial[0] -= delta
            if (
                bounds[1].minimum_percent <= trial[1] <= bounds[1].maximum_percent
                and bounds[0].minimum_percent <= trial[0] <= bounds[0].maximum_percent
            ):
                results.append((label, "typical", tuple(trial)))
        return results

    def _stress_test(
        self,
        vector: tuple[float, float, float, float],
        sources: dict[str, _ResolvedSource],
        route: Route,
        request: PpcToLc3RetrofitRequest,
        cost_book: CostBook | None,
    ) -> tuple[list[RetrofitStressScenario], float]:
        bounds = self._bounds_tuple(request)
        scenarios: list[RetrofitStressScenario] = []
        chemistry_vectors: list[list[float]] = []
        output_penalty = 0.0
        unknown_penalty = 0.0
        for label, chemistry_scenario, scenario_vector in self._stress_vectors(vector, bounds):
            blend = self._temporary_blend(scenario_vector, sources, name=f"LC3 stress {label}")
            preview = preview_blend(
                self.repository,
                blend,
                root_id=blend.blend_id,
                chemistry_scenario=chemistry_scenario,
            )
            metrics = self._quick_evaluate(
                scenario_vector, sources, route, request, cost_book
            )
            predicted = metrics.predicted_output_tph
            shortfall = max(0.0, request.target_output_tph - (predicted or 0.0))
            output_penalty += shortfall / request.target_output_tph
            unknown_penalty += len(preview.unknown_chemistry_fields) / 9.0
            available = [
                value
                for value in preview.chemistry.model_dump().values()
                if value is not None
            ]
            if available:
                chemistry_vectors.append([float(value) for value in available])
            scenarios.append(
                RetrofitStressScenario(
                    scenario=label,
                    chemistry_scenario=chemistry_scenario,
                    clinker_percent=scenario_vector[0],
                    calcined_clay_percent=scenario_vector[1],
                    limestone_percent=scenario_vector[2],
                    gypsum_percent=scenario_vector[3],
                    predicted_output_tph=predicted,
                    electricity_kwh_t=metrics.electricity_kwh_t,
                    thermal_kcal_kg=metrics.thermal_kcal_kg,
                    material_cost_inr_t=metrics.material_cost_inr_t,
                    total_variable_cost_inr_t=metrics.total_variable_cost_inr_t,
                    material_co2_kg_t=metrics.material_co2_kg_t,
                    chemistry_complete=preview.chemistry_complete,
                    unknown_chemistry_fields=preview.unknown_chemistry_fields,
                    feasible=predicted is not None and predicted > 0,
                    notes=preview.warnings[:6],
                )
            )
        spread_penalty = 0.0
        if len(chemistry_vectors) >= 2:
            lengths = [len(item) for item in chemistry_vectors]
            common = min(lengths)
            if common:
                for column in range(common):
                    values = [row[column] for row in chemistry_vectors]
                    mean = sum(values) / len(values)
                    if abs(mean) > 1e-9:
                        spread_penalty += (max(values) - min(values)) / abs(mean)
                spread_penalty /= common
        count = max(1, len(scenarios))
        robustness = 100.0 - 45.0 * output_penalty / count - 25.0 * unknown_penalty / count - 30.0 * min(1.0, spread_penalty)
        return scenarios, max(0.0, min(100.0, robustness))

    def _formulation_chain(
        self,
        vector: tuple[float, float, float, float],
        sources: dict[str, _ResolvedSource],
        request: PpcToLc3RetrofitRequest,
        metrics: _QuickMetrics,
    ) -> list[FormulationStageResult]:
        clinker, clay, limestone, gypsum = vector
        raw_clay_feed = (
            clay / request.raw_clay_to_calcined_yield
            if request.clay_supply_mode == "onsite_calcination"
            else 0.0
        )
        return [
            FormulationStageResult(
                level="quarry_stockpile",
                name="Raw-material and stockpile basis",
                purpose="Provide chemically controlled feedstocks to the existing clinker line and LC3 additions",
                inputs=[sources["clinker"].name, sources["limestone"].name],
                outputs=["Clinker-feed source", "Cement-grade limestone addition"],
                assumptions=["Existing quarry/raw-meal system is inherited from the PPC plant unless separately redesigned"],
            ),
            FormulationStageResult(
                level="raw_meal",
                name="Existing clinker raw-meal formulation",
                purpose="Produce the clinker constituent used by the LC3 cement",
                inputs=[sources["clinker"].name],
                outputs=[f"{clinker:.2f} t clinker per 100 t LC3"],
                assumptions=["Raw-meal recipe and clinker yield remain linked to the selected clinker source"],
            ),
            FormulationStageResult(
                level="kiln_feed",
                name="Kiln-feed and fuel-ash basis",
                purpose="Carry raw meal, process returns and fuel ash into clinker production",
                inputs=["Existing kiln-feed formulation"],
                outputs=["Clinker chemistry supplied to the LC3 formulation"],
                assumptions=["Kiln dust, bypass dust and fuel-ash corrections require plant calibration"],
            ),
            FormulationStageResult(
                level="clinker",
                name="Clinker constituent",
                purpose="Supply hydraulic Portland-clinker phases to the LC3 system",
                inputs=[sources["clinker"].name],
                outputs=[f"Clinker factor {clinker:.2f}%"],
                key_results={"clinker_percent": clinker},
            ),
            FormulationStageResult(
                level="finished_cement",
                name="LC3 finished-cement formulation",
                purpose="Blend clinker, calcined clay, limestone and gypsum for finish grinding",
                inputs=[source.name for source in sources.values()],
                outputs=["LC3 cement"],
                key_results={
                    "clinker_percent": clinker,
                    "calcined_clay_percent": clay,
                    "limestone_percent": limestone,
                    "gypsum_percent": gypsum,
                },
            ),
            FormulationStageResult(
                level="fuel",
                name="Thermal-energy formulation",
                purpose="Supply clinker burning and, where selected, clay calcination",
                inputs=["Existing kiln fuel mix", "Reference clay-calciner fuel duty"],
                outputs=[f"{metrics.thermal_kcal_kg:.1f} kcal/kg LC3 reference thermal demand"],
                key_results={
                    "thermal_kcal_kg_lc3": metrics.thermal_kcal_kg,
                    "raw_clay_feed_t_per_100t_lc3": raw_clay_feed,
                },
            ),
            FormulationStageResult(
                level="electrical_energy",
                name="Electrical-energy formulation",
                purpose="Supply grinding, conveying, calcination auxiliaries and packing",
                inputs=["Grid/captive/WHR/renewable mix — plant editable"],
                outputs=[f"{metrics.electricity_kwh_t:.2f} kWh/t LC3 reference demand"],
                key_results={"electricity_kwh_t_lc3": metrics.electricity_kwh_t},
            ),
        ]

    def _full_candidate(
        self,
        vector: tuple[float, float, float, float],
        sources: dict[str, _ResolvedSource],
        route: Route,
        request: PpcToLc3RetrofitRequest,
        cost_book: CostBook | None,
        quick: _QuickMetrics,
    ) -> RetrofitCandidate:
        stress_tests, robustness = self._stress_test(
            vector, sources, route, request, cost_book
        )
        score_penalty = self._scalar_objective(
            quick, request.objective_weights, request
        ) + (100.0 - robustness) / 100.0
        deterministic_score = 100.0 / (1.0 + score_penalty)
        components = []
        bounds = self._bounds_tuple(request)
        for role, percentage, bound in zip(ROLES, vector, bounds, strict=True):
            source = sources[role]
            components.append(
                RetrofitComponentShare(
                    role=role,  # type: ignore[arg-type]
                    component_type=source.reference.component_type,
                    reference_id=source.reference.reference_id,
                    name=source.name,
                    percentage=percentage,
                    minimum_percent=bound.minimum_percent,
                    maximum_percent=bound.maximum_percent,
                    source_status="existing plant source" if role in {"clinker", "gypsum"} else "retrofit source",
                )
            )
        shortfall = max(
            0.0, request.target_output_tph - (quick.predicted_output_tph or 0.0)
        )
        blocking_gaps = [
            item
            for item in quick.missing_assets
            if item.requirement == "required"
            and not (
                request.clay_supply_mode == "onsite_calcination"
                and item.asset_code == "CLAY_CALCINER"
            )
        ]
        feasible = (
            quick.predicted_output_tph is not None
            and quick.predicted_output_tph > 0
            and not blocking_gaps
            and self._clay_limestone_ratio_is_valid(vector, request)
        )
        trace = [
            CalculationTraceStep(
                sequence=1,
                section="pruning",
                operation="percentage feasibility",
                formula="SUM(component %) = 100 and min_i <= x_i <= max_i",
                inputs={role: value for role, value in zip(ROLES, vector, strict=True)},
                result=sum(vector),
                unit="%",
            ),
            CalculationTraceStep(
                sequence=2,
                section="route",
                operation="capacity screening",
                formula="min(equipment effective capacity / stage factor)",
                inputs={"target_output_tph": request.target_output_tph},
                result=quick.predicted_output_tph,
                unit="t/h LC3",
            ),
            CalculationTraceStep(
                sequence=3,
                section="cost",
                operation="variable cost",
                formula="material cost + electricity*kWh tariff + thermal*kcal tariff/1000",
                inputs={
                    "materials": quick.material_cost_inr_t,
                    "energy": quick.energy_cost_inr_t,
                },
                result=quick.total_variable_cost_inr_t,
                unit="INR/t LC3",
            ),
            CalculationTraceStep(
                sequence=4,
                section="robustness",
                operation="stress score",
                formula="100 - output shortfall - chemistry gaps - low/high spread penalties",
                inputs={"stress_scenarios": len(stress_tests)},
                result=robustness,
                unit="0-100",
            ),
        ]
        return RetrofitCandidate(
            candidate_id=new_id("lc3cand"),
            name=f"LC3 {vector[0]:.1f}/{vector[1]:.1f}/{vector[2]:.1f}/{vector[3]:.1f}",
            components=components,
            feasible=feasible,
            deterministic_score=round(deterministic_score, 4),
            predicted_output_tph=quick.predicted_output_tph,
            output_shortfall_tph=round(shortfall, 4),
            bottleneck_machine_name=quick.bottleneck,
            route_compatibility_score=quick.route_compatibility_score,
            route_efficiency_score=quick.route_efficiency_score,
            electricity_kwh_t=round(quick.electricity_kwh_t, 4),
            thermal_kcal_kg=round(quick.thermal_kcal_kg, 4),
            material_cost_inr_t=round(quick.material_cost_inr_t, 4),
            energy_cost_inr_t=round(quick.energy_cost_inr_t, 4),
            total_variable_cost_inr_t=round(quick.total_variable_cost_inr_t, 4),
            material_co2_kg_t=round(quick.material_co2_kg_t, 4),
            clinker_factor_percent=vector[0],
            robustness_score=round(robustness, 2),
            retrofit_complexity_score=quick.retrofit_complexity_score,
            chemistry=quick.chemistry,
            chemistry_complete=quick.chemistry_complete,
            unknown_chemistry_fields=list(quick.unknown_fields),
            missing_assets=list(quick.missing_assets),
            stress_tests=stress_tests,
            formulation_chain=self._formulation_chain(vector, sources, request, quick),
            warnings=list(dict.fromkeys(quick.warnings))[:20],
            calculation_trace=trace,
        )

    def _deduplicate_candidates(
        self, candidates: Iterable[RetrofitCandidate]
    ) -> list[RetrofitCandidate]:
        seen: set[tuple[float, float, float, float]] = set()
        result: list[RetrofitCandidate] = []
        for candidate in candidates:
            vector = tuple(item.percentage for item in candidate.components)
            if vector not in seen:
                seen.add(vector)  # type: ignore[arg-type]
                result.append(candidate)
        return result

    def _dominates(self, left: RetrofitCandidate, right: RetrofitCandidate) -> bool:
        left_values = (
            -(left.total_variable_cost_inr_t or 1e12),
            -(left.material_co2_kg_t or 1e12),
            left.predicted_output_tph or 0.0,
            -(left.electricity_kwh_t or 1e12),
            -(left.thermal_kcal_kg or 1e12),
            left.robustness_score,
            -left.retrofit_complexity_score,
        )
        right_values = (
            -(right.total_variable_cost_inr_t or 1e12),
            -(right.material_co2_kg_t or 1e12),
            right.predicted_output_tph or 0.0,
            -(right.electricity_kwh_t or 1e12),
            -(right.thermal_kcal_kg or 1e12),
            right.robustness_score,
            -right.retrofit_complexity_score,
        )
        return all(a >= b - 1e-9 for a, b in zip(left_values, right_values, strict=True)) and any(
            a > b + 1e-9 for a, b in zip(left_values, right_values, strict=True)
        )

    def _mark_pareto(self, candidates: list[RetrofitCandidate]) -> None:
        for candidate in candidates:
            candidate.pareto_efficient = candidate.feasible and not any(
                other.candidate_id != candidate.candidate_id
                and other.feasible
                and self._dominates(other, candidate)
                for other in candidates
            )

    def _baseline(
        self,
        ppc: Blend,
        route: Route,
        request: PpcToLc3RetrofitRequest,
        cost_book: CostBook | None,
    ) -> RetrofitBaseline:
        preview = preview_blend(self.repository, ppc, root_id=ppc.blend_id)
        analysis = analyse_route(
            self.repository, ppc, route, request.target_output_tph
        )
        # Use the existing preview values for baseline; unlike candidate design,
        # no reference cost substitution is hidden here.
        return RetrofitBaseline(
            blend_id=ppc.blend_id,
            blend_name=ppc.name,
            family=ppc.family,
            route_id=route.route_id,
            route_name=route.name,
            predicted_output_tph=analysis.predicted_output_tph,
            electricity_kwh_t=analysis.electricity_kwh_t_output,
            thermal_kcal_kg=analysis.thermal_kcal_kg_output,
            material_cost_inr_t=preview.material_cost_inr_t,
            material_co2_kg_t=preview.estimated_co2_kg_t,
            warnings=preview.warnings + analysis.reasons,
        )

    def _assumptions(
        self, request: PpcToLc3RetrofitRequest, cost_book: CostBook | None
    ) -> list[AssumptionRecord]:
        return [
            AssumptionRecord(
                key="solver",
                value="staged deterministic",
                basis="Pruning, coordinate descent, Pareto filtering and robustness stress tests; no AI model",
            ),
            AssumptionRecord(
                key="clay_supply_mode",
                value=request.clay_supply_mode,
                basis="User-selected retrofit pathway",
            ),
            AssumptionRecord(
                key="electricity_tariff",
                value=str(cost_book.electricity_inr_kwh if cost_book and cost_book.electricity_inr_kwh is not None else 8.5),
                basis=(
                    "Selected cost book"
                    if cost_book and cost_book.electricity_inr_kwh is not None
                    else "Reference fallback; replace with plant tariff"
                ),
            ),
            AssumptionRecord(
                key="thermal_tariff",
                value=str(cost_book.thermal_fuel_inr_mkcal if cost_book and cost_book.thermal_fuel_inr_mkcal is not None else 900),
                basis=(
                    "Selected cost book"
                    if cost_book and cost_book.thermal_fuel_inr_mkcal is not None
                    else "Reference fallback; replace with plant tariff"
                ),
            ),
            AssumptionRecord(
                key="clay_to_limestone_ratio",
                value=f"{request.clay_to_limestone_ratio_min:.2f}-{request.clay_to_limestone_ratio_max:.2f}",
                basis="Reference LC3 formulation-screening envelope; plant and performance validation required",
            ),
            AssumptionRecord(
                key="raw_clay_to_calcined_yield",
                value=f"{request.raw_clay_to_calcined_yield:.4f}",
                basis="Editable BRIXTA reference assumption",
            ),
            AssumptionRecord(
                key="calcined_clay_reactivity_index",
                value=f"{request.calcined_clay_reactivity_index:.4f}",
                basis="Screening placeholder; replace with plant/laboratory reactivity evidence",
            ),
            AssumptionRecord(
                key="clay_kaolinite_percent",
                value=f"{request.clay_kaolinite_percent:.2f}%",
                basis="Screening placeholder; replace with mineralogical analysis",
            ),
            AssumptionRecord(
                key="reference_clay_calciner",
                value=(
                    f"{request.reference_clay_calciner_capacity_tph:.1f} t/h, "
                    f"{request.reference_clay_calciner_electricity_kwh_t:.1f} kWh/t, "
                    f"{request.reference_clay_calciner_thermal_kcal_kg:.0f} kcal/kg"
                ),
                basis="Used only when onsite calcination is selected and the route lacks a clay calciner",
            ),
        ]

    def _data_to_replace(
        self,
        sources: dict[str, _ResolvedSource],
        route: Route,
        cost_book: CostBook | None,
        request: PpcToLc3RetrofitRequest,
    ) -> list[str]:
        items = [
            "Actual clinker, calcined-clay, limestone and gypsum delivered/internal costs",
            "Actual material CO2 factors and accounting boundary",
            "Actual cement standard/compliance envelope and laboratory performance targets",
            "Actual cement-mill throughput, separator efficiency, circulating load and power curve",
            "Actual silo capacities, feeder ranges, conveying routes and product-changeover constraints",
            "Actual plant electricity and thermal-fuel tariffs",
            "Actual material chemistry low/typical/high profiles, including SO3 and alkalis",
        ]
        if request.clay_supply_mode == "onsite_calcination":
            items.extend(
                [
                    "Raw-clay kaolinite/mineralogy and activation test results",
                    "Clay-calciner vendor capacity, heat, electricity, residence time and conversion data",
                    "Raw-clay moisture, drying requirement and calcined-clay yield",
                ]
            )
        if cost_book is None:
            items.append("Select or create a plant cost book; workbook currently uses reference tariffs")
        if not route.nodes:
            items.append("Plant route connections and equipment instances")
        for source in sources.values():
            if source.reference.component_type == "material":
                material = self.repository.get("materials", source.reference.reference_id)
                if isinstance(material, Material):
                    if material.cost_inr_per_t is None:
                        items.append(f"{material.name}: actual cost")
                    if material.co2_kg_per_t is None:
                        items.append(f"{material.name}: actual material CO2 factor")
        return list(dict.fromkeys(items))
