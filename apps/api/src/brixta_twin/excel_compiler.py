from __future__ import annotations

from io import BytesIO

import xlsxwriter
from xlsxwriter.format import Format

from .models import CostBook, Material, RetrofitCandidate, RetrofitStudyResult
from .retrofit import REFERENCE_CO2_KG_T, REFERENCE_COST_INR_T
from .storage import Repository


def compile_retrofit_workbook(
    repository: Repository,
    study: RetrofitStudyResult,
    candidate_id: str | None = None,
) -> bytes:
    candidate = _candidate(study, candidate_id)
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    workbook.set_properties(
        {
            "title": f"BRIXTA PPC-to-LC3 Retrofit — {candidate.name}",
            "subject": "Deterministic cement-plant retrofit engineering model",
            "author": "BRIXTA",
            "company": "BRIXTA",
            "comments": (
                "Reference engineering workbook. Replace blue input cells with plant, vendor, "
                "laboratory and commercial data before investment or compliance decisions."
            ),
        }
    )
    workbook.set_calc_mode("auto")

    formats = _formats(workbook)
    readme = workbook.add_worksheet("00_READ_ME")
    control = workbook.add_worksheet("01_MODEL_CONTROL")
    assumptions = workbook.add_worksheet("02_ASSUMPTIONS")
    materials = workbook.add_worksheet("03_MATERIALS")
    chain = workbook.add_worksheet("04_FORMULATION_CHAIN")
    candidates = workbook.add_worksheet("05_CANDIDATES")
    mass = workbook.add_worksheet("06_MASS_BALANCE")
    energy = workbook.add_worksheet("07_ENERGY_CAPACITY")
    cost = workbook.add_worksheet("08_COST_CO2")
    stress = workbook.add_worksheet("09_STRESS_TEST")
    replace = workbook.add_worksheet("10_DATA_TO_REPLACE")
    trace = workbook.add_worksheet("11_CALCULATION_TRACE")
    dashboard = workbook.add_worksheet("12_DASHBOARD")

    _write_readme(readme, study, candidate, formats)
    _write_control(control, study, candidate, formats)
    component_rows = _write_materials(
        repository, materials, study, candidate, formats
    )
    _write_assumptions(assumptions, study, formats)
    _write_chain(chain, candidate, formats)
    _write_candidates(workbook, candidates, study, formats)
    _write_mass_balance(mass, candidate, component_rows, formats)
    _write_energy(energy, candidate, formats)
    _write_cost_co2(cost, candidate, component_rows, formats)
    _write_stress(stress, candidate, formats)
    _write_replacements(replace, study, formats)
    _write_trace(trace, candidate, formats)
    _write_dashboard(dashboard, candidate, formats)

    workbook.close()
    return output.getvalue()


def _candidate(study: RetrofitStudyResult, candidate_id: str | None) -> RetrofitCandidate:
    selected_id = candidate_id or study.selected_candidate_id
    candidate = next(
        (item for item in study.candidates if item.candidate_id == selected_id),
        study.candidates[0] if study.candidates else None,
    )
    if candidate is None:
        raise ValueError("Retrofit study has no exportable candidate")
    return candidate


def _formats(workbook: xlsxwriter.Workbook) -> dict[str, Format]:
    return {
        "title": workbook.add_format(
            {"bold": True, "font_size": 18, "font_color": "#FFFFFF", "bg_color": "#17324D", "align": "left", "valign": "vcenter"}
        ),
        "section": workbook.add_format(
            {"bold": True, "font_size": 12, "font_color": "#FFFFFF", "bg_color": "#245B78", "border": 1}
        ),
        "header": workbook.add_format(
            {"bold": True, "font_color": "#FFFFFF", "bg_color": "#397A8A", "border": 1, "text_wrap": True, "align": "center", "valign": "vcenter"}
        ),
        "label": workbook.add_format({"bold": True, "bg_color": "#E8EEF2", "border": 1}),
        "input": workbook.add_format({"bg_color": "#D9EAF7", "border": 1, "num_format": "0.00"}),
        "reference": workbook.add_format({"bg_color": "#FFF2CC", "border": 1, "num_format": "0.00"}),
        "formula": workbook.add_format({"bg_color": "#E7E6E6", "border": 1, "num_format": "0.00"}),
        "measured": workbook.add_format({"bg_color": "#E2F0D9", "border": 1, "num_format": "0.00"}),
        "warning": workbook.add_format({"bg_color": "#FCE4D6", "font_color": "#9C0006", "border": 1, "text_wrap": True}),
        "text": workbook.add_format({"border": 1, "text_wrap": True, "valign": "top"}),
        "small": workbook.add_format({"font_size": 9, "font_color": "#666666", "text_wrap": True}),
        "percent": workbook.add_format({"border": 1, "num_format": "0.00%"}),
        "percent_input": workbook.add_format({"bg_color": "#D9EAF7", "border": 1, "num_format": "0.00"}),
        "money": workbook.add_format({"border": 1, "num_format": "₹#,##0.00"}),
        "integer": workbook.add_format({"border": 1, "num_format": "0"}),
        "number": workbook.add_format({"border": 1, "num_format": "0.00"}),
        "kpi": workbook.add_format(
            {"bold": True, "font_size": 15, "font_color": "#17324D", "bg_color": "#EAF3F7", "border": 1, "align": "center", "valign": "vcenter", "num_format": "0.00"}
        ),
    }


