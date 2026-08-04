from __future__ import annotations

from .blending import chemistry_for_scenario, direct_production_fractions, preview_blend
from .models import (
    AssumptionRecord,
    Blend,
    CalculationTraceStep,
    CarbonBreakdown,
    Chemistry,
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
from .mineralogy import bogue_potential_phases, clinker_basis_chemistry, screen_clinker_behaviour
from .optimisation import cement_moduli, weighted_chemistry
from .quality import opc43_gate
from .routing import analyse_route, stage_throughput_factor
from .storage import Repository


CALCULATION_VERSION = "0.7.1"


def _output_product(blend: Blend, route: Route) -> str:
    if route.route_kind == "clinker_only":
        return "clinker"
    return {
        "raw_material_stockpile": "raw material",
        "raw_meal": "raw meal",
        "clinker_blend": "clinker",
        "finished_cement": "cement",
        "premix": "premix",
    }.get(blend.blend_class, "product")



def _process_stream_for_stage(stage: str) -> str:
    if stage in {"crushing", "raw_grinding"}:
        return "clinker_raw_feed"
    if stage == "thermal_transformation":
        return "clinker_line"
    if stage == "clay_calcination":
        return "calcined_clay_line"
    if stage in {"cement_grinding", "packing_dispatch"}:
        return "finished_cement"
    return "product_stream"


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

        preview = preview_blend(
            self.repo,
            blend,
            root_id=blend.blend_id,
            chemistry_scenario=request.chemistry_scenario,
        )
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
        output_product = _output_product(blend, route)
        has_cement_grinding = "cement_grinding" in route_stages
        produces_clinker = "thermal_transformation" in route_stages
        produces_calcined_clay = "clay_calcination" in route_stages
        has_upstream_clinker_process = bool(
            route_stages.intersection(
                {"crushing", "raw_grinding", "thermal_transformation"}
            )
        )

        events: list[RunEvent] = []
        calculation_trace: list[CalculationTraceStep] = []

        def trace(
            section: str,
            operation: str,
            formula: str,
            inputs: dict[str, float | str | None],
            result: float | str | None,
            unit: str | None = None,
            route_node_id: str | None = None,
        ) -> None:
            calculation_trace.append(
                CalculationTraceStep(
                    sequence=len(calculation_trace) + 1,
                    section=section,
                    operation=operation,
                    formula=formula,
                    inputs=inputs,
                    result=result,
                    unit=unit,
                    route_node_id=route_node_id,
                )
            )

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
        if request.target_blaine_m2_kg is not None and not has_cement_grinding:
            validate(
                "info",
                "BLAINE_NOT_APPLICABLE",
                "Target Blaine was ignored because the selected route has no cement-grinding stage",
            )
            request = request.model_copy(update={"target_blaine_m2_kg": None})
        if any(item.component_type == "blend" for item in blend.components):
            log(
                "EXPAND",
                "BLEND",
                f"Nested recipe flattened to {len(preview.flattened_components)} base materials",
            )

        chemistry = preview.chemistry
        lsf: float | None = None
        sm: float | None = None
        am: float | None = None
        if blend.blend_class == "raw_meal":
            lsf, sm, am = cement_moduli(chemistry)
            log(
                "CALC",
                "RAW_MEAL",
                "LSF={} SM={} AM={}".format(
                    f"{lsf:.2f}" if lsf is not None else "N/A",
                    f"{sm:.3f}" if sm is not None else "N/A",
                    f"{am:.3f}" if am is not None else "N/A",
                ),
            )
            trace(
                "chemistry",
                "Calculate raw-meal moduli",
                "LSF=100CaO/(2.8SiO2+1.18Al2O3+0.65Fe2O3); SM=SiO2/(Al2O3+Fe2O3); AM=Al2O3/Fe2O3",
                {"CaO": chemistry.cao, "SiO2": chemistry.sio2, "Al2O3": chemistry.al2o3, "Fe2O3": chemistry.fe2o3},
                (
                    f"LSF={lsf:.3f}, SM={sm:.4f}, AM={am:.4f}"
                    if None not in (lsf, sm, am)
                    else "incomplete chemistry"
                ),
            )
        else:
            validate(
                "info",
                "CHEMISTRY_SCOPE",
                "LSF, SM and AM are not applicable because this is not a raw-meal blend",
            )
            log("CHECK", "CHEMISTRY", f"Weighted {blend.blend_class.replace('_', ' ')} chemistry calculated")

        derived_yield: float | None = None
        effective_yield = request.raw_meal_to_clinker_yield
        if request.auto_mass_conversion and blend.blend_class == "raw_meal":
            if chemistry.loi is None:
                validate(
                    "warning",
                    "MASS_CONVERSION_UNKNOWN",
                    "Automatic raw-meal-to-clinker conversion requested, but LOI is unknown; the manual yield is retained",
                )
            else:
                moisture = request.kiln_feed_moisture_percent or 0.0
                derived_yield = max(
                    0.0,
                    min(1.0, (1.0 - chemistry.loi / 100.0) * (1.0 - moisture / 100.0)),
                )
                effective_yield = derived_yield
                log(
                    "CALC",
                    "MASS_CONVERSION",
                    f"LOI/moisture-derived raw-meal-to-clinker yield={derived_yield:.4f}",
                )
                trace(
                    "mass balance",
                    "Calculate raw-meal-to-clinker yield",
                    "yield=(1−LOI/100)×(1−feed moisture/100)",
                    {"LOI_percent": chemistry.loi, "feed_moisture_percent": moisture},
                    derived_yield,
                    "t clinker/t raw meal",
                )

        for warning in preview.warnings:
            code = "DATA_GAP" if "no " in warning.lower() or "unreported" in warning.lower() else "VALIDATION"
            validate("warning", code, warning)
        validate(
            "warning",
            "PHYSICAL_VALIDATION",
            "No laboratory or plant performance validation is attached to this run",
        )
        route_analysis = analyse_route(
            self.repo,
            blend,
            route,
            request.target_output_tph,
            effective_yield,
        )
        log("INFO", "ROUTE", route_analysis.description)
        log("FLOW", "ROUTE", route_analysis.flow_summary)
        if route_analysis.graph is not None:
            graph = route_analysis.graph
            log(
                "GRAPH",
                "ROUTE_DAG",
                "Kahn order={} | critical_path={}".format(
                    " → ".join(graph.topological_order) or "N/A",
                    " → ".join(graph.critical_path_labels) or "N/A",
                ),
            )
            trace(
                "route graph",
                "Validate and order process DAG",
                "Kahn topological sort; critical path by DAG dynamic programming using factor/effective-capacity node weights",
                {
                    "nodes": float(len(route.nodes)),
                    "edges": float(len(route.edges)),
                    "acyclic": str(graph.acyclic),
                },
                " → ".join(graph.topological_order) if graph.acyclic else "cycle/invalid graph",
            )
            if graph.acyclic:
                order = {node_id: index for index, node_id in enumerate(graph.topological_order)}
                machines.sort(key=lambda item: order.get(item[0], len(order)))
        if not route_analysis.compatible:
            validate(
                "block",
                "ROUTE_COMPATIBILITY",
                "Selected route is incomplete for this blend: "
                + (", ".join(route_analysis.missing_stages) or "no usable capacity"),
            )

        is_opc43_candidate = (
            blend.blend_class == "finished_cement"
            and (
                blend.family.upper().startswith("OPC")
                or "OPC" in (blend.applicable_standard or "").upper()
            )
        )
        quality_gate = opc43_gate(request.quality_measurements) if is_opc43_candidate else None
        if quality_gate is not None:
            if quality_gate.status == "fail":
                validate("block", "OPC43_GATE", "One or more measured OPC 43 quality requirements failed")
            elif quality_gate.status == "review":
                validate("warning", "OPC43_GATE", "OPC 43 production gate is incomplete; attach all required laboratory results")
            else:
                validate("info", "OPC43_GATE", "All supplied OPC 43 laboratory gate values pass")

        fractions_by_type: dict[str, float] = {}
        for component in preview.flattened_components:
            fractions_by_type[component.material_type] = (
                fractions_by_type.get(component.material_type, 0.0)
                + component.percentage / 100.0
            )
        production_fractions = direct_production_fractions(self.repo, blend)
        if blend.blend_class == "finished_cement":
            fractions_by_type["clinker"] = production_fractions["clinker"]
            fractions_by_type["calcined_clay"] = production_fractions["calcined_clay"]
        clinker_fraction = fractions_by_type.get("clinker", 0.0)
        calcined_clay_fraction = fractions_by_type.get("calcined_clay", 0.0)
        if blend.blend_class == "finished_cement":
            log(
                "FLOW",
                "PRODUCTION_STREAMS",
                f"clinker={clinker_fraction * 100:.3f}% calcined_clay={calcined_clay_fraction * 100:.3f}% "
                f"cement_additions={production_fractions['cement_addition'] * 100:.3f}%",
            )
            trace(
                "material streams",
                "Resolve direct and nested production streams",
                "finished-cement direct components retain semantic boundaries before recursive material flattening",
                {
                    "clinker_fraction": clinker_fraction,
                    "calcined_clay_fraction": calcined_clay_fraction,
                    "cement_addition_fraction": production_fractions["cement_addition"],
                },
                "stream fractions resolved",
            )

        fuel_ash_contribution: float | None = None
        fuel_ash_adjusted_chemistry: Chemistry | None = None
        fuel_material: Material | None = None
        if request.fuel_material_id:
            stored_fuel = self.repo.get("materials", request.fuel_material_id)
            if not isinstance(stored_fuel, Material):
                raise ValueError("Unknown fuel material")
            fuel_material = stored_fuel
            if request.fuel_rate_kg_t_clinker is None or stored_fuel.fuel_ash_percent is None:
                validate(
                    "warning",
                    "FUEL_ASH_UNKNOWN",
                    "Fuel ash contribution needs both fuel rate and ash percentage",
                )
            elif stored_fuel.fuel_ash_chemistry is None:
                validate(
                    "warning",
                    "FUEL_ASH_CHEMISTRY_UNKNOWN",
                    "Fuel ash mass is known but its oxide chemistry is missing",
                )
            elif blend.blend_class != "raw_meal":
                validate(
                    "info",
                    "FUEL_ASH_SCOPE",
                    "Fuel ash chemistry is only merged into raw-meal kiln calculations",
                )
            else:
                fuel_ash_contribution = (
                    request.fuel_rate_kg_t_clinker * stored_fuel.fuel_ash_percent / 100.0
                )
                log(
                    "CALC",
                    "FUEL_ASH",
                    f"Fuel ash adds {fuel_ash_contribution:.2f} kg/t clinker to the kiln mineral input",
                )
                trace(
                    "kiln chemistry",
                    "Calculate retained fuel-ash mass",
                    "ash kg/t clinker = fuel kg/t clinker × ash % / 100",
                    {
                        "fuel_rate_kg_t_clinker": request.fuel_rate_kg_t_clinker,
                        "fuel_ash_percent": stored_fuel.fuel_ash_percent,
                    },
                    fuel_ash_contribution,
                    "kg/t clinker",
                )

        clinker_chemistry: Chemistry | None = None
        clinker_mineralogy = None
        clinker_behaviour = None
        clinker_lsf: float | None = None
        clinker_sm: float | None = None
        clinker_am: float | None = None
        clinker_basis_warnings: list[str] = []
        clinker_basis_source: str | None = None

        if blend.blend_class == "raw_meal" and produces_clinker:
            clinker_chemistry, clinker_basis_warnings = clinker_basis_chemistry(
                chemistry,
                effective_yield,
                fuel_material.fuel_ash_chemistry if fuel_material else None,
                fuel_ash_contribution,
            )
            clinker_basis_source = "predicted from raw meal after LOI/moisture loss and retained fuel ash"
            fuel_ash_adjusted_chemistry = (
                clinker_chemistry if fuel_ash_contribution is not None else None
            )
        elif clinker_fraction > 0:
            direct_clinker_components = [
                component
                for component in preview.flattened_components
                if component.production_stream == "clinker"
                and component.material_type == "clinker"
            ]
            clinker_feed_components = [
                component
                for component in preview.flattened_components
                if component.production_stream == "clinker_raw_feed"
            ]
            chemistry_candidates: list[tuple[Chemistry, float, str]] = []
            if direct_clinker_components:
                subset_fraction = sum(item.percentage for item in direct_clinker_components) / 100.0
                subset_materials = [materials[item.material_id] for item in direct_clinker_components]
                subset_percentages = [
                    item.percentage / max(subset_fraction, 1e-12)
                    for item in direct_clinker_components
                ]
                direct_chemistry = weighted_chemistry(
                    subset_materials,
                    subset_percentages,
                    request.chemistry_scenario,
                )
                normalised_direct, direct_warnings = clinker_basis_chemistry(direct_chemistry)
                clinker_basis_warnings.extend(direct_warnings)
                if normalised_direct is not None:
                    chemistry_candidates.append((normalised_direct, subset_fraction, "direct clinker material"))

            if clinker_feed_components:
                feed_fraction = sum(item.percentage for item in clinker_feed_components) / 100.0
                feed_materials = [materials[item.material_id] for item in clinker_feed_components]
                feed_percentages = [
                    item.percentage / max(feed_fraction, 1e-12)
                    for item in clinker_feed_components
                ]
                nested_raw_chemistry = weighted_chemistry(
                    feed_materials,
                    feed_percentages,
                    request.chemistry_scenario,
                )
                predicted_nested, nested_warnings = clinker_basis_chemistry(
                    nested_raw_chemistry,
                    effective_yield,
                    fuel_material.fuel_ash_chemistry if fuel_material else None,
                    fuel_ash_contribution,
                )
                clinker_basis_warnings.extend(nested_warnings)
                if predicted_nested is not None:
                    chemistry_candidates.append((predicted_nested, feed_fraction, "nested clinker/raw-meal recipe"))

            if chemistry_candidates:
                weights_total = sum(weight for _, weight, _ in chemistry_candidates)
                combined_values: dict[str, float | None] = {}
                for oxide in Chemistry.model_fields:
                    reported = [
                        (getattr(candidate, oxide), weight)
                        for candidate, weight, _ in chemistry_candidates
                    ]
                    if any(value is None for value, _ in reported):
                        combined_values[oxide] = None
                    else:
                        combined_values[oxide] = sum(
                            float(value) * weight for value, weight in reported if value is not None
                        ) / max(weights_total, 1e-12)
                clinker_chemistry = Chemistry(**combined_values)
                sources = ", ".join(source for _, _, source in chemistry_candidates)
                clinker_basis_source = f"combined from {sources}"
                trace(
                    "clinker chemistry",
                    "Resolve clinker-producing nested recipe",
                    "preserve direct clinker/raw-meal component boundary; predict clinker chemistry for raw-feed subset; combine on clinker-output share",
                    {
                        "clinker_fraction_of_cement": clinker_fraction,
                        "direct_clinker_fraction": sum(item.percentage for item in direct_clinker_components) / 100.0,
                        "nested_clinker_recipe_fraction": sum(item.percentage for item in clinker_feed_components) / 100.0,
                        "raw_meal_to_clinker_yield": effective_yield,
                    },
                    clinker_basis_source,
                )

        for warning in clinker_basis_warnings:
            validate("warning", "CLINKER_CHEMISTRY_BASIS", warning)

        if clinker_chemistry is not None:
            clinker_lsf, clinker_sm, clinker_am = cement_moduli(clinker_chemistry)
            clinker_mineralogy = bogue_potential_phases(clinker_chemistry)
            clinker_behaviour = screen_clinker_behaviour(
                clinker_chemistry,
                clinker_mineralogy,
                clinker_lsf,
                clinker_sm,
                clinker_am,
                request.kiln_temperature_c,
            )
            log(
                "CALC",
                "CLINKER_CHEMISTRY",
                "{} | LSF={} SM={} AM={}".format(
                    clinker_basis_source or "clinker basis",
                    f"{clinker_lsf:.2f}" if clinker_lsf is not None else "N/A",
                    f"{clinker_sm:.3f}" if clinker_sm is not None else "N/A",
                    f"{clinker_am:.3f}" if clinker_am is not None else "N/A",
                ),
            )
            trace(
                "clinker chemistry",
                "Establish clinker oxide calculation basis",
                "raw-meal route: oxide mass/t clinker=(raw oxide%×1000/yield)+(ash kg/t×ash oxide%); direct-clinker route: isolate clinker constituent; then normalise reported nonvolatile oxides to 100%",
                {
                    "raw_meal_to_clinker_yield": effective_yield if blend.blend_class == "raw_meal" else None,
                    "fuel_ash_kg_t_clinker": fuel_ash_contribution,
                    "clinker_fraction_of_recipe": clinker_fraction,
                },
                clinker_basis_source or "clinker chemistry calculated",
            )
            if clinker_mineralogy is not None:
                ferrite = (
                    clinker_mineralogy.c4af_percent
                    if clinker_mineralogy.c4af_percent is not None
                    else clinker_mineralogy.calcium_aluminoferrite_ss_percent
                )
                log(
                    "CALC",
                    "MINERALOGY",
                    "Bogue potential phases C3S={} C2S={} C3A={} ferrite={}".format(
                        f"{clinker_mineralogy.c3s_percent:.2f}%" if clinker_mineralogy.c3s_percent is not None else "N/A",
                        f"{clinker_mineralogy.c2s_percent:.2f}%" if clinker_mineralogy.c2s_percent is not None else "N/A",
                        f"{clinker_mineralogy.c3a_percent:.2f}%" if clinker_mineralogy.c3a_percent is not None else "N/A",
                        f"{ferrite:.2f}%" if ferrite is not None else "N/A",
                    ),
                )
                trace(
                    "clinker mineralogy",
                    "Estimate potential clinker phases",
                    "ASTM-style Bogue equations on loss-free clinker oxides; A/F<0.64 uses calcium aluminoferrite solid-solution branch",
                    {
                        "CaO": clinker_chemistry.cao,
                        "SiO2": clinker_chemistry.sio2,
                        "Al2O3": clinker_chemistry.al2o3,
                        "Fe2O3": clinker_chemistry.fe2o3,
                        "SO3": clinker_chemistry.so3,
                    },
                    (
                        f"C3S={clinker_mineralogy.c3s_percent}, C2S={clinker_mineralogy.c2s_percent}, "
                        f"C3A={clinker_mineralogy.c3a_percent}, ferrite={ferrite}"
                    ),
                    "mass % potential phase",
                )
                for warning in clinker_mineralogy.warnings:
                    validate("info", "BOGUE_LIMITATION", warning)
            if clinker_behaviour is not None:
                log(
                    "CHECK",
                    "CLINKER_BEHAVIOUR",
                    f"burnability={clinker_behaviour.burnability_class} ({clinker_behaviour.burnability_score}) "
                    f"free_lime_risk={clinker_behaviour.free_lime_risk} fuel={clinker_behaviour.expected_fuel_demand}",
                )
                trace(
                    "clinker behaviour",
                    "Screen burnability and expected behaviour",
                    "Transparent penalties from LSF, SM, liquid-phase proxy, potential C3S and entered kiln temperature",
                    {
                        "LSF": clinker_lsf,
                        "SM": clinker_sm,
                        "liquid_phase_1450_percent": clinker_behaviour.liquid_phase_1450_percent,
                        "kiln_temperature_c": request.kiln_temperature_c,
                    },
                    f"score={clinker_behaviour.burnability_score}; class={clinker_behaviour.burnability_class}",
                )
        elif produces_clinker:
            validate(
                "info",
                "MINERALOGY_SCOPE",
                "Clinker mineralogy requires raw-meal chemistry or a direct clinker constituent with major-oxide chemistry",
            )

        weighted_grindability = 0.0
        grindability_complete = True
        for component in preview.flattened_components:
            material = materials[component.material_id]
            if material.grindability_factor is None:
                grindability_complete = False
                weighted_grindability += component.percentage / 100.0
            else:
                weighted_grindability += material.grindability_factor * component.percentage / 100.0
        target_blaine = request.target_blaine_m2_kg
        grinding_capacity_factor = 1.0
        grinding_energy_factor = 1.0
        design_blaines = [
            machine.design_blaine_m2_kg
            for _, machine in machines
            if machine.process_stage == "cement_grinding" and machine.design_blaine_m2_kg is not None
        ]
        if target_blaine is not None and design_blaines:
            design_blaine = sum(design_blaines) / len(design_blaines)
            fineness_ratio = max(target_blaine / design_blaine, 0.1)
            grinding_capacity_factor = max(0.35, min(1.5, fineness_ratio ** -0.55 / weighted_grindability))
            grinding_energy_factor = max(0.5, min(2.5, fineness_ratio ** 0.65 * weighted_grindability))
            log(
                "CALC",
                "GRINDING",
                f"Blaine/grindability capacity factor={grinding_capacity_factor:.3f} energy factor={grinding_energy_factor:.3f}",
            )
            if not grindability_complete:
                validate(
                    "warning",
                    "GRINDABILITY_ASSUMED",
                    "One or more material grindability factors are unknown; 1.0 was used for those components",
                )

        capacity_candidates: list[tuple[float, str, Machine]] = []
        machine_factors: list[tuple[str, Machine, float, float, float | None]] = []
        for node_id, machine in machines:
            factor = stage_throughput_factor(
                machine,
                blend,
                route_stages,
                fractions_by_type,
                effective_yield,
                route.route_kind,
            )
            effective_capacity = machine.rated_capacity_tph * machine.availability
            if machine.maximum_stable_tph is not None:
                effective_capacity = min(effective_capacity, machine.maximum_stable_tph)
            if machine.process_stage == "cement_grinding":
                effective_capacity *= grinding_capacity_factor
            output_capacity = effective_capacity / factor if factor > 0 else None
            if output_capacity is not None:
                capacity_candidates.append((output_capacity, node_id, machine))
            machine_factors.append((node_id, machine, factor, effective_capacity, output_capacity))

        # Validate every active kiln before publishing production, energy or
        # cost results.  A BLOCK is a failed operating case, not a warning that
        # may coexist with a successful achieved-output headline.
        for _, machine, factor, _, _ in machine_factors:
            if factor <= 0 or machine.process_stage != "thermal_transformation":
                continue
            if (
                machine.maximum_feed_moisture_percent is not None
                and request.kiln_feed_moisture_percent is not None
                and request.kiln_feed_moisture_percent > machine.maximum_feed_moisture_percent
            ):
                validate("block", "KILN_MOISTURE_ENVELOPE", f"Kiln feed moisture exceeds {machine.name}'s stored limit")
            if (
                machine.minimum_temperature_c is not None
                and request.kiln_temperature_c is not None
                and request.kiln_temperature_c < machine.minimum_temperature_c
            ):
                validate("block", "KILN_TEMPERATURE_ENVELOPE", f"Kiln temperature is below {machine.name}'s stored minimum")
            if (
                machine.maximum_temperature_c is not None
                and request.kiln_temperature_c is not None
                and request.kiln_temperature_c > machine.maximum_temperature_c
            ):
                validate("block", "KILN_TEMPERATURE_ENVELOPE", f"Kiln temperature exceeds {machine.name}'s stored maximum")
            if (
                machine.minimum_oxygen_percent is not None
                and request.kiln_oxygen_percent is not None
                and request.kiln_oxygen_percent < machine.minimum_oxygen_percent
            ):
                validate("block", "KILN_OXYGEN_ENVELOPE", f"Kiln oxygen is below {machine.name}'s stored minimum")
            if (
                machine.maximum_oxygen_percent is not None
                and request.kiln_oxygen_percent is not None
                and request.kiln_oxygen_percent > machine.maximum_oxygen_percent
            ):
                validate("block", "KILN_OXYGEN_ENVELOPE", f"Kiln oxygen exceeds {machine.name}'s stored maximum")
            if (
                machine.maximum_free_lime_percent is not None
                and request.clinker_free_lime_percent is not None
                and request.clinker_free_lime_percent > machine.maximum_free_lime_percent
            ):
                validate("block", "FREE_LIME_GATE", f"Measured clinker free lime exceeds {machine.name}'s stored limit")

        if not capacity_candidates:
            raise ValueError("No route machine is required by this blend")
        bottleneck, bottleneck_node_id, bottleneck_machine = min(
            capacity_candidates, key=lambda item: item[0]
        )
        run_blocked = any(item.severity == "block" for item in validation)
        output = 0.0 if run_blocked else min(request.target_output_tph, bottleneck)
        total_output = output * request.duration_hours

        machine_metrics: list[MachineRunMetric] = []
        electricity = 0.0
        thermal = 0.0
        for node_id, machine, factor, effective_capacity, output_capacity in machine_factors:
            actual_throughput = output * factor
            target_throughput = request.target_output_tph * factor
            load_percent = actual_throughput / effective_capacity * 100 if effective_capacity else 0
            target_load_percent = target_throughput / effective_capacity * 100 if effective_capacity else 0
            stage_energy_factor = grinding_energy_factor if machine.process_stage == "cement_grinding" else 1.0
            electricity_contribution = (
                0.0
                if run_blocked
                else machine.specific_electricity_kwh_t * factor * stage_energy_factor
            )
            thermal_contribution = (
                0.0 if run_blocked else machine.specific_heat_kcal_kg * factor
            )
            electricity += electricity_contribution
            thermal += thermal_contribution
            machine_metrics.append(
                MachineRunMetric(
                    node_id=node_id,
                    machine_id=machine.machine_id,
                    machine_name=machine.name,
                    process_stage=machine.process_stage,
                    process_stream=_process_stream_for_stage(machine.process_stage),
                    throughput_factor_t_stage_per_t_output=factor,
                    actual_throughput_tph=actual_throughput,
                    effective_capacity_tph=effective_capacity,
                    output_equivalent_capacity_tph=output_capacity,
                    target_throughput_tph=target_throughput,
                    target_load_percent=target_load_percent,
                    load_percent=load_percent,
                    electricity_kwh_t_output=electricity_contribution,
                    thermal_kcal_kg_output=thermal_contribution,
                )
            )
            log(
                "FLOW",
                node_id,
                f"machine={machine.name} stage={machine.process_stage} stream={_process_stream_for_stage(machine.process_stage)} throughput={actual_throughput:.2f} t/h "
                f"capacity={effective_capacity:.2f} t/h load={load_percent:.1f}% factor={factor:.4f} "
                f"electricity={electricity_contribution:.3f} kWh/t output thermal={thermal_contribution:.3f} kcal/kg output",
            )
            trace(
                "route execution",
                f"Execute {machine.process_stage} node",
                "required stage t/h=output t/h×stage factor; effective capacity=min(rated×availability, stable max); energy=specific energy×stage factor",
                {
                    "machine": machine.name,
                    "output_tph": output,
                    "stage_factor": factor,
                    "rated_capacity_tph": machine.rated_capacity_tph,
                    "availability": machine.availability,
                    "specific_electricity_kwh_t": machine.specific_electricity_kwh_t,
                    "specific_heat_kcal_kg": machine.specific_heat_kcal_kg,
                },
                f"stage={actual_throughput:.3f} t/h; load={load_percent:.2f}%; kWh/t output={electricity_contribution:.4f}; kcal/kg output={thermal_contribution:.4f}",
                route_node_id=node_id,
            )
            if not run_blocked and factor > 0 and actual_throughput < machine.minimum_stable_tph:
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
                f"{bottleneck_machine.name} constrains {output_product} output at {bottleneck:.2f} t/h",
            )
        else:
            validate(
                "info",
                "CAPACITY_HEADROOM",
                f"Target is feasible; {bottleneck_machine.name} has {bottleneck - output:.2f} t/h {output_product} headroom",
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
        electricity_tariff_source = (
            f"cost book {cost_book.name} v{cost_book.version}"
            if cost_book and cost_book.electricity_inr_kwh is not None
            else "run input"
        )
        thermal_tariff_source = (
            f"cost book {cost_book.name} v{cost_book.version}"
            if cost_book and cost_book.thermal_fuel_inr_mkcal is not None
            else "run input"
        )
        if (
            cost_book
            and cost_book.electricity_inr_kwh is not None
            and abs(cost_book.electricity_inr_kwh - request.electricity_inr_kwh) > 1e-9
        ):
            validate(
                "warning",
                "COST_BOOK_ELECTRICITY_OVERRIDE",
                "Selected cost book overrides the run electricity tariff: "
                f"₹{request.electricity_inr_kwh:.2f}/kWh entered, "
                f"₹{electricity_rate:.2f}/kWh applied",
            )
        if (
            cost_book
            and cost_book.thermal_fuel_inr_mkcal is not None
            and abs(cost_book.thermal_fuel_inr_mkcal - request.thermal_fuel_inr_mkcal) > 1e-9
        ):
            validate(
                "warning",
                "COST_BOOK_THERMAL_OVERRIDE",
                "Selected cost book overrides the run thermal-fuel tariff: "
                f"₹{request.thermal_fuel_inr_mkcal:.2f}/million kcal entered, "
                f"₹{thermal_rate:.2f}/million kcal applied",
            )
        electricity_cost = electricity * electricity_rate
        thermal_cost = thermal * thermal_rate / 1000
        energy_cost = electricity_cost + thermal_cost

        # Blend percentages live on the blend's own mass basis.  A raw-meal
        # recipe sent through a clinker-only route therefore consumes
        # 1 / yield tonnes of blend for every tonne of clinker output.  Finished
        # cement and all same-basis routes retain the normal 1:1 factor.
        material_input_factor = (
            1.0 / max(effective_yield, 1e-9)
            if blend.blend_class == "raw_meal" and output_product == "clinker"
            else 1.0
        )
        material_metrics: list[MaterialRunMetric] = []
        material_cost_entries = {
            entry.material_id: entry for entry in (cost_book.material_costs if cost_book else [])
        }
        material_cost_contributions: list[float] = []
        missing_material_costs: list[str] = []
        material_co2_contributions: list[float] = []
        missing_material_co2: list[str] = []

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
            stream_factor = (
                1.0 / max(effective_yield, 1e-9)
                if component.production_stream == "clinker_raw_feed"
                else material_input_factor
                if blend.blend_class == "raw_meal" and output_product == "clinker"
                else 1.0
            )
            tonnes_per_t_output = fraction * stream_factor
            unit_cost, cost_basis = applied_material_cost(material)
            contribution = (
                unit_cost * tonnes_per_t_output if unit_cost is not None else None
            )
            if contribution is None:
                missing_material_costs.append(material.name)
            else:
                material_cost_contributions.append(contribution)
            co2_contribution = (
                material.co2_kg_per_t * tonnes_per_t_output
                if material.co2_kg_per_t is not None
                else None
            )
            if co2_contribution is None:
                missing_material_co2.append(material.name)
            else:
                material_co2_contributions.append(co2_contribution)
            material_metrics.append(
                MaterialRunMetric(
                    material_id=material.material_id,
                    production_stream=component.production_stream,
                    material_name=material.name,
                    material_type=material.material_type,
                    percentage=component.percentage,
                    tonnes_per_t_output=tonnes_per_t_output,
                    tonnes_per_hour=output * tonnes_per_t_output,
                    tonnes_per_run=total_output * tonnes_per_t_output,
                    applied_unit_cost_inr_t=unit_cost,
                    cost_basis=cost_basis,
                    cost_inr_t_output=contribution,
                    co2_kg_t_output=co2_contribution,
                    evidence_class=component.evidence_class,
                )
            )

        total_material_input_tph = sum(
            item.tonnes_per_hour for item in material_metrics
        )
        total_material_input_tonnes = sum(
            item.tonnes_per_run for item in material_metrics
        )

        material_cost = (
            sum(material_cost_contributions)
            if not missing_material_costs and not run_blocked
            else None
        )
        material_co2 = (
            sum(material_co2_contributions)
            if not missing_material_co2 and not run_blocked
            else None
        )
        if missing_material_costs:
            validate(
                "warning",
                "MISSING_ROUTE_COST",
                "Cost is N/A because the selected route/cost book has no applicable price for: "
                + ", ".join(missing_material_costs),
            )
        direct_cost = material_cost + energy_cost if material_cost is not None else None

        clinker_only_cost_basis = output_product == "clinker" and not has_cement_grinding
        included_costs = ["route electricity", "route thermal fuel"]
        excluded_costs: list[str] = []
        if material_cost is None:
            excluded_costs.append("applicable material prices (not fully provided)")
        else:
            included_costs.insert(0, "applicable materials")

        if clinker_only_cost_basis:
            packing_cost = None
            labour_cost = cost_book.clinker_labour_inr_t if cost_book else None
            maintenance_cost = cost_book.clinker_maintenance_inr_t if cost_book else None
            other_variable_cost = (
                cost_book.clinker_other_variable_inr_t if cost_book else None
            )
            factory_overhead_cost = (
                cost_book.clinker_factory_overhead_inr_t if cost_book else None
            )
            outbound_logistics_cost = None
            operating_cost_basis = (
                "clinker-only output; only clinker-stage allocations are applied"
            )
            operating_fields = [labour_cost, maintenance_cost, other_variable_cost]
            plant_cash_cost = (
                direct_cost + sum(value for value in operating_fields if value is not None)
                if direct_cost is not None and all(value is not None for value in operating_fields)
                else None
            )
            full_cost = (
                plant_cash_cost + factory_overhead_cost
                if plant_cash_cost is not None and factory_overhead_cost is not None
                else None
            )
            excluded_costs.extend(
                [
                    "cement grinding (route not present)",
                    "cement packing and dispatch (route not present)",
                    "finished-cement outbound logistics (route not present)",
                    "cement-wide labour, maintenance and overhead allocations (not applied to clinker output)",
                ]
            )
            if cost_book and any(
                value is not None
                for value in (
                    cost_book.packing_inr_t,
                    cost_book.labour_inr_t,
                    cost_book.maintenance_inr_t,
                    cost_book.other_variable_inr_t,
                    cost_book.factory_overhead_inr_t,
                    cost_book.outbound_logistics_inr_t,
                )
            ):
                validate(
                    "info",
                    "CEMENT_DOWNSTREAM_COSTS_EXCLUDED",
                    "Cement-wide packing, dispatch, logistics and operating allocations were not charged to clinker output",
                )
            route_cost_fields = [
                ("clinker-stage labour", labour_cost),
                ("clinker-stage maintenance", maintenance_cost),
                ("clinker-stage other variable operating costs", other_variable_cost),
                ("clinker-stage factory overhead", factory_overhead_cost),
            ]
        else:
            packing_cost = cost_book.packing_inr_t if cost_book else None
            labour_cost = cost_book.labour_inr_t if cost_book else None
            maintenance_cost = cost_book.maintenance_inr_t if cost_book else None
            other_variable_cost = cost_book.other_variable_inr_t if cost_book else None
            factory_overhead_cost = cost_book.factory_overhead_inr_t if cost_book else None
            outbound_logistics_cost = (
                cost_book.outbound_logistics_inr_t if cost_book else None
            )
            operating_cost_basis = "finished-output cost-book allocation"
            operating_fields = [
                packing_cost,
                labour_cost,
                maintenance_cost,
                other_variable_cost,
            ]
            plant_cash_cost = (
                direct_cost + sum(value for value in operating_fields if value is not None)
                if direct_cost is not None and all(value is not None for value in operating_fields)
                else None
            )
            full_cost = (
                plant_cash_cost + factory_overhead_cost + outbound_logistics_cost
                if plant_cash_cost is not None
                and factory_overhead_cost is not None
                and outbound_logistics_cost is not None
                else None
            )
            route_cost_fields = [
                ("packing materials", packing_cost),
                ("labour", labour_cost),
                ("maintenance", maintenance_cost),
                ("other variable operating costs", other_variable_cost),
                ("factory overhead", factory_overhead_cost),
                ("outbound logistics", outbound_logistics_cost),
            ]

        for name, value in route_cost_fields:
            if value is None:
                excluded_costs.append(f"{name} (applicable value not provided)")
            else:
                included_costs.append(name)
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
            AssumptionRecord(key="electricity_tariff", value=f"₹{electricity_rate:.2f}/kWh", basis=electricity_tariff_source),
            AssumptionRecord(key="thermal_fuel_tariff", value=f"₹{thermal_rate:.2f}/million kcal", basis=thermal_tariff_source),
            AssumptionRecord(key="run_duration", value=f"{request.duration_hours:.2f} h", basis="Run input"),
            AssumptionRecord(
                key="material_input_basis",
                value=f"{material_input_factor:.6f} t input/t {output_product}",
                basis=(
                    "Raw-meal blend divided by raw-meal-to-clinker yield"
                    if material_input_factor != 1.0
                    else "Blend and output use the same mass basis"
                ),
            ),
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
                    value=f"{effective_yield:.3f}",
                    basis=(
                        "Derived from raw-meal LOI and entered moisture"
                        if derived_yield is not None
                        else "Run input used to convert upstream equipment capacity to output-equivalent capacity"
                    ),
                )
            )
        assumptions.extend(
            [
                AssumptionRecord(
                    key="chemistry_scenario",
                    value=request.chemistry_scenario,
                    basis="Material minimum/typical/maximum chemistry selection",
                ),
                AssumptionRecord(
                    key="route_graph_algorithm",
                    value="Kahn topological sort + DAG dynamic programming",
                    basis="Pure deterministic route ordering and critical-path analysis",
                ),
                AssumptionRecord(
                    key="clinker_mineralogy_method",
                    value="ASTM-style Bogue potential phases" if clinker_mineralogy else "Not applicable",
                    basis="Loss-free clinker oxide screening; not a substitute for XRD/Rietveld",
                ),
                AssumptionRecord(
                    key="grinding_capacity_factor",
                    value=f"{grinding_capacity_factor:.4f}",
                    basis=(
                        "Stored material grindability and target/design Blaine correction"
                        if has_cement_grinding
                        else "Not applicable; route has no cement-grinding stage"
                    ),
                ),
                AssumptionRecord(
                    key="grinding_energy_factor",
                    value=f"{grinding_energy_factor:.4f}",
                    basis=(
                        "Stored material grindability and target/design Blaine correction"
                        if has_cement_grinding
                        else "Not applicable; route has no cement-grinding stage"
                    ),
                ),
            ]
        )

        evidence = list(blend.evidence)
        for material in materials.values():
            evidence.extend(material.evidence)
        for _, machine in machines:
            evidence.extend(machine.evidence)
        if cost_book:
            evidence.extend(cost_book.evidence)
        if fuel_material:
            evidence.extend(fuel_material.evidence)

        warnings = [item.message for item in validation if item.severity in {"warning", "block"}]
        information = [item.message for item in validation if item.severity == "info"]
        log(
            "CHECK",
            "MASS",
            f"Direct={preview.direct_total_percentage:.3f}% "
            f"flattened={preview.flattened_total_percentage:.3f}% "
            f"output={output:.3f} t/h {output_product} "
            f"material_input={total_material_input_tph:.3f} t/h",
        )
        if run_blocked:
            log("RESULT", "RUN", "BLOCKED: no achieved production, energy or cost result is valid until all blocking conditions are resolved")
        else:
            log("RESULT", "RUN", f"Completed with {len(warnings)} warnings and {len(information)} information messages")

        result = RunResult(
            run_id=new_id("run"),
            created_at=now(),
            request=request,
            calculation_version=CALCULATION_VERSION,
            run_status="blocked" if run_blocked else "completed",
            output_product=output_product,
            blend_snapshot=blend,
            route_snapshot=route,
            cost_book_snapshot=cost_book,
            material_snapshots=list(materials.values()),
            machine_snapshots=[machine for _, machine in machines],
            chemistry=chemistry,
            chemistry_scenario=request.chemistry_scenario,
            route_analysis=route_analysis,
            quality_gate=quality_gate,
            derived_raw_meal_to_clinker_yield=derived_yield,
            fuel_ash_contribution_kg_t_clinker=fuel_ash_contribution,
            fuel_ash_adjusted_chemistry=fuel_ash_adjusted_chemistry,
            clinker_chemistry=clinker_chemistry,
            clinker_lsf=clinker_lsf,
            clinker_silica_modulus=clinker_sm,
            clinker_alumina_modulus=clinker_am,
            clinker_mineralogy=clinker_mineralogy,
            clinker_behaviour=clinker_behaviour,
            calculation_trace=calculation_trace,
            grinding_capacity_factor=grinding_capacity_factor,
            grinding_energy_factor=grinding_energy_factor,
            lsf=lsf,
            silica_modulus=sm,
            alumina_modulus=am,
            bottleneck_tph=bottleneck,
            bottleneck_machine_id=bottleneck_machine.machine_id,
            bottleneck_machine_name=bottleneck_machine.name,
            achievable_output_tph=output,
            total_output_tonnes=total_output,
            material_input_t_per_t_output=(total_material_input_tph / output if output > 0 else None),
            total_material_input_tph=total_material_input_tph,
            total_material_input_tonnes=total_material_input_tonnes,
            electricity_kwh_t=electricity,
            thermal_kcal_kg=thermal,
            applied_electricity_inr_kwh=electricity_rate,
            electricity_tariff_source=electricity_tariff_source,
            applied_thermal_fuel_inr_mkcal=thermal_rate,
            thermal_tariff_source=thermal_tariff_source,
            material_cost_inr_t=material_cost,
            energy_cost_inr_t=energy_cost,
            direct_model_cost_inr_t=direct_cost,
            estimated_co2_kg_t=material_co2,
            resolved_components=preview.flattened_components,
            material_metrics=material_metrics,
            machine_metrics=machine_metrics,
            cost_breakdown=CostBreakdown(
                materials_inr_t=material_cost,
                electricity_inr_t=electricity_cost,
                thermal_inr_t=thermal_cost,
                energy_inr_t=energy_cost,
                direct_model_cost_inr_t=direct_cost,
                packing_inr_t=packing_cost,
                labour_inr_t=labour_cost,
                maintenance_inr_t=maintenance_cost,
                other_variable_inr_t=other_variable_cost,
                plant_cash_cost_inr_t=plant_cash_cost,
                factory_overhead_inr_t=factory_overhead_cost,
                outbound_logistics_inr_t=outbound_logistics_cost,
                full_cost_inr_t=full_cost,
                cost_book_name=cost_book.name if cost_book else None,
                operating_cost_basis=operating_cost_basis,
                included_costs=included_costs,
                excluded_costs=excluded_costs,
            ),
            energy_breakdown=EnergyBreakdown(
                electricity_kwh_t=electricity,
                thermal_kcal_kg=thermal,
                total_electricity_mwh=electricity * total_output / 1000,
                total_thermal_gcal=thermal * total_output / 1000,
            ),
            carbon_breakdown=CarbonBreakdown(
                materials_kg_co2_t=(
                    material_co2
                ),
                total_materials_tonnes=total_material_input_tonnes,
                total_materials_kg_co2=(
                    material_co2 * total_output
                    if material_co2 is not None
                    else None
                ),
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
