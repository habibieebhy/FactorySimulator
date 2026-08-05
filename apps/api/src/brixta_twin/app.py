from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import TypeVar

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from .blending import preview_blend
from .models import (
    Blend,
    BlendCreate,
    BlendPreview,
    CalibrationCreate,
    CalibrationError,
    CalibrationRecord,
    CostBook,
    CostBookCreate,
    Machine,
    MachineCreate,
    Material,
    MaterialCreate,
    RawMixOptimisationRequest,
    RawMixOptimisationResult,
    PpcToLc3RetrofitRequest,
    RetrofitStudyResult,
    SaveRetrofitCandidateRequest,
    Route,
    RouteCreate,
    RouteRecommendationSet,
    RunRequest,
    RunResult,
    new_id,
    now,
)
from .excel_compiler import compile_retrofit_workbook
from .engineering_router import build_engineering_router
from .optimisation import optimise_raw_mix
from .retrofit import PpcToLc3Designer
from .routing import recommend_routes
from .seed import seed
from .simulation import Engine
from .storage import Repository


Entity = TypeVar("Entity", bound=BaseModel)


def create_app(path: str | Path | None = None) -> FastAPI:
    repo = Repository(path)
    seed(repo)
    engine = Engine(repo)
    retrofit_designer = PpcToLc3Designer(repo)
    app = FastAPI(title="BRIXTA Cement Twin API", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(build_engineering_router(repo))

    def active(table: str, include_archived: bool) -> list[BaseModel]:
        items = repo.list(table)
        return items if include_archived else [item for item in items if not getattr(item, "archived", False)]

    def require(table: str, entity_id: str, model: type[Entity]) -> Entity:
        item = repo.get(table, entity_id)
        if not isinstance(item, model):
            raise HTTPException(404, f"Unknown {table[:-1].replace('_', ' ')}")
        return item

    def set_archived(table: str, entity_id: str, model: type[Entity], archived: bool) -> Entity:
        item = require(table, entity_id, model)
        updated = item.model_copy(
            update={"archived": archived, "archived_at": now() if archived else None}
        )
        return repo.save(table, updated)  # type: ignore[return-value]

    def safe_delete(table: str, entity_id: str, model: type[Entity]) -> dict[str, object]:
        require(table, entity_id, model)
        references = repo.references(table, entity_id)
        if references:
            raise HTTPException(
                409,
                {
                    "message": "Record is referenced by immutable history; archive it instead",
                    "references": references,
                },
            )
        repo.delete(table, entity_id)
        return {"deleted": True, "entity_id": entity_id}

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "brixta-cement-twin-api", "version": "1.0.0"}

    @app.get("/api/materials", response_model=list[Material])
    def materials(include_archived: bool = Query(False)) -> list[BaseModel]:
        return active("materials", include_archived)

    @app.post("/api/materials", response_model=Material)
    def add_material(payload: MaterialCreate) -> BaseModel:
        return repo.save(
            "materials",
            Material(**payload.model_dump(), material_id=new_id("mat"), created_at=now()),
        )

    @app.post("/api/materials/{material_id}/versions", response_model=Material)
    def version_material(material_id: str, payload: MaterialCreate) -> BaseModel:
        previous = require("materials", material_id, Material)
        return repo.save(
            "materials",
            Material(
                **payload.model_dump(),
                material_id=new_id("mat"),
                version=previous.version + 1,
                lineage_id=previous.lineage_id or previous.material_id,
                created_at=now(),
            ),
        )

    @app.post("/api/materials/{material_id}/archive", response_model=Material)
    def archive_material(material_id: str) -> Material:
        return set_archived("materials", material_id, Material, True)

    @app.post("/api/materials/{material_id}/restore", response_model=Material)
    def restore_material(material_id: str) -> Material:
        return set_archived("materials", material_id, Material, False)

    @app.delete("/api/materials/{material_id}")
    def delete_material(material_id: str) -> dict[str, object]:
        return safe_delete("materials", material_id, Material)

    @app.get("/api/blends", response_model=list[Blend])
    def blends(include_archived: bool = Query(False)) -> list[BaseModel]:
        return active("blends", include_archived)

    @app.post("/api/blends/preview", response_model=BlendPreview)
    def preview_new_blend(payload: BlendCreate) -> BlendPreview:
        try:
            return preview_blend(repo, payload)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/blends/{blend_id}/preview", response_model=BlendPreview)
    def preview_saved_blend(blend_id: str) -> BlendPreview:
        blend = require("blends", blend_id, Blend)
        try:
            return preview_blend(repo, blend, root_id=blend.blend_id)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    def save_blend(payload: BlendCreate, previous: Blend | None = None) -> BaseModel:
        blend = Blend(
            **payload.model_dump(),
            blend_id=new_id("blend"),
            version=(previous.version + 1 if previous else 1),
            lineage_id=((previous.lineage_id or previous.blend_id) if previous else None),
            created_at=now(),
        )
        try:
            preview_blend(repo, blend, root_id=blend.blend_id)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return repo.save("blends", blend)

    @app.post("/api/blends", response_model=Blend)
    def add_blend(payload: BlendCreate) -> BaseModel:
        return save_blend(payload)

    @app.post("/api/blends/{blend_id}/versions", response_model=Blend)
    def version_blend(blend_id: str, payload: BlendCreate) -> BaseModel:
        return save_blend(payload, require("blends", blend_id, Blend))

    @app.post("/api/blends/{blend_id}/archive", response_model=Blend)
    def archive_blend(blend_id: str) -> Blend:
        return set_archived("blends", blend_id, Blend, True)

    @app.post("/api/blends/{blend_id}/restore", response_model=Blend)
    def restore_blend(blend_id: str) -> Blend:
        return set_archived("blends", blend_id, Blend, False)

    @app.delete("/api/blends/{blend_id}")
    def delete_blend(blend_id: str) -> dict[str, object]:
        return safe_delete("blends", blend_id, Blend)

    @app.get("/api/machines", response_model=list[Machine])
    def machines(include_archived: bool = Query(False)) -> list[BaseModel]:
        return active("machines", include_archived)

    @app.post("/api/machines", response_model=Machine)
    def add_machine(payload: MachineCreate) -> BaseModel:
        return repo.save(
            "machines",
            Machine(**payload.model_dump(), machine_id=new_id("machine"), created_at=now()),
        )

    @app.post("/api/machines/{machine_id}/versions", response_model=Machine)
    def version_machine(machine_id: str, payload: MachineCreate) -> BaseModel:
        previous = require("machines", machine_id, Machine)
        return repo.save(
            "machines",
            Machine(
                **payload.model_dump(),
                machine_id=new_id("machine"),
                version=previous.version + 1,
                lineage_id=previous.lineage_id or previous.machine_id,
                created_at=now(),
            ),
        )

    @app.post("/api/machines/{machine_id}/archive", response_model=Machine)
    def archive_machine(machine_id: str) -> Machine:
        return set_archived("machines", machine_id, Machine, True)

    @app.post("/api/machines/{machine_id}/restore", response_model=Machine)
    def restore_machine(machine_id: str) -> Machine:
        return set_archived("machines", machine_id, Machine, False)

    @app.delete("/api/machines/{machine_id}")
    def delete_machine(machine_id: str) -> dict[str, object]:
        return safe_delete("machines", machine_id, Machine)

    @app.get("/api/routes", response_model=list[Route])
    def routes(include_archived: bool = Query(False)) -> list[BaseModel]:
        return active("routes", include_archived)

    def save_route(payload: RouteCreate, previous: Route | None = None) -> BaseModel:
        machine_ids = {item.machine_id for item in active("machines", False) if isinstance(item, Machine)}
        unknown = [node.machine_id for node in payload.nodes if node.machine_id not in machine_ids]
        if unknown:
            raise HTTPException(422, f"Route contains unknown or archived machines: {', '.join(unknown)}")
        return repo.save(
            "routes",
            Route(
                **payload.model_dump(),
                route_id=new_id("route"),
                version=(previous.version + 1 if previous else 1),
                lineage_id=((previous.lineage_id or previous.route_id) if previous else None),
                created_at=now(),
            ),
        )

    @app.post("/api/routes", response_model=Route)
    def add_route(payload: RouteCreate) -> BaseModel:
        return save_route(payload)

    @app.post("/api/routes/{route_id}/versions", response_model=Route)
    def version_route(route_id: str, payload: RouteCreate) -> BaseModel:
        return save_route(payload, require("routes", route_id, Route))

    @app.post("/api/routes/{route_id}/archive", response_model=Route)
    def archive_route(route_id: str) -> Route:
        return set_archived("routes", route_id, Route, True)

    @app.post("/api/routes/{route_id}/restore", response_model=Route)
    def restore_route(route_id: str) -> Route:
        return set_archived("routes", route_id, Route, False)

    @app.delete("/api/routes/{route_id}")
    def delete_route(route_id: str) -> dict[str, object]:
        return safe_delete("routes", route_id, Route)

    @app.get("/api/route-recommendations", response_model=RouteRecommendationSet)
    def route_recommendations(
        blend_id: str,
        target_output_tph: float = Query(100, gt=0),
        selected_route_id: str | None = None,
    ) -> RouteRecommendationSet:
        blend = require("blends", blend_id, Blend)
        try:
            return recommend_routes(repo, blend, target_output_tph, selected_route_id)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/raw-mix/optimise", response_model=RawMixOptimisationResult)
    def optimise(payload: RawMixOptimisationRequest) -> RawMixOptimisationResult:
        try:
            return optimise_raw_mix(repo, payload)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc


    @app.post("/api/retrofit/ppc-to-lc3/design", response_model=RetrofitStudyResult)
    def design_ppc_to_lc3(payload: PpcToLc3RetrofitRequest) -> RetrofitStudyResult:
        try:
            return retrofit_designer.design(payload)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/retrofit-studies", response_model=list[RetrofitStudyResult])
    def retrofit_studies() -> list[BaseModel]:
        return repo.list("retrofit_studies")

    @app.get("/api/retrofit-studies/{study_id}", response_model=RetrofitStudyResult)
    def get_retrofit_study(study_id: str) -> RetrofitStudyResult:
        return require("retrofit_studies", study_id, RetrofitStudyResult)

    @app.get("/api/retrofit-studies/{study_id}/export.xlsx")
    def export_retrofit_study_xlsx(
        study_id: str,
        candidate_id: str | None = None,
    ) -> Response:
        study = require("retrofit_studies", study_id, RetrofitStudyResult)
        try:
            content = compile_retrofit_workbook(repo, study, candidate_id)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        filename = f"BRIXTA_PPC_to_LC3_{study_id}.xlsx"
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.post(
        "/api/retrofit-studies/{study_id}/candidates/{candidate_id}/save-blend",
        response_model=Blend,
    )
    def save_retrofit_candidate_as_blend(
        study_id: str,
        candidate_id: str,
        payload: SaveRetrofitCandidateRequest,
    ) -> BaseModel:
        study = require("retrofit_studies", study_id, RetrofitStudyResult)
        candidate = next(
            (item for item in study.candidates if item.candidate_id == candidate_id),
            None,
        )
        if candidate is None:
            raise HTTPException(404, "Unknown retrofit candidate")
        components = []
        for item in candidate.components:
            if item.component_type == "material":
                components.append(
                    {
                        "component_type": "material",
                        "material_id": item.reference_id,
                        "blend_id": None,
                        "percentage": item.percentage,
                    }
                )
            else:
                components.append(
                    {
                        "component_type": "blend",
                        "material_id": None,
                        "blend_id": item.reference_id,
                        "percentage": item.percentage,
                    }
                )
        blend_payload = BlendCreate(
            name=payload.name or candidate.name,
            blend_class="finished_cement",
            family="LC3",
            objective="PPC-to-LC3 retrofit Pareto candidate",
            applicable_standard=(
                payload.applicable_standard
                or "Reference LC3 screening; physical and compliance validation required"
            ),
            components=components,
            evidence=[],
        )
        return save_blend(blend_payload)

    @app.get("/api/cost-books", response_model=list[CostBook])
    def cost_books(include_archived: bool = Query(False)) -> list[BaseModel]:
        return active("cost_books", include_archived)

    @app.post("/api/cost-books", response_model=CostBook)
    def add_cost_book(payload: CostBookCreate) -> BaseModel:
        return repo.save(
            "cost_books",
            CostBook(**payload.model_dump(), cost_book_id=new_id("cost"), created_at=now()),
        )

    @app.post("/api/cost-books/{cost_book_id}/versions", response_model=CostBook)
    def version_cost_book(cost_book_id: str, payload: CostBookCreate) -> BaseModel:
        previous = require("cost_books", cost_book_id, CostBook)
        return repo.save(
            "cost_books",
            CostBook(
                **payload.model_dump(),
                cost_book_id=new_id("cost"),
                version=previous.version + 1,
                lineage_id=previous.lineage_id or previous.cost_book_id,
                created_at=now(),
            ),
        )

    @app.post("/api/cost-books/{cost_book_id}/archive", response_model=CostBook)
    def archive_cost_book(cost_book_id: str) -> CostBook:
        return set_archived("cost_books", cost_book_id, CostBook, True)

    @app.post("/api/cost-books/{cost_book_id}/restore", response_model=CostBook)
    def restore_cost_book(cost_book_id: str) -> CostBook:
        return set_archived("cost_books", cost_book_id, CostBook, False)

    @app.delete("/api/cost-books/{cost_book_id}")
    def delete_cost_book(cost_book_id: str) -> dict[str, object]:
        return safe_delete("cost_books", cost_book_id, CostBook)

    @app.post("/api/runs", response_model=RunResult)
    def run(payload: RunRequest) -> RunResult:
        try:
            return engine.run(payload)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/runs/variability", response_model=list[RunResult])
    def run_variability(payload: RunRequest) -> list[RunResult]:
        try:
            return [
                engine.run(payload.model_copy(update={"chemistry_scenario": scenario}))
                for scenario in ("low", "typical", "high")
            ]
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/runs", response_model=list[RunResult])
    def runs() -> list[BaseModel]:
        return repo.list("runs")

    @app.get("/api/runs/{run_id}", response_model=RunResult)
    def get_run(run_id: str) -> RunResult:
        return require("runs", run_id, RunResult)

    @app.get("/api/calibrations", response_model=list[CalibrationRecord])
    def calibrations() -> list[BaseModel]:
        return repo.list("calibrations")

    @app.post("/api/calibrations", response_model=CalibrationRecord)
    def add_calibration(payload: CalibrationCreate) -> BaseModel:
        result = require("runs", payload.run_id, RunResult)
        pairs = [
            ("output_tph", result.achievable_output_tph, payload.actual_output_tph),
            ("electricity_kwh_t", result.electricity_kwh_t, payload.actual_electricity_kwh_t),
            ("thermal_kcal_kg", result.thermal_kcal_kg, payload.actual_thermal_kcal_kg),
            ("direct_cost_inr_t", result.direct_model_cost_inr_t, payload.actual_direct_cost_inr_t),
            ("co2_kg_t", result.estimated_co2_kg_t, payload.actual_co2_kg_t),
        ]
        errors = []
        for metric, simulated, actual in pairs:
            absolute = simulated - actual if simulated is not None and actual is not None else None
            percent = absolute / actual * 100 if absolute is not None and actual not in {None, 0} else None
            errors.append(
                CalibrationError(
                    metric=metric,
                    simulated=simulated,
                    actual=actual,
                    absolute_error=absolute,
                    percent_error=percent,
                )
            )
        return repo.save(
            "calibrations",
            CalibrationRecord(
                **payload.model_dump(),
                calibration_id=new_id("cal"),
                created_at=now(),
                errors=errors,
            ),
        )

    @app.get("/api/runs/{run_id}/export.json")
    def export_run_json(run_id: str) -> Response:
        result = require("runs", run_id, RunResult)
        return Response(
            content=result.model_dump_json(indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{run_id}.json"'},
        )

    @app.get("/api/runs/{run_id}/export.csv")
    def export_run_csv(run_id: str) -> Response:
        result = require("runs", run_id, RunResult)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["section", "item", "value", "unit_or_detail"])
        product = result.output_product
        valid_value = lambda value: value if result.run_status == "completed" else None
        rows = [
            ("run", "run_id", result.run_id, ""),
            ("run", "created_at", result.created_at.isoformat(), "UTC"),
            ("run", "calculation_version", result.calculation_version, ""),
            ("run", "status", result.run_status, ""),
            ("configuration", "blend", result.blend_snapshot.name if result.blend_snapshot else result.request.blend_id, ""),
            ("configuration", "route", result.route_snapshot.name if result.route_snapshot else result.request.route_id, ""),
            ("configuration", "route_kind", result.route_analysis.route_kind if result.route_analysis else "legacy", ""),
            ("configuration", "route_flow", result.route_analysis.flow_summary if result.route_analysis else "legacy", ""),
            ("configuration", "route_compatibility_score", result.route_analysis.compatibility_score if result.route_analysis else None, "0-100"),
            ("configuration", "route_efficiency_score", result.route_analysis.efficiency_score if result.route_analysis else None, "0-100 deterministic score"),
            ("configuration", "route_graph_acyclic", result.route_analysis.graph.acyclic if result.route_analysis and result.route_analysis.graph else None, "Kahn topological sort"),
            ("configuration", "route_critical_path", " -> ".join(result.route_analysis.graph.critical_path_labels) if result.route_analysis and result.route_analysis.graph else None, "DAG capacity-critical path"),
            ("configuration", "route_critical_path_hours_per_t_output", result.route_analysis.graph.critical_path_hours_per_t_output if result.route_analysis and result.route_analysis.graph else None, "h/t output"),
            ("configuration", "cost_book", result.cost_book_snapshot.name if result.cost_book_snapshot else "none", ""),
            ("configuration", "chemistry_scenario", result.chemistry_scenario, "low/typical/high"),
            ("output", "product", product, ""),
            ("output", "target", result.request.target_output_tph, f"t/h {product}"),
            ("output", "achieved", valid_value(result.achievable_output_tph), f"t/h {product}"),
            ("material_input", "factor", valid_value(result.material_input_t_per_t_output), f"t input/t {product}"),
            ("material_input", "rate", valid_value(result.total_material_input_tph), "t/h input materials"),
            ("material_input", "run_total", valid_value(result.total_material_input_tonnes), "t input materials/run"),
            ("output", "bottleneck", result.bottleneck_machine_name or "unknown", f"{result.bottleneck_tph:.3f} t/h {product}"),
            ("energy", "electricity", valid_value(result.electricity_kwh_t), f"kWh/t {product}"),
            ("energy", "thermal", valid_value(result.thermal_kcal_kg), f"kcal/kg {product}"),
            ("cost", "materials", valid_value(result.material_cost_inr_t), f"INR/t {product}"),
            ("tariff", "electricity_applied", result.applied_electricity_inr_kwh, f"INR/kWh; {result.electricity_tariff_source}"),
            ("tariff", "thermal_applied", result.applied_thermal_fuel_inr_mkcal, f"INR/million kcal; {result.thermal_tariff_source}"),
            ("cost", "energy", valid_value(result.energy_cost_inr_t), f"INR/t {product}"),
            ("cost", "direct_model_total", valid_value(result.direct_model_cost_inr_t), f"INR/t {product}"),
            ("cost", "plant_cash_cost", valid_value(result.cost_breakdown.plant_cash_cost_inr_t) if result.cost_breakdown else None, f"INR/t {product}"),
            ("cost", "full_cost", valid_value(result.cost_breakdown.full_cost_inr_t) if result.cost_breakdown else None, f"INR/t {product}"),
            ("carbon", "materials", valid_value(result.estimated_co2_kg_t), f"kg CO2/t {product}"),
            ("mass_conversion", "derived_raw_meal_to_clinker_yield", result.derived_raw_meal_to_clinker_yield, "fraction"),
            ("process_correction", "grinding_capacity_factor", result.grinding_capacity_factor, "multiplier"),
            ("process_correction", "grinding_energy_factor", result.grinding_energy_factor, "multiplier"),
            ("process_correction", "fuel_ash_contribution", result.fuel_ash_contribution_kg_t_clinker, "kg/t clinker"),
            ("clinker_moduli", "LSF", result.clinker_lsf, "clinker basis"),
            ("clinker_moduli", "SM", result.clinker_silica_modulus, "clinker basis"),
            ("clinker_moduli", "AM", result.clinker_alumina_modulus, "clinker basis"),
            ("clinker_mineralogy", "C3S", result.clinker_mineralogy.c3s_percent if result.clinker_mineralogy else None, "potential mass %; Bogue estimate"),
            ("clinker_mineralogy", "C2S", result.clinker_mineralogy.c2s_percent if result.clinker_mineralogy else None, "potential mass %; Bogue estimate"),
            ("clinker_mineralogy", "C3A", result.clinker_mineralogy.c3a_percent if result.clinker_mineralogy else None, "potential mass %; Bogue estimate"),
            ("clinker_mineralogy", "C4AF", result.clinker_mineralogy.c4af_percent if result.clinker_mineralogy else None, "potential mass %; Bogue estimate"),
            ("clinker_behaviour", "burnability", result.clinker_behaviour.burnability_class if result.clinker_behaviour else None, "deterministic screening"),
            ("clinker_behaviour", "free_lime_risk", result.clinker_behaviour.free_lime_risk if result.clinker_behaviour else None, "deterministic screening"),
            ("clinker_behaviour", "expected_fuel_demand", result.clinker_behaviour.expected_fuel_demand if result.clinker_behaviour else None, "deterministic screening"),
            ("clinker_behaviour", "expected_early_strength", result.clinker_behaviour.expected_early_strength if result.clinker_behaviour else None, "deterministic screening"),
            ("clinker_behaviour", "expected_sulfate_resistance", result.clinker_behaviour.expected_sulfate_resistance if result.clinker_behaviour else None, "deterministic screening"),
            ("quality", "OPC43_gate", result.quality_gate.status if result.quality_gate else "not_applicable", "measured-results gate"),
        ]
        writer.writerows(rows)
        for item in result.material_metrics:
            writer.writerow(["material_percent", item.material_name, item.percentage, f"mass percent; stream={item.production_stream}"])
            writer.writerow(["material_per_output", item.material_name, item.tonnes_per_t_output, f"t input/t {product}"])
            writer.writerow(["material_rate", item.material_name, valid_value(item.tonnes_per_hour), "t/h input material"])
            writer.writerow(["material_run_total", item.material_name, valid_value(item.tonnes_per_run), f"t/{result.request.duration_hours:g} h run"])
            writer.writerow(["material_cost", item.material_name, valid_value(item.cost_inr_t_output), f"INR/t {product}; {item.cost_basis}; unit cost={item.applied_unit_cost_inr_t}"])
        for item in result.machine_metrics:
            writer.writerow(["machine", item.machine_name, item.load_percent, f"load percent; stream={item.process_stream}; stage={item.process_stage}"])
            writer.writerow(["machine_target", item.machine_name, item.target_load_percent, "target-required load percent"])
            writer.writerow(["machine_flow", item.machine_name, item.actual_throughput_tph, f"t/h; factor={item.throughput_factor_t_stage_per_t_output}"])
            writer.writerow(["machine_electricity", item.machine_name, item.electricity_kwh_t_output, f"kWh/t {product}; stream={item.process_stream}"])
            writer.writerow(["machine_thermal", item.machine_name, item.thermal_kcal_kg_output, f"kcal/kg {product}; stream={item.process_stream}"])
        for step in result.calculation_trace:
            writer.writerow([
                "calculation_trace",
                f"{step.sequence}:{step.section}:{step.operation}",
                step.result,
                f"{step.unit or ''}; formula={step.formula}; route_node={step.route_node_id or ''}; inputs={step.inputs}",
            ])
        for item in result.validation:
            writer.writerow(["validation", item.code, item.severity, item.message])
        if result.route_analysis:
            for reason in result.route_analysis.reasons:
                writer.writerow(["route", "reason", reason, ""])
        if result.quality_gate:
            for check in result.quality_gate.checks:
                writer.writerow(["quality", check.metric, check.measured, f"{check.status}; {check.requirement}"])
        for item in result.assumptions:
            writer.writerow(["assumption", item.key, item.value, item.basis])
        for item in result.evidence_references:
            writer.writerow(["evidence", item.source_title, item.evidence_class, item.page or item.source_uri or ""])
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{run_id}.csv"'},
        )

    return app


app = create_app()
