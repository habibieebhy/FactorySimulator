from __future__ import annotations

from collections import defaultdict
from typing import Literal

from .models import (
    Blend,
    BlendClass,
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


def chemistry_for_scenario(material: Material, scenario: str) -> Chemistry:
    profile = (
        material.chemistry_min
        if scenario == "low"
        else material.chemistry_max
        if scenario == "high"
        else None
    )
    if profile is None:
        return material.chemistry
    # A range profile may contain only the oxides that were actually sampled.
    # Unspecified bounds inherit the typical value; they must not become a
    # new data gap merely because (for example) only CaO variability is known.
    return Chemistry(
        **{
            oxide: (
                getattr(profile, oxide)
                if getattr(profile, oxide) is not None
                else getattr(material.chemistry, oxide)
            )
            for oxide in Chemistry.model_fields
        }
    )


def _stream_for_direct_component(
    repository: Repository,
    root_blend: BlendCreate,
    component,
) -> tuple[str, str | None, str | None, BlendClass | None]:
    """Classify the manufacturing stream before recursive flattening.

    This preserves the semantic boundary of a nested clinker/raw-meal recipe.
    Without it, limestone inside clinker feed is indistinguishable from
    limestone added directly at the cement mill.
    """
    if component.component_type == "material":
        material = repository.get("materials", component.material_id or "")
        if not isinstance(material, Material):
            raise ValueError(f"Unknown material {component.material_id or '<missing>'}")
        if root_blend.blend_class == "finished_cement":
            if material.material_type == "clinker" or material.functional_role == "clinker":
                stream = "clinker"
            elif material.material_type == "calcined_clay":
                stream = "calcined_clay"
            else:
                stream = "cement_addition"
        elif root_blend.blend_class in {"raw_meal", "raw_material_stockpile"}:
            stream = "clinker_raw_feed"
        elif root_blend.blend_class == "clinker_blend":
            stream = "clinker" if material.material_type == "clinker" else "clinker_raw_feed"
        else:
            stream = "direct_product"
        return stream, material.material_id, material.name, None

    child = repository.get("blends", component.blend_id or "")
    if not isinstance(child, Blend):
        raise ValueError(f"Unknown nested blend {component.blend_id or '<missing>'}")
    if root_blend.blend_class == "finished_cement":
        if child.blend_class in {"clinker_blend", "raw_meal"}:
            stream = "clinker_raw_feed"
        elif child.blend_class == "premix":
            stream = "cement_addition"
        else:
            stream = "cement_addition"
    elif root_blend.blend_class in {"raw_meal", "raw_material_stockpile"}:
        stream = "clinker_raw_feed"
    elif root_blend.blend_class == "clinker_blend":
        stream = "clinker_raw_feed" if child.blend_class in {"raw_meal", "raw_material_stockpile"} else "clinker"
    else:
        stream = "direct_product"
    return stream, child.blend_id, child.name, child.blend_class


def _expand_resolved_components(
    repository: Repository,
    blend: BlendCreate,
    multiplier: float,
    stack: tuple[str, ...],
    stream: str,
    root_component_type: Literal["material", "blend"],
    root_component_id: str | None,
    root_component_name: str | None,
    root_blend_class: BlendClass | None,
    hierarchy_path: tuple[str, ...],
    totals: dict[tuple[str, str, str | None], float],
) -> None:
    for component in blend.components:
        share = multiplier * component.percentage / 100.0
        if component.component_type == "material":
            material_id = component.material_id
            if material_id is None or not isinstance(repository.get("materials", material_id), Material):
                raise ValueError(f"Unknown material {material_id or '<missing>'}")
            totals[(material_id, stream, root_component_id)] += share
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
        _expand_resolved_components(
            repository,
            child,
            share,
            (*stack, child_id),
            stream,
            root_component_type,
            root_component_id,
            root_component_name,
            root_blend_class,
            (*hierarchy_path, child_id),
            totals,
        )


def resolve_blend_components(
    repository: Repository,
    blend: BlendCreate,
    root_id: str | None = None,
) -> list[ResolvedBlendComponent]:
    totals: dict[tuple[str, str, str | None], float] = defaultdict(float)
    metadata: dict[
        str | None,
        tuple[
            Literal["material", "blend"],
            str | None,
            BlendClass | None,
            str,
            tuple[str, ...],
        ],
    ] = {}
    stack = (root_id,) if root_id else ()
    for component in blend.components:
        stream, root_component_id, root_component_name, root_blend_class = _stream_for_direct_component(
            repository, blend, component
        )
        metadata[root_component_id] = (
            component.component_type,
            root_component_name,
            root_blend_class,
            stream,
            (root_component_id,) if root_component_id else (),
        )
        if component.component_type == "material":
            assert component.material_id is not None
            totals[(component.material_id, stream, root_component_id)] += component.percentage / 100.0
        else:
            assert component.blend_id is not None
            child = repository.get("blends", component.blend_id)
            if not isinstance(child, Blend):
                raise ValueError(f"Unknown nested blend {component.blend_id}")
            _expand_resolved_components(
                repository,
                child,
                component.percentage / 100.0,
                (*stack, component.blend_id),
                stream,
                component.component_type,
                root_component_id,
                root_component_name,
                root_blend_class,
                (component.blend_id,),
                totals,
            )

    resolved: list[ResolvedBlendComponent] = []
    for (material_id, stream, root_component_id), fraction in sorted(totals.items()):
        material = repository.get("materials", material_id)
        if not isinstance(material, Material):
            raise ValueError(f"Unknown material {material_id}")
        root_type, root_name, root_class, _, path = metadata.get(
            root_component_id, ("material", None, None, stream, ())
        )
        resolved.append(
            ResolvedBlendComponent(
                material_id=material_id,
                material_name=material.name,
                material_type=material.material_type,
                percentage=round(fraction * 100.0, 6),
                evidence_class=(material.evidence[0].evidence_class if material.evidence else "unverified"),
                material_version=material.version,
                production_stream=stream,
                root_component_type=root_type,
                root_component_id=root_component_id,
                root_component_name=root_name,
                root_blend_class=root_class,
                hierarchy_path=list(path),
            )
        )
    return resolved


def flatten_blend(
    repository: Repository,
    blend: BlendCreate,
    root_id: str | None = None,
) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for component in resolve_blend_components(repository, blend, root_id=root_id):
        totals[component.material_id] += component.percentage / 100.0
    return dict(totals)


def direct_production_fractions(
    repository: Repository,
    blend: BlendCreate,
) -> dict[str, float]:
    fractions = {"clinker": 0.0, "calcined_clay": 0.0, "cement_addition": 0.0}
    if blend.blend_class != "finished_cement":
        return fractions
    for component in blend.components:
        share = component.percentage / 100.0
        stream, _, _, _ = _stream_for_direct_component(repository, blend, component)
        if stream in {"clinker", "clinker_raw_feed"}:
            fractions["clinker"] += share
        elif stream == "calcined_clay":
            fractions["calcined_clay"] += share
        else:
            fractions["cement_addition"] += share
    return fractions


def _compatibility_warnings(
    repository: Repository,
    blend: BlendCreate,
    flattened: dict[str, float],
    resolved: list[ResolvedBlendComponent],
) -> list[str]:
    warnings: list[str] = []
    material_types: set[str] = set()
    functional_roles: set[str] = set()
    evidence_classes: set[str] = set()
    for material_id in flattened:
        material = repository.get("materials", material_id)
        if not isinstance(material, Material):
            continue
        material_types.add(material.material_type)
        functional_roles.add(material.functional_role)
        evidence_classes.update(item.evidence_class for item in material.evidence)
        if material.data_gaps:
            warnings.append(
                f"{material.name} has unreported fields: {', '.join(material.data_gaps)}"
            )
        if material.cost_inr_per_t is None:
            warnings.append(f"{material.name} has no cost value")
        if material.co2_kg_per_t is None:
            warnings.append(f"{material.name} has no CO2 factor")
        component_streams = {
            item.production_stream for item in resolved if item.material_id == material_id
        }
        expected_classes = {blend.blend_class}
        if "clinker_raw_feed" in component_streams:
            expected_classes = {"raw_meal", "raw_material_stockpile", "clinker_blend"}
        if material.applicable_blend_classes and not (
            expected_classes & set(material.applicable_blend_classes)
        ):
            warnings.append(
                f"{material.name} is not approved for its {', '.join(sorted(component_streams)) or 'product'} stream"
            )

    if blend.blend_class == "finished_cement":
        direct_fractions = direct_production_fractions(repository, blend)
        if direct_fractions["clinker"] <= 0:
            warnings.append("Finished cement contains no clinker material or nested clinker/raw-meal blend")
        direct_roles: set[str] = set()
        for component in blend.components:
            if component.component_type == "material":
                material = repository.get("materials", component.material_id or "")
                if isinstance(material, Material):
                    direct_roles.add(material.functional_role)
            else:
                child = repository.get("blends", component.blend_id or "")
                if isinstance(child, Blend) and child.blend_class in {"clinker_blend", "raw_meal"}:
                    direct_roles.add("clinker")
                else:
                    direct_roles.add("cement_addition")
        allowed_roles = {"clinker", "cement_addition", "set_regulator", "process_additive", "recycled_process_material"}
        incompatible_roles = direct_roles - allowed_roles
        if incompatible_roles:
            warnings.append(
                "Finished cement contains incompatible direct functional roles: "
                + ", ".join(sorted(incompatible_roles))
            )
        if "set_regulator" not in direct_roles:
            warnings.append("Finished cement contains no gypsum or set regulator")
    elif blend.blend_class in {"raw_material_stockpile", "raw_meal"}:
        incompatible_roles = functional_roles - {"raw_kiln_feed", "corrective", "recycled_process_material"}
        if incompatible_roles:
            warnings.append(
                "Raw-material blend contains incompatible functional roles: "
                + ", ".join(sorted(incompatible_roles))
            )
    elif blend.blend_class == "fuel_blend":
        incompatible_roles = functional_roles - {"fuel", "alternative_fuel"}
        if incompatible_roles:
            warnings.append(
                "Fuel blend contains non-fuel functional roles: "
                + ", ".join(sorted(incompatible_roles))
            )
    elif blend.blend_class == "clinker_blend" and functional_roles - {"clinker"}:
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
    chemistry_scenario: str = "typical",
) -> BlendPreview:
    resolved = resolve_blend_components(repository, blend, root_id=root_id)
    flattened: dict[str, float] = defaultdict(float)
    for item in resolved:
        flattened[item.material_id] += item.percentage / 100.0
    values: dict[str, float | None] = {key: 0.0 for key in Chemistry.model_fields}
    unknown_fields: set[str] = set()
    material_cost = 0.0
    co2 = 0.0
    cost_complete = True
    co2_complete = True
    for material_id, fraction in sorted(flattened.items()):
        material = repository.get("materials", material_id)
        if not isinstance(material, Material):
            raise ValueError(f"Unknown material {material_id}")
        selected_chemistry = chemistry_for_scenario(material, chemistry_scenario)
        for key in values:
            oxide = getattr(selected_chemistry, key)
            accumulated = values[key]
            if oxide is None:
                unknown_fields.add(key)
                values[key] = None
            elif accumulated is not None:
                values[key] = accumulated + oxide * fraction
        if material.cost_inr_per_t is None:
            cost_complete = False
        else:
            material_cost += material.cost_inr_per_t * fraction
        if material.co2_kg_per_t is None:
            co2_complete = False
        else:
            co2 += material.co2_kg_per_t * fraction

    direct_total = sum(item.percentage for item in blend.components)
    flattened_total = sum(flattened.values()) * 100.0
    if abs(flattened_total - 100.0) > 0.01:
        raise ValueError(
            f"Flattened blend totals {flattened_total:.4f}%; expected 100.00%"
        )
    warnings = _compatibility_warnings(repository, blend, flattened, resolved)
    if unknown_fields:
        warnings.append(
            "Weighted chemistry is incomplete because these fields are unknown: "
            + ", ".join(sorted(field.upper() for field in unknown_fields))
        )
    return BlendPreview(
        blend_name=blend.name,
        blend_class=blend.blend_class,
        direct_total_percentage=round(direct_total, 6),
        flattened_total_percentage=round(flattened_total, 6),
        flattened_components=resolved,
        chemistry=Chemistry(**values),
        chemistry_scenario=chemistry_scenario,  # type: ignore[arg-type]
        chemistry_complete=not unknown_fields,
        unknown_chemistry_fields=sorted(unknown_fields),
        material_cost_inr_t=material_cost if cost_complete else None,
        estimated_co2_kg_t=co2 if co2_complete else None,
        warnings=warnings,
    )
