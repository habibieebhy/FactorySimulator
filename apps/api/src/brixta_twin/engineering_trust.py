from __future__ import annotations

from collections import Counter
from typing import Literal, Protocol, Sequence

from pydantic import BaseModel, Field

from .engineering_catalog import EngineeringCatalog, ProductDefinition, load_engineering_catalog
from .models import Blend, CostBook, Machine, Material, RetrofitCandidate, RetrofitStudyResult, Route, new_id
from .storage import Repository


KnowledgeStatus = Literal["known", "assumed", "uncertain", "unknown"]
ReviewStatus = Literal["pass", "conditional", "hold", "fail", "not_reviewed"]
GateDecision = Literal["proceed_to_pilot", "hold_for_validation", "reject", "advisory_only"]
ValidationAvailability = Literal["available", "partial", "unavailable", "not_confirmed"]
RiskLevel = Literal["low", "medium", "high", "critical"]
EvidenceClass = Literal[
    "plant_measurement",
    "laboratory_result",
    "validated_historical",
    "vendor_guarantee",
    "project_engineering",
    "regulatory_or_standard",
    "peer_reviewed",
    "reference_engineering",
    "user_assumption",
    "unknown",
]


class PredictionLike(Protocol):
    code: str
    category: str
    label: str
    prediction: float | str | None
    confidence_percent: float
    required_validation: list[str]
    source_basis: list[str]
    risk: str


class RecommendationLike(Protocol):
    recommendation_id: str
    title: str
    discipline: str
    confidence_percent: float
    required_validation: list[str]
    risk: str


class EvidenceRecord(BaseModel):
    evidence_id: str
    subject: str
    evidence_class: EvidenceClass
    title: str
    source_uri: str | None = None
    revision_or_date: str | None = None
    applies_to: list[str] = Field(default_factory=list)
    quality_score_percent: float = Field(ge=0, le=100)
    status: KnowledgeStatus
    limitations: list[str] = Field(default_factory=list)


class CriticalAssumption(BaseModel):
    assumption_id: str
    subject: str
    statement: str
    basis: str
    consequence_if_wrong: str
    sensitivity: Literal["low", "medium", "high", "critical"] = "medium"
    replacement_data: str


class UnknownInput(BaseModel):
    input_id: str
    category: str
    item: str
    consequence: str
    criticality: Literal["low", "medium", "high", "critical"] = "medium"
    can_use_reference_default: bool = True
    validation_or_replacement: str


class SensitivityDriver(BaseModel):
    variable: str
    direction: str
    importance_percent: float = Field(ge=0, le=100)
    rationale: str
    recommended_test: str


class PredictionInterval(BaseModel):
    low: float | None = None
    central: float | str | None = None
    high: float | None = None
    unit: str | None = None
    basis: str


class ValidationRequirement(BaseModel):
    validation_id: str
    category: str
    measurement: str
    purpose: str
    acceptable_tolerance: str
    frequency_or_sample: str
    owner: str
    availability: ValidationAvailability = "not_confirmed"
    blocking: bool = True
    evidence_generated: str


class FailureMode(BaseModel):
    failure_mode_id: str
    discipline: str
    failure_mode: str
    cause: str
    consequence: str
    severity: int = Field(ge=1, le=5)
    likelihood: int = Field(ge=1, le=5)
    detectability: int = Field(ge=1, le=5)
    risk_priority_number: int = Field(ge=1, le=125)
    mitigation: str
    rollback_trigger: str


class DisciplineReview(BaseModel):
    discipline: str
    mandatory: bool = True
    status: ReviewStatus
    findings: list[str] = Field(default_factory=list)
    blocking_issues: list[str] = Field(default_factory=list)
    evidence_reviewed: list[str] = Field(default_factory=list)
    approval_required_from: str


class ScenarioAssessment(BaseModel):
    scenario_id: str
    name: str
    why_it_exists: str
    expected_benefit: list[str] = Field(default_factory=list)
    expected_downside: list[str] = Field(default_factory=list)
    probability_of_success_percent: float = Field(ge=0, le=100)
    required_validation: list[str] = Field(default_factory=list)
    business_impact: str
    engineering_impact: str
    risk_level: RiskLevel
    rank: int
    recommended_for_pilot: bool = False


class DecisionGate(BaseModel):
    decision: GateDecision
    production_change_authorised: bool = False
    pilot_authorised: bool = False
    reason: str
    blocking_conditions: list[str] = Field(default_factory=list)
    conditions_to_advance: list[str] = Field(default_factory=list)
    rollback_required: bool = True
    approval_requirements: list[str] = Field(default_factory=list)


class TrustQuestionAnswer(BaseModel):
    question: str
    answer: str
    status: Literal["adequate", "partial", "inadequate"]
    supporting_ids: list[str] = Field(default_factory=list)


class TrustAssessment(BaseModel):
    assessment_id: str
    catalog_version: str
    product_definition_id: str | None = None
    evidence_coverage_percent: float = Field(ge=0, le=100)
    data_completeness_percent: float = Field(ge=0, le=100)
    traceability_percent: float = Field(ge=0, le=100)
    validation_readiness_percent: float = Field(ge=0, le=100)
    overall_confidence_percent: float = Field(ge=0, le=100)
    confidence_band: Literal["low", "medium", "high"]
    critical_assumptions: list[CriticalAssumption] = Field(default_factory=list)
    unknown_inputs: list[UnknownInput] = Field(default_factory=list)
    sensitive_variables: list[SensitivityDriver] = Field(default_factory=list)
    evidence_register: list[EvidenceRecord] = Field(default_factory=list)
    validation_plan: list[ValidationRequirement] = Field(default_factory=list)
    risk_register: list[FailureMode] = Field(default_factory=list)
    review_committee: list[DisciplineReview] = Field(default_factory=list)
    scenario_assessments: list[ScenarioAssessment] = Field(default_factory=list)
    trust_questions: list[TrustQuestionAnswer] = Field(default_factory=list)
    decision_gate: DecisionGate


