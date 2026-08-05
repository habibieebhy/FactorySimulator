from __future__ import annotations

from io import BytesIO

import xlsxwriter
from xlsxwriter.format import Format
from xlsxwriter.worksheet import Worksheet

from .engineering_decision import EngineeringCase, EngineeringValidationRecord
from .models import CostBook, Machine, Material, RetrofitCandidate, RetrofitStudyResult, Route
from .retrofit import REFERENCE_CO2_KG_T, REFERENCE_COST_INR_T
from .storage import Repository


FormatMap = dict[str, Format]


def compile_engineering_workbook(
    repository: Repository,
    case: EngineeringCase,
    study: RetrofitStudyResult,
    candidate: RetrofitCandidate,
    validations: list[EngineeringValidationRecord] | None = None,
) -> bytes:
    """Compile an auditable engineering decision workbook.

    Blue cells are plant inputs, yellow cells are BRIXTA assumptions, grey cells
    are formulas, and green cells contain recorded plant/laboratory actuals.
    """

    if case.trust_assessment is None or case.decision_gate is None:
        raise ValueError("Engineering workbook requires a version 1.0.0 trust assessment and decision gate")
    validations = validations or []
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    workbook.set_calc_mode("auto")
    workbook.set_properties(
        {
            "title": f"BRIXTA Engineering Decision — {case.project.project_name}",
            "subject": "Traceable cement engineering recommendation and pilot workbook",
            "author": case.project.engineer,
            "company": "BRIXTA",
            "comments": (
                "Reference engineering model. Replace blue cells with verified plant, vendor, "
                "laboratory and commercial data before production changes."
            ),
        }
    )
    formats = _formats(workbook)

    sheets = {
        name: workbook.add_worksheet(name)
        for name in [
            "00_COVER",
            "01_PROJECT_SUMMARY",
            "02_ASSUMPTIONS",
            "03_MISSING_DATA",
            "04_EXECUTIVE_SUMMARY",
            "05_TRUST_SUMMARY",
            "06_EVIDENCE_REGISTER",
            "07_CONFIDENCE_REGISTER",
            "08_RISK_REGISTER",
            "09_REVIEW_COMMITTEE",
            "10_RAW_MATERIALS",
            "11_XRF",
            "12_XRD",
            "13_MACHINE_DATA",
            "14_FUEL",
            "15_POWER",
            "16_COSTS",
            "17_PRODUCTION",
            "18_ROUTE",
            "19_EQUIPMENT",
            "20_TARIFFS",
            "21_QUALITY_TARGETS",
            "30_MASS_BALANCE",
            "31_HEAT_BALANCE",
            "32_RAW_MIX",
            "33_KILN",
            "34_GRINDING",
            "35_ENERGY",
            "36_EQUIPMENT_UTIL",
            "37_PRODUCTION_CALC",
            "38_COST_CALC",
            "39_CARBON",
            "40_SENSITIVITY",
            "41_SCENARIO_COMPARE",
            "42_SCENARIO_RATIONALE",
            "50_PLANT_ACTUALS",
            "51_LAB_RESULTS",
            "52_XRF_COMPARISON",
            "53_XRD_COMPARISON",
            "54_FREE_LIME",
            "55_STRENGTH",
            "56_POWER",
            "57_COAL",
            "58_THERMAL",
            "59_COMMENTS",
            "60_DEVIATION",
            "61_ROOT_CAUSE",
            "62_ENGINEER_SIGNOFF",
            "63_QUALITY_SIGNOFF",
            "64_PLANT_SIGNOFF",
            "65_VALIDATION_MATRIX",
            "66_OPERATOR_CHECKLIST",
            "67_ROLLBACK",
            "70_DECISION",
            "71_PILOT_BATCH",
            "72_LEARNING",
            "73_LESSONS_LEARNED",
            "74_VERSION_HISTORY",
        ]
    }

    route = repository.get("routes", case.route_id)
    cost_book = (
        repository.get("cost_books", case.cost_book_id)
        if case.cost_book_id
        else None
    )
    if not isinstance(route, Route):
        raise ValueError("Engineering case route is unavailable")
    if cost_book is not None and not isinstance(cost_book, CostBook):
        cost_book = None

    _write_cover(sheets["00_COVER"], case, formats)
    _write_project_summary(sheets["01_PROJECT_SUMMARY"], case, study, candidate, formats)
    _write_assumptions(sheets["02_ASSUMPTIONS"], case, formats)
    _write_missing_data(sheets["03_MISSING_DATA"], case, formats)
    _write_executive(sheets["04_EXECUTIVE_SUMMARY"], case, formats)
    _write_trust_summary(sheets["05_TRUST_SUMMARY"], case, formats)
    _write_evidence_register(sheets["06_EVIDENCE_REGISTER"], case, formats)
    _write_confidence_register(sheets["07_CONFIDENCE_REGISTER"], case, formats)
    _write_risk_register(sheets["08_RISK_REGISTER"], case, formats)
    _write_review_committee(sheets["09_REVIEW_COMMITTEE"], case, formats)
    material_rows = _write_raw_materials(
        sheets["10_RAW_MATERIALS"], repository, candidate, cost_book, formats
    )
    _write_xrf(sheets["11_XRF"], repository, candidate, formats)
    _write_xrd(sheets["12_XRD"], repository, candidate, formats)
    machine_rows = _write_machine_data(
        sheets["13_MACHINE_DATA"], repository, route, formats
    )
    _write_fuel(sheets["14_FUEL"], formats)
    _write_power(sheets["15_POWER"], candidate, formats)
    _write_costs(sheets["16_COSTS"], candidate, cost_book, formats)
    _write_production_input(sheets["17_PRODUCTION"], case, study, candidate, formats)
    _write_route(sheets["18_ROUTE"], route, repository, formats)
    _write_equipment(sheets["19_EQUIPMENT"], repository, route, formats)
    _write_tariffs(sheets["20_TARIFFS"], study, cost_book, formats)
    _write_quality_targets(sheets["21_QUALITY_TARGETS"], case, formats)
    _write_mass_balance(sheets["30_MASS_BALANCE"], candidate, material_rows, formats)
    _write_heat_balance(sheets["31_HEAT_BALANCE"], candidate, formats)
    _write_raw_mix(sheets["32_RAW_MIX"], formats)
    _write_kiln(sheets["33_KILN"], study, candidate, formats)
    _write_grinding(sheets["34_GRINDING"], candidate, formats)
    _write_energy(sheets["35_ENERGY"], candidate, formats)
    _write_equipment_util(
        sheets["36_EQUIPMENT_UTIL"], repository, route, machine_rows, formats
    )
    _write_production_calc(sheets["37_PRODUCTION_CALC"], case, formats)
    _write_cost_calc(sheets["38_COST_CALC"], candidate, material_rows, formats)
    _write_carbon(sheets["39_CARBON"], candidate, material_rows, formats)
    _write_sensitivity(sheets["40_SENSITIVITY"], candidate, formats)
    _write_scenarios(sheets["41_SCENARIO_COMPARE"], study, formats)
    _write_scenario_rationale(sheets["42_SCENARIO_RATIONALE"], case, formats)
    _write_plant_actuals(sheets["50_PLANT_ACTUALS"], validations, formats)
    _write_lab_results(sheets["51_LAB_RESULTS"], validations, formats)
    _write_xrf_comparison(sheets["52_XRF_COMPARISON"], formats)
    _write_xrd_comparison(sheets["53_XRD_COMPARISON"], formats)
    _write_free_lime(sheets["54_FREE_LIME"], validations, formats)
    _write_strength(sheets["55_STRENGTH"], validations, formats)
    _write_validation_metric(sheets["56_POWER"], "Power validation", "kWh/t", formats)
    _write_validation_metric(sheets["57_COAL"], "Coal / fuel validation", "kg/t or kcal/kg", formats)
    _write_validation_metric(sheets["58_THERMAL"], "Thermal validation", "kcal/kg", formats)
    _write_comments(sheets["59_COMMENTS"], validations, formats)
    _write_deviation(sheets["60_DEVIATION"], validations, formats)
    _write_root_cause(sheets["61_ROOT_CAUSE"], validations, formats)
    _write_signoff(sheets["62_ENGINEER_SIGNOFF"], "Engineer", validations, formats)
    _write_signoff(sheets["63_QUALITY_SIGNOFF"], "Quality Head", validations, formats)
    _write_signoff(sheets["64_PLANT_SIGNOFF"], "Plant Head", validations, formats)
    _write_validation_matrix(sheets["65_VALIDATION_MATRIX"], case, formats)
    _write_operator_checklist(sheets["66_OPERATOR_CHECKLIST"], case, formats)
    _write_rollback(sheets["67_ROLLBACK"], case, formats)
    _write_decision(sheets["70_DECISION"], case, formats)
    _write_pilot(sheets["71_PILOT_BATCH"], case, formats)
    _write_learning(sheets["72_LEARNING"], case, validations, formats)
    _write_lessons_learned(sheets["73_LESSONS_LEARNED"], case, validations, formats)
    _write_version_history(sheets["74_VERSION_HISTORY"], case, formats)

    workbook.close()
    return output.getvalue()


def _formats(workbook: xlsxwriter.Workbook) -> FormatMap:
    border = 1
    return {
        "title": workbook.add_format(
            {
                "bold": True,
                "font_size": 18,
                "font_color": "#FFFFFF",
                "bg_color": "#102A43",
                "align": "left",
                "valign": "vcenter",
            }
        ),
        "section": workbook.add_format(
            {
                "bold": True,
                "font_size": 12,
                "font_color": "#FFFFFF",
                "bg_color": "#245B78",
                "border": border,
            }
        ),
        "header": workbook.add_format(
            {
                "bold": True,
                "font_color": "#FFFFFF",
                "bg_color": "#397A8A",
                "border": border,
                "text_wrap": True,
                "align": "center",
                "valign": "vcenter",
            }
        ),
        "label": workbook.add_format(
            {"bold": True, "bg_color": "#E8EEF2", "border": border}
        ),
        "input": workbook.add_format(
            {"bg_color": "#D9EAF7", "border": border, "num_format": "0.00"}
        ),
        "reference": workbook.add_format(
            {"bg_color": "#FFF2CC", "border": border, "num_format": "0.00"}
        ),
        "formula": workbook.add_format(
            {"bg_color": "#E7E6E6", "border": border, "num_format": "0.00"}
        ),
        "actual": workbook.add_format(
            {"bg_color": "#E2F0D9", "border": border, "num_format": "0.00"}
        ),
        "warning": workbook.add_format(
            {
                "bg_color": "#FCE4D6",
                "font_color": "#9C0006",
                "border": border,
                "text_wrap": True,
            }
        ),
        "good": workbook.add_format(
            {"bg_color": "#E2F0D9", "font_color": "#006100", "border": border}
        ),
        "text": workbook.add_format(
            {"border": border, "text_wrap": True, "valign": "top"}
        ),
        "small": workbook.add_format(
            {"font_size": 9, "font_color": "#666666", "text_wrap": True}
        ),
        "number": workbook.add_format({"border": border, "num_format": "0.00"}),
        "integer": workbook.add_format({"border": border, "num_format": "0"}),
        "money": workbook.add_format(
            {"border": border, "num_format": "₹#,##0.00"}
        ),
        "percent": workbook.add_format(
            {"border": border, "num_format": "0.00%"}
        ),
        "kpi": workbook.add_format(
            {
                "bold": True,
                "font_size": 15,
                "font_color": "#102A43",
                "bg_color": "#EAF3F7",
                "border": border,
                "align": "center",
                "valign": "vcenter",
                "num_format": "0.00",
            }
        ),
        "date": workbook.add_format(
            {"border": border, "num_format": "yyyy-mm-dd hh:mm"}
        ),
    }


