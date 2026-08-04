export type ConfidenceBand = "low" | "medium" | "high";
export type RiskRating = "low" | "medium" | "high" | "critical";
export type DecisionStatus = "draft" | "proceed" | "hold" | "reject";

export type EngineeringProject = {
  project_name: string;
  plant_name: string;
  engineer: string;
  product_target: string;
  revision: string;
  bis_constraints: string[];
  customer_constraints: string[];
  pilot_quantity_t: number;
  pilot_rate_fraction: number;
  monitoring_hours: number;
  notes: string | null;
};

export type EngineeringPrediction = {
  code: string;
  category: string;
  label: string;
  prediction: number | string | null;
  unit: string | null;
  confidence_percent: number;
  confidence_band: ConfidenceBand;
  reason: string;
  required_validation: string[];
  source_basis: string[];
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
  actions: EngineeringAction[];
  expected_results: EngineeringPrediction[];
  confidence_percent: number;
  reasons: string[];
  required_validation: string[];
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
  learning_summary: string;
};