def _setup(sheet, widths: list[tuple[int, int, float]]) -> None:
    sheet.hide_gridlines(2)
    sheet.freeze_panes(4, 0)
    for first, last, width in widths:
        sheet.set_column(first, last, width)


def _title(sheet, text: str, formats, last_col: int = 7) -> None:
    sheet.merge_range(0, 0, 1, last_col, text, formats["title"])
    sheet.set_row(0, 25)
    sheet.set_row(1, 10)


def _write_readme(sheet, study, candidate, formats) -> None:
    _setup(sheet, [(0, 0, 24), (1, 1, 90)])
    _title(sheet, "BRIXTA PPC-TO-LC3 RETROFIT ENGINEERING WORKBOOK", formats, 1)
    rows = [
        ("Study ID", study.study_id),
        ("Calculation version", study.calculation_version),
        ("Selected design", candidate.name),
        ("Purpose", "Calibrate and reproduce the BRIXTA reference retrofit design using confidential plant values."),
        ("Solver", study.algorithm),
        ("Scope", "PPC baseline to LC3 retrofit: formulation, route capacity, energy, cost, CO2, asset gaps and robustness."),
        ("Important", "This workbook is a reference engineering model, not product certification or an investment guarantee."),
        ("How to use", "Replace blue cells with plant/vendor/laboratory/commercial values. Grey cells are formulas. Yellow cells are BRIXTA reference assumptions."),
        ("Recalculation", "Desktop Excel recalculates formulas automatically. Change the selected formulation percentages and target output to test plant-specific cases."),
    ]
    for row, (label, value) in enumerate(rows, 3):
        sheet.write(row, 0, label, formats["label"])
        sheet.write(row, 1, value, formats["warning"] if label == "Important" else formats["text"])


def _write_control(sheet, study, candidate, formats) -> None:
    _setup(sheet, [(0, 0, 30), (1, 1, 20), (2, 2, 20), (3, 3, 55)])
    _title(sheet, "MODEL CONTROL", formats, 3)
    sheet.write_row(3, 0, ["Parameter", "BRIXTA reference", "Plant input", "Basis / instruction"], formats["header"])
    rows = [
        ("Target LC3 output", study.request.target_output_tph, study.request.target_output_tph, "t/h; replace with required plant campaign output"),
        ("Electricity tariff", _electricity_tariff(study), _electricity_tariff(study), "INR/kWh"),
        ("Thermal-fuel tariff", _thermal_tariff(study), _thermal_tariff(study), "INR/million kcal"),
        ("Raw clay to calcined-clay yield", study.request.raw_clay_to_calcined_yield, study.request.raw_clay_to_calcined_yield, "fraction; onsite calcination only"),
        ("Calcined-clay reactivity index", study.request.calcined_clay_reactivity_index, study.request.calcined_clay_reactivity_index, "0-1 screening index; replace with test evidence"),
        ("Clay kaolinite", study.request.clay_kaolinite_percent, study.request.clay_kaolinite_percent, "% mineralogical basis"),
        ("Reference clay-calciner capacity", study.request.reference_clay_calciner_capacity_tph, study.request.reference_clay_calciner_capacity_tph, "t/h product"),
        ("Reference calciner electricity", study.request.reference_clay_calciner_electricity_kwh_t, study.request.reference_clay_calciner_electricity_kwh_t, "kWh/t calcined clay"),
        ("Reference calciner thermal duty", study.request.reference_clay_calciner_thermal_kcal_kg, study.request.reference_clay_calciner_thermal_kcal_kg, "kcal/kg calcined clay"),
    ]
    for row, item in enumerate(rows, 4):
        sheet.write(row, 0, item[0], formats["label"])
        sheet.write(row, 1, item[1], formats["reference"])
        sheet.write(row, 2, item[2], formats["input"])
        sheet.write(row, 3, item[3], formats["text"])
    sheet.data_validation(4, 2, 12, 2, {"validate": "decimal", "criteria": ">=", "value": 0})
    sheet.write(14, 0, "Selected candidate", formats["label"])
    sheet.write(14, 1, candidate.name, formats["reference"])
    sheet.write(14, 2, candidate.name, formats["input"])


