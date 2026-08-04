from __future__ import annotations

from .blending import chemistry_for_scenario
from .mineralogy import (
    bogue_potential_phases,
    clinker_basis_chemistry,
    clinker_family_envelope,
    screen_clinker_behaviour,
)
from .models import (
    CalculationTraceStep,
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


def _phase_value(mineralogy: object, name: str) -> float | None:
    if mineralogy is None:
        return None
    if name == "c4af":
        value = getattr(mineralogy, "c4af_percent", None)
        return value if value is not None else getattr(mineralogy, "calcium_aluminoferrite_ss_percent", None)
    return getattr(mineralogy, f"{name}_percent", None)


def optimise_raw_mix(repository: Repository, request: RawMixOptimisationRequest) -> RawMixOptimisationResult:
    materials: list[Material] = []
    minimums: list[float] = []
    maximums: list[float] = []
    warnings: list[str] = []
    trace: list[CalculationTraceStep] = []
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

    envelope = clinker_family_envelope(request.clinker_family)
    target_lsf = envelope.target_lsf if envelope else request.target_lsf
    target_sm = envelope.target_sm if envelope else request.target_sm
    target_am = envelope.target_am if envelope else request.target_am
    phase_targets: dict[str, float | None] = {
        "c3s": request.target_c3s_percent if request.target_c3s_percent is not None else (envelope.target_c3s if envelope else None),
        "c2s": request.target_c2s_percent if request.target_c2s_percent is not None else (envelope.target_c2s if envelope else None),
        "c3a": request.target_c3a_percent if request.target_c3a_percent is not None else (envelope.target_c3a if envelope else None),
        "c4af": request.target_c4af_percent if request.target_c4af_percent is not None else (envelope.target_c4af if envelope else None),
    }
    trace.append(
        CalculationTraceStep(
            sequence=1,
            section="optimisation",
            operation="Set deterministic objective",
            formula="Σ normalized(moduli error²) + 0.65×Σ normalized(Bogue-phase error²) + burnability penalty",
            inputs={
                "family": request.clinker_family,
                "target_lsf": target_lsf,
                "target_sm": target_sm,
                "target_am": target_am,
                **{f"target_{key}": value for key, value in phase_targets.items()},
            },
            result="objective configured",
        )
    )

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

    evaluations = 0

    def evaluate(candidate: list[float]):
        nonlocal evaluations
        evaluations += 1
        chemistry = weighted_chemistry(materials, candidate, request.chemistry_scenario)
        lsf, sm, am = cement_moduli(chemistry)
        if lsf is None or sm is None or am is None:
            return chemistry, lsf, sm, am, None, None, None, 1e12
        clinker_yield = 1.0 - chemistry.loi / 100.0 if chemistry.loi is not None else None
        clinker_chemistry, _ = clinker_basis_chemistry(chemistry, clinker_yield)
        mineralogy = bogue_potential_phases(clinker_chemistry)
        behaviour = screen_clinker_behaviour(clinker_chemistry, mineralogy, lsf, sm, am)
        score = (
            ((lsf - target_lsf) / max(target_lsf, 1.0)) ** 2
            + ((sm - target_sm) / max(target_sm, 0.1)) ** 2
            + ((am - target_am) / max(target_am, 0.1)) ** 2
        )
        phase_scales = {"c3s": 10.0, "c2s": 10.0, "c3a": 3.0, "c4af": 4.0}
        for name, target in phase_targets.items():
            value = _phase_value(mineralogy, name)
            if target is not None:
                score += 0.65 * (25.0 if value is None else ((value - target) / phase_scales[name]) ** 2)
        if behaviour and behaviour.burnability_score is not None:
            score += 0.10 * (max(0.0, 60.0 - behaviour.burnability_score) / 60.0) ** 2
        return chemistry, lsf, sm, am, clinker_chemistry, mineralogy, behaviour, score

    *_, best = evaluate(percentages)
    accepted_moves = 0
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
                    *_, score = evaluate(candidate)
                    if score + 1e-12 < best:
                        percentages = candidate
                        best = score
                        accepted_moves += 1
                        improved = True

    chemistry, lsf, sm, am, clinker_chemistry, mineralogy, behaviour, best = evaluate(percentages)
    clinker_yield = None if chemistry.loi is None else max(0.0, min(1.0, 1.0 - chemistry.loi / 100.0))
    if chemistry.loi is None:
        warnings.append("LOI is incomplete, so raw-meal-to-clinker yield remains unknown")

    moduli_ok = (
        lsf is not None and abs(lsf - target_lsf) <= 1.5
        and sm is not None and abs(sm - target_sm) <= 0.10
        and am is not None and abs(am - target_am) <= 0.12
    )
    phases_ok = True
    tolerances = {"c3s": 6.0, "c2s": 6.0, "c3a": 2.5, "c4af": 3.5}
    for name, target in phase_targets.items():
        value = _phase_value(mineralogy, name)
        if target is not None and (value is None or abs(value - target) > tolerances[name]):
            phases_ok = False
    feasible = bool(moduli_ok and phases_ok)
    if not feasible:
        warnings.append(
            "The selected materials/bounds do not closely reach every active modulus and clinker-phase target; widen bounds or add a corrective material"
        )

    if clinker_chemistry is not None:
        _, basis_warnings = clinker_basis_chemistry(chemistry, clinker_yield)
        warnings.extend(basis_warnings)
    if mineralogy is not None:
        warnings.extend(mineralogy.warnings)

    positive_suggestions = [
        (material, percentage)
        for material, percentage in zip(materials, percentages, strict=True)
        if percentage > 1e-8
    ]
    rounded_percentages = [round(percentage, 4) for _, percentage in positive_suggestions]
    if rounded_percentages:
        largest_index = max(range(len(rounded_percentages)), key=rounded_percentages.__getitem__)
        rounded_percentages[largest_index] = round(
            rounded_percentages[largest_index] + (100.0 - sum(rounded_percentages)),
            4,
        )

    trace.extend(
        [
            CalculationTraceStep(
                sequence=2,
                section="optimisation",
                operation="Pairwise bounded mass-transfer search",
                formula="For step ∈ [10,5,2,1,0.5,0.2,0.1,0.05], transfer source→destination when objective decreases",
                inputs={"candidate_evaluations": float(evaluations), "accepted_moves": float(accepted_moves)},
                result=round(best, 8),
                unit="dimensionless objective",
            ),
            CalculationTraceStep(
                sequence=3,
                section="chemistry",
                operation="Calculate cement moduli",
                formula="LSF=100CaO/(2.8SiO2+1.18Al2O3+0.65Fe2O3); SM=SiO2/(Al2O3+Fe2O3); AM=Al2O3/Fe2O3",
                inputs={"CaO": chemistry.cao, "SiO2": chemistry.sio2, "Al2O3": chemistry.al2o3, "Fe2O3": chemistry.fe2o3},
                result=f"LSF={lsf:.3f}, SM={sm:.4f}, AM={am:.4f}" if None not in (lsf, sm, am) else "incomplete",
            ),
            CalculationTraceStep(
                sequence=4,
                section="mass balance",
                operation="Convert raw meal to clinker basis",
                formula="yield=1−LOI/100; oxide mass/t clinker=(raw oxide%×1000/yield)+fuel-ash oxide mass; normalise reported oxides to 100%",
                inputs={"LOI": chemistry.loi, "yield": clinker_yield},
                result="clinker oxide basis calculated" if clinker_chemistry else "unavailable",
            ),
            CalculationTraceStep(
                sequence=5,
                section="mineralogy",
                operation="Estimate potential clinker phases",
                formula="ASTM-style Bogue equations on loss-free clinker chemistry",
                inputs={"family": request.clinker_family},
                result=(
                    f"C3S={mineralogy.c3s_percent:.2f}, C2S={mineralogy.c2s_percent:.2f}, "
                    f"C3A={mineralogy.c3a_percent:.2f}, C4AF={_phase_value(mineralogy, 'c4af'):.2f}"
                    if mineralogy and None not in (
                        mineralogy.c3s_percent,
                        mineralogy.c2s_percent,
                        mineralogy.c3a_percent,
                        _phase_value(mineralogy, "c4af"),
                    )
                    else "unavailable"
                ),
                unit="mass % potential phase",
            ),
        ]
    )

    return RawMixOptimisationResult(
        feasible=feasible,
        suggestions=[
            RawMixSuggestion(
                material_id=material.material_id,
                material_name=material.name,
                percentage=percentage,
            )
            for (material, _), percentage in zip(positive_suggestions, rounded_percentages, strict=True)
        ],
        chemistry=chemistry,
        clinker_chemistry=clinker_chemistry,
        mineralogy=mineralogy,
        behaviour=behaviour,
        clinker_family=request.clinker_family,
        lsf=lsf,
        silica_modulus=sm,
        alumina_modulus=am,
        estimated_clinker_yield=clinker_yield,
        objective_error=best,
        calculation_trace=trace,
        warnings=list(dict.fromkeys(warnings)),
    )
