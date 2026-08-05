from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any

from pydantic import BaseModel, Field


class ProductDefinition(BaseModel):
    product_id: str
    name: str
    family: str
    description: str
    required_material_roles: list[str] = Field(default_factory=list)
    optional_material_roles: list[str] = Field(default_factory=list)
    required_process_capabilities: list[str] = Field(default_factory=list)
    required_validation: list[str] = Field(default_factory=list)
    default_quality_standard_ids: list[str] = Field(default_factory=list)


class DisciplineReviewDefinition(BaseModel):
    discipline: str
    mandatory: bool = True
    questions: list[str] = Field(default_factory=list)


class EvidenceClassDefinition(BaseModel):
    evidence_class: str
    base_quality: float = Field(ge=0, le=1)


class DecisionPolicy(BaseModel):
    minimum_pilot_confidence_percent: float = Field(default=70, ge=0, le=100)
    minimum_evidence_coverage_percent: float = Field(default=60, ge=0, le=100)
    maximum_critical_unknowns: int = Field(default=0, ge=0)
    maximum_high_risks: int = Field(default=2, ge=0)
    require_validation_plan: bool = True
    require_all_mandatory_reviews: bool = True
    production_change_requires_approved_pilot: bool = True


class EngineeringCatalog(BaseModel):
    catalog_version: str
    product_definitions: list[ProductDefinition] = Field(default_factory=list)
    discipline_reviews: list[DisciplineReviewDefinition] = Field(default_factory=list)
    evidence_classes: list[EvidenceClassDefinition] = Field(default_factory=list)
    decision_policy: DecisionPolicy = Field(default_factory=DecisionPolicy)

    def product(self, product_id_or_name: str | None) -> ProductDefinition | None:
        if not product_id_or_name:
            return None
        needle = product_id_or_name.strip().lower()
        for item in self.product_definitions:
            if item.product_id.lower() == needle or item.name.lower() == needle:
                return item
        for item in self.product_definitions:
            if needle in item.name.lower() or needle in item.product_id.lower():
                return item
        return None

    def evidence_quality(self, evidence_class: str) -> float:
        needle = evidence_class.strip().lower()
        aliases: dict[str, str] = {
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
        needle = aliases.get(needle, needle)
        for item in self.evidence_classes:
            if item.evidence_class == needle:
                return item.base_quality
        return 0.25


@lru_cache(maxsize=1)
def load_engineering_catalog() -> EngineeringCatalog:
    resource = files("brixta_twin").joinpath("config/engineering_catalog.json")
    with resource.open("r", encoding="utf-8") as handle:
        payload: dict[str, Any] = json.load(handle)
    return EngineeringCatalog.model_validate(payload)