def _write_assumptions(sheet, study, formats) -> None:
    _setup(sheet, [(0, 0, 30), (1, 1, 28), (2, 2, 85)])
    _title(sheet, "ASSUMPTION REGISTER", formats, 2)
    sheet.write_row(3, 0, ["Key", "Value", "Basis"], formats["header"])
    for row, item in enumerate(study.assumptions, 4):
        sheet.write(row, 0, item.key, formats["text"])
        sheet.write(row, 1, item.value, formats["reference"])
        sheet.write(row, 2, item.basis, formats["text"])


def _component_defaults(repository, study, component) -> tuple[float, float, str]:
    cost_book = repository.get("cost_books", study.request.cost_book_id) if study.request.cost_book_id else None
    unit_cost = None
    unit_co2 = None
    source = "BRIXTA reference"
    if component.component_type == "material":
        material = repository.get("materials", component.reference_id)
        if isinstance(material, Material):
            unit_cost = material.cost_inr_per_t
            unit_co2 = material.co2_kg_per_t
            if isinstance(cost_book, CostBook):
                entry = next((item for item in cost_book.material_costs if item.material_id == material.material_id), None)
                if entry and entry.purchased_delivered_cost_inr_t is not None:
                    unit_cost = entry.purchased_delivered_cost_inr_t
                    source = "Cost book"
            if unit_cost is not None or unit_co2 is not None:
                source = "Plant/library record"
    return (
        float(unit_cost if unit_cost is not None else REFERENCE_COST_INR_T[component.role]),
        float(unit_co2 if unit_co2 is not None else REFERENCE_CO2_KG_T[component.role]),
        source,
    )


def _write_materials(repository, sheet, study, candidate, formats) -> dict[str, int]:
    _setup(sheet, [(0, 0, 18), (1, 1, 34), (2, 3, 18), (4, 7, 14), (8, 9, 18), (10, 10, 24)])
    _title(sheet, "MATERIALS AND EDITABLE LC3 FORMULATION", formats, 10)
    headers = ["Role", "Source", "Type", "Reference ID", "BRIXTA %", "Plant input %", "Minimum %", "Maximum %", "Unit cost INR/t", "Material CO2 kg/t", "Value source"]
    sheet.write_row(3, 0, headers, formats["header"])
    rows: dict[str, int] = {}
    for row, component in enumerate(candidate.components, 4):
        rows[component.role] = row + 1  # Excel row number
        unit_cost, unit_co2, value_source = _component_defaults(repository, study, component)
        values = [
            component.role,
            component.name,
            component.component_type,
            component.reference_id,
            component.percentage,
            component.percentage,
            component.minimum_percent,
            component.maximum_percent,
            unit_cost,
            unit_co2,
            value_source,
        ]
        for column, value in enumerate(values):
            fmt = formats["text"]
            if column == 4:
                fmt = formats["reference"]
            elif column in {5, 8, 9}:
                fmt = formats["input"]
            elif column in {6, 7}:
                fmt = formats["reference"]
            sheet.write(row, column, value, fmt)
        sheet.data_validation(row, 5, row, 5, {
            "validate": "decimal",
            "criteria": "between",
            "minimum": f"=G{row+1}",
            "maximum": f"=H{row+1}",
            "input_title": "Plant formulation percentage",
            "input_message": "Keep the dosage inside the BRIXTA screening bounds.",
        })
    total_row = 4 + len(candidate.components)
    sheet.write(total_row, 3, "TOTAL", formats["label"])
    sheet.write_formula(total_row, 4, f"=SUM(E5:E{total_row})", formats["formula"])
    sheet.write_formula(total_row, 5, f"=SUM(F5:F{total_row})", formats["formula"])
    sheet.conditional_format(total_row, 5, total_row, 5, {"type": "cell", "criteria": "not between", "minimum": 99.999, "maximum": 100.001, "format": formats["warning"]})
    sheet.write(total_row + 2, 0, "Blue cells are the plant-editable formulation and commercial/environmental inputs.", formats["small"])
    return rows


