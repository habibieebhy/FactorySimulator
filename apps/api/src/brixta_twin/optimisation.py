from __future__ import annotations

from .blending import chemistry_for_scenario
from .models import (
    Chemistry,
    Material,
    RawMixOptimisationRequest,
    RawMixOptimisationResult,
    RawMixSuggestion,
)
from .storage import Repository


REQUIRED_MODULI_OXIDES = ("cao", "sio2", "al2o3", "fe2o3")


def cement_moduli(chemistry: Chemistry) -> tuple[float | None, float | None, float | None]:
    if any(getattr(chemistry, oxide) is None for oxide in REQUIRED_MODULI_OXIDES):
        return None, None, None
    cao = float(chemistry.cao or 0)
    sio2 = float(chemistry.sio2 or 0)
    al2o3 = float(chemistry.al2o3 or 0)
    fe2o3 = float(chemistry.fe2o3 or 0)
    lsf_denominator = 2.8 * sio2 + 1.18 * al2o3 + 0.65 * fe2o3
    sm_denominator = al2o3 + fe2o3
    return (
        cao / lsf_denominator * 100 if lsf_denominator else None,
        sio2 / sm_denominator if sm_denominator else None,
        al2o3 / fe2o3 if fe2o3 else None,
    )


def weighted_chemistry(materials: list[Material], percentages: list[float], scenario: str) -> Chemistry:
    values: dict[str, float | None] = {}
    for oxide in Chemistry.model_fields:
        total = 0.0
        complete = True
        for material, percentage in zip(materials, percentages, strict=True):
            value = getattr(chemistry_for_scenario(material, scenario), oxide)
            if value is None:
                complete = False
                break
            total += value * percentage / 100.0
        values[oxide] = total if complete else None
    return Chemistry(**values)


def optimise_raw_mix(repository: Repository, request: RawMixOptimisationRequest) -> RawMixOptimisationResult:
    materials: list[Material] = []
    minimums: list[float] = []
    maximums: list[float] = []
    warnings: list[str] = []
    for constraint in request.materials:
        item = repository.get("materials", constraint.material_id)
        if not isinstance(item, Material):
            raise ValueError(f"Unknown material {constraint.material_id}")
        selected = chemistry_for_scenario(item, request.chemistry_scenario)
        missing = [oxide.upper() for oxide in REQUIRED_MODULI_OXIDES if getattr(selected, oxide) is None]
        if missing:
            raise ValueError(f"{item.name} cannot be optimised; missing {', '.join(missing)}")
        materials.append(item)
        minimums.append(constraint.minimum_percent)
        maximums.append(constraint.maximum_percent)

    if sum(minimums) > 100.000001 or sum(maximums) < 99.999999:
        raise ValueError("Raw-mix bounds cannot total 100%")

    percentages = minimums[:]
    remaining = 100.0 - sum(percentages)
    capacities = [maximum - minimum for minimum, maximum in zip(minimums, maximums, strict=True)]
    while remaining > 1e-9:
        open_indices = [index for index, capacity in enumerate(capacities) if capacity > 1e-9]
        if not open_indices:
            break
        share = remaining / len(open_indices)
        moved = 0.0
        for index in open_indices:
            addition = min(share, capacities[index])
            percentages[index] += addition
            capacities[index] -= addition
            remaining -= addition
            moved += addition
        if moved <= 1e-12:
            break

    def objective(candidate: list[float]) -> float:
        chemistry = weighted_chemistry(materials, candidate, request.chemistry_scenario)
        lsf, sm, am = cement_moduli(chemistry)
        if lsf is None or sm is None or am is None:
            return 1e12
        return (
            ((lsf - request.target_lsf) / max(request.target_lsf, 1.0)) ** 2
            + ((sm - request.target_sm) / max(request.target_sm, 0.1)) ** 2
            + ((am - request.target_am) / max(request.target_am, 0.1)) ** 2
        )

    best = objective(percentages)
    for step in (10.0, 5.0, 2.0, 1.0, 0.5, 0.2, 0.1, 0.05):
        improved = True
        while improved:
            improved = False
            for source in range(len(percentages)):
                for destination in range(len(percentages)):
                    if source == destination:
                        continue
                    transfer = min(
                        step,
                        percentages[source] - minimums[source],
                        maximums[destination] - percentages[destination],
                    )
                    if transfer <= 1e-12:
                        continue
                    candidate = percentages[:]
                    candidate[source] -= transfer
                    candidate[destination] += transfer
                    score = objective(candidate)
                    if score + 1e-12 < best:
                        percentages = candidate
                        best = score
                        improved = True

    chemistry = weighted_chemistry(materials, percentages, request.chemistry_scenario)
    lsf, sm, am = cement_moduli(chemistry)
    feasible = lsf is not None and sm is not None and am is not None and best < 0.0025
    if not feasible:
        warnings.append("The selected materials/bounds do not closely reach all three target moduli; widen bounds or add a corrective material")
    if chemistry.loi is None:
        clinker_yield = None
        warnings.append("LOI is incomplete, so raw-meal-to-clinker yield remains unknown")
    else:
        clinker_yield = max(0.0, min(1.0, 1.0 - chemistry.loi / 100.0))

    return RawMixOptimisationResult(
        feasible=feasible,
        suggestions=[
            RawMixSuggestion(
                material_id=material.material_id,
                material_name=material.name,
                percentage=round(percentage, 4),
            )
            for material, percentage in zip(materials, percentages, strict=True)
        ],
        chemistry=chemistry,
        lsf=lsf,
        silica_modulus=sm,
        alumina_modulus=am,
        estimated_clinker_yield=clinker_yield,
        objective_error=best,
        warnings=warnings,
    )
