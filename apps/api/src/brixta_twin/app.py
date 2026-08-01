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
    CostBook,
    CostBookCreate,
    Machine,
    MachineCreate,
    Material,
    MaterialCreate,
    Route,
    RouteCreate,
    RunRequest,
    RunResult,
    new_id,
    now,
)
from .seed import seed
from .simulation import Engine
from .storage import Repository


Entity = TypeVar("Entity", bound=BaseModel)


def create_app(path: str | Path | None = None) -> FastAPI:
    repo = Repository(path)
    seed(repo)
    engine = Engine(repo)
    app = FastAPI(title="BRIXTA Cement Twin API", version="0.4.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
        return {"status": "ok", "service": "brixta-cement-twin-api", "version": "0.4.0"}

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

    @app.get("/api/runs", response_model=list[RunResult])
    def runs() -> list[BaseModel]:
        return repo.list("runs")

    @app.get("/api/runs/{run_id}", response_model=RunResult)
    def get_run(run_id: str) -> RunResult:
        return require("runs", run_id, RunResult)

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
        rows = [
            ("run", "run_id", result.run_id, ""),
            ("run", "created_at", result.created_at.isoformat(), "UTC"),
            ("run", "calculation_version", result.calculation_version, ""),
            ("configuration", "blend", result.blend_snapshot.name if result.blend_snapshot else result.request.blend_id, ""),
            ("configuration", "route", result.route_snapshot.name if result.route_snapshot else result.request.route_id, ""),
            ("configuration", "cost_book", result.cost_book_snapshot.name if result.cost_book_snapshot else "none", ""),
            ("output", "target", result.request.target_output_tph, "t/h cement"),
            ("output", "achieved", result.achievable_output_tph, "t/h cement"),
            ("output", "bottleneck", result.bottleneck_machine_name or "unknown", f"{result.bottleneck_tph:.3f} t/h cement-equivalent"),
            ("energy", "electricity", result.electricity_kwh_t, "kWh/t cement"),
            ("energy", "thermal", result.thermal_kcal_kg, "kcal/kg cement"),
            ("cost", "materials", result.material_cost_inr_t, "INR/t cement"),
            ("cost", "energy", result.energy_cost_inr_t, "INR/t cement"),
            ("cost", "direct_model_total", result.direct_model_cost_inr_t, "INR/t cement"),
            ("cost", "plant_cash_cost", result.cost_breakdown.plant_cash_cost_inr_t if result.cost_breakdown else None, "INR/t cement"),
            ("cost", "full_cost", result.cost_breakdown.full_cost_inr_t if result.cost_breakdown else None, "INR/t cement"),
            ("carbon", "materials", result.estimated_co2_kg_t, "kg CO2/t cement"),
        ]
        writer.writerows(rows)
        for item in result.material_metrics:
            writer.writerow(["material", item.material_name, item.percentage, f"mass percent; {item.cost_basis}; unit cost={item.applied_unit_cost_inr_t}"])
        for item in result.machine_metrics:
            writer.writerow(["machine", item.machine_name, item.load_percent, "load percent"])
        for item in result.validation:
            writer.writerow(["validation", item.code, item.severity, item.message])
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{run_id}.csv"'},
        )

    return app


app = create_app()