class EngineeringTrustService:
    """Earn confidence from evidence, completeness, validation and multidisciplinary review.

    This service never upgrades a recommendation merely because an optimiser found
    an attractive number. Production authority is withheld until evidence and
    validation gates are satisfied.
    """

    def __init__(self, repository: Repository, catalog: EngineeringCatalog | None = None) -> None:
        self.repository = repository
        self.catalog = catalog or load_engineering_catalog()

    def assess(
        self,
        *,
        study: RetrofitStudyResult,
        candidate: RetrofitCandidate,
        product_target: str,
        product_definition_id: str | None,
        standard_ids: Sequence[str],
        validation_resources: Sequence[str],
        predictions: Sequence[PredictionLike],
        recommendations: Sequence[RecommendationLike],
        missing_data: Sequence[dict[str, str]],
        calculation_trace_count: int,
        calibration_samples: int,
    ) -> TrustAssessment:
        product = self.catalog.product(product_definition_id or product_target)
        evidence = self._evidence_register(study, candidate, standard_ids)
        assumptions = self._critical_assumptions(study, candidate)
        unknowns = self._unknown_inputs(missing_data)
        sensitivities = self._sensitivity_drivers(candidate, predictions)
        validation_plan = self._validation_plan(
            product,
            predictions,
            recommendations,
            validation_resources,
        )
        risks = self._risk_register(study, candidate, unknowns)

        evidence_coverage = self._evidence_coverage(evidence)
        completeness = self._data_completeness(unknowns)
        traceability = self._traceability(calculation_trace_count, predictions, evidence)
        validation_readiness = self._validation_readiness(validation_plan)
        confidence = self._earned_confidence(
            candidate=candidate,
            evidence_coverage=evidence_coverage,
            completeness=completeness,
            traceability=traceability,
            validation_readiness=validation_readiness,
            calibration_samples=calibration_samples,
            unknowns=unknowns,
            risks=risks,
        )
        reviews = self._committee_reviews(
            product=product,
            study=study,
            candidate=candidate,
            evidence=evidence,
            unknowns=unknowns,
            validation_plan=validation_plan,
            risks=risks,
        )
        scenarios = self._scenario_assessments(study, validation_plan)
        gate = self._decision_gate(
            confidence=confidence,
            evidence_coverage=evidence_coverage,
            validation_plan=validation_plan,
            unknowns=unknowns,
            risks=risks,
            reviews=reviews,
        )
        questions = self._trust_questions(
            evidence=evidence,
            assumptions=assumptions,
            unknowns=unknowns,
            validation_plan=validation_plan,
            traceability=traceability,
        )
        return TrustAssessment(
            assessment_id=new_id("trust"),
            catalog_version=self.catalog.catalog_version,
            product_definition_id=product.product_id if product else None,
            evidence_coverage_percent=evidence_coverage,
            data_completeness_percent=completeness,
            traceability_percent=traceability,
            validation_readiness_percent=validation_readiness,
            overall_confidence_percent=confidence,
            confidence_band=self._band(confidence),
            critical_assumptions=assumptions,
            unknown_inputs=unknowns,
            sensitive_variables=sensitivities,
            evidence_register=evidence,
            validation_plan=validation_plan,
            risk_register=risks,
            review_committee=reviews,
            scenario_assessments=scenarios,
            trust_questions=questions,
            decision_gate=gate,
        )

    def prediction_interval(
        self,
        code: str,
        value: float | str | None,
        confidence_percent: float,
        unit: str | None,
    ) -> PredictionInterval:
        if not isinstance(value, (int, float)):
            return PredictionInterval(
                central=value,
                unit=unit,
                basis="Qualitative prediction; numeric interval is not applicable.",
            )
        base_width = {
            "output_tph": 0.08,
            "electricity_kwh_t": 0.12,
            "thermal_kcal_kg": 0.15,
            "variable_cost_inr_t": 0.18,
            "material_co2_kg_t": 0.12,
            "clinker_factor_percent": 0.02,
            "clinker_flow_tph": 0.10,
            "calcined_clay_flow_tph": 0.12,
        }.get(code, 0.15)
        confidence_penalty = max(0.0, (80.0 - confidence_percent) / 100.0)
        width = min(0.50, base_width + confidence_penalty * 0.60)
        low = value * (1.0 - width)
        high = value * (1.0 + width)
        if code.endswith("percent"):
            low = max(0.0, low)
            high = min(100.0, high)
        return PredictionInterval(
            low=round(low, 4),
            central=round(float(value), 4),
            high=round(high, 4),
            unit=unit,
            basis=(
                "Screening interval derived from prediction class, earned confidence, "
                "data completeness and absence of plant calibration; it is not a statistical confidence interval."
            ),
        )

    def _evidence_register(
        self,
        study: RetrofitStudyResult,
        candidate: RetrofitCandidate,
        standard_ids: Sequence[str],
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        seen: set[tuple[str, str, str]] = set()

        def add(
            subject: str,
            evidence_class: str,
            title: str,
            *,
            source_uri: str | None = None,
            applies_to: Sequence[str] = (),
            limitations: Sequence[str] = (),
        ) -> None:
            canonical = self._canonical_evidence_class(evidence_class)
            key = (subject, canonical, title)
            if key in seen:
                return
            seen.add(key)
            quality = self.catalog.evidence_quality(canonical) * 100.0
            status: KnowledgeStatus
            if quality >= 85:
                status = "known"
            elif quality >= 55:
                status = "uncertain"
            elif quality > 0:
                status = "assumed"
            else:
                status = "unknown"
            records.append(
                EvidenceRecord(
                    evidence_id=new_id("evidence"),
                    subject=subject,
                    evidence_class=canonical,  # type: ignore[arg-type]
                    title=title,
                    source_uri=source_uri,
                    applies_to=list(applies_to),
                    quality_score_percent=round(quality, 1),
                    status=status,
                    limitations=list(limitations),
                )
            )

        for component in candidate.components:
            if component.component_type == "material":
                material = self.repository.get("materials", component.reference_id)
                if isinstance(material, Material):
                    if material.evidence:
                        for item in material.evidence:
                            add(
                                subject=f"material:{material.material_id}",
                                evidence_class=item.evidence_class,
                                title=item.source_title,
                                source_uri=item.source_uri,
                                applies_to=["chemistry", "cost", "carbon", "formulation"],
                                limitations=[item.note] if item.note else [],
                            )
                    else:
                        add(
                            subject=f"material:{material.material_id}",
                            evidence_class="unknown",
                            title=f"No evidence attached to {material.name}",
                            applies_to=["chemistry", "cost", "carbon", "formulation"],
                            limitations=["Material values cannot be independently audited."],
                        )
            else:
                blend = self.repository.get("blends", component.reference_id)
                if isinstance(blend, Blend):
                    if blend.evidence:
                        for item in blend.evidence:
                            add(
                                subject=f"blend:{blend.blend_id}",
                                evidence_class=item.evidence_class,
                                title=item.source_title,
                                source_uri=item.source_uri,
                                applies_to=["formulation", "chemistry"],
                                limitations=[item.note] if item.note else [],
                            )
                    else:
                        add(
                            subject=f"blend:{blend.blend_id}",
                            evidence_class="reference_engineering",
                            title=f"Versioned blend definition: {blend.name}",
                            applies_to=["formulation"],
                            limitations=["Constituent plant measurements may still be missing."],
                        )

        route = self.repository.get("routes", study.request.route_id)
        if isinstance(route, Route):
            add(
                subject=f"route:{route.route_id}",
                evidence_class="project_engineering",
                title=f"Versioned process route: {route.name}",
                applies_to=["process", "capacity", "mechanical"],
                limitations=["Connectivity is evidenced; actual valve, conveyor and operating status require site verification."],
            )
            for node in route.nodes:
                machine = self.repository.get("machines", node.machine_id)
                if not isinstance(machine, Machine):
                    continue
                if machine.evidence:
                    for item in machine.evidence:
                        add(
                            subject=f"machine:{machine.machine_id}",
                            evidence_class=item.evidence_class,
                            title=item.source_title,
                            source_uri=item.source_uri,
                            applies_to=["capacity", "energy", "mechanical", "thermal"],
                            limitations=[item.note] if item.note else [],
                        )
                else:
                    add(
                        subject=f"machine:{machine.machine_id}",
                        evidence_class="reference_engineering",
                        title=f"Stored machine model: {machine.name}",
                        applies_to=["capacity", "energy", "mechanical", "thermal"],
                        limitations=["Nameplate and performance-curve evidence not attached."],
                    )

        cost_book = (
            self.repository.get("cost_books", study.request.cost_book_id)
            if study.request.cost_book_id
            else None
        )
        if isinstance(cost_book, CostBook):
            if cost_book.evidence:
                for item in cost_book.evidence:
                    add(
                        subject=f"cost_book:{cost_book.cost_book_id}",
                        evidence_class=item.evidence_class,
                        title=item.source_title,
                        source_uri=item.source_uri,
                        applies_to=["cost", "tariff"],
                        limitations=[item.note] if item.note else [],
                    )
            else:
                add(
                    subject=f"cost_book:{cost_book.cost_book_id}",
                    evidence_class="user_assumption",
                    title=f"Commercial basis: {cost_book.name}",
                    applies_to=["cost", "tariff"],
                    limitations=["Effective date and documentary support must be confirmed."],
                )

        confirmed_standards: list[str] = []
        unresolved_standard_notes: list[str] = []
        for standard_id in standard_ids:
            cleaned = standard_id.strip()
            if not cleaned:
                continue
            lowered = cleaned.lower()
            if any(token in lowered for token in ("confirm", "tbd", "unknown", "to be defined", "not linked")):
                unresolved_standard_notes.append(cleaned)
                continue
            confirmed_standards.append(cleaned)
            add(
                subject=f"quality_standard:{cleaned}",
                evidence_class="regulatory_or_standard",
                title=cleaned,
                applies_to=["quality", "compliance", "release"],
            )
        if not confirmed_standards:
            add(
                subject="quality_standard:unresolved",
                evidence_class="unknown",
                title="Applicable product standard not linked",
                applies_to=["quality", "compliance", "release"],
                limitations=[
                    "BRIXTA cannot make a compliance claim without a versioned standard and acceptance criteria.",
                    *unresolved_standard_notes,
                ],
            )

        for item in study.assumptions:
            add(
                subject=f"assumption:{item.key}",
                evidence_class="reference_engineering",
                title=f"{item.key}: {item.value}",
                applies_to=["simulation"],
                limitations=[item.basis],
            )
        return records

    def _critical_assumptions(
        self, study: RetrofitStudyResult, candidate: RetrofitCandidate
    ) -> list[CriticalAssumption]:
        assumptions: list[CriticalAssumption] = []
        for item in study.assumptions:
            text = f"{item.key} = {item.value}"
            low = item.key.lower()
            sensitivity: Literal["low", "medium", "high", "critical"] = "medium"
            consequence = "Prediction may shift outside the displayed screening interval."
            replacement = "Replace with a documented plant, vendor or laboratory value."
            if any(token in low for token in ("yield", "capacity", "thermal", "electricity", "reactivity")):
                sensitivity = "high"
            assumptions.append(
                CriticalAssumption(
                    assumption_id=new_id("assumption"),
                    subject=item.key,
                    statement=text,
                    basis=item.basis,
                    consequence_if_wrong=consequence,
                    sensitivity=sensitivity,
                    replacement_data=replacement,
                )
            )
        if candidate.bottleneck_machine_name:
            assumptions.append(
                CriticalAssumption(
                    assumption_id=new_id("assumption"),
                    subject="effective_bottleneck_capacity",
                    statement=f"{candidate.bottleneck_machine_name} effective capacity represents sustainable plant duty.",
                    basis="Stored route and machine model",
                    consequence_if_wrong="Predicted output and utilization may be materially overstated or understated.",
                    sensitivity="critical",
                    replacement_data="Conduct a witnessed equipment performance test with downtime and quality reconciliation.",
                )
            )
        return assumptions

    def _unknown_inputs(self, missing_data: Sequence[dict[str, str]]) -> list[UnknownInput]:
        output: list[UnknownInput] = []
        for item in missing_data:
            text = item.get("item", "Unspecified data")
            category = item.get("category", "engineering")
            reason = item.get("reason", "Required to validate the engineering prediction")
            combined = f"{category} {text} {reason}".lower()
            criticality: Literal["low", "medium", "high", "critical"] = "medium"
            can_default = True
            if any(token in combined for token in ("standard", "safety", "interlock", "required asset", "applicable bis")):
                criticality = "critical"
                can_default = False
            elif any(token in combined for token in ("xrf", "xrd", "effective capacity", "free lime", "strength", "fuel", "heat balance", "operating envelope")):
                criticality = "high"
            output.append(
                UnknownInput(
                    input_id=new_id("unknown"),
                    category=category,
                    item=text,
                    consequence=reason,
                    criticality=criticality,
                    can_use_reference_default=can_default,
                    validation_or_replacement=f"Obtain and attach traceable {text.lower()} evidence.",
                )
            )
        return output

    def _sensitivity_drivers(
        self,
        candidate: RetrofitCandidate,
        predictions: Sequence[PredictionLike],
    ) -> list[SensitivityDriver]:
        drivers = [
            SensitivityDriver(
                variable="Effective bottleneck capacity and availability",
                direction="Higher demonstrated capacity increases sustainable output; downtime reduces it.",
                importance_percent=95,
                rationale=f"Route screening identifies {candidate.bottleneck_machine_name or 'an unresolved route constraint'} as binding.",
                recommended_test="Witnessed capacity and availability test with mass-flow reconciliation.",
            ),
            SensitivityDriver(
                variable="Material chemistry and variability",
                direction="Chemistry excursions can change raw mix, clinker formation, sulfate balance and product quality.",
                importance_percent=90,
                rationale="Formulation calculations depend on representative oxide chemistry and variability bounds.",
                recommended_test="Representative XRF programme with low/typical/high and seasonal samples.",
            ),
            SensitivityDriver(
                variable="Calcined-clay mineralogy/reactivity or SCM reactivity",
                direction="Lower reactivity can increase strength risk and change optimum dosage/fineness.",
                importance_percent=88,
                rationale="Chemical composition alone does not establish pozzolanic reaction performance.",
                recommended_test="XRD/Rietveld plus validated reactivity and mortar-strength testing.",
            ),
            SensitivityDriver(
                variable="Grinding response and separator performance",
                direction="Harder material or lower separator efficiency reduces throughput and increases electricity.",
                importance_percent=82,
                rationale="Candidate output and power depend on route-specific reference grinding burdens.",
                recommended_test="Plant grindability trial, separator efficiency and circulating-load measurement.",
            ),
            SensitivityDriver(
                variable="Fuel NCV, moisture, ash and heat losses",
                direction="Lower net heat input or higher losses increase fuel consumption and may constrain output.",
                importance_percent=80,
                rationale="Thermal predictions are reference screening until a plant heat balance is closed.",
                recommended_test="Fuel laboratory analysis and complete kiln/calciner heat balance.",
            ),
        ]
        if not any(item.code == "thermal_kcal_kg" for item in predictions):
            drivers = [item for item in drivers if not item.variable.startswith("Fuel")]
        return drivers

    def _validation_plan(
        self,
        product: ProductDefinition | None,
        predictions: Sequence[PredictionLike],
        recommendations: Sequence[RecommendationLike],
        validation_resources: Sequence[str],
    ) -> list[ValidationRequirement]:
        available = {item.strip().lower() for item in validation_resources if item.strip()}
        requirements: list[ValidationRequirement] = []
        seen: set[tuple[str, str]] = set()

        def availability_for(text: str) -> ValidationAvailability:
            needle = text.lower()
            if not available:
                return "not_confirmed"
            if any(token in needle for token in available):
                return "available"
            if any(token in " ".join(available) for token in needle.split() if len(token) > 4):
                return "partial"
            return "not_confirmed"

        def add(category: str, measurement: str, purpose: str, blocking: bool = True) -> None:
            key = (category, measurement)
            if key in seen:
                return
            seen.add(key)
            requirements.append(
                ValidationRequirement(
                    validation_id=new_id("validation"),
                    category=category,
                    measurement=measurement,
                    purpose=purpose,
                    acceptable_tolerance="Plant-approved engineering or product-standard tolerance must be entered before execution.",
                    frequency_or_sample="Define representative sampling frequency and retained reference sample.",
                    owner=self._validation_owner(category),
                    availability=availability_for(measurement),
                    blocking=blocking,
                    evidence_generated=f"Signed {measurement} record linked to the engineering case and revision.",
                )
            )

        if product:
            for item in product.required_validation:
                add("product", item.replace("_", " "), f"Required by configured product definition {product.name}.")
        for prediction in predictions:
            for item in prediction.required_validation:
                add(prediction.category, item, f"Validate prediction: {prediction.label}")
        for recommendation in recommendations:
            for item in recommendation.required_validation:
                add(recommendation.discipline, item, f"Close recommendation gate: {recommendation.title}")
        return requirements

    def _risk_register(
        self,
        study: RetrofitStudyResult,
        candidate: RetrofitCandidate,
        unknowns: Sequence[UnknownInput],
    ) -> list[FailureMode]:
        raw: list[tuple[str, str, str, str, int, int, int, str, str]] = [
            (
                "chemistry",
                "Material chemistry differs from the model basis",
                "Unrepresentative XRF or seasonal quarry variation",
                "Moduli, clinker formation, sulfate balance or product quality may leave the approved envelope",
                5,
                3,
                3,
                "Representative low/typical/high chemistry programme and formulation stress test",
                "Stop or revert if composite chemistry leaves approved control limits",
            ),
            (
                "quality",
                "Strength, setting or soundness does not meet release criteria",
                "Reactivity, sulfate balance, fineness or curing response differs from screening assumptions",
                "Nonconforming cement or customer failure",
                5,
                3,
                3,
                "Controlled laboratory and pilot programme with product hold pending release",
                "Quarantine pilot material and return to approved formulation",
            ),
            (
                "process",
                "Sustainable output is below the predicted rate",
                "Effective capacity, availability, separator, fan or material-handling constraints are understated",
                "Campaign instability, starvation, blockage or missed production target",
                4,
                4,
                3,
                "Run witnessed capacity tests and begin pilot below predicted sustainable rate",
                "Reduce feed to the last stable approved rate",
            ),
            (
                "thermal",
                "Thermal demand or kiln/calciner stability is worse than predicted",
                "Fuel properties, moisture, heat loss or reaction duty differ from reference assumptions",
                "Excess fuel, unstable free lime, emissions or refractory risk",
                5,
                3,
                3,
                "Complete fuel analysis and heat balance; do not automatically change temperature",
                "Return fuel/feed/temperature controls to the approved baseline",
            ),
            (
                "mechanical",
                "Feeder, conveyor, silo, mill or fan cannot handle the new material duty",
                "Bulk behaviour, moisture, aeration, turndown or capacity was not verified",
                "Spillage, blockage, overload, downtime or unsafe intervention",
                5,
                3,
                3,
                "Mechanical compatibility review and low-rate material-handling trial",
                "Stop the affected stream and restore the previous material path",
            ),
        ]
        for gap in candidate.missing_assets:
            raw.append(
                (
                    "plant design",
                    f"Required capability unavailable: {gap.asset_name}",
                    "Selected scenario assumes an asset or function that is missing or unevidenced",
                    gap.reason,
                    5 if gap.requirement == "required" else 4,
                    4,
                    2,
                    "Close the asset gap through verified existing capability or approved project scope",
                    "Do not begin the pilot until the capability is available",
                )
            )
        critical_unknowns = sum(item.criticality == "critical" for item in unknowns)
        if critical_unknowns:
            raw.append(
                (
                    "governance",
                    "Critical unknowns remain unresolved",
                    "Mandatory standard, safety or implementation evidence is absent",
                    "The recommendation cannot be defended or safely implemented",
                    5,
                    4,
                    4,
                    "Resolve all critical unknowns and rerun the engineering review",
                    "Reject or hold the proposed change",
                )
            )
        output: list[FailureMode] = []
        for discipline, mode, cause, consequence, severity, likelihood, detectability, mitigation, rollback in raw:
            output.append(
                FailureMode(
                    failure_mode_id=new_id("risk"),
                    discipline=discipline,
                    failure_mode=mode,
                    cause=cause,
                    consequence=consequence,
                    severity=severity,
                    likelihood=likelihood,
                    detectability=detectability,
                    risk_priority_number=severity * likelihood * detectability,
                    mitigation=mitigation,
                    rollback_trigger=rollback,
                )
            )
        return sorted(output, key=lambda item: item.risk_priority_number, reverse=True)

    def _committee_reviews(
        self,
        *,
        product: ProductDefinition | None,
        study: RetrofitStudyResult,
        candidate: RetrofitCandidate,
        evidence: Sequence[EvidenceRecord],
        unknowns: Sequence[UnknownInput],
        validation_plan: Sequence[ValidationRequirement],
        risks: Sequence[FailureMode],
    ) -> list[DisciplineReview]:
        evidence_classes = Counter(item.evidence_class for item in evidence)
        critical_unknowns = [item for item in unknowns if item.criticality == "critical"]
        high_unknowns = [item for item in unknowns if item.criticality == "high"]
        unavailable_validation = [
            item for item in validation_plan if item.blocking and item.availability == "unavailable"
        ]
        reviews: list[DisciplineReview] = []
        for definition in self.catalog.discipline_reviews:
            discipline = definition.discipline
            findings: list[str] = []
            blocking: list[str] = []
            status: ReviewStatus = "conditional"
            if discipline == "chemistry":
                if candidate.chemistry_complete:
                    findings.append("Reported oxide chemistry is complete for the candidate screening model.")
                else:
                    blocking.append("Candidate chemistry contains unknown fields.")
                    status = "hold"
                if any(item.category in {"materials", "quality"} and item.criticality in {"high", "critical"} for item in unknowns):
                    blocking.append("Representative chemistry or quality evidence remains unresolved.")
                    status = "hold"
            elif discipline == "mineralogy":
                if any("xrd" in item.item.lower() or "mineral" in item.item.lower() for item in unknowns):
                    blocking.append("Measured mineralogy/reactivity is not attached.")
                    status = "hold"
                else:
                    findings.append("Mineralogy evidence is present for review.")
                    status = "pass"
            elif discipline == "process":
                if candidate.route_compatibility_score >= 90 and not any(gap.requirement == "required" for gap in candidate.missing_assets):
                    findings.append("Route compatibility screening is high and no required process asset gap is declared.")
                    status = "pass"
                else:
                    blocking.append("Route or required process capability is not fully closed.")
                    status = "hold"
            elif discipline == "thermal":
                if any(item.category in {"thermal", "fuel"} and item.criticality in {"high", "critical"} for item in unknowns):
                    blocking.append("Fuel and/or heat-balance evidence is incomplete.")
                    status = "hold"
                else:
                    findings.append("Thermal evidence is adequate for controlled screening, not automatic setting changes.")
                    status = "conditional"
            elif discipline == "mechanical":
                if candidate.missing_assets:
                    blocking.extend(f"Capability gap: {item.asset_name}" for item in candidate.missing_assets if item.requirement == "required")
                    status = "hold" if blocking else "conditional"
                else:
                    findings.append("No explicit equipment gap was detected by the configured route screening.")
                    status = "conditional"
            elif discipline == "economics":
                if evidence_classes["user_assumption"] or evidence_classes["unknown"]:
                    blocking.append("Commercial basis contains assumed or unknown evidence.")
                    status = "hold"
                else:
                    findings.append("Commercial inputs have traceable evidence classes.")
                    status = "conditional"
            elif discipline == "quality":
                if product is None:
                    blocking.append("Configured product definition is not resolved.")
                    status = "hold"
                elif not any(item.evidence_class == "regulatory_or_standard" for item in evidence):
                    blocking.append("Applicable quality standard is not linked.")
                    status = "hold"
                else:
                    findings.append("Product definition and quality-standard evidence are linked.")
                    status = "conditional"
            elif discipline == "operations":
                if any(item.category == "operations" and item.criticality in {"high", "critical"} for item in unknowns):
                    blocking.append("Availability, downtime, shift or operating-history evidence is incomplete.")
                    status = "hold"
                else:
                    findings.append("Pilot and rollback workflow is available for operator review.")
                    status = "conditional"
            elif discipline == "safety":
                if unavailable_validation:
                    blocking.append("A blocking validation cannot be performed.")
                    status = "fail"
                elif critical_unknowns or any(item.risk_priority_number >= 80 for item in risks):
                    blocking.append("Critical unknown or high-priority risk remains open.")
                    status = "hold"
                else:
                    findings.append("No unmitigated critical safety gate was detected in the supplied evidence.")
                    status = "conditional"
            if status == "conditional" and not blocking and not high_unknowns:
                status = "pass"
            reviews.append(
                DisciplineReview(
                    discipline=discipline,
                    mandatory=definition.mandatory,
                    status=status,
                    findings=findings or definition.questions,
                    blocking_issues=blocking,
                    evidence_reviewed=[item.evidence_id for item in evidence if discipline in item.applies_to][:12],
                    approval_required_from=self._review_owner(discipline),
                )
            )
        return reviews

    def _scenario_assessments(
        self,
        study: RetrofitStudyResult,
        validation_plan: Sequence[ValidationRequirement],
    ) -> list[ScenarioAssessment]:
        assessments: list[ScenarioAssessment] = []
        blocking_validation = [item.measurement for item in validation_plan if item.blocking]
        for index, candidate in enumerate(study.candidates, 1):
            benefits = [
                f"Predicted output {candidate.predicted_output_tph:.2f} t/h" if candidate.predicted_output_tph is not None else "Output unresolved",
                f"Variable cost {candidate.total_variable_cost_inr_t:.2f} INR/t" if candidate.total_variable_cost_inr_t is not None else "Cost unresolved",
                f"Material CO2 {candidate.material_co2_kg_t:.2f} kg/t" if candidate.material_co2_kg_t is not None else "Carbon unresolved",
            ]
            downsides = [
                f"Retrofit complexity score {candidate.retrofit_complexity_score:.1f}/100",
                f"Required/recommended asset gaps: {len(candidate.missing_assets)}",
            ]
            probability = max(
                5.0,
                min(
                    95.0,
                    0.45 * candidate.robustness_score
                    + 0.30 * candidate.route_compatibility_score
                    + 0.25 * candidate.route_efficiency_score
                    - 5.0 * sum(item.requirement == "required" for item in candidate.missing_assets),
                ),
            )
            risk: RiskLevel = "low"
            if candidate.missing_assets or probability < 75:
                risk = "medium"
            if any(item.requirement == "required" for item in candidate.missing_assets) or probability < 55:
                risk = "high"
            assessments.append(
                ScenarioAssessment(
                    scenario_id=candidate.candidate_id,
                    name=candidate.name,
                    why_it_exists=(
                        "Deterministic solver retained this candidate after feasibility pruning, bounded search, "
                        "Pareto filtering and robustness screening."
                    ),
                    expected_benefit=benefits,
                    expected_downside=downsides,
                    probability_of_success_percent=round(probability, 1),
                    required_validation=blocking_validation[:12],
                    business_impact="Compare output, variable cost, implementation complexity and material availability against the baseline.",
                    engineering_impact=f"Clinker factor {candidate.clinker_factor_percent:.2f}% with {len(candidate.missing_assets)} declared asset gap(s).",
                    risk_level=risk,
                    rank=index,
                    recommended_for_pilot=False,
                )
            )
        return assessments

    def _decision_gate(
        self,
        *,
        confidence: float,
        evidence_coverage: float,
        validation_plan: Sequence[ValidationRequirement],
        unknowns: Sequence[UnknownInput],
        risks: Sequence[FailureMode],
        reviews: Sequence[DisciplineReview],
    ) -> DecisionGate:
        policy = self.catalog.decision_policy
        blocking: list[str] = []
        critical_unknowns = [item for item in unknowns if item.criticality == "critical"]
        high_risks = [item for item in risks if item.risk_priority_number >= 60]
        mandatory_not_passed = [
            item for item in reviews if item.mandatory and item.status not in {"pass", "conditional"}
        ]
        unconfirmed_validation = [
            item for item in validation_plan
            if item.blocking and item.availability in {"unavailable", "not_confirmed"}
        ]
        if confidence < policy.minimum_pilot_confidence_percent:
            blocking.append(
                f"Earned confidence {confidence:.1f}% is below the configured pilot threshold {policy.minimum_pilot_confidence_percent:.1f}%."
            )
        if evidence_coverage < policy.minimum_evidence_coverage_percent:
            blocking.append(
                f"Evidence coverage {evidence_coverage:.1f}% is below the configured threshold {policy.minimum_evidence_coverage_percent:.1f}%."
            )
        if len(critical_unknowns) > policy.maximum_critical_unknowns:
            blocking.append(f"{len(critical_unknowns)} critical unknown input(s) remain unresolved.")
        if len(high_risks) > policy.maximum_high_risks:
            blocking.append(f"{len(high_risks)} high-priority risk(s) remain open.")
        if policy.require_all_mandatory_reviews and mandatory_not_passed:
            blocking.append(
                "Mandatory committee reviews not cleared: "
                + ", ".join(item.discipline for item in mandatory_not_passed)
            )
        if policy.require_validation_plan and unconfirmed_validation:
            blocking.append(
                f"{len(unconfirmed_validation)} blocking validation activity/activities are not confirmed available."
            )

        validation_unavailable = any(
            item.blocking and item.availability == "unavailable" for item in validation_plan
        )
        safety_failed = any(item.discipline == "safety" and item.status == "fail" for item in reviews)
        if validation_unavailable or safety_failed:
            decision: GateDecision = "reject"
            reason = "Implementation is refused because required validation or safety review cannot be completed."
        elif blocking:
            decision = "hold_for_validation"
            reason = "No production change is authorised. Close the listed evidence, review and validation gates first."
        elif policy.production_change_requires_approved_pilot:
            decision = "proceed_to_pilot"
            reason = "The case is eligible for a controlled pilot only; production scale-up still requires approved pilot evidence."
        else:
            decision = "proceed_to_pilot"
            reason = "The configured governance policy permits a controlled pilot after approvals."
        return DecisionGate(
            decision=decision,
            production_change_authorised=False,
            pilot_authorised=decision == "proceed_to_pilot",
            reason=reason,
            blocking_conditions=blocking,
            conditions_to_advance=[
                "Resolve every critical unknown and attach traceable evidence.",
                "Confirm availability and acceptance tolerances for every blocking validation.",
                "Close mandatory discipline reviews and sign-offs.",
                "Execute the controlled pilot with product hold, monitoring and rollback readiness.",
                "Approve scale-up only after prediction error and root-cause review.",
            ],
            rollback_required=True,
            approval_requirements=[
                "Process/Production Engineer",
                "Quality Head",
                "Plant Head",
                "Safety/Environment representative where the change affects process safety or emissions",
            ],
        )

    def _trust_questions(
        self,
        *,
        evidence: Sequence[EvidenceRecord],
        assumptions: Sequence[CriticalAssumption],
        unknowns: Sequence[UnknownInput],
        validation_plan: Sequence[ValidationRequirement],
        traceability: float,
    ) -> list[TrustQuestionAnswer]:
        known = [item for item in evidence if item.status == "known"]
        return [
            TrustQuestionAnswer(
                question="What do we know?",
                answer=f"{len(known)} evidence item(s) are classified as measured, laboratory, validated historical, vendor-guaranteed or regulatory evidence.",
                status="adequate" if known else "inadequate",
                supporting_ids=[item.evidence_id for item in known[:20]],
            ),
            TrustQuestionAnswer(
                question="What assumptions were made?",
                answer=f"{len(assumptions)} explicit engineering assumption(s) are registered with consequences and replacement data.",
                status="adequate" if assumptions else "partial",
                supporting_ids=[item.assumption_id for item in assumptions[:20]],
            ),
            TrustQuestionAnswer(
                question="What is uncertain?",
                answer=f"{len(unknowns)} unknown or insufficiently evidenced input(s) remain; {sum(item.criticality == 'critical' for item in unknowns)} are critical.",
                status="inadequate" if any(item.criticality == "critical" for item in unknowns) else "partial",
                supporting_ids=[item.input_id for item in unknowns[:20]],
            ),
            TrustQuestionAnswer(
                question="What evidence supports this prediction?",
                answer=f"{len(evidence)} evidence record(s) are linked and calculation traceability is {traceability:.1f}%.",
                status="adequate" if evidence and traceability >= 70 else "partial",
                supporting_ids=[item.evidence_id for item in evidence[:20]],
            ),
            TrustQuestionAnswer(
                question="What must be validated before implementation?",
                answer=f"{len(validation_plan)} validation requirement(s) are generated; {sum(item.blocking for item in validation_plan)} are blocking.",
                status="adequate" if validation_plan else "inadequate",
                supporting_ids=[item.validation_id for item in validation_plan[:20]],
            ),
        ]

    def _evidence_coverage(self, evidence: Sequence[EvidenceRecord]) -> float:
        if not evidence:
            return 0.0
        weighted = sum(item.quality_score_percent for item in evidence)
        coverage = weighted / len(evidence)
        diversity = len({item.evidence_class for item in evidence})
        coverage += min(10.0, diversity * 1.5)
        return round(min(100.0, coverage), 1)

    @staticmethod
    def _data_completeness(unknowns: Sequence[UnknownInput]) -> float:
        penalty = sum(
            {"low": 1.0, "medium": 2.5, "high": 5.0, "critical": 12.0}[item.criticality]
            for item in unknowns
        )
        return round(max(0.0, 100.0 - penalty), 1)

    @staticmethod
    def _traceability(
        calculation_trace_count: int,
        predictions: Sequence[PredictionLike],
        evidence: Sequence[EvidenceRecord],
    ) -> float:
        prediction_trace = (
            sum(bool(item.source_basis) and bool(item.required_validation) for item in predictions)
            / len(predictions)
            * 60.0
            if predictions
            else 0.0
        )
        calculation = min(25.0, calculation_trace_count * 2.5)
        evidence_link = min(15.0, len(evidence) * 0.75)
        return round(min(100.0, prediction_trace + calculation + evidence_link), 1)

    @staticmethod
    def _validation_readiness(plan: Sequence[ValidationRequirement]) -> float:
        if not plan:
            return 0.0
        score_map = {"available": 100.0, "partial": 65.0, "not_confirmed": 35.0, "unavailable": 0.0}
        weighted = 0.0
        total = 0.0
        for item in plan:
            weight = 2.0 if item.blocking else 1.0
            weighted += score_map[item.availability] * weight
            total += weight
        return round(weighted / total if total else 0.0, 1)

    @staticmethod
    def _earned_confidence(
        *,
        candidate: RetrofitCandidate,
        evidence_coverage: float,
        completeness: float,
        traceability: float,
        validation_readiness: float,
        calibration_samples: int,
        unknowns: Sequence[UnknownInput],
        risks: Sequence[FailureMode],
    ) -> float:
        score = (
            0.24 * evidence_coverage
            + 0.18 * completeness
            + 0.16 * traceability
            + 0.14 * validation_readiness
            + 0.12 * candidate.robustness_score
            + 0.08 * candidate.route_compatibility_score
            + 0.08 * candidate.route_efficiency_score
        )
        score += min(8.0, calibration_samples * 1.5)
        score -= 10.0 * sum(item.criticality == "critical" for item in unknowns)
        score -= 3.0 * sum(item.criticality == "high" for item in unknowns)
        score -= 5.0 * sum(item.risk_priority_number >= 80 for item in risks)
        return round(max(5.0, min(95.0, score)), 1)

    @staticmethod
    def _band(score: float) -> Literal["low", "medium", "high"]:
        if score >= 80:
            return "high"
        if score >= 55:
            return "medium"
        return "low"

    @staticmethod
    def _canonical_evidence_class(value: str) -> str:
        needle = value.strip().lower()
        aliases = {
            "measured": "plant_measurement",
            "plant": "plant_measurement",
            "lab": "laboratory_result",
            "laboratory": "laboratory_result",
            "vendor": "vendor_guarantee",
            "project": "project_engineering",
            "standard": "regulatory_or_standard",
            "reference": "reference_engineering",
            "assumed": "user_assumption",
            "unverified": "user_assumption",
        }
        canonical = aliases.get(needle, needle)
        allowed = {
            "plant_measurement",
            "laboratory_result",
            "validated_historical",
            "vendor_guarantee",
            "project_engineering",
            "regulatory_or_standard",
            "peer_reviewed",
            "reference_engineering",
            "user_assumption",
            "unknown",
        }
        return canonical if canonical in allowed else "user_assumption"

    @staticmethod
    def _validation_owner(category: str) -> str:
        lower = category.lower()
        if any(token in lower for token in ("quality", "product", "chemistry", "formulation")):
            return "Quality Laboratory / Quality Head"
        if any(token in lower for token in ("thermal", "fuel", "energy")):
            return "Process / Thermal Engineer"
        if any(token in lower for token in ("mechanical", "plant design", "capacity")):
            return "Mechanical / Project Engineer"
        if any(token in lower for token in ("cost", "economics", "commercial")):
            return "Cost Engineer / Commercial Owner"
        return "Process / Production Engineer"

    @staticmethod
    def _review_owner(discipline: str) -> str:
        mapping = {
            "chemistry": "Chief Chemist / Process Quality",
            "mineralogy": "Mineralogist / Laboratory Head",
            "process": "Process Head",
            "thermal": "Thermal / Pyroprocess Engineer",
            "mechanical": "Mechanical Head",
            "economics": "Cost Engineer / Finance representative",
            "quality": "Quality Head",
            "operations": "Production Head / Shift leadership",
            "safety": "Plant Safety and Environment authority",
        }
        return mapping.get(discipline, "Responsible discipline owner")