def _write_chain(sheet, candidate, formats) -> None:
    _setup(sheet, [(0, 0, 22), (1, 1, 32), (2, 2, 45), (3, 5, 38)])
    _title(sheet, "MULTI-LEVEL FORMULATION CHAIN", formats, 5)
    sheet.write_row(3, 0, ["Level", "Name", "Purpose", "Inputs", "Outputs", "Key results / assumptions"], formats["header"])
    for row, stage in enumerate(candidate.formulation_chain, 4):
        details = "; ".join(f"{key}={value}" for key, value in stage.key_results.items())
        assumptions = "; ".join(stage.assumptions)
        sheet.write_row(row, 0, [stage.level, stage.name, stage.purpose, "\n".join(stage.inputs), "\n".join(stage.outputs), "\n".join(filter(None, [details, assumptions]))], formats["text"])
        sheet.set_row(row, 48)


def _write_candidates(workbook, sheet, study, formats) -> None:
    _setup(sheet, [(0, 0, 7), (1, 1, 24), (2, 5, 13), (6, 17, 16)])
    _title(sheet, "PARETO CANDIDATE SHORTLIST", formats, 17)
    headers = ["Rank", "Candidate", "Clinker %", "Clay %", "Limestone %", "Gypsum %", "Output t/h", "Electricity kWh/t", "Thermal kcal/kg", "Variable cost INR/t", "Material CO2 kg/t", "Robustness", "Complexity", "Pareto", "Output delta vs PPC", "Electricity delta vs PPC", "Material-cost delta vs PPC", "Material-CO2 delta vs PPC"]
    sheet.write_row(3, 0, headers, formats["header"])
    for row, candidate in enumerate(study.candidates, 4):
        shares = {item.role: item.percentage for item in candidate.components}
        sheet.write_row(row, 0, [candidate.rank, candidate.name, shares["clinker"], shares["calcined_clay"], shares["limestone"], shares["gypsum"], candidate.predicted_output_tph, candidate.electricity_kwh_t, candidate.thermal_kcal_kg, candidate.total_variable_cost_inr_t, candidate.material_co2_kg_t, candidate.robustness_score, candidate.retrofit_complexity_score, "YES" if candidate.pareto_efficient else "NO", candidate.output_delta_vs_ppc_tph, candidate.electricity_delta_vs_ppc_kwh_t, candidate.material_cost_delta_vs_ppc_inr_t, candidate.material_co2_delta_vs_ppc_kg_t], formats["number"])
        sheet.write(row, 1, candidate.name, formats["text"])
        sheet.write(row, 13, "YES" if candidate.pareto_efficient else "NO", formats["measured"] if candidate.pareto_efficient else formats["text"])
    if study.candidates:
        chart = workbook.add_chart({"type": "scatter", "subtype": "straight_with_markers"})
        last_row = 4 + len(study.candidates) - 1
        chart.add_series({
            "name": "Cost vs CO2",
            "categories": f"='05_CANDIDATES'!$K$5:$K${last_row+1}",
            "values": f"='05_CANDIDATES'!$J$5:$J${last_row+1}",
            "marker": {"type": "circle", "size": 7},
        })
        chart.set_title({"name": "Candidate cost vs material CO2"})
        chart.set_x_axis({"name": "Material CO2 kg/t"})
        chart.set_y_axis({"name": "Variable cost INR/t"})
        chart.set_legend({"none": True})
        chart.set_size({"width": 620, "height": 330})
        sheet.insert_chart(4, 19, chart)


