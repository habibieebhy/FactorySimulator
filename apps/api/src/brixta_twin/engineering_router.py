from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from .engineering_catalog import EngineeringCatalog, load_engineering_catalog

from .engineering_decision import (
    EngineeringCase,
    EngineeringCaseCreate,
    EngineeringDecisionService,
    EngineeringLearningResult,
    EngineeringValidationCreate,
)
from .engineering_package import compile_engineering_package
from .engineering_workbook import compile_engineering_workbook
from .models import RetrofitStudyResult
from .storage import Repository


def build_engineering_router(repository: Repository) -> APIRouter:
    router = APIRouter(prefix="/api/engineering", tags=["engineering-decision"])
    service = EngineeringDecisionService(repository)

    @router.get("/catalog", response_model=EngineeringCatalog)
    def engineering_catalog() -> EngineeringCatalog:
        return load_engineering_catalog()

    @router.post("/cases", response_model=EngineeringCase)
    def create_engineering_case(payload: EngineeringCaseCreate) -> EngineeringCase:
        try:
            return service.create_case(payload)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.get("/cases", response_model=list[EngineeringCase])
    def list_engineering_cases() -> list[EngineeringCase]:
        return service.store.list_cases()

    @router.get("/cases/{case_id}", response_model=EngineeringCase)
    def get_engineering_case(case_id: str) -> EngineeringCase:
        case = service.store.get_case(case_id)
        if case is None:
            raise HTTPException(404, "Unknown engineering case")
        return case

    @router.get("/cases/{case_id}/trust")
    def engineering_case_trust(case_id: str):
        case = service.store.get_case(case_id)
        if case is None:
            raise HTTPException(404, "Unknown engineering case")
        if case.trust_assessment is None:
            raise HTTPException(409, "Legacy engineering case has no trust assessment; create a new revision under calculation version 1.0.0")
        return case.trust_assessment

    @router.get("/cases/{case_id}/package.zip")
    def export_engineering_package(case_id: str) -> Response:
        case = service.store.get_case(case_id)
        if case is None:
            raise HTTPException(404, "Unknown engineering case")
        if case.trust_assessment is None or case.decision_gate is None:
            raise HTTPException(409, "Legacy engineering case cannot be packaged; create a new revision under calculation version 1.0.0")
        study = repository.get("retrofit_studies", case.study_id)
        if not isinstance(study, RetrofitStudyResult):
            raise HTTPException(404, "Engineering case source study is unavailable")
        candidate = next(
            (item for item in study.candidates if item.candidate_id == case.candidate_id),
            None,
        )
        if candidate is None:
            raise HTTPException(404, "Engineering case scenario is unavailable")
        content = compile_engineering_package(
            repository,
            case,
            study,
            candidate,
            service.store.list_validations(case_id),
        )
        filename = f"BRIXTA_Digital_Engineering_Package_{case.case_id}_{case.project.revision}.zip"
        return Response(
            content=content,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.get("/cases/{case_id}/export.xlsx")
    def export_engineering_case(case_id: str) -> Response:
        case = service.store.get_case(case_id)
        if case is None:
            raise HTTPException(404, "Unknown engineering case")
        study = repository.get("retrofit_studies", case.study_id)
        if not isinstance(study, RetrofitStudyResult):
            raise HTTPException(404, "Engineering case retrofit study is unavailable")
        candidate = next(
            (item for item in study.candidates if item.candidate_id == case.candidate_id),
            None,
        )
        if candidate is None:
            raise HTTPException(404, "Engineering case candidate is unavailable")
        try:
            content = compile_engineering_workbook(
                repository,
                case,
                study,
                candidate,
                service.store.list_validations(case_id),
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        filename = f"BRIXTA_Engineering_Decision_{case.case_id}_{case.project.revision}.xlsx"
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.post(
        "/cases/{case_id}/validation",
        response_model=EngineeringLearningResult,
    )
    def import_engineering_validation(
        case_id: str,
        payload: EngineeringValidationCreate,
    ) -> EngineeringLearningResult:
        try:
            return service.validate_case(case_id, payload)
        except ValueError as exc:
            message = str(exc)
            status = 404 if message.startswith("Unknown engineering case") else 422
            raise HTTPException(status, message) from exc

    @router.get(
        "/cases/{case_id}/learning",
        response_model=EngineeringLearningResult | None,
    )
    def latest_engineering_learning(
        case_id: str,
    ) -> EngineeringLearningResult | None:
        try:
            return service.latest_learning(case_id)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    return router
