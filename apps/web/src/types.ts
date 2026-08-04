export type Evidence = {
  evidence_class: string;
  source_title: string;
  source_uri?: string | null;
  page?: string | null;
  note?: string | null;
};

export type Chemistry = {
  cao: number | null;
  sio2: number | null;
  al2o3: number | null;
  fe2o3: number | null;
  mgo: number | null;
  so3: number | null;
  na2o: number | null;
  k2o: number | null;
  loi: number | null;
};

export type Material = {
  material_id: string;
  version: number;
  lineage_id?: string | null;
  archived: boolean;
  archived_at?: string | null;
  created_at: string;
  name: string;
  material_type: string;
  functional_role: string;
  custom_subtype?: string | null;
  location?: string | null;
  processing_state: string;
  applicable_blend_classes: string[];
  chemistry: Chemistry;
  chemistry_min?: Chemistry | null;
  chemistry_max?: Chemistry | null;
  moisture_percent?: number | null;
  grindability_factor?: number | null;
  fuel_ash_percent?: number | null;
  fuel_calorific_value_kcal_kg?: number | null;
  fuel_ash_chemistry?: Chemistry | null;
  cost_inr_per_t: number | null;
  co2_kg_per_t: number | null;
  notes?: string | null;
  data_gaps: string[];
  evidence: Evidence[];
};

export type BlendComponent = {
  component_type: "material" | "blend";
  material_id?: string | null;
  blend_id?: string | null;
  percentage: number;
};

export type Blend = {
  blend_id: string;
  version: number;
  lineage_id?: string | null;
  archived: boolean;
  archived_at?: string | null;
  created_at: string;
  name: string;
  blend_class: string;
  family: string;
  objective: string;
  applicable_standard?: string | null;
  status: string;
  components: BlendComponent[];
  evidence: Evidence[];
};

export type ResolvedBlendComponent = {
  material_id: string;
  material_name: string;
  material_type: string;
  percentage: number;
  evidence_class: string;
  material_version: number;
  production_stream: string;
  root_component_type: "material" | "blend";
  root_component_id: string | null;
  root_component_name: string | null;
  root_blend_class: string | null;
  hierarchy_path: string[];
};

export type BlendPreview = {
  blend_name: string;
  blend_class: string;
  direct_total_percentage: number;
  flattened_total_percentage: number;
  flattened_components: ResolvedBlendComponent[];
  chemistry: Chemistry;
  chemistry_scenario: "low" | "typical" | "high";
  chemistry_complete: boolean;
  unknown_chemistry_fields: string[];
  material_cost_inr_t: number | null;
  estimated_co2_kg_t: number | null;
  warnings: string[];
};

export type Machine = {
  machine_id: string;
  version: number;
  lineage_id?: string | null;
  archived: boolean;
  archived_at?: string | null;
  created_at: string;
  name: string;
  machine_kind: string;
  process_stage: string;
  rated_capacity_tph: number;
  minimum_stable_tph: number;
  availability: number;
  specific_electricity_kwh_t: number;
  specific_heat_kcal_kg: number;
  capex_inr_crore: number;
  technology_readiness_level: number;
  maximum_stable_tph?: number | null;
  design_blaine_m2_kg?: number | null;
  maximum_feed_moisture_percent?: number | null;
  minimum_temperature_c?: number | null;
  maximum_temperature_c?: number | null;
  minimum_oxygen_percent?: number | null;
  maximum_oxygen_percent?: number | null;
  maximum_free_lime_percent?: number | null;
  evidence: Evidence[];
};

export type Route = {
  route_id: string;
  version: number;
  lineage_id?: string | null;
  archived: boolean;
  archived_at?: string | null;
  created_at: string;
  name: string;
  route_kind: string;
  nodes: {
    node_id: string;
    machine_id: string;
    label: string;
    position_x: number;
    position_y: number;
  }[];
  edges: {
    edge_id: string;
    source: string;
    target: string;
    stream_type: string;
  }[];
};

