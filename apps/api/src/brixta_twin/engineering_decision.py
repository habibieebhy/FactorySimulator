from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from statistics import median
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .models import (
    Blend,
    Machine,
    RetrofitCandidate,
    RetrofitStudyResult,
    Route,
    new_id,
    now,
)
from .storage import Repository


ConfidenceBand = Literal["low", "medium", "high"]
RiskRating = Literal["low", "medium", "high", "critical"]
DecisionStatus = Literal["draft", "proceed", "hold", "reject"]


class EngineeringProject(BaseModel):
    project_name: str = "PPC-to-LC3 Engineering Decision"
    plant_name: str = "Reference plant"
    engineer: str = "BRIXTA Engineering"
    product_target: str = "LC3"
    revision: str = "R0"
    bis_constraints: list[str] = Field(default_factory=list)
    customer_constraints: list[str] = Field(default_factory=list)
    pilot_quantity_t: float = Field(default=500.0, gt=0)
    pilot_rate_fraction: float = Field(default=0.60, gt=0, le=1)
    monitoring_hours: float = Field(default=72.0, gt=0)
    notes: str | None = None


class EngineeringCaseCreate(BaseModel):
    study_id: str
    candidate_id: str
    project: EngineeringProject = Field(default_factory=EngineeringProject)


class EngineeringPrediction(BaseModel):
    code: str
    category: str
    label: str
    prediction: float | str | None = None
    unit: str | None = None
    confidence_percent: float = Field(ge=0, le=100)
    confidence_band: ConfidenceBand
    reason: str
    required_validation: list[str] = Field(default_factory=list)
    source_basis: list[str] = Field(default_factory=list)
    risk: RiskRating = "medium"


class EngineeringAction(BaseModel):
    parameter: str
    current_value: float | str | None = None
    recommended_value: float | str | None = None
    unit: str | None = None
    change: float | str | None = None
    rationale: str


class EngineeringRecommendation(BaseModel):
    recommendation_id: str
    title: str
    discipline: str
    priority: Literal["P1", "P2", "P3"] = "P2"
    actions: list[EngineeringAction] = Field(default_factory=list)
    expected_results: list[EngineeringPrediction] = Field(default_factory=list)
    confidence_percent: float = Field(ge=0, le=100)
    reasons: list[str] = Field(default_factory=list)
    required_validation: list[str] = Field(default_factory=list)
    risk: RiskRating = "medium"
    proceed_condition: str


class PilotSetting(BaseModel):
    area: str
    parameter: str
    target: float | str | None = None
    unit: str | None = None
    basis: str
    validation: str


class PilotBatchPlan(BaseModel):
    pilot_quantity_t: float
    pilot_rate_tph: float | None = None
    formulation: list[dict[str, float | str]] = Field(default_factory=list)
    machine_settings: list[PilotSetting] = Field(default_factory=list)
    kiln_settings: list[PilotSetting] = Field(default_factory=list)
    mill_settings: list[PilotSetting] = Field(default_factory=list)
    sampling_plan: list[str] = Field(default_factory=list)
    required_lab_tests: list[str] = Field(default_factory=list)
    go_no_go_criteria: list[str] = Field(default_factory=list)
    monitoring_plan: list[str] = Field(default_factory=list)


class EngineeringCase(BaseModel):
    case_id: str
    created_at: datetime
    calculation_version: str = "0.9.0"
    status: DecisionStatus = "draft"
    project: EngineeringProject
    study_id: str
    candidate_id: str
    baseline_blend_id: str
    route_id: str
    cost_book_id: str | None = None
    risk_rating: RiskRating
    confidence_percent: float = Field(ge=0, le=100)
    confidence_band: ConfidenceBand
    executive_summary: str
    predictions: list[EngineeringPrediction] = Field(default_factory=list)
    recommendations: list[EngineeringRecommendation] = Field(default_factory=list)
    pilot_plan: PilotBatchPlan
    assumptions: list[dict[str, str]] = Field(default_factory=list)
    missing_data: list[dict[str, str]] = Field(default_factory=list)
    calculation_trace: list[dict[str, str | float | None]] = Field(default_factory=list)
    calibration_profile: dict[str, float] = Field(default_factory=dict)
    calibration_sample_count: int = 0