def _setup(sheet: Worksheet, widths: list[tuple[int, int, float]]) -> None:
    sheet.hide_gridlines(2)
    sheet.freeze_panes(4, 0)
    for first, last, width in widths:
        sheet.set_column(first, last, width)


def _title(sheet: Worksheet, text: str, formats: FormatMap, last_col: int = 7) -> None:
    sheet.merge_range(0, 0, 1, last_col, text, formats["title"])
    sheet.set_row(0, 25)
    sheet.set_row(1, 10)


def _write_cover(sheet: Worksheet, case: EngineeringCase, formats: FormatMap) -> None:
    _setup(sheet, [(0, 0, 28), (1, 1, 70)])
    _title(sheet, "BRIXTA ENGINEERING DECISION WORKBOOK", formats, 1)
    rows = [
        ("Project", case.project.project_name),
        ("Revision", case.project.revision),
        ("Simulation ID", case.case_id),
        ("Engineer", case.project.engineer),
        ("Plant", case.project.plant_name),
        ("Product", case.project.product_target),
        ("Date", case.created_at.isoformat()),
        ("Risk rating", case.risk_rating.upper()),
        ("Confidence", case.confidence_percent),
        ("Status", case.status.upper()),
    ]
    for row, (label, value) in enumerate(rows, 3):
        sheet.write(row, 0, label, formats["label"])
        sheet.write(row, 1, value, formats["warning"] if label == "Risk rating" else formats["text"])
    sheet.merge_range(15, 0, 18, 1, case.executive_summary, formats["warning"])


def _write_project_summary(
    sheet: Worksheet,
    case: EngineeringCase,
    study: RetrofitStudyResult,
    candidate: RetrofitCandidate,
    formats: FormatMap,
) -> None:
    _setup(sheet, [(0, 0, 32), (1, 1, 70)])
    _title(sheet, "PROJECT SUMMARY", formats, 1)
    rows = [
        ("Engineering case", case.case_id),
        ("Retrofit study", study.study_id),
        ("Selected candidate", candidate.name),
        ("Baseline blend", study.baseline.blend_name),
        ("Route", study.baseline.route_name),
        ("Requested output", study.request.target_output_tph),
        ("Supply pathway", study.request.clay_supply_mode),
        ("Calculation version", case.calculation_version),
        ("Calibration sample count", case.calibration_sample_count),
        ("Customer constraints", "\n".join(case.project.customer_constraints) or "None supplied"),
        ("BIS constraints", "\n".join(case.project.bis_constraints) or "Applicable standard not supplied"),
        ("Notes", case.project.notes or ""),
    ]
    for row, (label, value) in enumerate(rows, 3):
        sheet.write(row, 0, label, formats["label"])
        sheet.write(row, 1, value, formats["text"])


def _write_assumptions(sheet: Worksheet, case: EngineeringCase, formats: FormatMap) -> None:
    _setup(sheet, [(0, 0, 30), (1, 1, 25), (2, 2, 80)])
    _title(sheet, "ASSUMPTIONS REGISTER", formats, 2)
    sheet.write_row(3, 0, ["Key", "Value", "Basis"], formats["header"])
    for row, item in enumerate(case.assumptions, 4):
        sheet.write(row, 0, item.get("key"), formats["text"])
        sheet.write(row, 1, item.get("value"), formats["reference"])
        sheet.write(row, 2, item.get("basis"), formats["text"])
    start = 4 + len(case.assumptions) + 2
    sheet.write(start, 0, "Calibration profile", formats["section"])
    sheet.write_row(start + 1, 0, ["Metric", "Correction factor", "Samples"], formats["header"])
    for row, (metric, factor) in enumerate(case.calibration_profile.items(), start + 2):
        sheet.write(row, 0, metric, formats["text"])
        sheet.write(row, 1, factor, formats["reference"])
        sheet.write(row, 2, case.calibration_sample_count, formats["integer"])


def _write_missing_data(sheet: Worksheet, case: EngineeringCase, formats: FormatMap) -> None:
    _setup(sheet, [(0, 0, 18), (1, 1, 62), (2, 2, 70), (3, 3, 18)])
    _title(sheet, "MISSING DATA REGISTER", formats, 3)
    sheet.write_row(3, 0, ["Category", "Data item", "Why required", "Status"], formats["header"])
    for row, item in enumerate(case.missing_data, 4):
        sheet.write(row, 0, item["category"], formats["text"])
        sheet.write(row, 1, item["item"], formats["text"])
        sheet.write(row, 2, item["reason"], formats["text"])
        sheet.write(row, 3, "REPLACE / VERIFY", formats["warning"])


def _write_executive(sheet: Worksheet, case: EngineeringCase, formats: FormatMap) -> None:
    _setup(sheet, [(0, 0, 28), (1, 1, 20), (2, 2, 18), (3, 3, 68)])
    _title(sheet, "EXECUTIVE SUMMARY", formats, 3)
    sheet.merge_range(3, 0, 5, 3, case.executive_summary, formats["warning"])
    sheet.write_row(7, 0, ["Prediction", "Value", "Confidence", "Reason / required validation"], formats["header"])
    for row, item in enumerate(case.predictions, 8):
        sheet.write(row, 0, item.label, formats["label"])
        sheet.write(row, 1, item.prediction, formats["reference"])
        sheet.write(row, 2, item.confidence_percent, formats["number"])
        sheet.write(
            row,
            3,
            f"{item.reason}\nValidation: {', '.join(item.required_validation)}",
            formats["text"],
        )


def _material_defaults(
    repository: Repository,
    component,
    cost_book: CostBook | None,
) -> tuple[float, float, Material | None]:
    material = repository.get("materials", component.reference_id)
    if not isinstance(material, Material):
        return (
            REFERENCE_COST_INR_T[component.role],
            REFERENCE_CO2_KG_T[component.role],
            None,
        )
    cost = material.cost_inr_per_t
    if cost_book is not None:
        entry = next(
            (item for item in cost_book.material_costs if item.material_id == material.material_id),
            None,
        )
        if entry and entry.purchased_delivered_cost_inr_t is not None:
            cost = entry.purchased_delivered_cost_inr_t
    return (
        float(cost if cost is not None else REFERENCE_COST_INR_T[component.role]),
        float(
            material.co2_kg_per_t
            if material.co2_kg_per_t is not None
            else REFERENCE_CO2_KG_T[component.role]
        ),
        material,
    )


def _write_raw_materials(
    sheet: Worksheet,
    repository: Repository,
    candidate: RetrofitCandidate,
    cost_book: CostBook | None,
    formats: FormatMap,
) -> dict[str, int]:
    _setup(sheet, [(0, 0, 18), (1, 1, 34), (2, 10, 16)])
    _title(sheet, "RAW MATERIALS / FORMULATION INPUTS", formats, 10)
    headers = [
        "Role",
        "Material",
        "BRIXTA %",
        "Plant %",
        "Minimum %",
        "Maximum %",
        "Cost INR/t",
        "CO2 kg/t",
        "Moisture %",
        "LOI %",
        "Data status",
    ]
    sheet.write_row(3, 0, headers, formats["header"])
    rows: dict[str, int] = {}
    for row, component in enumerate(candidate.components, 4):
        rows[component.role] = row + 1
        cost, co2, material = _material_defaults(repository, component, cost_book)
        values = [
            component.role,
            component.name,
            component.percentage,
            component.percentage,
            component.minimum_percent,
            component.maximum_percent,
            cost,
            co2,
            material.moisture_percent if material else None,
            material.chemistry.loi if material else None,
            component.source_status,
        ]
        for column, value in enumerate(values):
            fmt = formats["text"]
            if column == 2:
                fmt = formats["reference"]
            elif column in {3, 6, 7, 8, 9}:
                fmt = formats["input"]
            elif column in {4, 5}:
                fmt = formats["reference"]
            sheet.write(row, column, value, fmt)
        sheet.data_validation(
            row,
            3,
            row,
            3,
            {
                "validate": "decimal",
                "criteria": "between",
                "minimum": f"=E{row + 1}",
                "maximum": f"=F{row + 1}",
            },
        )
    total_row = 4 + len(candidate.components)
    sheet.write(total_row, 1, "TOTAL", formats["label"])
    sheet.write_formula(total_row, 2, f"=SUM(C5:C{total_row})", formats["formula"])
    sheet.write_formula(total_row, 3, f"=SUM(D5:D{total_row})", formats["formula"])
    sheet.conditional_format(
        total_row,
        3,
        total_row,
        3,
        {
            "type": "cell",
            "criteria": "not between",
            "minimum": 99.999,
            "maximum": 100.001,
            "format": formats["warning"],
        },
    )
    return rows