export type RouteGraphAnalysis = {
  acyclic: boolean;
  topological_order: string[];
  source_nodes: string[];
  sink_nodes: string[];
  critical_path_node_ids: string[];
  critical_path_labels: string[];
  graph_depth: number;
  critical_path_hours_per_t_output: number | null;
  algorithm: string;
  warnings: string[];
};

export type RouteAnalysis = {
  route_id: string;
  route_name: string;
  route_kind: string;
  description: string;
  flow_summary: string;
  compatible: boolean;
  compatibility_score: number;
  efficiency_score: number;
  predicted_output_tph: number | null;
  bottleneck_machine_name: string | null;
  electricity_kwh_t_output: number | null;
  thermal_kcal_kg_output: number | null;
  weighted_availability: number | null;
  mean_technology_readiness_level: number | null;
  graph: RouteGraphAnalysis | null;
  pareto_efficient: boolean;
  distance_from_selected: number | null;
  improves_selected: boolean;
  improvement_reasons: string[];
  required_stages: string[];
  present_stages: string[];
  missing_stages: string[];
  extra_stages: string[];
  reasons: string[];
};

export type RouteRecommendationSet = {
  blend_id: string;
  target_output_tph: number;
  selected_route_id: string | null;
  selected: RouteAnalysis | null;
  nearest_more_efficient_route_id: string | null;
  algorithm: string;
  recommendations: RouteAnalysis[];
};

export type MaterialCostEntry = {
  material_id: string;
  purchased_delivered_cost_inr_t: number | null;
  internal_feed_cost_inr_t: number | null;
  evidence_class: string;
  note?: string | null;
};

export type CostBook = {
  cost_book_id: string;
  version: number;
  lineage_id?: string | null;
  archived: boolean;
  archived_at?: string | null;
  created_at: string;
  name: string;
  effective_date?: string | null;
  currency: string;
  electricity_inr_kwh: number | null;
  thermal_fuel_inr_mkcal: number | null;
  packing_inr_t: number | null;
  labour_inr_t: number | null;
  maintenance_inr_t: number | null;
  other_variable_inr_t: number | null;
  factory_overhead_inr_t: number | null;
  outbound_logistics_inr_t: number | null;
  clinker_labour_inr_t: number | null;
  clinker_maintenance_inr_t: number | null;
  clinker_other_variable_inr_t: number | null;
  clinker_factory_overhead_inr_t: number | null;
  material_costs: MaterialCostEntry[];
  evidence: Evidence[];
  notes?: string | null;
};


export type ClinkerFamily =
  | "moduli_only"
  | "general_purpose"
  | "high_early_strength"
  | "durable_belite"
  | "sulfate_resistant"
  | "low_carbon_belite"
  | "lc3_compatible"
  | "custom";

export type CalculationTraceStep = {
  sequence: number;
  section: string;
  operation: string;
  formula: string;
  inputs: Record<string, number | string | null>;
  result: number | string | null;
  unit: string | null;
  route_node_id: string | null;
};

export type ClinkerMineralogy = {
  method: string;
  calculation_basis: string;
  c3s_percent: number | null;
  c2s_percent: number | null;
  c3a_percent: number | null;
  c4af_percent: number | null;
  calcium_aluminoferrite_ss_percent: number | null;
  phase_total_percent: number | null;
  unallocated_percent: number | null;
  alumina_ferric_ratio: number | null;
  estimated_uncertainty_1sigma: Record<string, number>;
  warnings: string[];
};

export type ClinkerBehaviour = {
  method: string;
  liquid_phase_1450_percent: number | null;
  burnability_score: number | null;
  burnability_class: "good" | "moderate" | "difficult" | "unknown";
  free_lime_risk: "low" | "medium" | "high" | "unknown";
  expected_fuel_demand: "low" | "medium" | "high" | "unknown";
  expected_early_strength: "low" | "medium" | "high" | "unknown";
  expected_later_strength: "low" | "medium" | "high" | "unknown";
  expected_sulfate_resistance: "low" | "moderate" | "high" | "unknown";
  expected_heat_release: "low" | "moderate" | "high" | "unknown";
  predicted_family: ClinkerFamily | null;
  family_distance: number | null;
  rationale: string[];
};

