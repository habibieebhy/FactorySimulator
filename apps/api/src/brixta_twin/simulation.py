from .blending import preview_blend
from .models import Blend, Machine, Material, Route, RunEvent, RunRequest, RunResult, new_id, now
from .storage import Repository


class Engine:
    def __init__(self, repo: Repository):
        self.repo = repo

    def run(self, request: RunRequest) -> RunResult:
        blend = self.repo.get("blends", request.blend_id)
        route = self.repo.get("routes", request.route_id)
        if not isinstance(blend, Blend) or not isinstance(route, Route):
            raise ValueError("Unknown blend or route")

        preview = preview_blend(self.repo, blend, root_id=blend.blend_id)
        materials: dict[str, Material] = {}
        for component in preview.flattened_components:
            value = self.repo.get("materials", component.material_id)
            if not isinstance(value, Material):
                raise ValueError(f"Unknown material {component.material_id}")
            materials[component.material_id] = value

        machines: list[Machine] = []
        for node in route.nodes:
            value = self.repo.get("machines", node.machine_id)
            if not isinstance(value, Machine):
                raise ValueError(f"Unknown machine {node.machine_id}")
            machines.append(value)

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

        log("INFO", "RUN", "Simulation initialized")
        log("LOAD", "BLEND", f"Loaded {blend.name}")
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
        warnings = list(preview.warnings)
        if blend.blend_class != "finished_cement":
            warnings.append(
                "This route-level energy and output model is presently calibrated as a finished-cement screening route; use this blend class primarily for composition research"
            )
        if blend.blend_class == "raw_meal":
            lsf_denominator = (
                2.8 * chemistry.sio2
                + 1.18 * chemistry.al2o3
                + 0.65 * chemistry.fe2o3
            )
            lsf = chemistry.cao / lsf_denominator if lsf_denominator else None
            sm_denominator = chemistry.al2o3 + chemistry.fe2o3
            sm = chemistry.sio2 / sm_denominator if sm_denominator else None
            am = chemistry.al2o3 / chemistry.fe2o3 if chemistry.fe2o3 else None
            log(
                "CALC",
                "RAW_MEAL",
                "LSF={} SM={} AM={}".format(
                    f"{lsf:.3f}" if lsf is not None else "N/A",
                    f"{sm:.3f}" if sm is not None else "N/A",
                    f"{am:.3f}" if am is not None else "N/A",
                ),
            )
        else:
            warnings.append(
                "LSF, SM and AM are withheld because they are raw-meal control metrics, not finished-blend quality scores"
            )
            log(
                "CHECK",
                "CHEMISTRY",
                f"Weighted {blend.blend_class.replace('_', ' ')} chemistry calculated; raw-meal moduli withheld",
            )

        capacities = {
            machine.machine_id: machine.rated_capacity_tph * machine.availability
            for machine in machines
        }
        if not capacities:
            raise ValueError("Route contains no machines")
        bottleneck = min(capacities.values())
        output = min(request.target_output_tph, bottleneck)
        for machine in machines:
            capacity = capacities[machine.machine_id]
            log(
                "FLOW",
                machine.machine_id,
                f"capacity={capacity:.2f} t/h load={output / capacity * 100:.1f}%",
            )
            if request.target_output_tph > capacity:
                warnings.append(
                    f"{machine.name} constrains output at {capacity:.2f} t/h"
                )

        clinker_fraction = sum(
            component.percentage / 100.0
            for component in preview.flattened_components
            if materials[component.material_id].material_type == "clinker"
        )
        electricity = sum(
            machine.specific_electricity_kwh_t for machine in machines
        )
        thermal = (
            sum(machine.specific_heat_kcal_kg for machine in machines)
            * clinker_fraction
        )
        energy_cost = (
            electricity * request.electricity_inr_kwh
            + thermal * request.thermal_fuel_inr_mkcal / 1000
        )
        log(
            "HEAT",
            "ROUTE",
            f"electricity={electricity:.1f} kWh/t thermal={thermal:.1f} kcal/kg",
        )
        log(
            "CALC",
            "COST",
            f"material=₹{preview.material_cost_inr_t:.0f}/t energy=₹{energy_cost:.0f}/t",
        )
        for warning in warnings:
            log("WARN", "VALIDATION", warning)
        log(
            "CHECK",
            "MASS",
            f"Direct={preview.direct_total_percentage:.3f}% flattened={preview.flattened_total_percentage:.3f}%",
        )
        log("RESULT", "RUN", f"Completed with {len(warnings)} warnings")

        result = RunResult(
            run_id=new_id("run"),
            created_at=now(),
            request=request,
            chemistry=chemistry,
            lsf=lsf,
            silica_modulus=sm,
            alumina_modulus=am,
            bottleneck_tph=bottleneck,
            achievable_output_tph=output,
            electricity_kwh_t=electricity,
            thermal_kcal_kg=thermal,
            material_cost_inr_t=preview.material_cost_inr_t,
            energy_cost_inr_t=energy_cost,
            estimated_co2_kg_t=preview.estimated_co2_kg_t,
            resolved_components=preview.flattened_components,
            warnings=warnings,
            events=events,
        )
        self.repo.save("runs", result)
        return result