def _write_xrf(
    sheet: Worksheet,
    repository: Repository,
    candidate: RetrofitCandidate,
    formats: FormatMap,
) -> None:
    oxides = ["CaO", "SiO2", "Al2O3", "Fe2O3", "MgO", "SO3", "Na2O", "K2O", "LOI"]
    _setup(sheet, [(0, 1, 28), (2, 10, 13)])
    _title(sheet, "XRF INPUTS", formats, 10)
    sheet.write_row(3, 0, ["Role", "Material", *oxides], formats["header"])
    attrs = ["cao", "sio2", "al2o3", "fe2o3", "mgo", "so3", "na2o", "k2o", "loi"]
    for row, component in enumerate(candidate.components, 4):
        material = repository.get("materials", component.reference_id)
        sheet.write(row, 0, component.role, formats["text"])
        sheet.write(row, 1, component.name, formats["text"])
        for column, attr in enumerate(attrs, 2):
            value = getattr(material.chemistry, attr) if isinstance(material, Material) else None
            sheet.write(row, column, value, formats["input"])


def _write_xrd(
    sheet: Worksheet,
    repository: Repository,
    candidate: RetrofitCandidate,
    formats: FormatMap,
) -> None:
    _setup(sheet, [(0, 1, 28), (2, 8, 16)])
    _title(sheet, "XRD / MINERALOGY INPUTS", formats, 8)
    sheet.write_row(
        3,
        0,
        [
            "Role",
            "Material",
            "Kaolinite %",
            "Calcite %",
            "Quartz %",
            "Illite %",
            "Amorphous %",
            "Method",
            "Source / note",
        ],
        formats["header"],
    )
    for row, component in enumerate(candidate.components, 4):
        sheet.write(row, 0, component.role, formats["text"])
        sheet.write(row, 1, component.name, formats["text"])
        for column in range(2, 7):
            sheet.write_blank(row, column, None, formats["input"])
        sheet.write(row, 7, "XRD/Rietveld or validated equivalent", formats["input"])
        sheet.write(row, 8, "Replace before quality prediction", formats["warning"])


def _write_machine_data(
    sheet: Worksheet,
    repository: Repository,
    route: Route,
    formats: FormatMap,
) -> dict[str, int]:
    _setup(sheet, [(0, 2, 26), (3, 12, 16)])
    _title(sheet, "MACHINE DATA", formats, 12)
    headers = [
        "Node",
        "Machine",
        "Stage",
        "Rated t/h",
        "Availability",
        "Effective t/h",
        "Min stable t/h",
        "Max stable t/h",
        "Electricity kWh/t",
        "Heat kcal/kg",
        "Max moisture %",
        "Temperature envelope",
        "Data status",
    ]
    sheet.write_row(3, 0, headers, formats["header"])
    rows: dict[str, int] = {}
    for row, node in enumerate(route.nodes, 4):
        machine = repository.get("machines", node.machine_id)
        if not isinstance(machine, Machine):
            continue
        rows[node.node_id] = row + 1
        sheet.write(row, 0, node.label, formats["text"])
        sheet.write(row, 1, machine.name, formats["text"])
        sheet.write(row, 2, machine.process_stage, formats["text"])
        sheet.write(row, 3, machine.rated_capacity_tph, formats["input"])
        sheet.write(row, 4, machine.availability, formats["input"])
        sheet.write_formula(row, 5, f"=D{row + 1}*E{row + 1}", formats["formula"])
        sheet.write(row, 6, machine.minimum_stable_tph, formats["input"])
        sheet.write(row, 7, machine.maximum_stable_tph, formats["input"])
        sheet.write(row, 8, machine.specific_electricity_kwh_t, formats["input"])
        sheet.write(row, 9, machine.specific_heat_kcal_kg, formats["input"])
        sheet.write(row, 10, machine.maximum_feed_moisture_percent, formats["input"])
        envelope = (
            f"{machine.minimum_temperature_c or 'N/A'} to {machine.maximum_temperature_c or 'N/A'} °C"
        )
        sheet.write(row, 11, envelope, formats["input"])
        sheet.write(row, 12, "PLANT VALUE / REFERENCE", formats["warning"])
    return rows


def _write_fuel(sheet: Worksheet, formats: FormatMap) -> None:
    _setup(sheet, [(0, 0, 28), (1, 2, 18), (3, 3, 55)])
    _title(sheet, "FUEL INPUTS", formats, 3)
    sheet.write_row(3, 0, ["Parameter", "BRIXTA reference", "Plant input", "Basis"], formats["header"])
    rows = [
        ("Fuel type", "Not supplied", "", "Coal/petcoke/alternative-fuel blend"),
        ("NCV", None, None, "kcal/kg"),
        ("Ash", None, None, "%"),
        ("Moisture", None, None, "%"),
        ("Sulfur", None, None, "%"),
        ("Chlorine", None, None, "%"),
        ("Fuel rate", None, None, "kg/t clinker"),
    ]
    for row, item in enumerate(rows, 4):
        sheet.write(row, 0, item[0], formats["label"])
        sheet.write(row, 1, item[1], formats["reference"])
        sheet.write(row, 2, item[2], formats["input"])
        sheet.write(row, 3, item[3], formats["text"])


def _write_power(sheet: Worksheet, candidate: RetrofitCandidate, formats: FormatMap) -> None:
    _setup(sheet, [(0, 0, 28), (1, 2, 18), (3, 3, 55)])
    _title(sheet, "POWER INPUTS", formats, 3)
    sheet.write_row(3, 0, ["Parameter", "BRIXTA reference", "Plant input", "Basis"], formats["header"])
    rows = [
        ("Specific electricity", candidate.electricity_kwh_t, candidate.electricity_kwh_t, "kWh/t LC3"),
        ("Grid share", 1.0, 1.0, "fraction"),
        ("Captive share", 0.0, 0.0, "fraction"),
        ("WHR share", 0.0, 0.0, "fraction"),
        ("Renewable share", 0.0, 0.0, "fraction"),
        ("Grid CO2 factor", None, None, "kg CO2/kWh"),
    ]
    for row, item in enumerate(rows, 4):
        sheet.write(row, 0, item[0], formats["label"])
        sheet.write(row, 1, item[1], formats["reference"])
        sheet.write(row, 2, item[2], formats["input"])
        sheet.write(row, 3, item[3], formats["text"])


def _write_costs(
    sheet: Worksheet,
    candidate: RetrofitCandidate,
    cost_book: CostBook | None,
    formats: FormatMap,
) -> None:
    _setup(sheet, [(0, 0, 32), (1, 2, 20), (3, 3, 60)])
    _title(sheet, "COST INPUTS", formats, 3)
    sheet.write_row(3, 0, ["Cost item", "BRIXTA reference", "Plant input", "Scope / note"], formats["header"])
    rows = [
        ("Material cost", candidate.material_cost_inr_t, candidate.material_cost_inr_t, "INR/t LC3"),
        ("Electricity tariff", cost_book.electricity_inr_kwh if cost_book else 8.5, cost_book.electricity_inr_kwh if cost_book else 8.5, "INR/kWh"),
        ("Thermal fuel tariff", cost_book.thermal_fuel_inr_mkcal if cost_book else 900, cost_book.thermal_fuel_inr_mkcal if cost_book else 900, "INR/million kcal"),
        ("Labour", cost_book.labour_inr_t if cost_book else None, cost_book.labour_inr_t if cost_book else None, "INR/t"),
        ("Maintenance", cost_book.maintenance_inr_t if cost_book else None, cost_book.maintenance_inr_t if cost_book else None, "INR/t"),
        ("Factory overhead", cost_book.factory_overhead_inr_t if cost_book else None, cost_book.factory_overhead_inr_t if cost_book else None, "INR/t"),
        ("Packing", cost_book.packing_inr_t if cost_book else None, cost_book.packing_inr_t if cost_book else None, "INR/t"),
        ("Outbound logistics", cost_book.outbound_logistics_inr_t if cost_book else None, cost_book.outbound_logistics_inr_t if cost_book else None, "INR/t"),
    ]
    for row, item in enumerate(rows, 4):
        sheet.write(row, 0, item[0], formats["label"])
        sheet.write(row, 1, item[1], formats["reference"])
        sheet.write(row, 2, item[2], formats["input"])
        sheet.write(row, 3, item[3], formats["text"])


def _write_production_input(
    sheet: Worksheet,
    case: EngineeringCase,
    study: RetrofitStudyResult,
    candidate: RetrofitCandidate,
    formats: FormatMap,
) -> None:
    _setup(sheet, [(0, 0, 30), (1, 2, 20), (3, 3, 55)])
    _title(sheet, "PRODUCTION INPUTS", formats, 3)
    sheet.write_row(3, 0, ["Parameter", "BRIXTA reference", "Plant input", "Basis"], formats["header"])
    rows = [
        ("Requested output", study.request.target_output_tph, study.request.target_output_tph, "t/h"),
        ("Predicted sustainable output", candidate.predicted_output_tph, candidate.predicted_output_tph, "t/h"),
        ("Operating hours/day", 24, 24, "h/day"),
        ("Operating days/year", 330, 330, "days/year"),
        ("Pilot quantity", case.project.pilot_quantity_t, case.project.pilot_quantity_t, "t"),
        ("Pilot-rate fraction", case.project.pilot_rate_fraction, case.project.pilot_rate_fraction, "fraction of predicted output"),
    ]
    for row, item in enumerate(rows, 4):
        sheet.write(row, 0, item[0], formats["label"])
        sheet.write(row, 1, item[1], formats["reference"])
        sheet.write(row, 2, item[2], formats["input"])
        sheet.write(row, 3, item[3], formats["text"])


def _write_route(
    sheet: Worksheet,
    route: Route,
    repository: Repository,
    formats: FormatMap,
) -> None:
    _setup(sheet, [(0, 0, 18), (1, 2, 28), (3, 5, 18)])
    _title(sheet, "PROCESS ROUTE", formats, 5)
    sheet.write_row(3, 0, ["Seq", "Node", "Machine", "Stage", "Incoming", "Outgoing"], formats["header"])
    incoming: dict[str, list[str]] = {node.node_id: [] for node in route.nodes}
    outgoing: dict[str, list[str]] = {node.node_id: [] for node in route.nodes}
    for edge in route.edges:
        incoming.setdefault(edge.target, []).append(edge.source)
        outgoing.setdefault(edge.source, []).append(edge.target)
    for row, node in enumerate(route.nodes, 4):
        machine = repository.get("machines", node.machine_id)
        sheet.write_row(
            row,
            0,
            [
                row - 3,
                node.label,
                machine.name if isinstance(machine, Machine) else node.machine_id,
                machine.process_stage if isinstance(machine, Machine) else "unknown",
                ", ".join(incoming.get(node.node_id, [])),
                ", ".join(outgoing.get(node.node_id, [])),
            ],
            formats["text"],
        )


