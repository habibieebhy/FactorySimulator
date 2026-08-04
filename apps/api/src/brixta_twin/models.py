from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, Field, model_validator


class Evidence(BaseModel):
    evidence_class: str
    source_title: str
    source_uri: str | None = None
    page: str | None = None
    note: str | None = None


class Chemistry(BaseModel):
    """Oxide mass percentages.

    ``None`` means unreported/unknown.  A numeric zero is therefore reserved
    for a genuinely measured or sourced zero.  This distinction prevents a
    missing alkali or SO3 result from silently improving a candidate recipe.
    """

    cao: float | None = Field(default=None, ge=0, le=100)
    sio2: float | None = Field(default=None, ge=0, le=100)
    al2o3: float | None = Field(default=None, ge=0, le=100)
    fe2o3: float | None = Field(default=None, ge=0, le=100)
    mgo: float | None = Field(default=None, ge=0, le=100)
    so3: float | None = Field(default=None, ge=0, le=100)
    na2o: float | None = Field(default=None, ge=0, le=100)
    k2o: float | None = Field(default=None, ge=0, le=100)
    loi: float | None = Field(default=None, ge=0, le=100)


FunctionalRole = Literal[
    "raw_kiln_feed",
    "corrective",
    "clinker",
    "cement_addition",
    "set_regulator",
    "process_additive",
    "fuel",
    "alternative_fuel",
    "fuel_ash",
    "recycled_process_material",
]


class MaterialCreate(BaseModel):
    name: str
    material_type: str
    functional_role: FunctionalRole = "cement_addition"
    custom_subtype: str | None = None
    location: str | None = None
    processing_state: str = "as_received"
    applicable_blend_classes: list[str] = Field(default_factory=list)
    chemistry: Chemistry
    chemistry_min: Chemistry | None = None
    chemistry_max: Chemistry | None = None
    moisture_percent: float | None = Field(default=None, ge=0, le=100)
    grindability_factor: float | None = Field(default=None, gt=0)
    fuel_ash_percent: float | None = Field(default=None, ge=0, le=100)
    fuel_calorific_value_kcal_kg: float | None = Field(default=None, gt=0)
    fuel_ash_chemistry: Chemistry | None = None
    cost_inr_per_t: float | None = Field(default=None, ge=0)
    co2_kg_per_t: float | None = Field(default=None, ge=0)
    notes: str | None = None
    data_gaps: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def infer_legacy_role(self) -> "MaterialCreate":
        """Classify V0.4/seed payloads that pre-date functional roles."""

        if self.functional_role != "cement_addition":
            return self
        if self.material_type == "clinker":
            self.functional_role = "clinker"
        elif self.material_type == "gypsum":
            self.functional_role = "set_regulator"
        elif self.material_type in {"coal", "petcoke"}:
            self.functional_role = "fuel"
        elif self.material_type in {"biomass", "rdf", "alternative_fuel"}:
            self.functional_role = "alternative_fuel"
        elif self.material_type in {"silica_corrective", "iron_corrective", "bauxite", "laterite", "sand"}:
            self.functional_role = "corrective"
        elif "raw_meal" in self.applicable_blend_classes and "finished_cement" not in self.applicable_blend_classes:
            self.functional_role = "raw_kiln_feed"
        return self

    @model_validator(mode="after")
    def chemistry_ranges_are_ordered(self) -> "MaterialCreate":
        for oxide in Chemistry.model_fields:
            typical = getattr(self.chemistry, oxide)
            low = getattr(self.chemistry_min, oxide) if self.chemistry_min else None
            high = getattr(self.chemistry_max, oxide) if self.chemistry_max else None
            if low is not None and high is not None and low > high:
                raise ValueError(f"{oxide.upper()} minimum exceeds maximum")
            if typical is not None and low is not None and low > typical:
                raise ValueError(f"{oxide.upper()} minimum exceeds typical value")
            if typical is not None and high is not None and high < typical:
                raise ValueError(f"{oxide.upper()} maximum is below typical value")
        return self


class Material(MaterialCreate):
    material_id: str
    version: int = 1
    lineage_id: str | None = None
    archived: bool = False
    archived_at: datetime | None = None
    created_at: datetime


BlendClass = Literal[
    "raw_material_stockpile",
    "raw_meal",
    "fuel_blend",
    "clinker_blend",
    "finished_cement",
    "premix",
]