class EngineeringValidationCreate(BaseModel):
    actual_output_tph: float | None = Field(default=None, gt=0)
    actual_electricity_kwh_t: float | None = Field(default=None, ge=0)
    actual_thermal_kcal_kg: float | None = Field(default=None, ge=0)
    actual_variable_cost_inr_t: float | None = Field(default=None, ge=0)
    actual_material_co2_kg_t: float | None = Field(default=None, ge=0)
    actual_free_lime_percent: float | None = Field(default=None, ge=0, le=20)
    actual_strength_3d_mpa: float | None = Field(default=None, ge=0)
    actual_strength_28d_mpa: float | None = Field(default=None, ge=0)
    xrf_comparison: str | None = None
    xrd_comparison: str | None = None
    coal_observation: str | None = None
    power_observation: str | None = None
    thermal_observation: str | None = None
    comments: str | None = None
    root_cause: str | None = None
    decision: DecisionStatus = "hold"
    engineer_signoff: str | None = None
    quality_head_signoff: str | None = None
    plant_head_signoff: str | None = None

    @model_validator(mode="after")
    def has_actual_measurement(self) -> "EngineeringValidationCreate":
        numeric = (
            self.actual_output_tph,
            self.actual_electricity_kwh_t,
            self.actual_thermal_kcal_kg,
            self.actual_variable_cost_inr_t,
            self.actual_material_co2_kg_t,
            self.actual_free_lime_percent,
            self.actual_strength_3d_mpa,
            self.actual_strength_28d_mpa,
        )
        if not any(value is not None for value in numeric):
            raise ValueError("At least one actual pilot or plant measurement is required")
        return self


class PredictionError(BaseModel):
    metric: str
    predicted: float | None = None
    actual: float | None = None
    absolute_error: float | None = None
    percent_error: float | None = None
    recalibration_factor: float | None = None


class EngineeringValidationRecord(EngineeringValidationCreate):
    validation_id: str
    case_id: str
    created_at: datetime
    prediction_errors: list[PredictionError] = Field(default_factory=list)
    mean_absolute_percent_error: float | None = None
    confidence_before_percent: float
    confidence_after_percent: float
    calibration_profile: dict[str, float] = Field(default_factory=dict)
    calibration_sample_count: int = 0


class EngineeringLearningResult(BaseModel):
    case_id: str
    validation_id: str
    prediction_errors: list[PredictionError] = Field(default_factory=list)
    mean_absolute_percent_error: float | None = None
    confidence_before_percent: float
    confidence_after_percent: float
    calibration_profile: dict[str, float] = Field(default_factory=dict)
    calibration_sample_count: int = 0
    learning_summary: str


class EngineeringStore:
    """Small persistence layer for auditable engineering cases and pilot learning."""

    def __init__(self, repository: Repository) -> None:
        self.path = repository.path
        with self._connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS engineering_cases("
                "entity_id TEXT PRIMARY KEY,payload TEXT NOT NULL,created_at TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS engineering_validations("
                "entity_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL)"
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        return db

    def save_case(self, case: EngineeringCase) -> EngineeringCase:
        with self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO engineering_cases VALUES(?,?,?)",
                (case.case_id, case.model_dump_json(), case.created_at.isoformat()),
            )
        return case

    def get_case(self, case_id: str) -> EngineeringCase | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT payload FROM engineering_cases WHERE entity_id=?", (case_id,)
            ).fetchone()
        return EngineeringCase.model_validate_json(row["payload"]) if row else None

    def list_cases(self) -> list[EngineeringCase]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT payload FROM engineering_cases ORDER BY created_at DESC"
            ).fetchall()
        return [EngineeringCase.model_validate_json(row["payload"]) for row in rows]

    def save_validation(
        self, validation: EngineeringValidationRecord
    ) -> EngineeringValidationRecord:
        with self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO engineering_validations VALUES(?,?,?,?)",
                (
                    validation.validation_id,
                    validation.case_id,
                    validation.model_dump_json(),
                    validation.created_at.isoformat(),
                ),
            )
        return validation

    def list_validations(self, case_id: str | None = None) -> list[EngineeringValidationRecord]:
        query = "SELECT payload FROM engineering_validations"
        params: tuple[str, ...] = ()
        if case_id is not None:
            query += " WHERE case_id=?"
            params = (case_id,)
        query += " ORDER BY created_at ASC"
        with self._connect() as db:
            rows = db.execute(query, params).fetchall()
        return [
            EngineeringValidationRecord.model_validate_json(row["payload"])
            for row in rows
        ]