def _write_equipment(
    sheet: Worksheet,
    repository: Repository,
    route: Route,
    formats: FormatMap,
) -> None:
    _setup(sheet, [(0, 2, 28), (3, 9, 18)])
    _title(sheet, "EQUIPMENT REGISTER", formats, 9)
    sheet.write_row(
        3,
        0,
        ["Equipment", "Stage", "Kind", "Capacity t/h", "Availability", "Electricity", "Heat", "TRL", "Version", "Validation required"],
        formats["header"],
    )
    for row, node in enumerate(route.nodes, 4):
        machine = repository.get("machines", node.machine_id)
        if not isinstance(machine, Machine):
            continue
        sheet.write_row(
            row,
            0,
            [
                machine.name,
                machine.process_stage,
                machine.machine_kind,
                machine.rated_capacity_tph,
                machine.availability,
                machine.specific_electricity_kwh_t,
                machine.specific_heat_kcal_kg,
                machine.technology_readiness_level,
                machine.version,
                "Replace reference values with vendor and performance-test data",
            ],
            formats["text"],
        )


def _write_tariffs(
    sheet: Worksheet,
    study: RetrofitStudyResult,
    cost_book: CostBook | None,
    formats: FormatMap,
) -> None:
    _setup(sheet, [(0, 0, 28), (1, 2, 20), (3, 3, 55)])
    _title(sheet, "TARIFFS", formats, 3)
    sheet.write_row(3, 0, ["Tariff", "BRIXTA/reference", "Plant input", "Unit"], formats["header"])
    electricity = cost_book.electricity_inr_kwh if cost_book and cost_book.electricity_inr_kwh is not None else 8.5
    thermal = cost_book.thermal_fuel_inr_mkcal if cost_book and cost_book.thermal_fuel_inr_mkcal is not None else 900.0
    rows = [
        ("Electricity", electricity, electricity, "INR/kWh"),
        ("Thermal fuel", thermal, thermal, "INR/million kcal"),
        ("Water", None, None, "INR/m3"),
        ("Carbon price", None, None, "INR/t CO2"),
    ]
    for row, item in enumerate(rows, 4):
        sheet.write(row, 0, item[0], formats["label"])
        sheet.write(row, 1, item[1], formats["reference"])
        sheet.write(row, 2, item[2], formats["input"])
        sheet.write(row, 3, item[3], formats["text"])


def _write_quality_targets(sheet: Worksheet, case: EngineeringCase, formats: FormatMap) -> None:
    _setup(sheet, [(0, 0, 32), (1, 2, 20), (3, 3, 62)])
    _title(sheet, "QUALITY TARGETS", formats, 3)
    sheet.write_row(3, 0, ["Metric", "Reference", "Plant/BIS target", "Validation"], formats["header"])
    rows = [
        ("Applicable standard", "Not inferred", "\n".join(case.project.bis_constraints), "Confirm exact product and BIS clauses"),
        ("Blaine", None, None, "Plant/lab target"),
        ("Residue", None, None, "Plant/lab target"),
        ("Initial setting", None, None, "BIS and customer target"),
        ("Final setting", None, None, "BIS and customer target"),
        ("Soundness", None, None, "BIS target"),
        ("3-day strength", None, None, "BIS/customer target"),
        ("7-day strength", None, None, "BIS/customer target"),
        ("28-day strength", None, None, "BIS/customer target"),
        ("Free lime", None, None, "Plant clinker control limit"),
    ]
    for row, item in enumerate(rows, 4):
        sheet.write(row, 0, item[0], formats["label"])
        sheet.write(row, 1, item[1], formats["reference"])
        sheet.write(row, 2, item[2], formats["input"])
        sheet.write(row, 3, item[3], formats["text"])


def _write_mass_balance(
    sheet: Worksheet,
    candidate: RetrofitCandidate,
    material_rows: dict[str, int],
    formats: FormatMap,
) -> None:
    _setup(sheet, [(0, 0, 30), (1, 1, 36), (2, 4, 20)])
    _title(sheet, "MASS BALANCE", formats, 4)
    sheet.write_row(3, 0, ["Stream", "Formula", "Reference", "Plant case", "Unit"], formats["header"])
    sheet.write_row(4, 0, ["LC3 output", "17_PRODUCTION!C5", candidate.predicted_output_tph, None, "t/h"], formats["text"])
    sheet.write_formula(4, 3, "='17_PRODUCTION'!C5", formats["formula"])
    for row, role in enumerate(["clinker", "calcined_clay", "limestone", "gypsum"], 5):
        material_row = material_rows[role]
        sheet.write(row, 0, role.replace("_", " ").title(), formats["label"])
        sheet.write(row, 1, "Output × formulation % / 100", formats["text"])
        sheet.write_formula(row, 2, f"=$C$5*'10_RAW_MATERIALS'!C{material_row}/100", formats["reference"])
        sheet.write_formula(row, 3, f"=$D$5*'10_RAW_MATERIALS'!D{material_row}/100", formats["formula"])
        sheet.write(row, 4, "t/h", formats["text"])
    sheet.write(11, 0, "Balance closure", formats["label"])
    sheet.write_formula(11, 3, "=SUM(D6:D9)-D5", formats["formula"])
    sheet.write(11, 4, "t/h; target 0", formats["text"])


def _write_heat_balance(sheet: Worksheet, candidate: RetrofitCandidate, formats: FormatMap) -> None:
    _setup(sheet, [(0, 0, 32), (1, 1, 42), (2, 3, 20), (4, 4, 24)])
    _title(sheet, "HEAT BALANCE", formats, 4)
    sheet.write_row(3, 0, ["Heat item", "Basis", "Reference", "Plant input/result", "Unit"], formats["header"])
    rows = [
        ("Net specific thermal demand", "Route and selected clay pathway", candidate.thermal_kcal_kg, candidate.thermal_kcal_kg, "kcal/kg LC3"),
        ("Moisture evaporation", "Requires component moisture and exit temperature", None, None, "kcal/kg"),
        ("Reaction heat", "Requires mineralogy and reaction model", None, None, "kcal/kg"),
        ("Exit gas loss", "Requires gas flow and stack temperature", None, None, "kcal/kg"),
        ("Cooler loss", "Requires clinker/cooling-air measurements", None, None, "kcal/kg"),
        ("Shell radiation/convection", "Requires shell scan and ambient conditions", None, None, "kcal/kg"),
        ("Recovered heat", "Preheater/cooler/WHR recovery", None, None, "kcal/kg"),
    ]
    for row, item in enumerate(rows, 4):
        sheet.write(row, 0, item[0], formats["label"])
        sheet.write(row, 1, item[1], formats["text"])
        sheet.write(row, 2, item[2], formats["reference"])
        sheet.write(row, 3, item[3], formats["input"])
        sheet.write(row, 4, item[4], formats["text"])
    sheet.write(13, 0, "Heat-balance closure", formats["label"])
    sheet.write_formula(13, 3, "=SUM(D5:D11)-D5", formats["formula"])
    sheet.write(13, 4, "Screening placeholder; populate terms", formats["warning"])


def _write_raw_mix(sheet: Worksheet, formats: FormatMap) -> None:
    _setup(sheet, [(0, 0, 30), (1, 2, 22), (3, 3, 65)])
    _title(sheet, "RAW MIX / CLINKER FEED", formats, 3)
    sheet.write_row(3, 0, ["Metric", "Reference", "Plant input", "Note"], formats["header"])
    rows = [
        ("LSF", None, None, "Applicable to raw meal, not finished cement"),
        ("SM", None, None, "Applicable to raw meal, not finished cement"),
        ("AM", None, None, "Applicable to raw meal, not finished cement"),
        ("LOI-corrected clinker yield", None, None, "Enter plant raw-meal and clinker data"),
        ("Fuel ash correction", None, None, "Requires fuel ash chemistry and rate"),
        ("Kiln dust/bypass return", None, None, "Requires plant recycle balance"),
    ]
    for row, item in enumerate(rows, 4):
        sheet.write(row, 0, item[0], formats["label"])
        sheet.write(row, 1, item[1], formats["reference"])
        sheet.write(row, 2, item[2], formats["input"])
        sheet.write(row, 3, item[3], formats["text"])


def _write_kiln(
    sheet: Worksheet,
    study: RetrofitStudyResult,
    candidate: RetrofitCandidate,
    formats: FormatMap,
) -> None:
    _setup(sheet, [(0, 0, 32), (1, 2, 20), (3, 3, 65)])
    _title(sheet, "KILN ENGINEERING", formats, 3)
    sheet.write_row(3, 0, ["Parameter", "Reference", "Plant input", "Engineering note"], formats["header"])
    rows = [
        ("Clinker factor", candidate.clinker_factor_percent, candidate.clinker_factor_percent, "% of LC3"),
        ("Thermal demand", candidate.thermal_kcal_kg, candidate.thermal_kcal_kg, "kcal/kg LC3"),
        ("Burning-zone temperature", None, None, "Do not change from chemistry screening alone"),
        ("Kiln speed", None, None, "Requires kiln geometry, slope, filling and residence-time model"),
        ("Residence time", None, None, "Requires actual geometry and process measurement"),
        ("Kiln O2", None, None, "Requires plant operating envelope"),
        ("Free lime target", None, None, "Requires plant quality target"),
        ("Clay pathway", study.request.clay_supply_mode, study.request.clay_supply_mode, "Purchased or onsite calcination"),
    ]
    for row, item in enumerate(rows, 4):
        sheet.write(row, 0, item[0], formats["label"])
        sheet.write(row, 1, item[1], formats["reference"])
        sheet.write(row, 2, item[2], formats["input"])
        sheet.write(row, 3, item[3], formats["text"])


def _write_grinding(sheet: Worksheet, candidate: RetrofitCandidate, formats: FormatMap) -> None:
    _setup(sheet, [(0, 0, 32), (1, 2, 20), (3, 3, 65)])
    _title(sheet, "GRINDING ENGINEERING", formats, 3)
    sheet.write_row(3, 0, ["Parameter", "Reference", "Plant input", "Engineering note"], formats["header"])
    rows = [
        ("Total specific electricity", candidate.electricity_kwh_t, candidate.electricity_kwh_t, "Route total; allocate by machine using metering"),
        ("Target Blaine", None, None, "Determine through laboratory and mill trial"),
        ("Residue", None, None, "Determine through product target"),
        ("Separator efficiency", None, None, "Required for capacity and circulating load"),
        ("Circulating load", None, None, "Required for mill balance"),
        ("Grinding aid", None, None, "Supplier and trial data required"),
        ("Mill output", candidate.predicted_output_tph, candidate.predicted_output_tph, "t/h LC3 screening"),
    ]
    for row, item in enumerate(rows, 4):
        sheet.write(row, 0, item[0], formats["label"])
        sheet.write(row, 1, item[1], formats["reference"])
        sheet.write(row, 2, item[2], formats["input"])
        sheet.write(row, 3, item[3], formats["text"])