class BlendComponent(BaseModel):
    """One direct blend component.

    The optional-id shape preserves compatibility with V1 payloads, which only
    contained ``material_id``. New payloads explicitly declare whether the
    component is a material or another immutable blend version.
    """

    component_type: Literal["material", "blend"] = "material"
    material_id: str | None = None
    blend_id: str | None = None
    percentage: float = Field(gt=0, le=100)

    @model_validator(mode="after")
    def exactly_one_reference(self) -> "BlendComponent":
        if self.component_type == "material":
            if not self.material_id or self.blend_id:
                raise ValueError("Material components require material_id only")
        elif not self.blend_id or self.material_id:
            raise ValueError("Blend components require blend_id only")
        return self

    @property
    def reference_id(self) -> str:
        if self.component_type == "material":
            assert self.material_id is not None
            return self.material_id
        assert self.blend_id is not None
        return self.blend_id


class BlendCreate(BaseModel):
    name: str
    blend_class: BlendClass = "finished_cement"
    family: str = "Custom"
    objective: str = "reproduce_reference"
    applicable_standard: str | None = None
    components: list[BlendComponent] = Field(min_length=1)
    evidence: list[Evidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def total_is_one_hundred(self) -> "BlendCreate":
        total = sum(item.percentage for item in self.components)
        if abs(total - 100) > 0.01:
            raise ValueError(f"Blend totals {total:.2f}%; expected 100.00%")
        direct_references = [
            (item.component_type, item.reference_id) for item in self.components
        ]
        if len(direct_references) != len(set(direct_references)):
            raise ValueError("Duplicate direct components must be merged into one row")
        return self


class Blend(BlendCreate):
    blend_id: str
    version: int = 1
    status: str = "simulated"
    lineage_id: str | None = None
    archived: bool = False
    archived_at: datetime | None = None
    created_at: datetime


class ResolvedBlendComponent(BaseModel):
    material_id: str
    material_name: str
    material_type: str
    percentage: float
    evidence_class: str
    material_version: int = 1


class BlendPreview(BaseModel):
    blend_name: str
    blend_class: BlendClass
    direct_total_percentage: float
    flattened_total_percentage: float
    flattened_components: list[ResolvedBlendComponent]
    chemistry: Chemistry
    chemistry_scenario: Literal["low", "typical", "high"] = "typical"
    chemistry_complete: bool = False
    unknown_chemistry_fields: list[str] = Field(default_factory=list)
    material_cost_inr_t: float | None
    estimated_co2_kg_t: float | None
    warnings: list[str] = Field(default_factory=list)


class MachineBase(BaseModel):
    name: str
    process_stage: str
    rated_capacity_tph: float = Field(gt=0)
    minimum_stable_tph: float = Field(0, ge=0)
    availability: float = Field(0.92, gt=0, le=1)
    specific_electricity_kwh_t: float = Field(0, ge=0)
    specific_heat_kcal_kg: float = Field(0, ge=0)
    capex_inr_crore: float = Field(0, ge=0)
    technology_readiness_level: int = Field(9, ge=1, le=9)
    maximum_stable_tph: float | None = Field(default=None, gt=0)
    design_blaine_m2_kg: float | None = Field(default=None, gt=0)
    maximum_feed_moisture_percent: float | None = Field(default=None, ge=0, le=100)
    minimum_temperature_c: float | None = Field(default=None, gt=0)
    minimum_oxygen_percent: float | None = Field(default=None, ge=0, le=25)
    maximum_oxygen_percent: float | None = Field(default=None, ge=0, le=25)
    maximum_free_lime_percent: float | None = Field(default=None, ge=0, le=20)
    evidence: list[Evidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def stable_load_valid(self) -> "MachineBase":
        if self.minimum_stable_tph > self.rated_capacity_tph:
            raise ValueError("Minimum stable capacity exceeds rated capacity")
        if self.maximum_stable_tph is not None and self.maximum_stable_tph < self.minimum_stable_tph:
            raise ValueError("Maximum stable capacity is below minimum stable capacity")
        if (
            self.minimum_oxygen_percent is not None
            and self.maximum_oxygen_percent is not None
            and self.minimum_oxygen_percent > self.maximum_oxygen_percent
        ):
            raise ValueError("Minimum oxygen exceeds maximum oxygen")
        return self


class StandardMachineCreate(MachineBase):
    machine_kind: Literal["standard"] = "standard"
    input_material: str = "solid"
    output_material: str = "solid"


class ThermalMachineCreate(MachineBase):
    machine_kind: Literal["thermal"] = "thermal"
    maximum_temperature_c: float = Field(gt=0)
    residence_time_minutes: float = Field(gt=0)
    conversion_fraction: float = Field(gt=0, le=1)
    product_state: str = "clinker"


MachineCreate = Annotated[StandardMachineCreate | ThermalMachineCreate, Field(discriminator="machine_kind")]


class Machine(MachineBase):
    machine_id: str
    machine_kind: str
    input_material: str | None = None
    output_material: str | None = None
    maximum_temperature_c: float | None = None
    residence_time_minutes: float | None = None
    conversion_fraction: float | None = None
    product_state: str | None = None
    version: int = 1
    lineage_id: str | None = None
    archived: bool = False
    archived_at: datetime | None = None
    created_at: datetime


class RouteNode(BaseModel):
    node_id: str
    machine_id: str
    label: str
    position_x: float
    position_y: float


class RouteEdge(BaseModel):
    edge_id: str
    source: str
    target: str
    stream_type: str = "material"


class RouteCreate(BaseModel):
    name: str
    route_kind: Literal[
        "integrated",
        "grinding_only",
        "integrated_lc3",
        "clinker_only",
        "custom",
    ] = "custom"
    nodes: list[RouteNode]
    edges: list[RouteEdge]


class Route(RouteCreate):
    route_id: str
    version: int = 1
    lineage_id: str | None = None
    archived: bool = False
    archived_at: datetime | None = None
    created_at: datetime


class RouteAnalysis(BaseModel):
    route_id: str
    route_name: str
    route_kind: str
    description: str
    flow_summary: str
    compatible: bool
    compatibility_score: float = Field(ge=0, le=100)
    predicted_output_tph: float | None = None
    bottleneck_machine_name: str | None = None
    required_stages: list[str] = Field(default_factory=list)
    present_stages: list[str] = Field(default_factory=list)
    missing_stages: list[str] = Field(default_factory=list)
    extra_stages: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class RouteRecommendationSet(BaseModel):
    blend_id: str
    target_output_tph: float
    selected_route_id: str | None = None
    selected: RouteAnalysis | None = None
    recommendations: list[RouteAnalysis] = Field(default_factory=list)


class MaterialCostEntry(BaseModel):
    material_id: str
    purchased_delivered_cost_inr_t: float | None = Field(default=None, ge=0)
    internal_feed_cost_inr_t: float | None = Field(default=None, ge=0)
    evidence_class: str = "assumed"
    note: str | None = None


class CostBookCreate(BaseModel):
    name: str
    effective_date: str | None = None
    currency: str = "INR"
    electricity_inr_kwh: float | None = Field(default=None, ge=0)
    thermal_fuel_inr_mkcal: float | None = Field(default=None, ge=0)
    packing_inr_t: float | None = Field(default=None, ge=0)
    labour_inr_t: float | None = Field(default=None, ge=0)
    maintenance_inr_t: float | None = Field(default=None, ge=0)
    other_variable_inr_t: float | None = Field(default=None, ge=0)
    factory_overhead_inr_t: float | None = Field(default=None, ge=0)
    outbound_logistics_inr_t: float | None = Field(default=None, ge=0)
    clinker_labour_inr_t: float | None = Field(default=None, ge=0)
    clinker_maintenance_inr_t: float | None = Field(default=None, ge=0)
    clinker_other_variable_inr_t: float | None = Field(default=None, ge=0)
    clinker_factory_overhead_inr_t: float | None = Field(default=None, ge=0)
    material_costs: list[MaterialCostEntry] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    notes: str | None = None


class CostBook(CostBookCreate):
    cost_book_id: str
    version: int = 1
    lineage_id: str | None = None
    archived: bool = False
    archived_at: datetime | None = None
    created_at: datetime


ChemistryScenario = Literal["low", "typical", "high"]


class QualityMeasurements(BaseModel):
    """Measured cement results used by the OPC 43 production gate.

    The twin never invents strength or setting-time values.  Blank fields stay
    untested and keep the gate at REVIEW rather than being treated as a pass.
    """

    blaine_m2_kg: float | None = Field(default=None, gt=0)
    initial_setting_minutes: float | None = Field(default=None, ge=0)
    final_setting_minutes: float | None = Field(default=None, ge=0)
    le_chatelier_mm: float | None = Field(default=None, ge=0)
    autoclave_expansion_percent: float | None = Field(default=None, ge=0)
    strength_3d_mpa: float | None = Field(default=None, ge=0)
    strength_7d_mpa: float | None = Field(default=None, ge=0)
    strength_28d_mpa: float | None = Field(default=None, ge=0)


class QualityCheck(BaseModel):
    metric: str
    measured: float | None
    requirement: str
    status: Literal["pass", "fail", "not_tested"]


class QualityGate(BaseModel):
    standard: str = "IS 269:2015 — OPC 43 grade screening"
    status: Literal["pass", "fail", "review"]
    checks: list[QualityCheck] = Field(default_factory=list)
    note: str = "Laboratory test results are required; simulation chemistry alone cannot certify cement."


class RunRequest(BaseModel):
    blend_id: str
    route_id: str
    cost_book_id: str | None = None
    target_output_tph: float = Field(gt=0)
    duration_hours: float = Field(24, gt=0)
    electricity_inr_kwh: float = Field(8.5, ge=0)
    thermal_fuel_inr_mkcal: float = Field(900, ge=0)
    raw_meal_to_clinker_yield: float = Field(0.65, gt=0, le=1)
    auto_mass_conversion: bool = True
    chemistry_scenario: ChemistryScenario = "typical"
    target_blaine_m2_kg: float | None = Field(default=None, gt=0)
    fuel_material_id: str | None = None
    fuel_rate_kg_t_clinker: float | None = Field(default=None, ge=0)
    kiln_feed_moisture_percent: float | None = Field(default=None, ge=0, le=100)
    kiln_oxygen_percent: float | None = Field(default=None, ge=0, le=25)
    kiln_temperature_c: float | None = Field(default=None, gt=0)
    clinker_free_lime_percent: float | None = Field(default=None, ge=0, le=20)
    quality_measurements: QualityMeasurements | None = None


class RawMixMaterialConstraint(BaseModel):
    material_id: str
    minimum_percent: float = Field(0, ge=0, le=100)
    maximum_percent: float = Field(100, ge=0, le=100)

    @model_validator(mode="after")
    def valid_range(self) -> "RawMixMaterialConstraint":
        if self.minimum_percent > self.maximum_percent:
            raise ValueError("Raw-mix minimum exceeds maximum")
        return self


class RawMixOptimisationRequest(BaseModel):
    materials: list[RawMixMaterialConstraint] = Field(min_length=2)
    target_lsf: float = Field(95, gt=0)
    target_sm: float = Field(2.5, gt=0)
    target_am: float = Field(1.5, gt=0)
    chemistry_scenario: ChemistryScenario = "typical"

    @model_validator(mode="after")
    def material_constraints_are_unique(self) -> "RawMixOptimisationRequest":
        material_ids = [item.material_id for item in self.materials]
        if len(material_ids) != len(set(material_ids)):
            raise ValueError("Each raw-mix material may appear only once")
        return self


class RawMixSuggestion(BaseModel):
    material_id: str
    material_name: str
    percentage: float


class RawMixOptimisationResult(BaseModel):
    feasible: bool
    suggestions: list[RawMixSuggestion]
    chemistry: Chemistry
    lsf: float | None
    silica_modulus: float | None
    alumina_modulus: float | None
    estimated_clinker_yield: float | None
    objective_error: float
    warnings: list[str] = Field(default_factory=list)


class RunEvent(BaseModel):
    sequence: int
    elapsed_seconds: float
    level: str
    component: str
    message: str


class ValidationMessage(BaseModel):
    severity: Literal["block", "warning", "info"]
    code: str
    message: str


class AssumptionRecord(BaseModel):
    key: str
    value: str
    basis: str


class MachineRunMetric(BaseModel):
    node_id: str
    machine_id: str
    machine_name: str
    process_stage: str
    throughput_factor_t_stage_per_t_output: float = Field(
        validation_alias=AliasChoices(
            "throughput_factor_t_stage_per_t_output",
            "throughput_factor_t_stage_per_t_cement",
        )
    )
    actual_throughput_tph: float
    effective_capacity_tph: float
    output_equivalent_capacity_tph: float | None = Field(
        validation_alias=AliasChoices(
            "output_equivalent_capacity_tph",
            "cement_equivalent_capacity_tph",
        )
    )
    target_throughput_tph: float = 0
    target_load_percent: float = 0
    load_percent: float
    electricity_kwh_t_output: float = Field(
        validation_alias=AliasChoices(
            "electricity_kwh_t_output",
            "electricity_kwh_t_cement",
        )
    )
    thermal_kcal_kg_output: float = Field(
        validation_alias=AliasChoices(
            "thermal_kcal_kg_output",
            "thermal_kcal_kg_cement",
        )
    )


class MaterialRunMetric(BaseModel):
    material_id: str
    material_name: str
    material_type: str
    percentage: float
    tonnes_per_t_output: float | None = None
    tonnes_per_hour: float
    tonnes_per_run: float
    applied_unit_cost_inr_t: float | None = None
    cost_basis: str = "unknown"
    cost_inr_t_output: float | None = Field(
        validation_alias=AliasChoices("cost_inr_t_output", "cost_inr_t_cement")
    )
    co2_kg_t_output: float | None = Field(
        validation_alias=AliasChoices("co2_kg_t_output", "co2_kg_t_cement")
    )
    evidence_class: str


class CostBreakdown(BaseModel):
    materials_inr_t: float | None
    electricity_inr_t: float
    thermal_inr_t: float
    energy_inr_t: float
    direct_model_cost_inr_t: float | None
    packing_inr_t: float | None = None
    labour_inr_t: float | None = None
    maintenance_inr_t: float | None = None
    other_variable_inr_t: float | None = None
    plant_cash_cost_inr_t: float | None = None
    factory_overhead_inr_t: float | None = None
    outbound_logistics_inr_t: float | None = None
    full_cost_inr_t: float | None = None
    cost_book_name: str | None = None
    operating_cost_basis: str = "legacy/unspecified allocation"
    included_costs: list[str] = Field(default_factory=list)
    excluded_costs: list[str] = Field(default_factory=list)


class EnergyBreakdown(BaseModel):
    electricity_kwh_t: float
    thermal_kcal_kg: float
    total_electricity_mwh: float
    total_thermal_gcal: float


class CarbonBreakdown(BaseModel):
    materials_kg_co2_t: float | None
    total_materials_tonnes: float
    total_materials_kg_co2: float | None
    exclusions: list[str] = Field(default_factory=list)


class RunResult(BaseModel):
    run_id: str
    created_at: datetime
    request: RunRequest
    calculation_version: str = "0.6.0"
    run_status: Literal["completed", "blocked"] = "completed"
    output_product: str = "cement"
    blend_snapshot: Blend | None = None
    route_snapshot: Route | None = None
    cost_book_snapshot: CostBook | None = None
    material_snapshots: list[Material] = Field(default_factory=list)
    machine_snapshots: list[Machine] = Field(default_factory=list)
    chemistry: Chemistry
    chemistry_scenario: ChemistryScenario = "typical"
    route_analysis: RouteAnalysis | None = None
    quality_gate: QualityGate | None = None
    derived_raw_meal_to_clinker_yield: float | None = None
    fuel_ash_contribution_kg_t_clinker: float | None = None
    fuel_ash_adjusted_chemistry: Chemistry | None = None
    grinding_capacity_factor: float = 1.0
    grinding_energy_factor: float = 1.0
    lsf: float | None
    silica_modulus: float | None
    alumina_modulus: float | None
    bottleneck_tph: float
    bottleneck_machine_id: str | None = None
    bottleneck_machine_name: str | None = None
    achievable_output_tph: float
    total_output_tonnes: float = 0
    material_input_t_per_t_output: float | None = None
    total_material_input_tph: float | None = None
    total_material_input_tonnes: float | None = None
    electricity_kwh_t: float
    thermal_kcal_kg: float
    applied_electricity_inr_kwh: float | None = None
    electricity_tariff_source: str = "legacy run; not recorded"
    applied_thermal_fuel_inr_mkcal: float | None = None
    thermal_tariff_source: str = "legacy run; not recorded"
    material_cost_inr_t: float | None
    energy_cost_inr_t: float
    direct_model_cost_inr_t: float | None = None
    estimated_co2_kg_t: float | None
    resolved_components: list[ResolvedBlendComponent] = Field(default_factory=list)
    material_metrics: list[MaterialRunMetric] = Field(default_factory=list)
    machine_metrics: list[MachineRunMetric] = Field(default_factory=list)
    cost_breakdown: CostBreakdown | None = None
    energy_breakdown: EnergyBreakdown | None = None
    carbon_breakdown: CarbonBreakdown | None = None
    validation: list[ValidationMessage] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    information: list[str] = Field(default_factory=list)
    assumptions: list[AssumptionRecord] = Field(default_factory=list)
    evidence_references: list[Evidence] = Field(default_factory=list)
    events: list[RunEvent] = Field(default_factory=list)


class CalibrationCreate(BaseModel):
    run_id: str
    actual_output_tph: float | None = Field(default=None, gt=0)
    actual_electricity_kwh_t: float | None = Field(default=None, ge=0)
    actual_thermal_kcal_kg: float | None = Field(default=None, ge=0)
    actual_direct_cost_inr_t: float | None = Field(default=None, ge=0)
    actual_co2_kg_t: float | None = Field(default=None, ge=0)
    source_title: str
    source_uri: str | None = None
    note: str | None = None


class CalibrationError(BaseModel):
    metric: str
    simulated: float | None
    actual: float | None
    absolute_error: float | None
    percent_error: float | None


class CalibrationRecord(CalibrationCreate):
    calibration_id: str
    created_at: datetime
    errors: list[CalibrationError] = Field(default_factory=list)


def now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"
