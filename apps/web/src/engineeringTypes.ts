export type ConfidenceBand = "low" | "medium" | "high";
export type RiskRating = "low" | "medium" | "high" | "critical";
export type DecisionStatus = "draft" | "proceed" | "hold" | "reject";
export type ReviewStatus = "pass" | "conditional" | "hold" | "fail" | "not_reviewed";
export type GateDecision = "proceed_to_pilot" | "hold_for_validation" | "reject" | "advisory_only";
export type ValidationAvailability = "available" | "partial" | "unavailable" | "not_confirmed";

export type ProductDefinition = {
  product_id: string;
  name: string;
  family: string;
  description: string;
  required_material_roles: string[];
  optional_material_roles: string[];
  required_process_capabilities: string[];
  required_validation: string[];
  default_quality_standard_ids: string[];
};

export type EngineeringCatalog = {
  catalog_version: string;
  product_definitions: ProductDefinition[];
  discipline_reviews: Array<{
    discipline: string;
    mandatory: boolean;
    questions: string[];
  }>;
  evidence_classes: Array<{
    evidence_class: string;
    base_quality: number;
  }>;
  decision_policy: {
    minimum_pilot_confidence_percent: number;
    minimum_evidence_coverage_percent: number;
    maximum_critical_unknowns: number;
    maximum_high_risks: number;
    require_validation_plan: boolean;
    require_all_mandatory_reviews: boolean;
    production_change_requires_approved_pilot: boolean;
  };
};

export type EngineeringProject = {
  project_name: string;
  plant_name: string;
  engineer: string;
  product_target: string;
  product_definition_id: string | null;
  revision: string;
  quality_standard_ids: string[];
  bis_constraints: string[];
  customer_constraints: string[];
  validation_resources: string[];
  pilot_quantity_t: number;
  pilot_rate_fraction: number;
  monitoring_hours: number;
  notes: string | null;
};

export type PredictionInterval = {
  low: number | null;
  central: number | string | null;
  high: number | null;
  unit: string | null;
  basis: string;
};

export type EngineeringPrediction = {
  code: string;
  category: string;
  label: string;
  prediction: number | string | null;
  raw_prediction: number | string | null;
  calibration_factor: number;
  unit: string | null;
  confidence_percent: number;
  confidence_band: ConfidenceBand;
  prediction_interval: PredictionInterval | null;
  reason: string;
  method: string;
  critical_assumptions: string[];
  sensitive_variables: string[];
  unknown_inputs: string[];
  required_validation: string[];
  source_basis: string[];
  evidence_ids: string[];
  risk: RiskRating;
};

export type EngineeringAction = {
  parameter: string;
  current_value: number | string | null;
  recommended_value: number | string | null;
  unit: string | null;
  change: number | string | null;
  rationale: string;
};

export type EngineeringRecommendation = {
  recommendation_id: string;
  title: string;
  discipline: string;
  priority: "P1" | "P2" | "P3";
  recommendation_authority: "advisory_only" | "pilot_candidate" | "production_authorised";
  actions: EngineeringAction[];
  expected_results: EngineeringPrediction[];
  confidence_percent: number;
  reasons: string[];
  required_validation: string[];
  potential_failure_modes: string[];
  rollback_criteria: string[];
  approval_requirements: string[];
  risk: RiskRating;
  proceed_condition: string;
};

export type PilotSetting = {
  area: string;
  parameter: string;
  target: number | string | null;
  unit: string | null;
  basis: string;
  validation: string;
};

export type PilotBatchPlan = {
  pilot_quantity_t: number;
  pilot_rate_tph: number | null;
  formulation: Array<Record<string, number | string>>;
  machine_settings: PilotSetting[];
  kiln_settings: PilotSetting[];
  mill_settings: PilotSetting[];
  sampling_plan: string[];
  required_lab_tests: string[];
  go_no_go_criteria: string[];
  monitoring_plan: string[];
};

export type EvidenceRecord = {
  evidence_id: string;
  subject: string;
  evidence_class: string;
  title: string;
  source_uri: string | null;
  revision_or_date: string | null;
  applies_to: string[];
  quality_score_percent: number;
  status: "known" | "assumed" | "uncertain" | "unknown";
  limitations: string[];
};

export type CriticalAssumption = {
  assumption_id: string;
  subject: string;
  statement: string;
  basis: string;
  consequence_if_wrong: string;
  sensitivity: "low" | "medium" | "high" | "critical";
  replacement_data: string;
};