def _write_energy(sheet: Worksheet, candidate: RetrofitCandidate, formats: FormatMap) -> None:
    _setup(sheet, [(0, 0, 32), (1, 3, 20), (4, 4, 35)])
    _title(sheet, "ENERGY BALANCE", formats, 4)
    sheet.write_row(3, 0, ["Metric", "Reference", "Plant input", "Calculated", "Unit"], formats["header"])
    sheet.write_row(4, 0, ["Specific electricity", candidate.electricity_kwh_t, candidate.electricity_kwh_t, None, "kWh/t"], formats["text"])
    sheet.write_formula(4, 3, "=C5", formats["formula"])
    sheet.write_row(5, 0, ["Specific thermal demand", candidate.thermal_kcal_kg, candidate.thermal_kcal_kg, None, "kcal/kg"], formats["text"])
    sheet.write_formula(5, 3, "=C6", formats["formula"])
    sheet.write_row(6, 0, ["Output", candidate.predicted_output_tph, candidate.predicted_output_tph, None, "t/h"], formats["text"])
    sheet.write_formula(6, 3, "=C7", formats["formula"])
    sheet.write(8, 0, "Electrical load", formats["label"])
    sheet.write_formula(8, 3, "=D5*D7", formats["formula"])
    sheet.write(8, 4, "kW", formats["text"])
    sheet.write(9, 0, "Thermal load", formats["label"])
    sheet.write_formula(9, 3, "=D6*D7/1000", formats["formula"])
    sheet.write(9, 4, "Gcal/h", formats["text"])


def _write_equipment_util(
    sheet: Worksheet,
    repository: Repository,
    route: Route,
    machine_rows: dict[str, int],
    formats: FormatMap,
) -> None:
    _setup(sheet, [(0, 2, 28), (3, 7, 18)])
    _title(sheet, "EQUIPMENT UTILIZATION", formats, 7)
    sheet.write_row(3, 0, ["Node", "Machine", "Stage", "Required t/h", "Effective t/h", "Load %", "Headroom t/h", "Status"], formats["header"])
    for row, node in enumerate(route.nodes, 4):
        machine = repository.get("machines", node.machine_id)
        if not isinstance(machine, Machine):
            continue
        source_row = machine_rows.get(node.node_id)
        sheet.write(row, 0, node.label, formats["text"])
        sheet.write(row, 1, machine.name, formats["text"])
        sheet.write(row, 2, machine.process_stage, formats["text"])
        sheet.write_formula(row, 3, "='17_PRODUCTION'!C5", formats["formula"])
        if source_row:
            sheet.write_formula(row, 4, f"='13_MACHINE_DATA'!F{source_row}", formats["formula"])
        else:
            sheet.write(row, 4, machine.rated_capacity_tph * machine.availability, formats["reference"])
        sheet.write_formula(row, 5, f"=IFERROR(D{row + 1}/E{row + 1}*100,0)", formats["formula"])
        sheet.write_formula(row, 6, f"=E{row + 1}-D{row + 1}", formats["formula"])
        sheet.write_formula(row, 7, f'=IF(F{row + 1}>100,"OVERLOAD",IF(F{row + 1}>90,"TIGHT","OK"))', formats["formula"])
    sheet.conditional_format(4, 5, max(4, 3 + len(route.nodes)), 5, {"type": "3_color_scale"})


def _write_production_calc(sheet: Worksheet, case: EngineeringCase, formats: FormatMap) -> None:
    _setup(sheet, [(0, 0, 32), (1, 3, 20), (4, 4, 38)])
    _title(sheet, "PRODUCTION CALCULATION", formats, 4)
    sheet.write_row(3, 0, ["Metric", "Prediction", "Plant actual", "Deviation", "Unit / note"], formats["header"])
    output = next((item.prediction for item in case.predictions if item.code == "output_tph"), None)
    sheet.write_row(4, 0, ["Sustainable output", output, None, None, "t/h"], formats["text"])
    sheet.write_formula(4, 3, "=IF(C5=\"\",\"\",C5-B5)", formats["formula"])
    sheet.write_row(5, 0, ["Operating hours/day", 24, None, None, "h/day"], formats["text"])
    sheet.write_row(6, 0, ["Operating days/year", 330, None, None, "days/year"], formats["text"])
    sheet.write(8, 0, "Annual production", formats["label"])
    sheet.write_formula(8, 1, "=B5*B6*B7", formats["formula"])
    sheet.write_formula(8, 2, "=IF(C5=\"\",\"\",C5*C6*C7)", formats["formula"])
    sheet.write_formula(8, 3, "=IF(C9=\"\",\"\",C9-B9)", formats["formula"])
    sheet.write(8, 4, "t/year", formats["text"])


def _write_cost_calc(
    sheet: Worksheet,
    candidate: RetrofitCandidate,
    material_rows: dict[str, int],
    formats: FormatMap,
) -> None:
    _setup(sheet, [(0, 0, 32), (1, 3, 20), (4, 4, 42)])
    _title(sheet, "COST CALCULATION", formats, 4)
    sheet.write_row(3, 0, ["Cost item", "Reference", "Plant calculation", "Deviation", "Basis"], formats["header"])
    sheet.write(4, 0, "Materials", formats["label"])
    sheet.write(4, 1, candidate.material_cost_inr_t, formats["reference"])
    sheet.write_formula(4, 2, "=SUMPRODUCT('10_RAW_MATERIALS'!D5:D8,'10_RAW_MATERIALS'!G5:G8)/100", formats["formula"])
    sheet.write_formula(4, 3, "=C5-B5", formats["formula"])
    sheet.write(4, 4, "Dosage × delivered cost", formats["text"])
    sheet.write(5, 0, "Electricity", formats["label"])
    sheet.write_formula(5, 1, "='35_ENERGY'!B5*'20_TARIFFS'!B5", formats["reference"])
    sheet.write_formula(5, 2, "='35_ENERGY'!C5*'20_TARIFFS'!C5", formats["formula"])
    sheet.write_formula(5, 3, "=C6-B6", formats["formula"])
    sheet.write(5, 4, "kWh/t × tariff", formats["text"])
    sheet.write(6, 0, "Thermal fuel", formats["label"])
    sheet.write_formula(6, 1, "='35_ENERGY'!B6*'20_TARIFFS'!B6/1000", formats["reference"])
    sheet.write_formula(6, 2, "='35_ENERGY'!C6*'20_TARIFFS'!C6/1000", formats["formula"])
    sheet.write_formula(6, 3, "=C7-B7", formats["formula"])
    sheet.write(6, 4, "kcal/kg × INR/million kcal ÷1000", formats["text"])
    sheet.write(8, 0, "Variable cost", formats["label"])
    sheet.write(8, 1, candidate.total_variable_cost_inr_t, formats["reference"])
    sheet.write_formula(8, 2, "=SUM(C5:C7)", formats["formula"])
    sheet.write_formula(8, 3, "=C9-B9", formats["formula"])
    sheet.write(8, 4, "Excludes unentered fixed/commercial costs", formats["warning"])


def _write_carbon(
    sheet: Worksheet,
    candidate: RetrofitCandidate,
    material_rows: dict[str, int],
    formats: FormatMap,
) -> None:
    _setup(sheet, [(0, 0, 32), (1, 3, 20), (4, 4, 45)])
    _title(sheet, "CARBON CALCULATION", formats, 4)
    sheet.write_row(3, 0, ["Scope", "Reference", "Plant calculation", "Deviation", "Basis"], formats["header"])
    sheet.write(4, 0, "Material CO2", formats["label"])
    sheet.write(4, 1, candidate.material_co2_kg_t, formats["reference"])
    sheet.write_formula(4, 2, "=SUMPRODUCT('10_RAW_MATERIALS'!D5:D8,'10_RAW_MATERIALS'!H5:H8)/100", formats["formula"])
    sheet.write_formula(4, 3, "=C5-B5", formats["formula"])
    sheet.write(4, 4, "Dosage × material CO2 factor", formats["text"])
    sheet.write(5, 0, "Electricity CO2", formats["label"])
    sheet.write_blank(5, 1, None, formats["reference"])
    sheet.write_formula(5, 2, "=IF('15_POWER'!C10=\"\",\"\",'35_ENERGY'!C5*'15_POWER'!C10)", formats["formula"])
    sheet.write(5, 4, "Requires plant electricity factor", formats["text"])
    sheet.write(6, 0, "Fuel combustion CO2", formats["label"])
    sheet.write_blank(6, 1, None, formats["reference"])
    sheet.write_blank(6, 2, None, formats["input"])
    sheet.write(6, 4, "Requires fuel carbon and rate", formats["text"])
    sheet.write(8, 0, "Total reported CO2", formats["label"])
    sheet.write_formula(8, 2, "=SUM(C5:C7)", formats["formula"])
    sheet.write(8, 4, "kg CO2/t LC3", formats["text"])


def _write_sensitivity(sheet: Worksheet, candidate: RetrofitCandidate, formats: FormatMap) -> None:
    _setup(sheet, [(0, 1, 24), (2, 10, 16)])
    _title(sheet, "SENSITIVITY ANALYSIS", formats, 10)
    sheet.write_row(3, 0, ["Scenario", "Chemistry", "Clinker %", "Clay %", "Limestone %", "Gypsum %", "Output t/h", "Electricity", "Thermal", "Cost", "Material CO2"], formats["header"])
    for row, item in enumerate(candidate.stress_tests, 4):
        sheet.write_row(
            row,
            0,
            [
                item.scenario,
                item.chemistry_scenario,
                item.clinker_percent,
                item.calcined_clay_percent,
                item.limestone_percent,
                item.gypsum_percent,
                item.predicted_output_tph,
                item.electricity_kwh_t,
                item.thermal_kcal_kg,
                item.total_variable_cost_inr_t,
                item.material_co2_kg_t,
            ],
            formats["number"],
        )


