/**
 * services/types.ts — SupplyGuard AI Frontend Type Contracts
 *
 * All interfaces mirror actual Pydantic backend response schemas.
 * No fields are invented. Every field exists in a confirmed backend model.
 *
 * CRITICAL SCORE SCALE NOTE:
 *   ShipmentRisk.total_score    → 0–100 (engine scale) — USE for risk gauge
 *   Shipment.current_risk_score → 0–1   (DB field)     — NEVER use for risk gauge
 *   RouteScore.total_score      → 0–1   — display as ×100%
 *   FleetMatchScore.total_score → 0–1   — display as ×100%
 *   All r_* sub-scores          → 0–1   — Tailwind bar width = value × 100%
 */

// ---------------------------------------------------------------------------
// Severity / Status union types
// ---------------------------------------------------------------------------

export type RiskSeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
export type ColdChainSeverity = 'OK' | 'WARNING' | 'HIGH' | 'CRITICAL' | 'UNKNOWN'
export type CoolingCapability = 'ULTRA_COLD' | 'STANDARD_COLD' | 'AMBIENT'

// ---------------------------------------------------------------------------
// From schemas/shipment.py → ShipmentResponse
// ---------------------------------------------------------------------------

export interface Shipment {
  id: string
  tracking_number: string | null
  origin: string
  destination: string
  cargo_type: string
  cargo_category: string
  required_temp_min_c: number
  required_temp_max_c: number
  status: string
  assigned_vehicle_id: string | null
  carrier_id: string | null
  estimated_departure: string | null  // ISO datetime string
  estimated_arrival: string | null    // ISO datetime string
  /** 0–1 DB field — NOT the engine risk score. Never use for the risk gauge. */
  current_risk_score: number | null
  current_lat: number | null
  current_lon: number | null
  current_location_name: string | null
}

// ---------------------------------------------------------------------------
// From schemas/engine_responses.py → ShipmentRiskResponse
// ---------------------------------------------------------------------------

export interface ShipmentRisk {
  shipment_id: string
  /** 0–100 ENGINE SCALE — always use this for the risk gauge display */
  total_score: number
  severity: RiskSeverity
  r_disruption: number   // 0–1
  r_weather: number      // 0–1
  r_route: number        // 0–1
  r_cold_chain: number   // 0–1
  r_business: number     // 0–1
  contributing_disruption_ids: string[]
  weather_fallback: boolean
  cold_chain_fallback: boolean
  route_fallback: boolean
  assessed_at: string
}

// ---------------------------------------------------------------------------
// From schemas/engine_responses.py → ColdChainResponse
// ---------------------------------------------------------------------------

export interface ColdChainStatus {
  shipment_id: string
  telemetry_id: string | null
  cargo_rule_found: boolean
  is_in_excursion: boolean
  is_destructive: boolean
  cargo_temp_c: number | null
  allowed_min_c: number | null
  allowed_max_c: number | null
  max_allowable_excursion_temp_c: number | null
  /** Signed: positive = too warm, negative = too cold */
  deviation_c: number | null
  severity: ColdChainSeverity
  excursion_duration_minutes: number | null
  compliance_standard: string | null
  cargo_category: string
  grade: string | null
  assessed_at: string
}

// ---------------------------------------------------------------------------
// From schemas/engine_responses.py → RouteScoreResponse + RouteOptimizerResponse
// ---------------------------------------------------------------------------

export interface RouteScore {
  route_id: string
  route_name: string
  /** 0–1 — display as ×100% */
  total_score: number
  eta_hours: number
  eta_factor: number
  cost_factor: number
  disruption_factor: number
  weather_factor: number
  cold_chain_factor: number
  recommended: boolean
  warnings: string[]
}

export interface RouteRecommendation {
  shipment_id: string
  scored_routes: RouteScore[]
  no_route_found: boolean
  assessed_at: string
}

// ---------------------------------------------------------------------------
// From schemas/engine_responses.py → FleetMatchScoreResponse + FleetMatchResponse
// ---------------------------------------------------------------------------

export interface FleetMatchScore {
  asset_id: string
  vehicle_type: string
  cooling_capability: CoolingCapability
  /** 0–1 — display as ×100% */
  total_score: number
  proximity_km: number | null
  proximity_score: number
  cargo_compat_score: number
  refrigeration_score: number
  capacity_score: number
  availability_score: number
  estimated_shipment_weight_kg: number
  asset_capacity_kg: number
  recommended: boolean
}

export interface FleetMatch {
  shipment_id: string
  scored_assets: FleetMatchScore[]
  no_asset_found: boolean
  assessed_at: string
}

// ---------------------------------------------------------------------------
// From schemas/disruption.py → DisruptionResponse
// ---------------------------------------------------------------------------

export interface Disruption {
  id: string
  type: string
  severity: string
  title: string
  affected_corridor: string | null
  start_time: string
  expected_end_time: string | null
  impact_delay_hours: number | null
  recommended_reroute: string | null
  geometry_lat: number | null
  geometry_lon: number | null
}

// ---------------------------------------------------------------------------
// From schemas/engine_responses.py → AffectedShipmentEntry + DisruptionImpactResponse
// ---------------------------------------------------------------------------

export interface AffectedShipment {
  shipment_id: string
  shipment_status: string
  distance_km: number
}

export interface DisruptionImpact {
  disruption_id: string
  disruption_type: string
  disruption_severity: string
  proximity_radius_km: number
  affected_shipments: AffectedShipment[]
  assessed_at: string
}

// ---------------------------------------------------------------------------
// From schemas/fleet_asset.py → FleetAssetResponse
// ---------------------------------------------------------------------------

export interface FleetAsset {
  id: string
  vehicle_type: string
  license_plate: string | null
  status: string
  fuel_type: string | null
  cooling_system_type: string | null
  capacity_kg: number
  battery_charge_percent: number | null
  fuel_level_percent: number | null
  driver_name: string | null
  telemetry_stream_id: string | null
  current_lat: number | null
  current_lon: number | null
}

// ---------------------------------------------------------------------------
// From schemas/route.py → RouteResponse (map/catalog data, not optimizer output)
// ---------------------------------------------------------------------------

export interface RouteWaypoint {
  name: string
  lat: number
  lon: number
}

export interface ColdStorageDepot {
  name: string
  lat: number
  lon: number
}

export interface RouteData {
  route_id: string
  name: string
  origin: string
  destination: string
  distance_km: number
  typical_duration_hours: number
  highways: string[] | null
  waypoints: RouteWaypoint[] | null
  cold_storage_depots: ColdStorageDepot[] | null
}

// ---------------------------------------------------------------------------
// From schemas/ai_response.py → AIExplanationResponse
// ---------------------------------------------------------------------------

export interface AIExplanation {
  use_case: string
  entity_id: string
  headline: string
  explanation: string
  recommended_action: string
  /** Severity always comes from the deterministic engine — never from the model */
  severity: string
  /** True = live Granite call succeeded; False = deterministic fallback */
  ai_generated: boolean
  /** Model identifier when ai_generated=true; null when fallback */
  model_id: string | null
  generated_at: string
}

// ---------------------------------------------------------------------------
// From GET /health
// ---------------------------------------------------------------------------

export interface HealthResponse {
  status: string
  timestamp: string
}

// ---------------------------------------------------------------------------
// Carrier display-only lookup (no backend endpoint — display metadata only)
// ---------------------------------------------------------------------------

export const CARRIER_NAMES: Record<string, string> = {
  'CRR-401': 'FrostLine Logistics',
  'CRR-402': 'Apex Cargo Transporters',
  'CRR-403': 'Cascade Frozen Freight',
}
