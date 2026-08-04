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

export type RouteAnalysis = {
  route_id: string;
  route_name: string;
  route_kind: string;
  description: string;
  flow_summary: string;
  compatible: boolean;
  compatibility_score: number;
  predicted_output_tph: number | null;
  bottleneck_machine_name: string | null;
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

export type ValidationMessage = {
  severity: "block" | "warning" | "info";
  code: string;
  message: string;
};

export type MachineRunMetric = {
  node_id: string;
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
  lsf: number | null;
  silica_modulus: number | null;
  alumina_modulus: number | null;
  estimated_clinker_yield: number | null;
  objective_error: number;
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