def _write_mass_balance(sheet, candidate, rows, formats) -> None:
    _setup(sheet, [(0, 0, 28), (1, 4, 20)])
    _title(sheet, "MASS BALANCE", formats, 4)
    sheet.write_row(3, 0, ["Item", "Formula / link", "BRIXTA reference", "Plant-calculated", "Unit"], formats["header"])
    sheet.write_row(4, 0, ["Target LC3 output", "01_MODEL_CONTROL!C5", None, None, "t/h"], formats["text"])
    sheet.write_formula(4, 2, "='01_MODEL_CONTROL'!B5", formats["reference"])
    sheet.write_formula(4, 3, "='01_MODEL_CONTROL'!C5", formats["formula"])
    row = 5
    for role in ("clinker", "calcined_clay", "limestone", "gypsum"):
        material_row = rows[role]
        sheet.write(row, 0, f"{role.replace('_', ' ').title()} flow", formats["label"])
        sheet.write(row, 1, f"Output × formulation % / 100", formats["text"])
        sheet.write_formula(row, 2, f"=$C$5*'03_MATERIALS'!E{material_row}/100", formats["reference"])
        sheet.write_formula(row, 3, f"=$D$5*'03_MATERIALS'!F{material_row}/100", formats["formula"])
        sheet.write(row, 4, "t/h", formats["text"])
        row += 1
    sheet.write(row, 0, "Raw-clay feed for onsite calcination", formats["label"])
    sheet.write(row, 1, "Calcined-clay flow / clay yield", formats["text"])
    sheet.write_formula(row, 2, "=C7/'01_MODEL_CONTROL'!B8", formats["reference"])
    sheet.write_formula(row, 3, "=D7/'01_MODEL_CONTROL'!C8", formats["formula"])
    sheet.write(row, 4, "t/h raw clay", formats["text"])
    sheet.write(row + 2, 0, "Mass-balance check", formats["label"])
    sheet.write_formula(row + 2, 3, "=SUM(D6:D9)-D5", formats["formula"])
    sheet.write(row + 2, 4, "t/h; must equal 0", formats["text"])
    sheet.conditional_format(row + 2, 3, row + 2, 3, {"type": "cell", "criteria": "not between", "minimum": -0.001, "maximum": 0.001, "format": formats["warning"]})


def _write_energy(sheet, candidate, formats) -> None:
    _setup(sheet, [(0, 0, 30), (1, 1, 25), (2, 3, 20), (4, 4, 35)])
    _title(sheet, "ENERGY, CAPACITY AND BOTTLENECK", formats, 4)
    sheet.write_row(3, 0, ["Metric", "Basis", "BRIXTA reference", "Plant input / result", "Unit / note"], formats["header"])
    rows = [
        ("Predicted sustainable output", "Route/equipment capacity screening", candidate.predicted_output_tph, candidate.predicted_output_tph, "t/h LC3"),
        ("Electricity", "Selected route + clay pathway", candidate.electricity_kwh_t, candidate.electricity_kwh_t, "kWh/t LC3"),
        ("Thermal demand", "Selected route + clay pathway", candidate.thermal_kcal_kg, candidate.thermal_kcal_kg, "kcal/kg LC3"),
        ("Route compatibility", "Stage and capacity screening", candidate.route_compatibility_score, candidate.route_compatibility_score, "0-100"),
        ("Route efficiency", "Capacity/energy/availability score", candidate.route_efficiency_score, candidate.route_efficiency_score, "0-100"),
        ("Robustness", "Low/typical/high + dosage stress", candidate.robustness_score, candidate.robustness_score, "0-100"),
        ("Retrofit complexity", "Required/recommended asset gaps", candidate.retrofit_complexity_score, candidate.retrofit_complexity_score, "0-100; lower is easier"),
    ]
    for row, item in enumerate(rows, 4):
        sheet.write(row, 0, item[0], formats["label"])
        sheet.write(row, 1, item[1], formats["text"])
        sheet.write(row, 2, item[2], formats["reference"])
        sheet.write(row, 3, item[3], formats["input"])
        sheet.write(row, 4, item[4], formats["text"])
    sheet.write(12, 0, "Bottleneck", formats["label"])
    sheet.write(12, 1, candidate.bottleneck_machine_name or "Unresolved", formats["warning"] if candidate.bottleneck_machine_name else formats["text"])
    sheet.write(14, 0, "Missing / retrofit assets", formats["section"])
    for row, gap in enumerate(candidate.missing_assets, 15):
        sheet.write(row, 0, gap.asset_name, formats["label"])
        sheet.write(row, 1, gap.requirement, formats["warning"] if gap.requirement == "required" else formats["text"])
        sheet.write(row, 2, gap.reference_capacity_tph, formats["reference"])
        sheet.write(row, 3, gap.reference_capex_inr_crore, formats["reference"])
        sheet.write(row, 4, gap.reason, formats["text"])