export type ValidationMessage = {
  severity: "block" | "warning" | "info";
  code: string;
  message: string;
};

export type MachineRunMetric = {
  node_id: string;
  process_stream: string;
  machine_id: string;
  machine_name: string;
  process_stage: string;
  throughput_factor_t_stage_per_t_output: number;
  actual_throughput_tph: number;
  effective_capacity_tph: number;
  output_equivalent_capacity_tph: number | null;
  target_throughput_tph: number;
  target_load_percent: number;
  load_percent: number;
  electricity_kwh_t_output: number;
  thermal_kcal_kg_output: number;
};

export type MaterialRunMetric = {
  material_id: string;
  production_stream: string;
  material_name: string;
  material_type: string;
  percentage: number;
  tonnes_per_t_output: number | null;
  tonnes_per_hour: number;
  tonnes_per_run: number;
  applied_unit_cost_inr_t: number | null;
  cost_basis: string;
  cost_inr_t_output: number | null;
  co2_kg_t_output: number | null;
  evidence_class: string;
};

export type Result = {
  run_id: string;
  created_at: string;
  calculation_version: string;
  run_status: "completed" | "blocked";
  output_product: string;
  request: {
    blend_id: string;
    route_id: string;
    cost_book_id?: string | null;
    target_output_tph: number;
    duration_hours: number;
    electricity_inr_kwh: number;
    thermal_fuel_inr_mkcal: number;
    raw_meal_to_clinker_yield: number;
    auto_mass_conversion: boolean;
    chemistry_scenario: "low" | "typical" | "high";
    target_blaine_m2_kg?: number | null;
    fuel_material_id?: string | null;
    fuel_rate_kg_t_clinker?: number | null;
    kiln_feed_moisture_percent?: number | null;
    kiln_oxygen_percent?: number | null;
    kiln_temperature_c?: number | null;
    clinker_free_lime_percent?: number | null;
    quality_measurements?: QualityMeasurements | null;
  };
  blend_snapshot: Blend | null;
  route_snapshot: Route | null;
  cost_book_snapshot: CostBook | null;
  material_snapshots: Material[];
  machine_snapshots: Machine[];
  chemistry: Chemistry;
  chemistry_scenario: "low" | "typical" | "high";
  route_analysis: RouteAnalysis | null;
  quality_gate: QualityGate | null;
  derived_raw_meal_to_clinker_yield: number | null;
  fuel_ash_contribution_kg_t_clinker: number | null;
  fuel_ash_adjusted_chemistry: Chemistry | null;
  clinker_chemistry: Chemistry | null;
  clinker_lsf: number | null;
  clinker_silica_modulus: number | null;
  clinker_alumina_modulus: number | null;
  clinker_mineralogy: ClinkerMineralogy | null;
  clinker_behaviour: ClinkerBehaviour | null;
  calculation_trace: CalculationTraceStep[];
  grinding_capacity_factor: number;
  grinding_energy_factor: number;
  achievable_output_tph: number;
  total_output_tonnes: number;
  material_input_t_per_t_output: number | null;
  total_material_input_tph: number | null;
  total_material_input_tonnes: number | null;
  bottleneck_tph: number;
  bottleneck_machine_id: string | null;
  bottleneck_machine_name: string | null;
  electricity_kwh_t: number;
  thermal_kcal_kg: number;
  applied_electricity_inr_kwh: number | null;
  electricity_tariff_source: string;
  applied_thermal_fuel_inr_mkcal: number | null;
  thermal_tariff_source: string;
  material_cost_inr_t: number | null;
  energy_cost_inr_t: number;
  direct_model_cost_inr_t: number | null;
  estimated_co2_kg_t: number | null;
  lsf: number | null;
  silica_modulus: number | null;
  alumina_modulus: number | null;
  resolved_components: ResolvedBlendComponent[];
  material_metrics: MaterialRunMetric[];
  machine_metrics: MachineRunMetric[];
  cost_breakdown: {
    materials_inr_t: number | null;
    electricity_inr_t: number;
    thermal_inr_t: number;
    energy_inr_t: number;
    direct_model_cost_inr_t: number | null;
    packing_inr_t: number | null;
    labour_inr_t: number | null;
    maintenance_inr_t: number | null;
    other_variable_inr_t: number | null;
    plant_cash_cost_inr_t: number | null;
    factory_overhead_inr_t: number | null;
    outbound_logistics_inr_t: number | null;
    full_cost_inr_t: number | null;
    cost_book_name: string | null;
    operating_cost_basis: string;
    included_costs: string[];
    excluded_costs: string[];
  } | null;
  energy_breakdown: {
    electricity_kwh_t: number;
    thermal_kcal_kg: number;
    total_electricity_mwh: number;
    total_thermal_gcal: number;
  } | null;
  carbon_breakdown: {
    materials_kg_co2_t: number | null;
    total_materials_tonnes: number;
    total_materials_kg_co2: number | null;
    exclusions: string[];
  } | null;
  validation: ValidationMessage[];
  warnings: string[];
  information: string[];
  assumptions: { key: string; value: string; basis: string }[];
  evidence_references: Evidence[];
  events: {
    sequence: number;
    elapsed_seconds: number;
    level: string;
    component: string;
    message: string;
  }[];
};

