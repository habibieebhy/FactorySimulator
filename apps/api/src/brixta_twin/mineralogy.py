from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from .models import (
    Chemistry,
    ClinkerBehaviourScreening,
    ClinkerFamily,
    ClinkerMineralogy,
)


REQUIRED_BOGUE_OXIDES = ("cao", "sio2", "al2o3", "fe2o3")
NONVOLATILE_OXIDES = tuple(name for name in Chemistry.model_fields if name != "loi")


@dataclass(frozen=True, slots=True)
class ClinkerFamilyEnvelope:
    label: str
    target_lsf: float
    target_sm: float
    target_am: float
    target_c3s: float
    target_c2s: float
    target_c3a: float
    target_c4af: float
    description: str


CLINKER_FAMILY_ENVELOPES: dict[str, ClinkerFamilyEnvelope] = {
    "general_purpose": ClinkerFamilyEnvelope(
        label="General-purpose clinker",
        target_lsf=96.0,
        target_sm=2.40,
        target_am=1.50,
        target_c3s=60.0,
        target_c2s=20.0,
        target_c3a=8.0,
        target_c4af=10.0,
        description="Balanced Portland-clinker screening target.",
    ),
    "high_early_strength": ClinkerFamilyEnvelope(
        label="High early strength clinker",
        target_lsf=98.0,
        target_sm=2.30,
        target_am=1.40,
        target_c3s=66.0,
        target_c2s=14.0,
        target_c3a=8.0,
        target_c4af=10.0,
        description="Higher potential alite, with a burnability and free-lime penalty.",
    ),
    "durable_belite": ClinkerFamilyEnvelope(
        label="Durable belite-rich clinker",
        target_lsf=94.5,
        target_sm=2.45,
        target_am=1.35,
        target_c3s=52.0,
        target_c2s=29.0,
        target_c3a=7.0,
        target_c4af=11.0,
        description="Moderate alite and increased belite for slower heat and later-age strength screening.",
    ),
    "sulfate_resistant": ClinkerFamilyEnvelope(
        label="Sulfate-resistant clinker",
        target_lsf=95.0,
        target_sm=2.50,
        target_am=0.95,
        target_c3s=55.0,
        target_c2s=25.0,
        target_c3a=4.0,
        target_c4af=14.0,
        description="Low potential C3A and increased ferrite screening target.",
    ),
    "low_carbon_belite": ClinkerFamilyEnvelope(
        label="Lower-carbon belite-rich clinker",
        target_lsf=92.5,
        target_sm=2.45,
        target_am=1.30,
        target_c3s=44.0,
        target_c2s=37.0,
        target_c3a=7.0,
        target_c4af=10.0,
        description="Lower lime saturation and higher potential belite; slower early strength is expected.",
    ),
    "lc3_compatible": ClinkerFamilyEnvelope(
        label="LC3-compatible clinker screening",
        target_lsf=95.0,
        target_sm=2.35,
        target_am=1.25,
        target_c3s=55.0,
        target_c2s=25.0,
        target_c3a=7.0,
        target_c4af=12.0,
        description="Moderate silicate phases and controlled aluminate screening; sulfate balance still requires cement-system testing.",
    ),
}


def clinker_family_envelope(family: ClinkerFamily | str) -> ClinkerFamilyEnvelope | None:
    return CLINKER_FAMILY_ENVELOPES.get(str(family))


def clinker_basis_chemistry(
    raw_chemistry: Chemistry,
    raw_meal_to_clinker_yield: float | None = None,
    fuel_ash_chemistry: Chemistry | None = None,
    fuel_ash_kg_t_clinker: float | None = None,
) -> tuple[Chemistry | None, list[str]]:
    """Convert raw-meal chemistry to a loss-free clinker oxide basis.

    Oxide masses are calculated per tonne of clinker, retained fuel ash is
    added on the same mass basis, and the known nonvolatile oxides are then
    normalised to 100 %.  This is deterministic mass accounting, not an
    equilibrium or kinetic kiln model.
    """

    warnings: list[str] = []
    missing_major = [oxide.upper() for oxide in REQUIRED_BOGUE_OXIDES if getattr(raw_chemistry, oxide) is None]
    if missing_major:
        return None, ["Clinker-basis chemistry is unavailable; missing " + ", ".join(missing_major)]

    yield_value = raw_meal_to_clinker_yield
    if yield_value is None and raw_chemistry.loi is not None:
        yield_value = max(1e-9, 1.0 - raw_chemistry.loi / 100.0)
    if yield_value is None or yield_value <= 0:
        yield_value = 1.0
        warnings.append("Raw-meal-to-clinker yield was unavailable; loss-free normalisation used a unit mass basis")

    raw_meal_kg_t_clinker = 1000.0 / yield_value
    ash_mass = max(0.0, fuel_ash_kg_t_clinker or 0.0)
    oxide_masses: dict[str, float | None] = {}
    missing_nonvolatile: list[str] = []

    for oxide in NONVOLATILE_OXIDES:
        raw_value = getattr(raw_chemistry, oxide)
        if raw_value is None:
            oxide_masses[oxide] = None
            missing_nonvolatile.append(oxide.upper())
            continue
        mass = raw_meal_kg_t_clinker * raw_value / 100.0
        if ash_mass > 0 and fuel_ash_chemistry is not None:
            ash_value = getattr(fuel_ash_chemistry, oxide)
            if ash_value is None:
                warnings.append(f"Fuel-ash {oxide.upper()} is unknown and was not added")
            else:
                mass += ash_mass * ash_value / 100.0
        oxide_masses[oxide] = mass

    known_total = sum(value for value in oxide_masses.values() if value is not None)
    if known_total <= 0:
        return None, warnings + ["Known clinker oxide mass is zero"]

    values: dict[str, float | None] = {
        oxide: (mass / known_total * 100.0 if mass is not None else None)
        for oxide, mass in oxide_masses.items()
    }
    values["loi"] = 0.0
    if missing_nonvolatile:
        warnings.append(
            "Clinker chemistry was normalised over reported oxides; missing "
            + ", ".join(missing_nonvolatile)
        )
    return Chemistry(**values), warnings