def _write_scenarios(sheet: Worksheet, study: RetrofitStudyResult, formats: FormatMap) -> None:
    _setup(sheet, [(0, 1, 24), (2, 12, 16)])
    _title(sheet, "SCENARIO COMPARISON", formats, 12)
    sheet.write_row(3, 0, ["Rank", "Candidate", "Clinker %", "Clay %", "Limestone %", "Gypsum %", "Output", "Electricity", "Thermal", "Cost", "CO2", "Robustness", "Pareto"], formats["header"])
    for row, item in enumerate(study.candidates, 4):
        shares = {component.role: component.percentage for component in item.components}
        sheet.write_row(
            row,
            0,
            [
                item.rank,
                item.name,
                shares.get("clinker"),
                shares.get("calcined_clay"),
                shares.get("limestone"),
                shares.get("gypsum"),
                item.predicted_output_tph,
                item.electricity_kwh_t,
                item.thermal_kcal_kg,
                item.total_variable_cost_inr_t,
                item.material_co2_kg_t,
                item.robustness_score,
                "YES" if item.pareto_efficient else "NO",
            ],
            formats["number"],
        )
        sheet.write(row, 1, item.name, formats["text"])
        sheet.write(row, 12, "YES" if item.pareto_efficient else "NO", formats["good"] if item.pareto_efficient else formats["text"])


def _write_plant_actuals(
    sheet: Worksheet,
    validations: list[EngineeringValidationRecord],
    formats: FormatMap,
) -> None:
    _setup(sheet, [(0, 0, 34), (1, 2, 20), (3, 3, 55)])
    _title(sheet, "PLANT ACTUAL VALUES", formats, 3)
    sheet.write_row(3, 0, ["Metric", "Latest recorded", "Plant input", "Unit / note"], formats["header"])
    latest = validations[-1] if validations else None
    rows = [
        ("Output", latest.actual_output_tph if latest else None, None, "t/h"),
        ("Electricity", latest.actual_electricity_kwh_t if latest else None, None, "kWh/t"),
        ("Thermal", latest.actual_thermal_kcal_kg if latest else None, None, "kcal/kg"),
        ("Variable cost", latest.actual_variable_cost_inr_t if latest else None, None, "INR/t"),
        ("Material CO2", latest.actual_material_co2_kg_t if latest else None, None, "kg/t"),
    ]
    for row, item in enumerate(rows, 4):
        sheet.write(row, 0, item[0], formats["label"])
        sheet.write(row, 1, item[1], formats["actual"])
        sheet.write(row, 2, item[2], formats["input"])
        sheet.write(row, 3, item[3], formats["text"])


def _write_lab_results(
    sheet: Worksheet,
    validations: list[EngineeringValidationRecord],
    formats: FormatMap,
) -> None:
    _setup(sheet, [(0, 0, 32), (1, 2, 20), (3, 3, 55)])
    _title(sheet, "LAB RESULTS", formats, 3)
    sheet.write_row(3, 0, ["Test", "Latest recorded", "Plant input", "Unit / requirement"], formats["header"])
    latest = validations[-1] if validations else None
    rows = [
        ("Free lime", latest.actual_free_lime_percent if latest else None, None, "%"),
        ("3-day strength", latest.actual_strength_3d_mpa if latest else None, None, "MPa"),
        ("28-day strength", latest.actual_strength_28d_mpa if latest else None, None, "MPa"),
        ("Blaine", None, None, "m2/kg"),
        ("Residue", None, None, "%"),
        ("Initial setting", None, None, "minutes"),
        ("Final setting", None, None, "minutes"),
        ("Soundness", None, None, "plant/BIS method"),
    ]
    for row, item in enumerate(rows, 4):
        sheet.write(row, 0, item[0], formats["label"])
        sheet.write(row, 1, item[1], formats["actual"])
        sheet.write(row, 2, item[2], formats["input"])
        sheet.write(row, 3, item[3], formats["text"])


def _comparison_sheet(sheet: Worksheet, title: str, rows: list[str], formats: FormatMap) -> None:
    _setup(sheet, [(0, 0, 24), (1, 4, 20), (5, 5, 50)])
    _title(sheet, title, formats, 5)
    sheet.write_row(3, 0, ["Metric", "Predicted", "Actual", "Absolute deviation", "% deviation", "Comment"], formats["header"])
    for row, metric in enumerate(rows, 4):
        sheet.write(row, 0, metric, formats["label"])
        sheet.write_blank(row, 1, None, formats["reference"])
        sheet.write_blank(row, 2, None, formats["input"])
        sheet.write_formula(row, 3, f'=IF(OR(B{row + 1}="",C{row + 1}=""),"",C{row + 1}-B{row + 1})', formats["formula"])
        sheet.write_formula(row, 4, f'=IFERROR(D{row + 1}/B{row + 1}*100,"")', formats["formula"])
        sheet.write_blank(row, 5, None, formats["input"])


def _write_xrf_comparison(sheet: Worksheet, formats: FormatMap) -> None:
    _comparison_sheet(sheet, "XRF COMPARISON", ["CaO", "SiO2", "Al2O3", "Fe2O3", "MgO", "SO3", "Na2O", "K2O", "LOI"], formats)


def _write_xrd_comparison(sheet: Worksheet, formats: FormatMap) -> None:
    _comparison_sheet(sheet, "XRD COMPARISON", ["Kaolinite", "Calcite", "Quartz", "Illite", "Amorphous", "C3S", "C2S", "C3A", "C4AF"], formats)


def _write_free_lime(
    sheet: Worksheet,
    validations: list[EngineeringValidationRecord],
    formats: FormatMap,
) -> None:
    _comparison_sheet(sheet, "FREE LIME VALIDATION", ["Free lime %"], formats)
    if validations and validations[-1].actual_free_lime_percent is not None:
        sheet.write(4, 2, validations[-1].actual_free_lime_percent, formats["actual"])


def _write_strength(
    sheet: Worksheet,
    validations: list[EngineeringValidationRecord],
    formats: FormatMap,
) -> None:
    _comparison_sheet(sheet, "STRENGTH VALIDATION", ["3-day strength", "7-day strength", "28-day strength"], formats)
    if validations:
        latest = validations[-1]
        sheet.write(4, 2, latest.actual_strength_3d_mpa, formats["actual"])
        sheet.write(6, 2, latest.actual_strength_28d_mpa, formats["actual"])


def _write_validation_metric(
    sheet: Worksheet, title: str, unit: str, formats: FormatMap
) -> None:
    _comparison_sheet(sheet, title.upper(), [title], formats)
    sheet.write(4, 5, unit, formats["small"])


def _write_comments(
    sheet: Worksheet,
    validations: list[EngineeringValidationRecord],
    formats: FormatMap,
) -> None:
    _setup(sheet, [(0, 0, 22), (1, 1, 95)])
    _title(sheet, "ENGINEERING COMMENTS", formats, 1)
    sheet.write_row(3, 0, ["Source", "Comment"], formats["header"])
    latest = validations[-1] if validations else None
    rows = [
        ("Plant / pilot", latest.comments if latest else ""),
        ("XRF", latest.xrf_comparison if latest else ""),
        ("XRD", latest.xrd_comparison if latest else ""),
        ("Power", latest.power_observation if latest else ""),
        ("Coal/fuel", latest.coal_observation if latest else ""),
        ("Thermal", latest.thermal_observation if latest else ""),
    ]
    for row, item in enumerate(rows, 4):
        sheet.write(row, 0, item[0], formats["label"])
        sheet.write(row, 1, item[1], formats["input"])


def _write_deviation(
    sheet: Worksheet,
    validations: list[EngineeringValidationRecord],
    formats: FormatMap,
) -> None:
    _setup(sheet, [(0, 0, 28), (1, 5, 20)])
    _title(sheet, "DEVIATION ANALYSIS", formats, 5)
    sheet.write_row(3, 0, ["Metric", "Predicted", "Actual", "Absolute error", "% error", "Status"], formats["header"])
    latest = validations[-1] if validations else None
    errors = latest.prediction_errors if latest else []
    for row, item in enumerate(errors, 4):
        sheet.write_row(row, 0, [item.metric, item.predicted, item.actual, item.absolute_error, item.percent_error, "REVIEW"], formats["number"])
        sheet.write(row, 0, item.metric, formats["label"])


def _write_root_cause(
    sheet: Worksheet,
    validations: list[EngineeringValidationRecord],
    formats: FormatMap,
) -> None:
    _setup(sheet, [(0, 0, 28), (1, 1, 95)])
    _title(sheet, "ROOT CAUSE", formats, 1)
    latest = validations[-1] if validations else None
    sheet.write_row(3, 0, ["Item", "Analysis"], formats["header"])
    sheet.write(4, 0, "Recorded root cause", formats["label"])
    sheet.write(4, 1, latest.root_cause if latest else "", formats["input"])
    sheet.write(6, 0, "Required method", formats["label"])
    sheet.write(6, 1, "Classify material, measurement, model, machine, operating, quality and commercial causes. Link every correction to evidence.", formats["text"])


def _write_signoff(
    sheet: Worksheet,
    role: str,
    validations: list[EngineeringValidationRecord],
    formats: FormatMap,
) -> None:
    _setup(sheet, [(0, 0, 28), (1, 1, 70)])
    _title(sheet, f"{role.upper()} SIGN-OFF", formats, 1)
    latest = validations[-1] if validations else None
    attr = {
        "Engineer": "engineer_signoff",
        "Quality Head": "quality_head_signoff",
        "Plant Head": "plant_head_signoff",
    }[role]
    rows = [
        ("Name / sign-off", getattr(latest, attr) if latest else ""),
        ("Date", ""),
        ("Decision", latest.decision.upper() if latest else "HOLD"),
        ("Conditions / comments", ""),
    ]
    for row, item in enumerate(rows, 3):
        sheet.write(row, 0, item[0], formats["label"])
        sheet.write(row, 1, item[1], formats["input"])