export type QualityMeasurements = {
  blaine_m2_kg?: number | null;
  initial_setting_minutes?: number | null;
  final_setting_minutes?: number | null;
  le_chatelier_mm?: number | null;
  autoclave_expansion_percent?: number | null;
  strength_3d_mpa?: number | null;
  strength_7d_mpa?: number | null;
  strength_28d_mpa?: number | null;
};

export type QualityGate = {
  standard: string;
  status: "pass" | "fail" | "review";
  checks: { metric: string; measured: number | null; requirement: string; status: "pass" | "fail" | "not_tested" }[];
  note: string;
};

export type RawMixResult = {
  feasible: boolean;
  suggestions: { material_id: string; material_name: string; percentage: number }[];
  chemistry: Chemistry;
  clinker_chemistry: Chemistry | null;
  mineralogy: ClinkerMineralogy | null;
  behaviour: ClinkerBehaviour | null;
  clinker_family: ClinkerFamily;
  lsf: number | null;
  silica_modulus: number | null;
  alumina_modulus: number | null;
  estimated_clinker_yield: number | null;
  objective_error: number;
  calculation_trace: CalculationTraceStep[];
  warnings: string[];
};

export type Calibration = {
  calibration_id: string;
  run_id: string;
  created_at: string;
  actual_output_tph: number | null;
  actual_electricity_kwh_t: number | null;
  actual_thermal_kcal_kg: number | null;
  actual_direct_cost_inr_t: number | null;
  actual_co2_kg_t: number | null;
  source_title: string;
  source_uri?: string | null;
  note?: string | null;
  errors: { metric: string; simulated: number | null; actual: number | null; absolute_error: number | null; percent_error: number | null }[];
};

export type RetrofitReference = {
  component_type: "material" | "blend";
  reference_id: string;
};

export type PercentageBounds = {
  minimum_percent: number;
  maximum_percent: number;
};

export type RetrofitObjectiveWeights = {
  cost: number;
  co2: number;
  output: number;
  electricity: number;
  thermal: number;
  robustness: number;
  retrofit_complexity: number;
  clinker_factor: number;
};

export type RetrofitComponentShare = {
  role: "clinker" | "calcined_clay" | "limestone" | "gypsum";
  component_type: "material" | "blend";
  reference_id: string;
  name: string;
  percentage: number;
  minimum_percent: number;
  maximum_percent: number;
  source_status: string;
};

export type RetrofitAssetGap = {
  asset_code: string;
  asset_name: string;
  requirement: "required" | "recommended" | "optional";
  reason: string;
  reference_capacity_tph: number | null;
  reference_capex_inr_crore: number | null;
  assumption_basis: string;
};