def bogue_potential_phases(clinker_chemistry: Chemistry | None) -> ClinkerMineralogy | None:
    if clinker_chemistry is None:
        return None
    missing = [oxide.upper() for oxide in REQUIRED_BOGUE_OXIDES if getattr(clinker_chemistry, oxide) is None]
    if missing:
        return ClinkerMineralogy(warnings=["Bogue estimate unavailable; missing " + ", ".join(missing)])

    c = float(clinker_chemistry.cao or 0.0)
    s = float(clinker_chemistry.sio2 or 0.0)
    a = float(clinker_chemistry.al2o3 or 0.0)
    f = float(clinker_chemistry.fe2o3 or 0.0)
    so3 = float(clinker_chemistry.so3 or 0.0)
    af = a / f if f > 0 else None
    warnings: list[str] = []
    if clinker_chemistry.so3 is None:
        warnings.append("SO3 is unreported; the SO3 correction in potential C3S was treated as zero")

    ferrite_ss: float | None = None
    if af is not None and af < 0.64:
        c3s_raw = 4.071 * c - 7.600 * s - 4.479 * a - 2.859 * f - 2.852 * so3
        c3a_raw = 0.0
        c4af_raw = 0.0
        ferrite_ss = 2.100 * a + 1.702 * f
        warnings.append(
            "Al2O3/Fe2O3 is below 0.64; C3A is set to zero and the ferrite result is reported as a calcium aluminoferrite solid solution"
        )
    else:
        c3s_raw = 4.071 * c - 7.600 * s - 6.718 * a - 1.430 * f - 2.852 * so3
        c3a_raw = 2.650 * a - 1.692 * f
        c4af_raw = 3.043 * f

    c2s_raw = 2.867 * s - 0.7544 * c3s_raw
    raw_values = {"C3S": c3s_raw, "C2S": c2s_raw, "C3A": c3a_raw, "C4AF": c4af_raw}
    for phase, value in raw_values.items():
        if value < 0:
            warnings.append(f"Calculated {phase} was negative ({value:.2f}%); it was clipped to zero for screening")

    c3s = max(0.0, c3s_raw)
    c2s = max(0.0, c2s_raw)
    c3a = max(0.0, c3a_raw)
    c4af = max(0.0, c4af_raw)
    phase_total = c3s + c2s + c3a + c4af + max(0.0, ferrite_ss or 0.0)
    unallocated = 100.0 - phase_total
    if phase_total > 100.5:
        warnings.append(
            f"Potential phases total {phase_total:.2f}%; values were not renormalised because the excess is a model-diagnostic signal"
        )
    warnings.append("Potential Bogue phases are screening estimates, not XRD/Rietveld measurements")

    return ClinkerMineralogy(
        c3s_percent=round(c3s, 4),
        c2s_percent=round(c2s, 4),
        c3a_percent=round(c3a, 4),
        c4af_percent=round(c4af, 4) if ferrite_ss is None else None,
        calcium_aluminoferrite_ss_percent=(round(ferrite_ss, 4) if ferrite_ss is not None else None),
        phase_total_percent=round(phase_total, 4),
        unallocated_percent=round(unallocated, 4),
        alumina_ferric_ratio=(round(af, 4) if af is not None else None),
        warnings=warnings,
    )


