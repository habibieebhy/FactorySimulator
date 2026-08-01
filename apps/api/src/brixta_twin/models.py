from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class Evidence(BaseModel):
    evidence_class: str
    source_title: str
    source_uri: str | None = None
    page: str | None = None
    note: str | None = None


class Chemistry(BaseModel):
    cao: float = Field(ge=0, le=100)
    sio2: float = Field(ge=0, le=100)
    al2o3: float = Field(ge=0, le=100)
    fe2o3: float = Field(ge=0, le=100)
    mgo: float = Field(0, ge=0, le=100)
    so3: float = Field(0, ge=0, le=100)
    na2o: float = Field(0, ge=0, le=100)
    k2o: float = Field(0, ge=0, le=100)
    loi: float = Field(0, ge=0, le=100)


class MaterialCreate(BaseModel):
    name: str
    material_type: str
    location: str | None = None
    processing_state: str = "as_received"
    applicable_blend_classes: list[str] = Field(default_factory=list)
    chemistry: Chemistry
    cost_inr_per_t: float | None = Field(None, ge=0)
    co2_kg_per_t: float | None = Field(None, ge=0)
    notes: str | None = None
    data_gaps: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)


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
    evidence: list[Evidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def stable_load_valid(self) -> "MachineBase":
        if self.minimum_stable_tph > self.rated_capacity_tph:
            raise ValueError("Minimum stable capacity exceeds rated capacity")
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


class MaterialCostEntry(BaseModel):
    material_id: str
    purchased_delivered_cost_inr_t: float | None = Field(None, ge=0)
    internal_feed_cost_inr_t: float | None = Field(None, ge=0)
    evidence_class: str = "assumed"
    note: str | None = None


class CostBookCreate(BaseModel):
    name: str
    effective_date: str | None = None
    currency: str = "INR"
    electricity_inr_kwh: float | None = Field(None, ge=0)
    thermal_fuel_inr_mkcal: float | None = Field(None, ge=0)
    packing_inr_t: float | None = Field(None, ge=0)
    labour_inr_t: float | None = Field(None, ge=0)
    maintenance_inr_t: float | None = Field(None, ge=0)
    other_variable_inr_t: float | None = Field(None, ge=0)
    factory_overhead_inr_t: float | None = Field(None, ge=0)
    outbound_logistics_inr_t: float | None = Field(None, ge=0)
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


class RunRequest(BaseModel):
    blend_id: str
    route_id: str
    cost_book_id: str | None = None
    target_output_tph: float = Field(gt=0)
    duration_hours: float = Field(24, gt=0)
    electricity_inr_kwh: float = Field(8.5, ge=0)
    thermal_fuel_inr_mkcal: float = Field(900, ge=0)
    raw_meal_to_clinker_yield: float = Field(0.65, gt=0, le=1)


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
    throughput_factor_t_stage_per_t_cement: float
    actual_throughput_tph: float
    effective_capacity_tph: float
    cement_equivalent_capacity_tph: float | None
    load_percent: float
    electricity_kwh_t_cement: float
    thermal_kcal_kg_cement: float


class MaterialRunMetric(BaseModel):
    material_id: str
    material_name: str
    material_type: str
    percentage: float
    tonnes_per_hour: float
    tonnes_per_run: float
    applied_unit_cost_inr_t: float | None = None
    cost_basis: str = "unknown"
    cost_inr_t_cement: float | None
    co2_kg_t_cement: float | None
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
    calculation_version: str = "0.4.0"
    blend_snapshot: Blend | None = None
    route_snapshot: Route | None = None
    cost_book_snapshot: CostBook | None = None
    material_snapshots: list[Material] = Field(default_factory=list)
    machine_snapshots: list[Machine] = Field(default_factory=list)
    chemistry: Chemistry
    lsf: float | None
    silica_modulus: float | None
    alumina_modulus: float | None
    bottleneck_tph: float
    bottleneck_machine_id: str | None = None
    bottleneck_machine_name: str | None = None
    achievable_output_tph: float
    total_output_tonnes: float = 0
    electricity_kwh_t: float
    thermal_kcal_kg: float
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


def now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"