class EngineeringDecisionService:
    """Convert deterministic retrofit output into an auditable engineering workflow."""

    METRIC_FIELDS = {
        "output_tph": "actual_output_tph",
        "electricity_kwh_t": "actual_electricity_kwh_t",
        "thermal_kcal_kg": "actual_thermal_kcal_kg",
        "variable_cost_inr_t": "actual_variable_cost_inr_t",
        "material_co2_kg_t": "actual_material_co2_kg_t",
    }

    def __init__(self, repository: Repository) -> None:
        self.repository = repository
        self.store = EngineeringStore(repository)

    def create_case(self, payload: EngineeringCaseCreate) -> EngineeringCase:
        study = self.repository.get("retrofit_studies", payload.study_id)
        if not isinstance(study, RetrofitStudyResult):
            raise ValueError("Unknown retrofit study")
        candidate = next(
            (item for item in study.candidates if item.candidate_id == payload.candidate_id),
            None,
        )
        if candidate is None:
            raise ValueError("Unknown retrofit candidate")

        route = self.repository.get("routes", study.request.route_id)
        if not isinstance(route, Route):
            raise ValueError("Retrofit study route is unavailable")
        baseline_blend = self.repository.get("blends", study.request.existing_ppc_blend_id)
        if not isinstance(baseline_blend, Blend):
            raise ValueError("Retrofit baseline blend is unavailable")

        profile, samples = self._calibration_profile(
            payload.project.plant_name, payload.project.product_target
        )
        confidence = self._confidence(study, candidate, samples)
        band = self._confidence_band(confidence)
        risk = self._risk(study, candidate, confidence)
        predictions = self._predictions(study, candidate, confidence, profile)
        recommendations = self._recommendations(
            study, candidate, predictions, confidence, risk
        )
        pilot = self._pilot_plan(payload.project, route, candidate)
        missing_data = self._missing_data(study, candidate)
        executive_summary = self._executive_summary(
            payload.project, candidate, predictions, confidence, risk
        )
        case = EngineeringCase(
            case_id=new_id("engcase"),
            created_at=now(),
            project=payload.project,
            study_id=study.study_id,
            candidate_id=candidate.candidate_id,
            baseline_blend_id=baseline_blend.blend_id,
            route_id=route.route_id,
            cost_book_id=study.request.cost_book_id,
            risk_rating=risk,
            confidence_percent=confidence,
            confidence_band=band,
            executive_summary=executive_summary,
            predictions=predictions,
            recommendations=recommendations,
            pilot_plan=pilot,
            assumptions=[item.model_dump() for item in study.assumptions],
            missing_data=missing_data,
            calculation_trace=[
                {
                    "sequence": step.sequence,
                    "section": step.section,
                    "operation": step.operation,
                    "formula": step.formula,
                    "result": step.result,
                    "unit": step.unit,
                }
                for step in candidate.calculation_trace
            ],
            calibration_profile=profile,
            calibration_sample_count=samples,
        )
        return self.store.save_case(case)

    def validate_case(
        self, case_id: str, payload: EngineeringValidationCreate
    ) -> EngineeringLearningResult:
        case = self.store.get_case(case_id)
        if case is None:
            raise ValueError("Unknown engineering case")

        predicted = {
            item.code: float(item.prediction)
            for item in case.predictions
            if isinstance(item.prediction, (int, float))
        }
        errors: list[PredictionError] = []
        percent_errors: list[float] = []
        for metric, actual_field in self.METRIC_FIELDS.items():
            actual = getattr(payload, actual_field)
            estimate = predicted.get(metric)
            if actual is None or estimate is None:
                continue
            absolute = actual - estimate
            percent = (absolute / estimate * 100.0) if abs(estimate) > 1e-12 else None
            factor = actual / estimate if abs(estimate) > 1e-12 else None
            if percent is not None:
                percent_errors.append(abs(percent))
            errors.append(
                PredictionError(
                    metric=metric,
                    predicted=estimate,
                    actual=actual,
                    absolute_error=absolute,
                    percent_error=percent,
                    recalibration_factor=factor,
                )
            )
        mape = sum(percent_errors) / len(percent_errors) if percent_errors else None
        confidence_after = self._confidence_after(case.confidence_percent, mape)
        validation_id = new_id("engval")
        provisional = EngineeringValidationRecord(
            **payload.model_dump(),
            validation_id=validation_id,
            case_id=case.case_id,
            created_at=now(),
            prediction_errors=errors,
            mean_absolute_percent_error=mape,
            confidence_before_percent=case.confidence_percent,
            confidence_after_percent=confidence_after,
        )
        self.store.save_validation(provisional)
        profile, samples = self._calibration_profile(
            case.project.plant_name, case.project.product_target
        )
        final = provisional.model_copy(
            update={
                "calibration_profile": profile,
                "calibration_sample_count": samples,
            }
        )
        self.store.save_validation(final)
        return EngineeringLearningResult(
            case_id=case.case_id,
            validation_id=final.validation_id,
            prediction_errors=errors,
            mean_absolute_percent_error=mape,
            confidence_before_percent=case.confidence_percent,
            confidence_after_percent=confidence_after,
            calibration_profile=profile,
            calibration_sample_count=samples,
            learning_summary=self._learning_summary(mape, profile, samples),
        )

    def latest_learning(self, case_id: str) -> EngineeringLearningResult | None:
        case = self.store.get_case(case_id)
        if case is None:
            raise ValueError("Unknown engineering case")
        validations = self.store.list_validations(case_id)
        if not validations:
            return None
        item = validations[-1]
        return EngineeringLearningResult(
            case_id=case_id,
            validation_id=item.validation_id,
            prediction_errors=item.prediction_errors,
            mean_absolute_percent_error=item.mean_absolute_percent_error,
            confidence_before_percent=item.confidence_before_percent,
            confidence_after_percent=item.confidence_after_percent,
            calibration_profile=item.calibration_profile,
            calibration_sample_count=item.calibration_sample_count,
            learning_summary=self._learning_summary(
                item.mean_absolute_percent_error,
                item.calibration_profile,
                item.calibration_sample_count,
            ),
        )

    def _calibration_profile(
        self, plant_name: str, product_target: str
    ) -> tuple[dict[str, float], int]:
        factors: dict[str, list[float]] = {key: [] for key in self.METRIC_FIELDS}
        samples = 0
        for validation in self.store.list_validations():
            case = self.store.get_case(validation.case_id)
            if case is None:
                continue
            if (
                case.project.plant_name.strip().lower() != plant_name.strip().lower()
                or case.project.product_target.strip().lower()
                != product_target.strip().lower()
            ):
                continue
            samples += 1
            for error in validation.prediction_errors:
                if (
                    error.metric in factors
                    and error.recalibration_factor is not None
                    and 0.25 <= error.recalibration_factor <= 4.0
                ):
                    factors[error.metric].append(error.recalibration_factor)
        profile = {
            metric: float(median(values)) if values else 1.0
            for metric, values in factors.items()
        }
        return profile, samples

    def _confidence(
        self,
        study: RetrofitStudyResult,
        candidate: RetrofitCandidate,
        calibration_samples: int,
    ) -> float:
        score = (
            0.34 * candidate.robustness_score
            + 0.24 * candidate.route_compatibility_score
            + 0.17 * candidate.route_efficiency_score
            + (15.0 if candidate.chemistry_complete else 6.0)
        )
        required_gaps = sum(
            item.requirement == "required" for item in candidate.missing_assets
        )
        recommended_gaps = sum(
            item.requirement == "recommended" for item in candidate.missing_assets
        )
        score -= min(22.0, required_gaps * 7.0 + recommended_gaps * 2.0)
        score -= min(18.0, len(study.data_to_replace) * 0.7)
        score += min(10.0, calibration_samples * 2.0)
        return round(max(20.0, min(95.0, score)), 1)

    @staticmethod
    def _confidence_band(score: float) -> ConfidenceBand:
        if score >= 80:
            return "high"
        if score >= 55:
            return "medium"
        return "low"

    @staticmethod
    def _risk(
        study: RetrofitStudyResult,
        candidate: RetrofitCandidate,
        confidence: float,
    ) -> RiskRating:
        required = sum(item.requirement == "required" for item in candidate.missing_assets)
        if required >= 2 or confidence < 40:
            return "critical"
        if required == 1 or confidence < 60 or not candidate.chemistry_complete:
            return "high"
        if study.data_to_replace or confidence < 80:
            return "medium"
        return "low"

    def _predictions(
        self,
        study: RetrofitStudyResult,
        candidate: RetrofitCandidate,
        confidence: float,
        profile: dict[str, float],
    ) -> list[EngineeringPrediction]:
        def corrected(code: str, value: float | None) -> float | None:
            return None if value is None else round(value * profile.get(code, 1.0), 4)

        validation_common = [
            "Plant mass balance",
            "Plant power and fuel records",
            "Representative XRF",
            "Pilot production result",
        ]
        predicted_output = corrected("output_tph", candidate.predicted_output_tph)
        utilization = (
            min(100.0, predicted_output / study.request.target_output_tph * 100.0)
            if predicted_output is not None and study.request.target_output_tph > 0
            else None
        )
        components = {item.role: item.percentage for item in candidate.components}
        metrics = [
            EngineeringPrediction(
                code="output_tph",
                category="production",
                label="Sustainable LC3 output",
                prediction=predicted_output,
                unit="t/h",
                confidence_percent=confidence,
                confidence_band=self._confidence_band(confidence),
                reason=(
                    f"Route capacity screening identifies {candidate.bottleneck_machine_name or 'no resolved machine'} "
                    "as the binding equipment constraint."
                ),
                required_validation=["72-hour production trial", "Machine load and downtime log"],
                source_basis=["Route graph", "Stored machine capacities", "Calibration profile"],
                risk="high" if candidate.output_shortfall_tph > 0 else "medium",
            ),
            EngineeringPrediction(
                code="utilization_percent",
                category="production",
                label="Target-production attainment",
                prediction=round(utilization, 2) if utilization is not None else None,
                unit="% of requested output",
                confidence_percent=confidence,
                confidence_band=self._confidence_band(confidence),
                reason="Predicted sustainable output divided by the requested LC3 production rate.",
                required_validation=["Operating-hours reconciliation", "Availability and speed-loss log"],
                source_basis=["Target output", "Predicted output"],
            ),
            EngineeringPrediction(
                code="electricity_kwh_t",
                category="energy",
                label="Specific electricity",
                prediction=corrected("electricity_kwh_t", candidate.electricity_kwh_t),
                unit="kWh/t LC3",
                confidence_percent=max(20.0, confidence - 8.0),
                confidence_band=self._confidence_band(max(20.0, confidence - 8.0)),
                reason="Sum of route-specific electrical burdens plus the selected clay pathway.",
                required_validation=["Feeder-wise power meters", "Mill and fan load logs"],
                source_basis=["Machine specific electricity", "Route throughput factors"],
            ),
            EngineeringPrediction(
                code="thermal_kcal_kg",
                category="thermal",
                label="Specific thermal demand",
                prediction=corrected("thermal_kcal_kg", candidate.thermal_kcal_kg),
                unit="kcal/kg LC3",
                confidence_percent=max(20.0, confidence - 12.0),
                confidence_band=self._confidence_band(max(20.0, confidence - 12.0)),
                reason="Reference route heat duty including onsite clay calcination when selected.",
                required_validation=["Plant heat balance", "Fuel NCV", "Stack and cooler temperatures"],
                source_basis=["Stored thermal duties", "Clinker and clay fractions"],
                risk="high" if study.request.clay_supply_mode == "onsite_calcination" else "medium",
            ),
            EngineeringPrediction(
                code="variable_cost_inr_t",
                category="cost",
                label="Variable manufacturing cost",
                prediction=corrected(
                    "variable_cost_inr_t", candidate.total_variable_cost_inr_t
                ),
                unit="INR/t LC3",
                confidence_percent=max(20.0, confidence - 10.0),
                confidence_band=self._confidence_band(max(20.0, confidence - 10.0)),
                reason="Material, electricity and thermal-fuel costs only; fixed and financing costs are excluded.",
                required_validation=["Delivered material costs", "Tariffs", "Fuel invoices"],
                source_basis=["Cost book", "Reference placeholders where missing"],
            ),
            EngineeringPrediction(
                code="material_co2_kg_t",
                category="carbon",
                label="Material CO2 intensity",
                prediction=corrected(
                    "material_co2_kg_t", candidate.material_co2_kg_t
                ),
                unit="kg CO2/t LC3",
                confidence_percent=max(20.0, confidence - 10.0),
                confidence_band=self._confidence_band(max(20.0, confidence - 10.0)),
                reason="Weighted material factors; combustion and electricity-scope emissions require plant factors.",
                required_validation=["Verified material EPD/factors", "Fuel and electricity emission factors"],
                source_basis=["Material library", "Reference placeholders where missing"],
            ),
            EngineeringPrediction(
                code="clinker_factor_percent",
                category="formulation",
                label="Clinker factor",
                prediction=candidate.clinker_factor_percent,
                unit="%",
                confidence_percent=confidence,
                confidence_band=self._confidence_band(confidence),
                reason="Direct formulation decision variable from the selected Pareto candidate.",
                required_validation=["Weigh-feeder calibration", "Composite sample reconciliation"],
                source_basis=["Selected formulation"],
                risk="medium",
            ),
            EngineeringPrediction(
                code="clinker_flow_tph",
                category="mass balance",
                label="Clinker feed requirement",
                prediction=(
                    round(predicted_output * components.get("clinker", 0.0) / 100.0, 4)
                    if predicted_output is not None
                    else None
                ),
                unit="t/h",
                confidence_percent=confidence,
                confidence_band=self._confidence_band(confidence),
                reason="LC3 output multiplied by the selected clinker fraction.",
                required_validation=validation_common,
                source_basis=["Mass conservation", "Selected formulation"],
            ),
            EngineeringPrediction(
                code="calcined_clay_flow_tph",
                category="mass balance",
                label="Calcined-clay requirement",
                prediction=(
                    round(
                        predicted_output
                        * components.get("calcined_clay", 0.0)
                        / 100.0,
                        4,
                    )
                    if predicted_output is not None
                    else None
                ),
                unit="t/h",
                confidence_percent=confidence,
                confidence_band=self._confidence_band(confidence),
                reason="LC3 output multiplied by the selected calcined-clay fraction.",
                required_validation=["Clay feeder calibration", "Clay moisture and LOI"],
                source_basis=["Mass conservation", "Selected formulation"],
            ),
        ]
        return metrics

    def _recommendations(
        self,
        study: RetrofitStudyResult,
        candidate: RetrofitCandidate,
        predictions: list[EngineeringPrediction],
        confidence: float,
        risk: RiskRating,
    ) -> list[EngineeringRecommendation]:
        shares = {item.role: item.percentage for item in candidate.components}
        by_code = {item.code: item for item in predictions}
        recommendations: list[EngineeringRecommendation] = []

        recommendations.append(
            EngineeringRecommendation(
                recommendation_id=new_id("rec"),
                title="Adopt the selected LC3 formulation as a controlled pilot recipe",
                discipline="Clinker chemistry / cement formulation",
                priority="P1",
                actions=[
                    EngineeringAction(
                        parameter=role.replace("_", " ").title(),
                        current_value="Existing PPC dosage",
                        recommended_value=percentage,
                        unit="% by mass",
                        change="Replace with candidate dosage during pilot",
                        rationale="Selected by deterministic Pareto and robustness screening.",
                    )
                    for role, percentage in shares.items()
                ],
                expected_results=[
                    by_code["clinker_factor_percent"],
                    by_code["output_tph"],
                    by_code["variable_cost_inr_t"],
                    by_code["material_co2_kg_t"],
                ],
                confidence_percent=confidence,
                reasons=[
                    "Candidate survives formulation-bound and clay/limestone-ratio pruning.",
                    "Candidate is ranked using cost, CO2, output, energy, robustness and retrofit complexity.",
                ],
                required_validation=[
                    "XRF of all components",
                    "XRD/reactivity of calcined clay",
                    "Gypsum/SO3 optimisation trial",
                    "3-day, 7-day and 28-day strength",
                ],
                risk=risk,
                proceed_condition="Proceed only after feeder calibration and laboratory acceptance of the pilot recipe.",
            )
        )

        if candidate.output_shortfall_tph > 0 or candidate.bottleneck_machine_name:
            recommendations.append(
                EngineeringRecommendation(
                    recommendation_id=new_id("rec"),
                    title="Remove the binding production constraint before scaling LC3",
                    discipline="Plant design / mechanical / operations",
                    priority="P1",
                    actions=[
                        EngineeringAction(
                            parameter="Binding equipment",
                            current_value=candidate.bottleneck_machine_name or "Unresolved",
                            recommended_value="Validate effective capacity and debottleneck",
                            rationale=(
                                f"Reference screening indicates {candidate.output_shortfall_tph:.2f} t/h "
                                "of shortfall against the requested output."
                            ),
                        )
                    ],
                    expected_results=[by_code["output_tph"], by_code["utilization_percent"]],
                    confidence_percent=max(20.0, confidence - 5.0),
                    reasons=[
                        "Production cannot exceed the minimum output-equivalent capacity along the active route.",
                        "Nameplate capacity must be replaced by demonstrated effective capacity.",
                    ],
                    required_validation=[
                        "Machine performance test",
                        "Downtime classification",
                        "Feeder, conveyor, separator and fan capacity checks",
                    ],
                    risk="high",
                    proceed_condition="Do not claim the target output until the bottleneck performance test closes the capacity gap.",
                )
            )

        for gap in candidate.missing_assets:
            recommendations.append(
                EngineeringRecommendation(
                    recommendation_id=new_id("rec"),
                    title=f"Close retrofit gap: {gap.asset_name}",
                    discipline="Plant design / project engineering",
                    priority="P1" if gap.requirement == "required" else "P2",
                    actions=[
                        EngineeringAction(
                            parameter=gap.asset_name,
                            current_value="Missing or not evidenced",
                            recommended_value=(
                                f"Reference capacity {gap.reference_capacity_tph:.1f} t/h"
                                if gap.reference_capacity_tph is not None
                                else "Size from confirmed plant mass balance"
                            ),
                            rationale=gap.reason,
                        )
                    ],
                    expected_results=[],
                    confidence_percent=max(20.0, confidence - 10.0),
                    reasons=[gap.reason, gap.assumption_basis],
                    required_validation=[
                        "Site routing check",
                        "Vendor budgetary proposal",
                        "Storage and material-handling compatibility",
                    ],
                    risk="critical" if gap.requirement == "required" else "high",
                    proceed_condition=(
                        "Required asset must exist or be approved before pilot."
                        if gap.requirement == "required"
                        else "Confirm that existing equipment can perform the required function."
                    ),
                )
            )

        recommendations.append(
            EngineeringRecommendation(
                recommendation_id=new_id("rec"),
                title="Validate the heat and power balance before changing kiln or mill settings",
                discipline="Thermal / electrical / process engineering",
                priority="P1",
                actions=[
                    EngineeringAction(
                        parameter="Kiln temperature",
                        current_value="Plant operating envelope not supplied",
                        recommended_value="No automatic change",
                        rationale="Chemistry screening alone cannot justify a temperature increase or decrease.",
                    ),
                    EngineeringAction(
                        parameter="Specific electricity",
                        current_value=study.baseline.electricity_kwh_t,
                        recommended_value=by_code["electricity_kwh_t"].prediction,
                        unit="kWh/t",
                        change=candidate.electricity_delta_vs_ppc_kwh_t,
                        rationale="Use the candidate as the reference; validate by feeder-wise metering.",
                    ),
                    EngineeringAction(
                        parameter="Specific thermal demand",
                        current_value=study.baseline.thermal_kcal_kg,
                        recommended_value=by_code["thermal_kcal_kg"].prediction,
                        unit="kcal/kg",
                        change=candidate.thermal_delta_vs_ppc_kcal_kg,
                        rationale="Use the candidate as the reference; validate with a plant heat balance.",
                    ),
                ],
                expected_results=[
                    by_code["electricity_kwh_t"],
                    by_code["thermal_kcal_kg"],
                ],
                confidence_percent=max(20.0, confidence - 12.0),
                reasons=[
                    "The current model is screening-level and does not solve combustion kinetics or axial kiln temperature profiles.",
                    "Unmeasured fan, separator, heat-loss and fuel-NCV values dominate uncertainty.",
                ],
                required_validation=[
                    "Kiln heat balance",
                    "Fuel proximate/ultimate analysis and NCV",
                    "Stack O2 and gas flow",
                    "Cooler recovery test",
                    "Mill and fan power logging",
                ],
                risk="high",
                proceed_condition="Change thermal or mill settings only through an approved plant trial with interlocks and quality monitoring.",
            )
        )
        return recommendations

    def _pilot_plan(
        self,
        project: EngineeringProject,
        route: Route,
        candidate: RetrofitCandidate,
    ) -> PilotBatchPlan:
        output = candidate.predicted_output_tph
        pilot_rate = round(output * project.pilot_rate_fraction, 3) if output else None
        formulation = [
            {
                "role": item.role,
                "material": item.name,
                "percentage": item.percentage,
            }
            for item in candidate.components
        ]
        machine_settings: list[PilotSetting] = []
        for node in route.nodes:
            machine = self.repository.get("machines", node.machine_id)
            if not isinstance(machine, Machine):
                continue
            machine_settings.append(
                PilotSetting(
                    area=machine.process_stage,
                    parameter=f"{machine.name} throughput",
                    target=pilot_rate,
                    unit="t/h product-equivalent",
                    basis=(
                        f"Pilot rate set at {project.pilot_rate_fraction:.0%} of the predicted sustainable output; "
                        "replace with stage-specific mass-flow conversion before execution."
                    ),
                    validation="Confirm feeder/conveyor rate and machine load against nameplate and interlocks.",
                )
            )
        kiln_settings = [
            PilotSetting(
                area="kiln",
                parameter="Burning-zone temperature",
                target="Use existing approved operating envelope",
                basis="No chemistry-only temperature adjustment is authorised.",
                validation="Track free lime, clinker litre weight, kiln torque and fuel rate.",
            ),
            PilotSetting(
                area="kiln",
                parameter="Kiln O2 / draft / fuel rate",
                target="Plant baseline with controlled trial adjustment",
                basis="Requires plant instrumentation and fuel properties.",
                validation="Continuous trend and operator log; stop on interlock or quality excursion.",
            ),
        ]
        mill_settings = [
            PilotSetting(
                area="cement grinding",
                parameter="LC3 mill feed rate",
                target=pilot_rate,
                unit="t/h",
                basis="Controlled pilot rate, not full-scale target.",
                validation="Monitor mill differential pressure, vibration, separator load and motor power.",
            ),
            PilotSetting(
                area="cement grinding",
                parameter="Blaine / residue / separator setting",
                target="Set from approved laboratory trial target",
                basis="Strength and workability cannot be inferred from chemistry alone.",
                validation="Hourly Blaine/residue during stabilization; compressive strength by batch.",
            ),
        ]
        return PilotBatchPlan(
            pilot_quantity_t=project.pilot_quantity_t,
            pilot_rate_tph=pilot_rate,
            formulation=formulation,
            machine_settings=machine_settings,
            kiln_settings=kiln_settings,
            mill_settings=mill_settings,
            sampling_plan=[
                "Composite raw-material and cement samples before the trial.",
                "Hourly feeder reconciliation during the first 8 operating hours.",
                "Cement sample every 2 hours after stabilization.",
                "Clinker/free-lime sample at the plant-approved kiln sampling frequency.",
                "Retain sealed reference samples for dispute and recalibration analysis.",
            ],
            required_lab_tests=[
                "XRF of every component and composite cement",
                "XRD/Rietveld or validated calcined-clay reactivity test",
                "Moisture and LOI",
                "Blaine and residue",
                "Initial and final setting time",
                "Soundness",
                "3-day, 7-day and 28-day compressive strength",
                "Free lime for clinker-producing trials",
            ],
            go_no_go_criteria=[
                "No safety, interlock or environmental exceedance.",
                "Formulation mass balance closes within the plant-approved tolerance.",
                "No confirmed BIS/product-specification violation.",
                "Free lime and kiln stability remain inside the plant control envelope.",
                "Mill, separator, fan and packer loads remain inside approved operating limits.",
                "Quality Head accepts early results before extending the campaign.",
            ],
            monitoring_plan=[
                f"Trend production, power, fuel, temperatures, pressures and quality for {project.monitoring_hours:.0f} hours.",
                "Record every manual intervention and equipment trip.",
                "Compare actuals against workbook predictions by shift and by composite batch.",
                "Issue an engineering deviation report before scale-up.",
            ],
        )

    def _missing_data(
        self, study: RetrofitStudyResult, candidate: RetrofitCandidate
    ) -> list[dict[str, str]]:
        items: list[tuple[str, str, str]] = [
            ("materials", "Representative XRF with variability", "Required for chemistry and robustness"),
            ("materials", "XRD/mineralogy and clay reactivity", "Required for calcined-clay activation confidence"),
            ("materials", "PSD, moisture and LOI", "Required for mass, drying and grinding balances"),
            ("quarry", "Source, reserve and seasonal variability", "Required for supply robustness"),
            ("fuel", "NCV, ash, sulfur, chlorine and alkalis", "Required for fuel ash and heat balance"),
            ("thermal", "Stack/cooler temperatures and gas flows", "Required for heat-loss and recovery calculation"),
            ("machines", "Effective capacity and performance curves", "Required for bottleneck and utilization"),
            ("machines", "Geometry, residence time and operating envelope", "Required for kiln/calciner engineering"),
            ("grinding", "Bond Work Index or plant grindability", "Required for power and output prediction"),
            ("grinding", "Separator efficiency and circulating load", "Required for mill capacity"),
            ("commercial", "Delivered costs and current tariffs", "Required for plant-specific cost"),
            ("quality", "Applicable BIS/product targets", "Required for compliance gate"),
            ("quality", "Free lime, strength, setting and soundness history", "Required for recommendation validation"),
            ("operations", "Downtime, speed-loss and quality-loss history", "Required for utilization diagnosis"),
        ]
        for text in study.data_to_replace:
            items.append(("study", text, "Declared by the retrofit study"))
        for gap in candidate.missing_assets:
            items.append(("asset", gap.asset_name, gap.reason))
        unique: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for category, item, reason in items:
            key = (category, item)
            if key in seen:
                continue
            seen.add(key)
            unique.append({"category": category, "item": item, "reason": reason})
        return unique

    @staticmethod
    def _executive_summary(
        project: EngineeringProject,
        candidate: RetrofitCandidate,
        predictions: list[EngineeringPrediction],
        confidence: float,
        risk: RiskRating,
    ) -> str:
        values = {item.code: item for item in predictions}
        output = values["output_tph"].prediction
        cost = values["variable_cost_inr_t"].prediction
        co2 = values["material_co2_kg_t"].prediction
        return (
            f"{project.project_name} screens candidate {candidate.name} for {project.plant_name}. "
            f"The reference model predicts {output} t/h, variable cost {cost} INR/t and material CO2 {co2} kg/t. "
            f"Overall confidence is {confidence:.1f}% and risk is {risk.upper()}. "
            "The recommendation is not a production authorisation: the pilot plan, missing-data register, "
            "laboratory validation and plant sign-offs must be completed before scale-up."
        )

    @staticmethod
    def _confidence_after(before: float, mape: float | None) -> float:
        if mape is None:
            return before
        if mape <= 5:
            delta = 8
        elif mape <= 10:
            delta = 4
        elif mape <= 20:
            delta = 0
        elif mape <= 35:
            delta = -5
        else:
            delta = -10
        return round(max(10.0, min(99.0, before + delta)), 1)

    @staticmethod
    def _learning_summary(
        mape: float | None, profile: dict[str, float], samples: int
    ) -> str:
        if mape is None:
            return "Actual results were recorded, but no comparable predicted metric was supplied."
        factors = ", ".join(f"{key}={value:.3f}" for key, value in profile.items())
        return (
            f"Pilot mean absolute prediction error is {mape:.2f}%. "
            f"The plant/product calibration profile now contains {samples} validation record(s): {factors}. "
            "Future engineering cases for the same plant and product apply the median correction factor while retaining the raw prediction in the audit trail."
        )
