from __future__ import annotations

from collections.abc import Callable

from .models import QualityCheck, QualityGate, QualityMeasurements


def opc43_gate(measurements: QualityMeasurements | None) -> QualityGate:
    """Screen measured OPC 43 results against the stored IS 269 gate.

    This is deliberately a gate, not a strength predictor.  Untested values do
    not pass.  Users should verify the configured limits against the licensed
    standard and current BIS amendments before certification work.
    """

    checks: list[QualityCheck] = []

    def check(
        metric: str,
        value: float | None,
        requirement: str,
        predicate: Callable[[float], bool],
    ) -> None:
        checks.append(
            QualityCheck(
                metric=metric,
                measured=value,
                requirement=requirement,
                status=("not_tested" if value is None else "pass" if predicate(value) else "fail"),
            )
        )

    value = measurements or QualityMeasurements()
    check("Blaine fineness", value.blaine_m2_kg, ">= 225 m²/kg", lambda item: item >= 225)
    check("Initial setting", value.initial_setting_minutes, ">= 30 min", lambda item: item >= 30)
    check("Final setting", value.final_setting_minutes, "<= 600 min", lambda item: item <= 600)
    check("Le Chatelier soundness", value.le_chatelier_mm, "<= 10 mm", lambda item: item <= 10)
    check("Autoclave expansion", value.autoclave_expansion_percent, "<= 0.8%", lambda item: item <= 0.8)
    check("3-day compressive strength", value.strength_3d_mpa, ">= 23 MPa", lambda item: item >= 23)
    check("7-day compressive strength", value.strength_7d_mpa, ">= 33 MPa", lambda item: item >= 33)
    check("28-day compressive strength", value.strength_28d_mpa, "43–58 MPa", lambda item: 43 <= item <= 58)

    status = "fail" if any(item.status == "fail" for item in checks) else "pass" if all(item.status == "pass" for item in checks) else "review"
    return QualityGate(status=status, checks=checks)  # type: ignore[arg-type]