def _write_decision(sheet: Worksheet, case: EngineeringCase, formats: FormatMap) -> None:
    _setup(sheet, [(0, 0, 32), (1, 1, 88)])
    _title(sheet, "ENGINEERING DECISION GATE", formats, 1)
    gate = case.decision_gate
    if gate is None:
        raise ValueError("Engineering decision sheet requires a trust decision gate")
    workbook_decision = "YES — CONTROLLED PILOT ONLY" if gate.pilot_authorised else "NO" if gate.decision == "reject" else "HOLD"
    rows = [
        ("Should this recommendation proceed?", workbook_decision),
        ("Production change authorised?", "YES" if gate.production_change_authorised else "NO"),
        ("Controlled pilot authorised?", "YES" if gate.pilot_authorised else "NO"),
        ("Gate decision", gate.decision.upper()),
        ("Reason", gate.reason),
        ("Risk", case.risk_rating.upper()),
        ("Blocking conditions", "\n".join(gate.blocking_conditions) or "None"),
        ("Conditions to advance", "\n".join(gate.conditions_to_advance)),
        ("Approval requirements", "\n".join(gate.approval_requirements)),
        ("Required tests", "\n".join(sorted({test for rec in case.recommendations for test in rec.required_validation}))),
        ("Pilot quantity", case.pilot_plan.pilot_quantity_t),
        ("Monitoring plan", "\n".join(case.pilot_plan.monitoring_plan)),
    ]
    for row, item in enumerate(rows, 3):
        sheet.write(row, 0, item[0], formats["label"])
        critical = item[0] in {
            "Should this recommendation proceed?",
            "Production change authorised?",
            "Controlled pilot authorised?",
            "Gate decision",
            "Risk",
            "Blocking conditions",
        }
        sheet.write(row, 1, item[1], formats["warning"] if critical else formats["input"])
    sheet.data_validation(3, 1, 3, 1, {"validate": "list", "source": ["YES — CONTROLLED PILOT ONLY", "NO", "HOLD"]})


def _write_pilot(sheet: Worksheet, case: EngineeringCase, formats: FormatMap) -> None:
    _setup(sheet, [(0, 0, 26), (1, 1, 38), (2, 2, 22), (3, 4, 60)])
    _title(sheet, "PILOT PRODUCTION SHEET", formats, 4)
    sheet.write_row(3, 0, ["Section", "Parameter", "Target", "Basis", "Validation"], formats["header"])
    row = 4
    sheet.write(row, 0, "Pilot", formats["label"])
    sheet.write(row, 1, "Quantity", formats["label"])
    sheet.write(row, 2, case.pilot_plan.pilot_quantity_t, formats["input"])
    sheet.write(row, 3, "Engineering case", formats["text"])
    sheet.write(row, 4, "Plant approval", formats["text"])
    row += 1
    sheet.write(row, 0, "Pilot", formats["label"])
    sheet.write(row, 1, "Production rate", formats["label"])
    sheet.write(row, 2, case.pilot_plan.pilot_rate_tph, formats["input"])
    sheet.write(row, 3, "Controlled fraction of predicted output", formats["text"])
    sheet.write(row, 4, "Confirm stage-specific rates", formats["text"])
    row += 2
    for item in [*case.pilot_plan.machine_settings, *case.pilot_plan.kiln_settings, *case.pilot_plan.mill_settings]:
        sheet.write_row(row, 0, [item.area, item.parameter, item.target, item.basis, item.validation], formats["text"])
        row += 1
    row += 1
    for title, items in [
        ("Sampling plan", case.pilot_plan.sampling_plan),
        ("Required lab tests", case.pilot_plan.required_lab_tests),
        ("Go / no-go criteria", case.pilot_plan.go_no_go_criteria),
        ("Monitoring plan", case.pilot_plan.monitoring_plan),
    ]:
        sheet.write(row, 0, title, formats["section"])
        row += 1
        for item in items:
            sheet.write(row, 0, "•", formats["text"])
            sheet.merge_range(row, 1, row, 4, item, formats["text"])
            row += 1


def _write_learning(
    sheet: Worksheet,
    case: EngineeringCase,
    validations: list[EngineeringValidationRecord],
    formats: FormatMap,
) -> None:
    _setup(sheet, [(0, 0, 28), (1, 5, 20), (6, 6, 55)])
    _title(sheet, "MODEL LEARNING / RECALIBRATION", formats, 6)
    sheet.write_row(3, 0, ["Metric", "Predicted", "Actual", "Absolute error", "% error", "Correction factor", "Interpretation"], formats["header"])
    latest = validations[-1] if validations else None
    if latest:
        for row, item in enumerate(latest.prediction_errors, 4):
            sheet.write_row(
                row,
                0,
                [
                    item.metric,
                    item.predicted,
                    item.actual,
                    item.absolute_error,
                    item.percent_error,
                    item.recalibration_factor,
                    "Applied as median plant/product correction in future cases",
                ],
                formats["number"],
            )
            sheet.write(row, 0, item.metric, formats["label"])
        start = 5 + len(latest.prediction_errors)
        sheet.write(start, 0, "MAPE", formats["label"])
        sheet.write(start, 1, latest.mean_absolute_percent_error, formats["actual"])
        sheet.write(start + 1, 0, "Confidence before", formats["label"])
        sheet.write(start + 1, 1, latest.confidence_before_percent, formats["reference"])
        sheet.write(start + 2, 0, "Confidence after", formats["label"])
        sheet.write(start + 2, 1, latest.confidence_after_percent, formats["actual"])
    else:
        sheet.merge_range(4, 0, 6, 6, "No pilot/plant actuals have been imported. Enter actuals in the BRIXTA Learning stage or validation sheets.", formats["warning"])


def _write_trust_summary(
    sheet: Worksheet,
    case: EngineeringCase,
    formats: FormatMap,
) -> None:
    _setup(sheet, [(0, 0, 34), (1, 1, 22), (2, 2, 72)])
    _title(sheet, "ENGINEERING TRUST SUMMARY", formats, 2)
    trust = case.trust_assessment
    gate = case.decision_gate
    if trust is None or gate is None:
        raise ValueError("Trust summary requires a version 1.0.0 trust assessment and decision gate")
    rows = [
        ("Decision gate", gate.decision.upper(), gate.reason),
        ("Production change authorised", "YES" if gate.production_change_authorised else "NO", "A calculation or workbook never authorises a production change by itself."),
        ("Pilot authorised", "YES" if gate.pilot_authorised else "NO", "Controlled pilot eligibility is governed by evidence, validation, review and risk gates."),
        ("Earned confidence", trust.overall_confidence_percent, trust.confidence_band.upper()),
        ("Evidence coverage", trust.evidence_coverage_percent, "Quality-weighted evidence register coverage"),
        ("Data completeness", trust.data_completeness_percent, "Penalty applied for unknown and insufficiently evidenced inputs"),
        ("Calculation traceability", trust.traceability_percent, "Prediction basis, validation requirements, evidence and calculation trace"),
        ("Validation readiness", trust.validation_readiness_percent, "Availability of blocking laboratory and plant validation"),
        ("Critical assumptions", len(trust.critical_assumptions), "Every assumption has consequence and replacement-data instructions"),
        ("Unknown inputs", len(trust.unknown_inputs), "Unknowns remain explicit; they are never silently converted to zero"),
        ("Open risks", len(trust.risk_register), "Sorted by risk-priority number"),
        ("Mandatory reviews", sum(item.mandatory for item in trust.review_committee), "Multidisciplinary committee gate"),
    ]
    for row, (label, value, note) in enumerate(rows, 3):
        sheet.write(row, 0, label, formats["label"])
        fmt = formats["warning"] if label in {"Decision gate", "Production change authorised", "Pilot authorised"} else formats["number"]
        sheet.write(row, 1, value, fmt)
        sheet.write(row, 2, note, formats["text"])
    start = 17
    sheet.merge_range(start, 0, start, 2, "FIVE TRUST QUESTIONS", formats["section"])
    sheet.write_row(start + 1, 0, ["Question", "Status", "Answer"], formats["header"])
    for offset, item in enumerate(trust.trust_questions, start + 2):
        sheet.write(offset, 0, item.question, formats["label"])
        sheet.write(offset, 1, item.status.upper(), formats["good"] if item.status == "adequate" else formats["warning"])
        sheet.write(offset, 2, item.answer, formats["text"])


def _write_evidence_register(
    sheet: Worksheet,
    case: EngineeringCase,
    formats: FormatMap,
) -> None:
    _setup(sheet, [(0, 0, 20), (1, 1, 28), (2, 2, 24), (3, 3, 48), (4, 4, 36), (5, 6, 17), (7, 8, 44)])
    _title(sheet, "EVIDENCE REGISTER", formats, 8)
    sheet.write_row(3, 0, ["Evidence ID", "Subject", "Class", "Title", "Source URI", "Quality %", "Status", "Applies to", "Limitations"], formats["header"])
    for row, item in enumerate(case.evidence_register, 4):
        sheet.write_row(
            row,
            0,
            [
                item.evidence_id,
                item.subject,
                item.evidence_class,
                item.title,
                item.source_uri or "",
                item.quality_score_percent,
                item.status,
                "\n".join(item.applies_to),
                "\n".join(item.limitations),
            ],
            formats["text"],
        )
        sheet.write(row, 5, item.quality_score_percent, formats["number"])
        sheet.write(row, 6, item.status.upper(), formats["good"] if item.status == "known" else formats["warning"])


def _write_confidence_register(
    sheet: Worksheet,
    case: EngineeringCase,
    formats: FormatMap,
) -> None:
    _setup(sheet, [(0, 0, 22), (1, 1, 30), (2, 4, 18), (5, 5, 22), (6, 9, 55)])
    _title(sheet, "PREDICTION CONFIDENCE REGISTER", formats, 9)
    sheet.write_row(3, 0, ["Code", "Prediction", "Raw prediction", "Calibration factor", "Confidence %", "Interval", "Method", "Critical assumptions", "Sensitive variables", "Unknown inputs / validation"], formats["header"])
    for row, item in enumerate(case.predictions, 4):
        interval = item.prediction_interval
        interval_text = "N/A"
        if interval is not None:
            if interval.low is not None and interval.high is not None:
                interval_text = f"{interval.low} to {interval.high} {interval.unit or ''}".strip()
            else:
                interval_text = str(interval.central)
        sheet.write(row, 0, item.code, formats["text"])
        sheet.write(row, 1, f"{item.prediction} {item.unit or ''}".strip(), formats["text"])
        sheet.write(row, 2, item.raw_prediction, formats["reference"])
        sheet.write(row, 3, item.calibration_factor, formats["number"])
        sheet.write(row, 4, item.confidence_percent, formats["number"])
        sheet.write(row, 5, interval_text, formats["text"])
        sheet.write(row, 6, item.method, formats["text"])
        sheet.write(row, 7, "\n".join(item.critical_assumptions), formats["text"])
        sheet.write(row, 8, "\n".join(item.sensitive_variables), formats["text"])
        sheet.write(row, 9, "\n".join([*item.unknown_inputs, *item.required_validation]), formats["text"])