def _family_distance(
    family: ClinkerFamilyEnvelope,
    lsf: float | None,
    sm: float | None,
    am: float | None,
    mineralogy: ClinkerMineralogy,
) -> float | None:
    observations = [
        (lsf, family.target_lsf, 4.0),
        (sm, family.target_sm, 0.35),
        (am, family.target_am, 0.35),
        (mineralogy.c3s_percent, family.target_c3s, 10.0),
        (mineralogy.c2s_percent, family.target_c2s, 10.0),
        (mineralogy.c3a_percent, family.target_c3a, 3.0),
        (
            mineralogy.c4af_percent
            if mineralogy.c4af_percent is not None
            else mineralogy.calcium_aluminoferrite_ss_percent,
            family.target_c4af,
            4.0,
        ),
    ]
    terms = [((value - target) / scale) ** 2 for value, target, scale in observations if value is not None]
    return sqrt(sum(terms) / len(terms)) if terms else None


def screen_clinker_behaviour(
    clinker_chemistry: Chemistry | None,
    mineralogy: ClinkerMineralogy | None,
    lsf: float | None,
    sm: float | None,
    am: float | None,
    kiln_temperature_c: float | None = None,
) -> ClinkerBehaviourScreening | None:
    if clinker_chemistry is None or mineralogy is None:
        return None

    a = clinker_chemistry.al2o3
    f = clinker_chemistry.fe2o3
    liquid: float | None = None
    rationale: list[str] = []
    if a is not None and f is not None:
        liquid = 3.0 * a + 2.25 * f
        for oxide in ("mgo", "na2o", "k2o"):
            value = getattr(clinker_chemistry, oxide)
            if value is not None:
                liquid += min(value, 2.0) if oxide == "mgo" else value
        rationale.append("Liquid-phase proxy uses the Lea-Parker 1450 °C oxide expression")

    score = 100.0
    if lsf is not None:
        score -= max(0.0, lsf - 96.0) * 4.5
        score -= max(0.0, 92.0 - lsf) * 1.0
    if sm is not None:
        score -= max(0.0, sm - 2.40) * 22.0
        score -= max(0.0, 1.80 - sm) * 10.0
    if liquid is not None:
        score -= max(0.0, 22.0 - liquid) * 4.0
        score -= max(0.0, liquid - 30.0) * 2.0
    if mineralogy.c3s_percent is not None:
        score -= max(0.0, mineralogy.c3s_percent - 65.0)
    if kiln_temperature_c is not None:
        score += max(-8.0, min(8.0, (kiln_temperature_c - 1450.0) * 0.08))
        rationale.append("Entered kiln temperature applies a bounded correction to the chemistry-only burnability score")
    score = max(0.0, min(100.0, score))

    burnability_class = "good" if score >= 75 else "moderate" if score >= 55 else "difficult"
    if lsf is None:
        free_lime_risk = "unknown"
    elif lsf > 99 or score < 50:
        free_lime_risk = "high"
    elif lsf > 96 or score < 72:
        free_lime_risk = "medium"
    else:
        free_lime_risk = "low"
    fuel = "low" if score >= 80 else "medium" if score >= 58 else "high"

    c3s = mineralogy.c3s_percent
    c2s = mineralogy.c2s_percent
    c3a = mineralogy.c3a_percent
    early = "unknown" if c3s is None else "high" if c3s >= 60 else "medium" if c3s >= 50 else "low"
    later = "unknown" if c2s is None else "high" if c2s >= 28 else "medium" if c2s >= 18 else "low"
    sulfate = "unknown" if c3a is None else "high" if c3a <= 5 else "moderate" if c3a <= 8 else "low"
    if c3s is None or c3a is None:
        heat = "unknown"
    else:
        heat_index = c3s + 4.75 * c3a
        heat = "low" if heat_index <= 90 else "moderate" if heat_index <= 100 else "high"
        rationale.append(f"Potential heat index C3S + 4.75×C3A = {heat_index:.1f}")

    distances = {
        key: value
        for key, envelope in CLINKER_FAMILY_ENVELOPES.items()
        if (value := _family_distance(envelope, lsf, sm, am, mineralogy)) is not None
    }
    predicted_family = min(distances, key=lambda family_key: distances[family_key]) if distances else None
    family_distance = distances.get(predicted_family) if predicted_family else None
    rationale.extend(
        [
            "Burnability and fuel demand are transparent screening heuristics, not kiln-calibrated predictions",
            "Strength and sulfate labels are phase-based tendencies; laboratory validation remains mandatory",
        ]
    )

    return ClinkerBehaviourScreening(
        liquid_phase_1450_percent=(round(liquid, 4) if liquid is not None else None),
        burnability_score=round(score, 2),
        burnability_class=burnability_class,
        free_lime_risk=free_lime_risk,
        expected_fuel_demand=fuel,
        expected_early_strength=early,
        expected_later_strength=later,
        expected_sulfate_resistance=sulfate,
        expected_heat_release=heat,
        predicted_family=predicted_family,  # type: ignore[arg-type]
        family_distance=(round(family_distance, 4) if family_distance is not None else None),
        rationale=rationale,
    )
