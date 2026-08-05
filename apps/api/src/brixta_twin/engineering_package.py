from __future__ import annotations

import csv
import hashlib
import io
import json
from zipfile import ZIP_DEFLATED, ZipFile

from .engineering_decision import EngineeringCase, EngineeringValidationRecord
from .engineering_workbook import compile_engineering_workbook
from .models import RetrofitCandidate, RetrofitStudyResult
from .storage import Repository


def _csv_bytes(headers: list[str], rows: list[list[object]]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def compile_engineering_package(
    repository: Repository,
    case: EngineeringCase,
    study: RetrofitStudyResult,
    candidate: RetrofitCandidate,
    validations: list[EngineeringValidationRecord],
) -> bytes:
    if case.trust_assessment is None or case.decision_gate is None:
        raise ValueError("Engineering package requires a version 1.0.0 trust assessment and decision gate")
    workbook = compile_engineering_workbook(
        repository,
        case,
        study,
        candidate,
        validations,
    )
    workbook_name = f"BRIXTA_Engineering_Decision_{case.case_id}_{case.project.revision}.xlsx"
    manifest = {
        "package_type": "BRIXTA digital engineering package",
        "package_version": "1.0.0",
        "case_id": case.case_id,
        "revision": case.project.revision,
        "calculation_version": case.calculation_version,
        "catalog_version": case.trust_assessment.catalog_version,
        "created_at": case.created_at.isoformat(),
        "plant": case.project.plant_name,
        "product": case.project.product_target,
        "decision_gate": case.decision_gate.model_dump(mode="json"),
        "workbook": workbook_name,
        "workbook_sha256": hashlib.sha256(workbook).hexdigest(),
        "validation_records": len(validations),
        "files": [
            workbook_name,
            "engineering_case.json",
            "manifest.json",
            "evidence_register.csv",
            "risk_register.csv",
            "validation_plan.csv",
            "review_committee.csv",
            "scenario_register.csv",
            "recommendations.csv",
            "operator_checklist.txt",
            "rollback_procedure.txt",
            "README.txt",
        ],
    }

    evidence_csv = _csv_bytes(
        [
            "evidence_id",
            "subject",
            "evidence_class",
            "title",
            "source_uri",
            "quality_score_percent",
            "status",
            "applies_to",
            "limitations",
        ],
        [
            [
                item.evidence_id,
                item.subject,
                item.evidence_class,
                item.title,
                item.source_uri or "",
                item.quality_score_percent,
                item.status,
                " | ".join(item.applies_to),
                " | ".join(item.limitations),
            ]
            for item in case.evidence_register
        ],
    )
    risk_csv = _csv_bytes(
        [
            "risk_id",
            "discipline",
            "failure_mode",
            "cause",
            "consequence",
            "severity",
            "likelihood",
            "detectability",
            "rpn",
            "mitigation",
            "rollback_trigger",
        ],
        [
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
            ]
            for item in case.risk_register
        ],
    )
    validation_csv = _csv_bytes(
        [
            "validation_id",
            "category",
            "measurement",
            "purpose",
            "tolerance",
            "frequency_or_sample",
            "owner",
            "availability",
            "blocking",
            "evidence_generated",
        ],
        [
            [
                item.validation_id,
                item.category,
                item.measurement,
                item.purpose,
                item.acceptable_tolerance,
                item.frequency_or_sample,
                item.owner,
                item.availability,
                item.blocking,
                item.evidence_generated,
            ]
            for item in case.validation_plan
        ],
    )
    committee_csv = _csv_bytes(
        [
            "discipline",
            "mandatory",
            "status",
            "findings",
            "blocking_issues",
            "approval_required_from",
            "evidence_reviewed",
        ],
        [
            [
                item.discipline,
                item.mandatory,
                item.status,
                " | ".join(item.findings),
                " | ".join(item.blocking_issues),
                item.approval_required_from,
                " | ".join(item.evidence_reviewed),
            ]
            for item in case.review_committee
        ],
    )
    scenarios_csv = _csv_bytes(
        [
            "rank",
            "scenario_id",
            "name",
            "why_it_exists",
            "probability_of_success_percent",
            "risk_level",
            "expected_benefit",
            "expected_downside",
            "business_impact",
            "engineering_impact",
            "required_validation",
            "recommended_for_pilot",
        ],
        [
            [
                item.rank,
                item.scenario_id,
                item.name,
                item.why_it_exists,
                item.probability_of_success_percent,
                item.risk_level,
                " | ".join(item.expected_benefit),
                " | ".join(item.expected_downside),
                item.business_impact,
                item.engineering_impact,
                " | ".join(item.required_validation),
                item.recommended_for_pilot,
            ]
            for item in case.scenario_assessments
        ],
    )
    recommendations_csv = _csv_bytes(
        [
            "recommendation_id",
            "title",
            "discipline",
            "priority",
            "authority",
            "confidence_percent",
            "risk",
            "actions",
            "required_validation",
            "failure_modes",
            "rollback_criteria",
            "approval_requirements",
            "proceed_condition",
        ],
        [
            [
                item.recommendation_id,
                item.title,
                item.discipline,
                item.priority,
                item.recommendation_authority,
                item.confidence_percent,
                item.risk,
                " | ".join(
                    f"{action.parameter}: {action.current_value} -> {action.recommended_value} {action.unit or ''}".strip()
                    for action in item.actions
                ),
                " | ".join(item.required_validation),
                " | ".join(item.potential_failure_modes),
                " | ".join(item.rollback_criteria),
                " | ".join(item.approval_requirements),
                item.proceed_condition,
            ]
            for item in case.recommendations
        ],
    )

    operator_checklist = "\n".join(
        [
            "BRIXTA OPERATOR CHECKLIST",
            f"Case: {case.case_id}",
            f"Revision: {case.project.revision}",
            "",
            "PRE-START",
            "- Confirm current approved recipe and rollback recipe are available.",
            "- Confirm all interlocks, alarms and environmental monitoring are operational.",
            "- Confirm feeders, conveyors, silos, mills, fans and sampling points are available.",
            "- Confirm laboratory and shift teams understand the sampling and hold plan.",
            "",
            "DURING PILOT",
            *[f"- {item}" for item in case.pilot_plan.monitoring_plan],
            "",
            "GO / NO-GO",
            *[f"- {item}" for item in case.pilot_plan.go_no_go_criteria],
            "",
            "The operator must stop or hold the trial when any approved rollback trigger is reached.",
        ]
    ).encode("utf-8")
    rollback = "\n".join(
        [
            "BRIXTA ROLLBACK PROCEDURE",
            f"Case: {case.case_id}",
            f"Decision gate: {case.decision_gate.decision}",
            "",
            "TRIGGERS",
            *[f"- {item.rollback_trigger}" for item in case.risk_register],
            "",
            "CONTROLLED RESPONSE",
            "1. Stop increasing the changed parameter or production rate.",
            "2. Return recipe, feed, fuel and machine controls to the last approved baseline.",
            "3. Segregate and hold all affected material.",
            "4. Record time, readings, operator actions, samples and equipment state.",
            "5. Obtain Process, Quality and Plant Head disposition before restart.",
        ]
    ).encode("utf-8")
    readme = (
        "BRIXTA DIGITAL ENGINEERING PACKAGE\n\n"
        "This package contains an auditable engineering case, workbook, evidence register, "
        "risk register, validation plan, multidisciplinary review, scenario register, operator "
        "checklist and rollback procedure.\n\n"
        f"Decision gate: {case.decision_gate.decision}\n"
        f"Production change authorised: {case.decision_gate.production_change_authorised}\n"
        f"Pilot authorised: {case.decision_gate.pilot_authorised}\n\n"
        "Replace reference values only through controlled revision. Preserve the case ID, revision, "
        "calculation version and source evidence. Do not treat the workbook as product certification.\n"
    ).encode("utf-8")

    output = io.BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr(workbook_name, workbook)
        archive.writestr(
            "engineering_case.json",
            case.model_dump_json(indent=2).encode("utf-8"),
        )
        archive.writestr(
            "manifest.json",
            json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8"),
        )
        archive.writestr("evidence_register.csv", evidence_csv)
        archive.writestr("risk_register.csv", risk_csv)
        archive.writestr("validation_plan.csv", validation_csv)
        archive.writestr("review_committee.csv", committee_csv)
        archive.writestr("scenario_register.csv", scenarios_csv)
        archive.writestr("recommendations.csv", recommendations_csv)
        archive.writestr("operator_checklist.txt", operator_checklist)
        archive.writestr("rollback_procedure.txt", rollback)
        archive.writestr("README.txt", readme)
    return output.getvalue()
