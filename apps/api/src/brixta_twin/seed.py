from pydantic import BaseModel

from .models import (
    Blend,
    BlendComponent,
    Chemistry,
    CostBook,
    Evidence,
    Machine,
    Material,
    MaterialCostEntry,
    Route,
    RouteEdge,
    RouteNode,
    now,
)
from .storage import Repository


def _save_missing(repo: Repository, table: str, item: BaseModel, entity_id: str) -> None:
    """Add new seed records without overwriting a user's existing versions."""

    if repo.get(table, entity_id) is None:
        repo.save(table, item)


def seed(repo: Repository) -> None:
    corpus = Evidence(
        evidence_class="literature",
        source_title="BRIXTA reviewed public cement evidence corpus",
        note="Screening evidence only; independently verify before investment use",
    )
    assumed = Evidence(
        evidence_class="assumed",
        source_title="Starter reference profile",
        note="Replace with measured plant, laboratory or vendor data",
    )
    wah_pynkon = Evidence(
        evidence_class="official_project_document",
        source_title="Mining Plan with Progressive Mine Closure Plan — Wahpynkon Limestone Deposit",
        page="15",
        note="Composite borehole-core average reported in the captured evidence bundle",
    )
    lumshnong = Evidence(
        evidence_class="official_project_document",
        source_title="Pre-Feasibility Report — Lumshnong Limestone Mine production enhancement",
        page="15",
        note="Bench chemistry and reserve-weighted total captured from the project report",
    )
    cii_blends = Evidence(
        evidence_class="literature",
        source_title="CII — Blended Cement: Green, Durable & Sustainable (2022)",
        page="10",
        note="Captured reference compositions; product compliance still requires applicable testing",
    )
    cii_composite_trial = Evidence(
        evidence_class="plant_trial_report",
        source_title="CII composite cement plant trial case study",
        page="24",
        note="Captured plant trial recipe; transferability to another plant is unverified",
    )
    lc3_reference = Evidence(
        evidence_class="literature",
        source_title="Effects of Clay Type on the Properties of Limestone Calcined Clay Cement",
        page="abstract / mix design",
        note="Conventional LC3-50 composition captured from the research document",
    )

    materials = [
        Material(
            material_id="mat_wah_pynkon_limestone",
            created_at=now(),
            name="Wah–Pynkon Limestone Average",
            material_type="limestone",
            location="East Jaintia Hills, Meghalaya",
            processing_state="mine_average_as_reported",
            applicable_blend_classes=["raw_material_stockpile", "raw_meal", "premix"],
            chemistry=Chemistry(
                cao=52.28,
                sio2=2.47,
                al2o3=0.75,
                fe2o3=0.71,
                mgo=0.67,
                so3=None,
                na2o=None,
                k2o=None,
                loi=41.72,
            ),
            cost_inr_per_t=None,
            co2_kg_per_t=None,
            notes="Chemical average is evidenced; starter cost is not a delivered-cost validation.",
            data_gaps=["SO3", "Na2O", "K2O", "delivered cost", "processing CO2"],
            evidence=[wah_pynkon, assumed],
        ),
        Material(
            material_id="mat_lumshnong_limestone_weighted",
            created_at=now(),
            name="Lumshnong Limestone Mine — Reserve-Weighted Average",
            material_type="limestone",
            location="Lumshnong, East Jaintia Hills, Meghalaya",
            processing_state="mine_average_as_reported",
            applicable_blend_classes=["raw_material_stockpile", "raw_meal", "premix"],
            chemistry=Chemistry(
                cao=50.51,
                sio2=3.55,
                al2o3=1.22,
                fe2o3=1.27,
                mgo=1.41,
                so3=None,
                na2o=None,
                k2o=None,
                loi=40.88,
            ),
            chemistry_min=Chemistry(
                cao=46.45,
                sio2=2.05,
                al2o3=0.74,
                fe2o3=1.03,
                mgo=1.34,
                loi=37.65,
            ),
            chemistry_max=Chemistry(
                cao=51.75,
                sio2=8.82,
                al2o3=1.69,
                fe2o3=2.19,
                mgo=1.67,
                loi=41.77,
            ),
            cost_inr_per_t=None,
            co2_kg_per_t=None,
            notes="Reserve-weighted chemistry. Delivered cost and processing emissions are not reported.",
            data_gaps=["SO3", "Na2O", "K2O", "delivered cost", "processing CO2"],
            evidence=[lumshnong],
        ),
        Material(
            material_id="mat_lumshnong_high_grade_531_540",
            created_at=now(),
            name="Lumshnong Limestone Bench 531–540 mRL",
            material_type="limestone",
            location="Lumshnong, East Jaintia Hills, Meghalaya",
            processing_state="bench_sample_as_reported",
            applicable_blend_classes=["raw_material_stockpile", "raw_meal", "premix"],
            chemistry=Chemistry(
                cao=51.75,
                sio2=2.05,
                al2o3=0.74,
                fe2o3=1.03,
                mgo=1.34,
                so3=None,
                na2o=None,
                k2o=None,
                loi=41.77,
            ),
            cost_inr_per_t=None,
            co2_kg_per_t=None,
            notes="Higher-CaO bench scenario for quarry variability studies.",
            data_gaps=["SO3", "Na2O", "K2O", "delivered cost", "processing CO2"],
            evidence=[lumshnong],
        ),
        Material(
            material_id="mat_lumshnong_siliceous_585_594",
            created_at=now(),
            name="Lumshnong Limestone Bench 585–594 mRL",
            material_type="limestone",
            location="Lumshnong, East Jaintia Hills, Meghalaya",
            processing_state="bench_sample_as_reported",
            applicable_blend_classes=["raw_material_stockpile", "raw_meal", "premix"],
            chemistry=Chemistry(
                cao=46.45,
                sio2=8.82,
                al2o3=1.69,
                fe2o3=2.19,
                mgo=1.67,
                so3=None,
                na2o=None,
                k2o=None,
                loi=37.65,
            ),
            cost_inr_per_t=None,
            co2_kg_per_t=None,
            notes="Lower-CaO, higher-silica bench scenario for quarry variability studies.",
            data_gaps=["SO3", "Na2O", "K2O", "delivered cost", "processing CO2"],
            evidence=[lumshnong],
        ),
        Material(
            material_id="mat_reference_clinker",
            created_at=now(),
            name="Reference Portland Clinker",
            material_type="clinker",
            processing_state="ground_feed_ready",
            applicable_blend_classes=["clinker_blend", "finished_cement", "premix"],
            chemistry=Chemistry(
                cao=65.2,
                sio2=21.3,
                al2o3=5.1,
                fe2o3=3.3,
                mgo=1.5,
                so3=0.8,
                loi=0.5,
            ),
            cost_inr_per_t=4200,
            co2_kg_per_t=850,
            evidence=[assumed],
            data_gaps=["Na2O", "K2O"],
        ),
        Material(
            material_id="mat_reference_fly_ash",
            created_at=now(),
            name="Reference Fly Ash",
            material_type="fly_ash",
            processing_state="as_received",
            applicable_blend_classes=["finished_cement", "premix"],
            chemistry=Chemistry(
                cao=5,
                sio2=55,
                al2o3=26,
                fe2o3=7,
                mgo=1.5,
                so3=0.5,
                loi=3,
            ),
            cost_inr_per_t=1100,
            co2_kg_per_t=25,
            evidence=[assumed],
            data_gaps=["Na2O", "K2O"],
        ),
        Material(
            material_id="mat_reference_gypsum",
            created_at=now(),
            name="Reference Gypsum",
            material_type="gypsum",
            processing_state="ground_feed_ready",
            applicable_blend_classes=["finished_cement", "premix"],
            chemistry=Chemistry(
                cao=32.5,
                sio2=1.5,
                al2o3=0.4,
                fe2o3=0.3,
                mgo=0.4,
                so3=44,
                loi=20,
            ),
            cost_inr_per_t=1800,
            co2_kg_per_t=30,
            evidence=[assumed],
            data_gaps=["Na2O", "K2O"],
        ),
        Material(
            material_id="mat_reference_calcined_clay",
            created_at=now(),
            name="Reference Calcined Clay",
            material_type="calcined_clay",
            processing_state="calcined_and_ground",
            applicable_blend_classes=["finished_cement", "premix"],
            chemistry=Chemistry(
                cao=1,
                sio2=52,
                al2o3=39,
                fe2o3=3,
                mgo=0.5,
                so3=0.2,
                loi=2.5,
            ),
            cost_inr_per_t=2300,
            co2_kg_per_t=180,
            evidence=[assumed],
            data_gaps=["Na2O", "K2O"],
        ),
        Material(
            material_id="mat_reference_ggbs",
            created_at=now(),
            name="Reference GGBFS",
            material_type="ggbs",
            processing_state="ground_feed_ready",
            applicable_blend_classes=["finished_cement", "premix"],
            chemistry=Chemistry(
                cao=40,
                sio2=35,
                al2o3=13,
                fe2o3=0.7,
                mgo=8,
                so3=1,
                loi=1,
            ),
            cost_inr_per_t=1700,
            co2_kg_per_t=65,
            notes="Generic screening profile; replace with a supplier certificate and delivered quotation.",
            data_gaps=["Na2O", "K2O", "source-specific glass content", "activity index"],
            evidence=[assumed],
        ),
        Material(
            material_id="mat_ground_wah_pynkon_proxy",
            created_at=now(),
            name="Ground Wah–Pynkon Limestone — Research Proxy",
            material_type="limestone",
            location="East Jaintia Hills, Meghalaya",
            processing_state="ground_research_proxy",
            applicable_blend_classes=["finished_cement", "premix"],
            chemistry=Chemistry(cao=52.28, sio2=2.47, al2o3=0.75, fe2o3=0.71, mgo=0.67, so3=None, na2o=None, k2o=None, loi=41.72),
            cost_inr_per_t=None,
            co2_kg_per_t=None,
            notes="Oxides copied from evidenced quarry chemistry; fineness, grindability, cost and finished-cement performance are not validated.",
            data_gaps=["SO3", "Na2O", "K2O", "fineness", "grindability", "delivered cost", "processing CO2"],
            evidence=[wah_pynkon, assumed],
        ),
        Material(
            material_id="mat_ground_lumshnong_proxy",
            created_at=now(),
            name="Ground Lumshnong Limestone — Research Proxy",
            material_type="limestone",
            location="Lumshnong, East Jaintia Hills, Meghalaya",
            processing_state="ground_research_proxy",
            applicable_blend_classes=["finished_cement", "premix"],
            chemistry=Chemistry(cao=50.51, sio2=3.55, al2o3=1.22, fe2o3=1.27, mgo=1.41, so3=None, na2o=None, k2o=None, loi=40.88),
            cost_inr_per_t=None,
            co2_kg_per_t=None,
            notes="Oxides copied from reserve-weighted quarry chemistry; fineness, grindability, cost and finished-cement performance are not validated.",
            data_gaps=["SO3", "Na2O", "K2O", "fineness", "grindability", "delivered cost", "processing CO2"],
            evidence=[lumshnong, assumed],
        ),
    ]
    for item in materials:
        _save_missing(repo, "materials", item, item.material_id)

    starter_cost_book = CostBook(
        cost_book_id="cost_book_starter_v1",
        created_at=now(),
        name="Starter Screening Cost Book — Replace Inputs",
        effective_date=None,
        electricity_inr_kwh=8.5,
        thermal_fuel_inr_mkcal=900,
        packing_inr_t=None,
        labour_inr_t=None,
        maintenance_inr_t=None,
        other_variable_inr_t=None,
        factory_overhead_inr_t=None,
        outbound_logistics_inr_t=None,
        material_costs=[
            MaterialCostEntry(
                material_id=item.material_id,
                purchased_delivered_cost_inr_t=item.cost_inr_per_t,
                internal_feed_cost_inr_t=None,
                evidence_class="assumed",
                note="Purchased starter price copied from the material record. Internal feed cost intentionally left blank to prevent clinker-cost double counting.",
            )
            for item in materials
        ],
        evidence=[assumed],
        notes="Screening template only. Create a new version with quotations, invoices and plant operating data.",
    )
    _save_missing(repo, "cost_books", starter_cost_book, starter_cost_book.cost_book_id)

    blends = [
        Blend(
            blend_id="blend_reference_opc_95_5",
            created_at=now(),
            status="reference",
            name="Reference OPC 95/5",
            blend_class="finished_cement",
            family="OPC",
            objective="reproduce_captured_reference",
            applicable_standard="Reference composition; compliance review required",
            components=[
                BlendComponent(material_id="mat_reference_clinker", percentage=95),
                BlendComponent(material_id="mat_reference_gypsum", percentage=5),
            ],
            evidence=[cii_blends],
        ),
        Blend(
            blend_id="blend_reference_ppc",
            created_at=now(),
            status="reference",
            name="Reference PPC 64/31/5",
            blend_class="finished_cement",
            family="PPC",
            applicable_standard="IS 1489 Part 1 — review required",
            components=[
                BlendComponent(material_id="mat_reference_clinker", percentage=64),
                BlendComponent(material_id="mat_reference_fly_ash", percentage=31),
                BlendComponent(material_id="mat_reference_gypsum", percentage=5),
            ],
            evidence=[cii_blends],
        ),
        Blend(
            blend_id="blend_reference_psc_38_57_5",
            created_at=now(),
            status="reference",
            name="Reference PSC 38/57/5",
            blend_class="finished_cement",
            family="PSC",
            objective="reproduce_captured_reference",
            applicable_standard="Reference composition; compliance review required",
            components=[
                BlendComponent(material_id="mat_reference_clinker", percentage=38),
                BlendComponent(material_id="mat_reference_ggbs", percentage=57),
                BlendComponent(material_id="mat_reference_gypsum", percentage=5),
            ],
            evidence=[cii_blends],
        ),
        Blend(
            blend_id="blend_reference_composite_45_25_25_5",
            created_at=now(),
            status="reference",
            name="Reference Composite 45/25/25/5",
            blend_class="finished_cement",
            family="Composite cement",
            objective="reproduce_captured_reference",
            applicable_standard="Reference composition; compliance review required",
            components=[
                BlendComponent(material_id="mat_reference_clinker", percentage=45),
                BlendComponent(material_id="mat_reference_fly_ash", percentage=25),
                BlendComponent(material_id="mat_reference_ggbs", percentage=25),
                BlendComponent(material_id="mat_reference_gypsum", percentage=5),
            ],
            evidence=[cii_blends],
        ),
        Blend(
            blend_id="blend_plant_trial_composite_30_5_47_18_4_5",
            created_at=now(),
            status="reference",
            name="Plant-Trial Composite 30.5/47/18/4.5",
            blend_class="finished_cement",
            family="Composite cement",
            objective="reproduce_captured_plant_trial",
            applicable_standard="Plant-trial evidence; independent compliance review required",
            components=[
                BlendComponent(material_id="mat_reference_clinker", percentage=30.5),
                BlendComponent(material_id="mat_reference_ggbs", percentage=47),
                BlendComponent(material_id="mat_reference_fly_ash", percentage=18),
                BlendComponent(material_id="mat_reference_gypsum", percentage=4.5),
            ],
            evidence=[cii_composite_trial],
        ),
        Blend(
            blend_id="blend_reference_lc3_50",
            created_at=now(),
            status="reference",
            name="Reference LC3-50 50/30/15/5",
            blend_class="finished_cement",
            family="LC3",
            objective="reproduce_captured_reference",
            applicable_standard="Research reference; physical and compliance validation required",
            components=[
                BlendComponent(material_id="mat_reference_clinker", percentage=50),
                BlendComponent(material_id="mat_reference_calcined_clay", percentage=30),
                BlendComponent(material_id="mat_ground_wah_pynkon_proxy", percentage=15),
                BlendComponent(material_id="mat_reference_gypsum", percentage=5),
            ],
            evidence=[lc3_reference, wah_pynkon],
        ),
        Blend(
            blend_id="blend_lc3_mineral_premix",
            created_at=now(),
            name="LC3 Mineral Premix 2:1",
            blend_class="premix",
            family="LC3 intermediate",
            objective="reusable_calcined_clay_limestone_premix",
            applicable_standard="Research only",
            components=[
                BlendComponent(
                    material_id="mat_reference_calcined_clay", percentage=66.666667
                ),
                BlendComponent(
                    material_id="mat_ground_wah_pynkon_proxy", percentage=33.333333
                ),
            ],
            evidence=[corpus],
        ),
        Blend(
            blend_id="blend_lc3_nested_candidate",
            created_at=now(),
            name="LC3 Nested Research Candidate",
            blend_class="finished_cement",
            family="LC3",
            objective="reduce_clinker_and_co2",
            applicable_standard="Research only",
            components=[
                BlendComponent(material_id="mat_reference_clinker", percentage=50),
                BlendComponent(
                    component_type="blend",
                    blend_id="blend_lc3_mineral_premix",
                    percentage=45,
                ),
                BlendComponent(material_id="mat_reference_gypsum", percentage=5),
            ],
            evidence=[corpus],
        ),
        Blend(
            blend_id="blend_lumshnong_quarry_variability",
            created_at=now(),
            name="Lumshnong Quarry Variability Demonstrator",
            blend_class="raw_material_stockpile",
            family="Limestone preblend",
            objective="compare_reported_bench_variability",
            applicable_standard="Research screening only",
            components=[
                BlendComponent(
                    material_id="mat_lumshnong_high_grade_531_540", percentage=50
                ),
                BlendComponent(
                    material_id="mat_lumshnong_siliceous_585_594", percentage=50
                ),
            ],
            evidence=[lumshnong],
        ),
    ]
    for item in blends:
        _save_missing(repo, "blends", item, item.blend_id)

    def machine(
        machine_id: str,
        name: str,
        stage: str,
        capacity: float,
        electricity: float,
        heat: float = 0,
    ) -> Machine:
        return Machine(
            machine_id=machine_id,
            machine_kind="thermal" if heat else "standard",
            created_at=now(),
            name=name,
            process_stage=stage,
            rated_capacity_tph=capacity,
            minimum_stable_tph=capacity * 0.35,
            availability=0.9 if heat else 0.93,
            specific_electricity_kwh_t=electricity,
            specific_heat_kcal_kg=heat,
            capex_inr_crore=0,
            technology_readiness_level=9,
            maximum_stable_tph=capacity * (0.9 if heat else 0.93),
            design_blaine_m2_kg=320 if stage == "cement_grinding" else None,
            maximum_feed_moisture_percent=1.5 if stage == "thermal_transformation" else None,
            minimum_temperature_c=1350 if stage == "thermal_transformation" else None,
            minimum_oxygen_percent=1.0 if stage == "thermal_transformation" else None,
            maximum_oxygen_percent=4.0 if stage == "thermal_transformation" else None,
            maximum_free_lime_percent=2.0 if stage == "thermal_transformation" else None,
            maximum_temperature_c=1450 if heat else None,
            residence_time_minutes=35 if heat else None,
            conversion_fraction=0.98 if heat else None,
            product_state="clinker" if heat else None,
            input_material=None if heat else "solid",
            output_material=None if heat else "solid",
            evidence=[assumed],
        )

    machines = [
        machine("machine_crusher", "Crusher 01", "crushing", 180, 2.5),
        machine("machine_raw_mill", "Raw Mill 01", "raw_grinding", 140, 17),
        machine(
            "machine_rotary_kiln",
            "Rotary Kiln Baseline",
            "thermal_transformation",
            82,
            24,
            670,
        ),
        machine("machine_cement_mill", "Cement Mill 01", "cement_grinding", 130, 29),
        machine("machine_packer", "Packer 01", "packing_dispatch", 120, 3),
        Machine(
            machine_id="machine_clay_calciner",
            machine_kind="thermal",
            created_at=now(),
            name="Clay Calciner Research Baseline",
            process_stage="clay_calcination",
            rated_capacity_tph=50,
            minimum_stable_tph=17.5,
            availability=0.9,
            specific_electricity_kwh_t=20,
            specific_heat_kcal_kg=650,
            capex_inr_crore=0,
            technology_readiness_level=7,
            maximum_temperature_c=850,
            residence_time_minutes=40,
            conversion_fraction=0.95,
            product_state="calcined_clay",
            evidence=[assumed],
        ),
    ]
    for item in machines:
        _save_missing(repo, "machines", item, item.machine_id)

    integrated_route = Route(
        route_id="route_integrated_baseline_v03",
        created_at=now(),
        name="Integrated Plant Baseline v0.3",
        route_kind="integrated",
        nodes=[
            RouteNode(
                node_id="crusher",
                machine_id="machine_crusher",
                label="Crusher",
                position_x=0,
                position_y=80,
            ),
            RouteNode(
                node_id="raw_mill",
                machine_id="machine_raw_mill",
                label="Raw mill",
                position_x=240,
                position_y=80,
            ),
            RouteNode(
                node_id="kiln",
                machine_id="machine_rotary_kiln",
                label="Kiln",
                position_x=480,
                position_y=80,
            ),
            RouteNode(
                node_id="cement_mill",
                machine_id="machine_cement_mill",
                label="Cement mill",
                position_x=720,
                position_y=80,
            ),
            RouteNode(
                node_id="packer",
                machine_id="machine_packer",
                label="Packer",
                position_x=960,
                position_y=80,
            ),
        ],
        edges=[
            RouteEdge(edge_id=f"edge_{index}", source=source, target=target)
            for index, (source, target) in enumerate(
                [
                    ("crusher", "raw_mill"),
                    ("raw_mill", "kiln"),
                    ("kiln", "cement_mill"),
                    ("cement_mill", "packer"),
                ],
                1,
            )
        ],
    )
    grinding_route = Route(
        route_id="route_grinding_unit_v03",
        created_at=now(),
        name="Grinding Unit — Purchased Clinker",
        route_kind="grinding_only",
        nodes=[
            RouteNode(node_id="cement_mill", machine_id="machine_cement_mill", label="Cement mill", position_x=180, position_y=80),
            RouteNode(node_id="packer", machine_id="machine_packer", label="Packer", position_x=500, position_y=80),
        ],
        edges=[RouteEdge(edge_id="edge_grinding_1", source="cement_mill", target="packer")],
    )
    lc3_route = Route(
        route_id="route_integrated_lc3_v03",
        created_at=now(),
        name="Integrated Plant + Clay Calciner — R&D",
        route_kind="integrated_lc3",
        nodes=[
            RouteNode(node_id="crusher", machine_id="machine_crusher", label="Crusher", position_x=0, position_y=40),
            RouteNode(node_id="raw_mill", machine_id="machine_raw_mill", label="Raw mill", position_x=220, position_y=40),
            RouteNode(node_id="kiln", machine_id="machine_rotary_kiln", label="Kiln", position_x=440, position_y=40),
            RouteNode(node_id="clay_calciner", machine_id="machine_clay_calciner", label="Clay calciner", position_x=440, position_y=210),
            RouteNode(node_id="cement_mill", machine_id="machine_cement_mill", label="Cement mill", position_x=700, position_y=120),
            RouteNode(node_id="packer", machine_id="machine_packer", label="Packer", position_x=960, position_y=120),
        ],
        edges=[
            RouteEdge(edge_id="edge_lc3_1", source="crusher", target="raw_mill"),
            RouteEdge(edge_id="edge_lc3_2", source="raw_mill", target="kiln"),
            RouteEdge(edge_id="edge_lc3_3", source="kiln", target="cement_mill"),
            RouteEdge(edge_id="edge_lc3_4", source="clay_calciner", target="cement_mill"),
            RouteEdge(edge_id="edge_lc3_5", source="cement_mill", target="packer"),
        ],
    )
    for route in [integrated_route, grinding_route, lc3_route]:
        _save_missing(repo, "routes", route, route.route_id)

    # V0.5 corrects legacy seed semantics without touching user-created IDs.
    # Historical runs remain immutable because they already contain snapshots.
    seed_materials = {item.material_id: item for item in materials}
    for material_id in seed_materials:
        existing = repo.get("materials", material_id)
        reference = seed_materials[material_id]
        if isinstance(existing, Material):
            repo.save(
                "materials",
                existing.model_copy(
                    update={
                        "functional_role": reference.functional_role,
                        "chemistry": reference.chemistry,
                        "chemistry_min": reference.chemistry_min,
                        "chemistry_max": reference.chemistry_max,
                        "moisture_percent": reference.moisture_percent,
                        "grindability_factor": reference.grindability_factor,
                        "fuel_ash_percent": reference.fuel_ash_percent,
                        "fuel_calorific_value_kcal_kg": reference.fuel_calorific_value_kcal_kg,
                        "fuel_ash_chemistry": reference.fuel_ash_chemistry,
                        "data_gaps": reference.data_gaps,
                    }
                ),
            )

    seed_machines = {item.machine_id: item for item in machines}
    for machine_id in {
        "machine_crusher",
        "machine_raw_mill",
        "machine_rotary_kiln",
        "machine_cement_mill",
        "machine_packer",
    }:
        existing = repo.get("machines", machine_id)
        reference = seed_machines[machine_id]
        if isinstance(existing, Machine):
            repo.save(
                "machines",
                existing.model_copy(
                    update={
                        "maximum_stable_tph": reference.maximum_stable_tph,
                        "design_blaine_m2_kg": reference.design_blaine_m2_kg,
                        "maximum_feed_moisture_percent": reference.maximum_feed_moisture_percent,
                        "minimum_temperature_c": reference.minimum_temperature_c,
                        "minimum_oxygen_percent": reference.minimum_oxygen_percent,
                        "maximum_oxygen_percent": reference.maximum_oxygen_percent,
                        "maximum_free_lime_percent": reference.maximum_free_lime_percent,
                    }
                ),
            )
