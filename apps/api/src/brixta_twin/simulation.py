from __future__ import annotations

from .blending import preview_blend
from .models import (
    AssumptionRecord,
    Blend,
    CarbonBreakdown,
    CostBook,
    CostBreakdown,
    EnergyBreakdown,
    Evidence,
    Machine,
    MachineRunMetric,
    Material,
    MaterialRunMetric,
    Route,
    RunEvent,
    RunRequest,
    RunResult,
    ValidationMessage,
    new_id,
    now,
)
from .storage import Repository


CALCULATION_VERSION = "0.4.0"


def _unique_evidence(items: list[Evidence]) -> list[Evidence]:
    seen: set[tuple[str, str, str | None, str | None]] = set()
    unique: list[Evidence] = []
    for item in items:
        key = (item.evidence_class, item.source_title, item.source_uri, item.page)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


class Engine:
    def __init__(self, repo: Repository):
        self.repo = repo

    def run(self, request: RunRequest) -> RunResult:
        blend = self.repo.get("blends", request.blend_id)
        route = self.repo.get("routes", request.route_id)
        if not isinstance(blend, Blend) or not isinstance(route, Route):
            raise ValueError("Unknown blend or route")
        cost_book = None
        if request.cost_book_id:
            stored_cost_book = self.repo.get("cost_books", request.cost_book_id)
            if not isinstance(stored_cost_book, CostBook):
                raise ValueError("Unknown cost book")
            cost_book = stored_cost_book

        preview = preview_blend(self.repo, blend, root_id=blend.blend_id)
        materials: dict[str, Material] = {}
        for component in preview.flattened_components:
            value = self.repo.get("materials", component.material_id)
            if not isinstance(value, Material):
                raise ValueError(f"Unknown material {component.material_id}")
            materials[component.material_id] = value

        machines: list[tuple[str, Machine]] = []
        for node in route.nodes:
            value = self.repo.get("machines", node.machine_id)
            if not isinstance(value, Machine):
                raise ValueError(f"Unknown machine {node.machine_id}")
            machines.append((node.node_id, value))
        if not machines:
            raise ValueError("Route contains no machines")
        route_stages = {machine.process_stage for _, machine in machines}
        produces_clinker = "thermal_transformation" in route_stages
        produces_calcined_clay = "clay_calcination" in route_stages
        has_upstream_clinker_process = bool(
            route_stages.intersection(
                {"crushing", "raw_grinding", "thermal_transformation"}
            )
        )

        events: list[RunEvent] = []

        def log(level: str, component: str, message: str) -> None:
            events.append(
                RunEvent(
                    sequence=len(events) + 1,
                    elapsed_seconds=round(len(events) * 0.17, 2),
                    level=level,
                    component=component,
                    message=message,
                )
            )

        validation: list[ValidationMessage] = []

        def validate(severity: str, code: str, message: str) -> None:
            validation.append(
                ValidationMessage(severity=severity, code=code, message=message)  # type: ignore[arg-type]
            )
            log("WARN" if severity != "info" else "INFO", code, message)

        log("INFO", "RUN", f"Simulation initialized with calculation model {CALCULATION_VERSION}")
        log("LOAD", "BLEND", f"Loaded immutable blend {blend.name} v{blend.version}")
        log("LOAD", "ROUTE", f"Loaded immutable route {route.name} v{route.version} ({route.route_kind})")
        if cost_book:
            log("LOAD", "COST_BOOK", f"Loaded cost book {cost_book.name} v{cost_book.version}")
        else:
            validate(
                "warning",
                "NO_COST_BOOK",
                "No versioned cost book selected; only legacy purchased-material prices and run tariffs are available",
            )
        if any(item.component_type == "blend" for item in blend.components):
            log(
                "EXPAND",
                "BLEND",
                f"Nested recipe flattened to {len(preview.flattened_components)} base materials",
            )

        chemistry = preview.chemistry
        lsf = None
        sm = None
        am = None
        if blend.blend_class == "raw_meal":
            lsf_denominator = (
                2.8 * chemistry.sio2
                + 1.18 * chemistry.al2o3
                + 0.65 * chemistry.fe2o3
            )
            lsf = chemistry.cao / lsf_denominator * 100 if lsf_denominator else None
            sm_denominator = chemistry.al2o3 + chemistry.fe2o3
            sm = chemistry.sio2 / sm_denominator if sm_denominator else None
            am = chemistry.al2o3 / chemistry.fe2o3 if chemistry.fe2o3 else None
            log(
                "CALC",
                "RAW_MEAL",
                "LSF={} SM={} AM={}".format(
                    f"{lsf:.2f}" if lsf is not None else "N/A",
                    f"{sm:.3f}" if sm is not None else "N/A",
                    f"{am:.3f}" if am is not None else "N/A",
                ),
            )
        else:
            validate(
                "info",
                "CHEMISTRY_SCOPE",
                "LSF, SM and AM are not applicable because this is not a raw-meal blend",
            )
            log("CHECK", "CHEMISTRY", f"Weighted {blend.blend_class.replace('_', ' ')} chemistry calculated")

        for warning in preview.warnings:
            code = "DATA_GAP" if "no " in warning.lower() or "unreported" in warning.lower() else "VALIDATION"
            validate("warning", code, warning)
        validate(
            "warning",
            "PHYSICAL_VALIDATION",
            "No laboratory or plant performance validation is attached to this run",
        )

        fractions_by_type: dict[str, float] = {}
        for component in preview.flattened_components:
            fractions_by_type[component.material_type] = (
                fractions_by_type.get(component.material_type, 0.0)
                + component.percentage / 100.0
            )
        clinker_fraction = fractions_by_type.get("clinker", 0.0)
        calcined_clay_fraction = fractions_by_type.get("calcined_clay", 0.0)

        def stage_factor(machine: Machine) -> float:
            if blend.blend_class != "finished_cement":
                return 1.0
            if not has_upstream_clinker_process and not produces_calcined_clay:
                return 1.0
            if machine.process_stage in {"crushing", "raw_grinding"}:
                return clinker_fraction / request.raw_meal_to_clinker_yield
            if machine.process_stage == "thermal_transformation":
                return clinker_fraction
            if machine.process_stage == "clay_calcination":
                return calcined_clay_fraction
            return 1.0

        capacity_candidates: list[tuple[float, str, Machine]] = []
        machine_factors: list[tuple[str, Machine, float, float, float | None]] = []
        for node_id, machine in machines:
            factor = stage_factor(machine)
            effective_capacity = machine.rated_capacity_tph * machine.availability
            cement_capacity = effective_capacity / factor if factor > 0 else None
            if cement_capacity is not None:
                capacity_candidates.append((cement_capacity, node_id, machine))
            machine_factors.append((node_id, machine, factor, effective_capacity, cement_capacity))

        if not capacity_candidates:
            raise ValueError("No route machine is required by this blend")
        bottleneck, bottleneck_node_id, bottleneck_machine = min(
            capacity_candidates, key=lambda item: item[0]
        )
        output = min(request.target_output_tph, bottleneck)
        total_output = output * request.duration_hours

        machine_metrics: list[MachineRunMetric] = []
        electricity = 0.0
        thermal = 0.0
        for node_id, machine, factor, effective_capacity, cement_capacity in machine_factors:
            actual_throughput = output * factor
            load_percent = actual_throughput / effective_capacity * 100 if effective_capacity else 0
            electricity_contribution = machine.specific_electricity_kwh_t * factor
            thermal_contribution = machine.specific_heat_kcal_kg * factor
            electricity += electricity_contribution
            thermal += thermal_contribution
            machine_metrics.append(
                MachineRunMetric(
                    node_id=node_id,
                    machine_id=machine.machine_id,
                    machine_name=machine.name,
                    process_stage=machine.process_stage,
                    throughput_factor_t_stage_per_t_cement=factor,
                    actual_throughput_tph=actual_throughput,
                    effective_capacity_tph=effective_capacity,
                    cement_equivalent_capacity_tph=cement_capacity,
                    load_percent=load_percent,
                    electricity_kwh_t_cement=electricity_contribution,
                    thermal_kcal_kg_cement=thermal_contribution,
                )
            )
            log(
                "FLOW",
                machine.machine_id,
                f"stage={actual_throughput:.2f} t/h capacity={effective_capacity:.2f} t/h load={load_percent:.1f}% factor={factor:.4f}",
            )
            if factor > 0 and actual_throughput < machine.minimum_stable_tph:
                validate(
                    "warning",
                    "MINIMUM_STABLE_LOAD",
                    f"{machine.name} operates below its stored minimum stable load",
                )
            if machine.technology_readiness_level < 8:
                validate(
                    "warning",
                    "LOW_TRL",
                    f"{machine.name} is TRL {machine.technology_readiness_level}; exclude it from an investor base case",
                )

        if request.target_output_tph > bottleneck:
            validate(
                "warning",
                "CAPACITY_CONSTRAINT",
                f"{bottleneck_machine.name} constrains cement output at {bottleneck:.2f} t/h",
            )
        else:
            validate(
                "info",
                "CAPACITY_HEADROOM",
                f"Target is feasible; {bottleneck_machine.name} has {bottleneck - output:.2f} t/h cement-equivalent headroom",
            )

        electricity_rate = (
            cost_book.electricity_inr_kwh
            if cost_book and cost_book.electricity_inr_kwh is not None
            else request.electricity_inr_kwh
        )
        thermal_rate = (
            cost_book.thermal_fuel_inr_mkcal
            if cost_book and cost_book.thermal_fuel_inr_mkcal is not None
            else request.thermal_fuel_inr_mkcal
        )
        electricity_cost = electricity * electricity_rate
        thermal_cost = thermal * thermal_rate / 1000
        energy_cost = electricity_cost + thermal_cost
        material_metrics: list[MaterialRunMetric] = []
        material_cost_entries = {
            entry.material_id: entry for entry in (cost_book.material_costs if cost_book else [])
        }
        material_cost_contributions: list[float] = []
        missing_material_costs: list[str] = []

        def applied_material_cost(material: Material) -> tuple[float | None, str]:
            internally_produced = (
                material.material_type == "clinker" and produces_clinker
            ) or (
                material.material_type == "calcined_clay" and produces_calcined_clay
            )
            entry = material_cost_entries.get(material.material_id)
            if internally_produced:
                return (
                    entry.internal_feed_cost_inr_t if entry else None,
                    "internal feed/raw-material cost; process energy added separately",
                )
            if entry:
                return entry.purchased_delivered_cost_inr_t, "purchased delivered cost from cost book"
            if cost_book:
                return None, "missing purchased cost in selected cost book"
            return material.cost_inr_per_t, "legacy material-record purchased cost"

        for component in preview.flattened_components:
            material = materials[component.material_id]
            fraction = component.percentage / 100.0
            unit_cost, cost_basis = applied_material_cost(material)
            contribution = unit_cost * fraction if unit_cost is not None else None
            if contribution is None:
                missing_material_costs.append(material.name)
            else:
                material_cost_contributions.append(contribution)
            material_metrics.append(
                MaterialRunMetric(
                    material_id=material.material_id,
                    material_name=material.name,
                    material_type=material.material_type,
                    percentage=component.percentage,
                    tonnes_per_hour=output * fraction,
                    tonnes_per_run=total_output * fraction,
                    applied_unit_cost_inr_t=unit_cost,
                    cost_basis=cost_basis,
                    cost_inr_t_cement=contribution,
                    co2_kg_t_cement=(material.co2_kg_per_t * fraction if material.co2_kg_per_t is not None else None),
                    evidence_class=component.evidence_class,
                )
            )

        material_cost = (
            sum(material_cost_contributions) if not missing_material_costs else None
        )
        if missing_material_costs:
            validate(
                "warning",
                "MISSING_ROUTE_COST",
                "Cost is N/A because the selected route/cost book has no applicable price for: "
                + ", ".join(missing_material_costs),
            )
        direct_cost = material_cost + energy_cost if material_cost is not None else None

        operating_fields = [
            cost_book.packing_inr_t if cost_book else None,
            cost_book.labour_inr_t if cost_book else None,
            cost_book.maintenance_inr_t if cost_book else None,
            cost_book.other_variable_inr_t if cost_book else None,
        ]
        plant_cash_cost = (
            direct_cost + sum(value for value in operating_fields if value is not None)
            if direct_cost is not None and all(value is not None for value in operating_fields)
            else None
        )
        full_cost = (
            plant_cash_cost
            + cost_book.factory_overhead_inr_t
            + cost_book.outbound_logistics_inr_t
            if plant_cash_cost is not None
            and cost_book
            and cost_book.factory_overhead_inr_t is not None
            and cost_book.outbound_logistics_inr_t is not None
            else None
        )
        excluded_costs: list[str] = []
        if not cost_book or cost_book.packing_inr_t is None:
            excluded_costs.append("packing materials")
        if not cost_book or cost_book.labour_inr_t is None:
            excluded_costs.append("labour")
        if not cost_book or cost_book.maintenance_inr_t is None:
            excluded_costs.append("maintenance")
        if not cost_book or cost_book.other_variable_inr_t is None:
            excluded_costs.append("other variable operating costs")
        if not cost_book or cost_book.factory_overhead_inr_t is None:
            excluded_costs.append("factory overhead")
        if not cost_book or cost_book.outbound_logistics_inr_t is None:
            excluded_costs.append("outbound logistics")
        excluded_costs.extend(["depreciation", "finance", "taxes", "margin"])

        log("HEAT", "ROUTE", f"electricity={electricity:.2f} kWh/t thermal={thermal:.2f} kcal/kg")
        log(
            "CALC",
            "COST",
            "materials={} electricity=₹{:.0f}/t thermal=₹{:.0f}/t direct_total={}".format(
                f"₹{material_cost:.0f}/t" if material_cost is not None else "N/A",
                electricity_cost,
                thermal_cost,
                f"₹{direct_cost:.0f}/t" if direct_cost is not None else "N/A",
            ),
        )

        assumptions = [
            AssumptionRecord(key="calculation_version", value=CALCULATION_VERSION, basis="Deterministic screening engine"),
            AssumptionRecord(key="electricity_tariff", value=f"₹{electricity_rate:.2f}/kWh", basis=f"Cost book {cost_book.name}" if cost_book and cost_book.electricity_inr_kwh is not None else "Run input"),
            AssumptionRecord(key="thermal_fuel_tariff", value=f"₹{thermal_rate:.2f}/million kcal", basis=f"Cost book {cost_book.name}" if cost_book and cost_book.thermal_fuel_inr_mkcal is not None else "Run input"),
            AssumptionRecord(key="run_duration", value=f"{request.duration_hours:.2f} h", basis="Run input"),
        ]
        assumptions.append(
            AssumptionRecord(
                key="cost_book",
                value=f"{cost_book.name} v{cost_book.version}" if cost_book else "None",
                basis="Immutable run snapshot" if cost_book else "Legacy fallback; not investor-grade",
            )
        )
        if has_upstream_clinker_process:
            assumptions.append(
                AssumptionRecord(
                    key="raw_meal_to_clinker_yield",
                    value=f"{request.raw_meal_to_clinker_yield:.3f}",
                    basis="Run input used to convert upstream equipment capacity to cement-equivalent capacity",
                )
            )

        evidence = list(blend.evidence)
        for material in materials.values():
            evidence.extend(material.evidence)
        for _, machine in machines:
            evidence.extend(machine.evidence)
        if cost_book:
            evidence.extend(cost_book.evidence)

        warnings = [item.message for item in validation if item.severity in {"warning", "block"}]
        information = [item.message for item in validation if item.severity == "info"]
        log("CHECK", "MASS", f"Direct={preview.direct_total_percentage:.3f}% flattened={preview.flattened_total_percentage:.3f}%")
        log("RESULT", "RUN", f"Completed with {len(warnings)} warnings and {len(information)} information messages")

        result = RunResult(
            run_id=new_id("run"),
            created_at=now(),
            request=request,
            calculation_version=CALCULATION_VERSION,
            blend_snapshot=blend,
            route_snapshot=route,
            cost_book_snapshot=cost_book,
            material_snapshots=list(materials.values()),
            machine_snapshots=[machine for _, machine in machines],
            chemistry=chemistry,
            lsf=lsf,
            silica_modulus=sm,
            alumina_modulus=am,
            bottleneck_tph=bottleneck,
            bottleneck_machine_id=bottleneck_machine.machine_id,
            bottleneck_machine_name=bottleneck_machine.name,
            achievable_output_tph=output,
            total_output_tonnes=total_output,
            electricity_kwh_t=electricity,
            thermal_kcal_kg=thermal,
            material_cost_inr_t=material_cost,
            energy_cost_inr_t=energy_cost,
            direct_model_cost_inr_t=direct_cost,
            estimated_co2_kg_t=preview.estimated_co2_kg_t,
            resolved_components=preview.flattened_components,
            material_metrics=material_metrics,
            machine_metrics=machine_metrics,
            cost_breakdown=CostBreakdown(
                materials_inr_t=material_cost,
                electricity_inr_t=electricity_cost,
                thermal_inr_t=thermal_cost,
                energy_inr_t=energy_cost,
                direct_model_cost_inr_t=direct_cost,
                packing_inr_t=cost_book.packing_inr_t if cost_book else None,
                labour_inr_t=cost_book.labour_inr_t if cost_book else None,
                maintenance_inr_t=cost_book.maintenance_inr_t if cost_book else None,
                other_variable_inr_t=cost_book.other_variable_inr_t if cost_book else None,
                plant_cash_cost_inr_t=plant_cash_cost,
                factory_overhead_inr_t=cost_book.factory_overhead_inr_t if cost_book else None,
                outbound_logistics_inr_t=cost_book.outbound_logistics_inr_t if cost_book else None,
                full_cost_inr_t=full_cost,
                cost_book_name=cost_book.name if cost_book else None,
                excluded_costs=excluded_costs,
            ),
            energy_breakdown=EnergyBreakdown(
                electricity_kwh_t=electricity,
                thermal_kcal_kg=thermal,
                total_electricity_mwh=electricity * total_output / 1000,
                total_thermal_gcal=thermal * total_output / 1000,
            ),
            carbon_breakdown=CarbonBreakdown(
                materials_kg_co2_t=preview.estimated_co2_kg_t,
                total_materials_tonnes=total_output,
                total_materials_kg_co2=(preview.estimated_co2_kg_t * total_output if preview.estimated_co2_kg_t is not None else None),
                exclusions=["site-specific transport", "construction CAPEX", "downstream concrete use and carbonation"],
            ),
            validation=validation,
            warnings=warnings,
            information=information,
            assumptions=assumptions,
            evidence_references=_unique_evidence(evidence),
            events=events,
        )
        self.repo.save("runs", result)
        return result