def _write_risk_register(
    sheet: Worksheet,
    case: EngineeringCase,
    formats: FormatMap,
) -> None:
    _setup(sheet, [(0, 0, 18), (1, 1, 18), (2, 4, 50), (5, 8, 12), (9, 10, 50)])
    _title(sheet, "ENGINEERING RISK REGISTER", formats, 10)
    sheet.write_row(3, 0, ["Risk ID", "Discipline", "Failure mode", "Cause", "Consequence", "Severity", "Likelihood", "Detectability", "RPN", "Mitigation", "Rollback trigger"], formats["header"])
    for row, item in enumerate(case.risk_register, 4):
        sheet.write_row(
            row,
            0,
            [
                item.failure_mode_id,
                item.discipline,
                item.failure_mode,
                item.cause,
                item.consequence,
                item.severity,
                item.likelihood,
                item.detectability,
                item.risk_priority_number,
                item.mitigation,
                item.rollback_trigger,
            ],
            formats["text"],
        )
        sheet.write(row, 8, item.risk_priority_number, formats["warning"] if item.risk_priority_number >= 60 else formats["number"])


def _write_review_committee(
    sheet: Worksheet,
    case: EngineeringCase,
    formats: FormatMap,
) -> None:
    _setup(sheet, [(0, 0, 20), (1, 2, 14), (3, 4, 65), (5, 5, 34), (6, 6, 55)])
    _title(sheet, "MULTIDISCIPLINARY ENGINEERING REVIEW", formats, 6)
    sheet.write_row(3, 0, ["Discipline", "Mandatory", "Status", "Findings", "Blocking issues", "Approval owner", "Evidence reviewed"], formats["header"])
    for row, item in enumerate(case.review_committee, 4):
        sheet.write(row, 0, item.discipline, formats["label"])
        sheet.write(row, 1, "YES" if item.mandatory else "NO", formats["text"])
        sheet.write(row, 2, item.status.upper(), formats["good"] if item.status == "pass" else formats["warning"])
        sheet.write(row, 3, "\n".join(item.findings), formats["text"])
        sheet.write(row, 4, "\n".join(item.blocking_issues), formats["warning"] if item.blocking_issues else formats["text"])
        sheet.write(row, 5, item.approval_required_from, formats["text"])
        sheet.write(row, 6, "\n".join(item.evidence_reviewed), formats["text"])


def _write_scenario_rationale(
    sheet: Worksheet,
    case: EngineeringCase,
    formats: FormatMap,
) -> None:
    _setup(sheet, [(0, 0, 8), (1, 1, 28), (2, 4, 52), (5, 6, 18), (7, 9, 52)])
    _title(sheet, "SCENARIO ENGINEERING RATIONALE", formats, 9)
    sheet.write_row(3, 0, ["Rank", "Scenario", "Why it exists", "Expected benefit", "Expected downside", "Probability %", "Risk", "Business impact", "Engineering impact", "Required validation"], formats["header"])
    for row, item in enumerate(case.scenario_assessments, 4):
        sheet.write(row, 0, item.rank, formats["integer"])
        sheet.write(row, 1, item.name, formats["label"])
        sheet.write(row, 2, item.why_it_exists, formats["text"])
        sheet.write(row, 3, "\n".join(item.expected_benefit), formats["text"])
        sheet.write(row, 4, "\n".join(item.expected_downside), formats["text"])
        sheet.write(row, 5, item.probability_of_success_percent, formats["number"])
        sheet.write(row, 6, item.risk_level.upper(), formats["warning"] if item.risk_level in {"high", "critical"} else formats["text"])
        sheet.write(row, 7, item.business_impact, formats["text"])
        sheet.write(row, 8, item.engineering_impact, formats["text"])
        sheet.write(row, 9, "\n".join(item.required_validation), formats["text"])


def _write_validation_matrix(
    sheet: Worksheet,
    case: EngineeringCase,
    formats: FormatMap,
) -> None:
    _setup(sheet, [(0, 0, 18), (1, 3, 50), (4, 4, 42), (5, 7, 24), (8, 8, 18), (9, 9, 55)])
    _title(sheet, "VALIDATION MATRIX", formats, 9)
    sheet.write_row(3, 0, ["Validation ID", "Category", "Measurement", "Purpose", "Acceptance tolerance", "Frequency / sample", "Owner", "Availability", "Blocking", "Evidence generated"], formats["header"])
    for row, item in enumerate(case.validation_plan, 4):
        sheet.write_row(
            row,
            0,
            [
                item.validation_id,
                item.category,
                item.measurement,
                item.purpose,
                item.acceptable_tolerance,
                item.frequency_or_sample,
                item.owner,
                item.availability,
                "YES" if item.blocking else "NO",
                item.evidence_generated,
            ],
            formats["text"],
        )
        sheet.write(row, 7, item.availability.upper(), formats["good"] if item.availability == "available" else formats["warning"])
        sheet.write(row, 8, "YES" if item.blocking else "NO", formats["warning"] if item.blocking else formats["text"])


def _write_operator_checklist(
    sheet: Worksheet,
    case: EngineeringCase,
    formats: FormatMap,
) -> None:
    _setup(sheet, [(0, 0, 8), (1, 1, 82), (2, 2, 24)])
    _title(sheet, "SHIFT / OPERATOR CHECKLIST", formats, 2)
    sheet.write_row(3, 0, ["Done", "Checklist item", "Responsible / time"], formats["header"])
    items = [
        "Confirm approved case ID, revision, recipe and rollback recipe.",
        "Confirm all interlocks, alarms and environmental monitoring are operational.",
        "Confirm feeder calibration, material identity and silo route.",
        "Confirm laboratory sampling resources and product-hold instruction.",
        *case.pilot_plan.monitoring_plan,
        *case.pilot_plan.go_no_go_criteria,
    ]
    for row, item in enumerate(items, 4):
        sheet.write(row, 0, "☐", formats["input"])
        sheet.write(row, 1, item, formats["text"])
        sheet.write(row, 2, "", formats["input"])


def _write_rollback(
    sheet: Worksheet,
    case: EngineeringCase,
    formats: FormatMap,
) -> None:
    _setup(sheet, [(0, 0, 8), (1, 2, 70)])
    _title(sheet, "ROLLBACK PROCEDURE", formats, 2)
    sheet.merge_range(3, 0, 3, 2, "The trial must be stopped or held when any approved rollback trigger occurs.", formats["warning"])
    sheet.write_row(5, 0, ["Step", "Rollback action", "Record / approval"], formats["header"])
    actions = [
        "Stop increasing the changed parameter or production rate.",
        "Return recipe, feed, fuel and machine controls to the last approved baseline.",
        "Segregate and hold affected material; preserve representative samples.",
        "Record time, readings, alarms, operator actions and equipment state.",
        "Obtain Process, Quality and Plant Head disposition before restart.",
    ]
    for row, item in enumerate(actions, 6):
        sheet.write(row, 0, row - 5, formats["integer"])
        sheet.write(row, 1, item, formats["text"])
        sheet.write(row, 2, "", formats["input"])
    start = 13
    sheet.merge_range(start, 0, start, 2, "CASE-SPECIFIC ROLLBACK TRIGGERS", formats["section"])
    for row, item in enumerate(case.risk_register, start + 1):
        sheet.write(row, 0, item.discipline, formats["label"])
        sheet.write(row, 1, item.rollback_trigger, formats["warning"])
        sheet.write(row, 2, item.mitigation, formats["text"])


def _write_lessons_learned(
    sheet: Worksheet,
    case: EngineeringCase,
    validations: list[EngineeringValidationRecord],
    formats: FormatMap,
) -> None:
    _setup(sheet, [(0, 0, 20), (1, 1, 26), (2, 4, 48), (5, 7, 20)])
    _title(sheet, "LESSONS LEARNED / CONTROLLED MODEL IMPROVEMENT", formats, 7)
    sheet.write_row(3, 0, ["Validation ID", "Accepted for calibration", "Rejection reason", "Root cause", "Corrective action / comments", "MAPE %", "Confidence before", "Confidence after"], formats["header"])
    for row, item in enumerate(validations, 4):
        sheet.write(row, 0, item.validation_id, formats["text"])
        sheet.write(row, 1, "YES" if item.accepted_for_calibration else "NO", formats["good"] if item.accepted_for_calibration else formats["warning"])
        sheet.write(row, 2, item.calibration_rejection_reason or "", formats["text"])
        sheet.write(row, 3, item.root_cause or "", formats["text"])
        sheet.write(row, 4, item.comments or "", formats["text"])
        sheet.write(row, 5, item.mean_absolute_percent_error, formats["number"])
        sheet.write(row, 6, item.confidence_before_percent, formats["number"])
        sheet.write(row, 7, item.confidence_after_percent, formats["number"])
    if not validations:
        sheet.merge_range(4, 0, 6, 7, "No completed validation record exists. The model must not learn from unvalidated or unsigned observations.", formats["warning"])


def _write_version_history(
    sheet: Worksheet,
    case: EngineeringCase,
    formats: FormatMap,
) -> None:
    trust = case.trust_assessment
    gate = case.decision_gate
    if trust is None or gate is None:
        raise ValueError(
            "Version history requires a trust assessment and decision gate"
        )

    _setup(sheet, [(0, 0, 24), (1, 1, 34), (2, 2, 28), (3, 3, 70)])
    _title(sheet, "VERSION HISTORY AND MODEL MANIFEST", formats, 3)
    sheet.write_row(3, 0, ["Field", "Value", "Owner", "Traceability note"], formats["header"])
    rows = [
        ("Case ID", case.case_id, case.project.engineer, "Immutable engineering decision identifier"),
        ("Revision", case.project.revision, case.project.engineer, "Controlled project revision"),
        ("Calculation version", case.calculation_version, "BRIXTA", "Equation and decision-engine version"),
        ("Catalog version", trust.catalog_version, "BRIXTA", "Configurable product, evidence and governance catalog"),
        ("Source study", case.study_id, "BRIXTA", "Scenario-generation source"),
        ("Source scenario", case.candidate_id, "BRIXTA", "Selected candidate identifier"),
        ("Baseline blend", case.baseline_blend_id, "Plant / BRIXTA", "Versioned formulation basis"),
        ("Route", case.route_id, "Plant / BRIXTA", "Versioned process route"),
        ("Created at", case.created_at.isoformat(), case.project.engineer, "Case generation timestamp"),
        ("Decision gate", gate.decision, "Engineering review committee", gate.reason),
    ]
    for row, item in enumerate(rows, 4):
        sheet.write_row(row, 0, item, formats["text"])