def _write_cost_co2(sheet, candidate, rows, formats) -> None:
    _setup(sheet, [(0, 0, 32), (1, 2, 20), (3, 3, 45)])
    _title(sheet, "COST AND CO2 MODEL", formats, 3)
    sheet.write_row(3, 0, ["Metric", "BRIXTA reference", "Plant-calculated", "Formula / basis"], formats["header"])
    sheet.write(4, 0, "Material cost", formats["label"])
    sheet.write(4, 1, candidate.material_cost_inr_t, formats["reference"])
    sheet.write_formula(4, 2, "=SUMPRODUCT('03_MATERIALS'!F5:F8,'03_MATERIALS'!I5:I8)/100", formats["formula"])
    sheet.write(4, 3, "SUMPRODUCT(plant formulation %, unit cost)/100", formats["text"])
    sheet.write(5, 0, "Electricity cost", formats["label"])
    sheet.write_formula(5, 1, "='07_ENERGY_CAPACITY'!C6*'01_MODEL_CONTROL'!B6", formats["reference"])
    sheet.write_formula(5, 2, "='07_ENERGY_CAPACITY'!D6*'01_MODEL_CONTROL'!C6", formats["formula"])
    sheet.write(5, 3, "kWh/t × INR/kWh", formats["text"])
    sheet.write(6, 0, "Thermal cost", formats["label"])
    sheet.write_formula(6, 1, "='07_ENERGY_CAPACITY'!C7*'01_MODEL_CONTROL'!B7/1000", formats["reference"])
    sheet.write_formula(6, 2, "='07_ENERGY_CAPACITY'!D7*'01_MODEL_CONTROL'!C7/1000", formats["formula"])
    sheet.write(6, 3, "kcal/kg × INR/million kcal ÷ 1000", formats["text"])
    sheet.write(7, 0, "Total variable cost", formats["label"])
    sheet.write(7, 1, candidate.total_variable_cost_inr_t, formats["reference"])
    sheet.write_formula(7, 2, "=SUM(C5:C7)", formats["formula"])
    sheet.write(7, 3, "Material + electricity + thermal", formats["text"])
    sheet.write(9, 0, "Material CO2", formats["label"])
    sheet.write(9, 1, candidate.material_co2_kg_t, formats["reference"])
    sheet.write_formula(9, 2, "=SUMPRODUCT('03_MATERIALS'!F5:F8,'03_MATERIALS'!J5:J8)/100", formats["formula"])
    sheet.write(9, 3, "SUMPRODUCT(plant formulation %, material CO2)/100", formats["text"])
    sheet.write(11, 0, "Commercial costs deliberately excluded", formats["section"])
    sheet.write(12, 0, "Fixed overhead, depreciation, financing, taxes, distribution and product-specific quality costs are not invented. Add plant data before commercial decisions.", formats["warning"])
    sheet.merge_range(12, 0, 13, 3, "Fixed overhead, depreciation, financing, taxes, distribution and product-specific quality costs are not invented. Add plant data before commercial decisions.", formats["warning"])


def _write_stress(sheet, candidate, formats) -> None:
    _setup(sheet, [(0, 0, 22), (1, 5, 14), (6, 10, 18), (11, 11, 45)])
    _title(sheet, "ROBUSTNESS / STRESS TEST", formats, 11)
    headers = ["Scenario", "Chemistry", "Clinker %", "Clay %", "Limestone %", "Gypsum %", "Output t/h", "Electricity", "Thermal", "Variable cost", "Material CO2", "Notes"]
    sheet.write_row(3, 0, headers, formats["header"])
    for row, scenario in enumerate(candidate.stress_tests, 4):
        sheet.write_row(row, 0, [scenario.scenario, scenario.chemistry_scenario, scenario.clinker_percent, scenario.calcined_clay_percent, scenario.limestone_percent, scenario.gypsum_percent, scenario.predicted_output_tph, scenario.electricity_kwh_t, scenario.thermal_kcal_kg, scenario.total_variable_cost_inr_t, scenario.material_co2_kg_t, "; ".join(scenario.notes[:3])], formats["number"])
        sheet.write(row, 0, scenario.scenario, formats["text"])
        sheet.write(row, 1, scenario.chemistry_scenario, formats["text"])
        sheet.write(row, 11, "; ".join(scenario.notes[:3]), formats["text"])