export type RetrofitStressScenario = {
  scenario: string;
  chemistry_scenario: "low" | "typical" | "high";
  clinker_percent: number;
  calcined_clay_percent: number;
  limestone_percent: number;
  gypsum_percent: number;
  predicted_output_tph: number | null;
  electricity_kwh_t: number | null;
  thermal_kcal_kg: number | null;
  material_cost_inr_t: number | null;
  total_variable_cost_inr_t: number | null;
  material_co2_kg_t: number | null;
  chemistry_complete: boolean;
  unknown_chemistry_fields: string[];
  feasible: boolean;
  notes: string[];
};

export type FormulationStageResult = {
  level: string;
  name: string;
  purpose: string;
  inputs: string[];
  outputs: string[];
  key_results: Record<string, number | string | null>;
  assumptions: string[];
};

export type RetrofitCandidate = {
  candidate_id: string;
  name: string;
  components: RetrofitComponentShare[];
  feasible: boolean;
  pareto_efficient: boolean;
  rank: number | null;
  deterministic_score: number;
  predicted_output_tph: number | null;
  output_shortfall_tph: number;
  output_delta_vs_ppc_tph: number | null;
  electricity_delta_vs_ppc_kwh_t: number | null;
  thermal_delta_vs_ppc_kcal_kg: number | null;
  material_cost_delta_vs_ppc_inr_t: number | null;
  material_co2_delta_vs_ppc_kg_t: number | null;
  bottleneck_machine_name: string | null;
  route_compatibility_score: number;
  route_efficiency_score: number;
  electricity_kwh_t: number | null;
  thermal_kcal_kg: number | null;
  material_cost_inr_t: number | null;
  energy_cost_inr_t: number | null;
  total_variable_cost_inr_t: number | null;
  material_co2_kg_t: number | null;
  clinker_factor_percent: number;
  robustness_score: number;
  retrofit_complexity_score: number;
  chemistry: Chemistry;
  chemistry_complete: boolean;
  unknown_chemistry_fields: string[];
  missing_assets: RetrofitAssetGap[];
  stress_tests: RetrofitStressScenario[];
  formulation_chain: FormulationStageResult[];
  warnings: string[];
  calculation_trace: CalculationTraceStep[];
};

export type RetrofitStudyResult = {
  study_id: string;
  created_at: string;
  calculation_version: string;
  study_type: "ppc_to_lc3";
  request: {
    existing_ppc_blend_id: string;
    route_id: string;
    cost_book_id: string | null;
    target_output_tph: number;
    clinker_source: RetrofitReference | null;
    calcined_clay_source: RetrofitReference | null;
    limestone_source: RetrofitReference | null;
    gypsum_source: RetrofitReference | null;
    clay_supply_mode: "purchased_calcined_clay" | "onsite_calcination";
    raw_clay_material_id: string | null;
    clinker_bounds: PercentageBounds;
    calcined_clay_bounds: PercentageBounds;
    limestone_bounds: PercentageBounds;
    gypsum_bounds: PercentageBounds;
    clay_to_limestone_ratio_min: number;
    clay_to_limestone_ratio_max: number;
    raw_clay_to_calcined_yield: number;
    calcined_clay_reactivity_index: number;
    clay_kaolinite_percent: number;
    reference_clay_calciner_capacity_tph: number;
    reference_clay_calciner_electricity_kwh_t: number;
    reference_clay_calciner_thermal_kcal_kg: number;
    objective_weights: RetrofitObjectiveWeights;
    target_candidates: number;
  };
  baseline: {
    blend_id: string;
    blend_name: string;
    family: string;
    route_id: string;
    route_name: string;
    predicted_output_tph: number | null;
    electricity_kwh_t: number | null;
    thermal_kcal_kg: number | null;
    material_cost_inr_t: number | null;
    material_co2_kg_t: number | null;
    warnings: string[];
  };
  selected_candidate_id: string | null;
  candidates: RetrofitCandidate[];
  algorithm: string;
  assumptions: { key: string; value: string; basis: string }[];
  data_to_replace: string[];
  warnings: string[];
};
