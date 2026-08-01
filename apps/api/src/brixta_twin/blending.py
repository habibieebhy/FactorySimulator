from __future__ import annotations

from collections import defaultdict

from .models import (
    Blend,
    BlendCreate,
    BlendPreview,
    Chemistry,
    Material,
    ResolvedBlendComponent,
)
from .storage import Repository


FINISHED_CEMENT_MATERIALS = {
    "clinker",
    "fly_ash",
    "gypsum",
    "calcined_clay",
    "limestone",
    "ggbs",
    "slag",
    "silica_fume",
    "natural_pozzolan",
    "rice_husk_ash",
    "metakaolin",
    "cement_kiln_dust",
    "grinding_aid",
}
RAW_MATERIALS = {
    "limestone",
    "clay",
    "shale",
    "silica_corrective",
    "iron_corrective",
    "bauxite",
    "laterite",
    "sand",
}
FUEL_MATERIALS = {"coal", "petcoke", "biomass", "rdf", "alternative_fuel"}


def _expand_components(
    repository: Repository,
    blend: BlendCreate,
    multiplier: float,
    stack: tuple[str, ...],
    totals: dict[str, float],
) -> None:
    for component in blend.components:
        share = multiplier * component.percentage / 100.0
        if component.component_type == "material":
            material_id = component.material_id
            if material_id is None or not isinstance(
                repository.get("materials", material_id), Material
            ):
                raise ValueError(f"Unknown material {material_id or '<missing>'}")
            totals[material_id] += share
            continue

        child_id = component.blend_id
        if child_id is None:
            raise ValueError("Nested blend component is missing blend_id")
        if child_id in stack:
            chain = " -> ".join((*stack, child_id))
            raise ValueError(f"Circular blend reference detected: {chain}")
        child = repository.get("blends", child_id)
        if not isinstance(child, Blend):
            raise ValueError(f"Unknown nested blend {child_id}")
        _expand_components(repository, child, share, (*stack, child_id), totals)


def flatten_blend(
    repository: Repository,
    blend: BlendCreate,
    root_id: str | None = None,
) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    stack = (root_id,) if root_id else ()
    _expand_components(repository, blend, 1.0, stack, totals)
    return dict(totals)


def _compatibility_warnings(
    repository: Repository,
    blend: BlendCreate,
    flattened: dict[str, float],
) -> list[str]:
    warnings: list[str] = []
    material_types: set[str] = set()
    evidence_classes: set[str] = set()
    for material_id in flattened:
        material = repository.get("materials", material_id)
        if not isinstance(material, Material):
            continue
        material_types.add(material.material_type)
        evidence_classes.update(item.evidence_class for item in material.evidence)
        if material.data_gaps:
            warnings.append(
                f"{material.name} has unreported fields: {', '.join(material.data_gaps)}"
            )
        if material.cost_inr_per_t is None:
            warnings.append(f"{material.name} has no cost value")
        if material.co2_kg_per_t is None:
            warnings.append(f"{material.name} has no CO2 factor")
        if material.applicable_blend_classes and (
            blend.blend_class not in material.applicable_blend_classes
        ):
            warnings.append(
                f"{material.name} is not approved for {blend.blend_class.replace('_', ' ')} in its material record"
            )

    if blend.blend_class == "finished_cement":
        incompatible = material_types - FINISHED_CEMENT_MATERIALS
        if incompatible:
            warnings.append(
                "Finished cement contains incompatible material types: "
                + ", ".join(sorted(incompatible))
            )
        if "clinker" not in material_types:
            warnings.append("Finished cement contains no clinker component")
        if "gypsum" not in material_types:
            warnings.append("Finished cement contains no gypsum or set regulator")
    elif blend.blend_class in {"raw_material_stockpile", "raw_meal"}:
        incompatible = material_types - RAW_MATERIALS
        if incompatible:
            warnings.append(
                "Raw-material blend contains incompatible material types: "
                + ", ".join(sorted(incompatible))
            )
    elif blend.blend_class == "fuel_blend":
        incompatible = material_types - FUEL_MATERIALS
        if incompatible:
            warnings.append(
                "Fuel blend contains non-fuel material types: "
                + ", ".join(sorted(incompatible))
            )
    elif blend.blend_class == "clinker_blend" and material_types - {"clinker"}:
        warnings.append("Clinker blend contains a material that is not classified as clinker")

    if not evidence_classes:
        warnings.append("No material evidence is attached")
    elif evidence_classes & {"assumed", "evidence_gap", "unverified"}:
        warnings.append("One or more components use assumed or unverified data")
    return warnings


def preview_blend(
    repository: Repository,
    blend: BlendCreate,
    root_id: str | None = None,
) -> BlendPreview:
    flattened = flatten_blend(repository, blend, root_id=root_id)
    values = {key: 0.0 for key in Chemistry.model_fields}
    material_cost = 0.0
    co2 = 0.0
    cost_complete = True
    co2_complete = True
    resolved: list[ResolvedBlendComponent] = []

    for material_id, fraction in sorted(flattened.items()):
        material = repository.get("materials", material_id)
        if not isinstance(material, Material):
            raise ValueError(f"Unknown material {material_id}")
        for key in values:
            values[key] += getattr(material.chemistry, key) * fraction
        if material.cost_inr_per_t is None:
            cost_complete = False
        else:
            material_cost += material.cost_inr_per_t * fraction
        if material.co2_kg_per_t is None:
            co2_complete = False
        else:
            co2 += material.co2_kg_per_t * fraction
        resolved.append(
            ResolvedBlendComponent(
                material_id=material_id,
                material_name=material.name,
                material_type=material.material_type,
                percentage=round(fraction * 100.0, 6),
                evidence_class=(
                    material.evidence[0].evidence_class
                    if material.evidence
                    else "unverified"
                ),
                material_version=material.version,
            )
        )

    direct_total = sum(item.percentage for item in blend.components)
    flattened_total = sum(flattened.values()) * 100.0
    if abs(flattened_total - 100.0) > 0.01:
        raise ValueError(
            f"Flattened blend totals {flattened_total:.4f}%; expected 100.00%"
        )
    return BlendPreview(
        blend_name=blend.name,
        blend_class=blend.blend_class,
        direct_total_percentage=round(direct_total, 6),
        flattened_total_percentage=round(flattened_total, 6),
        flattened_components=resolved,
        chemistry=Chemistry(**values),
        material_cost_inr_t=material_cost if cost_complete else None,
        estimated_co2_kg_t=co2 if co2_complete else None,
        warnings=_compatibility_warnings(repository, blend, flattened),
    )