def _write_replacements(sheet, study, formats) -> None:
    _setup(sheet, [(0, 0, 7), (1, 1, 85), (2, 2, 22), (3, 3, 35)])
    _title(sheet, "DATA TO REPLACE BEFORE PLANT DECISION", formats, 3)
    sheet.write_row(3, 0, ["Priority", "Data item", "Status", "Action"], formats["header"])
    for row, item in enumerate(study.data_to_replace, 4):
        priority = "HIGH" if row < 10 else "MEDIUM"
        sheet.write(row, 0, priority, formats["warning"] if priority == "HIGH" else formats["text"])
        sheet.write(row, 1, item, formats["text"])
        sheet.write(row, 2, "REFERENCE / MISSING", formats["reference"])
        sheet.write(row, 3, "Replace in the relevant blue workbook input cell or plant data table", formats["text"])


def _write_trace(sheet, candidate, formats) -> None:
    _setup(sheet, [(0, 0, 8), (1, 2, 24), (3, 3, 65), (4, 4, 55), (5, 6, 20)])
    _title(sheet, "CALCULATION TRACE", formats, 6)
    sheet.write_row(3, 0, ["Seq", "Section", "Operation", "Formula", "Inputs", "Result", "Unit"], formats["header"])
    for row, step in enumerate(candidate.calculation_trace, 4):
        sheet.write_row(row, 0, [step.sequence, step.section, step.operation, step.formula, str(step.inputs), step.result, step.unit], formats["text"])


def _write_dashboard(sheet, candidate, formats) -> None:
    _setup(sheet, [(0, 7, 18)])
    _title(sheet, "LC3 RETROFIT DASHBOARD", formats, 7)
    kpis = [
        ("Plant LC3 output", "='07_ENERGY_CAPACITY'!D5", "t/h"),
        ("Plant variable cost", "='08_COST_CO2'!C8", "INR/t"),
        ("Plant material CO2", "='08_COST_CO2'!C10", "kg/t"),
        ("Plant electricity", "='07_ENERGY_CAPACITY'!D6", "kWh/t"),
        ("Plant thermal demand", "='07_ENERGY_CAPACITY'!D7", "kcal/kg"),
        ("Formulation total", "='03_MATERIALS'!F9", "%"),
    ]
    for index, (label, formula, unit) in enumerate(kpis):
        row = 3 + (index // 3) * 4
        col = (index % 3) * 2
        sheet.merge_range(row, col, row, col + 1, label, formats["section"])
        sheet.merge_range(row + 1, col, row + 2, col + 1, formula, formats["kpi"])
        sheet.write(row + 3, col, unit, formats["small"])
    sheet.merge_range(12, 0, 12, 7, "SELECTED BRIXTA DESIGN", formats["section"])
    sheet.write(13, 0, candidate.name, formats["kpi"])
    sheet.merge_range(13, 0, 14, 7, candidate.name, formats["kpi"])
    sheet.merge_range(16, 0, 16, 7, "BOTTLENECK / RETROFIT ACTION", formats["section"])
    bottleneck = candidate.bottleneck_machine_name or "No route bottleneck resolved"
    actions = "; ".join(item.asset_name for item in candidate.missing_assets) or "Use existing plant route"
    sheet.merge_range(17, 0, 18, 7, f"Bottleneck: {bottleneck}\nRetrofit assets: {actions}", formats["warning"])


def _electricity_tariff(study: RetrofitStudyResult) -> float:
    for item in study.assumptions:
        if item.key == "electricity_tariff":
            try:
                return float(item.value)
            except ValueError:
                pass
    return 8.5


def _thermal_tariff(study: RetrofitStudyResult) -> float:
    for item in study.assumptions:
        if item.key == "thermal_tariff":
            try:
                return float(item.value)
            except ValueError:
                pass
    return 900.0
