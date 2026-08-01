export type Evidence = {
  evidence_class: string;
  source_title: string;
  source_uri?: string | null;
  page?: string | null;
  note?: string | null;
};

export type Chemistry = {
  cao: number;
  sio2: number;
  al2o3: number;
  fe2o3: number;
  mgo: number;
  so3: number;
  na2o: number;
  k2o: number;
  loi: number;
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
  location?: string | null;
  processing_state: string;
  applicable_blend_classes: string[];
  chemistry: Chemistry;
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
  throughput_factor_t_stage_per_t_cement: number;
  actual_throughput_tph: number;
  effective_capacity_tph: number;
  cement_equivalent_capacity_tph: number | null;
  load_percent: number;
  electricity_kwh_t_cement: number;
  thermal_kcal_kg_cement: number;
};

export type MaterialRunMetric = {
  material_id: string;
  material_name: string;
  material_type: string;
  percentage: number;
  tonnes_per_hour: number;
  tonnes_per_run: number;
  applied_unit_cost_inr_t: number | null;
  cost_basis: string;
  cost_inr_t_cement: number | null;
  co2_kg_t_cement: number | null;
  evidence_class: string;
};

export type Result = {
  run_id: string;
  created_at: string;
  calculation_version: string;
  request: {
    blend_id: string;
    route_id: string;
    cost_book_id?: string | null;
    target_output_tph: number;
    duration_hours: number;
    electricity_inr_kwh: number;
    thermal_fuel_inr_mkcal: number;
    raw_meal_to_clinker_yield: number;
  };
  blend_snapshot: Blend | null;
  route_snapshot: Route | null;
  cost_book_snapshot: CostBook | null;
  material_snapshots: Material[];
  machine_snapshots: Machine[];
  chemistry: Chemistry;
  achievable_output_tph: number;
  total_output_tonnes: number;
  bottleneck_tph: number;
  bottleneck_machine_id: string | null;
  bottleneck_machine_name: string | null;
  electricity_kwh_t: number;
  thermal_kcal_kg: number;
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