export type UnknownInput = {
  input_id: string;
  category: string;
  item: string;
  consequence: string;
  criticality: "low" | "medium" | "high" | "critical";
  can_use_reference_default: boolean;
  validation_or_replacement: string;
};

export type SensitivityDriver = {
  variable: string;
  direction: string;
  importance_percent: number;
  rationale: string;
  recommended_test: string;
};

export type ValidationRequirement = {
  validation_id: string;
  category: string;
  measurement: string;
  purpose: string;
  acceptable_tolerance: string;
  frequency_or_sample: string;
  owner: string;
  availability: ValidationAvailability;
  blocking: boolean;
  evidence_generated: string;
};

export type FailureMode = {
  failure_mode_id: string;
  discipline: string;
  failure_mode: string;
  cause: string;
  consequence: string;
  severity: number;
  likelihood: number;
  detectability: number;
  risk_priority_number: number;
  mitigation: string;
  rollback_trigger: string;
};

export type DisciplineReview = {
  discipline: string;
  mandatory: boolean;
  status: ReviewStatus;
  findings: string[];
  blocking_issues: string[];
  evidence_reviewed: string[];
  approval_required_from: string;
};

export type ScenarioAssessment = {
  scenario_id: string;
  name: string;
  why_it_exists: string;
  expected_benefit: string[];
  expected_downside: string[];
  probability_of_success_percent: number;
  required_validation: string[];
  business_impact: string;
  engineering_impact: string;
  risk_level: RiskRating;
  rank: number;
  recommended_for_pilot: boolean;
};

export type DecisionGate = {
  decision: GateDecision;
  production_change_authorised: boolean;
  pilot_authorised: boolean;
  reason: string;
  blocking_conditions: string[];
  conditions_to_advance: string[];
  rollback_required: boolean;
  approval_requirements: string[];
};

export type TrustQuestionAnswer = {
  question: string;
  answer: string;
  status: "adequate" | "partial" | "inadequate";
  supporting_ids: string[];
};

export type TrustAssessment = {
  assessment_id: string;
  catalog_version: string;
  product_definition_id: string | null;
  evidence_coverage_percent: number;
  data_completeness_percent: number;
  traceability_percent: number;
  validation_readiness_percent: number;
  overall_confidence_percent: number;
  confidence_band: ConfidenceBand;
  critical_assumptions: CriticalAssumption[];
  unknown_inputs: UnknownInput[];
  sensitive_variables: SensitivityDriver[];
  evidence_register: EvidenceRecord[];
  validation_plan: ValidationRequirement[];
  risk_register: FailureMode[];
  review_committee: DisciplineReview[];
  scenario_assessments: ScenarioAssessment[];
  trust_questions: TrustQuestionAnswer[];
  decision_gate: DecisionGate;
};

export type EngineeringCase = {
  case_id: string;
  created_at: string;
  calculation_version: string;
  status: DecisionStatus;
  project: EngineeringProject;
  study_id: string;
  candidate_id: string;
  baseline_blend_id: string;
  route_id: string;
  cost_book_id: string | null;
  risk_rating: RiskRating;
  confidence_percent: number;
  confidence_band: ConfidenceBand;
  executive_summary: string;
  predictions: EngineeringPrediction[];
  recommendations: EngineeringRecommendation[];
  pilot_plan: PilotBatchPlan;
  assumptions: Array<Record<string, string>>;
  missing_data: Array<{ category: string; item: string; reason: string }>;
  calculation_trace: Array<Record<string, string | number | null>>;
  calibration_profile: Record<string, number>;
  calibration_sample_count: number;
  trust_assessment: TrustAssessment;
  decision_gate: DecisionGate;
  evidence_register: EvidenceRecord[];
  risk_register: FailureMode[];
  review_committee: DisciplineReview[];
  validation_plan: ValidationRequirement[];
  scenario_assessments: ScenarioAssessment[];
  unknown_inputs: UnknownInput[];
};

export type PredictionError = {
  metric: string;
  predicted: number | null;
  actual: number | null;
  absolute_error: number | null;
  percent_error: number | null;
  recalibration_factor: number | null;
};

export type EngineeringLearningResult = {
  case_id: string;
  validation_id: string;
  prediction_errors: PredictionError[];
  mean_absolute_percent_error: number | null;
  confidence_before_percent: number;
  confidence_after_percent: number;
  calibration_profile: Record<string, number>;
  calibration_sample_count: number;
  accepted_for_calibration: boolean;
  calibration_rejection_reason: string | null;
  learning_summary: string;
};
